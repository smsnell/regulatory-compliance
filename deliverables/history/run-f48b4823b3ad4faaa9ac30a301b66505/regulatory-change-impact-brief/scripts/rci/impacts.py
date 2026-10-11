"""U11 exact scoped predicate bindings and conservative four-state dispositions.

The bounded interpretation is derived analysis. Quote checks bind its assertions
without authenticating legal interpretation or any approval.
"""
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
import shutil
import sys
from uuid import uuid4

from .validation_cache import disk_verified
from .contracts import (ASSIGNED_REVIEW_DATE, SNAPSHOT_PATHS, json_bytes, parse_json,
    require, reduce_states, sha256_bytes, validate_interpretation, validate_schema)
from .evidence import _read, _write
from .ids import BusinessKey, new_record_id, stable_business_id
from .reconcile import PREDICATES, validate_reconciliation
from .normalize import load_dictionary
from .runtime import (SKILL, file_inventory, host_command, invoke_host, preflight,
    verify_inventory, visible_usage)
from .snapshots import read_chain, stage_records, write_snapshot

VERSION = 'rci-u11-impacts/1'
STAGE = 'impact-analysis'
DIRECTORY = 'analysis/impacts'


def _chain(store):
    fourth = validate_reconciliation(store)
    return read_chain(store.root, count=3) + [fourth]


def create_impact_request(store, metadata):
    chain = _chain(store)
    index = {r['id']: r for s in chain for r in stage_records(s)}
    extracts = []
    for evidence in sorted((r for r in index.values() if r['record_type'] == 'evidence'), key=lambda r:r['id']):
        capture = index[evidence['capture_id']]
        if capture['content_type'].split(';')[0].strip().lower() not in {'text/plain','text/csv'}:
            continue
        if 'derived_from_capture_id' in capture and capture['derivation']['method'] != 'HTMLParser visible text (no scripts/styles)':
            continue
        text = _read(store.root, evidence['local_reference']).decode('utf-8')
        extracts.append(dict(evidence_id=evidence['id'],capture_id=capture['id'],path=evidence['local_reference'],
            sha256=evidence['content_hash'],locator=evidence['locator'],text=text,text_sha256=sha256_bytes(text.encode())))
    require(extracts, 'No readable retained evidence for impact bindings')
    dictionary = load_dictionary()
    request = dict(schema_version='rci-interpretation-request/1',packet_id='packet-'+uuid4().hex,
        run_id=store.run_id,stage=STAGE,created_at=store.providers.now(),assigned_review_date=ASSIGNED_REVIEW_DATE,
        expected_response_schema='rci-interpretation-response/1',
        upstream=[dict(snapshot_id=s['snapshot_id'],sequence=s['sequence'],path=SNAPSHOT_PATHS[s['sequence']-1],
            sha256=sha256_bytes(_read(store.root,SNAPSHOT_PATHS[s['sequence']-1]))) for s in chain],
        extracts=extracts,field_dictionary=dict(version=dictionary['schema_version'],fields=dictionary,
            sha256=sha256_bytes(json_bytes(dictionary))),metadata=deepcopy(metadata))
    validate_schema(request,'interpretation-request')
    _write(store.root,DIRECTORY+'/request.json',json_bytes(request))
    return request


def _binding(candidate, chain):
    require(len(candidate['conditions']) == 1, 'One explicit typed impact binding required')
    d = parse_json(candidate['conditions'][0].encode())
    require(isinstance(d,dict) and set(d)=={'schema_version','rule_id','system_id','scope','necessary','impact'},
        'Invalid impact binding fields')
    require(d['schema_version']=='rci-impact-binding/1','Unknown impact binding version')
    require(isinstance(d['scope'],str) and d['scope'].strip(),'Exact output/interaction scope required')
    require(candidate['system_ids']==[d['system_id']] and candidate['role']=='unknown' and
        not candidate['timing_candidates'] and not candidate['exception_candidates'] and candidate['uncertainty'] is None,
        'Impact binding cannot establish roles, timing, exceptions or uncertain meanings implicitly')
    rules = {r['id']:r for r in chain[2]['state']['binding_rules']+chain[3]['state']['policy_controls']}
    rule = rules.get(d['rule_id'])
    require(rule is not None and candidate['basis_type']==rule['basis_type'],'Unknown rule or changed authority basis')
    scopes = {r['rule_id']:r['system_ids'] for r in chain[2]['state']['extensions']['u09_authority']['value']['candidates']}
    require(d['system_id'] in scopes.get(rule['id'],rule.get('system_ids',[])), 'Binding outside assessed system scope')
    require(isinstance(d['necessary'],list),'Necessary predicates must be explicit')
    terms = d['necessary']+[d['impact']]
    index = {r['id']:r for s in chain for r in stage_records(s)}
    citations={(c['evidence_id'],c['quote']) for c in candidate['citations']}
    allowed = set(rule.get('predicates',[rule.get('control')])) | {rule.get('obligation',rule.get('control'))}
    for term in terms:
        require(isinstance(term,dict) and set(term)=={'predicate','equals','rule_predicate','evidence_id','quote'},
            'Each term needs exact predicate, typed value and quoted rule binding')
        require(term['predicate'] in PREDICATES,'New or reported predicate requires escalation')
        require(term['equals'] is not None and (type(term['equals']) is bool if term['predicate'] in PREDICATES[:5]
            else isinstance(term['equals'],str) and bool(term['equals'].strip())), 'Invalid predicate comparison value')
        require(term['rule_predicate'] in allowed,'Arbitrary prose cannot introduce a rule predicate')
        require(term['evidence_id'] in rule['evidence_ids'] and (term['evidence_id'],term['quote']) in citations,
            'Term lacks cited originating rule support')
        require(term['quote'] in index[term['evidence_id']]['quoted_support'],'Term quote absent from rule evidence')
        support_value=term['rule_predicate']
        if support_value.startswith('exception scope: '):support_value=support_value[len('exception scope: '):]
        elif support_value.startswith('exception: '):support_value=support_value[len('exception: '):]
        elif support_value.startswith('role='):support_value=None
        require(support_value is None or support_value in term['quote'],'Binding quote omits the exact rule predicate/control')
        if term['rule_predicate'].startswith('role='):
            require(term['predicate']==term['rule_predicate'][5:]+'_role' and term['equals'] is True,
                'Role must independently bind its affirmative role fact')
    # Every captured condition, role and exception remains a necessary input.
    # Unknown roles and exception decisions cannot be silently dropped.
    mapped={t['rule_predicate'] for t in terms}
    require(set(rule.get('predicates',[])) <= mapped,'Unbound necessary rule/role/exception condition')
    return d


def _evaluate(store, request_raw, response_raw, chain):
    result=validate_interpretation(request_raw,response_raw,root=store.root,run_id=store.run_id,stage=STAGE,upstream=chain)
    accepted, reviews = [], []
    for number,candidate in enumerate(result.response['candidates'],1):
        try:
            require(result.disposition=='proposed',result.reason or 'Unsupported impact exchange')
            d=_binding(candidate,chain)
            accepted.append(d)
            reason=None
        except (ValueError,KeyError,TypeError) as error:
            reason=str(error)
        reviews.append(dict(number=number,candidate=deepcopy(candidate),disposition='bound-draft' if reason is None else 'unresolved',reason=reason))
    return result,accepted,reviews


def submit_impact(store, proposal_bytes):
    directory=DIRECTORY+'/exchanges/'+uuid4().hex
    _write(store.root,directory+'/proposal.json',proposal_bytes)
    request_raw=_read(store.root,DIRECTORY+'/request.json')
    _write(store.root,directory+'/request.json',request_raw)
    status,reason='failed','Invalid impact proposal'
    try:
        proposal=parse_json(proposal_bytes)
        require(isinstance(proposal,dict) and set(proposal)=={'disposition','diagnostic','candidates'},'Invalid impact proposal fields')
        request=parse_json(request_raw); metadata=deepcopy(request['metadata'])
        metadata.update(reported_model=None,reported_effort=None,usage=None)
        response=dict(**proposal,schema_version='rci-interpretation-response/1',run_id=store.run_id,stage=STAGE,
            packet_id=request['packet_id'],packet_sha256=sha256_bytes(request_raw),responded_at=store.providers.now(),metadata=metadata)
        response_raw=json_bytes(response);_write(store.root,directory+'/response.json',response_raw)
        result,accepted,reviews=_evaluate(store,request_raw,response_raw,_chain(store))
        status='proposed' if accepted else 'unresolved';reason=result.reason or next((r['reason'] for r in reviews if r['reason']),None)
        pointers={name:dict(path=directory+'/'+name+'.json',sha256=sha256_bytes(raw)) for name,raw in
            [('request',request_raw),('response',response_raw)]}
        _write(store.root,DIRECTORY+'/submission.json',json_bytes(pointers))
        return dict(disposition=status,reason=reason,production_package=False)
    except (ValueError,OSError) as error:
        reason=str(error);raise
    finally:
        _write(store.root,directory+'/validation.json',json_bytes(dict(run_id=store.run_id,stage=STAGE,
            status=status,reason=reason,source_evidence=False,semantic_proof=False)))


def _submission(store,chain):
    if not (store.root/(DIRECTORY+'/submission.json')).exists():return None,None,[],[]
    pointers=parse_json(_read(store.root,DIRECTORY+'/submission.json'))
    require(isinstance(pointers,dict) and set(pointers)=={'request','response'},'Invalid impact submission')
    raws={}
    for name,pointer in pointers.items():
        require(set(pointer)=={'path','sha256'} and pointer['path'].startswith(DIRECTORY+'/exchanges/'),'Invalid impact pointer')
        raws[name]=_read(store.root,pointer['path'])
        require(sha256_bytes(raws[name])==pointer['sha256'],'Changed impact interpretation bytes')
    require(raws['request']==_read(store.root,DIRECTORY+'/request.json'),'Different impact packet')
    return (pointers,)+_evaluate(store,raws['request'],raws['response'],chain)


def _binding_key(binding):
    def term(value):return {k:value[k] for k in ('predicate','equals','rule_predicate')}
    return json_bytes(dict(rule_id=binding['rule_id'],system_id=binding['system_id'],scope=binding['scope'],
        necessary=sorted((term(t) for t in binding['necessary']),key=json_bytes),impact=term(binding['impact'])))


def disposition(authority, facts, impact_value):
    """G3 table: authority withholding precedes contradictions, then unknowns."""
    if not authority:return 'unresolved'
    if any(f['state']=='conflicting' for f in facts):return 'conflicting'
    if not facts or any(f['state']!='supported' or f.get('value') is None for f in facts) or impact_value is None:
        return 'unresolved'
    return 'supported-impact' if impact_value else 'supported-no-impact'


def negative_control_nontrigger(terms, facts):
    """Absent disclosure/timing/provenance cannot establish scoped exclusion."""
    protected={'notice_present','notice_before_first_interaction','machine_readable_provenance'}
    return sorted({term['predicate'] for term in terms if term['predicate'] in protected and
        term['equals'] is True and any(f['predicate']==term['predicate'] and f['state']=='supported' and
            f.get('value') is not None and f['value']['resolved_value'] is False for f in facts)})


def candidate_semantic_basis(candidate, basis_type):
    """Identify the captured question without analysis UUIDs or candidate order."""
    if not isinstance(candidate,dict):candidate={}
    conditions=candidate.get('conditions',[])
    timing=candidate.get('timing_candidates',[])
    conditions=conditions if isinstance(conditions,list) else []
    timing=timing if isinstance(timing,list) else []
    predicates=[];descriptor={}
    for raw in conditions+timing:
        if not isinstance(raw,str):continue
        try:
            value=parse_json(raw.encode())
            if not isinstance(value,dict):continue
            if value.get('basis_id') and value.get('meaning_key'):descriptor=value;break
            predicates.append({k:value[k] for k in ('kind','predicate','scope','value','control') if k in value})
        except (ValueError,TypeError):
            if raw in conditions:predicates.append(raw)
    semantic=dict(kind='candidate-review',basis_type=basis_type,
        basis_id=descriptor.get('basis_id'),meaning_key=descriptor.get('meaning_key'))
    if not semantic['basis_id'] or not semantic['meaning_key']:
        exceptions=candidate.get('exception_candidates',[])
        semantic.update(summary=candidate.get('summary') if isinstance(candidate.get('summary'),str) else None,
            predicates=sorted(predicates,key=json_bytes),role=candidate.get('role') if isinstance(candidate.get('role'),str) else None,
            exceptions=sorted(e for e in exceptions if isinstance(e,str)) if isinstance(exceptions,list) else [])
    return semantic


def project(store):
    chain=_chain(store);third,fourth=chain[2:]
    pointers,result,bindings,reviews=_submission(store,chain)
    state=dict(impacts=[],unaffected_items=[],conflicts=[],unresolved_items=[])
    accounting=dict(schema_version=VERSION,draft_only=True,interpretation=pointers,candidate_reviews=reviews,coverage=[])
    scope=chain[0]['state']['systems_in_scope'];facts=fourth['state']['system_facts']
    authority=third['state']['extensions']['u09_authority']['value']
    authority_candidates=[]
    if authority.get('interpretation'):
        authority_candidates=parse_json(_read(store.root,authority['interpretation']['response']['path']))['candidates']
    supported_scope={c['rule_id']:c['system_ids'] for c in authority['candidates']}
    rules=third['state']['binding_rules']+fourth['state']['policy_controls']
    by_rule=defaultdict(list)
    for binding in bindings:by_rule[(binding['rule_id'],binding['system_id'],binding['scope'])].append(binding)
    for rule in rules:
        systems=supported_scope.get(rule['id'],rule.get('system_ids',[]))
        for system in scope:
            bound=[(s,values) for (rid,sid,s),values in by_rule.items() if rid==rule['id'] and sid==system]
            if system not in systems:
                accounting['coverage'].append(dict(system_id=system,rule_id=rule['id'],rule_basis=rule['rule_version_id'],
                    basis_type=rule['basis_type'],scope=None,state='unresolved',impact_record_ids=[],evidence_ids=rule['evidence_ids'],
                    source_basis=[rule['id']],reason='Outside established candidate system scope; no affirmative exclusion inferred',owner='Legal',
                    resolution_need='Legal must confirm scoped applicability/exclusion',blocker_ids=[]));continue
            for scope_key,values in bound or [('unbound',[])]:
                binding=values[0] if len({_binding_key(v) for v in values})==1 else None
                terms=([t for v in values for t in v['necessary']+[v['impact']]] if binding is None else binding['necessary']+[binding['impact']])
                matching=[];unknown=False;comparisons=[]
                for term in terms:
                    found=[f for f in facts if f['system_id']==system and f['predicate']==term['predicate'] and
                        f['value'] is not None and f['value'].get('scope')==scope_key]
                    matching.extend(found)
                    if len(found)!=1 or found[0]['state']!='supported':unknown=True;continue
                    comparisons.append(json_bytes(found[0]['value']['resolved_value'])==json_bytes(term['equals']))
                matching=list({f['id']:f for f in matching}.values())
                established=(rule.get('applicability','established')=='established' and rule.get('effective_from') is not None and
                    rule['effective_from']<=ASSIGNED_REVIEW_DATE and (rule.get('effective_until') is None or ASSIGNED_REVIEW_DATE<rule['effective_until']))
                outcome=disposition(established,matching,None if unknown or not terms else all(comparisons))
                if len({_binding_key(v) for v in values})>1 and established:outcome='conflicting'
                missing_controls=negative_control_nontrigger(terms,matching) if outcome=='supported-no-impact' else []
                if missing_controls:outcome='unresolved'
                reason=('Established scoped rule and affirmative triggering evidence' if outcome=='supported-impact' else
                    'Established scoped rule and affirmative scoped exclusion/non-trigger evidence' if outcome=='supported-no-impact' else
                    'Relevant scoped factual assertions or predicate mappings disagree' if outcome=='conflicting' else
                    'Rule timing, exact predicate/scope binding or necessary factual/exception support remains unknown')
                if missing_controls:
                    reason='Affirmative absence of '+', '.join(missing_controls)+' does not establish a scoped exclusion/non-trigger; Legal must review the impact condition'
                key=BusinessKey(system,rule['rule_version_id'],'rule-impact',scope_key)
                owners={f['owner'] for f in matching if f['owner'] is not None};owner=next(iter(owners)) if len(owners)==1 else None
                evidence=sorted(set(rule['evidence_ids'])|{e for f in matching for e in f['evidence_ids']})
                record=dict(id=new_record_id(store.run_id,5,'impact'),record_type='impact',summary=system+': '+rule['summary']+' ('+scope_key+')',
                    evidence_ids=evidence,identity_key=asdict(key),impact_id=stable_business_id('impact',key),system_id=system,rule_id=rule['id'],
                    fact_ids=sorted(f['id'] for f in matching),state=outcome,basis_type=rule['basis_type'],
                    source_basis=sorted({rule['id']}|{b for f in matching for b in f['source_basis']}),reason=reason,owner=owner,
                    resolution_need=None if outcome.startswith('supported-') else 'System owner must verify exact scoped facts; Legal must resolve rule meanings and exceptions; Operations confirms policy activation.')
                collection='impacts' if outcome=='supported-impact' else 'unaffected_items' if outcome=='supported-no-impact' else 'unresolved_items'
                state[collection].append(record)
                accounting['coverage'].append(dict(system_id=system,rule_id=rule['id'],rule_basis=rule['rule_version_id'],basis_type=rule['basis_type'],
                    scope=scope_key,state=outcome,impact_record_ids=[record['id']],evidence_ids=evidence,source_basis=record['source_basis'],
                    reason=reason,owner=owner,resolution_need=record['resolution_need'],blocker_ids=[]))
                if outcome=='conflicting':
                    state['conflicts'].append(dict(id=new_record_id(store.run_id,5,'conflict'),record_type='conflict',summary=record['summary']+' disagreement',
                        evidence_ids=evidence,source_basis=record['source_basis'],reason=reason,owner=owner,resolution_need=record['resolution_need'],
                        subject_ids=[record['id']]+record['fact_ids'],state='conflicting'))
    for candidate in authority.get('candidate_reviews',[]):
        if candidate['disposition']=='supported-draft-rule':continue
        number=candidate['number']
        original=authority_candidates[number-1] if 0<number<=len(authority_candidates) else {'summary':candidate.get('claimed_summary')}
        basis_type='guidance' if candidate['disposition']=='guidance-context' else 'binding-legal'
        for system in scope:
            accounting['coverage'].append(dict(system_id=system,candidate_number=candidate['number'],rule_id=None,rule_basis=None,
                basis_type=basis_type,candidate_basis=candidate_semantic_basis(original,basis_type),scope=None,state='unresolved',
                impact_record_ids=[],evidence_ids=[],source_basis=candidate.get('blocker_ids') or ['U09 candidate '+str(candidate['number'])],
                reason='Candidate withheld: '+candidate['disposition'],owner='Legal',resolution_need='Legal must establish authority and exact scoped applicability',
                blocker_ids=candidate.get('blocker_ids',[])))
    if not authority.get('candidate_reviews') and not third['state']['binding_rules']:
        for system in scope:
            accounting['coverage'].append(dict(system_id=system,rule_id=None,rule_basis=None,basis_type='binding-legal',scope=None,state='unresolved',
                impact_record_ids=[],evidence_ids=[],source_basis=[b['id'] for b in third['state']['authority_blockers']] or ['authority'],
                reason='No established candidate rule basis; formal evaluation deferred',owner='Legal',resolution_need='Legal must establish candidate rule basis',
                blocker_ids=[b['id'] for b in third['state']['authority_blockers']]))
    # Retain every policy candidate, including pending/disputed versions with no control record.
    for review in fourth['state']['extensions']['u10_reconciliation']['value']['candidate_reviews']:
        candidate=review['candidate']
        if candidate['basis_type']!='internal-control':continue
        descriptor=None
        try:descriptor=parse_json(candidate['conditions'][0].encode())
        except (ValueError,IndexError,TypeError):pass
        matched_controls=[] if descriptor is None else [r for r in rules if
            r['version_key']['basis_id']=='POLICY:'+descriptor.get('basis_id','') and
            r['version_key']['meaning_key']==descriptor.get('meaning_key') and
            descriptor.get('activation')=='active' and descriptor.get('effective_from') is not None and
            descriptor['effective_from']<=ASSIGNED_REVIEW_DATE and
            (descriptor.get('effective_until') is None or ASSIGNED_REVIEW_DATE<descriptor['effective_until'])]
        if matched_controls:
            for entry in accounting['coverage']:
                if entry['rule_id'] in {r['id'] for r in matched_controls}:
                    entry.setdefault('policy_candidate_numbers',[]).append(review['number'])
            continue
        for system in scope:
            accounting['coverage'].append(dict(system_id=system,candidate_number=review['number'],rule_id=None,rule_basis=None,
                basis_type='internal-control',candidate_basis=candidate_semantic_basis(candidate,'internal-control'),scope=None,state='unresolved',impact_record_ids=[],evidence_ids=sorted({c['evidence_id'] for c in candidate['citations']}),
                source_basis=['U10 policy candidate '+str(review['number'])],reason='Policy candidate activation/version/scope unresolved',owner='Operations',
                resolution_need='Operations confirms activation; Legal resolves meaning/version disputes',blocker_ids=[]))
    state['extensions']={'u11_impacts':dict(schema_version=VERSION,value=accounting)}
    status=reduce_states([fourth['status'],'partial' if any(c['state'] in {'unresolved','conflicting'} for c in accounting['coverage']) else 'complete'])
    return chain,state,status,pointers,result


def canonical_state(snapshot):
    """Remove random current-stage identifiers while preserving graph multiplicity."""
    records={r['id']:r for r in stage_records(snapshot)}
    def replace(value,trail=()):
        if isinstance(value,str) and value in records:
            require(value not in trail,'Cyclic derived accounting')
            return replace({k:v for k,v in records[value].items() if k!='id'},trail+(value,))
        if isinstance(value,dict):return {k:replace(v,trail) for k,v in value.items() if k!='id'}
        if isinstance(value,list):return sorted((replace(v,trail) for v in value),key=json_bytes)
        return value
    return json_bytes(dict(state=replace(snapshot['state']),status=snapshot['status'],consumed=snapshot['consumed_record_ids'],
        bindings=snapshot.get('interpretation_bindings',[]),decisions=replace(snapshot['decisions']),unresolved=replace(snapshot['unresolved'])))


def freeze_impacts(store, *, write=True):
    from .runner import _snapshot
    chain,state,status,pointers,result=project(store)
    predecessor=dict(snapshot_id=chain[-1]['snapshot_id'],path=SNAPSHOT_PATHS[3],sha256=sha256_bytes(_read(store.root,SNAPSHOT_PATHS[3])))
    fifth=_snapshot(store,5,state,status,store.providers,predecessor=predecessor,
        consumed=sorted(r['id'] for s in chain for r in stage_records(s)))
    if result is not None and result.disposition=='proposed':fifth['interpretation_bindings']=[pointers]
    if write:
        write_snapshot(store.root,fifth,upstream=chain)
        validate_impacts(store)
    return fifth


@disk_verified
def validate_impacts(store):
    actual=read_chain(store.root,count=5)[4];expected=freeze_impacts(store,write=False)
    require(canonical_state(actual)==canonical_state(expected),'Stage 05 differs from verified predicate bindings and coverage')
    return actual


def interpret_impacts(store, config, *, timeout=180):
    chain=_chain(store)
    if not chain[2]['state']['binding_rules'] and not chain[3]['state']['policy_controls']:return freeze_impacts(store)
    host,version=preflight(config);root=store.root
    if not (root/SKILL.name).exists():
        shutil.copytree(SKILL,root/SKILL.name,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(SKILL.parent/'snapshot.schema.json',root/'snapshot.schema.json')
        directory=root/'.agents/skills';directory.mkdir(parents=True)
        (directory/SKILL.name).symlink_to('../../'+SKILL.name,target_is_directory=True)
    def pointer(path):return dict(path=path,sha256=sha256_bytes(_read(root,path)))
    metadata=dict(host_version=version,requested_model=config['host']['model'],requested_effort=config['host']['effort'],
        reported_model=None,reported_effort=None,usage=None,
        instruction_versions=[pointer(SKILL.name+'/SKILL.md'),pointer(SKILL.name+'/references/impacts.md')],
        reference_versions=[pointer(SKILL.name+'/references/g3-fact-and-impact-contract.md')])
    create_impact_request(store,metadata);immutable=file_inventory(root)
    command=host_command(host,root,config['host']['model'],config['host']['effort'])
    prompt=(f'Use regulatory-change-impact-brief U11 impact branch. Read {root/SKILL.name}/references/impacts.md '
        f'and analysis/impacts/request.json and frozen Stage03/04. Submit once: {sys.executable} '
        f'{root/SKILL.name}/scripts/stage.py submit-impact --root {root} --proposal {root}/analysis/impacts/agent-proposal.json. '
        'Stop after submission; supervisor writes Stage05. No later units.')
    _write(root,DIRECTORY+'/host-prompt.txt',prompt.encode())
    _write(root,DIRECTORY+'/host-invocation.json',json_bytes(dict(command=command,metadata=metadata)))
    invoke_host(command,prompt,root,timeout,analysis_directory=DIRECTORY);verify_inventory(root,immutable)
    require((root/(DIRECTORY+'/submission.json')).is_file(),'Host did not submit impact interpretation')
    _write(root,DIRECTORY+'/host-outcome.json',json_bytes(dict(visible_usage=visible_usage(root,analysis_directory=DIRECTORY),production_package=False)))
    return freeze_impacts(store)
