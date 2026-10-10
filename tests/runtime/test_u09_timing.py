"""U09 temporal acceptance on separately captured SYNTHETIC source variants."""
from copy import deepcopy

import httpx
import pytest

from rci.authority import submit_authority, freeze_authority, validate_authority
from rci.contracts import json_bytes, parse_json
from rci.evidence import EvidenceStore, _write
from rci.runner import run_stages
from rci.runtime import Providers
from rci.source_manifest import manifest
from rci.snapshots import read_chain
from runtime.test_u09 import (CONFIG, LegalReplay, TIMING, SOURCE_TEXT, packet, proposal,
    descriptor, set_descriptor)


def captured_variant(tmp_path, replacements):
    class Variant(LegalReplay):
        def handler(self,request):
            response=super().handler(request)
            raw=response.content
            for old,new in replacements.items():raw=raw.replace(old.encode(),new.encode())
            return httpx.Response(response.status_code,content=raw,headers=response.headers)
    providers=Providers();root=tmp_path/providers.run_id();root.mkdir()
    store=EvidenceStore(root,root.name,providers)
    config=deepcopy(CONFIG);config['output_root']='out';raw=json_bytes(config)
    _write(root,'analysis/config.json',raw)
    reader=Variant(store)
    try:
        run_stages(store,config,manifest(config),reader,config_bytes=raw,providers=providers,
            linked_reports=True,legal_extracts=True)
    finally:reader.close()
    request=packet(root)
    has_oj=any('body of OJ;' in e['locator']['value'] for e in request['extracts'])
    value=proposal(request) if has_oj else dict(disposition='unsupported',
        diagnostic='No readable requested OJ authority; login content is not legislation',candidates=[])
    if not has_oj:
        return root,store,value
    for citation in value['candidates'][0]['citations']:
        citation['quote']=replacements.get(citation['quote'],citation['quote'])
    return root,store,value


def test_newer_future_amendment_excluded_without_retrieval_date_override(tmp_path):
    version='AMEND-v2 2026-09-01'
    relationship='Amends regulation 2024/1689 from 2027-01-01.'
    replacements={SOURCE_TEXT['AMEND'][1]:version,SOURCE_TEXT['AMEND'][2]:relationship}
    root,store,value=captured_variant(tmp_path,replacements)
    d=descriptor(value);source=next(s for s in d['sources'] if s['source_id']=='AMEND')
    source.update(version='AMEND-v2',version_quote=version,publication_date='2026-09-01',
        relationship='future',relationship_quote=relationship,effective_from='2027-01-01')
    set_descriptor(value,d)
    result=submit_authority(root,json_bytes(value));third=freeze_authority(store)
    assert result['disposition']=='proposed',result
    assert third['state']['binding_rules'][0]['effective_from']=='2026-08-02'
    assert third['state']['binding_rules'][0]['source_publication_date']=='2026-07-01'
    assert source['publication_date']>'2026-08-26'
    assert not third['state']['authority_blockers']
    validate_authority(store)


@pytest.mark.parametrize('start,end,expected',[('2026-08-26','2027-01-01','proposed'),
    ('2026-08-27','2027-01-01','unresolved'),('2026-08-02','2026-08-26','unresolved')])
def test_date_boundary_inclusive_start_exclusive_end(tmp_path,start,end,expected):
    new=f'Synthetic rule applies from {start} until {end} exclusively.'
    root,store,value=captured_variant(tmp_path,{TIMING:new})
    d=descriptor(value);d['timing'].update(basis=new,effective_from=start,effective_until=end)
    entry=next(s for s in d['support'] if s['component']=='timing');entry.update(value=new,quote=new)
    set_descriptor(value,d)
    result=submit_authority(root,json_bytes(value));third=freeze_authority(store)
    assert result['disposition']==expected,result
    assert bool(third['state']['authority_blockers'])==(expected=='unresolved')


def test_newer_guidance_remains_context_and_cannot_change_binding_timing(tmp_path):
    version='FAQ-v2 2026-09-01'
    root,store,value=captured_variant(tmp_path,{SOURCE_TEXT['FAQ'][1]:version})
    d=descriptor(value);source=next(s for s in d['sources'] if s['source_id']=='FAQ')
    source.update(version='FAQ-v2',version_quote=version,publication_date='2026-09-01')
    set_descriptor(value,d)
    value['candidates'].append(dict(summary='Explanatory context only',basis_type='guidance',
        citations=[dict(evidence_id=source['evidence_id'],quote='Explanatory context only')],
        conditions=[],role='unknown',timing_candidates=[],exception_candidates=[],uncertainty=None,system_ids=['AI-001']))
    assert submit_authority(root,json_bytes(value))['disposition']=='proposed'
    third=freeze_authority(store)
    assert len(third['state']['guidance_context'])==1
    assert third['state']['timing_rules'][0]['effective_from']=='2026-08-02'
    assert not third['state']['authority_blockers']


@pytest.mark.parametrize('failure',['unrelated','login'])
def test_wrong_act_and_login_response_retained_but_never_formal_authority(tmp_path,failure):
    replacements={'Regulation 2024/1689':'Sign in' if failure=='login' else 'Agricultural Regulation 9999/1',
        '2024/1689':'9999/1'}
    root,store,value=captured_variant(tmp_path,replacements)
    result=submit_authority(root,json_bytes(value));third=freeze_authority(store)
    assert result['disposition']=='unresolved'
    assert third['status']=='blocked' and not third['state']['binding_rules']
    attempts=store.inventory()
    oj=[e for e in attempts if e['attempt']['source_id']=='OJ']
    assert oj and all(e['capture'] is not None for e in oj)
    assert all((root/e['capture']['local_reference']).is_file() for e in oj)
    if failure=='login':
        assert all(e['attempt']['identity_check']=='mismatch' for e in oj)
        assert not any(e['assertion']=='Captured legal/context page body for OJ'
            for e in read_chain(root,count=2)[1]['state']['evidence'])
