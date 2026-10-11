"""Inspect only the fresh submission occurrence and its preservation boundary."""
from datetime import datetime, timezone
from html import unescape
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / 'regulatory-change-impact-brief/scripts'))
from rci.contracts import SNAPSHOT_PATHS
from rci.decisions import enabled, producer_inventory, project
from rci.history import verify_archive
from rci.runtime import SKILL
from rci.validate import validate_package


def digest(path):
    with path.open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


spec = importlib.util.spec_from_file_location('u20_checker', REPO / 'docs/verification/check-u20.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
root = REPO / 'deliverables'
before_summary = json.loads((OUT / 'before.json').read_text())
inventory_path = REPO / before_summary['protected_inventory_path']
assert digest(inventory_path) == before_summary['protected_inventory_sha256']
before = json.loads(inventory_path.read_text())
outcome = json.loads((OUT / 'launcher.log').read_text())
assert outcome == json.loads((root / 'analysis/outcome.json').read_text())
assert outcome['supersedes_run_id'] == before['predecessor_run_id']
assert outcome['run_id'] != before['predecessor_run_id']
assert not outcome['missing_artifacts'] and not outcome['missing_snapshots']
inspection = checker.inspect(root, 'live')
(OUT / 'live-inspection.json').write_text(json.dumps(inspection, indent=2) + '\n')
chain = validate_package(root)
assert inspection['assigned_review_date'] == before['assigned_review_date'] == '2026-08-26'
assert digest(REPO / 'config/review.u20.json') == before['config_sha256']
assert enabled(chain[0])
assert json.loads((root / 'analysis/producer-code.json').read_text()) == producer_inventory(SKILL)
decisions = [decision for snapshot in chain for decision in snapshot['decisions']]
assert decisions and len({d['id'] for d in decisions}) == len(decisions)
assert all(outcome['run_id'] in d['id'] for d in decisions)
assert all(snapshot['decisions'] == project(snapshot) for snapshot in chain)
model = chain[5]['state']['export_model']
assert model['decisions'] == decisions
brief = unescape((root / 'compliance-brief.md').read_text())
assert all(d['id'] in brief and d['chosen_behavior'] in brief and d['rationale'] in brief for d in decisions)
archive_root = root / 'history' / before['predecessor_run_id']
archive = verify_archive(archive_root)
prior_chain = validate_package(archive_root)
assert prior_chain[0]['run_id'] == before['predecessor_run_id']
prior_attempts = {a['id'] for a in prior_chain[1]['state']['attempts']}
current_attempts = {a['id'] for a in chain[1]['state']['attempts']}
assert current_attempts and not prior_attempts & current_attempts
archive_paths = {row['path'] for row in archive.manifest['inventory']}
preserved_in_archive = 0
unchanged_at_original_path = 0
for path, expected in before['protected_files'].items():
    actual_path = REPO / path
    relative = path.removeprefix('deliverables/')
    if path.startswith('deliverables/') and relative in archive_paths:
        actual_path = archive_root / relative
        preserved_in_archive += 1
    else:
        unchanged_at_original_path += 1
    assert actual_path.is_file() and digest(actual_path) == expected, str(actual_path)
assert not (root / '.incomplete-replacement.json').exists()
if outcome['status'] == 'blocked':
    assert outcome['publication_status'] == 'blocked'
    assert not outcome['package_acceptance']
    assert not (root / '.completion.json').exists()
    assert chain[2]['state']['authority_blockers']
    assert not chain[2]['state']['binding_rules']
    assert not model['impacts'] and model['unresolved_coverage']
    assert not model['actions'] and inspection['calendar_events'] == 0
    assert all(r['delivery_status'] == 'not-sent' for r in model['review_requests'])
    assert not model.get('feedback')
result = {
    'checked_at': datetime.now(timezone.utc).isoformat(),
    'run_id': outcome['run_id'], 'predecessor_run_id': before['predecessor_run_id'],
    'outcome': outcome, 'assigned_review_date': inspection['assigned_review_date'],
    'decision_counts_by_stage': inspection['decision_counts'],
    'exported_decision_count': len(decisions),
    'decision_reconstruction_and_brief_propagation': 'passed',
    'current_producer_inventory_match': 'passed',
    'fresh_attempt_ids_disjoint_from_predecessor': 'passed',
    'mechanical_validation': inspection['mechanical_validation'],
    'archive_root': str(archive_root.relative_to(REPO)),
    'archive_inventory_sha256': archive.inventory_sha256,
    'archive_hash_and_package_validation': 'passed',
    'preservation': {'protected_file_count': len(before['protected_files']),
        'preserved_in_predecessor_archive': preserved_in_archive,
        'unchanged_at_original_path': unchanged_at_original_path,
        'changed_or_missing': []},
    'authority_blockers': chain[2]['state']['authority_blockers'],
    'source_statuses': inspection['sources'],
    'csv_rows': inspection['csv_rows'], 'calendar_events': inspection['calendar_events'],
    'supported_impacts': len(model['impacts']), 'proposed_actions': len(model['actions']),
    'review_request_count': len(model['review_requests']),
    'snapshots': inspection['snapshots'], 'artifacts': inspection['artifacts'],
    'scope': 'One fresh live occurrence; package and preservation checks only. No regression rerun.'}
(OUT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('run_id', 'decision_counts_by_stage',
    'exported_decision_count', 'mechanical_validation', 'preservation')}))
