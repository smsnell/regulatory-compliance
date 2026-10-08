"""U07 scope/bootstrap acceptance; replay transport is test-only."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import httpx
import pytest
from jsonschema import Draft202012Validator

from rci.adapters import ReadAdapters
from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes
from rci.evidence import EvidenceStore
from rci.ids import new_record_id
from rci.runner import capture_slice, declared_scope, discover_scope, validate_slice
from rci.runtime import Providers
from rci.snapshots import accept_package, read_chain, validate_snapshot

ROOT = Path(__file__).resolve().parents[2]
CAPTURES = ROOT / 'docs/verification/u05-anonymous-live'
REPORT = parse_json((CAPTURES / 'analysis/source-access.json').read_bytes())
OLD = EvidenceStore(CAPTURES, REPORT['run_id']).inventory()
RESPONSES = {e['attempt']['effective_locator']:e for e in OLD}
CONFIG = parse_json((ROOT / 'config/review.example.json').read_bytes())
IDS = [f'AI-{i:03d}' for i in range(1,9)]  # Actual observed IDs; replay is not a live read.
DECLARED = dict(schema_version='rci-scope-input/1', system_ids=IDS,
                basis_version='u07-test-request/1', authorized_by='test request owner',
                source_basis=['explicit test request using observed U05 IDs'])


class Replay:
    def __init__(self, store, *, systems_failed=False, interrupted=False):
        self.store = store
        self.calls = []
        self.systems_failed, self.interrupted = systems_failed, interrupted
        self.client = httpx.Client(transport=httpx.MockTransport(self.handler))
        self.reader = ReadAdapters(store, client=self.client, retries=0)

    def handler(self, request):
        url = str(request.url)
        # Every network dispatch already has a durable start, before a terminal.
        starts = list((self.store.root / 'analysis/attempts').glob('*.start.json'))
        terminals = list((self.store.root / 'analysis/attempts').glob('*.terminal.json'))
        assert len(starts) == len(terminals) + 1
        self.calls.append(url)
        systems = next(s['route'] for s in CONFIG['sources'] if s['id'] == 'SYSTEMS')
        if url.startswith(systems):
            if self.interrupted:
                raise KeyboardInterrupt()
            if self.systems_failed:
                raise httpx.ConnectError('test unavailable')
        event = RESPONSES.get(url)
        if event is None:
            return httpx.Response(403, content=b'access unavailable', headers={'Content-Type':'text/plain'})
        a = event['attempt']
        headers = {'Content-Type':a['content_type']}
        status = int(a['outcome'].removeprefix('HTTP '))
        if status in {301,302,303,307,308}:
            headers['Location'] = event['capture']['representation_metadata']['redirect_target']
        return httpx.Response(status, headers=headers, content=(CAPTURES/a['local_reference']).read_bytes())

    def read(self, source):
        return self.reader.read(source)

    def close(self):
        self.client.close()


@pytest.fixture
def execute(tmp_path):
    config = deepcopy(CONFIG)
    config['output_root'] = 'u07-test-output'
    path = tmp_path / 'config.json'
    path.write_bytes(json_bytes(config))
    def run(declaration=None, **kwargs):
        scope = None
        if declaration is not None:
            scope = tmp_path / 'scope.json'
            scope.write_bytes(json_bytes(declaration))
        with patch('rci.runtime.REPO', tmp_path):
            outcome = capture_slice(path, scope_path=scope, **kwargs)
        candidate = tmp_path / outcome['candidate']
        return outcome, candidate
    return run


@pytest.mark.parametrize('declared', [False, True])
def test_both_scope_paths_actual_records_and_exact_import(execute, declared):
    outcome, root = execute(DECLARED if declared else None, reader_factory=Replay)
    assert outcome['capture_slice_complete'], outcome
    assert outcome['status'] == 'blocked' and not outcome['production_package']
    first, second = read_chain(root, count=2)
    assert first['state']['systems_in_scope'] == IDS
    assert first['state']['assigned_review_date'] == '2026-08-26'
    assert first['state']['as_of'] == '2026-08-26T00:00:00Z'
    assert not first['consumed_record_ids'] and first['predecessor'] is None
    assert first['state']['audiences'] == ['Legal','Operations']
    assert second['predecessor']['sha256'] == sha256_bytes((root/SNAPSHOT_PATHS[0]).read_bytes())
    assert outcome['scope_comparison']['result'] == 'matched'
    store = EvidenceStore(root, outcome['run_id'])
    events = store.inventory()
    originals = {e['attempt']['attempt_key']:e['attempt'] for e in events}
    assert len(second['state']['attempts']) == len(events)
    assert {s['source_id'] for s in second['state']['sources']} == {s['id'] for s in CONFIG['sources']}
    assert len(second['state']['normalized_rows']) == 26
    assert len(second['state']['evidence']) == 3
    for attempt in second['state']['attempts']:
        projection = dict(attempt)
        projection.pop('scope_basis_id', None)
        assert projection == originals[attempt['attempt_key']]
    basis, = first['state']['scope_basis']
    assert basis['evidence_ids'] == []
    if declared:
        assert basis['basis_kind'] == 'declared' and basis['attempt_key'] is None
    else:
        assert basis['basis_kind'] == 'discovered'
        imported, = [a for a in second['state']['attempts'] if a['attempt_key'] == basis['attempt_key']]
        assert imported['scope_basis_id'] == basis['id']
        for key in ('retrieved_at','local_reference','content_hash'):
            assert imported[key] == basis[key]
        assert basis['retrieved_at'] <= first['created_at']
    assert outcome['missing_snapshots'] == list(SNAPSHOT_PATHS[2:])
    with pytest.raises((ValueError,OSError)):
        accept_package(root)


def test_declared_scope_survives_failed_live_corroboration(execute):
    outcome, root = execute(DECLARED, reader_factory=lambda s:Replay(s, systems_failed=True))
    first, second = read_chain(root, count=2)
    assert first['state']['systems_in_scope'] == IDS
    assert outcome['scope_comparison']['current_ids'] is None
    assert second['status'] == 'partial'
    assert any('cannot be corroborated' in d['reason'] for d in second['state']['diagnostics'])
    attempts = [a for a in second['state']['attempts'] if a['source_id']=='SYSTEMS']
    assert attempts and all(a['content'] is a['content_hash'] is a['local_reference'] is None for a in attempts)
    assert len(second['state']['sources']) == 10


def test_declared_scope_difference_preserved(execute):
    request = deepcopy(DECLARED)
    request['system_ids'] = IDS[:-1] + ['AUTHORIZED-OTHER-ID']
    outcome, root = execute(request, reader_factory=Replay)
    first, second = read_chain(root,count=2)
    assert first['state']['systems_in_scope'] == request['system_ids']
    assert outcome['scope_comparison']['missing_ids'] == ['AUTHORIZED-OTHER-ID']
    assert outcome['scope_comparison']['additional_ids'] == ['AI-008']
    assert second['status'] == 'partial'
    assert any('differ from frozen' in d['reason'] for d in second['state']['diagnostics'])


@pytest.mark.parametrize('interrupt', [False,True])
def test_failed_discovery_is_incomplete_not_package(execute, interrupt):
    outcome, root = execute(reader_factory=lambda s:Replay(s, systems_failed=not interrupt, interrupted=interrupt))
    assert not outcome['capture_slice_complete'] and not outcome['package_acceptance']
    assert outcome['missing_snapshots'] == list(SNAPSHOT_PATHS)
    assert not (root/'snapshots').exists()
    events = EvidenceStore(root,outcome['run_id']).inventory()
    assert len(events)==1 and events[0]['attempt']['source_id']=='SYSTEMS'
    assert events[0]['attempt']['content'] is None
    assert outcome['status'] == ('failed' if interrupt else 'blocked')
    with pytest.raises((ValueError,OSError)):
        accept_package(root)


@pytest.mark.parametrize('kind', ['seven','nine','duplicate','blank','missing','duplicate-header','malformed'])
def test_discovery_rejects_wrong_count_or_ambiguous_ids(tmp_path, kind):
    from rci.adapters.anonymous_sheets import csv_rows
    tab = next(r for r in REPORT['register_readiness']['registers'] if r['source_id']=='SYSTEMS')['tabs'][0]
    rows = csv_rows((CAPTURES/tab['local_reference']).read_bytes())
    col = rows[0].index('system_id')
    if kind=='seven': rows.pop()
    elif kind=='nine': rows.append([*rows[-1]]); rows[-1][col]='extra-actual-ID'
    elif kind=='duplicate': rows[2][col]=rows[1][col]
    elif kind=='blank': rows[1][col]=''
    elif kind=='missing': rows[0][col]='unknown_id'
    elif kind=='duplicate-header':
        for row in rows: row.append(row[col])
    else: rows[1].pop()
    import csv, io
    stream=io.StringIO(); csv.writer(stream).writerows(rows)
    store=EvidenceStore(tmp_path,'run-u07-identity')
    event=store.acquire('SYSTEMS','test-only','test-only',lambda:dict(data=stream.getvalue().encode(),
        content_type='text/csv',representation_metadata={'method':'test-only'},identity_check='verified',retrieval_status='retrieved'))
    ready={'registers':[{'source_id':'SYSTEMS','ready':True,'tabs':[{**tab,'attempt_id':event['attempt']['id'],
        'local_reference':event['attempt']['local_reference']}]}]}
    with patch('rci.runner.register_readiness',return_value=ready):
        with pytest.raises(ContractError): discover_scope(store)
        if kind in {'seven','nine'}:
            actual,_=discover_scope(store,require_eight=False)
            assert len(actual)==(7 if kind=='seven' else 9)


@pytest.mark.parametrize('change', ['count','duplicate','blank','unauthorized','date','extra'])
def test_declared_input_schema_rejects_bad_scope(change):
    value=deepcopy(DECLARED)
    if change=='count': value['system_ids'].pop()
    elif change=='duplicate': value['system_ids'][1]=value['system_ids'][0]
    elif change=='blank': value['system_ids'][0]=' '
    elif change=='unauthorized': value['authorized_by']=''
    elif change=='date': value['assigned_review_date']='2027-01-01'
    else: value['attempt_key']='fake'
    with pytest.raises(ContractError): declared_scope(json_bytes(value))


def test_retry_fresh_run_and_unchanged_previous_bytes(execute):
    first, old = execute(reader_factory=lambda s:Replay(s,systems_failed=True))
    before={p.relative_to(old).as_posix():p.read_bytes() for p in old.rglob('*') if p.is_file()}
    second, new = execute(reader_factory=Replay, supersedes_run_id=first['run_id'], change_reason='Source access restored')
    assert second['run_id'] != first['run_id'] and second['capture_slice_complete']
    scope=read_chain(new,count=2)[0]
    assert scope['state']['supersedes_run_id']==first['run_id']
    assert scope['state']['change_reason']=='Source access restored'
    assert before=={p.relative_to(old).as_posix():p.read_bytes() for p in old.rglob('*') if p.is_file()}
    assert read_chain(new,count=2)[1]['predecessor']['snapshot_id']==scope['snapshot_id']


def test_interruption_with_unfinished_journal_preserves_start(execute):
    class Unfinished:
        def __init__(self,store): self.store=store
        def read(self,source):
            self.store.start(source.id,source.route,source.adapter)
            raise KeyboardInterrupt()
        def close(self): pass
    outcome,root=execute(reader_factory=Unfinished)
    assert outcome['status']=='failed' and not outcome['capture_slice_complete']
    assert len(list((root/'analysis/attempts').glob('*.start.json')))==1
    assert not list((root/'analysis/attempts').glob('*.terminal.json'))
    assert outcome['missing_snapshots']==list(SNAPSHOT_PATHS)
    with pytest.raises(ContractError,match='incomplete attempt journal'):
        EvidenceStore(root,outcome['run_id']).inventory()


def test_retry_requires_real_retained_occurrence_and_reason(execute):
    with pytest.raises(ContractError): execute(reader_factory=Replay,supersedes_run_id='run-nonexistent',change_reason='retry')
    with pytest.raises(ContractError): execute(reader_factory=Replay,supersedes_run_id='run-nonexistent')


@pytest.mark.parametrize('mutation', ['comparison','path'])
def test_capture_accounting_independently_rejects_changed_basis(execute, mutation):
    outcome,root=execute(reader_factory=Replay)
    second=parse_json((root/SNAPSHOT_PATHS[1]).read_bytes())
    accounting=second['state']['extensions']['u07_capture']['value']
    if mutation=='comparison':
        accounting['scope_comparison']['current_ids']=['fake']
    else:
        accounting['raw_tables'][0]['source_basis'][1]='../../outside.csv'
    (root/SNAPSHOT_PATHS[1]).write_bytes(json_bytes(second))
    with pytest.raises(ContractError,match='scope comparison differs|not an original register capture'):
        validate_slice(EvidenceStore(root,outcome['run_id']))


def test_tampered_scope_or_discovery_import_rejected(execute):
    outcome,root=execute(reader_factory=Replay)
    first,second=read_chain(root,count=2)
    for field,value in [('retrieved_at','2026-01-01T00:00:00Z'),('attempt_key','other-key'),('local_reference','sources/missing.bin')]:
        bad=deepcopy(second)
        a=next(a for a in bad['state']['attempts'] if 'scope_basis_id' in a)
        a[field]=value
        with pytest.raises(ContractError): validate_snapshot(bad,root=root,upstream=[first])
    with (root/SNAPSHOT_PATHS[0]).open('ab') as stream: stream.write(b'\n')
    with pytest.raises(ContractError): read_chain(root,count=2)


def test_launcher_one_command_with_journal_before_dispatch(tmp_path, capsys):
    config=deepcopy(CONFIG); config['output_root']='u07-cli-output'
    path=tmp_path/'config.json';path.write_bytes(json_bytes(config))
    spec=importlib.util.spec_from_file_location('u07_launcher', ROOT/'regulatory-change-impact-brief/scripts/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def injected(*args,**kwargs): return capture_slice(*args,**kwargs,reader_factory=Replay)
    with patch('rci.runtime.REPO',tmp_path), patch('rci.runner.capture_slice',injected), patch.object(sys,'argv',['run.py','--config',str(path),'--capture-slice']):
        assert module.main()==3
    outcome=json.loads(capsys.readouterr().out)
    assert outcome['capture_slice_complete']
    first,second=read_chain(tmp_path/outcome['candidate'],count=2)
    assert len(second['state']['sources'])==10
    assert first['consumed_record_ids']==[]


def test_new_schema_format_and_frozen_fingerprints():
    schema=ROOT/'regulatory-change-impact-brief/references/schemas/scope-input.schema.json'
    Draft202012Validator.check_schema(parse_json(schema.read_bytes()))
    Draft202012Validator.check_schema(parse_json((schema.parent/'capture-accounting.schema.json').read_bytes()))
    assert sha256_bytes((ROOT/'snapshot.schema.json').read_bytes())=='sha256:8de9874ded18fa97294e83012796e4c386aa60ccfd30f8eca89cabdf2a267ac3'
    assert sha256_bytes((ROOT/'regulatory-change-impact-brief/references/schemas/contracts.schema.json').read_bytes())=='sha256:946d7fa46c18373f01313e1c2aab7b48b25b296527cbae0cf138f31f9c8915ec'


@pytest.fixture
def retained_slice(tmp_path):
    original = ROOT / 'u07-verification/.staging/run-6bec153b2d1343a5a43cc2f333798c4d'
    root = tmp_path / 'retained'
    shutil.copytree(original, root)
    second = parse_json((root / SNAPSHOT_PATHS[1]).read_bytes())
    return root, second


@pytest.mark.parametrize('mutation', [
    'role', 'invalid-type', 'boolean-as-number', 'wrong-evidence', 'missing-row',
    'duplicate-row', 'business-id', 'system-id', 'row-locator', 'field-locator',
    'raw-cell', 'mapping-column', 'mapping-meaning', 'missing-mapping',
    'missing-tables', 'duplicate-table', 'evidence-locator', 'existing-date',
])
def test_independent_normalized_provenance(retained_slice, mutation):
    root, second = retained_slice
    state = second['state']
    row = next(r for r in state['normalized_rows']
               if r['source_id'] == 'SYSTEMS' and r['system_id'] == 'AI-005')
    if mutation == 'role': row['values']['fields']['provider_role'] = True
    elif mutation == 'invalid-type': row['values']['fields']['provider_role'] = 'APPROVED'
    elif mutation == 'boolean-as-number': row['values']['fields']['deployer_role'] = 1
    elif mutation == 'wrong-evidence':
        row['evidence_ids'] = [next(e['id'] for e in state['evidence'] if 'CALENDAR' in e['assertion'])]
    elif mutation == 'missing-row':
        state['normalized_rows'].remove(row)
        second['produced_record_ids'].remove(row['id'])
    elif mutation == 'duplicate-row':
        duplicate = deepcopy(row)
        duplicate['id'] = new_record_id(second['run_id'], 2, 'normalized-row')
        state['normalized_rows'].append(duplicate)
        second['produced_record_ids'].append(duplicate['id'])
    elif mutation == 'business-id': row['source_business_id'] = 'unrelated-ID'
    elif mutation == 'system-id': row['system_id'] = 'AI-001'
    elif mutation == 'row-locator': row['locator']['value'] = 'AI System Register (gid 0) row 999'
    elif mutation == 'field-locator': row['values']['field_locators']['provider_role']['value'] = 'R999C999'
    elif mutation == 'raw-cell': row['values']['raw']['cells'][4] = 'yes'
    elif mutation == 'mapping-column': state['mappings'][0]['fields']['system_id']['column'] = 99
    elif mutation == 'mapping-meaning': state['mappings'][0]['fields']['system_id']['meaning'] = 'Unestablished meaning'
    elif mutation == 'missing-mapping':
        removed = state['mappings'].pop()
        second['produced_record_ids'].remove(removed['id'])
    elif mutation == 'missing-tables': state['extensions']['u07_capture']['value']['raw_tables'] = []
    elif mutation == 'duplicate-table':
        tables = state['extensions']['u07_capture']['value']['raw_tables']
        tables.append(deepcopy(tables[0]))
    elif mutation == 'evidence-locator': state['evidence'][0]['locator']['value'] = 'unrelated table'
    else:
        next(r for r in state['normalized_rows'] if r['source_id'] == 'CALENDAR')['existing_due_date'] = '2035-01-01'
    (root / SNAPSHOT_PATHS[1]).write_bytes(json_bytes(second))
    with pytest.raises(ContractError):
        validate_slice(EvidenceStore(root, second['run_id']))


@pytest.mark.parametrize('mutation', ['missing-source', 'source-locator', 'attempt-locator', 'adapter', 'authority'])
def test_independent_required_source_coverage(retained_slice, mutation):
    root, second = retained_slice
    state = second['state']
    source = next(s for s in state['sources'] if s['source_id'] == 'LAW')
    attempt = next(a for a in state['attempts'] if a['source_id'] == 'LAW')
    if mutation == 'missing-source':
        removed = [source, attempt] + [c for c in state['captures'] if c['attempt_id'] == attempt['id']]
        for collection in ('sources', 'attempts', 'captures'):
            state[collection] = [r for r in state[collection] if r not in removed]
        second['produced_record_ids'] = [i for i in second['produced_record_ids'] if i not in {r['id'] for r in removed}]
        for phase in ('start', 'terminal'):
            (root / f'analysis/attempts/{attempt["attempt_key"]}.{phase}.json').unlink()
    elif mutation == 'source-locator': source['locator'] = 'https://example.com/unrelated'
    elif mutation == 'authority': source['authority'] = 'binding'
    else:
        field = 'original_locator' if mutation == 'attempt-locator' else 'adapter'
        attempt[field] = 'https://example.com/unrelated' if mutation == 'attempt-locator' else 'wrong-adapter'
        # Change journal and snapshot consistently: journal equality is insufficient.
        for phase in ('start', 'terminal'):
            path = root / f'analysis/attempts/{attempt["attempt_key"]}.{phase}.json'
            event = parse_json(path.read_bytes())
            event['attempt'][field] = attempt[field]
            path.write_bytes(json_bytes(event))
    (root / SNAPSHOT_PATHS[1]).write_bytes(json_bytes(second))
    with pytest.raises(ContractError):
        validate_slice(EvidenceStore(root, second['run_id']))


@pytest.mark.parametrize('source_id,declared', [('LAW', True), ('SYSTEMS', True), ('SYSTEMS', False)])
@pytest.mark.parametrize('late', [False, True])
def test_capture_storage_failure_propagates(execute, source_id, declared, late):
    from rci import evidence
    original_write = evidence._write
    def failing_write(root, relative, data):
        if relative.startswith('sources/'):
            key = Path(relative).stem
            start = parse_json((root / f'analysis/attempts/{key}.start.json').read_bytes())
            if start['attempt']['source_id'] == source_id:
                if late: original_write(root, relative, data)
                raise OSError('Injected source storage failure')
        return original_write(root, relative, data)
    with patch('rci.evidence._write', failing_write):
        outcome, root = execute(DECLARED if declared else None, reader_factory=Replay)
    assert outcome['status'] == 'failed' and not outcome['capture_slice_complete'], outcome
    assert not outcome['package_acceptance']
    events = EvidenceStore(root, outcome['run_id']).inventory()
    failed = [e for e in events if e['attempt']['source_id'] == source_id]
    assert failed and all(e['diagnostic']['failure_type'] == 'OSError' for e in failed)
    assert all(e['attempt']['content'] is e['attempt']['content_hash'] is None for e in failed)
    if late:
        assert all((root / e['diagnostic']['affected_output']).is_file() for e in failed)
    if declared:
        first, second = validate_slice(EvidenceStore(root, outcome['run_id']))
        assert first['status'] == 'complete' and second['status'] == 'failed'
        assert len(second['state']['sources']) == 10
        # An internally matching journal cannot excuse an incorrect stage state.
        second['status'] = 'partial'
        (root / SNAPSHOT_PATHS[1]).write_bytes(json_bytes(second))
        with pytest.raises(ContractError): validate_slice(EvidenceStore(root, outcome['run_id']))
    else:
        assert outcome['missing_snapshots'] == list(SNAPSHOT_PATHS)


def test_capture_integrity_failure_is_failed_not_scope_limitation(execute):
    class DamagingReplay(Replay):
        def read(self, source):
            events = super().read(source)
            if source.id == 'LAW':
                (self.store.root / events[-1]['attempt']['local_reference']).write_bytes(b'corrupted capture')
            return events
    outcome, root = execute(DECLARED, reader_factory=DamagingReplay)
    assert outcome['status'] == 'failed' and not outcome['capture_slice_complete'], outcome
    assert 'hash mismatch' in outcome['reason']
    assert not (root / SNAPSHOT_PATHS[1]).exists()
    with pytest.raises(ContractError): EvidenceStore(root, outcome['run_id']).inventory()
