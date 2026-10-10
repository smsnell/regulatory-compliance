"""Unexpected top-level Stage 03 records must not escape U09 projection checks."""
import pytest
from copy import deepcopy
import httpx

from rci.authority import freeze_authority, submit_authority, validate_authority
from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json
from rci.evidence import EvidenceStore
from rci.ids import new_record_id
from rci.snapshots import read_chain
from runtime.test_u09 import captured, clone, packet, proposal


def test_authorized_mirror_route_does_not_grant_official_binding_authority(tmp_path):
    from runtime.test_u09 import CONFIG, LegalReplay
    from rci.evidence import _write
    from rci.runner import run_stages
    from rci.runtime import Providers
    from rci.source_manifest import manifest
    official=next(s['route'] for s in CONFIG['sources'] if s['id']=='OJ')
    mirror='https://mirror.example.org/regulation'
    class MirrorReplay(LegalReplay):
        def handler(self,request):
            # An identical synthetic title/body hosted at an authorized mirror
            # must not inherit official authority from the declared OJ label.
            if str(request.url)==mirror:
                request=httpx.Request('GET',official)
            return super().handler(request)
    config=deepcopy(CONFIG);config['output_root']='out'
    next(s for s in config['sources'] if s['id']=='OJ')['route']=mirror
    providers=Providers();root=tmp_path/providers.run_id();root.mkdir()
    store=EvidenceStore(root,root.name,providers);raw=json_bytes(config)
    _write(root,'analysis/config.json',raw)
    reader=MirrorReplay(store)
    try:
        run_stages(store,config,manifest(config),reader,config_bytes=raw,providers=providers,
            linked_reports=True,legal_extracts=True)
    finally:reader.close()
    request=packet(root)
    result=submit_authority(root,json_bytes(proposal(request)))
    third=freeze_authority(store)
    assert result['disposition']=='unresolved'
    assert not third['state']['binding_rules'] and third['state']['authority_blockers']


def test_top_level_gap_cannot_be_injected_after_authority_projection(captured,tmp_path):
    root=clone(captured,tmp_path);request=packet(root)
    submit_authority(root,json_bytes(proposal(request)))
    store=EvidenceStore(root,root.name);freeze_authority(store)
    third=parse_json((root/SNAPSHOT_PATHS[2]).read_bytes())
    gap=dict(id=new_record_id(root.name,3,'gap'),record_type='gap',summary='Unrequested authority gap',
        evidence_ids=[],source_basis=['synthetic injection'],reason='Unexpected supplied record',
        owner='Legal',resolution_need='Verify',subject_ids=[],state='unresolved')
    third['unresolved'].append(gap);third['produced_record_ids'].append(gap['id'])
    (root/SNAPSHOT_PATHS[2]).write_bytes(json_bytes(third))
    read_chain(root,count=3)
    with pytest.raises(ContractError,match='Stage 03 differs'):validate_authority(store)
