"""Mechanical artifact output and independent semantic parsing, U14–U16."""
import csv
from datetime import date
from html import unescape
import io

from icalendar import Calendar
import pytest

from importlib import import_module

brief = import_module('rci.renderers.brief')
calendar = import_module('rci.renderers.calendar')
csv_register = import_module('rci.renderers.csv_register')
from rci.validate import validate_artifacts


@pytest.fixture
def export_model():
    rule = dict(id='rule-record', rule_version_id='rule:v1:legal-meaning', source_versions=['OJ-v1'], basis_type='legal-rule')
    internal = dict(id='internal-record', rule_version_id='rule:v1:internal-meaning', source_versions=['POL-v1'], basis_type='internal-control')
    impacts = []
    for n, state in enumerate(('supported-impact', 'supported-no-impact', 'conflicting', 'unresolved')):
        impacts.append(dict(id=f'impact-record-{n}', impact_id=f'impact:v1:{n}', system_id='學習系統',
            rule_id='rule-record' if n < 2 else 'internal-record', state=state,
            identity_key=dict(distinguishing_scope='learner chat'), evidence_ids=['evidence-one', 'evidence-two'],
            summary='Scoped finding, with "quoted" Unicode é資料', reason='Exact scoped evidence supports this state',
            owner=None if n == 3 else 'Operations', resolution_need='Confirm the missing evidence' if n >= 2 else None,
            basis_type='legal-rule' if n < 2 else 'internal-control'))
    actions = []
    for n, due in enumerate(('2026-09-01', '2026-09-02', None)):
        actions.append(dict(id=f'action-record-{n}', action_id='action:v1:' + str(n) * 64,
            system_id='學習系統', impact_ids=['impact-record-0'], distinguishing_scope='learner chat',
            summary=f'Proposed action {n}, retain "quotes" and Unicode 資料', owner=None if n == 2 else 'Marketing',
            proposed_due_date=due, existing_due_date='2026-08-31', date_basis='Proposed date awaiting human review' if due else 'No date can be established from the evidence',
            approval_status='pending', evidence_ids=['evidence-one'], source_basis=['rule:v1:legal-meaning']))
    request = dict(request_id='review-one', required_reviewer='Operations', question='Approve the exact proposed date?',
        subject_ids=['action-record-0'], source_versions=['OJ-v1'], delivery_status='not-sent', evidence_ids=['evidence-one'])
    calendar_context = [dict(id='calendar-row-1', source_business_id='CAL-001', system_id='學習系統',
        evidence_ids=['evidence-two'], values=dict(fields=dict(action='Original source task', owner='Marketing',
            existing_due_date='2026-09-05', operational_status='closed', required_reviewer='Legal'),
            raw=dict(headers=['due_date', 'status', 'approval_required'], cells=['2026-09-05', 'closed', 'legal']))),
        dict(id='calendar-row-2', source_business_id='CAL-ALL', system_id='ALL', evidence_ids=['evidence-two'],
            values=dict(fields=dict(action='Hold source-wide readiness meeting', owner='Operations',
                existing_due_date='2026-08-31', operational_status='scheduled', required_reviewer='Operations'),
                raw=dict(headers=['due_date', 'status', 'approval_required'], cells=['2026-08-31', 'scheduled', 'operations'])))]
    return dict(run_id='run-renderer-fixture', assigned_review_date='2026-08-26', status='partial', draft_version='draft-1',
        recipients=['Legal', 'Operations'], systems_in_scope=['學習系統'], created_at='2026-08-27T15:00:00.123Z',
        source_quality=[dict(id='source-record', source_id='OJ', retrieval_status='retrieved', summary='Captured exact retained source')],
        limitations=[dict(id='gap-one', summary='Missing report attachment', evidence_ids=['evidence-two'], resolution_need='Obtain an authorized attachment')],
        rules=[rule, internal], impacts=impacts, actions=actions, review_requests=[request], calendar_context=calendar_context,
        unresolved_coverage=[],
        decisions=[dict(id='decision-one', summary='Keep proposals pending', chosen_behavior='Prepare requests',
                        rationale='Human review is required for a changed date', evidence_ids=['evidence-one'])],
        evidence_index=[dict(id='evidence-one', local_reference='sources/source.txt', content_hash='sha256:'+'a'*64,
                             locator='line:1'), dict(id='evidence-two', local_reference='sources/report.txt',
                                                     content_hash='sha256:'+'b'*64, locator='line:2')])


def write_artifacts(root, model):
    rendered = {'impact-register.csv': csv_register.render(model), 'compliance-brief.md': brief.render(model),
                'action-calendar.ics': calendar.render(model)}
    for path, raw in rendered.items():
        (root / path).write_bytes(raw)
    return rendered


def test_all_outputs_round_trip_semantics(export_model, tmp_path):
    raw = write_artifacts(tmp_path, export_model)
    assert validate_artifacts(tmp_path, export_model)
    assert write_artifacts(tmp_path, export_model) == raw


def test_csv_columns_cardinality_unicode_quotes_and_multiple_actions(export_model, tmp_path):
    raw = write_artifacts(tmp_path, export_model)['impact-register.csv']
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''))
    assert reader.fieldnames == csv_register.COLUMNS
    rows = list(reader)
    assert len(rows) == len(export_model['impacts']) == 4
    first = rows[0]
    assert first['system_id'] == '學習系統'
    assert first['action_ids'].split(';') == [a['action_id'] for a in export_model['actions']]
    assert first['proposed_due_date'] == '2026-09-01;2026-09-02;'
    assert first['proposed_action'] == ';'.join(a['summary'] for a in export_model['actions'])
    assert first['evidence_ids'] == 'evidence-one;evidence-two'
    assert rows[-1]['owner'] == '' and rows[-1]['reason'] and rows[-1]['resolution_need']
    assert rows[0]['basis_type'] == 'legal-rule' and rows[-1]['basis_type'] == 'internal-control'
    assert raw.endswith(b'\r\n') and b'""quotes""' in raw
    assert validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('value', ['=1+1', '+1+1', '-1+1', '@SUM(A1)', '\t=1+1', '\r=1+1', '\n=1+1',
                                  "'literal", '  =HYPERLINK("https://example.test")', ' \t+SUM(A1)',
                                  'reason, "quoted"\nsecond line', 'é資料'])
def test_csv_formula_safety_is_reversible(export_model, tmp_path, value):
    export_model['impacts'][0]['reason'] = value
    # CR is a CSV scalar case; RFC 5545 TEXT carries LF, not literal CR.
    if '\r' not in value:
        export_model['actions'][0]['summary'] = value
    raw = write_artifacts(tmp_path, export_model)['impact-register.csv']
    row = next(csv.DictReader(io.StringIO(raw.decode('utf-8'), newline='')))
    assert row['reason'] == csv_register.display(value)
    if value.startswith(("'", '\t', '\r', '\n')) or value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
        assert row['reason'].startswith("'")
    assert validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('status', ['complete', 'partial', 'blocked'])
def test_brief_mandatory_sections_states_scope_recipients_and_ids(export_model, tmp_path, status):
    export_model['status'] = status
    raw = write_artifacts(tmp_path, export_model)['compliance-brief.md']
    text = unescape(raw.decode('utf-8'))
    for title in ('Scope', 'Source quality', 'Source limitations', 'Supported observations', 'Conflicts', 'Unresolved scope',
                  'Proposed actions and dates', 'Existing operational calendar', 'Decisions requested', 'Engineering decisions', 'Evidence index'):
        assert '## '+title in text
    assert 'Run status: '+status in text and 'Recipients: Legal;Operations' in text
    assert 'Proposed date: Undated' in text and 'No date can be established from the evidence' in text
    assert 'Existing operational date: 2026-08-31' in text
    assert 'Delivery: not-sent' in text and 'have not been sent' in text
    for impact in export_model['impacts']:
        assert impact['impact_id'] in text and impact['state'] in text
    for record in export_model['evidence_index']:
        assert record['id'] in text and record['local_reference'] in text
    assert '[Stage 07](snapshots/07-publication-validation.json)' in text
    assert validate_artifacts(tmp_path, export_model)


def test_brief_source_text_cannot_inject_markdown_or_html(export_model, tmp_path):
    malicious = '資料 **bold** _italics_ [click](javascript:bad) ![image](https://bad.test) `code` <script>bad</script>\n## Fake heading\n- item | cell \\ escape'
    export_model['impacts'][0]['summary'] = malicious
    export_model['limitations'][0]['summary'] = malicious
    export_model['source_quality'][0]['summary'] = malicious
    export_model['actions'][0]['summary'] = malicious
    export_model['review_requests'][0]['question'] = malicious
    export_model['calendar_context'][0]['values']['fields']['action'] = malicious
    raw = write_artifacts(tmp_path, export_model)['compliance-brief.md'].decode('utf-8')
    for syntax in ('**bold**', '_italics_', '[click]', '![image]', '`code`', '<script>', '\n## Fake heading'):
        assert syntax not in raw
    assert malicious in unescape(raw)
    assert validate_artifacts(tmp_path, export_model)


def test_brief_retains_unmatched_and_all_native_calendar_semantics(export_model, tmp_path):
    raw = write_artifacts(tmp_path, export_model)['compliance-brief.md']
    decoded = unescape(raw.decode('utf-8'))
    assert decoded.index('## Proposed actions and dates') < decoded.index('## Existing operational calendar') < decoded.index('## Decisions requested')
    for row in export_model['calendar_context']:
        fields = row['values']['fields']
        assert '### Calendar row ' + row['id'] in decoded
        assert 'Source row: ' + row['source_business_id'] in decoded
        assert 'Native action: ' + fields['action'] in decoded
        assert 'Existing operational date: ' + fields['existing_due_date'] in decoded
        assert 'Operational status: ' + fields['operational_status'] in decoded
        assert 'Required reviewer: ' + fields['required_reviewer'] in decoded
        assert 'Evidence: ' + ';'.join(row['evidence_ids']) in decoded
    assert 'System: ALL' in decoded and 'Source review path: legal' in decoded
    assert 'do not establish approval or completion' in decoded
    events = Calendar.from_ical((tmp_path / 'action-calendar.ics').read_bytes()).walk('VEVENT')
    assert len(events) == 2 and all(str(event['SUMMARY']) != 'Original source task' for event in events)
    assert validate_artifacts(tmp_path, export_model)


def test_brief_calendar_preserves_invalid_native_values_and_missing_fields(export_model, tmp_path):
    row = export_model['calendar_context'][0]
    row['values']['fields'] = dict(action='Undated source task')
    row['values']['raw']['cells'] = ['date pending', 'approved', 'source-owner']
    raw = write_artifacts(tmp_path, export_model)['compliance-brief.md']
    decoded = unescape(raw.decode('utf-8'))
    assert 'Source date text: date pending' in decoded
    assert 'Source status text: approved' in decoded
    assert 'Source review path: source-owner' in decoded
    assert 'Operational status: Not established' in decoded and 'Required reviewer: Not established' in decoded
    assert validate_artifacts(tmp_path, export_model)


def test_brief_empty_operational_calendar_is_explicit(export_model, tmp_path):
    export_model['calendar_context'] = []
    raw = write_artifacts(tmp_path, export_model)['compliance-brief.md']
    assert '## Existing operational calendar' in raw.decode('utf-8')
    assert 'No retained operational calendar rows.' in raw.decode('utf-8')
    assert validate_artifacts(tmp_path, export_model)


def unresolved_row(identity, *, rule_id=None, state='unresolved', reason='Candidate omitted; current coverage remains unresolved'):
    return dict(impact_id='impact:v1:coverage-'+identity, system_id='學習系統', rule_id=rule_id,
        rule_basis=None, basis_type='binding-legal', state=state, scope=None,
        summary='Unresolved source coverage: '+identity, evidence_ids=['evidence-two'],
        source_basis=['captured-source-coverage'], source_versions=[], reason=reason, owner=None,
        resolution_need='Legal and system owner must establish the missing scoped assessment',
        blocker_ids=['authority-blocker'] if identity=='authority' else [],
        identity_key=dict(distinguishing_scope='unbound-candidate-scope'), semantic_basis=dict(kind=identity))


def test_csv_union_preserves_omitted_and_authority_blocked_coverage_without_invention(export_model, tmp_path):
    missing = unresolved_row('omitted')
    blocked = unresolved_row('authority', reason='Authority basis remains blocked; no established rule version')
    export_model['unresolved_coverage'] = [missing, blocked]
    raw = write_artifacts(tmp_path, export_model)['impact-register.csv']
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8'), newline='')))
    assert len(rows) == len(export_model['impacts']) + 2
    indexed = {row['impact_id']: row for row in rows}
    assert set(indexed) == {row['impact_id'] for row in export_model['impacts'] + export_model['unresolved_coverage']}
    for item in (missing, blocked):
        row = indexed[item['impact_id']]
        assert row['state'] == 'unresolved' and row['reason'] == item['reason']
        assert row['approval_status'] == 'pending' and row['resolution_need']
        for field in ('rule_ref', 'proposed_action', 'proposed_due_date', 'action_ids', 'owner', 'source_versions'):
            assert row[field] == ''
    assert validate_artifacts(tmp_path, export_model)


def test_brief_unresolved_coverage_ids_withheld_rules_and_real_rule_context(export_model, tmp_path):
    withheld = unresolved_row('authority', state='conflicting', reason='Conflicting authority prevents a rule conclusion')
    known = unresolved_row('scope', rule_id='rule-record')
    known['scope'] = 'learner chat'
    export_model['unresolved_coverage'] = [withheld, known]
    raw = write_artifacts(tmp_path, export_model)['compliance-brief.md']
    decoded = unescape(raw.decode('utf-8'))
    section = decoded.split('## Unresolved scope', 1)[1].split('## Proposed actions and dates', 1)[0]
    for item in (withheld, known):
        assert '### Unresolved item '+item['impact_id'] in section
        assert 'State: '+item['state'] in section and item['reason'] in section
    assert 'Rule: Not established; Legal review required' in section
    assert 'Scope: Not established; scope review required' in section
    assert 'Rule: rule:v1:legal-meaning' in section and 'Scope: learner chat' in section
    assert validate_artifacts(tmp_path, export_model)


def test_empty_accepted_impacts_still_exports_coverage_and_empty_calendar(export_model, tmp_path):
    export_model.update(impacts=[], actions=[], review_requests=[], unresolved_coverage=[unresolved_row('authority')], status='blocked')
    raw = write_artifacts(tmp_path, export_model)
    rows = list(csv.DictReader(io.StringIO(raw['impact-register.csv'].decode('utf-8'), newline='')))
    assert len(rows) == 1 and rows[0]['approval_status'] == 'pending'
    section = unescape(raw['compliance-brief.md'].decode('utf-8')).split('## Unresolved scope', 1)[1].split('## Proposed actions and dates', 1)[0]
    assert '### Unresolved item ' in section and 'None recorded.' not in section
    assert Calendar.from_ical(raw['action-calendar.ics']).walk('VEVENT') == []
    assert validate_artifacts(tmp_path, export_model)


def test_calendar_all_day_exclusive_end_tentative_stable_uid(export_model, tmp_path):
    raw = write_artifacts(tmp_path, export_model)['action-calendar.ics']
    events = Calendar.from_ical(raw).walk('VEVENT')
    assert len(events) == 2
    for event, action in zip(events, export_model['actions']):
        assert str(event['UID']) == action['action_id'] + '@regulatory-change-impact-brief'
        assert event['DTSTART'].params['VALUE'] == 'DATE'
        assert type(event.decoded('DTSTART')) is date
        assert event.decoded('DTEND').toordinal() == event.decoded('DTSTART').toordinal() + 1
        assert str(event['STATUS']) == 'TENTATIVE'
        for label in ('Action:', 'System:', 'Responsible role:', 'Source/decision basis:', 'Date basis:', 'Approval:', 'Run:', 'Evidence:'):
            assert label in str(event['DESCRIPTION'])
    export_model['run_id'] = 'run-next'
    export_model['actions'][0]['proposed_due_date'] = '2026-09-03'
    updated = calendar.render(export_model)
    assert [str(e['UID']) for e in Calendar.from_ical(updated).walk('VEVENT')] == [str(e['UID']) for e in events]
    assert validate_artifacts(tmp_path, {**export_model, 'run_id':'run-renderer-fixture',
        'actions': [{**export_model['actions'][0], 'proposed_due_date':'2026-09-01'}, *export_model['actions'][1:]]})


@pytest.mark.parametrize('actions', [[], 'undated'])
def test_empty_calendar_is_valid_and_undated_excluded(export_model, tmp_path, actions):
    export_model['actions'] = [] if actions == [] else [export_model['actions'][-1]]
    raw = write_artifacts(tmp_path, export_model)['action-calendar.ics']
    parsed = Calendar.from_ical(raw)
    assert parsed['VERSION'] == '2.0' and parsed['PRODID']
    assert parsed.walk('VEVENT') == []
    assert raw.startswith(b'BEGIN:VCALENDAR\r\n') and raw.endswith(b'END:VCALENDAR\r\n')
    assert validate_artifacts(tmp_path, export_model)


def test_calendar_unicode_escaping_utf8_folding_and_crlf(export_model, tmp_path):
    summary = ('學習資料 é; comma, backslash\\ and newline\n' * 20)
    export_model['actions'][0]['summary'] = summary
    raw = write_artifacts(tmp_path, export_model)['action-calendar.ics']
    assert all(len(line) <= 75 for line in raw.split(b'\r\n'))
    assert b'\n' not in raw.replace(b'\r\n', b'')
    assert b'\r\n ' in raw
    assert str(Calendar.from_ical(raw).walk('VEVENT')[0]['SUMMARY']) == summary
    assert validate_artifacts(tmp_path, export_model)
