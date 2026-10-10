"""U13 authentication, detached bindings and explicit prior-draft revalidation."""
from copy import deepcopy

import pytest

from rci.contracts import ContractError, validate_schema
from rci.reviews import (AuthenticationContext, CarryForwardContext, ConditionResolution,
                         ReviewerPolicy, approval_for_feedback, create_review_request,
                         match_feedback, process_feedback)


HASH = 'sha256:' + 'a' * 64
PATHS = ('impact-register.csv', 'compliance-brief.md', 'action-calendar.ics')


@pytest.fixture
def review_case():
    def request(run, subject):
        return create_review_request(run_id=run, draft_version='draft-1', subject_ids=[subject],
            subject_system_ids=['S1'], source_versions=['source:exact-v1'], evidence_ids=['evidence-' + run],
            question='Approve proposed remediation date?', required_reviewer='Legal')
    old = request('run-old', 'old-action')
    new = request('run-new', 'new-action')
    artifacts = [dict(path=path, sha256=HASH) for path in PATHS]
    binding = dict(request_id=old['request_id'], run_id=old['run_id'], draft_version=old['draft_version'], artifacts=artifacts)
    payload = dict(responder_identity='legal@example.test', responder_role='Legal',
        claimed_request_id=old['request_id'], claimed_run_id=old['run_id'], claimed_draft_version=old['draft_version'],
        claimed_subject_ids=old['subject_ids'], claimed_source_versions=old['source_versions'],
        claimed_artifacts=artifacts, reviewer_response_at='2026-08-27T10:00:00Z', outcome='approved',
        reasons=['The exact proposed date is acceptable'], conditions=[])
    policy = ReviewerPolicy.from_dict(dict(reviewers=[dict(identity='legal@example.test', roles=['Legal'],
        channels=['authenticated-operator'], system_ids=['S1'])]))
    auth = AuthenticationContext.from_dict(dict(identity='legal@example.test', channel='authenticated-operator',
                                              basis='verified operator session-123'))
    def records(run, subject):
        evidence_id = 'evidence-' + run
        return {subject: dict(id=subject, record_type='action', action_id='action:stable',
                system_id='S1', evidence_ids=[evidence_id], proposed_due_date='2026-09-01',
                existing_due_date='2026-08-31', approval_status='pending'),
                evidence_id: dict(id=evidence_id, record_type='evidence', evidence_ids=[],
                    content_hash=HASH, local_reference='sources/' + run + '.txt', source_id='source-S1')}
    reviewed = dict(root='history/run-old',
        stage06=dict(snapshot_id='old-six', path='snapshots/06-actions-and-approvals.json', sha256=HASH),
        stage07=dict(snapshot_id='old-seven', path='snapshots/07-publication-validation.json', sha256=HASH))
    context = CarryForwardContext(reviewed, (dict(snapshot_id='new-five',
        path='snapshots/05-impact-analysis.json', sha256=HASH),),
        (dict(reviewed_id='old-action', current_id='new-action'),),
        records('run-old', 'old-action'), records('run-new', 'new-action'))
    return dict(run_id='run-new', request=new, reviewed_request=old, review_binding=binding,
                payload=payload, policy=policy, authentication=auth, current_time='2026-08-28T00:00:00Z',
                reviewed_at='2026-08-27T09:00:00Z', carry_forward=context)


def assert_quarantined(result):
    validate_schema(result, 'feedback')
    assert result['match_status'] == 'unresolved'
    assert result['subject_ids'] == [] and result['request_id'] is None
    assert result['reasons'] and 'revalidation' not in result


def test_request_complete_and_preparation_is_unsent(review_case):
    request = review_case['request']
    validate_schema(request, 'review-request')
    assert request['request_id'] and request['run_id'] == 'run-new'
    assert request['subject_ids'] and request['source_versions'] and request['evidence_ids']
    assert request['delivery_status'] == 'not-sent' and request['delivery_evidence_ids'] == []
    assert approval_for_feedback(run_id='run-new', request=request)['status'] == 'pending'


def test_verified_fixture_binding_to_new_run_outcome_does_not_mutate_action(review_case):
    before = deepcopy(review_case['carry_forward'].current_records)
    feedback = match_feedback(**review_case)
    assert feedback['match_status'] == 'matched' and feedback['authentication'] == 'verified'
    assert feedback['claimed_run_id'] == 'run-old' and feedback['request_id'] == review_case['request']['request_id']
    assert feedback['subject_ids'] == ['new-action']
    validate_schema(feedback, 'feedback')
    approval = approval_for_feedback(run_id='run-new', request=review_case['request'], feedback=feedback)
    assert approval['status'] == 'approved' and approval['feedback_ids'] == [feedback['id']]
    assert review_case['carry_forward'].current_records == before
    assert before['new-action']['existing_due_date'] == '2026-08-31'
    assert before['new-action']['proposed_due_date'] == '2026-09-01'
    assert review_case['request']['delivery_status'] == 'not-sent'


def test_fresh_retrieval_occurrences_preserve_exact_reviewed_factual_dates(review_case):
    context = review_case['carry_forward']
    old = context.reviewed_records['old-action']
    current = context.current_records['new-action']
    old['retrieved_at'], current['retrieved_at'] = '2026-08-27T09:00:00Z', '2026-08-28T00:00:00Z'
    old['retained_assertion'] = dict(retrieved_at=old['retrieved_at'], observed_on='2026-08-26',
                                    effective_from='2026-08-01', value=False, scope='learner chat')
    current['retained_assertion'] = {**old['retained_assertion'], 'retrieved_at':current['retrieved_at']}
    assert match_feedback(**review_case)['match_status'] == 'matched'
    for field, value in [('observed_on', '2026-08-25'), ('effective_from', '2026-08-02'),
                         ('value', True), ('scope', 'public')]:
        current['retained_assertion'] = {**old['retained_assertion'], 'retrieved_at':current['retrieved_at'],
                                         field:value}
        assert_quarantined(match_feedback(**review_case))


@pytest.mark.parametrize('field,value', [
    ('claimed_request_id', 'wrong-request'), ('claimed_subject_ids', ['another-subject']),
    ('claimed_run_id', 'run-superseded'), ('claimed_draft_version', 'superseded-version'),
    ('claimed_source_versions', ['source:changed']), ('responder_role', 'Operations'),
    ('responder_identity', 'imposter@example.test'), ('reviewer_response_at', None),
    ('reviewer_response_at', '2026-08-27T08:59:59Z'), ('reviewer_response_at', '2026-08-29T00:00:00Z'),
    ('reviewer_response_at', 'not-a-time'), ('claimed_subject_ids', []),
    ('claimed_artifacts', []),
])
def test_mismatches_are_preserved_unresolved(review_case, field, value):
    review_case['payload'][field] = value
    result = match_feedback(**review_case)
    assert_quarantined(result)
    assert approval_for_feedback(run_id='run-new', request=review_case['request'], feedback=result)['status'] == 'pending'


def test_wrong_artifact_hash_quarantined(review_case):
    review_case['payload'] = deepcopy(review_case['payload'])
    review_case['payload']['claimed_artifacts'][0]['sha256'] = 'sha256:' + 'b' * 64
    assert_quarantined(match_feedback(**review_case))


@pytest.mark.parametrize('auth', [None, AuthenticationContext('legal@example.test', 'untrusted-email', 'claim'),
                                AuthenticationContext('imposter@example.test', 'authenticated-operator', 'proof'),
                                AuthenticationContext('legal@example.test', 'authenticated-operator', '')])
def test_payload_role_and_authentication_fields_are_not_identity_proof(review_case, auth):
    review_case['payload'].update(authentication='verified', authentication_basis='I am Legal')
    review_case['authentication'] = auth
    result = match_feedback(**review_case)
    assert_quarantined(result)
    assert result['authentication'] == 'unverified'


def test_authorized_identity_still_requires_scope_and_role_mapping(review_case):
    review_case['policy'] = ReviewerPolicy.from_dict(dict(reviewers=[dict(identity='legal@example.test',
        roles=['Legal'], channels=['authenticated-operator'], system_ids=['S2'])]))
    assert_quarantined(match_feedback(**review_case))


def test_authenticated_old_feedback_never_automatically_applies(review_case):
    review_case['carry_forward'] = None
    result = match_feedback(**review_case)
    assert_quarantined(result)
    assert result['authentication'] == 'verified'
    assert 'explicit revalidation' in result['summary']


@pytest.mark.parametrize('change', ['fact', 'date', 'source', 'scope', 'evidence', 'subject', 'correspondence'])
def test_carry_forward_requires_exact_unchanged_relevant_basis(review_case, change):
    context = review_case['carry_forward']
    if change == 'fact':
        context.current_records['new-action']['substantive_fact'] = False
    elif change == 'date':
        context.current_records['new-action']['proposed_due_date'] = '2026-09-02'
    elif change == 'source':
        review_case['request']['source_versions'] = ['source:v2']
    elif change == 'scope':
        review_case['request']['subject_system_ids'] = []
    elif change == 'evidence':
        context.current_records['evidence-run-new']['content_hash'] = 'sha256:' + 'b' * 64
    elif change == 'subject':
        context.current_records['new-action']['action_id'] = 'action:other'
    else:
        context.subject_bindings[0]['current_id'] = 'not-requested'
    assert_quarantined(match_feedback(**review_case))


def test_rejected_feedback_remains_rejection(review_case):
    review_case['payload']['outcome'] = 'rejected'
    feedback = match_feedback(**review_case)
    assert feedback['match_status'] == 'matched'
    assert approval_for_feedback(run_id='run-new', request=review_case['request'], feedback=feedback)['status'] == 'rejected'


def test_conditional_requires_conditions_and_independent_exact_resolution(review_case):
    review_case['payload']['outcome'] = 'conditional'
    assert_quarantined(match_feedback(**review_case))
    review_case['payload']['conditions'] = ['Confirm system-owner readiness']
    feedback = match_feedback(**review_case)
    assert feedback['match_status'] == 'matched'
    for resolution in (None, ConditionResolution(('other condition',), ('evidence-run-new',), True),
                       ConditionResolution(tuple(feedback['conditions']), (), True),
                       ConditionResolution(tuple(feedback['conditions']), ('evidence-run-new',), False)):
        assert approval_for_feedback(run_id='run-new', request=review_case['request'], feedback=feedback,
                                     condition_resolution=resolution)['status'] == 'pending'
    resolution = ConditionResolution(tuple(feedback['conditions']), ('evidence-run-new',), True)
    approval = approval_for_feedback(run_id='run-new', request=review_case['request'], feedback=feedback,
                                     condition_resolution=resolution)
    assert approval['status'] == 'approved' and approval['conditions_satisfied']
    assert approval['condition_evidence_ids'] == ['evidence-run-new']


def test_trusted_policy_loader_rejects_ambiguous_authority(review_case):
    reviewer = dict(identity='legal@example.test', roles=['Legal'], channels=['authenticated-operator'], system_ids=['S1'])
    with pytest.raises(ContractError, match='ambiguous'):
        ReviewerPolicy.from_dict(dict(reviewers=[reviewer, reviewer]))
    with pytest.raises(ContractError):
        AuthenticationContext.from_dict(dict(identity='legal@example.test', channel='operator', basis=''))


def test_incomplete_claims_can_be_quarantined_without_resolved_links(review_case):
    review_case['payload'] = {}
    assert_quarantined(match_feedback(**review_case))


def test_approval_cannot_target_other_request_role_or_subject(review_case):
    feedback = match_feedback(**review_case)
    for field, value in [('request_id', 'another'), ('subject_ids', ['other']), ('responder_role', 'Operations')]:
        altered = deepcopy(feedback)
        altered[field] = value
        assert approval_for_feedback(run_id='run-new', request=review_case['request'], feedback=altered)['status'] == 'pending'
