"""G5 integrated history/corruption/fresh recovery with synthetic host/transport."""
from datetime import datetime

from integration.pipeline_harness import execute
from rci.contracts import SNAPSHOT_PATHS, STAGES, parse_json, sha256_bytes
from rci.history import inspect_current, verify_archive
from rci.snapshots import COMPLETION_MARKER, INCOMPLETE_MARKER, accept_package
from rci.validate import validate_package


def attempts(chain):
    return {a['attempt_key']:a for a in chain[1]['state']['attempts']}


def assert_fresh(previous, current):
    earlier, later = attempts(previous), attempts(current)
    assert earlier and later and set(earlier).isdisjoint(later)
    instant = lambda s:datetime.fromisoformat(s.replace('Z', '+00:00'))
    assert min(instant(a['started_at']) for a in later.values()) > \
           max(instant(a['retrieved_at']) for a in earlier.values())
    assert {s['snapshot_id'] for s in previous}.isdisjoint(s['snapshot_id'] for s in current)
    assert {s['run_id'] for s in previous}.isdisjoint(s['run_id'] for s in current)


def test_public_run_changed_source_preserved_history_corruption_and_fresh_recovery(tmp_path):
    first, root = execute(tmp_path, launcher=True)
    assert first['production_package'] and first['package_acceptance'], first
    assert first['launcher_exit_code'] == (0 if first['status'] == 'complete' else 2)
    assert first['test_host_calls'] == ['authority', 'reconciliation', 'impacts']
    initial = validate_package(root)
    assert [s['stage'] for s in initial] == list(STAGES)
    assert initial == accept_package(root)
    first_bytes = {path:(root / path).read_bytes() for path in SNAPSHOT_PATHS}
    first_hashes = {a['source_id']:a['content_hash'] for a in initial[1]['state']['attempts']
                    if a['content_hash'] is not None}
    (root / 'operator-notes.txt').write_text('Unrelated operator file survives all replacements.')

    second, root = execute(tmp_path, mutation='closed')
    assert second['production_package'] and second['package_acceptance'], second
    changed = validate_package(root)
    assert_fresh(initial, changed)
    assert changed[0]['state']['supersedes_run_id'] == first['run_id']
    second_hashes = {a['source_id']:a['content_hash'] for a in changed[1]['state']['attempts']
                     if a['content_hash'] is not None}
    assert any(first_hashes[s] != second_hashes[s] for s in first_hashes.keys() & second_hashes.keys())
    recomputation = parse_json((root / 'analysis/recomputation.json').read_bytes())
    assert recomputation['earliest_changed_sequence'] == 2, recomputation
    assert recomputation['recompute_sequences'] == list(range(1, 8))
    original_archive = verify_archive(root / ('history/' + first['run_id']))
    assert validate_package(original_archive.root) == initial
    assert all((original_archive.root / path).read_bytes() == raw for path, raw in first_bytes.items())

    damaged = b'Synthetic corruption of the current brief; original evidence must survive.\n'
    (root / 'compliance-brief.md').write_bytes(damaged)
    inspection = inspect_current(root, validator=validate_package)
    assert not inspection['accepted'] and inspection['run_id'] == second['run_id']
    row = next(r for r in inspection['inventory'] if r['path'] == 'compliance-brief.md')
    assert row['availability'] == 'corrupt' and row['sha256'] == sha256_bytes(damaged)
    assert (root / COMPLETION_MARKER).exists()  # A stale success flag cannot mask actual damage.

    third, root = execute(tmp_path, mutation='closed', launcher=True)
    assert third['production_package'] and third['package_acceptance'], third
    repaired = validate_package(root)
    assert_fresh(changed, repaired)
    assert repaired == accept_package(root)
    assert repaired[0]['state']['supersedes_run_id'] == second['run_id']
    recorded_inspection = parse_json((root / 'analysis/prior-inspection.json').read_bytes())
    assert not recorded_inspection['accepted'] and recorded_inspection['run_id'] == second['run_id']
    assert any(r['path'] == 'compliance-brief.md' and r['availability'] == 'corrupt'
               for r in recorded_inspection['inventory'])
    failed_occurrence = verify_archive(root / ('history/' + second['run_id']))
    assert (failed_occurrence.root / 'compliance-brief.md').read_bytes() == damaged
    assert any(r['path'] == 'compliance-brief.md' and r['availability'] == 'corrupt'
               for r in failed_occurrence.manifest['inventory'])
    recomputation = parse_json((root / 'analysis/recomputation.json').read_bytes())
    assert recomputation['earliest_changed_sequence'] is None, recomputation
    assert recomputation['recompute_sequences'] == list(range(1, 8))
    assert not (root / INCOMPLETE_MARKER).exists()
    assert (root / 'operator-notes.txt').read_text() == 'Unrelated operator file survives all replacements.'
    assert validate_package(original_archive.root) == initial
    assert all((root / path).is_file() for path in SNAPSHOT_PATHS)
    assert all((root / name).is_file() for name in (
        'impact-register.csv', 'compliance-brief.md', 'action-calendar.ics'))
