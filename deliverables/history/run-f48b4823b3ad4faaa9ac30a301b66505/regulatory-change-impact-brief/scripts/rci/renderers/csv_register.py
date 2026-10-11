"""UTF-8 CSV with reversible, explicit spreadsheet display escaping."""
import csv
import io

COLUMNS = ['impact_id', 'system_id', 'rule_ref', 'state', 'evidence_ids', 'reason',
           'owner', 'proposed_action', 'proposed_due_date', 'approval_status',
           'run_id', 'assigned_review_date', 'action_ids', 'resolution_need',
           'basis_type', 'source_versions']


def display(value):
    value = str(value) if value is not None else ''
    # Also escape leading apostrophes so decoding is unambiguous.
    unsafe = (value.startswith(("'", '\t', '\r', '\n')) or
              value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')))
    return "'" + value if unsafe else value


def render(model):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator='\r\n')
    writer.writeheader()
    rules = {r['id']: r for r in model['rules']}
    for impact in sorted(model['impacts'], key=lambda r: r['impact_id']):
        actions = sorted((a for a in model['actions'] if impact['id'] in a['impact_ids']), key=lambda a:a['action_id'])
        rule = rules[impact['rule_id']]
        row = dict(impact_id=impact['impact_id'], system_id=impact['system_id'],
            rule_ref=rule['rule_version_id'], state=impact['state'],
            evidence_ids=';'.join(impact['evidence_ids']), reason=impact['reason'], owner=impact['owner'],
            proposed_action=';'.join(a['summary'] for a in actions),
            proposed_due_date=';'.join(a['proposed_due_date'] or '' for a in actions),
            approval_status=';'.join(a['approval_status'] for a in actions) if actions else 'not-required',
            run_id=model['run_id'], assigned_review_date=model['assigned_review_date'],
            action_ids=';'.join(a['action_id'] for a in actions),
            resolution_need=impact['resolution_need'] or ('No action required for this supported scope.' if not actions else ';'.join(a['date_basis'] for a in actions)),
            basis_type=impact['basis_type'], source_versions=';'.join(rule.get('source_versions', [rule['rule_version_id']])))
        writer.writerow({k:display(v) for k,v in row.items()})
    for item in sorted(model.get('unresolved_coverage', []), key=lambda r: r['impact_id']):
        rule = rules.get(item.get('rule_id'))
        row = dict(impact_id=item['impact_id'], system_id=item['system_id'],
            rule_ref=rule['rule_version_id'] if rule else '', state=item['state'],
            evidence_ids=';'.join(item['evidence_ids']), reason=item['reason'], owner=item['owner'],
            proposed_action='', proposed_due_date='', approval_status='pending',
            run_id=model['run_id'], assigned_review_date=model['assigned_review_date'], action_ids='',
            resolution_need=item['resolution_need'], basis_type=item['basis_type'],
            source_versions=';'.join(item['source_versions']))
        writer.writerow({k:display(v) for k,v in row.items()})
    return stream.getvalue().encode('utf-8')
