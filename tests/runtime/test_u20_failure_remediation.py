"""E05: real public launcher diagnostics across setup/storage boundaries."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from rci import pipeline
from rci.contracts import json_bytes
from runtime.test_u07 import CONFIG, DECLARED


def invoke(tmp_path, monkeypatch, capsys, *, scope=False):
    config=deepcopy(CONFIG);config['output_root']='out'
    config_path=tmp_path/'config.json';config_path.write_bytes(json_bytes(config))
    script=Path(__file__).resolve().parents[2]/'regulatory-change-impact-brief/scripts/run.py'
    spec=importlib.util.spec_from_file_location('remediation_launcher',script)
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    argv=['run.py','--config',str(config_path)]
    if scope:
        path=tmp_path/'scope.json';path.write_bytes(json_bytes(DECLARED))
        argv += ['--scope',str(path)]
    monkeypatch.setattr('rci.runtime.REPO',tmp_path)
    monkeypatch.setattr('rci.runtime.preflight',lambda config:None)
    monkeypatch.setattr(sys,'argv',argv)
    assert launcher.main()==1
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize('relative',[
    'analysis/config.json','analysis/scope-input.json',
    'analysis/run-context.json','analysis/prior-inspection.json',
])
def test_initial_write_failure_retains_accurate_context(tmp_path,monkeypatch,capsys,relative):
    original=pipeline._write
    def fail(root,path,raw):
        if path==relative:raise OSError('controlled initial write failure')
        return original(root,path,raw)
    monkeypatch.setattr(pipeline,'_write',fail)
    result=invoke(tmp_path,monkeypatch,capsys,scope=True)
    assert result['affected_stage']=='candidate-initialization'
    assert result['affected_outputs']==[relative]
    assert result['run_id'] and result['candidate_created']
    candidate=tmp_path/result['candidate']
    assert candidate.name==result['run_id']
    assert result['diagnostic_persistence']=='retained'
    assert json.loads((candidate/result['diagnostic_record']).read_text())==result
    assert result['next_owner']=='Operator' and 'fresh source attempts' in result['recovery_action']
    assert not (tmp_path/'out/.completion.json').exists()


def test_unwritable_storage_reports_context_without_claiming_retention(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(pipeline,'_write',lambda *a:(_ for _ in ()).throw(OSError('controlled storage unavailable')))
    result=invoke(tmp_path,monkeypatch,capsys)
    assert result['affected_stage']=='candidate-initialization'
    assert result['run_id'] and result['candidate_created']
    assert result['diagnostic_persistence']=='unavailable' and result['diagnostic_record'] is None
    candidate=tmp_path/result['candidate']
    assert candidate.is_dir() and not (candidate/'analysis/outcome.json').exists()
    assert 'controlled storage unavailable' in result['diagnostic_error']


def test_candidate_directory_failure_does_not_create_a_fake_outcome(tmp_path,monkeypatch,capsys):
    original=Path.mkdir
    def mkdir(path,*args,**kwargs):
        if path.parent.name=='.staging':raise OSError('controlled candidate mkdir failure')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'mkdir',mkdir)
    result=invoke(tmp_path,monkeypatch,capsys)
    assert result['affected_stage']=='candidate-initialization'
    assert result['run_id'] and not result['candidate_created']
    assert result['diagnostic_persistence']=='unavailable' and result['diagnostic_record'] is None
    assert not (tmp_path/result['candidate']).exists()


@pytest.mark.parametrize('operation,stage',[
    ('inspect','current-package-inspection'),('feedback','feedback-retention'),
    ('archive','feedback-archive'),
])
def test_setup_boundaries_are_not_misclassified_as_capture(tmp_path,monkeypatch,capsys,operation,stage):
    def fail(*args,**kwargs):raise OSError('controlled '+operation+' failure')
    if operation=='inspect':monkeypatch.setattr('rci.history.inspect_current',fail)
    elif operation=='feedback':monkeypatch.setattr(pipeline,'_retain_feedback',fail)
    else:
        # A prior occurrence and supplied feedback trigger its preservation before intake.
        root=tmp_path/'out';(root/'snapshots').mkdir(parents=True)
        (root/'snapshots/01-scope.json').write_text('prior bytes must survive')
        monkeypatch.setattr('rci.history.inspect_current',lambda *a,**kw:dict(run_id='run-prior',accepted=False))
        monkeypatch.setattr('rci.history.archive_current',fail)
        original=pipeline.run
        def with_feedback(*args,**kwargs):
            kwargs['feedback_path']=tmp_path/'feedback.json'
            return original(*args,**kwargs)
        monkeypatch.setattr(pipeline,'run',with_feedback)
    result=invoke(tmp_path,monkeypatch,capsys)
    assert result['affected_stage']==stage
    assert result['run_id'] and result['next_owner']=='Operator'
    if operation=='inspect':
        assert not result['candidate_created'] and result['diagnostic_persistence']=='unavailable'
    else:
        assert result['candidate_created'] and result['diagnostic_persistence']=='retained'
        assert (tmp_path/result['candidate']/result['diagnostic_record']).is_file()
    if operation=='archive':assert (tmp_path/'out/snapshots/01-scope.json').read_text()=='prior bytes must survive'


def test_second_writer_failure_has_context_without_writing_candidate(tmp_path,monkeypatch,capsys):
    from rci.runtime import writer_lock
    with writer_lock(tmp_path/'out'):
        result=invoke(tmp_path,monkeypatch,capsys)
    assert result['affected_stage']=='output-lock'
    assert not result['candidate_created'] and result['diagnostic_persistence']=='unavailable'
    assert result['run_id'] and not (tmp_path/result['candidate']).exists()
