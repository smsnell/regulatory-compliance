"""Approved narrow U10 resolution: absence evidence and explicit report review.

Synthetic assertions are captured and submitted through the real semantic
stages. A resolved report does not rewrite its original capture status.
"""
from copy import deepcopy
from unittest.mock import patch

import pytest

from rci.contracts import json_bytes, parse_json
from rci.reconcile import PREDICATES, validate_reconciliation, _chain, _submission, _report_resolved
from rci.evidence import EvidenceStore
from runtime.test_u10 import capture, clone, packet, candidate, policy_candidate, submit, fourth


SCOPE = 'learner chat'
VALUES = {
    'notice_present': (True, 'page-capture', 'notice is present'),
    'notice_before_first_interaction': (True, 'interaction-test', 'notice appears before first interaction'),
    'machine_readable_provenance': (True, 'export-test', 'export test confirms machine-readable provenance'),
    'provider_role': (False, 'owner-statement', 'current provider role is no'),
    'deployer_role': (True, 'owner-statement', 'current deployer role is yes'),
    'output_scope': ('generated replies', 'owner-statement', 'output consists of generated replies'),
    'exposed_group': ('learners', 'owner-statement', 'audience consists of learners'),
    'human_review_path': ('staff review', 'owner-statement', 'staff review occurs before delivery'),
    'exception_claim': ('No exception claimed', 'owner-statement', 'No exception claimed'),
}
QUOTES = {p: 'AI-007 learner chat Marketing confirms suitability on 2026-08-26: '+v[2]+'.'
          for p,v in VALUES.items()}
COMPLETENESS = 'All relevant output/interaction scopes in this complete report are: learner chat.'
REVIEW_QUOTE = 'AI-007 Marketing confirms suitability on 2026-08-26. '+COMPLETENESS
REPORT = '\n'.join(['SYNTHETIC TEST ONLY.', *QUOTES.values(), REVIEW_QUOTE])
CLAIM_QUOTE = 'AI-007 learner chat Marketing requests an exception on 2026-08-26; approval is pending.'


@pytest.fixture(scope='module')
def captured_resolution(tmp_path_factory):
    with patch('runtime.test_u10.REPORT', REPORT):
        return capture(tmp_path_factory.mktemp('u10-explicit-report-resolution'))


@pytest.fixture(scope='module')
def captured_claim(tmp_path_factory):
    with patch('runtime.test_u10.REPORT', REPORT.replace(QUOTES['exception_claim'],CLAIM_QUOTE)):
        return capture(tmp_path_factory.mktemp('u10-actual-exception-claim'))


def assessments(request, claimed=False):
    facts = [candidate(request, predicate=p, value=v, quote=QUOTES[p], kind=kind,
        **({'exception_disposition':'none-claimed'} if p=='exception_claim' else {}))
        for p,(v,kind,_) in VALUES.items() if p!='exception_claim' or not claimed]
    if claimed:
        facts.append(candidate(request,predicate='exception_claim',value='approval is pending',quote=CLAIM_QUOTE))
    else:
        change(facts[-1], value_quote='No exception claimed')
    eid = next(e['evidence_id'] for e in request['extracts'] if REVIEW_QUOTE in e['text'])
    review = dict(summary='Explicit scoped report completeness assessment', basis_type='factual',
        citations=[dict(evidence_id=eid, quote=REVIEW_QUOTE)],
        conditions=[json_bytes(dict(schema_version='rci-u10-basis/1',kind='report-review',
            evidence_id=eid,quote=REVIEW_QUOTE,identity_quote='AI-007',scopes=[SCOPE],
            review_date_quote='2026-08-26',complete=True,completeness_quote=COMPLETENESS,
            owner='Marketing')).decode()],role='unknown',timing_candidates=[],exception_candidates=[],
        uncertainty=None,system_ids=['AI-007'])
    return facts, review


def change(candidate_record, **fields):
    descriptor = parse_json(candidate_record['conditions'][0].encode())
    descriptor.update(fields)
    candidate_record['conditions'] = [json_bytes(descriptor).decode()]


def report_entry(snapshot):
    return next(r for r in snapshot['state']['extensions']['u10_reconciliation']['value']['reports']
                if r['report']['system_id']=='AI-007' and r['report']['evidence_ids'])


def test_explicit_absence_and_complete_own_report_resolve_without_approval(captured_resolution, tmp_path):
    root = clone(captured_resolution,tmp_path)
    request = packet(root)
    facts, review = assessments(request)
    submit(root, facts+[review,policy_candidate(request)])
    snapshot = fourth(root)
    validate_reconciliation(EvidenceStore(root,root.name))
    entry = report_entry(snapshot)
    assert entry['gap_id'] is None
    assert entry['resolution']['scopes']==[SCOPE]
    assert entry['resolution']['declaration_candidate_numbers']==[10]
    supported = [f for f in snapshot['state']['system_facts'] if f['system_id']=='AI-007'
                 and f['predicate'] in PREDICATES]
    assert len(supported)==9 and all(f['state']=='supported' for f in supported)
    exception = next(f for f in supported if f['predicate']=='exception_claim')
    assert exception['value']['resolved_value']=='No exception claimed'
    assert snapshot['status']=='partial'  # Other systems and immutable capture limitations survive.
    assert snapshot['state']['evidence_gaps']
    # Even supported aggregate facts cannot replace this report's own coverage.
    store=EvidenceStore(root,root.name)
    _,_,accepted,reviews=_submission(store,_chain(store))
    declarations=[(n,d) for n,_,d,_ in accepted if d['kind']=='report-review']
    other_basis=deepcopy(accepted)
    for _,_,descriptor,_ in other_basis:
        if descriptor['kind']=='fact' and descriptor['predicate']=='notice_present':
            descriptor['evidence_id']='another-report-evidence'
    assert not _report_resolved(entry['report'],declarations,other_basis,reviews,supported)
    extra_scope=deepcopy(accepted)
    for _,_,descriptor,_ in extra_scope:
        if descriptor['kind']=='fact' and descriptor['predicate']=='notice_present':
            descriptor['scope']='another audience'
    assert not _report_resolved(entry['report'],declarations,extra_scope,reviews,supported)


@pytest.mark.parametrize('failure', [
    'missing-declaration','incomplete-declaration','missing-predicate','wrong-system',
    'wrong-scope','stale-suitability','missing-absence-disposition','boolean-exception',
    'fabricated-absence','contradictory-declaration','missing-completeness-quote',
])
def test_unresolved_report_and_exception_boundaries(captured_resolution,tmp_path,failure):
    root = clone(captured_resolution,tmp_path)
    request = packet(root)
    facts, review = assessments(request)
    declarations = [review]
    if failure=='missing-declaration': declarations=[]
    elif failure=='incomplete-declaration': change(review,complete=False)
    elif failure=='missing-predicate': facts.pop(0)
    elif failure=='wrong-system': review['system_ids']=['AI-008']
    elif failure=='wrong-scope': change(facts[0],scope='public page')
    elif failure=='stale-suitability': change(facts[-1],review_date_quote=None)
    elif failure=='missing-absence-disposition':
        d=parse_json(facts[-1]['conditions'][0].encode());d.pop('exception_disposition')
        facts[-1]['conditions']=[json_bytes(d).decode()]
    elif failure=='boolean-exception': change(facts[-1],value=False)
    elif failure=='fabricated-absence': change(facts[-1],value='No exemption requested')
    elif failure=='contradictory-declaration':
        other=deepcopy(review);change(other,complete=False);declarations.append(other)
    elif failure=='missing-completeness-quote': change(review,completeness_quote='Invented complete learner chat scope')
    submit(root,facts+declarations+[policy_candidate(request)])
    snapshot=fourth(root)
    entry=report_entry(snapshot)
    assert entry['gap_id'] is not None and 'resolution' not in entry
    assert snapshot['status']=='partial'
    if failure in {'stale-suitability','missing-absence-disposition','boolean-exception',
                   'fabricated-absence'}:
        exception=next(f for f in snapshot['state']['system_facts'] if
            f['system_id']=='AI-007' and f['predicate']=='exception_claim')
        assert exception['state']=='unresolved'


def test_actual_exception_claim_still_requires_authorized_legal_decision(captured_claim,tmp_path):
    root=clone(captured_claim,tmp_path)
    request=packet(root)
    facts,review=assessments(request,claimed=True)
    submit(root,facts+[review,policy_candidate(request)])
    snapshot=fourth(root)
    assert report_entry(snapshot)['gap_id'] is not None
    exception=next(f for f in snapshot['state']['system_facts'] if
        f['system_id']=='AI-007' and f['predicate']=='exception_claim')
    assert exception['state']=='unresolved'
    assert 'authorized Legal decision' in exception['reason']
