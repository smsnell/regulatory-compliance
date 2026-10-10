"""U03 A/S/I/R checks. Synthetic inputs and disposable roots only."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator
from rci.contracts import ContractError, json_bytes, parse_json, sha256_bytes
from rci.runtime import (REPO, SKILL, host_command, invoke_host, preflight,
                         production_skeleton as production, validate_config, verify_final, writer_lock)
from u03_harness import FakeProviders, prepare, verify_exchange

CONFIG = parse_json((REPO/'config/review.example.json').read_bytes())


def test_sample_and_imports():
    assert validate_config(CONFIG) == CONFIG
    import httpx, icalendar, rci.contracts, rci.ids, rci.snapshots
    for name in ('runtime-config.schema.json','runtime-proposal.schema.json'):
        Draft202012Validator.check_schema(parse_json((SKILL/'references/schemas'/name).read_bytes()))


@pytest.mark.parametrize('change',[
    {'assigned_review_date':'2026-10-08'}, {'expected_system_count':7},
    {'fixture_mode':True}, {'api_key':'secret'}, {'output_root':'../outside'},
    {'output_root':'/tmp/outside'}, {'recipients':['Legal']},
    {'host':{**CONFIG['host'],'token':'secret'}},
    {'host':{**CONFIG['host'],'effort':'low'}},
    {'sources':CONFIG['sources'][:-1]},
    {'sources':[CONFIG['sources'][0]]*10},
])
def test_config_rejects_invalid_setup(change):
    with pytest.raises(ContractError):
        validate_config({**CONFIG,**change})


@pytest.mark.parametrize('route',['fixture://SYSTEMS','https://user:secret@example.com/',
                                  'https://example.com/?token=secret'])
def test_credentials_and_fixture_routes_rejected(route):
    config=deepcopy(CONFIG);config['sources'][0]['route']=route
    with pytest.raises(ContractError):validate_config(config)


@pytest.mark.parametrize('output_root', [
    'regulatory-change-impact-brief', 'regulatory-change-impact-brief/scripts/output',
    'docs/output', 'references/output', 'tests/fixtures/output', 'config/output',
    'interviews/output', 'skill-alias/output',
])
def test_output_input_overlap_rejected_before_any_writes(tmp_path, output_root):
    repo=tmp_path/'repo';repo.mkdir()
    skill=repo/SKILL.name
    schema=skill/'references/schemas/runtime-config.schema.json'
    schema.parent.mkdir(parents=True)
    schema.write_bytes((SKILL/'references/schemas/runtime-config.schema.json').read_bytes())
    (repo/'skill-alias').symlink_to(skill, target_is_directory=True)
    config_path=repo/'review.json'
    config_path.write_bytes(json_bytes({**CONFIG,'output_root':output_root}))
    before={p.relative_to(repo):p.read_bytes() if p.is_file() else None
            for p in repo.rglob('*')}
    with patch('rci.runtime.REPO',repo),patch('rci.runtime.SKILL',skill), \
         patch('rci.runtime.preflight',return_value=('/host','codex-cli 0.161.0')) as host, \
         patch('rci.runtime.prepare_workspace',side_effect=AssertionError('unsafe copy reached')):
        with pytest.raises(ContractError,match='output'):
            production(config_path)
        host.assert_not_called()
    assert {p.relative_to(repo):p.read_bytes() if p.is_file() else None
            for p in repo.rglob('*')} == before


@pytest.mark.parametrize('route', [
    'https://example.com/?%70assword=synthetic-credential',
    'https://example.com/#access_token=synthetic-credential',
    'https://example.com/?%2570assword=synthetic-credential',
    'https://example.com/?key=synthetic-credential',
    'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL_202601744&%70assword=synthetic-credential',
    'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=synthetic-credential',
    'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL_202601744#synthetic-credential',
])
def test_credential_routes_rejected_before_host_or_writes(tmp_path, route):
    config=deepcopy(CONFIG);config['sources'][0]['route']=route
    config_path=tmp_path/'review.json';config_path.write_bytes(json_bytes(config))
    with patch('rci.runtime.preflight') as host,patch('rci.runtime.writer_lock') as lock:
        with pytest.raises(ContractError) as error:
            production(config_path)
        assert 'synthetic-credential' not in str(error.value)
        host.assert_not_called()
        lock.assert_not_called()


def test_disclosed_uri_queries_and_dedicated_output_remain_supported():
    config=deepcopy(CONFIG)
    config['output_root']='review-output/pilot'
    config['sources'][2]['route']='https://eur-lex.europa.eu/legal-content/EN/TXT/?%75ri=OJ%3AL_202601744'
    assert validate_config(config) == config


def test_config_inside_output_rejected_before_writes(tmp_path):
    output=tmp_path/'review-output';output.mkdir()
    config_path=output/'review.json'
    config_path.write_bytes(json_bytes({**CONFIG,'output_root':'review-output'}))
    before=config_path.read_bytes()
    with patch('rci.runtime.REPO',tmp_path),patch('rci.runtime.preflight') as host:
        with pytest.raises(ContractError,match='output'):
            production(config_path)
        host.assert_not_called()
    assert list(output.iterdir()) == [config_path]
    assert config_path.read_bytes() == before


def test_deterministic_providers_and_isolated_prefix():
    with TemporaryDirectory() as directory:
        a, ai = prepare(Path(directory),FakeProviders())
        # A second deterministic provider starts with the same ID; collision rejects.
        with pytest.raises(FileExistsError):prepare(Path(directory),FakeProviders())
        provider=FakeProviders();provider.run_id()
        b, bi = prepare(Path(directory),provider)
        assert a != b and ai['sources/systems.txt']==bi['sources/systems.txt']
        assert parse_json((a/'analysis/request.json').read_bytes())['created_at']=='2026-10-08T04:00:00Z'
        assert not (a/'.completion.json').exists()


def test_stage_round_trip_independent_verification_and_tamper():
    with TemporaryDirectory() as directory:
        root,immutable=prepare(Path(directory),FakeProviders())
        request=parse_json((root/'analysis/request.json').read_bytes())
        candidate=parse_json((REPO/'tests/fixtures/u02/package/analysis/response.json').read_bytes())['candidates'][0]
        candidate['citations'][0]['evidence_id']=request['extracts'][0]['evidence_id']
        proposal=root/'analysis/agent-proposal.json'
        proposal.write_bytes(json_bytes({'disposition':'proposed','diagnostic':None,'candidates':[candidate]}))
        env={**os.environ,'RCI_CHILD_RUN':root.name,'PYTHONDONTWRITEBYTECODE':'1'}
        helper=root/SKILL.name/'scripts/stage.py'
        done=subprocess.run([sys.executable,str(helper),'submit','--root',str(root),'--proposal',str(proposal)],
                            capture_output=True,env=env)
        assert done.returncode==0,done.stdout
        assert verify_exchange(root,immutable).disposition=='proposed'
        assert (root/'analysis/proposal.json').read_bytes()==proposal.read_bytes()
        again=subprocess.run([sys.executable,str(helper),'submit','--root',str(root),'--proposal',str(proposal)],
                             capture_output=True,env=env)
        assert again.returncode==1  # no overwrite/reuse
        (root/'sources/systems.txt').write_text('changed')
        with pytest.raises(ContractError,match='immutable'):verify_exchange(root,immutable)


def test_recursive_launch_before_host_or_writes():
    with patch.dict(os.environ,{'RCI_CHILD_RUN':'active'}),patch('rci.runtime.subprocess.run') as call:
        with pytest.raises(ContractError,match='recursive'):preflight(CONFIG)
        call.assert_not_called()


def test_host_unavailable_auth_and_version_failures():
    with patch('rci.runtime.shutil.which',return_value=None):
        with pytest.raises(ContractError,match='unavailable'):preflight(CONFIG)
    good=subprocess.CompletedProcess([],0,stdout='codex-cli 0.161.0\n')
    bad=subprocess.CompletedProcess([],1,stdout='')
    with patch('rci.runtime.shutil.which',return_value='/host'),patch('rci.runtime.subprocess.run',side_effect=[good,bad]):
        with pytest.raises(ContractError,match='authentication'):preflight(CONFIG)
    with patch('rci.runtime.shutil.which',return_value='/host'),patch('rci.runtime.subprocess.run',return_value=bad):
        with pytest.raises(ContractError,match='version'):preflight(CONFIG)


def test_host_profile_has_no_inherited_integrations():
    command=host_command('/host',Path('/tmp/work'),'gpt-6.1-sol','medium')
    for value in ('--ignore-user-config','--ignore-rules','--ephemeral','workspace-write',
                  'approval_policy="never"','sandbox_workspace_write.network_access=false'):
        assert value in command
    assert not any('bypass' in arg for arg in command)


def test_writer_exclusion_releases_after_failure():
    with TemporaryDirectory() as directory:
        root=Path(directory)
        with writer_lock(root):
            with pytest.raises(ContractError,match='another writer'):
                with writer_lock(root):pass
        with writer_lock(root):pass


def test_host_exit_zero_cannot_supply_missing_or_old_package():
    with TemporaryDirectory() as directory:
        root=Path(directory);(root/'analysis').mkdir()
        invoke_host([sys.executable,'-c','print("complete")'],'',root,5)
        with pytest.raises(OSError):verify_final(root,'new-run','2026-10-08T00:00:00Z')
    with pytest.raises(ContractError,match='foreign'):
        verify_final(REPO/'tests/fixtures/u02/package','new-run','2026-10-08T00:00:00Z')


def test_host_timeout_nonzero_and_interruption_retain_diagnostics():
    with TemporaryDirectory() as directory:
        root=Path(directory);(root/'analysis').mkdir()
        with pytest.raises(ContractError,match='timed out'):
            invoke_host([sys.executable,'-c','import time; time.sleep(10)'],'',root,0.1)
        assert (root/'analysis/host-events.jsonl').exists()
        with pytest.raises(ContractError,match='host failed'):
            invoke_host([sys.executable,'-c','raise SystemExit(1)'],'',root,5)
        process=__import__('unittest.mock',fromlist=['MagicMock']).MagicMock()
        process.communicate.side_effect=KeyboardInterrupt
        process.pid=123
        with patch('rci.runtime.subprocess.Popen',return_value=process),patch('rci.runtime.os.killpg') as kill:
            with pytest.raises(ContractError,match='interrupted'):
                invoke_host(['/host'],'',root,5)
            kill.assert_called_once()
            process.wait.assert_called_once()


def test_invalid_setup_does_not_touch_current_output():
    with TemporaryDirectory() as directory:
        config=Path(directory)/'bad.json';config.write_text('{"token":"secret"}')
        with patch('rci.runtime.writer_lock') as lock:
            with pytest.raises(ContractError):production(config)
            lock.assert_not_called()
    command=[sys.executable,str(SKILL/'scripts/run.py'),'--config',str(REPO/'config/review.example.json'),'--fixture']
    result=subprocess.run(command,capture_output=True)
    assert result.returncode==2


@pytest.mark.parametrize('host_result',['blocked','false-success','interrupted'])
@pytest.mark.parametrize('output_root',['deliverables','review-output/pilot'])
def test_production_supervisor_checks_actual_outcome_and_preserves_current(host_result, output_root):
    import shutil
    with TemporaryDirectory() as directory:
        repo=Path(directory)
        shutil.copyfile(REPO/'snapshot.schema.json',repo/'snapshot.schema.json')
        config_path=repo/'config.json';config_path.write_bytes(json_bytes({**CONFIG,'output_root':output_root}))
        output=repo/output_root;output.mkdir(parents=True)
        current=output/'compliance-brief.md';current.write_bytes(b'previous current package')
        def host(command,prompt,candidate,timeout):
            if host_result=='interrupted':raise ContractError('host interrupted')
            if host_result=='blocked':
                (candidate/'analysis/stage-outcome.json').write_bytes(json_bytes({
                    'run_id':candidate.name,'status':'blocked',
                    'reason':'U03 skeleton: live stage engines are not implemented'}))
        with patch('rci.runtime.REPO',repo),patch('rci.runtime.preflight',return_value=('/host','codex-cli 0.161.0')), \
             patch('rci.runtime.invoke_host',side_effect=host):
            outcome=production(config_path)
        assert outcome['status']==('blocked' if host_result=='blocked' else 'failed')
        assert current.read_bytes()==b'previous current package'
        assert not (output/'.completion.json').exists()
        assert len(list((output/'.staging').iterdir()))==1


def test_missing_final_artifact_and_packet_response_rejected():
    import shutil
    with TemporaryDirectory() as directory:
        package=Path(directory)/'package'
        shutil.copytree(REPO/'tests/fixtures/u02/package',package)
        (package/'action-calendar.ics').unlink()
        with pytest.raises((ContractError,OSError)):
            verify_final(package,'run-u02-synthetic','2026-10-07T00:00:00Z')
    with TemporaryDirectory() as directory:
        root,immutable=prepare(Path(directory),FakeProviders())
        with pytest.raises(OSError):verify_exchange(root,immutable)


def test_missing_dependency_and_unsupported_python_stop_preflight():
    with patch('rci.runtime.sys.version_info',(3,11)):
        with pytest.raises(ContractError,match='Python 3.12'):preflight(CONFIG)
    with patch('rci.runtime.importlib.metadata.version',side_effect=__import__('importlib.metadata',fromlist=['PackageNotFoundError']).PackageNotFoundError('httpx')):
        with pytest.raises(__import__('importlib.metadata',fromlist=['PackageNotFoundError']).PackageNotFoundError):preflight(CONFIG)


def test_recorded_actual_host_exchange_and_metadata():
    from rci.contracts import validate_interpretation
    from rci.snapshots import read_chain
    root=REPO/'tests/fixtures/u03/host-exchange'
    request=parse_json((root/'analysis/request.json').read_bytes())
    result=validate_interpretation((root/'analysis/request.json').read_bytes(),
                                  (root/'analysis/response.json').read_bytes(),root=root,
                                  run_id=request['run_id'],stage=request['stage'],upstream=read_chain(root,count=2))
    assert result.disposition=='proposed'
    assert request['metadata']['host_version']=='codex-cli 0.161.0'
    assert request['metadata']['requested_model']=='gpt-6.1-sol'
    assert request['metadata']['requested_effort']=='high'
    outcome=parse_json((root/'analysis/outcome.json').read_bytes())
    assert outcome['status']=='complete' and outcome['production_package'] is False
    assert outcome['visible_usage'][0]['input_tokens']>0


def test_host_preflight_timeout_is_explicit_failure():
    with patch('rci.runtime.shutil.which',return_value='/host'),patch('rci.runtime.subprocess.run',side_effect=subprocess.TimeoutExpired(['/host'],15)):
        with pytest.raises(ContractError,match='preflight timed out'):preflight(CONFIG)
