"""U06 independent semantic, provenance, format and metamorphic acceptance."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random

import httpx
import pytest

from rci.adapters import ReadAdapters
from rci.adapters.anonymous_sheets import csv_rows
from rci.adapters.readiness import register_readiness
from rci.contracts import ContractError, json_bytes, sha256_bytes, validate_schema
from rci.evidence import EvidenceStore
from rci.normalize import load_dictionary, normalize_registers, normalize_table, validate_values
from rci.source_manifest import disclosed_manifest


ROOT = Path(__file__).resolve().parents[2]
CAPTURES = ROOT / 'docs/verification/u05-anonymous-live'
REPORT = json.loads((CAPTURES / 'analysis/source-access.json').read_bytes())
REGISTERS = REPORT['register_readiness']['registers']


def table(source):
    register = next(r for r in REGISTERS if r['source_id'] == source)
    tab, = register['tabs']
    return csv_rows((CAPTURES / tab['local_reference']).read_bytes()), tab


def normalize(source, rows=None):
    raw, tab = table(source)
    return normalize_table(source, rows if rows is not None else raw, run_id='run-u06-test',
        tab_title=tab['title'], sheet_id=tab['sheet_id'], evidence_ids=['test-only-table-evidence'],
        source_basis=[source, tab['local_reference'], tab['content_hash']])


def meanings(result):
    return sorted((r['source_business_id'], r['system_id'], json_bytes(r['values']['fields']))
                  for r in result['normalized_rows'])


def change(source, header, value):
    rows, _ = table(source)
    rows[1][rows[0].index(header)] = value
    return rows


@pytest.mark.parametrize('source,count', [('SYSTEMS', 8), ('EVIDENCE', 10), ('CALENDAR', 8)])
def test_all_real_rows_and_exact_dictionary_basis(source, count):
    rows, tab = table(source)
    dictionary = load_dictionary()
    spec = dictionary['registers'][source]
    assert [f['header'] for f in spec['fields']] == rows[0]
    assert spec['basis']['path'] == tab['local_reference']
    assert spec['basis']['sha256'] == sha256_bytes((CAPTURES / tab['local_reference']).read_bytes())
    result = normalize(source)
    assert result['status'] == 'complete' and not result['diagnostics']
    assert len(result['normalized_rows']) == count
    for number, record in enumerate(result['normalized_rows'], 2):
        validate_schema(record, 'normalized-row')
        validate_values(record['values'])
        assert record['values']['raw'] == {'headers': rows[0], 'cells': rows[number - 1]}
        assert record['locator']['value'].endswith(f'row {number}')
        assert record['values']['validation_status'] == 'valid'
    for mapping in result['mappings']:
        validate_schema(mapping, 'mapping')
        assert set(mapping['fields']) == set(rows[0])


@pytest.mark.parametrize('source', ['SYSTEMS', 'EVIDENCE', 'CALENDAR'])
@pytest.mark.parametrize('seed', [1, 19, 73])
def test_shuffled_rows_headers_and_extra_columns_preserve_meanings(source, seed):
    rows, _ = table(source)
    baseline = normalize(source)
    rng = random.Random(seed)
    order = list(range(len(rows[0])))
    rng.shuffle(order)
    transformed = [[row[i] for i in order] + ['unrelated extra' if n == 0 else f'raw {n}']
                   for n, row in enumerate(rows)]
    data = transformed[1:]
    rng.shuffle(data)
    transformed[1:] = data
    result = normalize(source, transformed)
    assert result['status'] == 'complete'
    assert meanings(result) == meanings(baseline)
    for number, record in enumerate(result['normalized_rows'], 2):
        fields = record['values']['fields']
        assert record['values']['raw']['cells'] == transformed[number - 1]
        for spec in load_dictionary()['registers'][source]['fields']:
            column = transformed[0].index(spec['header']) + 1
            assert record['values']['field_locators'][spec['field']]['value'].endswith(f'R{number}C{column}')
            assert spec['field'] in fields
        mapping, = result['mappings']
        assert mapping['fields'][spec['header']]['column'] == column


@pytest.mark.parametrize('source,date_header,version_header,date_field', [
    ('SYSTEMS', 'evidence_updated_at', 'record_version', 'evidence_updated_on'),
    ('EVIDENCE', 'reported_at', None, 'reported_on'),
    ('CALENDAR', 'due_date', 'source_version', 'existing_due_date')])
def test_newer_valid_dates_versions_and_stable_ids(source, date_header, version_header, date_field):
    rows = change(source, date_header, '2031-02-28')
    if version_header:
        rows[1][rows[0].index(version_header)] = 'new-valid-version-2031'
    result = normalize(source, rows)
    assert result['status'] == 'complete'
    current = result['normalized_rows'][0]
    original = normalize(source)['normalized_rows'][0]
    assert (current['source_business_id'], current['system_id']) == (original['source_business_id'], original['system_id'])
    assert current['values']['fields'][date_field] == '2031-02-28'
    if version_header:
        assert current['values']['fields'][version_header] == 'new-valid-version-2031'
    assert 'source_revision_at' not in current and 'observed_at' not in current
    assert 'proposed_due_date' not in current and 'reviewer_response_at' not in current


@pytest.mark.parametrize('source', ['SYSTEMS', 'EVIDENCE', 'CALENDAR'])
@pytest.mark.parametrize('case', ['duplicate', 'missing', 'unknown_rename', 'blank_header'])
def test_ambiguous_required_mappings_are_visible_and_raw_retained(source, case):
    rows, _ = table(source)
    if case == 'duplicate':
        for row in rows:
            row.append(row[0])
    elif case == 'missing':
        for row in rows:
            del row[1]
    elif case == 'unknown_rename':
        rows[0][1] = rows[0][1] + '_renamed'
    else:
        rows[0][1] = ''
    result = normalize(source, rows)
    assert result['status'] == 'partial' and result['diagnostics']
    assert result['normalized_rows'] == result['mappings'] == []
    assert result['raw_tables'][0]['rows'] == rows
    for diagnostic in result['diagnostics']:
        validate_schema(diagnostic, 'diagnostic')
        assert diagnostic['resolution_need'] and diagnostic['source_basis']


@pytest.mark.parametrize('source,header,value,field', [
    ('SYSTEMS', 'provider_role', 'Yes', 'provider_role'),
    ('SYSTEMS', 'deployer_role', 1, 'deployer_role'),
    ('SYSTEMS', 'current_notice', 'machine_readable_provenance', 'current_notice'),
    ('SYSTEMS', 'evidence_updated_at', '2031-02-29', 'evidence_updated_on'),
    ('SYSTEMS', 'owner', '', 'owner'),
    ('EVIDENCE', 'reported_at', '2026-08-20T00:00:00Z', 'reported_on'),
    ('EVIDENCE', 'evidence_state', 'compliant', 'evidence_state'),
    ('EVIDENCE', 'status', 'approved', 'operational_status'),
    ('CALENDAR', 'due_date', '09/04/2026', 'existing_due_date'),
    ('CALENDAR', 'approval_required', '2026-09-04', 'required_reviewer'),
    ('CALENDAR', 'status', 'approved', 'operational_status')])
def test_invalid_values_not_promoted_and_original_retained(source, header, value, field):
    rows = change(source, header, value)
    result = normalize(source, rows)
    assert result['status'] == 'partial'
    assert any(header in d['reason'] for d in result['diagnostics'])
    record = result['normalized_rows'][0]
    assert record['values']['validation_status'] == 'unresolved'
    assert field not in record['values']['fields']
    assert record['values']['raw']['cells'][rows[0].index(header)] == value
    validate_values(record['values'])


@pytest.mark.parametrize('source,identity', [('SYSTEMS', 'system_id'), ('EVIDENCE', 'record_id'), ('CALENDAR', 'action_id')])
def test_conflicting_ids_mark_both_rows_without_winner(source, identity):
    rows, _ = table(source)
    col = rows[0].index(identity)
    rows[2][col] = rows[1][col]
    for data in (rows, [rows[0]] + list(reversed(rows[1:]))):
        result = normalize(source, data)
        conflicting = [r for r in result['normalized_rows'] if r['source_business_id'] == rows[1][col]]
        assert len(conflicting) == 2
        assert all(r['values']['validation_status'] == 'unresolved' for r in conflicting)
        assert sum('conflicting source identity' in d['reason'] for d in result['diagnostics']) == 2
        assert len(result['normalized_rows']) == len(rows) - 1


@pytest.mark.parametrize('source', ['SYSTEMS', 'EVIDENCE', 'CALENDAR'])
def test_no_row_position_identity_and_no_truncated_row_acceptance(source):
    rows, _ = table(source)
    identity = load_dictionary()['registers'][source]['identity_header']
    rows[1][rows[0].index(identity)] = ''
    rows[2].pop()
    result = normalize(source, rows)
    assert len(result['normalized_rows']) == len(rows) - 3
    assert result['raw_tables'][0]['rows'] == rows
    assert any('row width' in d['reason'] for d in result['diagnostics'])
    assert any(identity in d['reason'] for d in result['diagnostics'])


@pytest.mark.parametrize('source', ['SYSTEMS', 'EVIDENCE', 'CALENDAR'])
def test_every_required_field_is_checked_without_fuzzy_aliases(source):
    original, _ = table(source)
    for index, header in enumerate(original[0]):
        rows = deepcopy(original)
        rows[0][index] = header.replace('_', ' ').title()
        # Even a plausibly friendly spelling needs a documented alias.
        if rows[0][index] == header:
            rows[0][index] += ' renamed'
        result = normalize(source, rows)
        assert not result['normalized_rows'] and result['diagnostics']
        assert any(header in d['reason'] for d in result['diagnostics'])


def test_duplicate_id_on_malformed_row_still_marks_valid_row_unresolved():
    rows, _ = table('EVIDENCE')
    rows[2][0] = rows[1][0]
    rows[2].pop()
    result = normalize('EVIDENCE', rows)
    assert result['normalized_rows'][0]['values']['validation_status'] == 'unresolved'
    assert any('conflicting source identity' in d['reason'] for d in result['diagnostics'])


def test_unknown_tab_and_empty_table_are_visible():
    for rows, title in [([], 'AI System Register'), (table('SYSTEMS')[0], 'Renamed register')]:
        result = normalize_table('SYSTEMS', rows, run_id='run-u06-test', tab_title=title,
                                sheet_id=0, evidence_ids=['test-only'], source_basis=['SYSTEMS'])
        assert result['diagnostics'] and not result['normalized_rows']
        assert result['raw_tables'][0]['rows'] == rows


def test_unrelated_blank_cell_is_benign_and_retained():
    rows, _ = table('SYSTEMS')
    for number, row in enumerate(rows):
        row.append('optional extra' if number == 0 else '')
    result = normalize('SYSTEMS', rows)
    assert result['status'] == 'complete'
    assert meanings(result) == meanings(normalize('SYSTEMS'))
    assert result['normalized_rows'][0]['values']['raw']['cells'][-1] == ''


@pytest.mark.parametrize('source', ['SYSTEMS', 'EVIDENCE', 'CALENDAR'])
@pytest.mark.parametrize('extras', [['audit', 'audit'], [''], ['', 'audit', 'audit']])
def test_unrelated_blank_or_duplicate_headers_preserve_semantics(source, extras):
    rows, _ = table(source)
    baseline = normalize(source)
    transformed = [row + (extras if number == 0 else
                         [f'extra {number}/{column}' for column in range(len(extras))])
                   for number, row in enumerate(rows)]
    result = normalize(source, transformed)
    assert result['status'] == 'complete' and not result['diagnostics']
    assert meanings(result) == meanings(baseline)
    assert result['mappings'][0]['fields'] == baseline['mappings'][0]['fields']
    assert result['raw_tables'][0]['rows'] == transformed
    for number, record in enumerate(result['normalized_rows'], 1):
        assert record['values']['raw'] == {'headers': transformed[0], 'cells': transformed[number]}
        assert record['values']['field_locators'] == baseline['normalized_rows'][number - 1]['values']['field_locators']


def test_meaning_boundaries_and_actual_all_scope_token():
    systems = {r['system_id']: r['values']['fields'] for r in normalize('SYSTEMS')['normalized_rows']}
    assert systems['AI-003']['current_notice'] == 'visible_label'
    assert systems['AI-008']['current_notice'] == 'visible_label'
    assert all('provenance' not in fields and 'approval_status' not in fields for fields in systems.values())
    assert systems['AI-005']['provider_role'] is None
    assert systems['AI-001']['provider_role'] is False and systems['AI-001']['deployer_role'] is True
    assert systems['AI-001']['evidence_state'] == 'complete'
    incidents = {r['source_business_id']: r['values']['fields'] for r in normalize('EVIDENCE')['normalized_rows']}
    assert incidents['REC-001']['operational_status'] == 'closed'
    assert incidents['REC-010']['source_record_type'] == 'exception_request'
    assert incidents['REC-010']['operational_status'] == 'draft'
    actions = normalize('CALENDAR')['normalized_rows']
    assert actions[-1]['source_business_id'] == 'ACT-008' and actions[-1]['system_id'] == 'ALL'
    assert actions[-1]['values']['fields']['required_reviewer'] == 'Operations'
    assert actions[2]['values']['fields']['required_reviewer'] == 'Legal'
    assert not any('approval_status' in r['values']['fields'] for r in actions)


def test_supplemental_schema_rejects_type_confusion_and_unexpected_meanings():
    values = normalize('SYSTEMS')['normalized_rows'][0]['values']
    for field, value in [('provider_role', 'yes'), ('evidence_updated_on', 'bad-date'),
                         ('current_notice', 'provenance_verified')]:
        corrupt = deepcopy(values)
        corrupt['fields'][field] = value
        with pytest.raises(ContractError, match='invalid normalized values'):
            validate_values(corrupt)
    corrupt = deepcopy(values)
    del corrupt['fields']['system_id']
    with pytest.raises(ContractError):
        validate_values(corrupt)


def test_real_retained_capture_integration_and_evidence_bindings():
    store = EvidenceStore(CAPTURES, REPORT['run_id'])
    before = store.inventory()
    result = normalize_registers(store)
    assert result['status'] == 'complete' and not result['diagnostics']
    assert Counter(r['source_id'] for r in result['normalized_rows']) == {'SYSTEMS': 8, 'EVIDENCE': 10, 'CALENDAR': 8}
    assert len(result['evidence']) == len(result['mappings']) == 3
    assert store.inventory() == before
    captures = {e['capture']['id']: e['capture'] for e in before if e['capture']}
    evidence = {e['id']: e for e in result['evidence']}
    for record in result['normalized_rows'] + result['mappings']:
        claim, = [evidence[e] for e in record['evidence_ids']]
        capture = captures[claim['capture_id']]
        raw = (CAPTURES / claim['local_reference']).read_bytes()
        assert sha256_bytes(raw) == capture['content_hash'] == claim['content_hash']
        assert claim['quoted_support'] == raw.decode('utf-8')
        validate_schema(claim, 'evidence')


def test_read_adapter_capture_normalizer_with_actual_response_replay(tmp_path):
    """Exercise actual U05 adapter dispatch with explicitly test-only retained bodies."""
    old = EvidenceStore(CAPTURES, REPORT['run_id']).inventory()
    responses = {}
    for event in old:
        a = event['attempt']
        if a['source_id'] in {'SYSTEMS', 'EVIDENCE', 'CALENDAR'}:
            responses[a['effective_locator']] = event
    store = EvidenceStore(tmp_path, 'run-u06-replay')
    calls = []
    def handler(request):
        calls.append(str(request.url))
        assert request.method == 'GET' and not request.content and 'Authorization' not in request.headers
        event = responses[str(request.url)]
        attempt = event['attempt']
        body = (CAPTURES / attempt['local_reference']).read_bytes()
        status = int(attempt['outcome'].removeprefix('HTTP '))
        headers = {'Content-Type': attempt['content_type']}
        if status in {301, 302, 303, 307, 308}:
            headers['Location'] = event['capture']['representation_metadata']['redirect_target']
        return httpx.Response(status, headers=headers, content=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        reader = ReadAdapters(store, client=client, retries=0)
        for source in disclosed_manifest():
            if source.id in {'SYSTEMS', 'EVIDENCE', 'CALENDAR'}:
                reader.read(source)
    assert register_readiness(store)['status'] == 'ready'
    result = normalize_registers(store)
    assert result['status'] == 'complete' and len(result['normalized_rows']) == 26
    assert len(calls) == len(store.inventory())
    assert all('run-u06-replay' in r['id'] for r in result['normalized_rows'] + result['evidence'])
    for source in ('SYSTEMS', 'EVIDENCE', 'CALENDAR'):
        assert meanings({'normalized_rows': [r for r in result['normalized_rows'] if r['source_id'] == source]}) == meanings(normalize(source))


def test_unavailable_capture_yields_visible_issues_without_fallback():
    root = ROOT / 'docs/verification/u05-live'
    report = json.loads((root / 'analysis/source-access.json').read_bytes())
    result = normalize_registers(EvidenceStore(root, report['run_id']))
    assert result['status'] == 'partial'
    assert not result['normalized_rows'] and not result['mappings'] and not result['evidence']
    assert len(result['diagnostics']) == 3
    assert all(d['reason'] == 'missing-caller-authentication' for d in result['diagnostics'])
