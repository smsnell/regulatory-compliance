"""Immutable snapshot serialization, typed graph checks and package acceptance.

No stage orchestration, promotion, source adapter or recovery mechanics live here.
"""
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contracts import (AS_OF, COLLECTIONS, SNAPSHOT_PATHS, STAGES, ContractError,
                        json_bytes, json_values_equal, package_path, parse_json, require, sha256_bytes,
                        validate_schema, verify_file, validate_interpretation, reduce_states)
from .ids import BusinessKey, check_record_id, stable_business_id, rule_version_id, action_rule_basis

INCOMPLETE_MARKER = ".incomplete-replacement.json"
COMPLETION_MARKER = ".completion.json"
ARTIFACT_PATHS = {"impact-register.csv", "compliance-brief.md", "action-calendar.ics"}

# Internal graph edges. Source/system/business IDs have separate namespaces.
# Same-stage relations are permitted only in these typed directions; consumption
# always remains strictly upstream. Stage 02 evidence never masquerades as input.
LINKS = {
    "evidence_ids": ({"evidence"}, True),
    "attempt_ids": ({"attempt"}, True),
    "attempt_id": ({"attempt"}, True),
    "capture_id": ({"capture"}, True),
    "scope_basis_id": ({"scope-basis"}, False),
    "rule_id": ({"rule", "policy-control"}, True),
    "fact_ids": ({"fact", "incident", "conflict", "gap"}, False),
    "impact_ids": ({"impact"}, False),
    "subject_ids": ({"fact", "incident", "conflict", "gap", "impact", "action", "rule",
                     "timing-rule", "policy-control", "review-request", "artifact", "source",
                     "approval", "evidence", "scope-basis", "validation-check"}, True),
    "delivery_evidence_ids": ({"evidence"}, False),
    "feedback_ids": ({"feedback"}, True),
    "condition_evidence_ids": ({"evidence"}, False),
    "derived_from_capture_id": ({"capture"}, True),
}
DIRECT_PROVENANCE = {"scope-basis", "source", "attempt", "capture", "evidence", "mapping",
                     "gap", "blocker", "diagnostic", "decision", "validation-check",
                     "approval", "review-request", "feedback", "artifact"}


def stage_records(snapshot: dict) -> list[dict]:
    result = [r for collection in COLLECTIONS[snapshot['sequence'] - 1]
              for r in snapshot['state'][collection]]
    return result + snapshot['unresolved'] + snapshot['decisions']


def _record_checks(record: dict, snapshot: dict, root: Path) -> None:
    kind, state = record['record_type'], record.get('state')
    require(record['summary'].strip().lower() not in {'tbd', 'todo', 'unknown', 'placeholder'},
            'summary is a placeholder')
    if not record['evidence_ids'] and kind not in DIRECT_PROVENANCE:
        require(state in {'unresolved', 'conflicting'} and bool(record.get('resolution_need')),
                'factual conclusion lacks claim evidence')
    if state in {'unresolved', 'conflicting'} and kind not in {'gap', 'conflict'}:
        require(bool(record.get('source_basis')) and bool(record.get('reason')) and
                'owner' in record and bool(record.get('resolution_need')),
                'uncertainty requires basis/reason/owner/resolution need')
    if kind == 'fact' and state == 'supported':
        require(record['value'] is not None, 'supported fact has unknown value')
    if kind == 'impact':
        require(record['system_id'] in snapshot['_scope'], 'impact outside frozen scope')
        key = BusinessKey(**record['identity_key'])
        require(key.system_id == record['system_id'] and
                record['impact_id'] == stable_business_id('impact', key), 'impact business identity mismatch')
        if state in {'supported-impact', 'supported-no-impact'}:
            require(bool(record['fact_ids']) and bool(record['evidence_ids']),
                    'supported impact/no-impact requires affirmative rule and fact evidence')
    if kind == 'action':
        key = BusinessKey(**record['identity_key'])
        require(key.system_id == record['system_id'] and key.kind == record['action_kind'] and
                key.distinguishing_scope == record['distinguishing_scope'] and
                record['action_id'] == stable_business_id('action', key), 'action business identity mismatch')
        require(record['system_id'] in snapshot['_scope'], 'action outside frozen scope')
        if record['proposed_due_date'] is not None:
            require(bool(record['evidence_ids']), 'proposed date requires evidence')
    if kind in {'rule', 'policy-control'}:
        require(record['rule_version_id'] == rule_version_id(**record['version_key']),
                'rule meaning/version identity mismatch')
        require(record['supersedes_rule_version_id'] != record['rule_version_id'], 'rule supersedes itself')
    if kind == 'timing-rule':
        if record['applicability'] == 'established':
            require(record['precision'] != 'unknown', 'unknown boundary precision is unresolved')
            require(record['precision'] != 'instant' or _known_timezone(record['boundary_timezone']),
                    'unknown intraday boundary is unresolved')
    if kind in {'attempt', 'scope-basis', 'source'}:
        has_content = record['content_hash'] is not None
        require(has_content == (record['local_reference'] is not None), 'content path/hash null mismatch')
        if has_content:
            require(record['local_reference'].startswith('sources/'), 'primary content must be under sources/')
            verify_file(root, record, 'local_reference', 'content_hash')
    if kind == 'attempt':
        require((record['content'] is not None) == (record['content_hash'] is not None), 'content/hash null mismatch')
        require(_instant(record['started_at']) <= _instant(record['retrieved_at']), 'attempt ends before start')
        require(record['content_type_known'] or record['content_type'] == 'application/octet-stream',
                'unknown MIME must be explicit')
        if record['retrieval_status'] == 'retrieved':
            require(record['content'] is not None, 'retrieved attempt obtained no content')
    if kind == 'scope-basis':
        require(record['system_ids'] == snapshot['_scope'], 'scope basis disagrees with frozen scope')
        if record['basis_kind'] == 'discovered':
            require(record['attempt_key'] is not None and record['retrieved_at'] is not None
                    and record['content_hash'] is not None, 'discovered scope requires original capture provenance')
        else:
            require(record['attempt_key'] is None and record['retrieved_at'] is None,
                    'declared scope must not invent a retrieval')
    if kind == 'capture':
        require(record['local_reference'].startswith('sources/'), 'capture outside sources/')
        verify_file(root, record, 'local_reference', 'content_hash')
    if kind == 'evidence':
        require(not record['evidence_ids'], 'primary claim evidence cannot recursively support itself')
        verify_file(root, record, 'local_reference', 'content_hash')
    if kind == 'review-request':
        require(record['run_id'] == snapshot['run_id'], 'cross-run review request')
        require(record['delivery_status'] != 'sent' or bool(record['delivery_evidence_ids']),
                'sent request lacks actual delivery evidence')
        require(set(record['subject_system_ids']) <= set(snapshot['_scope']), 'request outside scope')
    if kind == 'feedback':
        require(record['match_status'] != 'matched' or (record['subject_ids'] and
                record['request_id'] and record['authentication'] == 'verified'),
                'matched feedback requires authenticated resolved subject/request')
        require(bool(record['reasons'] or record['conditions']), 'feedback requires reasons or conditions')
        require(record['authentication'] != 'verified' or bool(record['authentication_basis']),
                'authentication lacks trusted channel basis')
        require(record['match_status'] != 'matched' or
                ('reviewed_draft' in record and 'revalidation' in record),
                'matched feedback requires retained reviewed draft and revalidation')
    if kind == 'artifact':
        require(record['path'] in ARTIFACT_PATHS, 'unexpected final artifact path')
        verify_file(root, record)


def _instant(value: str):
    from datetime import datetime, timedelta
    leap = value[17:19] == '60'
    checked = value[:17] + ('59' if leap else value[17:19]) + value[19:]
    return datetime.fromisoformat(checked.upper().replace('Z', '+00:00')) + timedelta(seconds=int(leap))


def _known_timezone(value: str | None) -> bool:
    if value == 'UTC':
        return True
    if value is None or value == '-00:00':  # RFC3339 unknown local offset
        return False
    if re.fullmatch(r'[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
        return True
    # Reject ambiguous abbreviations and unknown labels. Never infer the host zone.
    if '/' not in value:
        return False
    try:
        ZoneInfo(value)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def _subject_systems(record: dict, index: dict, seen=None) -> set[str]:
    seen = set() if seen is None else seen
    if record['id'] in seen:
        return set()
    seen.add(record['id'])
    systems = set(record.get('system_ids', []))
    if 'system_id' in record:
        systems.add(record['system_id'])
    for identity in record.get('subject_ids', []):
        systems.update(_subject_systems(index[identity][1], index, seen))
    return systems


def _reviewed_request(feedback, root, current_run):
    """Verify retained review context bytes, without applying historical feedback.

    This checks the snapshot chain and the reviewed request/artifact bindings.
    Full historical business validation and archive creation remain U17/U18 work.
    """
    reference = feedback['reviewed_draft']
    require(feedback['claimed_run_id'] != current_run and
            reference['root'] == 'history/' + str(feedback['claimed_run_id']),
            'reviewed draft must identify a retained prior run')
    archive = package_path(root, reference['root'])
    require(not ((archive / INCOMPLETE_MARKER).exists() or (archive / INCOMPLETE_MARKER).is_symlink()),
            'incomplete reviewed draft')
    chain, records = [], {}
    previous_raw = None
    for i, path in enumerate(SNAPSHOT_PATHS):
        file = package_path(archive, path)
        require(file.is_file(), 'missing reviewed snapshot')
        raw = file.read_bytes()
        if i in (5, 6):
            pointer = reference['stage06' if i == 5 else 'stage07']
            require(pointer['path'] == path and pointer['sha256'] == sha256_bytes(raw),
                    'reviewed snapshot path/hash mismatch')
        prior = parse_json(raw); validate_schema(prior)
        require(prior['run_id'] == feedback['claimed_run_id'] and prior['sequence'] == i + 1 and
                prior['stage'] == STAGES[i], 'reviewed snapshot run/stage mismatch')
        if i in (5, 6):
            require(pointer['snapshot_id'] == prior['snapshot_id'], 'reviewed snapshot identity mismatch')
        expected = None if i == 0 else {'snapshot_id':chain[-1]['snapshot_id'],
                    'path':SNAPSHOT_PATHS[i-1],'sha256':sha256_bytes(previous_raw)}
        require(prior['predecessor'] == expected, 'reviewed predecessor mismatch')
        require(set(prior['consumed_record_ids']) <= set(records), 'reviewed consumption is not upstream')
        produced = stage_records(prior)
        require(len({r['id'] for r in produced}) == len(produced) and
                set(prior['produced_record_ids']) == {r['id'] for r in produced}, 'reviewed produced identity mismatch')
        for record in produced:
            check_record_id(record['id'], prior['run_id'], i + 1, record['record_type'])
            require(record['id'] not in records, 'duplicate reviewed record')
            records[record['id']] = record
        # Use the same core contract checks for every retained stage. Historical
        # feedback is structurally checked but never recursively reapplied.
        _validate_snapshot(prior, root=archive, upstream=chain, retained_review=True)
        chain.append(prior); previous_raw = raw
    require(len({s['snapshot_id'] for s in chain}) == 7, 'duplicate reviewed snapshot identity')
    final = chain[-1]
    require(final['state']['publication_status'] == 'validated' and
            final['status'] in {'complete','partial'} and
            reduce_states(s['status'] for s in chain) == final['status'], 'reviewed draft is not validated')
    requests = [r for r in stage_records(chain[5]) if r['record_type'] == 'review-request' and
                r['request_id'] == feedback['claimed_request_id']]
    bindings = [b for b in final['state']['review_bindings'] if b['request_id'] == feedback['claimed_request_id']]
    require(len(requests) == len(bindings) == 1, 'missing/ambiguous reviewed request binding')
    request, binding = requests[0], bindings[0]
    require(binding['run_id'] == request['run_id'] == feedback['claimed_run_id'] and
            binding['draft_version'] == request['draft_version'] == feedback['claimed_draft_version'] and
            sorted(request['source_versions']) == sorted(feedback['claimed_source_versions']) and
            set(feedback['claimed_subject_ids']) <= set(request['subject_ids']) and
            feedback['responder_role'] == request['required_reviewer'], 'reviewed version claims disagree')
    pointers = binding['artifacts']
    require(len(pointers) == 3 and {p['path'] for p in pointers} == ARTIFACT_PATHS and
            sorted(pointers, key=lambda p:p['path']) == sorted(feedback['claimed_artifacts'], key=lambda p:p['path']),
            'reviewed artifact claims disagree')
    inventory = {a['path']:a for a in final['state']['artifacts']}
    require(len(inventory) == len(final['state']['artifacts']) == 3 and
            set(inventory) == ARTIFACT_PATHS and not final['state']['missing_artifacts'] and
            bool(final['state']['validation_checks']) and
            all(c['result'] == 'passed' for c in final['state']['validation_checks']), 'invalid reviewed artifact inventory')
    for pointer in pointers:
        require(inventory[pointer['path']]['sha256'] == pointer['sha256'] and
                inventory[pointer['path']]['validation_status'] == 'valid', 'reviewed artifact inventory mismatch')
        verify_file(archive, pointer)
    require(feedback['reviewer_response_at'] is not None and
            _instant(feedback['reviewer_response_at']) >= _instant(final['created_at']), 'feedback predates reviewed draft')
    return records, request


def _review_subject_key(record):
    for field in ('action_id','impact_id','rule_version_id','source_id'):
        if field in record:
            return (record['record_type'], record[field])
    if record['record_type'] == 'fact':
        return ('fact',record['system_id'],record['predicate'])
    if record['record_type'] in {'incident','normalized-row'}:
        return (record['record_type'],record['system_id'],record['source_business_id'])
    if record['record_type'] == 'scope-basis':
        return ('scope-basis',tuple(sorted(record['system_ids'])))
    return None


def _feedback_revalidation(feedback, request, snapshot, upstream, index, root):
    reviewed_records, _ = _reviewed_request(feedback, root, snapshot['run_id'])
    report = feedback['revalidation']
    require(report['current_run_id'] == request['run_id'] == snapshot['run_id'] and
            report['current_request_id'] == request['request_id'] and
            report['current_draft_version'] == request['draft_version'] and
            sorted(report['current_source_versions']) == sorted(request['source_versions']) and
            report['reviewed_stage07_sha256'] == feedback['reviewed_draft']['stage07']['sha256'] and
            request['required_reviewer'] == feedback['responder_role'], 'wrong current revalidation binding')
    pointers = [{'snapshot_id':s['snapshot_id'],'path':SNAPSHOT_PATHS[i],
                 'sha256':sha256_bytes(package_path(root,SNAPSHOT_PATHS[i]).read_bytes())} for i,s in enumerate(upstream)]
    require(report['upstream'] == pointers, 'revalidation loses current input bytes')
    pairs = report['subject_bindings']
    require(len(pairs) == len(feedback['claimed_subject_ids']) == len(feedback['subject_ids']) and
            {p['reviewed_id'] for p in pairs} == set(feedback['claimed_subject_ids']) and
            {p['current_id'] for p in pairs} == set(feedback['subject_ids']) and
            set(feedback['subject_ids']) <= set(request['subject_ids']), 'wrong revalidation subject correspondence')
    for pair in pairs:
        old, current = reviewed_records.get(pair['reviewed_id']), index[pair['current_id']][1]
        require(old is not None and _review_subject_key(old) is not None and
                _review_subject_key(old) == _review_subject_key(current), 'revalidation changes semantic subject')
    for check in report['checks'].values():
        require(check['result'] == 'passed', 'revalidation remains failed/unresolved')
        for identity in check['evidence_ids']:
            require(identity in index and index[identity][0] < snapshot['sequence'] and
                    index[identity][1]['record_type'] == 'evidence' and identity in snapshot['consumed_record_ids'],
                    'revalidation evidence must be consumed current-run evidence')
    require(_instant(feedback['reviewer_response_at']) <= _instant(snapshot['created_at']), 'feedback is from the future')


def _review_checks(records, index, snapshot, upstream, root, *, retained_review=False):
    requests = [r for _, r in index.values() if r['record_type'] == 'review-request']
    request_ids = [r['request_id'] for r in requests]
    require(len(request_ids) == len(set(request_ids)), 'ambiguous review request business identity')
    requests = {r['request_id']: r for r in requests}
    decisions = set()
    for record in records:
        if record['record_type'] == 'approval':
            for subject in record['subject_ids']:
                key = (record['request_id'], subject, record['required_reviewer'])
                require(key not in decisions, 'ambiguous duplicate approval requirement')
                decisions.add(key)
    for record in records:
        kind = record['record_type']
        if kind == 'review-request':
            systems = set().union(*(_subject_systems(index[i][1], index) for i in record['subject_ids']))
            require(systems <= set(record['subject_system_ids']), 'request loses subject system scope')
        if kind == 'feedback':
            if record['match_status'] == 'unresolved':
                require(not record['subject_ids'] and record['request_id'] is None,
                        'unresolved feedback must not assert resolved bindings')
                continue
            request = requests.get(record['request_id'])
            require(request is not None, 'matched feedback has unknown request')
            if not retained_review:
                _feedback_revalidation(record, request, snapshot, upstream, index, root)
        if kind == 'approval':
            request = requests.get(record['request_id'])
            if record['request_id'] is not None:
                require(request is not None and record['required_reviewer'] == request['required_reviewer'] and
                        set(record['subject_ids']) <= set(request['subject_ids']),
                        'approval disagrees with request/subject/reviewer')
            for identity in record['feedback_ids']:
                feedback = index[identity][1]
                require(feedback['request_id'] == record['request_id'] and
                        set(record['subject_ids']) <= set(feedback['subject_ids']) and
                        feedback['responder_role'] == record['required_reviewer'],
                        'approval feedback belongs to another request/subject/reviewer')
            if record['status'] == 'approved':
                require(request is not None and bool(record['feedback_ids']) and all(
                    index[i][1]['authentication'] == 'verified' and index[i][1]['match_status'] == 'matched' and
                    index[i][1]['outcome'] in {'approved', 'conditional'} and
                    (index[i][1]['outcome'] != 'conditional' or index[i][1]['conditions']) and
                    (not index[i][1]['conditions'] or
                     (record.get('conditions_satisfied') is True and record.get('condition_evidence_ids')))
                    for i in record['feedback_ids']), 'approval lacks authenticated matching feedback')


def validate_snapshot(snapshot: dict, *, root: Path, upstream: list[dict]) -> None:
    _validate_snapshot(snapshot, root=root, upstream=upstream)


def _validate_snapshot(snapshot: dict, *, root: Path, upstream: list[dict],
                       retained_review: bool = False) -> None:
    validate_schema(snapshot)
    seq, run = snapshot['sequence'], snapshot['run_id']
    require(len(upstream) == seq - 1, 'snapshot requires immediate full upstream prefix')
    index: dict[str, tuple[int, dict]] = {}
    snapshot_ids = {snapshot['snapshot_id']}
    scope = snapshot['state']['systems_in_scope'] if seq == 1 else upstream[0]['state']['systems_in_scope']
    require(len(scope) == len(set(scope)) == 8, 'scope must identify eight distinct actual systems')
    if seq == 1:
        require(snapshot['predecessor'] is None and not snapshot['consumed_record_ids'], 'Stage 01 has no predecessor/input')
        require(set(snapshot['state']['audiences']) == {'Legal', 'Operations'} and
                len(snapshot['state']['audiences']) == 2, 'scope audience mismatch')
        require(snapshot['state']['as_of'] == AS_OF, 'assigned review date changed')
        require(snapshot['state']['supersedes_run_id'] != run, 'run supersedes itself')
        require(snapshot['state']['supersedes_run_id'] is None or bool(snapshot['state']['change_reason']),
                'superseding run requires reason')
    for expected_seq, prior in enumerate(upstream, 1):
        require(prior['run_id'] == run and prior['sequence'] == expected_seq
                and prior['stage'] == STAGES[expected_seq - 1], 'cross-run/out-of-order upstream')
        require(prior['snapshot_id'] not in snapshot_ids, 'duplicate snapshot identity')
        snapshot_ids.add(prior['snapshot_id'])
        raw = package_path(root, SNAPSHOT_PATHS[expected_seq - 1]).read_bytes()
        require(json_values_equal(parse_json(raw), prior), 'upstream object differs from retained bytes')
        for record in stage_records(prior):
            require(record['id'] not in index, 'duplicate upstream record identity')
            index[record['id']] = (expected_seq, record)
    if seq > 1:
        previous = upstream[-1]
        expected = {'snapshot_id': previous['snapshot_id'], 'path': SNAPSHOT_PATHS[seq - 2],
                    'sha256': sha256_bytes(package_path(root, SNAPSHOT_PATHS[seq - 2]).read_bytes())}
        require(snapshot['predecessor'] == expected, 'wrong immediate predecessor identity/path/bytes')
        require(bool(snapshot['consumed_record_ids']), 'later stage requires upstream consumption')
    for identity in snapshot['consumed_record_ids']:
        require(identity in index and index[identity][0] < seq, 'dangling/current-stage consumed record')
    records = stage_records(snapshot)
    current_ids = [record['id'] for record in records]
    require(len(current_ids) == len(set(current_ids)), 'duplicate produced record identity')
    require(set(current_ids) == set(snapshot['produced_record_ids']), 'produced IDs must enumerate all current records')
    for record in records:
        check_record_id(record['id'], run, seq, record['record_type'])
        require(record['id'] not in index, 'reused record identity')
        index[record['id']] = (seq, record)
    # Pass scope separately without mutating immutable snapshot dictionaries.
    contextual = {**snapshot, '_scope': scope}
    for record in records:
        _record_checks(record, contextual, root)
    for record in records:
        for field, (types, same_stage) in LINKS.items():
            if field not in record:
                continue
            values = record[field] if isinstance(record[field], list) else [record[field]]
            for identity in values:
                require(identity in index and identity != record['id'], 'dangling/self record link: ' + field)
                target_seq, target = index[identity]
                require(target['record_type'] in types, 'wrong record link type: ' + field)
                require(target_seq < seq or same_stage, 'forbidden same-stage record link: ' + field)
                if target_seq < seq:
                    require(identity in snapshot['consumed_record_ids'], 'upstream link missing from consumption: ' + field)
        if record['record_type'] == 'action' and record['approval_status'] == 'approved':
            approvals = [r for _, r in index.values() if r['record_type'] == 'approval'
                         and record['id'] in r['subject_ids']]
            require(any(r['status'] == 'approved' for r in approvals),
                    'approved action lacks an explicit approval record')
            require(all(r['status'] in {'approved', 'not-required'} for r in approvals),
                    'approved action has an unresolved or rejected approval requirement')
        if record['record_type'] == 'impact':
            rule = index[record['rule_id']][1]
            require(record['identity_key']['rule_basis'] == rule['rule_version_id'],
                    'impact identity loses rule version')
            require(record['basis_type'] == rule['basis_type'], 'impact changes authority basis type')
            if rule['record_type'] == 'policy-control':
                require(record['system_id'] in rule['system_ids'], 'impact outside control system scope')
            for identity in record['fact_ids']:
                systems = _subject_systems(index[identity][1], index)
                require(not systems or systems == {record['system_id']}, 'impact fact belongs to another system')
            if record['state'].startswith('supported-'):
                require(rule.get('applicability', 'established') == 'established', 'unsupported rule basis')
                require(all(index[i][1].get('state') == 'supported' for i in record['fact_ids']), 'unsupported factual predicate')
        if record['record_type'] == 'action':
            impacts = [index[i][1] for i in record['impact_ids']]
            require(bool(impacts) and all(i['system_id'] == record['system_id'] for i in impacts),
                    'action impact belongs to another system')
            bases = [index[i['rule_id']][1]['rule_version_id'] for i in impacts]
            require(record['identity_key']['rule_basis'] == action_rule_basis(bases),
                    'action identity loses originating rule bases')
        if record['record_type'] == 'evidence':
            capture = index[record['capture_id']][1]
            require(all(record[k] == capture[k] for k in ('local_reference', 'content_hash')), 'evidence/capture mismatch')
            if capture['content_type'].split(';', 1)[0].strip().lower().startswith('text/'):
                require(record['quoted_support'].encode('utf-8') in verify_file(
                    root, record, 'local_reference', 'content_hash'), 'claim quotation absent from retained text')
        if record['record_type'] == 'capture':
            attempt = index[record['attempt_id']][1]
            if 'derived_from_capture_id' not in record:
                require(record['representation'] == attempt['content'] and all(
                    record[k] == attempt[k] for k in ('local_reference', 'content_hash', 'content_type')),
                    'capture/attempt representation or MIME mismatch')
            else:
                parent = index[record['derived_from_capture_id']][1]
                require(parent['attempt_id'] == record['attempt_id'], 'derived capture changes acquisition attempt')
                require(record['representation'] == 'extract' and
                        package_path(root, record['local_reference']) != package_path(root, parent['local_reference']),
                        'derived representation must retain a separate extract file')
                parent_time = parent.get('derivation', {}).get('processed_at', attempt['retrieved_at'])
                require(_instant(record['derivation']['processed_at']) >= _instant(parent_time),
                        'derivation predates its retained input')
        if record['record_type'] == 'source':
            attempts = [index[i][1] for i in record['attempt_ids']]
            require(all(a['source_id'] == record['source_id'] for a in attempts), 'source/attempt identity mismatch')
            require(any(all(record[k] == a[k] for k in ('retrieved_at','retrieval_status','content_hash','local_reference','content_type','version_metadata'))
                        for a in attempts), 'source summary has no matching original attempt')
    # Reject cycles in same-stage relationships, including subject links.
    edges = {r['id']: [] for r in records}
    for record in records:
        for field in LINKS:
            if field in record:
                values = record[field] if isinstance(record[field], list) else [record[field]]
                edges[record['id']].extend(i for i in values if i in edges)
    visiting, visited = set(), set()
    def visit(identity):
        require(identity not in visiting, 'cyclic current-stage graph')
        if identity in visited:
            return
        visiting.add(identity)
        for target in edges[identity]:
            visit(target)
        visiting.remove(identity)
        visited.add(identity)
    for identity in edges:
        visit(identity)
    _review_checks(records, index, snapshot, upstream, root, retained_review=retained_review)
    # Business identity collisions are errors, never a silent merge.
    for field in ('impact_id', 'action_id', 'request_id', 'rule_version_id'):
        values = [r[field] for r in records if field in r and r['record_type'] not in {'approval', 'feedback'}]
        require(len(values) == len(set(values)), 'colliding business identity: ' + field)
    if seq == 2:
        attempts = snapshot['state']['attempts']
        require(len({a['attempt_key'] for a in attempts}) == len(attempts), 'duplicate imported attempt')
        sources = snapshot['state']['sources']
        require(len({s['source_id'] for s in sources}) == len(sources), 'duplicate source declaration')
        referenced = [i for s in sources for i in s['attempt_ids']]
        require(set(referenced) == {a['id'] for a in attempts} and len(referenced) == len(attempts),
                'attempt omitted/repeated in source inventory')
        captures = snapshot['state']['captures']
        captured_attempts = [c['attempt_id'] for c in captures if 'derived_from_capture_id' not in c]
        require(len(captured_attempts) == len(set(captured_attempts)) and set(captured_attempts) ==
                {a['id'] for a in attempts if a['content'] is not None}, 'obtained content needs exactly one primary capture')
        for basis in upstream[0]['state']['scope_basis']:
            if basis['basis_kind'] == 'discovered':
                matches = [a for a in attempts if a['attempt_key'] == basis['attempt_key']]
                require(len(matches) == 1, 'scope discovery attempt must be imported exactly once')
                attempt = matches[0]
                require(attempt.get('scope_basis_id') == basis['id'] and attempt['source_id'] == 'SYSTEMS'
                        and attempt['identity_check'] == 'verified', 'scope discovery import identity mismatch')
                require(all(attempt[k] == basis[k] for k in ('retrieved_at', 'local_reference', 'content_hash')),
                        'scope discovery original provenance changed')
    if seq == 3 and snapshot['state']['authority_blockers']:
        require(snapshot['status'] in {'blocked', 'failed'}, 'required authority blockers cannot fail open')
    if seq == 5:
        for collection, allowed in [('impacts', {'supported-impact'}), ('unaffected_items', {'supported-no-impact'}),
                                    ('unresolved_items', {'unresolved', 'conflicting'})]:
            require(all(r['state'] in allowed for r in snapshot['state'][collection]), 'impact collection/state mismatch')
    if seq == 7:
        require(snapshot['status'] == reduce_states([s['status'] for s in upstream] + [snapshot['status']]),
                'publication status loses an upstream run outcome')
        state = snapshot['state']
        paths = [a['path'] for a in state['artifacts']]
        require(len(paths) == len(set(paths)), 'duplicate artifact path')
        if state['publication_status'] == 'validated':
            require(snapshot['status'] in {'complete', 'partial'} and set(paths) == ARTIFACT_PATHS
                    and all(a['validation_status'] == 'valid' for a in state['artifacts'])
                    and not state['missing_artifacts'] and bool(state['validation_checks'])
                    and all(c['result'] == 'passed' for c in state['validation_checks']),
                    'validated package requires three real artifacts and passed checks')
        elif state['publication_status'] == 'failed':
            require(snapshot['status'] == 'failed', 'publication/run failure mismatch')
        else:
            require(snapshot['status'] == 'blocked', 'publication/run blocker mismatch')
        require(not set(paths) & {m['path'] for m in state['missing_artifacts']}, 'artifact both present and missing')
        for missing in state['missing_artifacts']:
            require(missing['path'] in ARTIFACT_PATHS and not package_path(root, missing['path']).exists(),
                    'false missing artifact inventory')
        requests = {r['request_id']: r for prior in upstream for r in stage_records(prior)
                    if r['record_type'] == 'review-request'}
        bindings = state['review_bindings']
        require(len(bindings) == len({b['request_id'] for b in bindings}), 'duplicate detached binding')
        if state['publication_status'] == 'validated':
            require({b['request_id'] for b in bindings} == set(requests), 'unbound final review request')
        for binding in bindings:
            request = requests.get(binding['request_id'])
            require(request is not None and binding['run_id'] == run and
                    binding['draft_version'] == request['draft_version'], 'wrong detached review version')
            require(len(binding['artifacts']) == 3 and {p['path'] for p in binding['artifacts']} == ARTIFACT_PATHS,
                    'review binding must cover exact three final artifacts')
            for pointer in binding['artifacts']:
                verify_file(root, pointer)
    bindings = snapshot.get('interpretation_bindings', [])
    require(len({b['request']['path'] for b in bindings}) == len(bindings) and
            len({b['response']['path'] for b in bindings}) == len(bindings), 'duplicate accepted interpretation')
    for binding in bindings:
        for pointer in binding.values():
            require(pointer['path'].startswith('analysis/'), 'interpretation outside analysis/')
            verify_file(root, pointer)
        exchange = validate_interpretation(verify_file(root, binding['request']),
                                           verify_file(root, binding['response']), root=root,
                                           run_id=run, stage=snapshot['stage'], upstream=upstream)
        require(exchange.disposition == 'proposed', 'accepted interpretation binding is unresolved')


def write_snapshot(root: Path, snapshot: dict, *, upstream: list[dict]) -> dict:
    """Validate then serialize/write once. Existing snapshot files are immutable."""
    validate_snapshot(snapshot, root=root, upstream=upstream)
    path = SNAPSHOT_PATHS[snapshot['sequence'] - 1]
    target = package_path(root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json_bytes(snapshot)
    if (root / path).exists() or (root / path).is_symlink():
        raise FileExistsError('immutable snapshot path already exists: ' + path)
    with target.open('xb') as stream:
        stream.write(data)
    return {'snapshot_id': snapshot['snapshot_id'], 'path': path, 'sha256': sha256_bytes(data)}


def read_chain(root: Path, *, count: int = 7) -> list[dict]:
    """Validate a disk prefix. An incomplete marker rejects even with completion."""
    require(1 <= count <= 7, 'invalid stage count')
    require(not ((root / INCOMPLETE_MARKER).exists() or (root / INCOMPLETE_MARKER).is_symlink()), 'incomplete replacement; package rejected')
    snapshots = []
    for path in SNAPSHOT_PATHS[:count]:
        snapshot = parse_json(package_path(root, path).read_bytes())
        validate_snapshot(snapshot, root=root, upstream=snapshots)
        snapshots.append(snapshot)
    return snapshots


def validate_marker(marker: dict, definition: str, root: Path) -> None:
    validate_schema(marker, definition)
    if definition == 'incomplete-marker':
        new, old = marker['new_run_id'], marker['old_run_id']
        require(new != old, 'replacement must use a new run')
        require(marker['candidate']['root'] == '.staging/' + new, 'wrong candidate root')
        package_path(root, marker['candidate']['root'])
        if old is None:
            require(marker['archive'] is None, 'first run has no prior archive')
        else:
            require(marker['archive'] is not None and marker['archive']['root'] == 'history/' + old,
                    'missing verified old archive')
            package_path(root, marker['archive']['root'])
    elif definition == 'completion-marker':
        require(marker['stage07']['path'] == SNAPSHOT_PATHS[-1], 'wrong completion stage')
    else:
        raise ContractError('expected package marker definition')


def accept_package(root: Path) -> list[dict]:
    """U02 acceptance primitive; U17 supplies independent artifact meaning checks."""
    require(not ((root / INCOMPLETE_MARKER).exists() or (root / INCOMPLETE_MARKER).is_symlink()), 'incomplete replacement wins over completion')
    completion = parse_json(package_path(root, COMPLETION_MARKER).read_bytes())
    validate_marker(completion, 'completion-marker', root)
    verify_file(root, completion['stage07'])
    snapshots = read_chain(root)
    final = snapshots[-1]
    require(completion['run_id'] == final['run_id'] and
            completion['stage07']['snapshot_id'] == final['snapshot_id'], 'completion marker identity mismatch')
    require(final['state']['publication_status'] == 'validated', 'package is not validated')
    return snapshots
