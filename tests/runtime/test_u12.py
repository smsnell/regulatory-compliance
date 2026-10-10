"""U12 exact deduplication, dates, operational states and immutable exports."""
from copy import deepcopy
from dataclasses import asdict

import pytest
from rci.actions import (build_actions,freeze_actions,validate_actions,unresolved_coverage,build_export_model,
    retained_source_versions)
from rci.contracts import ContractError,json_bytes,validate_schema,sha256_bytes
from rci.evidence import EvidenceStore
from rci.ids import BusinessKey,rule_version_id
from rci.impacts import freeze_impacts,submit_impact
from rci.snapshots import read_chain
from runtime.test_u11 import captured,prepare,binding
from runtime.test_u10 import capture,packet,submit,fourth


def inputs(state='supported-impact',basis='one'):
    rule=dict(id='rule-'+basis,summary='Supply scoped notice',obligation='Supply scoped notice',
        rule_version_id=rule_version_id(basis,'v1'),basis_type='binding-legal')
    key=BusinessKey('AI-007',rule['rule_version_id'],'rule-impact','learner chat')
    impact=dict(id='impact-'+basis,system_id='AI-007',rule_id=rule['id'],identity_key=asdict(key),
        state=state,evidence_ids=['evidence-one'],owner='Marketing',source_basis=['basis-'+basis])
    return impact,rule


def row(task,date='2026-09-05',status='closed',identity='CAL-001',system='AI-007'):
    return dict(id='row-'+identity,system_id=system,source_business_id=identity,evidence_ids=['evidence-calendar'],
        values={'fields':dict(action=task,owner='Marketing',existing_due_date=date,operational_status=status,
            required_reviewer='Legal',source_version='CAL-v1')})


def test_exact_match_closed_status_and_date_remain_operational():
    impact,rule=inputs();proposal=build_actions('run-test',[impact],[rule],[])[0][0]
    existing=row(proposal['summary'])
    actions,accounting,no_action=build_actions('run-test',[impact],[rule],[existing])
    action=actions[0]
    assert action['existing_due_date']=='2026-09-05' and action['proposed_due_date']=='2026-09-05'
    assert action['approval_status']=='pending' and accounting[0]['match']=='exact'
    assert accounting[0]['existing_rows'][0]['values']['fields']['operational_status']=='closed'
    assert accounting[0]['approved_date'] is None and not no_action
    validate_schema(action,'action')


@pytest.mark.parametrize('second_date',['2026-09-05','2026-09-06'])
def test_ambiguous_duplicates_preserve_every_native_identity_and_date(second_date):
    impact,rule=inputs();proposal=build_actions('run-test',[impact],[rule],[])[0][0]
    rows=[row(proposal['summary']),row(proposal['summary'],date=second_date,identity='CAL-002')]
    actions,accounting,_=build_actions('run-test',[impact],[rule],rows)
    assert actions[0]['state']=='unresolved' and accounting[0]['match']=='ambiguous'
    assert len(accounting[0]['existing_rows'])==2
    assert set(accounting[0]['existing_dates'])=={'2026-09-05',second_date}
    assert actions[0]['existing_due_date']==('2026-09-05' if second_date=='2026-09-05' else None)


def test_same_basis_multiple_impacts_group_and_different_bases_preserved():
    impact,rule=inputs();second=deepcopy(impact);second['id']='impact-copy'
    actions,accounting,_=build_actions('run-test',[impact,second],[rule],[])
    assert len(actions)==1 and actions[0]['impact_ids']==['impact-copy','impact-one']
    unrelated,other_rule=inputs(basis='two')
    actions,_,_=build_actions('run-test',[impact,unrelated],[rule,other_rule],[])
    assert len(actions)==2 and actions[0]['action_id']!=actions[1]['action_id']


def test_unaffected_has_explicit_no_action_reason_undated_proposal_stable():
    impact,rule=inputs(state='supported-no-impact')
    actions,_,reasons=build_actions('run-test',[impact],[rule],[])
    assert not actions and reasons[0]['impact_id']==impact['id'] and reasons[0]['reason']
    impact['state']='unresolved'
    first=build_actions('run-test',[impact],[rule],[])[0][0]
    second=build_actions('run-test',[impact],[rule],[row('urgent')])[0][0]
    assert first['action_id']==second['action_id'] and second['proposed_due_date'] is None
    assert second['existing_due_date'] is None and second['resolution_need']


def test_stage06_graph_requests_export_and_tamper(captured,tmp_path):
    root=prepare(captured,tmp_path,[False]);store=EvidenceStore(root,root.name)
    submit_impact(store,json_bytes(dict(disposition='proposed',diagnostic=None,candidates=[binding(root)])))
    fifth=freeze_impacts(store);sixth=freeze_actions(store);validate_schema(sixth);validate_actions(store)
    model=sixth['state']['export_model']
    assert model['schema_version']=='rci-draft-export/1' and model['draft'] is True
    assert model['impacts'] and model['actions'] and model['coverage'] and model['evidence_index']
    assert model['unresolved_coverage']
    changed_chain=deepcopy(read_chain(root,count=5))
    coverage=changed_chain[4]['state']['extensions']['u11_impacts']['value']['coverage']
    next(c for c in coverage if not c['impact_record_ids'])['reason']='A changed authority review question'
    changed_model=build_export_model(changed_chain,sixth['state'],sixth['status'])
    assert changed_model['draft_version']!=model['draft_version']
    assert {r['impact_id'] for r in changed_model['unresolved_coverage']}=={r['impact_id'] for r in model['unresolved_coverage']}
    assert all(a['approval_status']=='pending' and a['proposed_due_date'] is None for a in model['actions'])
    assert {r['required_reviewer'] for r in model['review_requests']}=={'Legal','Operations','system-owner'}
    assert all(r['delivery_status']=='not-sent' and r['draft_version']==model['draft_version'] for r in model['review_requests'])
    assert fifth['snapshot_id']==sixth['predecessor']['snapshot_id']
    actual=root/'snapshots/06-actions-and-approvals.json';altered=deepcopy(sixth)
    altered['state']['export_model']['status']='complete';actual.write_bytes(json_bytes(altered))
    with pytest.raises(ContractError):validate_actions(store)


def coverage_chain(number=1,record_suffix='one'):
    basis=dict(kind='candidate-review',basis_type='binding-legal',basis_id='article-notice',meaning_key='learner-chat/v1')
    entry=dict(system_id='AI-007',candidate_number=number,rule_id=None,rule_basis=None,basis_type='binding-legal',
        candidate_basis=basis,scope=None,state='unresolved',impact_record_ids=[],evidence_ids=['evidence-'+record_suffix],
        source_basis=['blocker-'+record_suffix],reason='Authority pending',owner='Legal',resolution_need='Legal must establish authority',
        blocker_ids=['blocker-'+record_suffix])
    return [{},{},{'state':dict(binding_rules=[],extensions={'u09_authority':{'value':{'candidate_reviews':[]}}})},
        {'state':dict(policy_controls=[],extensions={'u10_reconciliation':{'value':{'candidate_reviews':[]}}})},
        {'state':{'extensions':{'u11_impacts':{'value':{'coverage':[entry]}}}}}]


def test_unresolved_coverage_is_plain_stable_semantic_export():
    first=unresolved_coverage(coverage_chain())[0]
    reordered=unresolved_coverage(coverage_chain(number=9,record_suffix='new-run'))[0]
    assert first['impact_id']==reordered['impact_id'] and first['impact_id'].startswith('impact:v1:')
    assert first['identity_key']['kind']=='coverage-review'
    assert first['rule_id'] is None and first['rule_basis'] is None and first['source_versions']==[]
    assert not {'id','record_type','fact_ids','action_ids','proposed_due_date'} & set(first)
    assert first['system_id']=='AI-007' and first['basis_type']=='binding-legal' and first['state']=='unresolved'
    assert first['reason'] and first['owner']=='Legal' and first['resolution_need'] and first['source_basis']
    changed=coverage_chain();changed[4]['state']['extensions']['u11_impacts']['value']['coverage'][0]['candidate_basis']['meaning_key']='learner-chat/v2'
    assert unresolved_coverage(changed)[0]['impact_id']!=first['impact_id']


def test_unresolved_coverage_preserves_real_rule_reference_and_excludes_typed_impacts():
    chain=coverage_chain();entry=chain[4]['state']['extensions']['u11_impacts']['value']['coverage'][0]
    impact,rule=inputs();chain[2]['state']['binding_rules']=[rule]
    entry.update(rule_id=rule['id'],rule_basis=rule['rule_version_id'],scope='learner chat')
    row=unresolved_coverage(chain)[0]
    assert row['rule_id']==rule['id'] and row['rule_basis']==rule['rule_version_id']
    assert row['source_versions']==[rule['rule_version_id']]
    entry['impact_record_ids']=[impact['id']]
    assert unresolved_coverage(chain)==[]


def test_duplicate_candidate_questions_retain_bases_under_one_display_identity():
    chain=coverage_chain();coverage=chain[4]['state']['extensions']['u11_impacts']['value']['coverage']
    second=deepcopy(coverage[0]);second.update(candidate_number=9,evidence_ids=['evidence-two'],source_basis=['blocker-two'],blocker_ids=['blocker-two'])
    coverage.append(second)
    rows=unresolved_coverage(chain)
    assert len(rows)==1
    assert rows[0]['evidence_ids']==['evidence-one','evidence-two']
    assert rows[0]['source_basis']==['blocker-one','blocker-two']
    assert rows[0]['blocker_ids']==['blocker-one','blocker-two']
    coverage.reverse()
    assert unresolved_coverage(chain)==rows


def test_source_binding_uses_genuine_capture_hash_without_rule_version():
    digest='sha256:'+'a'*64
    chain=[{},dict(state=dict(attempts=[dict(id='attempt-one',source_id='OJ')],
        captures=[dict(attempt_id='attempt-one',representation='full',content_hash=digest)]))]
    versions=retained_source_versions(chain,[])
    assert versions==['captured-source:OJ:full:'+digest]
    from rci.reviews import create_review_request
    request=create_review_request(run_id='synthetic-run',draft_version='sha256:'+'b'*64,
        subject_ids=['source-one'],subject_system_ids=[],source_versions=versions,evidence_ids=[],
        question='Legal must review the retained source with withheld meaning',required_reviewer='Legal')
    assert request['source_versions']==versions and request['delivery_status']=='not-sent'
    chain[1]['state']['captures']=[]
    # The verified predecessor binds exact retained bytes, including formatting.
    exact_hash=sha256_bytes(b'  '+json_bytes(chain[1])+b'\n')
    chain.append(dict(predecessor=dict(sha256=exact_hash)))
    assert retained_source_versions(chain,[])==['source-register-snapshot:'+exact_hash]


def test_stage06_with_all_formal_rules_withheld_binds_retained_sources(captured,tmp_path):
    root=capture(tmp_path,supported_authority=False);packet(root);submit(root,[]);fourth(root)
    store=EvidenceStore(root,root.name);fifth=freeze_impacts(store)
    assert not read_chain(root,count=4)[2]['state']['binding_rules']
    assert not read_chain(root,count=4)[3]['state']['policy_controls']
    sixth=freeze_actions(store);validate_actions(store)
    model=sixth['state']['export_model']
    assert model['rules']==[] and model['unresolved_coverage']
    assert model['source_versions'] and all(v.startswith('captured-source:') for v in model['source_versions'])
    assert sixth['state']['review_requests']
    assert all(r['source_versions']==model['source_versions'] and r['delivery_status']=='not-sent' for r in sixth['state']['review_requests'])
    assert all(row['rule_id'] is None and row['rule_basis'] is None for row in model['unresolved_coverage'])
