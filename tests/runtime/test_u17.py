"""Seven-stage integration and independent corruption rejection for G4."""
from copy import deepcopy
from pathlib import Path
import shutil
import pytest

from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes
from rci.snapshots import accept_package, read_chain
from rci.validate import validate_package
from integration.pipeline_harness import execute


@pytest.fixture(scope='module')
def package(tmp_path_factory):
    parent=tmp_path_factory.mktemp('g4-complete-pipeline')
    outcome,root=execute(parent,launcher=True)
    assert outcome['status']=='partial',outcome
    assert outcome['launcher_exit_code']==2 and outcome['package_acceptance'],outcome
    return root


def test_representative_then_all_eight_scope(package):
    chain=validate_package(package)
    model=chain[5]['state']['export_model']
    representative=[i for i in model['impacts'] if i['system_id']=='AI-007']
    assert representative and all(i['evidence_ids'] and i['reason'] for i in representative)
    assert len(chain)==7 and len(chain[0]['state']['systems_in_scope'])==8
    assert {c['system_id'] for c in model['coverage']}==set(chain[0]['state']['systems_in_scope'])
    assert any(a['proposed_due_date'] is None for a in model['actions'])
    assert all(r['delivery_status']=='not-sent' for r in model['review_requests'])
    assert len(chain[-1]['state']['artifacts'])==3 and chain[-1]['state']['publication_status']=='validated'
    assert accept_package(package)==chain


@pytest.mark.parametrize('mutation',['csv','brief','calendar','source','predecessor','final-hash'])
def test_independent_package_corruption(package,tmp_path,mutation):
    root=tmp_path/'draft';shutil.copytree(package,root,ignore=shutil.ignore_patterns('.staging','history','.writer.lock'))
    final=parse_json((root/SNAPSHOT_PATHS[6]).read_bytes())
    if mutation=='source':
        source=read_chain(root)[1]['state']['captures'][0]['local_reference'];(root/source).unlink()
    elif mutation=='predecessor':
        final['predecessor']['sha256']='sha256:'+'0'*64
    elif mutation=='final-hash':
        marker=parse_json((root/'.completion.json').read_bytes());marker['stage07']['sha256']='sha256:'+'0'*64
        (root/'.completion.json').write_bytes(json_bytes(marker))
    else:
        name={'csv':'impact-register.csv','brief':'compliance-brief.md','calendar':'action-calendar.ics'}[mutation]
        raw=(root/name).read_bytes()
        if mutation=='csv':raw=raw.replace(b'unresolved',b'supported-no-impact',1)
        elif mutation=='brief':raw+=b'\nAll systems are legally approved.\n'
        else:raw=raw.replace(b'VERSION:2.0',b'VERSION:1.0')
        (root/name).write_bytes(raw)
        # Coherently rehash artifact records/bindings to expose semantic validator,
        # rather than merely demonstrating final-byte hashing.
        for a in final['state']['artifacts']:
            if a['path']==name:a['sha256']=sha256_bytes(raw)
        for b in final['state']['review_bindings']:
            for p in b['artifacts']:
                if p['path']==name:p['sha256']=sha256_bytes(raw)
    if mutation!='final-hash':(root/SNAPSHOT_PATHS[6]).write_bytes(json_bytes(final))
    with pytest.raises((ContractError,OSError)):
        accept_package(root) if mutation=='final-hash' else validate_package(root)


@pytest.mark.parametrize('failure',['no-submission','changed-source'])
def test_failed_or_truncated_host_cannot_return_success(tmp_path,failure):
    outcome,root=execute(tmp_path,fail_host=failure,launcher=True)
    assert outcome['status']=='failed' and outcome['launcher_exit_code']==1
    assert not outcome['production_package'] and not outcome['package_acceptance']
    assert not (root/'.completion.json').exists()


@pytest.mark.parametrize('case',['conflict','authority-blocked'])
def test_conflict_and_authority_blocked_outputs(tmp_path,case):
    outcome,root=execute(tmp_path,launcher=True,conflict=case=='conflict',unavailable_authority=case=='authority-blocked')
    chain=validate_package(root)
    model=chain[5]['state']['export_model']
    if case=='authority-blocked':
        assert outcome['status']=='blocked' and outcome['launcher_exit_code']==3,outcome
        assert chain[-1]['state']['publication_status']=='blocked' and not (root/'.completion.json').exists()
        assert chain[2]['state']['authority_blockers']
    else:
        assert outcome['status']=='partial',outcome
        assert any(i['state']=='conflicting' for i in model['impacts'])
    assert model['limitations'] and model['review_requests']
