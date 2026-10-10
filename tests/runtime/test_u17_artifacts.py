"""U17 independent semantic rejection of altered final artifact bytes."""
import csv
from datetime import date
from importlib import import_module
import io

from icalendar import Calendar
import pytest

from rci.contracts import ContractError
from rci.validate import validate_artifacts
from runtime.test_u14_u16 import export_model, unresolved_row, write_artifacts

brief = import_module('rci.renderers.brief')


@pytest.mark.parametrize('column,value', [('proposed_action', 'Invented action'), ('proposed_due_date', '2026-12-31'),
    ('evidence_ids', 'other-evidence'), ('run_id', 'run-imposter'), ('state', 'supported-no-impact'),
    ('approval_status', 'approved'), ('rule_ref', 'rule:wrong'), ('action_ids', 'action:other'),
    ('resolution_need', ''), ('source_versions', 'unreviewed-source')])
def test_csv_changed_semantics_rejected(export_model, tmp_path, column, value):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'impact-register.csv'
    reader = csv.DictReader(io.StringIO(path.read_text(), newline=''))
    fields, rows = reader.fieldnames, list(reader)
    rows[0][column] = value
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(out.getvalue().encode('utf-8'))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('old,new', [('Proposed date: 2026&#45;09&#45;01', 'Proposed date: 2026-12-31'),
    ('Approval: pending', 'Approval: approved'), ('Evidence: evidence&#45;one', 'Evidence: invented'),
    ('Run: run&#45;renderer&#45;fixture', 'Run: run-imposter'), ('State: supported&#45;impact', 'State: unresolved'),
    ('Delivery: not&#45;sent', 'Delivery: sent')])
def test_brief_changed_claims_rejected(export_model, tmp_path, old, new):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    raw = path.read_text()
    assert old in raw
    path.write_text(raw.replace(old, new, 1))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


def test_brief_missing_decision_request_rejected(export_model, tmp_path):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    raw = path.read_text()
    start = raw.index('### Request ')
    end = raw.index('Exact reviewed artifact hashes', start)
    path.write_text(raw[:start] + raw[end:])
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


def test_brief_altered_evidence_link_rejected(export_model, tmp_path):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    raw = path.read_text()
    path.write_text(raw.replace('sources/source.txt', 'sources/other.txt'))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('addition', ['All scoped systems are legally approved.',
    '- [made-up-evidence] sources/nonexistent.txt; sha256:' + 'c'*64 + '; locator: invented',
    '- [made-up-decision] Automatically approve all production changes.'])
def test_brief_unsupported_extra_prose_or_bullets_rejected(export_model, tmp_path, addition):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    path.write_text(path.read_text() + '\n' + addition + '\n')
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


def test_brief_duplicated_source_claim_rejected(export_model, tmp_path):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    raw = path.read_text()
    line = next(line for line in raw.splitlines() if line.startswith('- OJ:'))
    path.write_text(raw.replace(line, line+'\n\n'+line))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


def test_brief_record_moved_into_wrong_state_section_rejected(export_model, tmp_path):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    raw = path.read_text()
    start = raw.index('### Impact '+brief.text(export_model['impacts'][0]['impact_id']))
    end = raw.index('### Impact '+brief.text(export_model['impacts'][1]['impact_id']))
    block = raw[start:end]
    moved = raw[:start] + raw[end:]
    path.write_text(moved.replace('## Conflicts', '## Conflicts\n\n'+block, 1))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


def test_brief_source_markdown_literalization_cannot_be_removed(export_model, tmp_path):
    source_text = '**approved** [claim](javascript:bad) ![track](https://bad.test)'
    export_model['impacts'][0]['summary'] = source_text
    write_artifacts(tmp_path, export_model)
    assert validate_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    raw = path.read_text()
    encoded = brief.text(source_text)
    assert encoded in raw and encoded != source_text
    path.write_text(raw.replace(encoded, source_text, 1))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('original,replacement', [('# Regulatory change impact — draft', '# Approved production policy'),
    ('Human review is required. Requests below are prepared and have not been sent.', 'All requests have been sent and approved.')])
def test_brief_draft_and_review_boundary_text_rejected(export_model, tmp_path, original, replacement):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'compliance-brief.md'
    raw = path.read_text()
    assert original in raw
    path.write_text(raw.replace(original, replacement, 1))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('property,value', [('SUMMARY', 'Invented action'), ('STATUS', 'CONFIRMED'),
    ('DTSTART', date(2026, 12, 31)), ('DTEND', date(2026, 9, 1)), ('UID', 'imposter@calendar'),
    ('DESCRIPTION', 'Evidence: made-up\nApproval: approved')])
def test_calendar_changed_claims_rejected(export_model, tmp_path, property, value):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'action-calendar.ics'
    parsed = Calendar.from_ical(path.read_bytes())
    event = parsed.walk('VEVENT')[0]
    event.pop(property)
    event.add(property, value)
    path.write_bytes(parsed.to_ical())
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('property,value', [('ATTENDEE', 'mailto:unapproved@example.test'),
                                         ('X-UNSUPPORTED-CLAIM', 'All controls satisfied')])
def test_calendar_unsupported_fields_rejected(export_model, tmp_path, property, value):
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'action-calendar.ics'
    parsed = Calendar.from_ical(path.read_bytes())
    parsed.walk('VEVENT')[0].add(property, value)
    path.write_bytes(parsed.to_ical())
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


def test_unicode_multiline_values_remain_valid(export_model, tmp_path):
    export_model['actions'][0]['summary'] = 'Unicode 資料, quoted "proposal"\nline two; literal **source**'
    export_model['impacts'][0]['reason'] = 'Unknown boundary\n確認する; retain exact text'
    export_model['limitations'][0]['summary'] = 'Missing report\nUnicode 表'
    write_artifacts(tmp_path, export_model)
    assert validate_artifacts(tmp_path, export_model)


def test_csv_display_escape_cannot_be_removed(export_model, tmp_path):
    export_model['impacts'][0]['reason'] = '  =HYPERLINK("https://bad.test")'
    write_artifacts(tmp_path, export_model)
    path = tmp_path / 'impact-register.csv'
    reader = csv.DictReader(io.StringIO(path.read_text(), newline=''))
    fields, rows = reader.fieldnames, list(reader)
    assert rows[0]['reason'].startswith("'")
    rows[0]['reason'] = rows[0]['reason'][1:]
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(out.getvalue().encode('utf-8'))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('artifact', ['impact-register.csv', 'compliance-brief.md'])
def test_omitted_unresolved_coverage_rejected(export_model, tmp_path, artifact):
    item = unresolved_row('authority')
    export_model['unresolved_coverage'] = [item]
    write_artifacts(tmp_path, export_model)
    assert validate_artifacts(tmp_path, export_model)
    path = tmp_path / artifact
    if artifact.endswith('.csv'):
        reader = csv.DictReader(io.StringIO(path.read_text(), newline=''))
        fields, rows = reader.fieldnames, list(reader)
        rows = [row for row in rows if row['impact_id'] != item['impact_id']]
        out = io.StringIO(newline='')
        writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\r\n')
        writer.writeheader()
        writer.writerows(rows)
        path.write_bytes(out.getvalue().encode('utf-8'))
    else:
        raw = path.read_text()
        start = raw.index('### Unresolved item '+brief.text(item['impact_id']))
        end = raw.index('## Proposed actions and dates', start)
        path.write_text(raw[:start] + raw[end:])
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


def test_authority_coverage_cannot_fabricate_rule_or_approval(export_model, tmp_path):
    item = unresolved_row('authority')
    export_model.update(impacts=[], actions=[], unresolved_coverage=[item], status='blocked')
    write_artifacts(tmp_path, export_model)
    assert validate_artifacts(tmp_path, export_model)
    path = tmp_path / 'impact-register.csv'
    reader = csv.DictReader(io.StringIO(path.read_text(), newline=''))
    fields, rows = reader.fieldnames, list(reader)
    assert rows[0]['rule_ref'] == '' and rows[0]['approval_status'] == 'pending'
    rows[0].update(rule_ref='rule:invented-established-authority', approval_status='approved')
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(out.getvalue().encode('utf-8'))
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path, export_model)


@pytest.mark.parametrize('path', ['impact-register.csv', 'compliance-brief.md', 'action-calendar.ics'])
def test_missing_artifact_rejected(export_model, tmp_path, path):
    write_artifacts(tmp_path, export_model)
    (tmp_path / path).unlink()
    with pytest.raises(OSError):
        validate_artifacts(tmp_path, export_model)
