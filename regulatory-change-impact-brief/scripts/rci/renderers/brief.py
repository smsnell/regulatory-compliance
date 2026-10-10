"""Mechanical Markdown draft: every observation stays scoped and cited."""
from html import escape


def text(value):
    # HTML entities preserve exact text while preventing source Markdown/HTML injection.
    # Markdown syntax is parsed before entities are decoded. Numeric entities
    # retain readable literal punctuation without allowing links, emphasis,
    # headings, code spans, images or table separators from source content.
    return ''.join('&#'+str(ord(char))+';' if char in '\\`*_[]#!()+-~|\n\r' else escape(char, quote=True)
                   for char in str(value))


def calendar_source_value(row, header):
    raw = row.get('values', {}).get('raw', {})
    headers, cells = raw.get('headers', []), raw.get('cells', [])
    if headers.count(header) != 1:
        return 'Not recorded'
    position = headers.index(header)
    return cells[position] if position < len(cells) else 'Not recorded'


def render(model):
    lines = ['# Regulatory change impact — draft', '',
        f"Run: {text(model['run_id'])}", f"Assigned review date: {text(model['assigned_review_date'])}",
        f"Recipients: {text(';'.join(model['recipients']))}", 'Draft: true',
        f"Run status: {text(model['status'])}", f"Draft version: {text(model['draft_version'])}", '',
        'Human review is required. Requests below are prepared and have not been sent.', '',
        '## Scope', '', text(';'.join(model['systems_in_scope'])), '', '## Source quality', '']
    for s in model['source_quality']:
        lines.append(f"- {text(s['source_id'])}: {text(s['retrieval_status'])}; {text(s['summary'])} [{text(s['id'])}]")
    lines += ['', '## Source limitations', '']
    lines += [f"- {text(r['summary'])} [{text(r['id'])}]; evidence: {text(';'.join(r['evidence_ids']))}; resolution: {text(r.get('resolution_need') or r.get('reason') or 'See retained source assessment.')}" for r in model['limitations']] or ['No additional recorded limitations.']
    if 'source_resolution' in model:
        resolution = model['source_resolution']
        lines += ['', '## Source inspection resolution', '',
            'Original capture diagnostics and historical source statuses remain recorded above.', '',
            '### Capture resolution', '',
            f"Original upstream status: {text(resolution['original_upstream_status'])}",
            f"Effective upstream status: {text(resolution['effective_upstream_status'])}",
            f"Resolved diagnostics: {text(';'.join(resolution['resolved_diagnostic_ids']) or 'None recorded')}",
            f"Unresolved diagnostics: {text(';'.join(resolution['unresolved_diagnostic_ids']) or 'None recorded')}",
            f"Report sources: {text(';'.join(resolution['report_source_ids']) or 'None recorded')}", '']
        for assessment in resolution['legal_assessments']:
            lines += [f"### Legal source assessment {text(assessment['source_id'])}", '',
                f"Source: {text(assessment['source_id'])}",
                f"Resolved diagnostics: {text(';'.join(assessment['diagnostic_ids']))}",
                f"Rules: {text(';'.join(assessment['rule_ids']))}",
                f"Evidence: {text(';'.join(assessment['evidence_ids']))}", '']
        for entry in resolution['report_resolutions']:
            report, support = entry['report'], entry['resolution']
            lines += [f"### Report inspection {text(report['source_id'])}", '',
                f"Source row: {text(report['source_business_id'])}", f"System: {text(report['system_id'])}",
                f"Reference: {text(report['reference'])}", f"Owner: {text(report['owner'] or 'Unresolved; owner confirmation required')}",
                f"Original report result: {text(report['result'])}",
                f"Attempts: {text(';'.join(report['attempt_ids']))}", f"Captures: {text(';'.join(report['capture_ids']))}",
                f"Evidence: {text(';'.join(report['evidence_ids']))}",
                f"Fact candidates: {text(';'.join(map(str, entry['candidate_numbers'])))}",
                f"Declaration candidates: {text(';'.join(map(str, support['declaration_candidate_numbers'])))}",
                f"Scopes: {text(';'.join(support['scopes']))}",
                f"Resolution evidence: {text(';'.join(support['evidence_ids']))}", f"Reason: {text(support['reason'])}", '']
    rules = {r['id']: r for r in model['rules']}
    for title, states in [('Supported observations', {'supported-impact','supported-no-impact'}), ('Conflicts', {'conflicting'}), ('Unresolved scope', {'unresolved'})]:
        lines += ['', '## '+title, '']
        impacts = [r for r in model['impacts'] if r['state'] in states]
        coverage = model.get('unresolved_coverage', []) if title == 'Unresolved scope' else []
        if not impacts and not coverage: lines.append('None recorded.')
        for r in sorted(impacts, key=lambda r:r['impact_id']):
            lines += [f"### Impact {text(r['impact_id'])}", '',
                f"System: {text(r['system_id'])}", f"Scope: {text(r['identity_key']['distinguishing_scope'])}",
                f"Rule: {text(rules[r['rule_id']]['rule_version_id'])}", f"Basis: {text(r['basis_type'])}",
                f"State: {text(r['state'])}", f"Observation: {text(r['summary'])}",
                f"Reason: {text(r['reason'])}", f"Owner: {text(r['owner'] or 'Unresolved; owner confirmation required')}",
                f"Resolution: {text(r['resolution_need'] or 'Supported draft scope; human review pending')}",
                f"Evidence: {text(';'.join(r['evidence_ids']))}", '']
        for item in sorted(coverage, key=lambda r: r['impact_id']):
            rule = rules.get(item.get('rule_id'))
            lines += [f"### Unresolved item {text(item['impact_id'])}", '',
                f"System: {text(item['system_id'])}",
                f"Scope: {text(item.get('scope') or 'Not established; scope review required')}",
                f"Rule: {text(rule['rule_version_id'] if rule else 'Not established; Legal review required')}",
                f"Basis: {text(item['basis_type'])}", f"State: {text(item['state'])}",
                f"Observation: {text(item['summary'])}", f"Reason: {text(item['reason'])}",
                f"Owner: {text(item['owner'] or 'Unresolved; owner confirmation required')}",
                f"Resolution: {text(item['resolution_need'])}",
                f"Evidence: {text(';'.join(item['evidence_ids']))}", '']
    lines += ['', '## Proposed actions and dates', '']
    for a in sorted(model['actions'],key=lambda a:a['action_id']):
        impacts=[r['impact_id'] for r in model['impacts'] if r['id'] in a['impact_ids']]
        lines += [f"### Action {text(a['action_id'])}", '', f"System: {text(a['system_id'])}",
            f"Scope: {text(a['distinguishing_scope'])}", f"Proposal: {text(a['summary'])}",
            f"Owner: {text(a['owner'] or 'Unresolved; owner confirmation required')}",
            f"Proposed date: {text(a['proposed_due_date'] or 'Undated')}",
            f"Existing operational date: {text(a['existing_due_date'] or 'Not established')}",
            f"Date basis: {text(a['date_basis'])}", f"Approval: {text(a['approval_status'])}",
            f"Impacts: {text(';'.join(impacts))}", f"Evidence: {text(';'.join(a['evidence_ids']))}", '']
    if not model['actions']: lines.append('No supportable action proposals recorded.')
    lines += ['', '## Existing operational calendar', '',
        'Source rows retain operational dates, statuses and review paths; they do not establish approval or completion.', '']
    for row in model.get('calendar_context', []):
        fields = row['values']['fields']
        lines += [f"### Calendar row {text(row['id'])}", '',
            f"Source row: {text(row['source_business_id'])}", f"System: {text(row['system_id'])}",
            f"Native action: {text(fields.get('action') or 'Not established')}",
            f"Existing operational date: {text(fields.get('existing_due_date') or 'Not established')}",
            f"Reported owner: {text(fields.get('owner') or 'Not established')}",
            f"Operational status: {text(fields.get('operational_status') or 'Not established')}",
            f"Required reviewer: {text(fields.get('required_reviewer') or 'Not established')}",
            f"Source date text: {text(calendar_source_value(row, 'due_date'))}",
            f"Source status text: {text(calendar_source_value(row, 'status'))}",
            f"Source review path: {text(calendar_source_value(row, 'approval_required'))}",
            f"Evidence: {text(';'.join(row['evidence_ids']))}", '']
    if not model.get('calendar_context'): lines.append('No retained operational calendar rows.')
    lines += ['', '## Decisions requested', '']
    for r in model['review_requests']:
        lines += [f"### Request {text(r['request_id'])}", '', f"Reviewer: {text(r['required_reviewer'])}",
            f"Question: {text(r['question'])}", f"Subjects: {text(';'.join(r['subject_ids']))}",
            f"Source versions: {text(';'.join(r['source_versions']))}",
            f"Delivery: {text(r['delivery_status'])}", f"Evidence: {text(';'.join(r['evidence_ids']))}", '']
    if not model['review_requests']: lines.append('No additional decisions requested.')
    lines += ['', 'Exact reviewed artifact hashes are detached in [Stage 07](snapshots/07-publication-validation.json).', '', '## Engineering decisions', '']
    for d in model['decisions']:
        lines.append(f"- [{text(d['id'])}] {text(d['summary'])}; chosen: {text(d['chosen_behavior'])}; rationale: {text(d['rationale'])}; evidence: {text(';'.join(d['evidence_ids']))}")
    lines += ['', '## Evidence index', '']
    for e in model['evidence_index']:
        lines.append(f"- [{text(e['id'])}] {text(e['local_reference'])}; {text(e['content_hash'])}; locator: {text(e['locator'])}")
    return ('\n\n'.join(lines)+'\n').encode('utf-8')
