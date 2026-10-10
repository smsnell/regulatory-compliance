"""U12 conservative proposals, exact calendar matches and explicit draft exports."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict

from .validation_cache import disk_verified
from .contracts import (ASSIGNED_REVIEW_DATE,SNAPSHOT_PATHS,json_bytes,parse_json,require,reduce_states,sha256_bytes)
from .evidence import _read
from .ids import BusinessKey,action_rule_basis,new_record_id,stable_business_id
from .impacts import validate_impacts,canonical_state,candidate_semantic_basis
from .reviews import (create_review_request,process_feedback,approval_for_feedback,
    ReviewerPolicy,AuthenticationContext)
from .snapshots import read_chain,stage_records,write_snapshot,_subject_systems

VERSION='rci-u12-actions/1'


def build_actions(run_id, impacts, rules, calendar_rows):
    """Pure exact-match projection; no fuzzy identity, inferred dates or approval."""
    by_rule={r['id']:r for r in rules};groups=defaultdict(list)
    no_action=[]
    for impact in impacts:
        if impact['state']=='supported-no-impact':
            no_action.append(dict(impact_id=impact['id'],reason='Affirmative scoped non-trigger; no operational proposal required'));continue
        kind='review-rule-change' if impact['state']=='supported-impact' else 'verify-scoped-evidence'
        groups[(impact['system_id'],by_rule[impact['rule_id']]['rule_version_id'],kind,
            impact['identity_key']['distinguishing_scope'])].append(impact)
    actions=[];accounting=[]
    for (system,basis,kind,scope),members in sorted(groups.items()):
        bases=[by_rule[i['rule_id']]['rule_version_id'] for i in members]
        key=BusinessKey(system,action_rule_basis(bases),kind,scope)
        task=('Review scoped change: ' if kind=='review-rule-change' else 'Verify scoped evidence: ')+by_rule[members[0]['rule_id']].get('obligation',by_rule[members[0]['rule_id']].get('control',''))+' ('+scope+')'
        matches=[r for r in calendar_rows if r['system_id']==system and r['values']['fields'].get('action')==task]
        dates={r['values']['fields'].get('existing_due_date') for r in matches if r['values']['fields'].get('existing_due_date') is not None}
        owners={r['values']['fields'].get('owner') for r in matches if r['values']['fields'].get('owner') is not None}
        if not owners:owners={i['owner'] for i in members if i['owner'] is not None}
        ambiguous=len(matches)>1
        source_basis=sorted({b for i in members for b in i['source_basis']}|{r['id'] for r in matches})
        reason=('Multiple exact calendar matches require Operations identity/date resolution; every source row retained' if ambiguous else
            'One exact system/task calendar match retained independently of approval' if matches else
            'No exact existing system/task match; draft proposal remains undated')
        evidence=sorted({e for i in members for e in i['evidence_ids']}|{e for r in matches for e in r['evidence_ids']})
        action=dict(id=new_record_id(run_id,6,'action'),record_type='action',summary=task,evidence_ids=evidence,
            identity_key=asdict(key),action_id=stable_business_id('action',key),system_id=system,
            impact_ids=sorted(i['id'] for i in members),action_kind=kind,distinguishing_scope=scope,
            owner=next(iter(owners)) if len(owners)==1 else None,
            proposed_due_date=next(iter(dates)) if len(matches)==1 and len(dates)==1 else None,
            existing_due_date=next(iter(dates)) if len(dates)==1 else None,
            date_basis=('Proposed reuse of the sole exact source action date; source row '+matches[0]['id']+' and its evidence supply the date; Operations approval remains pending' if len(matches)==1 and len(dates)==1 else
                'No proposed due date: Operations must supply a supported proposed date; existing source dates remain operational assertions'),
            approval_status='pending',state='unresolved' if ambiguous or any(i['state'] in {'unresolved','conflicting'} for i in members) else 'proposed',
            source_basis=source_basis,reason=reason,resolution_need='Legal reviews interpretation and exceptions; system owner verifies scoped facts; Operations confirms task identity, owner and dates before any calendar commitment.')
        actions.append(action)
        accounting.append(dict(action_record_id=action['id'],action_id=action['action_id'],impact_ids=action['impact_ids'],
            rule_bases=sorted(set(bases)),match='ambiguous' if ambiguous else 'exact' if matches else 'new-proposal',
            rationale=reason,existing_rows=deepcopy(matches),existing_dates=sorted(dates),
            proposed_date=action['proposed_due_date'],approved_date=None,approval_basis=None))
    return actions,accounting,no_action


def _fingerprint(value):
    """Canonicalize current-stage graph IDs through stable business identities."""
    replacements={a['id']:a['action_id'] for a in value['actions']}
    def replace(v):
        if isinstance(v,str):return replacements.get(v,v)
        if isinstance(v,dict):return {k:replace(x) for k,x in v.items() if not (v.get('record_type')=='action' and k in {'id','approval_status'})}
        if isinstance(v,list):return sorted((replace(x) for x in v),key=json_bytes)
        return v
    return sha256_bytes(json_bytes(replace(value)))


def unresolved_coverage(chain):
    """Plain export questions with semantic identities; no invented graph records."""
    authority=chain[2]['state']['extensions']['u09_authority']['value']
    legal_reviews={r['number']:r for r in authority.get('candidate_reviews',[])}
    policy_reviews={r['number']:r['candidate'] for r in chain[3]['state']['extensions']['u10_reconciliation']['value']['candidate_reviews']}
    rules={r['id']:r for r in chain[2]['state']['binding_rules']+chain[3]['state']['policy_controls']}
    output=[]
    for entry in chain[4]['state']['extensions']['u11_impacts']['value']['coverage']:
        if entry['impact_record_ids']:continue
        rule=rules.get(entry['rule_id']);number=entry.get('candidate_number')
        if rule is not None:
            semantic=dict(kind='rule-review',basis_type=entry['basis_type'],rule_version_id=rule['rule_version_id'])
        elif entry.get('candidate_basis') is not None:
            semantic=deepcopy(entry['candidate_basis'])
        elif number is not None:
            candidate=policy_reviews.get(number,{}) if entry['basis_type']=='internal-control' else {'summary':legal_reviews.get(number,{}).get('claimed_summary')}
            semantic=candidate_semantic_basis(candidate,entry['basis_type'])
        else:
            semantic=dict(kind='unestablished-authority-review',basis_type=entry['basis_type'])
        basis='coverage-basis:v1:'+sha256_bytes(json_bytes(semantic)).split(':',1)[1]
        key=BusinessKey(entry['system_id'],basis,'coverage-review',entry['scope'] or 'unbound-candidate-scope')
        output.append(dict(impact_id=stable_business_id('impact',key),identity_key=asdict(key),
            system_id=entry['system_id'],rule_id=entry['rule_id'],rule_basis=entry['rule_basis'],basis_type=entry['basis_type'],
            state=entry['state'],scope=entry['scope'],summary='Unresolved coverage for '+entry['system_id']+': '+entry['reason'],
            evidence_ids=deepcopy(entry['evidence_ids']),source_basis=deepcopy(entry['source_basis']),
            source_versions=[] if rule is None else deepcopy(rule.get('source_versions',[rule['rule_version_id']])),
            reason=entry['reason'],owner=entry.get('owner'),resolution_need=entry.get('resolution_need'),
            blocker_ids=deepcopy(entry.get('blocker_ids',[])),semantic_basis=semantic))
    # Several withheld assessments can describe the same semantic review
    # question. Display one identity while retaining every supporting basis;
    # the original occurrence ledger remains available in model.coverage.
    grouped={}
    for row in output:
        if row['impact_id'] not in grouped:
            grouped[row['impact_id']]=row;continue
        target=grouped[row['impact_id']]
        require(target['identity_key']==row['identity_key'],'Coverage business identity collision')
        for field in ('evidence_ids','source_basis','source_versions','blocker_ids'):
            target[field]=sorted(set(target[field])|set(row[field]))
        for field in ('reason','resolution_need'):
            target[field]='; '.join(sorted({v for v in (target[field],row[field]) if v})) or None
        if target['owner']!=row['owner']:target['owner']=None
        if row['state']=='conflicting':target['state']='conflicting'
        target['summary']='Unresolved coverage for '+target['system_id']+': '+target['reason']
    return sorted(grouped.values(),key=lambda row:row['impact_id'])


def retained_source_versions(chain, rules):
    """Bind captured bytes even when their legal/policy meaning is withheld."""
    versions={v for rule in rules for v in rule.get('source_versions',[rule['rule_version_id']])}
    second=chain[1]
    attempts={r['id']:r for r in second['state']['attempts']}
    for capture in second['state']['captures']:
        source_id=attempts[capture['attempt_id']]['source_id']
        versions.add('captured-source:'+source_id+':'+capture['representation']+':'+capture['content_hash'])
    if not versions:
        # All reads can fail. Bind the actual retained source-capture snapshot,
        # explicitly as a register fingerprint rather than a rule version.
        versions.add('source-register-snapshot:'+chain[2]['predecessor']['sha256'])
    return sorted(versions)


def build_export_model(chain, state, status):
    records=[r for s in chain for r in stage_records(s)]
    fifth=chain[4]
    impacts=[r for r in stage_records(fifth) if r['record_type']=='impact']
    rules=[r for r in records if r['record_type'] in {'rule','policy-control'}]
    versions=retained_source_versions(chain,rules)
    model=dict(schema_version='rci-draft-export/1',run_id=chain[0]['run_id'],assigned_review_date=ASSIGNED_REVIEW_DATE,
        status=status,draft=True,recipients=chain[0]['state']['audiences'],systems_in_scope=chain[0]['state']['systems_in_scope'],
        created_at=fifth['created_at'],impacts=deepcopy(impacts),rules=deepcopy(rules),
        unresolved_coverage=unresolved_coverage(chain),
        facts=deepcopy(chain[3]['state']['system_facts']),actions=deepcopy(state['proposed_actions']),
        decisions=deepcopy([r for r in records if r['record_type']=='decision']),
        limitations=deepcopy([r for r in records if r['record_type'] in {'blocker','diagnostic','gap','conflict'} or
            r['record_type']=='impact' and r['state'] in {'unresolved','conflicting'}]),
        evidence_index=deepcopy(chain[1]['state']['evidence']),source_quality=deepcopy(chain[1]['state']['sources']),
        source_versions=versions,coverage=deepcopy(fifth['state']['extensions']['u11_impacts']['value']['coverage']),
        action_accounting=deepcopy(state['extensions']['u12_actions']['value']['actions']),
        calendar_context=deepcopy(state['extensions']['u12_actions']['value']['calendar_rows']))
    reconciliation=chain[3]['state']['extensions']['u10_reconciliation']['value']
    if 'capture_resolution' in reconciliation:
        # Expose the independently checked inspection ledger without removing
        # its original capture diagnostics or changing historical source status.
        model['source_resolution']=deepcopy(reconciliation['capture_resolution'])
        model['source_resolution']['report_resolutions']=deepcopy([
            entry for entry in reconciliation['reports']
            if entry['gap_id'] is None and 'resolution' in entry])
    model['draft_version']=_fingerprint(model)
    model.update(review_requests=deepcopy(state['review_requests']),approval_requirements=deepcopy(state['approval_requirements']),
        escalations=deepcopy(state['escalations']))
    model['limitations'].extend(deepcopy(state['escalations']))
    return model


def _apply_feedback(store,state):
    path=store.root/'analysis/feedback-input.json'
    if not path.exists():return
    envelope=parse_json(_read(store.root,'analysis/feedback-input.json'))
    require(isinstance(envelope,dict) and set(envelope)=={'feedback','carry_forward'} and isinstance(envelope['feedback'],list) and type(envelope['carry_forward']) is bool,'Feedback input requires explicit feedback/carry_forward envelope')
    inputs=envelope['feedback']
    if not inputs:return
    policy=ReviewerPolicy.from_dict(parse_json(_read(store.root,'analysis/reviewer-policy.json')))
    authentication=AuthenticationContext.from_dict(parse_json(_read(store.root,'analysis/authentication-context.json')))

    state['feedback']=process_feedback(store,state['review_requests'],state['proposed_actions'],inputs,
        policy=policy,authentication=authentication,carry_forward=envelope['carry_forward'])
    requests={r['request_id']:r for r in state['review_requests']}
    for approval in state['approval_requirements']:
        matched=[f for f in state['feedback'] if f['match_status']=='matched' and f['authentication']=='verified' and
            f['request_id']==approval['request_id'] and approval['subject_ids'][0] in f['subject_ids'] and
            f['responder_role']==approval['required_reviewer']]
        # Competing decisions cannot choose a date/order winner.
        if len(matched)!=1:continue
        decision=approval_for_feedback(run_id=store.run_id,request=requests[approval['request_id']],feedback=matched[0])
        for key in ('status','feedback_ids','condition_evidence_ids','conditions_satisfied'):
            if key in decision:approval[key]=decision[key]
    for action in state['proposed_actions']:
        requirements=[a for a in state['approval_requirements'] if action['id'] in a['subject_ids']]
        if any(a['status']=='rejected' for a in requirements):action['approval_status']='rejected'
        elif requirements and all(a['status'] in {'approved','not-required'} for a in requirements):action['approval_status']='approved'


def project(store, retained_requests=()):
    fifth=validate_impacts(store);chain=read_chain(store.root,count=4)+[fifth]
    records={r['id']:r for s in chain for r in stage_records(s)}
    impacts=[r for r in stage_records(fifth) if r['record_type']=='impact']
    rules=[r for r in records.values() if r['record_type'] in {'rule','policy-control'}]
    calendar=[r for r in chain[1]['state']['normalized_rows'] if r['source_id']=='CALENDAR']
    actions,accounting,no_action=build_actions(store.run_id,impacts,rules,calendar)
    state=dict(proposed_actions=actions,approval_requirements=[],escalations=[],review_requests=[],feedback=[],
        extensions={'u12_actions':dict(schema_version=VERSION,value=dict(schema_version=VERSION,draft_only=True,
            actions=accounting,no_action=no_action,calendar_rows=deepcopy(calendar)))})
    # Every unresolved coverage-only candidate and upstream limitation has a retained escalation.
    subjects=[r for r in records.values() if r['record_type'] in {'blocker','gap','conflict','diagnostic'}]
    for record in subjects:
        linked=[record['id']] if record['record_type'] in {'gap','conflict'} else list(record['evidence_ids'])
        if not linked:
            linked=[r['id'] for r in chain[1]['state']['sources'] if r['source_id'] in record.get('source_basis',[])]
        if not linked:linked=[chain[0]['state']['scope_basis'][0]['id']]
        role='Legal' if record.get('owner')=='Legal' or record['record_type']=='blocker' else 'Operations'
        state['escalations'].append(dict(id=new_record_id(store.run_id,6,'escalation'),record_type='escalation',
            summary='Review required: '+record['summary'],evidence_ids=record['evidence_ids'],
            source_basis=sorted(set(record.get('source_basis',[]))|{record['id']}),reason=record.get('reason',record['summary']),
            owner=record.get('owner'),resolution_need=record.get('resolution_need') or 'Reviewer must resolve the retained scoped question',
            subject_ids=linked,required_reviewer=role,state='unresolved'))
    for entry in fifth['state']['extensions']['u11_impacts']['value']['coverage']:
        if entry['impact_record_ids'] or entry['state'] not in {'unresolved','conflicting'}:continue
        # Coverage-only questions cannot point at a nonexistent rule/impact.
        linked=[entry['rule_id']] if entry['rule_id'] is not None else entry['evidence_ids'] or [chain[0]['state']['scope_basis'][0]['id']]
        role='Operations' if entry['basis_type']=='internal-control' and entry.get('owner')=='Operations' else 'Legal'
        state['escalations'].append(dict(id=new_record_id(store.run_id,6,'escalation'),record_type='escalation',
            summary='Coverage review for '+entry['system_id']+': '+entry['reason'],evidence_ids=entry['evidence_ids'],
            source_basis=entry['source_basis'],reason=entry['reason'],owner=entry.get('owner'),
            resolution_need=entry.get('resolution_need') or 'Reviewer must resolve exact system/rule scope',
            subject_ids=linked,required_reviewer=role,state='unresolved'))
    status=reduce_states([fifth['status'],'partial' if any(a['state']=='unresolved' for a in actions) else 'complete'])
    preliminary=build_export_model(chain,state,status);version=preliminary['draft_version'];versions=preliminary['source_versions']
    # Requests bind the complete substantive draft; none has been delivered.
    for role in ('Legal','Operations','system-owner'):
        identities=sorted({a['id'] for a in actions}|{sid for e in state['escalations'] if e['required_reviewer']==role for sid in e['subject_ids']})
        selected=[next((a for a in actions if a['id']==rid),records.get(rid)) for rid in identities]
        if not selected:continue
        index={rid:(0,r) for rid,r in records.items()}
        index.update({r['id']:(6,r) for r in actions+state['escalations']})
        systems=sorted(set().union(*(_subject_systems(r,index) for r in selected)))
        evidence=sorted({eid for r in selected for eid in r['evidence_ids']})
        request=create_review_request(run_id=store.run_id,draft_version=version,
            subject_ids=[r['id'] for r in selected],subject_system_ids=systems,source_versions=versions,evidence_ids=evidence,
            question=role+' must review scoped findings, supporting evidence and proposed responsibilities; dates and approvals remain pending.',
            required_reviewer=role)
        old=[r for r in retained_requests if r['required_reviewer']==role]
        require(len(old)<=1,'Duplicate role review request')
        if old:
            request['id']=old[0]['id'];request['request_id']=old[0]['request_id']
        state['review_requests'].append(request)
        for action in actions:
            state['approval_requirements'].append(dict(id=new_record_id(store.run_id,6,'approval'),record_type='approval',
                summary=role+' review pending for '+action['system_id'],evidence_ids=action['evidence_ids'],
                subject_ids=[action['id']],required_reviewer=role,status='pending',request_id=request['request_id'],feedback_ids=[]))
    _apply_feedback(store,state)
    state['export_model']=build_export_model(chain,state,status)
    require(state['export_model']['draft_version']==version,'Request construction changed substantive draft')
    return chain,state,status


def freeze_actions(store, *, write=True):
    from .runner import _snapshot
    retained=[]
    if not write and (store.root/SNAPSHOT_PATHS[5]).exists():
        retained=read_chain(store.root,count=6)[5]['state']['review_requests']
    chain,state,status=project(store,retained)
    predecessor=dict(snapshot_id=chain[-1]['snapshot_id'],path=SNAPSHOT_PATHS[4],sha256=sha256_bytes(_read(store.root,SNAPSHOT_PATHS[4])))
    sixth=_snapshot(store,6,state,status,store.providers,predecessor=predecessor,
        consumed=sorted(r['id'] for s in chain for r in stage_records(s)))
    if write:
        write_snapshot(store.root,sixth,upstream=chain)
        validate_actions(store)
    return sixth


@disk_verified
def validate_actions(store):
    actual=read_chain(store.root,count=6)[5];expected=freeze_actions(store,write=False)
    # Export repeats the same records. Compare their content through current-stage
    # graph canonicalization; request business UUIDs remain stable during rebuild.
    require(canonical_state(actual)==canonical_state(expected),'Stage 06 differs from exact action matching and draft export')
    return actual


def export_model(store):
    return deepcopy(validate_actions(store)['state']['export_model'])
