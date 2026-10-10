"""U11 conservative truth table, immutable bounded binding and coverage."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from rci.contracts import ContractError,json_bytes,sha256_bytes,validate_schema
from rci.evidence import EvidenceStore
from rci.impacts import (create_impact_request,submit_impact,freeze_impacts,validate_impacts,disposition,
    negative_control_nontrigger,candidate_semantic_basis)
from rci.snapshots import read_chain
from runtime.test_u10 import capture,clone,packet,candidate,policy_candidate,submit,fourth,REPORT


CONTROL='Provide a notice for learner chat interaction; absence of notice triggers review.'
POLICY=('SYNTHETIC POLICY ONLY. Quillhaven ALL systems internal policy P-v1 effective from 2026-08-01 '
    'active through 2027-01-01 exclusively. '+CONTROL)


@pytest.fixture(scope='module')
def captured(tmp_path_factory):
    # Isolated synthetic policy expresses the exact notice duty used in bindings.
    # The parent U10 human-review fixture keeps its separate policy meaning.
    with patch('runtime.test_u10.CONTROL',CONTROL),patch('runtime.test_u10.POLICY',POLICY):
        yield capture(tmp_path_factory.mktemp('u11'))


@pytest.mark.parametrize('authority,states,value,expected',[
    (False,['conflicting'],True,'unresolved'),(True,['conflicting','unresolved'],None,'conflicting'),
    (True,['unresolved'],False,'unresolved'),(True,['supported'],True,'supported-impact'),
    (True,['supported'],False,'supported-no-impact'),(True,[],False,'unresolved')])
def test_truth_table(authority,states,value,expected):
    assert disposition(authority,[dict(state=s,value={'resolved_value':True}) for s in states],value)==expected


def impact_packet(root):
    (root/'analysis/u11-reference.txt').write_text('Synthetic U11 exact predicate mapping test only')
    pointer=dict(path='analysis/u11-reference.txt',sha256=sha256_bytes((root/'analysis/u11-reference.txt').read_bytes()))
    metadata=dict(host_version=None,requested_model='synthetic-test',requested_effort='test-only',reported_model=None,
        reported_effort=None,usage=None,instruction_versions=[pointer],reference_versions=[pointer])
    return create_impact_request(EvidenceStore(root,root.name),metadata)


def binding(root,equals=False,scope='learner chat',predicate='notice_present'):
    fourth=read_chain(root,count=4)[3];rule=fourth['state']['policy_controls'][0]
    eid=rule['evidence_ids'][0]
    term=dict(predicate=predicate,equals=equals,rule_predicate=CONTROL,evidence_id=eid,quote=POLICY)
    descriptor=dict(schema_version='rci-impact-binding/1',rule_id=rule['id'],system_id='AI-007',scope=scope,necessary=[],impact=term)
    return dict(summary='Synthetic scoped impact binding',basis_type='internal-control',citations=[dict(evidence_id=eid,quote=POLICY)],
        conditions=[json_bytes(descriptor).decode()],role='unknown',timing_candidates=[],exception_candidates=[],uncertainty=None,system_ids=['AI-007'])


def prepare(captured,tmp_path,values):
    root=clone(captured,tmp_path);request=packet(root)
    claims=[candidate(request,value=v,quote=REPORT.splitlines()[1 if v is False else 0]) for v in values]
    submit(root,claims+[policy_candidate(request)]);fourth(root);impact_packet(root)
    return root


@pytest.mark.parametrize('values,expected',[
    ([False],'supported-impact'),([True],'supported-no-impact'),([True,False,None],'conflicting'),([None],'unresolved')])
def test_four_states_evidence_scopes_and_coverage(captured,tmp_path,values,expected):
    root=prepare(captured,tmp_path,values);store=EvidenceStore(root,root.name)
    before={p:p.read_bytes() for p in (root/'snapshots').glob('*')}
    result=submit_impact(store,json_bytes(dict(disposition='proposed',diagnostic=None,candidates=[binding(root)])))
    assert result['disposition']=='proposed',result
    snapshot=freeze_impacts(store);validate_schema(snapshot);validate_impacts(store)
    records=snapshot['state']['impacts']+snapshot['state']['unaffected_items']+snapshot['state']['unresolved_items']
    impact=next(i for i in records if i['system_id']=='AI-007' and i['basis_type']=='internal-control')
    assert impact['state']==expected and impact['evidence_ids']
    coverage=snapshot['state']['extensions']['u11_impacts']['value']['coverage']
    assert {c['system_id'] for c in coverage}==set(read_chain(root,count=1)[0]['state']['systems_in_scope'])
    assert all(p.read_bytes()==raw for p,raw in before.items())
    # Same-system legal rules remain independently unresolved; policy findings survive.
    assert any(c['basis_type']=='binding-legal' and c['state']=='unresolved' for c in coverage)


def test_missing_mapping_wrong_scope_reported_predicate_and_tamper(captured,tmp_path):
    root=prepare(captured,tmp_path,[False]);store=EvidenceStore(root,root.name)
    c=binding(root,scope='public');submit_impact(store,json_bytes(dict(disposition='proposed',diagnostic=None,candidates=[c])))
    snapshot=freeze_impacts(store)
    assert not snapshot['state']['unaffected_items'] and not snapshot['state']['impacts']
    raw=(root/'snapshots/05-impact-analysis.json').read_bytes()
    altered=deepcopy(snapshot);altered['state']['extensions']['u11_impacts']['value']['coverage'][0]['reason']='Fabricated result'
    (root/'snapshots/05-impact-analysis.json').write_bytes(json_bytes(altered))
    with pytest.raises(ContractError):validate_impacts(store)
    (root/'snapshots/05-impact-analysis.json').write_bytes(raw)
    isolated=tmp_path/'reported';isolated.mkdir()
    root=prepare(captured,isolated,[False]);store=EvidenceStore(root,root.name)
    c=binding(root,predicate='reported.notice_present')
    result=submit_impact(store,json_bytes(dict(disposition='proposed',diagnostic=None,candidates=[c])))
    assert result['disposition']=='unresolved' and 'predicate' in result['reason']


def test_stable_identity_under_fact_reorder(captured,tmp_path):
    root=prepare(captured,tmp_path,[False]);store=EvidenceStore(root,root.name)
    submit_impact(store,json_bytes(dict(disposition='proposed',diagnostic=None,candidates=[binding(root)])))
    first=freeze_impacts(store,write=False)
    from rci.impacts import _chain
    original=_chain(store);reordered=deepcopy(original);reordered[3]['state']['system_facts'].reverse()
    from rci.impacts import _submission
    submitted=_submission(store,original)
    with patch('rci.impacts._chain',return_value=reordered),patch('rci.impacts._submission',return_value=submitted):
        second=freeze_impacts(store,write=False)
    assert sorted(i['impact_id'] for i in first['state']['impacts'])==sorted(i['impact_id'] for i in second['state']['impacts'])


def test_policy_finding_survives_shared_legal_authority_blocker(captured,tmp_path):
    root=capture(tmp_path,supported_authority=False);request=packet(root)
    submit(root,[candidate(request,value=False,quote=REPORT.splitlines()[1]),policy_candidate(request)])
    fourth(root);impact_packet(root);store=EvidenceStore(root,root.name)
    submit_impact(store,json_bytes(dict(disposition='proposed',diagnostic=None,candidates=[binding(root)])))
    snapshot=freeze_impacts(store)
    assert snapshot['status']=='blocked'
    assert any(i['system_id']=='AI-007' and i['basis_type']=='internal-control' for i in snapshot['state']['impacts'])
    coverage=snapshot['state']['extensions']['u11_impacts']['value']['coverage']
    assert any(c['system_id']=='AI-007' and c['basis_type']=='binding-legal' and c['state']=='unresolved' and c['blocker_ids'] for c in coverage)


@pytest.mark.parametrize('predicate',['notice_present','notice_before_first_interaction','machine_readable_provenance'])
def test_negative_disclosure_control_is_not_affirmative_exclusion(predicate):
    terms=[dict(predicate=predicate,equals=True)]
    facts=[dict(predicate=predicate,state='supported',value={'resolved_value':False})]
    assert negative_control_nontrigger(terms,facts)==[predicate]
    facts[0]['value']['resolved_value']=True
    assert negative_control_nontrigger(terms,facts)==[]
    facts[0]['predicate']='provider_role';facts[0]['value']['resolved_value']=False
    assert negative_control_nontrigger([dict(predicate='provider_role',equals=True)],facts)==[]


def test_false_notice_positive_binding_cannot_generate_no_impact(captured,tmp_path):
    root=prepare(captured,tmp_path,[False]);store=EvidenceStore(root,root.name)
    submit_impact(store,json_bytes(dict(disposition='proposed',diagnostic=None,candidates=[binding(root,equals=True)])))
    snapshot=freeze_impacts(store)
    findings=[i for i in snapshot['state']['unresolved_items'] if i['system_id']=='AI-007' and i['basis_type']=='internal-control']
    assert len(findings)==1 and findings[0]['state']=='unresolved'
    assert 'Affirmative absence of notice_present' in findings[0]['reason']
    assert findings[0]['fact_ids'] and findings[0]['evidence_ids'] and findings[0]['resolution_need']
    assert not snapshot['state']['unaffected_items'] and not snapshot['state']['impacts']


def test_candidate_semantic_basis_omits_interpretation_record_ids():
    first=dict(summary='Pending policy',conditions=[json_bytes(dict(kind='policy-control',basis_id='notice-control',
        meaning_key='learner-notice/v1',evidence_id='record:first',effective_from='2026-08-01')).decode()])
    second=deepcopy(first)
    second['conditions']=[first['conditions'][0].replace('record:first','record:second').replace('2026-08-01','2026-08-02')]
    assert candidate_semantic_basis(first,'internal-control')==candidate_semantic_basis(second,'internal-control')
