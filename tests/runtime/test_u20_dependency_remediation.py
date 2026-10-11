"""E06 real producer fingerprint wiring, paired with G5's public fresh reruns.

Each mutation is isolated on copied inputs/code. No source hashes are invented,
and no retained audit package is edited. The supervisor always recomputes all
seven stages; unchanged fingerprints describe inputs, not reused outputs.
"""
from copy import deepcopy
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from rci import pipeline
from rci.contracts import STAGES, json_bytes, parse_json, sha256_bytes
from rci.recovery import classify_change
from rci.evidence import EvidenceStore
from rci.runner import capture_slice, validate_slice
from runtime.test_u07 import CONFIG, DECLARED, Replay


@pytest.fixture(scope='module')
def captured(tmp_path_factory):
    root=tmp_path_factory.mktemp('dependency-capture')
    config=deepcopy(CONFIG);config['output_root']='out'
    (root/'config.json').write_bytes(json_bytes(config))
    (root/'scope.json').write_bytes(json_bytes(DECLARED))
    with patch('rci.runtime.REPO',root):
        result=capture_slice(root/'config.json',scope_path=root/'scope.json',reader_factory=Replay)
    candidate=root/result['candidate']
    chain=validate_slice(EvidenceStore(candidate,result['run_id']))
    return chain


@pytest.fixture
def inputs(tmp_path, monkeypatch, captured):
    skill=tmp_path/'skill'
    shutil.copytree(pipeline.SKILL,skill)
    monkeypatch.setattr(pipeline,'SKILL',skill)
    root=tmp_path/'package';(root/'analysis').mkdir(parents=True)
    (root/'analysis/scope-input.json').write_bytes(json_bytes(DECLARED))
    chain=deepcopy(captured)
    return SimpleNamespace(root=root),deepcopy(CONFIG),chain,skill


@pytest.mark.parametrize('relative,sequence',[
    ('scripts/rci/decisions.py',1),('scripts/rci/snapshots.py',1),
    ('scripts/rci/pipeline.py',1),('scripts/rci/runner.py',1),
    ('scripts/rci/adapters/anonymous_sheets.py',2),
    ('references/field-dictionary.json',2),
    ('scripts/rci/authority_representations.py',3),
    ('references/authority-policy.md',3),
    ('references/schemas/authority-basis.schema.json',3),
    ('scripts/rci/reconcile.py',4),('references/reconciliation.md',4),
    ('scripts/rci/impacts.py',5),('references/impacts.md',5),
    ('scripts/rci/actions.py',6),('scripts/rci/reviews.py',6),
    ('scripts/rci/renderers/brief.py',7),('scripts/rci/validate.py',7),
])
def test_actual_dependency_bytes_classify_earliest_stage(inputs,relative,sequence):
    store,config,chain,skill=inputs
    before=pipeline._fingerprints(store,config,chain)
    path=skill/relative
    path.write_bytes(path.read_bytes()+b'\n')
    after=pipeline._fingerprints(store,config,chain)
    assert_classification(before,after,sequence)


def assert_classification(before,after,sequence):
    result=classify_change(before,after)
    assert result['earliest_changed_sequence']==sequence
    assert result['earliest_changed_stage']==STAGES[sequence-1]
    assert result['recompute_sequences']==list(range(1,8))
    assert result['fresh_source_attempts_required'] and result['current_file_inspection_required']
    for stage in STAGES[:sequence-1]:
        assert before['fingerprints'][stage]==after['fingerprints'][stage]
    assert before['fingerprints'][STAGES[sequence-1]]!=after['fingerprints'][STAGES[sequence-1]]


@pytest.mark.parametrize('change,sequence',[
    ('scope',1),('config',1),('scope-basis',1),('capture',2),
    ('feedback-input.json',6),('reviewer-policy.json',6),('authentication-context.json',6),
])
def test_actual_input_values_and_files_classify_earliest_stage(inputs,change,sequence):
    store,config,chain,skill=inputs
    before=pipeline._fingerprints(store,config,chain)
    if change=='scope':
        chain[0]['state']['systems_in_scope'][-1]='AI-SYNTHETIC-REPLACEMENT'
        declaration=deepcopy(DECLARED)
        declaration['system_ids']=chain[0]['state']['systems_in_scope']
        from rci.runner import declared_scope
        declared_scope(json_bytes(declaration))  # Still an admissible eight-ID request.
        (store.root/'analysis/scope-input.json').write_bytes(json_bytes(declaration))
    elif change=='config':config['host']['owner']='Changed authorized operator'
    elif change=='scope-basis':
        path=store.root/'analysis/scope-input.json'
        value=parse_json(path.read_bytes());value['basis_version']='changed-synthetic-version'
        path.write_bytes(json_bytes(value))
    elif change=='capture':chain[1]['state']['attempts'][0]['content_hash']=sha256_bytes(b'changed synthetic source content')
    else:(store.root/'analysis'/change).write_bytes(json_bytes({'synthetic_changed_input':True}))
    after=pipeline._fingerprints(store,config,chain)
    assert_classification(before,after,sequence)


def test_occurrence_and_output_location_do_not_invent_a_dependency_change(inputs):
    store,config,chain,skill=inputs
    before=pipeline._fingerprints(store,config,chain)
    config['output_root']='different-owned-output'
    chain[0]['run_id']='run-new';chain[0]['snapshot_id']='snapshot-new'
    chain[1]['state']['attempts'][0].update(attempt_key='attempt-new',retrieved_at='2026-10-10T00:00:00Z')
    after=pipeline._fingerprints(store,config,chain)
    assert before==after
    result=classify_change(before,after)
    assert result['earliest_changed_sequence'] is None
    assert result['recompute_sequences']==list(range(1,8))
