"""Read-only final package inspection; no acquisition, rendering, or approval.

Run with the pinned Python environment. The output is a mechanical inspection
record, not a legal assessment. --basis identifies live versus synthetic input.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html import unescape
import io
import json
from pathlib import Path
import sys

from icalendar import Calendar
from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'regulatory-change-impact-brief/scripts'))
from rci.contracts import SNAPSHOT_PATHS
from rci.snapshots import stage_records
from rci.validate import validate_package


def digest(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(root, basis):
    schema = json.loads((REPO / 'snapshot.schema.json').read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    chain = [json.loads((root / p).read_text()) for p in SNAPSHOT_PATHS]
    upstream = set()
    for index, snapshot in enumerate(chain):
        validator.validate(snapshot)
        assert snapshot['run_id'] == chain[0]['run_id']
        records = stage_records(snapshot)
        ids = {r['id'] for r in records}
        assert len(ids) == len(records) and not ids & upstream
        assert set(snapshot['consumed_record_ids']) <= upstream
        assert set(snapshot['produced_record_ids']) <= ids
        assert all(r['summary'].strip() and isinstance(r['evidence_ids'], list) for r in records)
        if index:
            assert snapshot['predecessor']['sha256'] == digest(root / SNAPSHOT_PATHS[index - 1])
            assert snapshot['predecessor']['snapshot_id'] == chain[index - 1]['snapshot_id']
        upstream.update(ids)
    captures = chain[1]['state']['captures']
    for capture in captures:
        assert digest(root / capture['local_reference']) == capture['content_hash']
    final = chain[6]['state']
    hashes = {a['path']: digest(root / a['path']) for a in final['artifacts']}
    assert len(hashes) == 3
    assert all(hashes[a['path']] == a['sha256'] for a in final['artifacts'])
    model = chain[5]['state']['export_model']
    requests = {r['request_id']: r for r in model['review_requests']}
    bindings = final['review_bindings']
    assert len(bindings) == len(requests)
    assert {b['request_id'] for b in bindings} == set(requests)
    for binding in bindings:
        assert {a['path']: a['sha256'] for a in binding['artifacts']} == hashes
    brief = unescape((root / 'compliance-brief.md').read_text())
    assert all(r['request_id'] in brief and r['delivery_status'] == 'not-sent' for r in requests.values())
    assert 'snapshots/07-publication-validation.json' in brief
    assert hashes['compliance-brief.md'] not in brief
    reader = csv.DictReader(io.StringIO((root / 'impact-register.csv').read_bytes().decode('utf-8')))
    rows = list(reader)
    required = {'impact_id','system_id','rule_ref','state','evidence_ids','reason',
                'owner','proposed_action','proposed_due_date','approval_status'}
    assert required <= set(reader.fieldnames)
    assert len({r['impact_id'] for r in rows}) == len(rows)
    assert len(rows) == len(model['impacts']) + len(model['unresolved_coverage'])
    events = Calendar.from_ical((root / 'action-calendar.ics').read_bytes()).walk('VEVENT')
    for event in events:
        assert str(event['STATUS']) == 'TENTATIVE'
        assert event['DTSTART'].params['VALUE'] == 'DATE'
        if 'DTEND' in event:
            assert event.decoded('DTEND') > event.decoded('DTSTART')
    # Full internal typed, semantic and interpretation reconstruction is separate
    # from the public schema and direct byte/graph/format checks above.
    assert validate_package(root) == chain
    scope = chain[0]['state']['systems_in_scope']
    assert len(scope) == 8
    assert set(scope) == {r['system_id'] for r in model['coverage']}
    attempts = chain[1]['state']['attempts']
    result = dict(
        inspected_at=datetime.now(timezone.utc).isoformat(), verifier='Codex U20 / check-u20.py',
        basis=basis, root=str(root.resolve()), run_id=chain[0]['run_id'],
        schema_sha256=digest(REPO / 'snapshot.schema.json'),
        checker_sha256=digest(Path(__file__)), stage_statuses=[s['status'] for s in chain],
        publication_status=final['publication_status'], snapshots={p:digest(root/p) for p in SNAPSHOT_PATHS},
        artifacts=hashes, captures_checked=len(captures), attempt_count=len(attempts),
        retrieval_start=min(a['started_at'] for a in attempts),
        retrieval_end=max(a['retrieved_at'] for a in attempts),
        assigned_review_date=model['assigned_review_date'], csv_rows=len(rows), calendar_events=len(events),
        system_dispositions={s:[dict(impact_id=r['impact_id'],state=r['state'],rule_ref=r['rule_ref'])
                                for r in rows if r['system_id']==s] for s in scope},
        sources=[{k:s.get(k) for k in ('source_id','retrieval_status','local_reference','content_hash')}
                 for s in chain[1]['state']['sources']],
        requests=[dict(request_id=r['request_id'],question=r['question'],required_reviewer=r['required_reviewer'],
                       subject_ids=r['subject_ids'],source_versions=r['source_versions'],
                       evidence_ids=r['evidence_ids'],delivery_status=r['delivery_status']) for r in requests.values()],
        review_bindings=bindings, mechanical_validation='passed',
        decision_counts=[sum(r.get('record_type') == 'decision' for r in stage_records(s)) for s in chain],
        exported_decision_count=len(model['decisions']),
        meaning_limit='Byte/graph/format agreement does not establish source meaning or legal applicability.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--basis', required=True, choices=['live', 'synthetic'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.package, args.basis)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:result[k] for k in ('run_id','basis','publication_status','csv_rows','calendar_events','mechanical_validation')}))
