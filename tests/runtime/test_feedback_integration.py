"""Public pipeline feedback intake against an actual retained synthetic draft."""
from copy import deepcopy
from datetime import datetime, timezone

from integration.pipeline_harness import execute
from rci.contracts import SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes
from rci.history import verify_archive
from rci.snapshots import accept_package
from rci.validate import validate_package


def test_authenticated_prior_draft_approval_is_scoped_and_invalid_binding_is_quarantined(tmp_path):
    first, root = execute(tmp_path, launcher=True)
    assert first['package_acceptance'] and first['production_package'], first
    previous = validate_package(root)
    old_state = previous[5]['state']
    target = next(a for a in old_state['proposed_actions'] if
                  a['system_id'] == 'AI-007' and a['action_kind'] == 'review-rule-change')
    other = next(a for a in old_state['proposed_actions'] if a['action_id'] != target['action_id'])
    request = next(r for r in old_state['review_requests'] if r['required_reviewer'] == 'Legal')
    binding = next(b for b in previous[6]['state']['review_bindings'] if b['request_id'] == request['request_id'])
    assert {target['id'], other['id']} <= set(request['subject_ids'])
    identity = 'legal@synthetic.example'
    reviewed = dict(root='history/' + first['run_id'], **{
        label:dict(snapshot_id=previous[i]['snapshot_id'], path=SNAPSHOT_PATHS[i],
                   sha256=sha256_bytes((root / SNAPSHOT_PATHS[i]).read_bytes()))
        for label, i in (('stage06', 5), ('stage07', 6))})
    payload = dict(responder_identity=identity, responder_role='Legal',
        claimed_request_id=request['request_id'], claimed_run_id=first['run_id'],
        claimed_draft_version=request['draft_version'], claimed_subject_ids=[target['id']],
        claimed_source_versions=request['source_versions'], claimed_artifacts=binding['artifacts'],
        reviewer_response_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        outcome='approved', reasons=['Synthetic authenticated Legal review approves only this exact action basis.'],
        conditions=[], reviewed_draft=reviewed)
    invalid = deepcopy(payload)
    invalid['claimed_subject_ids'] = [other['id']]
    invalid['claimed_artifacts'][0]['sha256'] = 'sha256:' + '0' * 64
    paths = {name:tmp_path / (name + '.json') for name in ('feedback', 'reviewer-policy', 'authentication')}
    paths['feedback'].write_bytes(json_bytes(dict(feedback=[payload, invalid], carry_forward=True)))
    paths['reviewer-policy'].write_bytes(json_bytes(dict(reviewers=[dict(identity=identity, roles=['Legal'],
        channels=['authenticated-operator'], system_ids=request['subject_system_ids'])])))
    paths['authentication'].write_bytes(json_bytes(dict(identity=identity, channel='authenticated-operator',
        basis='Synthetic test: separately verified local operator session; not a live identity assertion')))

    second, root = execute(tmp_path, launcher=True, feedback_path=paths['feedback'],
        reviewer_policy_path=paths['reviewer-policy'], authentication_path=paths['authentication'])
    assert second['package_acceptance'] and second['production_package'], second
    current = validate_package(root)
    assert current == accept_package(root)
    assert second['run_id'] != first['run_id']
    state = current[5]['state']
    current_target = next(a for a in state['proposed_actions'] if a['action_id'] == target['action_id'])
    matched, quarantined = state['feedback']
    assert matched['match_status'] == 'matched', matched
    assert matched['authentication'] == 'verified'
    assert matched['subject_ids'] == [current_target['id']]
    assert matched['claimed_run_id'] == first['run_id']
    assert matched['revalidation']['current_run_id'] == second['run_id']
    assert matched['reviewed_draft'] == reviewed
    assert all(check['result'] == 'passed' for check in matched['revalidation']['checks'].values())
    assert quarantined['match_status'] == 'unresolved'
    assert quarantined['request_id'] is None and quarantined['subject_ids'] == []
    assert 'revalidation' not in quarantined

    approved = [a for a in state['approval_requirements'] if a['status'] == 'approved']
    assert len(approved) == 1
    assert approved[0]['required_reviewer'] == 'Legal'
    assert approved[0]['subject_ids'] == [current_target['id']]
    assert approved[0]['feedback_ids'] == [matched['id']]
    assert all(a['status'] == 'pending' for a in state['approval_requirements'] if a is not approved[0])
    assert current_target['approval_status'] == 'pending'  # Other required reviewers have not approved.
    assert current_target['existing_due_date'] == target['existing_due_date']
    assert current_target['proposed_due_date'] == target['proposed_due_date']
    assert all(r['delivery_status'] == 'not-sent' and not r['delivery_evidence_ids'] for r in state['review_requests'])
    for source, retained in (('feedback', 'feedback-input'), ('reviewer-policy', 'reviewer-policy'),
                             ('authentication', 'authentication-context')):
        assert (root / ('analysis/' + retained + '.json')).read_bytes() == paths[source].read_bytes()
    archive = verify_archive(root / reviewed['root'])
    assert validate_package(archive.root) == previous
    assert all(a['status'] == 'pending' for a in previous[5]['state']['approval_requirements'])
    candidate = root / '.staging' / second['run_id']
    assert (candidate / reviewed['root'] / SNAPSHOT_PATHS[6]).read_bytes() == \
           (archive.root / SNAPSHOT_PATHS[6]).read_bytes()
    recorded = parse_json((root / 'analysis/prior-inspection.json').read_bytes())
    assert recorded['accepted'] and recorded['run_id'] == first['run_id']
