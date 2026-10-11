"""U20: actionable diagnostics for failures before a later snapshot exists."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json
from rci.pipeline import run
from runtime.test_u07 import CONFIG


@pytest.mark.parametrize('failure,stage,outputs', [
    ('capture','scope-and-source-capture',list(SNAPSHOT_PATHS[:2])),
    ('authority','authority-and-timing',[SNAPSHOT_PATHS[2]]),
])
def test_failed_supervisor_records_stage_outputs_recovery_and_owner(tmp_path,failure,stage,outputs):
    config=deepcopy(CONFIG);config['output_root']='out'
    path=tmp_path/'config.json';path.write_bytes(json_bytes(config))

    class Reader:
        def __init__(self,store): self.store=store
        def close(self): pass

    with patch('rci.runtime.REPO',tmp_path),patch('rci.runtime.preflight'), \
         patch('rci.runner.run_stages',side_effect=ContractError('synthetic capture failure') if failure=='capture' else None,
               return_value=(None,'partial')), \
         patch('rci.authority.interpret_authority',side_effect=ContractError('synthetic host interruption')):
        result=run(path,reader_factory=Reader)
    assert result['status']=='failed' and not result['production_package'] and not result['package_acceptance']
    assert result['affected_stage']==stage and result['affected_outputs']==outputs
    assert result['next_owner']=='Operator'
    assert 'fresh source attempts' in result['recovery_action'] and 'Preserve' in result['recovery_action']
    candidate=tmp_path/result['candidate']
    assert parse_json((candidate/'analysis/outcome.json').read_bytes())==result
    assert (candidate/('history/'+result['run_id'])/'analysis/outcome.json').read_bytes()==(candidate/'analysis/outcome.json').read_bytes()
    assert not (tmp_path/'out/.completion.json').exists()


def test_launcher_preflight_failure_reports_recovery_without_touching_outputs(tmp_path,monkeypatch,capsys):
    path=tmp_path/'bad-config.json';path.write_text('{}')
    script=Path(__file__).resolve().parents[2]/'regulatory-change-impact-brief/scripts/run.py'
    spec=importlib.util.spec_from_file_location('u20_launcher',script)
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    monkeypatch.setattr(sys,'argv',['run.py','--config',str(path)])
    assert launcher.main()==1
    result=json.loads(capsys.readouterr().out)
    assert result['affected_stage']=='launcher-preflight' and result['affected_outputs']==[]
    assert result['next_owner']=='Operator' and result['recovery_action']
    assert not result['production_package'] and list(tmp_path.iterdir())==[path]
