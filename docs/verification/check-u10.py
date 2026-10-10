#!/usr/bin/env python3
"""Independent U10 specimen inspection; stdlib only, no runtime/test helpers.

Run on a synthetic acceptance run root and save stdout. Quote matches prove
binding; the verifier records scoped observations for human semantic inspection.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
def read(path):return (root/path).read_bytes()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(read(path))
def ensure(value,reason):
    if not value:raise AssertionError(reason)
paths=['snapshots/01-scope.json','snapshots/02-source-capture.json',
       'snapshots/03-authority-and-timing.json','snapshots/04-evidence-reconciliation.json']
chain=[load(path) for path in paths]
run=chain[0]['run_id'];scope=chain[0]['state']['systems_in_scope']
ensure(len(set(scope))==8 and chain[0]['state']['assigned_review_date']=='2026-08-26','scope/date')
for index,snapshot in enumerate(chain):
    ensure(snapshot['run_id']==run and snapshot['sequence']==index+1,'run/stage')
    if index:
        ensure(snapshot['predecessor']==dict(snapshot_id=chain[index-1]['snapshot_id'],path=paths[index-1],
            sha256=digest(read(paths[index-1]))),'predecessor bytes')
second=chain[1]['state'];fourth=chain[3]['state'];a=fourth['extensions']['u10_reconciliation']['value']
records={r['id']:r for snapshot in chain for values in snapshot['state'].values() if isinstance(values,list)
         for r in values if isinstance(r,dict) and 'id' in r}
evidence={e['id']:e for e in second['evidence']}
for capture in second['captures']:ensure(digest(read(capture['local_reference']))==capture['content_hash'],'capture hash')
for e in evidence.values():
    ensure(digest(read(e['local_reference']))==e['content_hash'],'evidence hash')
    ensure(e['quoted_support'].encode() in read(e['local_reference']),'evidence quote')
rows=second['normalized_rows'];tables=second['extensions']['u08_capture']['value']['raw_tables']
ensure(len(a['register_rows'])==sum(max(0,len(t['rows'])-1) for t in tables),'raw occurrence count')
ensure(a['register_tables']==tables,'raw tables')
for table in tables:
    ensure(list(csv.reader(io.StringIO(read(table['source_basis'][1]).decode())))==table['rows'],'raw source table')
for table in tables:
    for number,cells in enumerate(table['rows'][1:],2):
        loc=f"{table['tab_title']} (gid {table['sheet_id']}) row {number}"
        entries=[e for e in a['register_rows'] if e['source_id']==table['source_id'] and e['locator']==loc]
        ensure(len(entries)==1 and entries[0]['raw_cells']==cells and entries[0]['output_record_ids'],'raw row disposition')
ensure({e['source_row_id'] for e in a['normalized_rows']}=={r['id'] for r in rows},'all normalized rows')
ensure([e['report'] for e in a['reports']]==second['extensions']['u08_reports']['value']['reports'],'all report occurrences')
ensure({e['system_id'] for e in a['systems']}==set(scope),'all systems')
for system in a['systems']:
    for register,members in system['registers'].items():
        ensure(members==[r['id'] for r in rows if r['system_id']==system['system_id'] and r['source_id']==register], 'membership')
for context in a['calendar_context']:
    row=records[context['source_row_id']]
    ensure(context['fields']==row['values']['fields'] and context['system_id']==row['system_id'],'calendar source values')
    ensure(context['approval_status']=='pending' and context['completion_status']=='unresolved' and context['scope_expansion'] is None,'status/ALL boundary')
observations=[]
for fact in fourth['system_facts']:
    ensure(all(eid in evidence for eid in fact['evidence_ids']),'fact evidence')
    if fact['value'] is None:ensure(fact['state']=='unresolved','unknown fact')
    elif not fact['predicate'].startswith('reported.'):
        observations.append(dict(system_id=fact['system_id'],predicate=fact['predicate'],state=fact['state'],value=fact['value']))
conflicts=[]
for conflict in fourth['conflicts']:
    ensure(conflict['reason'] and conflict['resolution_need'] and 'owner' in conflict,'conflict resolution')
    values=[records[identity]['value'] for identity in conflict['subject_ids'] if records[identity]['record_type']=='fact']
    conflicts.append(dict(id=conflict['id'],reason=conflict['reason'],owner=conflict['owner'],values=values,
        evidence_ids=conflict['evidence_ids'],resolution_need=conflict['resolution_need']))
for incident in fourth['incident_evidence']:
    detail=json.loads(incident['details']);row=records[detail['source_row_id']]
    ensure(detail['fields']==row['values']['fields'],'incident occurrence')
    raw=row['values']['raw']
    ensure(detail['raw']==raw and detail['validation_status']==row['values']['validation_status'],'incident raw/validation')
    ensure(incident['source_native_status']==raw['cells'][raw['headers'].index('status')],'native incident status')
    ensure(detail['resolution_status']=='unresolved' and detail['approval_status']=='pending','closed/status')
quotes=[]
pointers=a['interpretation']
if pointers:
    for pointer in pointers.values():ensure(digest(read(pointer['path']))==pointer['sha256'],'exchange hash')
    request=load(pointers['request']['path']);response=load(pointers['response']['path'])
    ensure(response['packet_sha256']==digest(read(pointers['request']['path'])) and request['run_id']==response['run_id']==run,'packet/run')
    ensure(request['stage']==response['stage']=='evidence-reconciliation','exchange stage')
    for review in a['candidate_reviews']:
        ensure(review['candidate']==response['candidates'][review['number']-1],'retained candidate')
        if review['disposition']=='accepted-draft-assertion':
            d=json.loads(review['candidate']['conditions'][0]);ev=evidence[d['evidence_id']]
            ensure(d['quote'].encode() in read(ev['local_reference']),'accepted literal support')
            quotes.append(dict(assessment=d,source_path=ev['local_reference'],source_sha256=ev['content_hash']))
for control in fourth['policy_controls']:
    ensure(control['basis_type']=='internal-control' and control['system_ids']==scope,'policy scope/basis')
    ensure(any(control['control'] in q['assessment']['quote'] and q['assessment']['kind']=='policy-control' for q in quotes),'policy control support')
for name in ['snapshots/05-impact-analysis.json','snapshots/06-actions-and-approvals.json',
             'snapshots/07-publication-validation.json','impact-register.csv','compliance-brief.md','action-calendar.ics']:
    ensure(not (root/name).exists(),'later output unexpectedly produced')
# Independent semantic oracle for this synthetic specimen's present/absent claims.
for observation in observations:
    if observation['predicate']=='notice_present':
        for assertion in observation['value']['assertions']:
            quote=next(q['assessment']['quote'] for q in quotes if q['assessment']['evidence_id'] in assertion['evidence_ids']
                and q['assessment']['value']==assertion['value'] and q['assessment']['scope']==observation['value']['scope'])
            if 'notice is present' in quote or 'visible label present' in quote:ensure(assertion['value'] is True,'positive notice meaning')
            if 'notice is absent' in quote:ensure(assertion['value'] is False,'negative notice meaning')
print(json.dumps(dict(run_id=run,root=str(root),inspector='stdlib independent byte/CSV/JSON inspector plus synthetic notice semantic oracle',
    snapshot_hashes={path:digest(read(path)) for path in paths},status=chain[3]['status'],scope=scope,
    raw_rows=len(a['register_rows']),normalized_rows=len(rows),reports=len(a['reports']),
    system_membership=a['systems'],observations=observations,conflicts=conflicts,policy_controls=fourth['policy_controls'],
    inspected_quotes=quotes,later_outputs_absent=True,live_company_or_legal_acceptance=False),indent=2))
