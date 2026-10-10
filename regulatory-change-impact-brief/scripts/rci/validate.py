"""Independent on-disk artifact semantics and Stage 07 publication validation."""
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
from html import unescape
import io
import re
from pathlib import Path
from icalendar import Calendar

from .contracts import (SNAPSHOT_PATHS, json_bytes, parse_json, package_path, require,
                        reduce_states, sha256_bytes)
from .ids import new_record_id
from .snapshots import read_chain, stage_records, write_snapshot

PATHS = ('impact-register.csv','compliance-brief.md','action-calendar.ics')
CSV_COLUMNS = ['impact_id','system_id','rule_ref','state','evidence_ids','reason','owner',
    'proposed_action','proposed_due_date','approval_status','run_id','assigned_review_date',
    'action_ids','resolution_need','basis_type','source_versions']


def _csv(raw, model):
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8'),newline=''))
    require(reader.fieldnames==CSV_COLUMNS,'CSV columns differ')
    rows=list(reader)
    require(len(rows)==len(model['impacts'])+len(model.get('unresolved_coverage',[])),'CSV coverage differs')
    rules={r['id']:r for r in model['rules']}
    actual={}
    for row in rows:
        require(None not in row and all(v is not None for v in row.values()),'malformed CSV row')
        for k,v in row.items():
            if v.startswith("'"):
                require(len(v)>1 and (v[1] in "'=+-@\t\r\n" or v[1:].lstrip(" \t\r\n").startswith(("=","+","-","@"))),'invalid display escaping')
                row[k]=v[1:]
            else: require(not v.startswith(('=','+','-','@','\t','\r','\n')) and not v.lstrip(' \t\r\n').startswith(('=','+','-','@')),'unsafe CSV cell')
        require(row['impact_id'] not in actual,'duplicate CSV impact')
        actual[row['impact_id']]=row
    for i in model['impacts']:
        actions=sorted([a for a in model['actions'] if i['id'] in a['impact_ids']],key=lambda a:a['action_id'])
        r=rules[i['rule_id']]
        expected={k:i[k] or '' for k in ('impact_id','system_id','state','reason','owner','basis_type')}
        expected.update(rule_ref=r['rule_version_id'],evidence_ids=';'.join(i['evidence_ids']),
            proposed_action=';'.join(a['summary'] for a in actions),
            proposed_due_date=';'.join(a['proposed_due_date'] or '' for a in actions),
            approval_status=';'.join(a['approval_status'] for a in actions) if actions else 'not-required',
            run_id=model['run_id'],assigned_review_date=model['assigned_review_date'],
            action_ids=';'.join(a['action_id'] for a in actions),
            resolution_need=i['resolution_need'] or ('No action required for this supported scope.' if not actions else ';'.join(a['date_basis'] for a in actions)),
            source_versions=';'.join(r.get('source_versions',[r['rule_version_id']])))
        require(actual.get(i['impact_id'])==expected,'CSV differs from Stage 06: '+i['impact_id'])
        for a in actions:
            if a['proposed_due_date']: date.fromisoformat(a['proposed_due_date'])

    for i in model.get('unresolved_coverage',[]):
        r=rules.get(i['rule_id'])
        expected={k:i[k] or '' for k in ('impact_id','system_id','state','reason','owner','basis_type','resolution_need')}
        expected.update(rule_ref=r['rule_version_id'] if r else '', evidence_ids=';'.join(i['evidence_ids']),
            proposed_action='', proposed_due_date='', approval_status='pending', action_ids='',
            run_id=model['run_id'], assigned_review_date=model['assigned_review_date'],
            source_versions=';'.join(i['source_versions']))
        require(actual.get(i['impact_id'])==expected,'CSV unresolved coverage differs: '+i['impact_id'])


def _brief(raw, model):
    # Read headings and field lines, independent of renderer execution.
    lines=[unescape(line) for line in raw.decode('utf-8').splitlines() if line]
    headers=['Scope','Source quality','Source limitations','Supported observations','Conflicts',
             'Unresolved scope','Proposed actions and dates','Existing operational calendar','Decisions requested','Engineering decisions','Evidence index']
    if 'source_resolution' in model: headers.insert(3,'Source inspection resolution')
    require([l[3:] for l in lines if l.startswith('## ')]==headers,'brief required sections differ')
    for k,v in [('Run',model['run_id']),('Assigned review date',model['assigned_review_date']),
                ('Recipients',';'.join(model['recipients'])),('Draft','true'),('Run status',model['status']),('Draft version',model['draft_version'])]:
        require(lines.count(k+': '+v)==1,'brief metadata differs: '+k)
    require(';'.join(model['systems_in_scope']) in lines,'brief scope missing')
    records={}; placements={}; current=None; section=None
    for line in lines:
        if line.startswith('### '):
            current=line[4:];require(current not in records,'duplicate brief record');records[current]={};placements[current]=section
        elif line.startswith('## '): current=None;section=line[3:]
        elif current is not None and ': ' in line:
            k,v=line.split(': ',1);require(k not in records[current],'duplicate brief field');records[current][k]=v
    rules={r['id']:r for r in model['rules']}
    expected={}
    if 'source_resolution' in model:
        resolution=model['source_resolution']
        expected['Capture resolution']={
            'Original upstream status':resolution['original_upstream_status'],
            'Effective upstream status':resolution['effective_upstream_status'],
            'Resolved diagnostics':';'.join(resolution['resolved_diagnostic_ids']) or 'None recorded',
            'Unresolved diagnostics':';'.join(resolution['unresolved_diagnostic_ids']) or 'None recorded',
            'Report sources':';'.join(resolution['report_source_ids']) or 'None recorded'}
        for assessment in resolution['legal_assessments']:
            expected['Legal source assessment '+assessment['source_id']]={
                'Source':assessment['source_id'],'Resolved diagnostics':';'.join(assessment['diagnostic_ids']),
                'Rules':';'.join(assessment['rule_ids']),'Evidence':';'.join(assessment['evidence_ids'])}
        for entry in resolution['report_resolutions']:
            report,support=entry['report'],entry['resolution']
            expected['Report inspection '+report['source_id']]={
                'Source row':report['source_business_id'],'System':report['system_id'],'Reference':report['reference'],
                'Owner':report['owner'] or 'Unresolved; owner confirmation required','Original report result':report['result'],
                'Attempts':';'.join(report['attempt_ids']),'Captures':';'.join(report['capture_ids']),
                'Evidence':';'.join(report['evidence_ids']),'Fact candidates':';'.join(map(str,entry['candidate_numbers'])),
                'Declaration candidates':';'.join(map(str,support['declaration_candidate_numbers'])),
                'Scopes':';'.join(support['scopes']),'Resolution evidence':';'.join(support['evidence_ids']),
                'Reason':support['reason']}
    for i in model['impacts']:
        expected['Impact '+i['impact_id']]={'System':i['system_id'],'Scope':i['identity_key']['distinguishing_scope'],
            'Rule':rules[i['rule_id']]['rule_version_id'],'Basis':i['basis_type'],'State':i['state'],
            'Observation':i['summary'],'Reason':i['reason'],'Owner':i['owner'] or 'Unresolved; owner confirmation required',
            'Resolution':i['resolution_need'] or 'Supported draft scope; human review pending','Evidence':';'.join(i['evidence_ids'])}
    for i in model.get('unresolved_coverage',[]):
        r=rules.get(i['rule_id'])
        expected['Unresolved item '+i['impact_id']]={'System':i['system_id'],
            'Scope':i['scope'] or 'Not established; scope review required',
            'Rule':r['rule_version_id'] if r else 'Not established; Legal review required',
            'Basis':i['basis_type'],'State':i['state'],'Observation':i['summary'],
            'Reason':i['reason'],'Owner':i['owner'] or 'Unresolved; owner confirmation required',
            'Resolution':i['resolution_need'],'Evidence':';'.join(i['evidence_ids'])}
    for a in model['actions']:
        expected['Action '+a['action_id']]={'System':a['system_id'],'Scope':a['distinguishing_scope'],'Proposal':a['summary'],
            'Owner':a['owner'] or 'Unresolved; owner confirmation required','Proposed date':a['proposed_due_date'] or 'Undated',
            'Existing operational date':a['existing_due_date'] or 'Not established','Date basis':a['date_basis'],
            'Approval':a['approval_status'],'Impacts':';'.join(i['impact_id'] for i in model['impacts'] if i['id'] in a['impact_ids']),
            'Evidence':';'.join(a['evidence_ids'])}
    for row in model.get('calendar_context',[]):
        fields=row['values']['fields']; raw_values=row['values'].get('raw',{});native=dict(zip(raw_values.get('headers',[]),raw_values.get('cells',[])))
        expected['Calendar row '+row['id']]={'Source row':row['source_business_id'],'System':row['system_id'],
            'Native action':fields.get('action') or 'Not established',
            'Existing operational date':fields.get('existing_due_date') or 'Not established',
            'Reported owner':fields.get('owner') or 'Not established',
            'Operational status':fields.get('operational_status') or 'Not established',
            'Required reviewer':fields.get('required_reviewer') or 'Not established',
            'Source date text':native.get('due_date') or 'Not established',
            'Source status text':native.get('status') or 'Not established',
            'Source review path':native.get('approval_required') or 'Not established',
            'Evidence':';'.join(row['evidence_ids'])}
    for r in model['review_requests']:
        expected['Request '+r['request_id']]={'Reviewer':r['required_reviewer'],'Question':r['question'],
            'Subjects':';'.join(r['subject_ids']),'Source versions':';'.join(r['source_versions']),
            'Delivery':r['delivery_status'],'Evidence':';'.join(r['evidence_ids'])}
    require(records==expected,'brief records differ from Stage 06')
    allowed=['# Regulatory change impact — draft',
        'Source rows retain operational dates, statuses and review paths; they do not establish approval or completion.',
        'Human review is required. Requests below are prepared and have not been sent.',
        'Exact reviewed artifact hashes are detached in [Stage 07](snapshots/07-publication-validation.json).',
        ';'.join(model['systems_in_scope'])]
    if 'source_resolution' in model:
        allowed.append('Original capture diagnostics and historical source statuses remain recorded above.')
    allowed += ['## '+h for h in headers]
    allowed += [k+': '+v for k,v in [('Run',model['run_id']),('Assigned review date',model['assigned_review_date']),
        ('Recipients',';'.join(model['recipients'])),('Draft','true'),('Run status',model['status']),('Draft version',model['draft_version'])]]
    for identity,fields in expected.items():
        allowed.append('### '+identity)
        allowed.extend(k+': '+v for k,v in fields.items())
        if identity.startswith('Impact '):
            state=fields['State']
            placement='Supported observations' if state.startswith('supported-') else 'Conflicts' if state=='conflicting' else 'Unresolved scope'
        elif identity.startswith('Unresolved item '): placement='Unresolved scope'
        elif identity.startswith('Calendar row '): placement='Existing operational calendar'
        elif identity=='Capture resolution' or identity.startswith(('Legal source assessment ','Report inspection ')):
            placement='Source inspection resolution'
        else: placement='Proposed actions and dates' if identity.startswith('Action ') else 'Decisions requested'
        require(placements[identity]==placement,'brief record in wrong section')
    for states in ({'supported-impact','supported-no-impact'},{'conflicting'},{'unresolved'}):
        if not any(i['state'] in states for i in model['impacts']) and not (states=={'unresolved'} and model.get('unresolved_coverage')): allowed.append('None recorded.')
    if not model.get('calendar_context'): allowed.append('No retained operational calendar rows.')
    if not model['limitations']: allowed.append('No additional recorded limitations.')
    if not model['actions']: allowed.append('No supportable action proposals recorded.')
    if not model['review_requests']: allowed.append('No additional decisions requested.')
    allowed += [f"- {r['source_id']}: {r['retrieval_status']}; {r['summary']} [{r['id']}]" for r in model['source_quality']]
    allowed += [f"- {r['summary']} [{r['id']}]; evidence: {';'.join(r['evidence_ids'])}; resolution: {r.get('resolution_need') or r.get('reason') or 'See retained source assessment.'}" for r in model['limitations']]
    allowed += [f"- [{d['id']}] {d['summary']}; chosen: {d['chosen_behavior']}; rationale: {d['rationale']}; evidence: {';'.join(d['evidence_ids'])}" for d in model['decisions']]
    allowed += [f"- [{e['id']}] {e['local_reference']}; {e['content_hash']}; locator: {e['locator']}" for e in model['evidence_index']]
    require(Counter(lines)==Counter(allowed),'brief contains missing, repeated or unsupported prose')
    fixed=set(['# Regulatory change impact — draft',
        'Source rows retain operational dates, statuses and review paths; they do not establish approval or completion.',*('## '+h for h in headers),
        'Human review is required. Requests below are prepared and have not been sent.',
        'Exact reviewed artifact hashes are detached in [Stage 07](snapshots/07-publication-validation.json).'])
    if 'source_resolution' in model:
        fixed.add('Original capture diagnostics and historical source statuses remain recorded above.')
    for line in raw.decode('utf-8').splitlines():
        if not line or line in fixed: continue
        payload=line[4:] if line.startswith('### ') else line[2:] if line.startswith('- ') else line
        payload=re.sub(r'&(?:#[0-9]+|#x[0-9a-fA-F]+|amp|lt|gt|quot|apos);', '', payload)
        require(not any(c in payload for c in '\\`*_#!()+~|<>'),'brief contains unescaped source markup')
        require(payload.count('[')==payload.count(']')==(1 if line.startswith('- ') else 0),'brief contains unescaped source link syntax')

    for source in model['source_quality']:
        require(f"- {source['source_id']}: {source['retrieval_status']}; {source['summary']} [{source['id']}]" in lines,'brief source quality missing')
    for r in model['limitations']:
        require(f"- {r['summary']} [{r['id']}]; evidence: {';'.join(r['evidence_ids'])}; resolution: {r.get('resolution_need') or r.get('reason') or 'See retained source assessment.'}" in lines,'brief limitation missing')
    for d in model['decisions']:
        require(f"- [{d['id']}] {d['summary']}; chosen: {d['chosen_behavior']}; rationale: {d['rationale']}; evidence: {';'.join(d['evidence_ids'])}" in lines,'brief decision missing')
    for e in model['evidence_index']:
        require(f"- [{e['id']}] {e['local_reference']}; {e['content_hash']}; locator: {e['locator']}" in lines,'brief evidence link missing')
    require('Exact reviewed artifact hashes are detached in [Stage 07](snapshots/07-publication-validation.json).' in lines,'brief detached binding missing')


def _calendar(raw, model):
    require(raw.endswith(b'\r\n') and b'\n' not in raw.replace(b'\r\n',b''),'calendar CRLF required')
    require(all(len(line)<=75 for line in raw.split(b'\r\n')),'calendar line exceeds 75 octets')
    cal=Calendar.from_ical(raw)
    require(str(cal.get('VERSION'))=='2.0' and bool(cal.get('PRODID')),'calendar header missing')
    require(set(cal.keys())=={'VERSION','PRODID'},'unsupported calendar properties')
    events=cal.walk('VEVENT'); actions=[a for a in model['actions'] if a['proposed_due_date'] is not None]
    require(len(events)==len(actions) and len(cal.subcomponents)==len(events),'calendar event coverage differs')
    expected={a['action_id']+'@regulatory-change-impact-brief':a for a in actions}
    seen=set()
    for event in events:
        uid=str(event.get('UID'));require(uid in expected and uid not in seen,'calendar UID differs');seen.add(uid)
        require(set(event.keys())=={'UID','DTSTAMP','DTSTART','DTEND','SUMMARY','DESCRIPTION','STATUS'},'unsupported event properties')
        a=expected[uid];day=date.fromisoformat(a['proposed_due_date'])
        for prop in ('UID','DTSTAMP','DTSTART','DTEND','SUMMARY','DESCRIPTION','STATUS'):
            require(prop in event and not isinstance(event[prop],list),'calendar missing or repeated '+prop)
        require(type(event.decoded('DTSTART')) is date and event.decoded('DTSTART')==day and
            type(event.decoded('DTEND')) is date and event.decoded('DTEND')==day+timedelta(days=1),'calendar date/exclusive end differs')
        require(event['DTSTART'].params.get('VALUE')=='DATE','calendar all-day type differs')
        stamp=event.decoded('DTSTAMP')
        require(stamp.utcoffset()==timedelta(0) and stamp==datetime.fromisoformat(model['created_at'].replace('Z','+00:00')).replace(microsecond=0),'calendar UTC stamp differs')
        require(str(event['STATUS'])=='TENTATIVE' and str(event['SUMMARY'])==a['summary'],'calendar summary/status differs')
        description='\n'.join(['Action: '+a['action_id'],'System: '+a['system_id'],
            'Responsible role: '+(a['owner'] or 'Unresolved; owner confirmation required'),
            'Source/decision basis: '+';'.join(a.get('source_basis',[])), 'Date basis: '+a['date_basis'],
            'Approval: '+a['approval_status'],'Run: '+model['run_id'],'Evidence: '+';'.join(a['evidence_ids']),
            'Draft proposal; human review required.'])
        require(str(event['DESCRIPTION'])==description,'calendar description differs')


def validate_artifacts(root, model):
    for path,check in zip(PATHS,(_csv,_brief,_calendar)):
        check(package_path(root,path).read_bytes(),model)
    return True


def _model(root):
    from .actions import validate_actions
    from .evidence import EvidenceStore
    sixth=validate_actions(EvidenceStore(root,parse_json((root/SNAPSHOT_PATHS[0]).read_bytes())['run_id']))
    return sixth['state']['export_model']


def freeze_publication(store):
    from .runner import _snapshot
    chain=read_chain(store.root,count=6)
    model=_model(store.root)
    artifacts=[]; checks=[]; missing=[]
    evidence=[e['id'] for e in model['evidence_index']]
    subjects=[r['id'] for r in model['impacts']+model['actions']+model['review_requests']]
    for path,check in zip(PATHS,(_csv,_brief,_calendar)):
        result='passed'; observed='Parsed values agree with frozen Stage 06.'
        target=package_path(store.root,path)
        if not target.is_file():
            result='failed';observed='Required artifact is missing.';missing.append(dict(path=path,reason=observed))
        else:
            raw=target.read_bytes()
            try: check(raw,model)
            except (ValueError,KeyError,TypeError,UnicodeError) as error: result='failed';observed=str(error)
            artifacts.append(dict(id=new_record_id(store.run_id,7,'artifact'),record_type='artifact',
                summary='Draft '+path+' for '+store.run_id,evidence_ids=evidence,path=path,sha256=sha256_bytes(raw),
                validation_status='valid' if result=='passed' else 'invalid',subject_ids=subjects))
        checks.append(dict(id=new_record_id(store.run_id,7,'validation-check'),record_type='validation-check',
            summary=path+' syntax and independent semantic comparison',evidence_ids=evidence,check_kind=path,
            result=result,expected='Required artifact parses and agrees exactly with Stage 06.',observed=observed,subject_ids=subjects))
    from .reconcile import resolved_run_status
    status=reduce_states([resolved_run_status(store.root,chain),
        'failed' if any(c['result']=='failed' for c in checks) else 'complete'])
    publication='failed' if status=='failed' else 'blocked' if status=='blocked' else 'validated'
    bindings=[]
    if len(artifacts)==3:
        pointers=[{k:a[k] for k in ('path','sha256')} for a in artifacts]
        bindings=[dict(request_id=r['request_id'],run_id=store.run_id,draft_version=r['draft_version'],artifacts=pointers) for r in model['review_requests']]
    state=dict(artifacts=artifacts,validation_checks=checks,publication_status=publication,missing_artifacts=missing,
        review_bindings=bindings,extensions={'publication_model':{'schema_version':'rci-publication-model/1',
            'value':{'export_fingerprint':sha256_bytes(json_bytes(model)),'path_resolution':'package-root-relative'}}})
    previous=chain[-1]
    final=_snapshot(store,7,state,status,store.providers,
        predecessor=dict(snapshot_id=previous['snapshot_id'],path=SNAPSHOT_PATHS[5],sha256=sha256_bytes((store.root/SNAPSHOT_PATHS[5]).read_bytes())),
        consumed=[r['id'] for s in chain for r in stage_records(s)])
    write_snapshot(store.root,final,upstream=chain)
    return final


def validate_package(root):
    """Validate a draft including honest blocked output; never accept failed output."""
    root=Path(root);chain=read_chain(root)
    model=_model(root)
    validate_artifacts(root,model)
    final=chain[-1]
    from .reconcile import resolved_run_status
    require(final['status']==resolved_run_status(root,chain[:-1]),'publication aggregate differs from reconstructed source resolution')
    require(final['status']!='failed' and final['state']['publication_status']!='failed','failed publication')
    require(len(final['state']['artifacts'])==3 and not final['state']['missing_artifacts'] and
        all(c['result']=='passed' for c in final['state']['validation_checks']),'incomplete publication validation')
    require(final['state']['extensions']['publication_model']['value']=={
        'export_fingerprint':sha256_bytes(json_bytes(model)),'path_resolution':'package-root-relative'},'publication export binding differs')
    require({b['request_id'] for b in final['state']['review_bindings']}=={r['request_id'] for r in model['review_requests']},'review bindings incomplete')
    return chain
