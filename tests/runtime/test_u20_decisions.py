"""E04 runtime decisions, using real producers and synthetic read/host seams."""
from copy import deepcopy
from html import unescape
from pathlib import Path
import shutil

import pytest

from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes
from rci.decisions import (CAPABILITY_PATH, LEGACY_PRODUCERS, PRODUCER_PATH,
                           producer_inventory, validate_producer)
from rci.evidence import EvidenceStore
from rci.runner import validate_slice
from rci.snapshots import read_chain, stage_records, validate_snapshot
from rci.validate import validate_package
from runtime.test_u07 import DECLARED, Replay, execute as scope_execute
from runtime.test_u17_complete import execute_full
from integration.pipeline_harness import execute


@pytest.mark.parametrize('declared', [False, True])
def test_scope_date_and_actual_source_routes_emit_decisions(scope_execute, declared):
    outcome, root = scope_execute(DECLARED if declared else None, reader_factory=Replay)
    assert outcome['capture_slice_complete'], outcome
    first, second = read_chain(root, count=2)
    by_summary = {d['summary']: d for d in first['decisions']}
    scope = by_summary['Scope input selection']
    basis, = first['state']['scope_basis']
    assert basis['id'] in scope['source_basis']
    assert ('declared' if declared else 'discovered') in scope['chosen_behavior']
    assert not scope['evidence_ids']  # Stage 01 direct basis, no forward links.
    date = by_summary['Assigned date precision encoding']
    assert first['state']['as_of'] in date['chosen_behavior']
    assert 'intraday' in date['tradeoffs'][0]
    assert len(second['decisions']) == len(second['state']['sources'])
    for source in second['state']['sources']:
        decision = next(d for d in second['decisions'] if d['summary'] == 'Source access: ' + source['source_id'])
        assert source['locator'] in decision['source_basis']
        assert set(source['attempt_ids']) <= set(decision['source_basis'])
        attempts = [a for a in second['state']['attempts'] if a['id'] in source['attempt_ids']]
        assert all(a['adapter'] in decision['chosen_behavior'] and a['outcome'] in decision['chosen_behavior'] for a in attempts)
        assert all(a['selection_reason'] in decision['chosen_behavior'] for a in attempts)
        assert decision['status'] == 'provisional-engineering'
    evidence = {e['id'] for e in second['state']['evidence']}
    assert any(d['evidence_ids'] for d in second['decisions'])
    assert all(set(d['evidence_ids']) <= evidence for d in second['decisions'])


def assert_export(chain, root):
    decisions = [d for s in chain[:5] for d in s['decisions']]
    assert chain[5]['state']['export_model']['decisions'] == decisions
    assert len({d['id'] for d in decisions}) == len(decisions)
    assert all(f"record:{chain[0]['run_id']}:" in d['id'] for d in decisions)
    brief = unescape((root / 'compliance-brief.md').read_text())
    for decision in decisions:
        assert decision['id'] in brief and decision['chosen_behavior'] in brief
    return next(d for d in chain[4]['decisions'] if d['summary'] == 'Draft continuation or deferral')


def test_complete_launcher_exports_substantive_decision_trail(tmp_path):
    outcome, root, exit_code, _ = execute_full(tmp_path)
    assert outcome['status'] == 'complete' and exit_code == 0, outcome
    chain = validate_package(root)
    disposition = assert_export(chain, root)
    assert 'complete draft' in disposition['chosen_behavior']
    assert disposition['evidence_ids']


@pytest.mark.parametrize('blocked', [False, True])
def test_partial_and_blocked_launcher_export_actual_disposition(tmp_path, blocked):
    outcome, root = execute(tmp_path, launcher=True, unavailable_authority=blocked)
    assert outcome['status'] == ('blocked' if blocked else 'partial'), outcome
    if blocked:
        chain = validate_package(root)
        decision = assert_export(chain, root)
        assert 'Defer' in decision['chosen_behavior']
        assert not outcome['package_acceptance'] and not (root / '.completion.json').exists()
        assert chain[-1]['state']['publication_status'] == 'blocked'
    else:
        decision = assert_export(validate_package(root), root)
        assert 'partial draft' in decision['chosen_behavior']


def test_recovery_decision_bound_to_preserved_occurrence(tmp_path):
    initial, root = execute(tmp_path, launcher=True)
    assert initial['package_acceptance'], initial
    original = validate_package(root)
    damaged = b'Synthetic damage retained for E04 recovery test.\n'
    (root / 'compliance-brief.md').write_bytes(damaged)
    repaired, root = execute(tmp_path, launcher=True)
    assert repaired['package_acceptance'], repaired
    chain = validate_package(root)
    decision = next(d for d in chain[0]['decisions'] if d['summary'] == 'Fresh run supersession and recovery')
    assert initial['run_id'] in decision['source_basis']
    assert 'recovery' in decision['chosen_behavior']
    assert chain[0]['state']['change_reason'] in decision['source_basis']
    assert (root / 'history' / initial['run_id'] / 'compliance-brief.md').read_bytes() == damaged
    assert {a['attempt_key'] for a in original[1]['state']['attempts']}.isdisjoint(
        a['attempt_key'] for a in chain[1]['state']['attempts'])
    assert_export(chain, root)


@pytest.mark.parametrize('mutation', ['omit', 'behavior', 'basis', 'duplicate', 'evidence'])
def test_decision_projection_rejects_semantic_tampering(scope_execute, mutation):
    _, root = scope_execute(DECLARED, reader_factory=Replay)
    chain = read_chain(root, count=2)
    actual = deepcopy(chain[1])
    decision = next(d for d in actual['decisions'] if d['evidence_ids'])
    if mutation == 'omit': actual['decisions'].remove(decision)
    elif mutation == 'behavior': decision['chosen_behavior'] = 'All sources verified and approved.'
    elif mutation == 'basis': decision['source_basis'] = ['invented authority']
    elif mutation == 'duplicate': actual['decisions'].append(deepcopy(decision))
    else: decision['evidence_ids'] = []
    actual['produced_record_ids'] = [r['id'] for r in stage_records(actual)]
    with pytest.raises(ContractError, match='decision|duplicate'):
        validate_snapshot(actual, root=root, upstream=chain[:1])


def rewrite_prefix(root, chain):
    for snapshot in chain:
        snapshot['produced_record_ids'] = [r['id'] for r in stage_records(snapshot)]
    (root / SNAPSHOT_PATHS[0]).write_bytes(json_bytes(chain[0]))
    chain[1]['predecessor']['sha256'] = sha256_bytes((root / SNAPSHOT_PATHS[0]).read_bytes())
    (root / SNAPSHOT_PATHS[1]).write_bytes(json_bytes(chain[1]))


@pytest.mark.parametrize('witness', ['inventory', 'none-current', 'none-later', 'bundle-later'])
def test_new_producer_cannot_downgrade_to_legacy_by_removing_profile(scope_execute, monkeypatch, tmp_path, witness):
    from rci import runner, runtime
    outcome, root = scope_execute(DECLARED, reader_factory=Replay)
    chain = read_chain(root, count=2)
    original_fingerprint = chain[0]['state']['code_fingerprint']
    assert sha256_bytes((root / PRODUCER_PATH).read_bytes()) == original_fingerprint
    if witness != 'inventory':
        (root / PRODUCER_PATH).unlink()  # Remove only this fresh test's witness.
    if witness == 'bundle-later':
        shutil.copytree(runtime.SKILL, root / runtime.SKILL.name)
    if witness.endswith('later'):
        later = tmp_path / 'later' / runtime.SKILL.name
        shutil.copytree(runtime.SKILL, later)
        path = later / 'scripts/rci/runner.py'
        path.write_bytes(path.read_bytes() + b'\n# Simulated later producer.\n')
        monkeypatch.setattr(runner, 'SKILL', later)
        monkeypatch.setattr(runtime, 'SKILL', later)
        assert runner._code_fingerprint() != original_fingerprint
    chain[0]['state']['extensions'].pop('u20_decisions')
    for snapshot in chain:
        snapshot['decisions'] = []
    rewrite_prefix(root, chain)
    assert chain[0]['state']['code_fingerprint'] == original_fingerprint
    with pytest.raises(ContractError, match='decision|producer|profile'):
        validate_slice(EvidenceStore(root, outcome['run_id']))


@pytest.mark.parametrize('mutation', ['malformed', 'mismatched', 'contradictory-pin'])
def test_producer_inventory_integrity(scope_execute, mutation):
    outcome, root = scope_execute(DECLARED, reader_factory=Replay)
    chain = read_chain(root, count=2)
    path = root / PRODUCER_PATH
    if mutation == 'malformed':
        path.write_bytes(b'[]\n')
    elif mutation == 'mismatched':
        inventory = parse_json(path.read_bytes())
        inventory[CAPABILITY_PATH] = 'sha256:' + '0' * 64
        path.write_bytes(json_bytes(inventory))
    else:
        chain[0]['state']['code_fingerprint'] = next(iter(LEGACY_PRODUCERS))
        rewrite_prefix(root, chain)
    with pytest.raises(ContractError, match='producer code inventory'):
        validate_slice(EvidenceStore(root, outcome['run_id']))


@pytest.mark.parametrize('claimed_fingerprint', list(LEGACY_PRODUCERS))
def test_new_scope_cannot_claim_legacy_producer_without_witness(scope_execute, claimed_fingerprint):
    outcome, root = scope_execute(DECLARED, reader_factory=Replay)
    chain = read_chain(root, count=2)
    (root / PRODUCER_PATH).unlink()
    chain[0]['state']['extensions'].pop('u20_decisions')
    chain[0]['state']['code_fingerprint'] = claimed_fingerprint
    for snapshot in chain:
        snapshot['decisions'] = []
    rewrite_prefix(root, chain)
    with pytest.raises(ContractError, match='scope differs from exact legacy witness'):
        validate_slice(EvidenceStore(root, outcome['run_id']))


def test_legacy_pin_cannot_override_conflicting_retained_bundle(scope_execute):
    from rci.runtime import SKILL
    _, root = scope_execute(DECLARED, reader_factory=Replay)
    first = read_chain(root, count=2)[0]
    (root / PRODUCER_PATH).unlink()
    first['state']['extensions'].pop('u20_decisions')
    first['state']['code_fingerprint'] = next(iter(LEGACY_PRODUCERS))
    shutil.copytree(SKILL, root / SKILL.name)
    with pytest.raises(ContractError, match='fingerprint differs from retained bundle'):
        validate_producer(root, first)


@pytest.mark.parametrize('fingerprint,witness', list(LEGACY_PRODUCERS.items()))
def test_legacy_producer_pin_has_exact_pre_remediation_witness(fingerprint, witness):
    repository = Path(__file__).resolve().parents[2]
    portable = repository / 'docs/verification/u20/remediation/legacy-producers'
    provenance = parse_json((portable / 'provenance.json').read_bytes())[fingerprint]
    relative, expected = witness
    assert provenance['original_scope_path'] == relative
    assert provenance['scope_sha256'] == expected
    path = portable / provenance['scope_copy']
    assert sha256_bytes(path.read_bytes()) == expected
    first = parse_json(path.read_bytes())
    assert first['state']['code_fingerprint'] == fingerprint
    assert 'u20_decisions' not in first['state']['extensions']
    if 'inventory_copy' in provenance:
        inventory = parse_json((portable / provenance['inventory_copy']).read_bytes())
        assert CAPABILITY_PATH not in inventory
        assert sha256_bytes(json_bytes(inventory)) == fingerprint
    else:
        baseline_bytes = (portable / provenance['baseline_copy']).read_bytes()
        assert sha256_bytes(baseline_bytes) == provenance['baseline_sha256']
        baseline = parse_json(baseline_bytes)
        assert baseline['files'][relative] == expected
    validate_producer(portable, first)


def test_profile_present_intermediate_package_needs_no_retroactive_inventory(scope_execute):
    outcome, root = scope_execute(DECLARED, reader_factory=Replay)
    (root / PRODUCER_PATH).unlink()
    validate_slice(EvidenceStore(root, outcome['run_id']))
