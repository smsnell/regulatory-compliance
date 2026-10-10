"""Optimization regressions: exact bytes invalidate, errors never become successes."""
from types import SimpleNamespace
import pytest
from rci.contracts import ContractError, validate_schema
from rci.validation_cache import disk_verified
from rci.normalize import _checked_validator


def test_disk_memo_rereads_and_copies(tmp_path):
    calls=[];store=SimpleNamespace(root=tmp_path,run_id='run-cache')
    file=tmp_path/'source';file.write_bytes(b'valid')
    @disk_verified
    def check(store):
        calls.append(1)
        if file.read_bytes()!=b'valid':raise ValueError('corrupt')
        return {'state':['supported']}
    assert check(store)=={'state':['supported']}
    check(store)['state'].append('forged')
    assert check(store)=={'state':['supported']} and len(calls)==1
    file.write_bytes(b'wrong')
    for _ in range(2):
        with pytest.raises(ValueError):check(store)
    assert len(calls)==3
    file.write_bytes(b'valid');(tmp_path/'added').write_bytes(b'new')
    check(store);assert len(calls)==4
    file.unlink()
    with pytest.raises(OSError):check(store)


def test_schema_cached_value_mutation_and_changed_schema(tmp_path):
    good={'version':'rci-business-key/1','system_id':'A','rule_basis':'B','kind':'C','distinguishing_scope':'D'}
    validate_schema(good,'business-key');validate_schema(good,'business-key')
    good['system_id']=''
    with pytest.raises(ContractError):validate_schema(good,'business-key')
    first=_checked_validator(b'{"type":"string"}')
    second=_checked_validator(b'{"type":"integer"}')
    assert first.is_valid('value') and not second.is_valid('value')


def test_link_never_read_or_cached(tmp_path,monkeypatch):
    from pathlib import Path
    root=tmp_path/'package';root.mkdir()
    outside=tmp_path/'outside';outside.write_bytes(b'private')
    (root/'link').symlink_to(outside)
    calls=[]
    monkeypatch.setattr(Path,'read_bytes',lambda self: (_ for _ in ()).throw(AssertionError('cache followed link')))
    @disk_verified
    def check(store):
        calls.append(1)
        return 'validator handles unsafe path'
    store=SimpleNamespace(root=root,run_id='run-cache')
    assert check(store)==check(store)
    assert len(calls)==2
