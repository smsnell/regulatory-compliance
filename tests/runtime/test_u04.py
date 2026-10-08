"""U04 A/S/I/R: synthetic storage faults and frozen G1 integration."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import pytest
from rci.contracts import ContractError, parse_json, validate_schema
from rci.evidence import EvidenceStore, _write
from rci.snapshots import read_chain, write_snapshot
from u03_harness import FakeProviders

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO/'tests/fixtures/u02/package'


def store(tmp_path):
    return EvidenceStore(tmp_path, 'run-u04-synthetic', FakeProviders())


def response(data=b'Synthetic paragraph 1: notice is visible.\n', **updates):
    return dict(data=data, representation_metadata={'permission': 'synthetic full retention'},
                content_type='text/plain; charset=utf-8', retrieval_status='retrieved',
                identity_check='verified', date_suitability='suitable', selected=True,
                selection_reason='Synthetic verified response', outcome='HTTP 200', **updates)


def test_response_matrix_and_independent_hashes(tmp_path):
    s = store(tmp_path)
    cases = json.loads((REPO/'tests/fixtures/u04/responses.json').read_text())['cases']
    for case in cases:
        key = s.start('REPORT', 'https://synthetic.invalid/report', 'synthetic')
        args = response()
        args.update(data=None if case['text'] is None else case['text'].encode(),
                    retrieval_status=case['status'], selected=case['selected'],
                    identity_check='mismatch' if case['name'] == 'login' else 'unverified')
        event = s.finish(key, **args)
        a = event['attempt']
        validate_schema(a, 'attempt')
        if case['text'] is None:
            assert a['content'] is a['content_hash'] is a['local_reference'] is event['capture'] is None
        else:
            raw = (tmp_path/a['local_reference']).read_bytes()
            assert raw == case['text'].encode()
            assert a['content_hash'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
            validate_schema(event['capture'], 'capture')
        assert a['retrieval_status'] == case['status'] and a['selected'] == case['selected']
    assert len(s.inventory()) == len(cases)


def test_start_precedes_dispatch_and_read_failure(tmp_path):
    s = store(tmp_path)
    def read():
        starts = list((tmp_path/'analysis/attempts').glob('*.start.json'))
        assert len(starts) == 1
        assert not list((tmp_path/'analysis/attempts').glob('*.terminal.json'))
        raise ConnectionError('secret must not enter journal')
    with pytest.raises(ConnectionError):
        s.acquire('REPORT', 'https://synthetic.invalid', 'synthetic', read)
    e, = s.inventory()
    assert e['attempt']['content_hash'] is None
    assert e['diagnostic']['stage'] == 'source-capture'
    assert 'secret' not in json.dumps(e)


@pytest.mark.parametrize('exception', [KeyboardInterrupt, SystemExit])
def test_interrupt_read_closes_and_reraises(tmp_path, exception):
    s = store(tmp_path)
    with pytest.raises(exception):
        s.acquire('REPORT', 'synthetic:report', 'synthetic', lambda: (_ for _ in ()).throw(exception()))
    e, = s.inventory()
    assert e['attempt']['outcome'] == exception.__name__
    assert e['capture'] is None


@pytest.mark.parametrize('exception', [OSError, KeyboardInterrupt])
def test_partial_capture_preserved_but_not_claimed(tmp_path, exception):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    def fail(root, path, data):
        if path.startswith('sources/'):
            _write(root, path, data[:3])
            raise exception('synthetic disk failure')
        return _write(root, path, data)
    with patch('rci.evidence._write', side_effect=fail):
        if exception is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt):
                s.finish(key, **response())
        else:
            s.finish(key, **response())
    e, = s.inventory()
    assert e['attempt']['content'] is e['attempt']['local_reference'] is e['capture'] is None
    assert e['attempt']['retrieval_status'] == 'unavailable'
    assert (tmp_path/e['diagnostic']['affected_output']).read_bytes() == b'Syn'
    assert e['diagnostic']['recovery_action'] and e['diagnostic']['next_owner'] is None


def test_terminal_disk_failure_and_hard_stop_reject_freeze(tmp_path):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    with pytest.raises(ContractError, match='incomplete'):
        s.inventory()  # Models an uncatchable process termination after dispatch.
    def fail(root, path, data):
        if '.terminal.' in path:
            raise OSError('terminal disk failure')
        return _write(root, path, data)
    with patch('rci.evidence._write', side_effect=fail), pytest.raises(OSError):
        s.finish(key, **response())
    assert list((tmp_path/'sources').iterdir())
    with pytest.raises(ContractError, match='incomplete'):
        s.inventory()


def test_duplicate_closure_and_no_mutation(tmp_path):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    first = s.finish(key, **response())
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ContractError, match='already closed'):
        s.finish(key, **response(b'changed'))
    assert before == {p: p.read_bytes() for p in before}
    first['attempt']['source_id'] = 'mutated'
    assert s.inventory()[0]['attempt']['source_id'] == 'REPORT'


@pytest.mark.parametrize('path', ['../escape', '/tmp/escape', 'sources/../escape',
                                  'sources//escape', 'sources/./escape', 'sources\\escape'])
def test_unsafe_paths(tmp_path, path):
    with pytest.raises(ContractError):
        _write(tmp_path, path, b'bad')


@pytest.mark.parametrize('directory', ['sources', 'analysis'])
def test_symlink_even_inside_root_rejected(tmp_path, directory):
    (tmp_path/'target').mkdir()
    (tmp_path/directory).symlink_to(tmp_path/'target', target_is_directory=True)
    with pytest.raises(OSError):
        _write(tmp_path, directory+'/file', b'bad')
    assert not (tmp_path/'target/file').exists()


def test_extract_unknown_mime_and_claim_locator(tmp_path):
    s = store(tmp_path)
    raw = b'Synthetic permitted paragraph: visible notice.'
    args = response(raw)
    args.update(representation='extract', content_type=None,
                representation_metadata={'method': 'permitted redaction', 'locator': 'paragraph 2',
                                         'permission': 'synthetic source owner authorization'})
    e = s.acquire('REPORT', 'synthetic:report', 'synthetic', lambda: args)
    a = e['attempt']
    assert a['content_type'] == 'application/octet-stream' and not a['content_type_known']
    assert a['content'] == 'extract'
    assert a['content_hash'] != 'sha256:' + hashlib.sha256(b'original secret\n'+raw).hexdigest()
    evidence = s.claim(e['capture'], locator={'kind':'paragraph', 'value':'2'},
                       assertion='Synthetic visible notice', quoted_support='visible notice')
    validate_schema(evidence, 'evidence')
    assert evidence['capture_id'] == e['capture']['id']
    with pytest.raises(ContractError):
        s.claim({**e['capture'], 'local_reference':'https://synthetic.invalid'},
                locator={'kind':'paragraph','value':'2'}, assertion='claim', quoted_support='notice')


def test_required_metadata_chronology_and_quotes(tmp_path):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    args = response()
    args['representation_metadata'] = None
    with pytest.raises(ContractError): s.finish(key, **args)
    args = response()
    args['retrieved_at'] = '2020-01-01T00:00:00Z'
    with pytest.raises(ContractError): s.finish(key, **args)
    e = s.finish(key, **response())
    with pytest.raises(ContractError, match='quote absent'):
        s.claim(e['capture'], locator={'kind':'paragraph','value':'1'}, assertion='unsupported', quoted_support='invented')
    (tmp_path/e['capture']['local_reference']).write_bytes(b'corrupt')
    with pytest.raises(ContractError, match='hash mismatch'): s.inventory()


def test_invalid_adapter_output_still_closed(tmp_path):
    s = store(tmp_path)
    with pytest.raises(TypeError):
        s.acquire('REPORT', 'synthetic:report', 'synthetic', lambda: {'unknown_field':True})
    e, = s.inventory()
    assert e['diagnostic']['reason'] == 'Adapter output or capture finalization failed'
    assert e['capture'] is None


def test_frozen_stage02_integration(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    prefix = read_chain(tmp_path, count=1)
    snapshot = parse_json((FIXTURE/'snapshots/02-source-capture.json').read_bytes())
    s = EvidenceStore(tmp_path, snapshot['run_id'], FakeProviders())
    # Preserve original discovery fixtures; add a genuinely separate retry/report read.
    args = response()
    args['retrieved_at'] = snapshot['created_at']
    class Clock:
        def now(self): return snapshot['created_at']
    s.providers = Clock()
    e = s.acquire('SYSTEMS', 'synthetic:linked-report', 'synthetic', lambda: args)
    a, c = e['attempt'], e['capture']
    claim = s.claim(c, locator={'kind':'paragraph','value':'1'}, assertion='Synthetic notice', quoted_support='notice is visible')
    snapshot['state']['attempts'].append(a)
    snapshot['state']['captures'].append(c)
    snapshot['state']['evidence'].append(claim)
    snapshot['state']['sources'][0]['attempt_ids'].append(a['id'])
    snapshot['produced_record_ids'].extend([a['id'], c['id'], claim['id']])
    # Remove only the copied Stage 02 target in this disposable test root.
    (tmp_path/'snapshots/02-source-capture.json').unlink()
    write_snapshot(tmp_path, snapshot, upstream=prefix)
    assert read_chain(tmp_path, count=2)[1] == snapshot
    assert s.inventory()[0]['attempt'] == a


def test_retry_and_linked_report_are_distinct_reads(tmp_path):
    s = store(tmp_path)
    events = [s.acquire('REPORT', 'synthetic:report', 'synthetic', lambda: response()) for _ in range(2)]
    events.append(s.acquire('LINKED', 'synthetic:linked', 'synthetic', lambda: response()))
    assert len({e['attempt']['attempt_key'] for e in events}) == 3
    assert len({e['attempt']['id'] for e in events}) == 3
    assert len({e['capture']['local_reference'] for e in events}) == 3
    assert len(s.inventory()) == 3


@pytest.mark.parametrize('args', [
    {'data': None}, {'content_type': ''}, {'content_type': '   '},
    {'retrieval_status': 'complete'}, {'retrieved_at': 'not-a-date'},
    {'representation':'extract'},
])
def test_invalid_response_metadata_rejected(tmp_path, args):
    s = store(tmp_path)
    response_args = response()
    response_args.update(args)
    with pytest.raises(ContractError):
        s.acquire('REPORT', 'synthetic:report', 'synthetic', lambda: response_args)
    e, = s.inventory()
    assert e['attempt']['content'] is None and e['diagnostic']


def test_source_fsync_failure_is_technical_not_content(tmp_path):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    import os
    real_fsync = os.fsync
    def fail(fd):
        # Source file descriptors are regular files opened exclusively here.
        import stat
        if stat.S_ISREG(os.fstat(fd).st_mode) and os.readlink(f'/proc/self/fd/{fd}').endswith('.bin'):
            raise OSError('synthetic durability failure')
        return real_fsync(fd)
    with patch('rci.evidence.os.fsync', side_effect=fail):
        e = s.finish(key, **response())
    assert e['capture'] is None and e['diagnostic']['failure_type'] == 'OSError'
    assert s.inventory()[0]['attempt']['content_hash'] is None


def test_partial_terminal_event_is_rejected_and_preserved(tmp_path):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    path = tmp_path/f'analysis/attempts/{key}.terminal.json'
    path.write_bytes(b'{"schema_version":')
    with pytest.raises(ContractError): s.inventory()
    with pytest.raises(ContractError, match='already closed'): s.finish(key, **response())
    assert path.read_bytes() == b'{"schema_version":'


def test_symlink_file_cannot_be_overwritten_or_claimed(tmp_path):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    (tmp_path/'sources').mkdir()
    (tmp_path/'victim').write_bytes(b'unchanged')
    (tmp_path/f'sources/{key}.bin').symlink_to(tmp_path/'victim')
    e = s.finish(key, **response())
    assert e['capture'] is None
    assert (tmp_path/'victim').read_bytes() == b'unchanged'


def test_changed_terminal_origin_and_cross_run_rejected(tmp_path):
    s = store(tmp_path)
    e = s.acquire('REPORT', 'synthetic:report', 'synthetic', lambda: response())
    path = tmp_path/f"analysis/attempts/{e['attempt']['attempt_key']}.terminal.json"
    original = path.read_bytes()
    modified = json.loads(original)
    modified['attempt']['original_locator'] = 'synthetic:different'
    path.write_text(json.dumps(modified))
    with pytest.raises(ContractError, match='original attempt'): s.inventory()
    path.write_bytes(original)
    with pytest.raises(ContractError, match='wrong journal binding'):
        EvidenceStore(tmp_path, 'run-another', FakeProviders()).inventory()


def test_inspection_fixture_is_independently_verifiable():
    root = REPO/'tests/fixtures/u04/inspection'
    s = EvidenceStore(root, 'run-u04-inspection')
    e, = s.inventory()
    claim = parse_json((root/'analysis/claim.json').read_bytes())
    validate_schema(claim, 'evidence')
    raw = (root/claim['local_reference']).read_bytes()
    assert 'sha256:' + hashlib.sha256(raw).hexdigest() == claim['content_hash']
    assert claim['capture_id'] == e['capture']['id']
    assert claim['quoted_support'].encode() in raw
    assert claim['locator'] == {'kind':'paragraph', 'value':'2'}


def test_diagnostic_missing_recovery_action_rejected(tmp_path):
    s = store(tmp_path)
    key = s.start('REPORT', 'synthetic:report', 'synthetic')
    e = s.finish(key, recoverable_failure='Synthetic failed read')
    path = tmp_path/f'analysis/attempts/{key}.terminal.json'
    del e['diagnostic']['recovery_action']
    path.write_text(json.dumps(e))
    with pytest.raises(ContractError, match='diagnostic fields'): s.inventory()


@pytest.mark.parametrize('failure,exception', [
    ('terminal-file-fsync', OSError),
    ('terminal-directory-fsync', OSError),
    ('after-terminal-write', OSError),
    ('after-terminal-write', KeyboardInterrupt),
    ('after-terminal-write', SystemExit),
])
def test_terminal_failure_stays_incomplete_after_reopen(tmp_path, failure, exception):
    import os
    s = store(tmp_path)
    real_fsync = os.fsync
    def sync(fd):
        path = Path(os.readlink(f'/proc/self/fd/{fd}'))
        terminal_exists = bool(list((tmp_path/'analysis/attempts').glob('*.terminal.json')))
        if (failure == 'terminal-file-fsync' and path.name.endswith('.terminal.json') or
                failure == 'terminal-directory-fsync' and
                path == tmp_path/'analysis/attempts' and terminal_exists):
            raise exception('synthetic terminal persistence failure')
        real_fsync(fd)
    def write(root, path, data):
        _write(root, path, data)
        if failure == 'after-terminal-write' and path.endswith('.terminal.json'):
            raise exception('synthetic terminal persistence failure')
    with patch('rci.evidence.os.fsync', side_effect=sync), \
         patch('rci.evidence._write', side_effect=write), pytest.raises(exception):
        s.acquire('REPORT', 'synthetic:report', 'synthetic', response)
    terminal, = (tmp_path/'analysis/attempts').glob('*.terminal.json')
    event = parse_json(terminal.read_bytes())
    # The original bug required fully parseable bytes, not a truncated JSON file.
    assert event['attempt']['retrieval_status'] == 'retrieved'
    assert (tmp_path/event['capture']['local_reference']).read_bytes() == response()['data']
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    reopened = store(tmp_path)
    with pytest.raises(ContractError, match='incomplete'): reopened.inventory()
    with pytest.raises(ContractError, match='incomplete'):
        reopened.claim(event['capture'], locator={'kind':'paragraph','value':'1'},
                       assertion='Synthetic notice', quoted_support='notice is visible')
    with pytest.raises(ContractError):
        reopened.finish(event['attempt']['attempt_key'], **response())
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind', ['attempt', 'capture'])
@pytest.mark.parametrize('change', ['foreign-run', 'wrong-stage', 'wrong-type', 'malformed-suffix'])
def test_journal_record_ids_revalidated_after_reopen(tmp_path, kind, change):
    s = store(tmp_path)
    event = s.acquire('REPORT', 'synthetic:report', 'synthetic', response)
    parts = event[kind]['id'].split(':')
    if change == 'foreign-run': parts[1] = 'run-foreign'
    if change == 'wrong-stage': parts[2] = '03'
    if change == 'wrong-type': parts[3] = 'evidence'
    if change == 'malformed-suffix': parts[4] = 'not-a-record-uuid'
    event[kind]['id'] = ':'.join(parts)
    key = event['attempt']['attempt_key']
    if kind == 'attempt':
        start_path = tmp_path/f'analysis/attempts/{key}.start.json'
        start = parse_json(start_path.read_bytes())
        start['attempt']['id'] = event['attempt']['id']
        start_path.write_text(json.dumps(start))
        event['capture']['attempt_id'] = event['attempt']['id']
    (tmp_path/f'analysis/attempts/{key}.terminal.json').write_text(json.dumps(event))
    reopened = store(tmp_path)
    with pytest.raises(ValueError): reopened.inventory()
    with pytest.raises(ValueError):
        reopened.claim(event['capture'], locator={'kind':'paragraph','value':'1'},
                       assertion='Synthetic notice', quoted_support='notice is visible')


@pytest.mark.parametrize('kind', ['attempt', 'capture'])
def test_duplicate_journal_record_ids_rejected(tmp_path, kind):
    s = store(tmp_path)
    first = s.acquire('REPORT', 'synthetic:first', 'synthetic', response)
    second = s.acquire('REPORT', 'synthetic:second', 'synthetic', response)
    second[kind]['id'] = first[kind]['id']
    key = second['attempt']['attempt_key']
    if kind == 'attempt':
        start_path = tmp_path/f'analysis/attempts/{key}.start.json'
        start = parse_json(start_path.read_bytes())
        start['attempt']['id'] = second['attempt']['id']
        start_path.write_text(json.dumps(start))
        second['capture']['attempt_id'] = second['attempt']['id']
    (tmp_path/f'analysis/attempts/{key}.terminal.json').write_text(json.dumps(second))
    with pytest.raises(ContractError, match='duplicate'): store(tmp_path).inventory()


@pytest.mark.parametrize('field', ['method', 'locator', 'permission'])
@pytest.mark.parametrize('value', [None, '', '   ', 123])
def test_extract_metadata_revalidated_after_reopen(tmp_path, field, value):
    args = response()
    args.update(representation='extract', representation_metadata={
        'method':'synthetic extraction', 'locator':'paragraph 1', 'permission':'synthetic authorization'})
    event = store(tmp_path).acquire('REPORT', 'synthetic:report', 'synthetic', lambda: args)
    metadata = event['capture']['representation_metadata']
    if value is None:
        del metadata[field]
    else:
        metadata[field] = value
    key = event['attempt']['attempt_key']
    (tmp_path/f'analysis/attempts/{key}.terminal.json').write_text(json.dumps(event))
    reopened = store(tmp_path)
    with pytest.raises(ContractError, match='extract'): reopened.inventory()
    with pytest.raises(ContractError, match='extract'):
        reopened.claim(event['capture'], locator={'kind':'paragraph','value':'1'},
                       assertion='Synthetic notice', quoted_support='notice is visible')


@pytest.mark.parametrize('failure', ['file-fsync', 'directory-fsync'])
def test_incomplete_guard_must_persist_before_content_or_terminal(tmp_path, failure):
    import os
    real_fsync = os.fsync
    def sync(fd):
        path = Path(os.readlink(f'/proc/self/fd/{fd}'))
        marker_exists = bool(list((tmp_path/'analysis/attempts').glob('*.incomplete.json')))
        if (failure == 'file-fsync' and path.name.endswith('.incomplete.json') or
                failure == 'directory-fsync' and
                path == tmp_path/'analysis/attempts' and marker_exists):
            raise OSError('synthetic guard persistence failure')
        real_fsync(fd)
    with patch('rci.evidence.os.fsync', side_effect=sync), pytest.raises(OSError):
        store(tmp_path).acquire('REPORT', 'synthetic:report', 'synthetic', response)
    assert not list(tmp_path.rglob('*.bin'))
    assert not list(tmp_path.rglob('*.terminal.json'))
    with pytest.raises(ContractError, match='incomplete'): store(tmp_path).inventory()


def test_guard_removal_failure_preserves_diagnostic_and_blocks_reopen(tmp_path):
    with patch('rci.evidence.os.unlink', side_effect=OSError('synthetic unlink failure')), \
         pytest.raises(OSError):
        store(tmp_path).acquire('REPORT', 'synthetic:report', 'synthetic', response)
    path, = (tmp_path/'analysis/attempts').glob('*.incomplete.json')
    diagnostic = parse_json(path.read_bytes())
    assert diagnostic['run_id'] == 'run-u04-synthetic'
    assert diagnostic['stage'] == 'source-capture' and diagnostic['source_id'] == 'REPORT'
    assert diagnostic['failure_type'] and diagnostic['reason'] and diagnostic['recovery_action']
    assert diagnostic['next_owner'] is None
    assert (tmp_path/diagnostic['affected_output']).is_file()
    with pytest.raises(ContractError, match='incomplete'): store(tmp_path).inventory()


@pytest.mark.parametrize('marker_kind', ['empty', 'truncated', 'dangling-symlink'])
def test_incomplete_marker_wins_over_valid_terminal(tmp_path, marker_kind):
    event = store(tmp_path).acquire('REPORT', 'synthetic:report', 'synthetic', response)
    marker = tmp_path/f"analysis/attempts/{event['attempt']['attempt_key']}.incomplete.json"
    if marker_kind == 'dangling-symlink':
        marker.symlink_to(tmp_path/'missing-diagnostic')
    else:
        marker.write_bytes(b'' if marker_kind == 'empty' else b'{"schema_version":')
    with pytest.raises(ContractError, match='incomplete'): store(tmp_path).inventory()


def test_hard_exit_after_terminal_write_rejects_reopened_inventory(tmp_path):
    import os
    import subprocess
    import sys
    code = '''
import os, sys
from pathlib import Path
from unittest.mock import patch
from rci.evidence import EvidenceStore, _write
def write(root, path, data):
    _write(root, path, data)
    if path.endswith('.terminal.json'):
        os._exit(23)
with patch('rci.evidence._write', side_effect=write):
    EvidenceStore(Path(sys.argv[1]), 'run-u04-synthetic').acquire(
        'REPORT', 'synthetic:report', 'synthetic', lambda: dict(
            data=b'Synthetic permitted report.', content_type='text/plain',
            representation_metadata={'permission':'synthetic retention'}, retrieval_status='retrieved'))
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)],
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1',
                                 'PYTHONPATH':str(REPO/'regulatory-change-impact-brief/scripts')},
                            capture_output=True, timeout=10)
    assert result.returncode == 23, result.stderr
    terminal, = (tmp_path/'analysis/attempts').glob('*.terminal.json')
    event = parse_json(terminal.read_bytes())
    assert (tmp_path/event['capture']['local_reference']).read_bytes() == b'Synthetic permitted report.'
    with pytest.raises(ContractError, match='incomplete'): store(tmp_path).inventory()
