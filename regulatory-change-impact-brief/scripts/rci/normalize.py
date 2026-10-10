"""U06 source-grounded normalization. No reconciliation or approval decisions.

normalize_table is the pure transformation seam. normalize_registers consumes
only U05's independently verified handoff and binds rows to retained evidence.
Unknown or invalid meanings remain raw with diagnostics, never guessed values.
"""
from collections import Counter
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker

from .adapters.anonymous_sheets import csv_rows
from .adapters.readiness import register_readiness
from .contracts import parse_json, require, validate_schema
from .ids import IdentityRegistry, IdentityConflict, new_record_id


REFERENCES = Path(__file__).resolve().parents[2] / 'references'
DICTIONARY_PATH = REFERENCES / 'field-dictionary.json'
VALUES_SCHEMA_PATH = REFERENCES / 'schemas/normalized-values.schema.json'


@lru_cache(maxsize=16)
def _checked_validator(raw):
    schema = parse_json(raw)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def load_dictionary():
    """Only reviewed exact headers are supported; this version declares no aliases."""
    dictionary = parse_json(DICTIONARY_PATH.read_bytes())
    validator = _checked_validator((REFERENCES / 'schemas/field-dictionary.schema.json').read_bytes())
    require(validator.is_valid(dictionary), 'invalid dictionary schema')
    require(dictionary['schema_version'] == 'rci-field-dictionary/1', 'unknown dictionary version')
    require(set(dictionary['registers']) == {'SYSTEMS', 'EVIDENCE', 'CALENDAR'}, 'invalid register dictionary')
    for spec in dictionary['registers'].values():
        fields = spec['fields']
        require(len({f['header'] for f in fields}) == len(fields)
                and len({f['field'] for f in fields}) == len(fields), 'ambiguous dictionary fields')
        require(spec['identity_header'] in {f['header'] for f in fields}, 'missing identity mapping')
        for field in fields:
            require(field['required'] is True and field['aliases'] == [], 'unreviewed mapping or alias')
            require(field['kind'] in {'text', 'date', 'enum'} and field['meaning'].strip(), 'invalid mapping meaning')
            if field['kind'] == 'enum':
                require(isinstance(field['tokens'], dict) and field['tokens'], 'missing explicit token mapping')
    return dictionary


def validate_values(value):
    """Supplement the frozen normalized-row values object; never alter G1."""
    validator = _checked_validator(VALUES_SCHEMA_PATH.read_bytes())
    errors = list(validator.iter_errors(value))
    require(not errors, 'invalid normalized values: ' + (errors[0].message if errors else ''))


def _value(raw, field):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('required value must be a nonempty source string')
    if field['kind'] == 'text':
        return raw
    if field['kind'] == 'date':
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', raw):
            raise ValueError('expected a date-only YYYY-MM-DD value')
        date.fromisoformat(raw)
        return raw
    if raw not in field['tokens']:
        raise ValueError('unknown source token; meaning not established')
    return field['tokens'][raw]


def normalize_table(source_id, table, *, run_id, tab_title, sheet_id,
                    evidence_ids, source_basis, retrieved_at=None):
    """Retain every row and cell, including invalid and identity-conflicting rows.

    Callers supply the validated acquisition context. Production callers use
    normalize_registers below; this seam does not establish source authenticity.
    A row lacking usable source/system identity remains in raw_tables rather
    than manufacturing a normalized-row identity to satisfy the core schema.
    """
    dictionary = load_dictionary()
    require(source_id in dictionary['registers'], 'unsupported register')
    require(isinstance(table, list) and all(isinstance(r, list) for r in table), 'invalid raw table shape')
    require(evidence_ids and source_basis, 'normalization requires evidence and source basis')
    spec = dictionary['registers'][source_id]
    rows, diagnostics, mappings = [], [], []
    raw_table = {'source_id': source_id, 'sheet_id': sheet_id, 'tab_title': tab_title,
                 'rows': deepcopy(table), 'source_basis': list(source_basis)}

    def issue(reason, row=None, owner=None):
        location = f'{tab_title} (gid {sheet_id})' + (f' row {row}' if row is not None else '')
        record = dict(id=new_record_id(run_id, 2, 'diagnostic'), record_type='diagnostic',
                      summary=f'{source_id}: {reason} at {location}', evidence_ids=list(evidence_ids),
                      source_basis=list(source_basis) + [location], reason=reason, owner=owner,
                      resolution_need='Source owner must establish/correct the field meaning, value or identity; preserve the original capture.')
        validate_schema(record, 'diagnostic')
        diagnostics.append(record)

    def result():
        return {'normalized_rows': rows, 'mappings': mappings, 'diagnostics': diagnostics,
                'raw_tables': [raw_table], 'status': 'partial' if diagnostics else 'complete'}

    if tab_title != spec['tab_title']:
        issue('unknown register tab; meaning not established')
        return result()
    if not table or len(table) < 2:
        issue('missing register header or data rows')
        return result()
    headers = table[0]
    if any(not isinstance(h, str) for h in headers):
        issue('invalid non-string header')
        return result()
    required_headers = {f['header'] for f in spec['fields']}
    if any(n > 1 and header in required_headers for header, n in Counter(headers).items()):
        issue('duplicated required headers; ambiguous required mapping')
        return result()
    missing = [f['header'] for f in spec['fields'] if f['header'] not in headers]
    for header in missing:
        issue('missing required field or unknown rename: ' + header)
    if missing:
        return result()
    positions = {f['field']: headers.index(f['header']) for f in spec['fields']}
    mapping = dict(id=new_record_id(run_id, 2, 'mapping'), record_type='mapping',
                   summary=f'Exact source-grounded {source_id} header mapping', evidence_ids=list(evidence_ids),
                   source_id=source_id, mapping_version=dictionary['schema_version'],
                   fields={f['header']: {'field': f['field'], 'column': positions[f['field']] + 1,
                                        'meaning': f['meaning']} for f in spec['fields']})
    validate_schema(mapping, 'mapping')
    mappings.append(mapping)
    identity_field = next(f['field'] for f in spec['fields'] if f['header'] == spec['identity_header'])
    identity_counts = Counter(r[positions[identity_field]] for r in table[1:]
                              if len(r) > positions[identity_field]
                              and isinstance(r[positions[identity_field]], str))
    identities = IdentityRegistry()
    for number, cells in enumerate(table[1:], 2):
        if len(cells) != len(headers):
            issue('row width differs from captured headers', number)
            continue
        start_issues = len(diagnostics)
        fields, locators = {}, {}
        owner_raw = cells[positions['owner']]
        owner = owner_raw if isinstance(owner_raw, str) and owner_raw.strip() else None
        for field in spec['fields']:
            column = positions[field['field']]
            locators[field['field']] = {'kind': 'sheet',
                'value': f'{tab_title} (gid {sheet_id}) R{number}C{column + 1}'}
            try:
                fields[field['field']] = _value(cells[column], field)
            except ValueError as exc:
                issue(f'invalid value for {field["header"]}: {exc}', number, owner)
        business_id, system_id = fields.get(identity_field), fields.get('system_id')
        if business_id is None or system_id is None:
            continue
        try:
            identities.operational(source_id, business_id)
        except IdentityConflict:
            pass  # Counts below mark *all* conflicting rows; no first/last winner.
        if identity_counts[business_id] > 1:
            issue('conflicting source identity: ' + business_id, number, owner)
        values = {'schema_version': 'rci-normalized-values/1', 'register': source_id,
                  'raw': {'headers': deepcopy(headers), 'cells': deepcopy(cells)},
                  'fields': fields, 'field_locators': locators,
                  'validation_status': 'unresolved' if len(diagnostics) > start_issues else 'valid'}
        validate_values(values)
        record = dict(id=new_record_id(run_id, 2, 'normalized-row'), record_type='normalized-row',
                      summary=f'Reported {source_id} row {business_id}', evidence_ids=list(evidence_ids),
                      source_id=source_id, source_business_id=business_id, system_id=system_id,
                      locator={'kind': 'sheet', 'value': f'{tab_title} (gid {sheet_id}) row {number}'},
                      values=values)
        if retrieved_at is not None:
            record['retrieved_at'] = retrieved_at
        if source_id == 'CALENDAR' and 'existing_due_date' in fields:
            record['existing_due_date'] = fields['existing_due_date']
        validate_schema(record, 'normalized-row')
        rows.append(record)
    return result()


def normalize_registers(store):
    """Consume the anonymous U05 handoff; retain visible issues for blocked inputs.

    Returns Stage 02-compatible collections plus raw table accounting. Does not
    write snapshots or change captures, selection, approval or assigned date.
    """
    readiness = register_readiness(store)
    events = {e['attempt']['id']: e for e in store.inventory()}
    result = {'normalized_rows': [], 'mappings': [], 'diagnostics': [], 'evidence': [],
              'raw_tables': [], 'status': 'complete'}
    for register in readiness['registers']:
        source_id = register['source_id']
        if not register['ready']:
            diagnostic = dict(id=new_record_id(store.run_id, 2, 'diagnostic'), record_type='diagnostic',
                summary=f'{source_id} normalization blocked: {register["blocker"]}', evidence_ids=[],
                source_basis=[source_id], reason=register['blocker'], owner=None,
                resolution_need='Obtain a complete identity-verified register capture through the documented U05 read route.')
            validate_schema(diagnostic, 'diagnostic')
            result['diagnostics'].append(diagnostic)
            result['status'] = 'partial'
            continue
        for tab in register['tabs']:
            event = events[tab['attempt_id']]
            capture = event['capture']
            raw = (store.root / capture['local_reference']).read_bytes()
            locator = {'kind': 'sheet', 'value': f'{tab["title"]} (gid {tab["sheet_id"]}) full CSV table'}
            evidence = store.claim(capture, locator=locator,
                assertion=f'Retained raw {source_id} register table; labels are reported assertions, not compliance or approval.',
                quoted_support=raw.decode('utf-8'))
            result['evidence'].append(evidence)
            normalized = normalize_table(source_id, csv_rows(raw), run_id=store.run_id,
                tab_title=tab['title'], sheet_id=tab['sheet_id'], evidence_ids=[evidence['id']],
                source_basis=[source_id, capture['local_reference'], capture['content_hash']],
                retrieved_at=event['attempt']['retrieved_at'])
            for key in ('normalized_rows', 'mappings', 'diagnostics', 'raw_tables'):
                result[key].extend(normalized[key])
            if normalized['status'] != 'complete':
                result['status'] = 'partial'
    return result
