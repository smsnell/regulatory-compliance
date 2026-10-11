"""E07 public workflow: synthetic authenticated conditions and changed drafts.

The reviewer roster and operator proof are deliberately synthetic. These runs
exercise matching and exports, and confer no company or legal authorization.
"""
from copy import deepcopy
import csv
from datetime import date, datetime, timezone, timedelta
from html import unescape
import io
import shutil
from unittest.mock import patch

from icalendar import Calendar
import pytest

from integration.pipeline_harness import execute
from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes
from rci.history import verify_archive
from rci.reviews import _basis, match_feedback
from rci.snapshots import accept_package
from rci.validate import validate_artifacts, validate_package
from runtime.test_u10 import CompanyReplay, REPORT
from runtime.test_u11 import CONTROL
from runtime.test_u13 import review_case


ARTIFACTS = ('impact-register.csv', 'compliance-brief.md', 'action-calendar.ics')
CONDITION = 'Obtain independent system-owner readiness evidence before committing this date.'
TASK = 'Review scoped change: ' + CONTROL + ' (learner chat)'


def test_dated_action_basis_remaps_only_its_generated_source_row_pointer():
    def records(run):
        row_id = 'record:' + run + ':02:normalized-row:source'
        row = dict(id=row_id, record_type='normalized-row', source_business_id='ACT-001',
                   values={'existing_due_date':'2026-09-04'}, evidence_ids=[])
        action = dict(id='action-' + run, record_type='action', action_id='action:stable',
            proposed_due_date='2026-09-04', existing_due_date='2026-09-04', source_basis=[row_id],
            date_basis='Proposed reuse of the sole exact source action date; source row ' + row_id +
            ' and its evidence supply the date; Operations approval remains pending')
        return action, {row_id:row, action['id']:action}
    old, old_records = records('old')
    new, new_records = records('new')
    assert _basis(old, old_records) == _basis(new, new_records)
    new['proposed_due_date'] = '2026-09-05'
    assert _basis(old, old_records) != _basis(new, new_records)


def test_changed_date_retains_verified_prior_binding_without_current_authorization(review_case):
    review_case['carry_forward'].current_records['new-action']['proposed_due_date'] = '2026-09-02'
    result = match_feedback(**review_case)
    assert result['authentication'] == 'verified' and result['match_status'] == 'unresolved'
    assert result['request_id'] is None and result['subject_ids'] == [] and 'revalidation' not in result
    assert result['reviewed_draft'] == review_case['carry_forward'].reviewed_draft
    assert result['claimed_artifacts'] == review_case['payload']['claimed_artifacts']


def _run(parent, variant='same', **kwargs):
    original = CompanyReplay.table
    def dated(self, table):
        table = original(self, table)
        headers = table[0]
        if headers[0] == 'action_id':
            values = dict(system_id='AI-007', action=TASK, due_date='2026-09-05' if variant == 'date' else '2026-09-04')
            for key, value in values.items():
                table[1][headers.index(key)] = value
        return table
    body = REPORT + ('\nSYNTHETIC TEST ONLY: report version changed; readiness still unverified.' if variant == 'content' else '')
    with patch.object(CompanyReplay, 'table', dated), patch('runtime.test_u10.REPORT', body):
        result, root = execute(parent, mutation='e07-dated', launcher=True, **kwargs)
    assert result['package_acceptance'] and result['production_package'], result
    assert result['launcher_exit_code'] == {'complete':0, 'partial':2, 'blocked':3}[result['status']], result
    return result, root, validate_package(root)


@pytest.fixture(scope='module')
def prior_draft(tmp_path_factory):
    parent = tmp_path_factory.mktemp('e07-prior')
    outcome, root, chain = _run(parent)
    target = next(a for a in chain[5]['state']['proposed_actions'] if
                  a['system_id'] == 'AI-007' and a['action_kind'] == 'review-rule-change')
    assert target['proposed_due_date'] == target['existing_due_date'] == '2026-09-04'
    return parent, outcome, chain, target


@pytest.fixture(scope='module', params=['same', 'date', 'content'])
def feedback_run(request, tmp_path_factory, prior_draft):
    prior_parent, first, previous, target = prior_draft
    parent = tmp_path_factory.mktemp('e07-' + request.param)
    shutil.copytree(prior_parent / 'out', parent / 'out')
    old_request = next(r for r in previous[5]['state']['review_requests'] if r['required_reviewer'] == 'Legal')
    binding = next(b for b in previous[6]['state']['review_bindings'] if b['request_id'] == old_request['request_id'])
    reviewed = dict(root='history/' + first['run_id'], **{
        name:dict(snapshot_id=previous[index]['snapshot_id'], path=SNAPSHOT_PATHS[index],
                  sha256=sha256_bytes((parent / 'out' / SNAPSHOT_PATHS[index]).read_bytes()))
        for name, index in [('stage06', 5), ('stage07', 6)]})
    identity = 'legal@synthetic.example'
    payload = dict(responder_identity=identity, responder_role='Legal',
        claimed_request_id=old_request['request_id'], claimed_run_id=first['run_id'],
        claimed_draft_version=old_request['draft_version'], claimed_subject_ids=[target['id']],
        claimed_source_versions=old_request['source_versions'], claimed_artifacts=binding['artifacts'],
        reviewer_response_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        outcome='conditional', reasons=['Synthetic reviewer requires readiness evidence for the exact proposed date.'],
        conditions=[CONDITION], reviewed_draft=reviewed)
    paths = {key:parent / (key + '.json') for key in ('feedback', 'policy', 'auth')}
    paths['feedback'].write_bytes(json_bytes(dict(feedback=[payload], carry_forward=True)))
    paths['policy'].write_bytes(json_bytes(dict(reviewers=[dict(identity=identity, roles=['Legal'],
        channels=['authenticated-operator'], system_ids=old_request['subject_system_ids'])])))
    paths['auth'].write_bytes(json_bytes(dict(identity=identity, channel='authenticated-operator',
        basis='Synthetic local operator proof only; no organizational authorization or real identity asserted.')))
    outcome, root, current = _run(parent, request.param, feedback_path=paths['feedback'],
        reviewer_policy_path=paths['policy'], authentication_path=paths['auth'])
    return dict(variant=request.param, outcome=outcome, root=root, current=current,
        previous=previous, target=target, payload=payload, reviewed=reviewed, paths=paths)


def _parse(root):
    rows = list(csv.DictReader(io.StringIO((root / ARTIFACTS[0]).read_text(), newline='')))
    # Decode display escaping independently of the production renderer.
    rows = [{k:v[1:] if v.startswith("'") else v for k,v in row.items()} for row in rows]
    records = {}
    current = None
    for line in (root / ARTIFACTS[1]).read_text().splitlines():
        line = unescape(line)
        if line.startswith('### '):
            current = line[4:]
            records[current] = {}
        elif line.startswith('## '):
            current = None
        elif current is not None and ': ' in line:
            key, value = line.split(': ', 1)
            records[current][key] = value
    events = {str(e['UID']).split('@')[0]:e for e in Calendar.from_ical((root / ARTIFACTS[2]).read_bytes()).walk('VEVENT')}
    return rows, records, events


def test_conditional_feedback_and_changed_basis_are_scoped(feedback_run):
    case = feedback_run
    state = case['current'][5]['state']
    feedback, = state['feedback']
    target = next(a for a in state['proposed_actions'] if a['action_id'] == case['target']['action_id'])
    assert feedback['authentication'] == 'verified'
    assert feedback['outcome'] == 'conditional' and feedback['conditions'] == [CONDITION]
    assert feedback['claimed_run_id'] == case['payload']['claimed_run_id']
    assert feedback['claimed_artifacts'] == case['payload']['claimed_artifacts']
    assert feedback['reviewed_draft'] == case['reviewed']
    if case['variant'] == 'same':
        assert feedback['match_status'] == 'matched', feedback
        assert feedback['subject_ids'] == [target['id']]
        assert feedback['revalidation']['current_run_id'] == case['outcome']['run_id']
        assert all(c['result'] == 'passed' for c in feedback['revalidation']['checks'].values())
        approval = next(a for a in state['approval_requirements'] if
                        a['subject_ids'] == [target['id']] and a['required_reviewer'] == 'Legal')
        assert approval['feedback_ids'] == [feedback['id']]
        assert approval['conditions_satisfied'] is False
        assert approval['status'] == 'pending'
    else:
        assert feedback['match_status'] == 'unresolved'
        assert feedback['request_id'] is None and feedback['subject_ids'] == []
        assert 'revalidation' not in feedback
        assert any('changed relevant' in reason for reason in feedback['reasons'])
        assert all(a['feedback_ids'] == [] for a in state['approval_requirements'])
    assert all(a['approval_status'] == 'pending' for a in state['proposed_actions'])
    assert all(a['status'] == 'pending' for a in state['approval_requirements'])
    assert all(r['delivery_status'] == 'not-sent' and not r['delivery_evidence_ids'] for r in state['review_requests'])


def test_all_artifacts_preserve_date_and_unmet_conditional_outcome(feedback_run):
    case = feedback_run
    rows, brief, events = _parse(case['root'])
    action = next(a for a in case['current'][5]['state']['proposed_actions'] if a['action_id'] == case['target']['action_id'])
    day = '2026-09-05' if case['variant'] == 'date' else '2026-09-04'
    assert action['existing_due_date'] == action['proposed_due_date'] == day
    relevant = [r for r in rows if action['action_id'] in r['action_ids'].split(';')]
    assert relevant
    assert all(r['proposed_due_date'] == day and r['approval_status'] == 'pending' for r in relevant)
    fields = brief['Action ' + action['action_id']]
    assert fields['Proposed date'] == fields['Existing operational date'] == day
    assert fields['Approval'] == 'pending'
    event = events[action['action_id']]
    assert event.decoded('DTSTART') == date.fromisoformat(day)
    assert event.decoded('DTEND') == date.fromisoformat(day) + timedelta(days=1)
    assert str(event['STATUS']) == 'TENTATIVE'
    if case['variant'] == 'same':
        for text in [*(r['resolution_need'] for r in relevant), fields['Reviewer feedback'], str(event['DESCRIPTION'])]:
            assert CONDITION in text
            assert 'conditional' in text and 'unmet' in text
            assert case['payload']['reasons'][0] in text
    else:
        assert CONDITION not in str(event['DESCRIPTION'])  # Quarantine is not a current action decision.
        assert any(CONDITION in str(fields) for name, fields in brief.items() if name.startswith('Feedback '))


def test_exact_prior_artifacts_and_history_remain_intact(feedback_run):
    case = feedback_run
    archived = verify_archive(case['root'] / case['reviewed']['root'])
    assert validate_package(archived.root) == case['previous']
    assert case['current'] == accept_package(case['root'])
    for artifact in case['payload']['claimed_artifacts']:
        raw = (archived.root / artifact['path']).read_bytes()
        assert sha256_bytes(raw) == artifact['sha256']
        candidate = case['root'] / '.staging' / case['outcome']['run_id']
        assert (candidate / case['reviewed']['root'] / artifact['path']).read_bytes() == raw
    for source, retained in [('feedback', 'feedback-input'), ('policy', 'reviewer-policy'), ('auth', 'authentication-context')]:
        assert (case['root'] / ('analysis/' + retained + '.json')).read_bytes() == case['paths'][source].read_bytes()
    inspected = parse_json((case['root'] / 'analysis/prior-inspection.json').read_bytes())
    assert inspected['accepted'] and inspected['run_id'] == case['previous'][0]['run_id']


@pytest.mark.parametrize('artifact', ARTIFACTS)
def test_independent_validator_rejects_changed_condition(feedback_run, tmp_path, artifact):
    if feedback_run['variant'] != 'same':
        pytest.skip('Matched conditional display is covered once per file.')
    root = feedback_run['root']
    for path in ARTIFACTS:
        shutil.copyfile(root / path, tmp_path / path)
    model = feedback_run['current'][5]['state']['export_model']
    assert validate_artifacts(tmp_path, model)
    raw = (tmp_path / artifact).read_bytes()
    if artifact.endswith('.ics'):
        cal = Calendar.from_ical(raw)
        event = next(e for e in cal.walk('VEVENT') if CONDITION in str(e['DESCRIPTION']))
        description = str(event['DESCRIPTION']).replace(CONDITION, 'Condition satisfied without independent evidence.')
        del event['DESCRIPTION']
        event.add('DESCRIPTION', description)
        changed = cal.to_ical()  # Preserve valid framing; fail on changed meaning.
    else:
        assert b'readiness evidence' in raw
        changed = raw.replace(b'readiness evidence', b'condition satisfied without proof')
    (tmp_path / artifact).write_bytes(changed)
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, model)
