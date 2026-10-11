"""T13 rejection witness through the public launcher using a retained baseline.

Run from the repository with the pinned U20 interpreter. Synthetic source and
authentication fixtures demonstrate behavior only, and confer no organizational
or Legal authorization. Repeated runs require a new --work-root; no files are
deleted or rewritten in the retained baseline.
"""
import argparse
from datetime import date, timedelta, datetime, timezone
import json
from pathlib import Path
import shutil
import sys

repo = Path.cwd()
sys.path[:0] = [str(repo / 'regulatory-change-impact-brief/scripts'), str(repo / 'tests')]
from rci.contracts import SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes
from rci.history import verify_archive
from rci.validate import validate_package
from runtime.test_feedback_remediation import _parse, _run, ARTIFACTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    previous = validate_package(args.baseline)
    target = next(a for a in previous[5]['state']['proposed_actions'] if
                  a['system_id'] == 'AI-007' and a['action_kind'] == 'review-rule-change')
    assert target['existing_due_date'] == target['proposed_due_date'] == '2026-09-04'
    old_request = next(r for r in previous[5]['state']['review_requests'] if r['required_reviewer'] == 'Legal')
    binding = next(b for b in previous[6]['state']['review_bindings'] if b['request_id'] == old_request['request_id'])
    reviewed = dict(root='history/' + previous[0]['run_id'], **{
        label:dict(snapshot_id=previous[index]['snapshot_id'], path=SNAPSHOT_PATHS[index],
            sha256=sha256_bytes((args.baseline / SNAPSHOT_PATHS[index]).read_bytes()))
        for label, index in [('stage06',5), ('stage07',6)]})
    identity = 'legal@synthetic.example'
    payload = dict(responder_identity=identity, responder_role='Legal',
        claimed_request_id=old_request['request_id'], claimed_run_id=previous[0]['run_id'],
        claimed_draft_version=old_request['draft_version'], claimed_subject_ids=[target['id']],
        claimed_source_versions=old_request['source_versions'], claimed_artifacts=binding['artifacts'],
        reviewer_response_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        outcome='rejected', reasons=['Synthetic reviewer rejects this exact proposal until independent owner readiness is supplied.'],
        conditions=[], reviewed_draft=reviewed)
    args.work_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(args.baseline, args.work_root / 'out', ignore=shutil.ignore_patterns('.staging'))
    paths = {key:args.work_root / (key + '.json') for key in ['feedback','policy','auth']}
    paths['feedback'].write_bytes(json_bytes(dict(feedback=[payload], carry_forward=True)))
    paths['policy'].write_bytes(json_bytes(dict(reviewers=[dict(identity=identity, roles=['Legal'],
        channels=['authenticated-operator'], system_ids=old_request['subject_system_ids'])])))
    paths['auth'].write_bytes(json_bytes(dict(identity=identity, channel='authenticated-operator',
        basis='Synthetic local operator proof only; no organizational authorization or real identity asserted.')))
    outcome, root, current = _run(args.work_root, feedback_path=paths['feedback'],
        reviewer_policy_path=paths['policy'], authentication_path=paths['auth'])
    state = current[5]['state']
    feedback, = state['feedback']
    action = next(a for a in state['proposed_actions'] if a['action_id'] == target['action_id'])
    assert feedback['match_status'] == 'matched' and feedback['authentication'] == 'verified'
    assert feedback['outcome'] == 'rejected' and not feedback['conditions']
    assert feedback['subject_ids'] == [action['id']]
    assert feedback['reviewed_draft'] == reviewed and feedback['claimed_artifacts'] == payload['claimed_artifacts']
    assert feedback['revalidation']['current_run_id'] == outcome['run_id']
    assert all(c['result'] == 'passed' for c in feedback['revalidation']['checks'].values())
    affected = [r for r in state['approval_requirements'] if r['feedback_ids']]
    assert len(affected) == 1
    assert affected[0]['subject_ids'] == [action['id']] and affected[0]['required_reviewer'] == 'Legal'
    assert affected[0]['status'] == 'rejected' and affected[0]['feedback_ids'] == [feedback['id']]
    assert all(r['status'] == 'pending' for r in state['approval_requirements'] if r not in affected)
    assert action['approval_status'] == 'rejected'
    assert all(a['approval_status'] == 'pending' for a in state['proposed_actions'] if a['id'] != action['id'])
    assert all(r['delivery_status'] == 'not-sent' and not r['delivery_evidence_ids'] for r in state['review_requests'])
    rows, brief, events = _parse(root)
    relevant = [r for r in rows if action['action_id'] in r['action_ids'].split(';')]
    assert relevant and all(r['approval_status'] == 'rejected' and r['proposed_due_date'] == '2026-09-04' for r in relevant)
    fields = brief['Action ' + action['action_id']]
    assert fields['Approval'] == 'rejected' and fields['Proposed date'] == fields['Existing operational date'] == '2026-09-04'
    event = events[action['action_id']]
    assert str(event['STATUS']) == 'TENTATIVE'  # Retained rejected draft, no calendar commitment.
    assert event.decoded('DTSTART') == date(2026,9,4) and event.decoded('DTEND') == date(2026,9,5)
    for text in [*(r['resolution_need'] for r in relevant), fields['Reviewer feedback'], str(event['DESCRIPTION'])]:
        assert 'Legal rejected; approval rejected' in text and payload['reasons'][0] in text
    archived = verify_archive(root / reviewed['root'])
    assert validate_package(archived.root) == previous
    for artifact in payload['claimed_artifacts']:
        prior_raw = (args.baseline / artifact['path']).read_bytes()
        assert (archived.root / artifact['path']).read_bytes() == prior_raw
        assert sha256_bytes(prior_raw) == artifact['sha256']
        candidate = root / '.staging' / outcome['run_id']
        assert (candidate / reviewed['root'] / artifact['path']).read_bytes() == prior_raw
    report = dict(synthetic_only=True, organizational_authorization_claimed=False,
        public_launcher=True, outcome=outcome, baseline=str(args.baseline), output=str(root),
        prior_run_id=previous[0]['run_id'], current_run_id=outcome['run_id'], action_id=action['action_id'],
        reviewed_draft=reviewed, prior_artifacts=payload['claimed_artifacts'],
        current_artifacts=[dict(path=name, sha256=sha256_bytes((root/name).read_bytes())) for name in ARTIFACTS],
        feedback=dict(match_status=feedback['match_status'], authentication=feedback['authentication'],
            outcome=feedback['outcome'], subject_ids=feedback['subject_ids'],
            conditions=feedback['conditions'], revalidation=feedback['revalidation']),
        assertions=dict(independent_csv_brief_ics=True, scoped_legal_rejection=True,
            other_reviewers_pending=True, other_actions_pending=True, original_dates_retained=True,
            prior_bindings_rehashed=True, prior_package_unchanged=True, requests_unsent=True))
    args.results.write_bytes(json_bytes(report))
    print(json.dumps(dict(current_run_id=outcome['run_id'], status=outcome['status'],
        package_acceptance=outcome['package_acceptance'], assertions='passed', results=str(args.results))))


if __name__ == '__main__':
    main()
