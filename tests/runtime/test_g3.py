"""G3 cross-unit fact/authority checks. No Stage 05 or impact engine."""
import pytest

from rci.evidence import EvidenceStore
from rci.reconcile import validate_reconciliation
from runtime.test_u10 import (REPORT, capture, captured, clone, packet, candidate, descriptor,
    set_descriptor, submit, fourth, accounting, policy_candidate)


@pytest.mark.parametrize('values,stale,expected,resolved',[
    ([True,None],False,'unresolved',None),
    ([True,False,None],False,'conflicting',None),
    ([True,True],False,'supported',True),
    ([False,False],False,'supported',False),
    ([True,False],True,'conflicting',None),
])
def test_unknown_conflict_and_typed_false_propagation(captured,tmp_path,values,stale,expected,resolved):
    root=clone(captured,tmp_path);request=packet(root)
    claims=[]
    for value in values:
        c=candidate(request,value=value,quote=REPORT.splitlines()[1 if value is False else 0])
        if stale and value is False:
            d=descriptor(c);d['review_date_quote']=None;set_descriptor(c,d)
        claims.append(c)
    claims.append(candidate(request,value=True,quote=REPORT.splitlines()[2],scope='public',kind='page-capture'))
    submit(root,claims);snapshot=fourth(root)
    facts=[f for f in snapshot['state']['system_facts'] if f['predicate']=='notice_present' and f['value']]
    chat=next(f for f in facts if f['value']['scope']=='learner chat')
    public=next(f for f in facts if f['value']['scope']=='public')
    assert chat['state']==expected and chat['value']['resolved_value'] is resolved
    assert len(chat['value']['assertions'])==len(values)
    assert public['state']=='supported' and public['value']['resolved_value'] is True
    assert len(accounting(snapshot)['candidate_reviews'])==len(claims)
    assert chat['evidence_ids'] and chat['owner']=='Marketing'
    if expected!='supported':assert chat['resolution_need']
    assert not (root/'snapshots/05-impact-analysis.json').exists()
    validate_reconciliation(EvidenceStore(root,root.name))


def test_facts_and_internal_control_survive_blocked_legal_authority(tmp_path):
    root=capture(tmp_path,supported_authority=False);request=packet(root)
    submit(root,[candidate(request),candidate(request,value=False,quote=REPORT.splitlines()[1]),
        policy_candidate(request)])
    snapshot=fourth(root)
    assert snapshot['status']=='blocked'
    fact=next(f for f in snapshot['state']['system_facts'] if f['predicate']=='notice_present' and f['value'])
    assert fact['state']=='conflicting' and len(fact['value']['assertions'])==2
    assert snapshot['state']['policy_controls'][0]['basis_type']=='internal-control'
    assert not (root/'snapshots/05-impact-analysis.json').exists()
    validate_reconciliation(EvidenceStore(root,root.name))


def test_unassessed_newer_capture_rejected_through_real_packet(tmp_path):
    from copy import deepcopy
    import httpx
    from rci.contracts import json_bytes
    from rci.evidence import _write
    from rci.runner import run_stages
    from rci.runtime import Providers
    from rci.source_manifest import manifest
    from rci.snapshots import read_chain
    from runtime.test_u09 import (CONFIG, LegalReplay, SOURCE_TEXT, OBLIGATION,
        packet as legal_packet, proposal, descriptor as legal_descriptor,
        set_descriptor as set_legal_descriptor, freeze)

    oj=next(s['route'] for s in CONFIG['sources'] if s['id']=='OJ')
    class TwoVersions(LegalReplay):
        oj_reads=0
        def read(self,source):
            super().read(source)
            if source.id=='OJ':super().read(source)
        def handler(self,request):
            response=super().handler(request)
            if str(request.url)==oj:
                self.oj_reads+=1
                if self.oj_reads==2:
                    return httpx.Response(200,headers=response.headers,content=response.content.replace(
                        SOURCE_TEXT['OJ'][1].encode(),b'OJ-v2 2026-09-01'))
            return response

    providers=Providers();root=tmp_path/providers.run_id();root.mkdir()
    store=EvidenceStore(root,root.name,providers)
    config=deepcopy(CONFIG);config['output_root']='out';raw=json_bytes(config)
    _write(root,'analysis/config.json',raw)
    reader=TwoVersions(store)
    try:
        run_stages(store,config,manifest(config),reader,config_bytes=raw,providers=providers,
            linked_reports=True,legal_extracts=True)
    finally:reader.close()
    request=legal_packet(root)
    newer=next(e for e in request['extracts'] if 'OJ-v2 2026-09-01' in e['text'])
    # The retained real packet contains BOTH captures. Source assessments cite
    # the historical one, while this component borrows the newer unassessed one.
    value=proposal({**request,'extracts':[e for e in request['extracts'] if e!=newer]})
    d=legal_descriptor(value);d['support'][0]['evidence_id']=newer['evidence_id']
    value['candidates'][0]['citations'].append(dict(evidence_id=newer['evidence_id'],quote=OBLIGATION))
    set_legal_descriptor(value,d)
    result,third=freeze(root,value)
    assert result['disposition']=='unresolved' and 'assessed source capture' in result['reason']
    assert third['interpretation_bindings']  # Frozen envelope/quote checks passed.
    assert not third['state']['binding_rules'] and third['status']=='blocked'
    second=read_chain(root,count=3)[1]
    assert len([a for a in second['state']['attempts'] if a['source_id']=='OJ'])==2
