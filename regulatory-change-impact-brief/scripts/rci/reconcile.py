"""U10 conservative factual reconciliation, immutable Stage 04 and row accounting.

Reported fields are transcriptions, never verified predicates. Semantic candidates
use the G1 exchange; conflicting assertions survive independently of row order.
Python verifies prerequisites and binding, not the truth of model interpretation.
"""
from collections import defaultdict
from copy import deepcopy
import re
import shutil
import sys
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from .adapters.reports import text_representation
from .contracts import (ASSIGNED_REVIEW_DATE, ContractError, SNAPSHOT_PATHS, json_bytes,
    package_path, parse_json, reduce_states, require, sha256_bytes, validate_interpretation,
    validate_schema)
from .evidence import _read, _write
from .ids import new_record_id, rule_version_id
from .normalize import load_dictionary
from .runtime import (SKILL, Providers, file_inventory, host_command, invoke_host,
    preflight, verify_inventory, visible_usage)
from .snapshots import read_chain, stage_records, write_snapshot

VERSION = 'rci-u10-reconciliation/1'
STAGE = 'evidence-reconciliation'
PREDICATES = ('notice_present', 'notice_before_first_interaction',
    'machine_readable_provenance', 'provider_role', 'deployer_role', 'output_scope',
    'exposed_group', 'human_review_path', 'exception_claim')
REGISTERS = ('SYSTEMS', 'EVIDENCE', 'CALENDAR')
POLICY_BOUNDARY = dict(schema_version='rci-u10-policy-extracts/1',
    value={'boundary':'Captured before Stage 02 freeze; internal policy meaning and activation require U10 assessment'})


def _exact_id(identity, text):
    return re.search(r'(?<![\w-])' + re.escape(identity) + r'(?![\w-])', text) is not None


def _schema(value, name):
    schema = parse_json((SKILL / ('references/schemas/' + name + '.schema.json')).read_bytes())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value))
    require(not errors, 'invalid U10 ' + name + ': ' + (errors[0].message if errors else ''))


def project_policy(store, *, persist=False, retained_captures=()):
    """Capture/recheck POLICY text only in a new Stage 02, never amend a snapshot."""
    captures, evidence = [], []
    for event in store.inventory():
        attempt, parent = event['attempt'], event['capture']
        if attempt['source_id'] != 'POLICY':
            continue
        text = text_representation(store, event)
        if text is None:
            continue
        capture = parent
        if parent['content_type'].split(';')[0].strip().lower() == 'text/html':
            path = 'sources/' + attempt['attempt_key'] + '.policy.txt'
            if persist:
                _write(store.root, path, text.encode('utf-8'))
                capture = dict(id=new_record_id(store.run_id, 2, 'capture'), record_type='capture',
                    summary='Derived internal policy text; activation and scope unverified', evidence_ids=[],
                    attempt_id=parent['attempt_id'], representation='extract', local_reference=path,
                    content_hash=sha256_bytes(text.encode('utf-8')), content_type='text/plain',
                    derived_from_capture_id=parent['id'],
                    derivation=dict(method='HTMLParser visible text (no scripts/styles)', processed_at=store.providers.now()),
                    representation_metadata=dict(method='HTMLParser visible text (no scripts/styles)',
                        locator='whole visible policy body', permission='Disclosed internal policy source retention'))
            else:
                matches = [c for c in retained_captures if c.get('derived_from_capture_id') == parent['id']]
                require(len(matches) == 1, 'missing or duplicated policy derivation')
                capture = deepcopy(matches[0])
                require(capture['local_reference'] == path and capture['content_hash'] == sha256_bytes(text.encode())
                    and capture['content_type'] == 'text/plain' and
                    capture['derivation']['method'] == 'HTMLParser visible text (no scripts/styles)' and
                    _read(store.root, path) == text.encode(), 'policy derivation differs from original')
            validate_schema(capture, 'capture')
            captures.append(capture)
        claim = dict(id=new_record_id(store.run_id, 2, 'evidence'), record_type='evidence',
            summary='Captured internal policy body; applicability requires assessment', evidence_ids=[],
            capture_id=capture['id'], local_reference=capture['local_reference'], content_hash=capture['content_hash'],
            locator=dict(kind='extract', value='whole visible POLICY body; quote locates paragraph'),
            assertion='Captured internal policy body', quoted_support=text)
        validate_schema(claim, 'evidence')
        evidence.append(claim)
    return dict(captures=captures, evidence=evidence)


def _chain(store):
    from .authority import validate_authority
    third = validate_authority(store)
    chain = read_chain(store.root, count=2) + [third]
    require(chain[0]['run_id'] == store.run_id, 'wrong reconciliation run')
    return chain


def create_reconciliation_request(store, metadata):
    """Dedicated packet path preserves the prerequisite authority exchange bytes."""
    chain = _chain(store)
    second = chain[1]['state']
    eligible = {i for r in second.get('extensions', {}).get('u08_reports', {}).get('value', {}).get('reports', [])
                for i in r['evidence_ids']}
    eligible.update(e['id'] for e in second['evidence'] if
        e['assertion'].startswith('Captured internal policy body') or
        any(e['id'] in r['evidence_ids'] for r in second['normalized_rows']))
    index = {r['id']:r for s in chain for r in stage_records(s)}
    extracts = []
    for eid in sorted(eligible):
        evidence = index[eid]; capture = index[evidence['capture_id']]
        require(capture['content_type'].split(';')[0].strip().lower() in {'text/plain','text/csv'},
                'U10 requires readable retained text, not unverified OCR')
        if 'derived_from_capture_id' in capture:
            require(capture['derivation']['method'] == 'HTMLParser visible text (no scripts/styles)',
                    'unsupported U10 derivation')
        text = _read(store.root, evidence['local_reference']).decode('utf-8')
        extracts.append(dict(evidence_id=eid, capture_id=capture['id'], path=evidence['local_reference'],
            sha256=evidence['content_hash'], locator=evidence['locator'], text=text,
            text_sha256=sha256_bytes(text.encode('utf-8'))))
    require(extracts, 'No readable company evidence for reconciliation packet')
    dictionary = load_dictionary()
    request = dict(schema_version='rci-interpretation-request/1', packet_id='packet-' + uuid4().hex,
        run_id=store.run_id, stage=STAGE, created_at=store.providers.now(), assigned_review_date=ASSIGNED_REVIEW_DATE,
        expected_response_schema='rci-interpretation-response/1',
        upstream=[dict(snapshot_id=s['snapshot_id'], sequence=s['sequence'], path=SNAPSHOT_PATHS[s['sequence']-1],
            sha256=sha256_bytes(_read(store.root, SNAPSHOT_PATHS[s['sequence']-1]))) for s in chain],
        extracts=extracts, field_dictionary=dict(version=dictionary['schema_version'], fields=dictionary,
            sha256=sha256_bytes(json_bytes(dictionary))), metadata=deepcopy(metadata))
    validate_schema(request, 'interpretation-request')
    _write(store.root, 'analysis/reconciliation/request.json', json_bytes(request))
    return request


def _assessment(candidate, chain):
    require(len(candidate['conditions']) == 1, 'one U10 typed assessment required')
    descriptor = parse_json(candidate['conditions'][0].encode('utf-8'))
    _schema(descriptor, 'reconciliation-basis')
    require(candidate['role'] == 'unknown' and not candidate['timing_candidates'] and
            not candidate['exception_candidates'], 'U10 uses typed assessment; no implicit roles, deadlines or exceptions')
    index = {r['id']:r for s in chain for r in stage_records(s)}
    citations = {(c['evidence_id'], c['quote']) for c in candidate['citations']}
    evidence = index.get(descriptor['evidence_id'])
    require(evidence is not None and (descriptor['evidence_id'], descriptor['quote']) in citations,
            'U10 assessment lacks an exact cited evidence quote')
    # One assessment has one basis; auxiliary citations cannot hide support from
    # the wrong report/system or add unsupported evidence to a supported record.
    require(citations == {(descriptor['evidence_id'], descriptor['quote'])}, 'U10 assessment requires one explicit basis')
    quote = descriptor['quote']
    capture = index[evidence['capture_id']]; attempt = index[capture['attempt_id']]
    require(descriptor['identity_quote'] in quote, 'identity support absent from assessment quote')
    if descriptor['kind'] == 'fact':
        require(candidate['basis_type'] == 'factual' and len(candidate['system_ids']) == 1,
                'factual assessment requires one system')
        system, = candidate['system_ids']
        require(_exact_id(system, descriptor['identity_quote']), 'report does not identify claimed system')
        reports = chain[1]['state'].get('extensions', {}).get('u08_reports', {}).get('value', {}).get('reports', [])
        require(any(r['system_id'] == system and descriptor['evidence_id'] in r['evidence_ids'] for r in reports),
                'fact support is not a linked report for this system')
        known_owners = {r['owner'] for r in reports if r['system_id'] == system and
                        descriptor['evidence_id'] in r['evidence_ids'] and r['owner'] is not None}
        require(descriptor['owner'] is None or descriptor['owner'] in known_owners or descriptor['owner'] in quote,
                'claimed factual owner lacks captured support')
        require(descriptor['value_quote'] in quote and descriptor['scope'] in quote,
                'factual value/scope lacks quoted support')
        require(descriptor['observed_on'] is None or descriptor['observed_on'] in quote,
                'invented observation date')
        require(descriptor['review_date_quote'] is None or
                (descriptor['review_date_quote'] in quote and ASSIGNED_REVIEW_DATE in descriptor['review_date_quote']),
                'review-date support absent')
        require(descriptor['value'] is None or
                isinstance(descriptor['value'], bool) or descriptor['value'] in descriptor['value_quote'],
                'text value not in value support')
        bool_predicates = set(PREDICATES[:5])
        require(descriptor['predicate'] not in bool_predicates or descriptor['value'] in (True, False, None),
                'boolean factual predicate requires a boolean or unknown')
        require(descriptor['predicate'] in bool_predicates or descriptor['value'] is None or
                isinstance(descriptor['value'], str) and descriptor['value'].strip(),
                'descriptive predicate requires nonempty text or unknown')
        if descriptor['predicate'] == 'machine_readable_provenance':
            require(descriptor['observation_kind'] == 'export-test', 'provenance requires export-test support; visible label is insufficient')
        if descriptor['predicate'] == 'notice_before_first_interaction':
            require(descriptor['observation_kind'] in {'page-capture','interaction-test'}, 'notice timing requires capture/test support')
        return descriptor, attempt
    require(candidate['basis_type'] == 'internal-control' and attempt['source_id'] == 'POLICY' and
            attempt['identity_check'] == 'verified', 'internal controls require identity-verified POLICY evidence')
    require(descriptor['control'] == candidate['summary'] and descriptor['control'] in quote,
            'policy control differs from quoted support')
    require(descriptor['version'] in descriptor['version_quote'] and descriptor['version_quote'] in quote,
            'policy version lacks captured support')
    require(all(date is None or date in quote for date in
            (descriptor['effective_from'], descriptor['effective_until'])), 'policy date not in quote')
    require(descriptor['activation_quote'] in quote, 'policy activation lacks support')
    require(descriptor['scope_quote'] in quote and (descriptor['scope_kind'] == 'all-scoped' and
            _exact_id('ALL',descriptor['scope_quote']) or descriptor['scope_kind'] == 'systems' and
            all(_exact_id(i,descriptor['scope_quote']) for i in candidate['system_ids'])), 'policy scope lacks support')
    if descriptor['scope_kind'] == 'all-scoped':
        require(set(candidate['system_ids']) == set(chain[0]['state']['systems_in_scope']), 'ALL policy scope must cover frozen scope exactly')
    return descriptor, attempt


def _evaluate(store, request_raw, response_raw, chain):
    result = validate_interpretation(request_raw, response_raw, root=store.root,
        run_id=store.run_id, stage=STAGE, upstream=chain)
    assessments, reviews = [], []
    for number, candidate in enumerate(result.response['candidates'], 1):
        descriptor = None
        try:
            require(result.disposition == 'proposed', result.reason or 'unsupported exchange')
            descriptor, attempt = _assessment(candidate, chain)
            assessments.append((number, candidate, descriptor, attempt))
            reason = None
        except (ValueError, KeyError, TypeError) as error:
            reason = str(error)
        reviews.append(dict(number=number, candidate=deepcopy(candidate),
            disposition='accepted-draft-assertion' if reason is None else 'unresolved', reason=reason))
    return result, assessments, reviews


def evaluate(store, request_raw, response_raw):
    return _evaluate(store, request_raw, response_raw, _chain(store))


def submit_reconciliation(store, proposal_bytes):
    directory = 'analysis/reconciliation/exchanges/' + uuid4().hex
    _write(store.root, directory + '/proposal.json', proposal_bytes)
    request_raw = _read(store.root, 'analysis/reconciliation/request.json')
    _write(store.root, directory + '/request.json', request_raw)
    status, reason = 'failed', 'invalid reconciliation proposal'
    try:
        proposal = parse_json(proposal_bytes)
        require(isinstance(proposal, dict) and set(proposal) == {'disposition','diagnostic','candidates'},
                'invalid reconciliation proposal fields')
        request = parse_json(request_raw)
        metadata = deepcopy(request['metadata'])
        metadata.update(reported_model=None, reported_effort=None, usage=None)
        response = dict(**proposal, schema_version='rci-interpretation-response/1',
            run_id=store.run_id, stage=STAGE, packet_id=request['packet_id'], packet_sha256=sha256_bytes(request_raw),
            responded_at=store.providers.now(), metadata=metadata)
        response_raw = json_bytes(response)
        _write(store.root, directory + '/response.json', response_raw)
        result, assessments, reviews = evaluate(store, request_raw, response_raw)
        status = 'proposed' if assessments else 'unresolved'
        reason = result.reason or next((r['reason'] for r in reviews if r['reason']), None)
        pointers = {name:dict(path=directory + '/' + name + '.json', sha256=sha256_bytes(raw))
                    for name, raw in [('request',request_raw),('response',response_raw)]}
        _write(store.root, 'analysis/reconciliation/submission.json', json_bytes(pointers))
        return dict(disposition=status, reason=reason, production_package=False)
    except (ValueError, OSError) as error:
        reason = str(error)
        raise
    finally:
        _write(store.root, directory + '/validation.json', json_bytes(dict(status=status, reason=reason,
            run_id=store.run_id, stage=STAGE, source_evidence=False, semantic_proof=False)))


def _submission(store, chain):
    path = store.root / 'analysis/reconciliation/submission.json'
    if not path.exists():
        return None, None, [], []
    pointers = parse_json(_read(store.root, 'analysis/reconciliation/submission.json'))
    require(isinstance(pointers, dict) and set(pointers) == {'request','response'}, 'invalid reconciliation submission')
    raws = {}
    for name, pointer in pointers.items():
        require(set(pointer) == {'path','sha256'} and pointer['path'].startswith('analysis/reconciliation/exchanges/'),
                'invalid reconciliation analysis pointer')
        raws[name] = _read(store.root, pointer['path'])
        require(sha256_bytes(raws[name]) == pointer['sha256'], 'changed reconciliation analysis bytes')
    require(raws['request'] == _read(store.root, 'analysis/reconciliation/request.json'), 'another reconciliation packet')
    result, assessments, reviews = _evaluate(store, raws['request'], raws['response'], chain)
    return pointers, result, assessments, reviews


def project(store):
    chain = _chain(store)
    first, second, third = chain
    scope = first['state']['systems_in_scope']
    rows = second['state']['normalized_rows']
    sources = {r['source_id']:r for r in second['state']['sources']}
    pointers, result, assessments, reviews = _submission(store, chain)
    state = dict(system_facts=[], policy_controls=[], incident_evidence=[], conflicts=[], evidence_gaps=[])
    accounting = dict(schema_version=VERSION, draft_only=True, assigned_review_date=ASSIGNED_REVIEW_DATE,
        interpretation=pointers, candidate_reviews=reviews, register_rows=[], register_tables=[],
        normalized_rows=[], reports=[], calendar_context=[], systems=[], fact_groups=[], issues=[], policy_context=[])
    groups = defaultdict(list)
    outputs = defaultdict(list)
    owners = defaultdict(set)
    dictionary = load_dictionary()
    for row in rows:
        if row['system_id'] in scope and row['source_id'] == 'SYSTEMS' and row['values']['fields'].get('owner'):
            owners[row['system_id']].add(row['values']['fields']['owner'])

    def owner(system):
        return next(iter(owners[system])) if len(owners[system]) == 1 else 'Operations' if owners[system] else None

    def record(kind, summary, evidence):
        return dict(id=new_record_id(store.run_id, 4, kind), record_type=kind, summary=summary,
                    evidence_ids=sorted(set(evidence)))

    def issue(system, predicate, scope_key, reason, basis, evidence=(), subjects=(), *, conflict=False, known_owner=None):
        kind = 'conflict' if conflict else 'gap'
        need = ('Legal must decide final interpretation/exception; ' if predicate in {'policy','exception_claim'} else '') + \
            'System owner must verify/correct the scoped facts; Operations must resolve operational questions. Preserve all records; no request has been sent.'
        links = list(subjects)
        if conflict and not links:
            links = list(evidence)
            if not links:
                source_id = 'POLICY' if predicate == 'policy' else scope_key.split(':',1)[0]
                require(source_id in sources,'conflict has no retained subject basis')
                links = [sources[source_id]['id']]
        value = dict(record(kind, reason, evidence), source_basis=list(basis), reason=reason,
            owner=known_owner if known_owner is not None else owner(system), resolution_need=need,
            subject_ids=sorted(set(links)), state='conflicting' if conflict else 'unresolved')
        state['conflicts' if conflict else 'evidence_gaps'].append(value)
        accounting['issues'].append(dict(record_id=value['id'], system_id=system, predicate=predicate, scope=scope_key))
        return value['id']

    def assertion(system, predicate, scope_key, value, evidence, basis, origin, known_owner, usable=True, reason=None, observed_on=None, retrieved_at=None):
        groups[(system,predicate,scope_key)].append(dict(value=deepcopy(value), evidence_ids=list(evidence),
            source_basis=list(basis), origin=origin, owner=known_owner, usable=usable, reason=reason,
            observed_on=observed_on, retrieved_at=retrieved_at))

    # Each row retains all raw cells and typed values through its upstream ID.
    # Per-field reported facts do not become verified role/notice predicates.
    for row in rows:
        system, register, fields = row['system_id'], row['source_id'], row['values']['fields']
        basis = [row['id'], row['locator']['value']]
        ev = row['evidence_ids']; known = fields.get('owner')
        outputs[row['id']]  # account even if no semantic values survive
        if system not in scope and not (system == 'ALL' and register == 'CALENDAR'):
            outputs[row['id']].append(issue(system, 'identity', register, 'Register system ID is outside frozen scope; no fuzzy join or scope change',
                basis, ev, known_owner=known))
        if not known:
            outputs[row['id']].append(issue(system, 'owner', register, 'Missing responsible owner', basis, ev))
        if register == 'SYSTEMS':
            for name in (f['field'] for f in dictionary['registers'][register]['fields']):
                value = fields.get(name)
                assertion(system, 'reported.' + name, 'SYSTEMS', value, ev, basis, row['id'], known,
                    usable=value is not None, reason=('Reported value is explicitly unknown' if name in fields else
                        'Missing/invalid reported value') if value is None else None,
                    retrieved_at=row.get('retrieved_at'))
        elif register == 'EVIDENCE':
            raw = row['values']['raw']
            native_status = raw['cells'][raw['headers'].index('status')]
            subjects = []
            if native_status.strip():
                incident = dict(record('incident', 'Source-reported evidence/incident ' + row['source_business_id'], ev),
                    source_business_id=row['source_business_id'], system_id=system, source_native_status=native_status,
                    details=json_bytes(dict(fields=fields, raw=raw, locator=row['locator'], source_row_id=row['id'],
                        validation_status=row['values']['validation_status'], resolution_status='unresolved', approval_status='pending',
                        meaning='Evidence supplied/status reported; neither compliance nor authorized incident resolution')).decode('utf-8'))
                if 'retrieved_at' in row: incident['retrieved_at'] = row['retrieved_at']
                state['incident_evidence'].append(incident); outputs[row['id']].append(incident['id'])
                subjects = [incident['id']]
            else:
                outputs[row['id']].append(issue(system,'reported.operational_status',row['source_business_id'],
                    'Missing source-native incident status; raw occurrence retained without an invented label',basis,ev,known_owner=known))
            label = fields.get('evidence_state')
            if label != 'complete':
                outputs[row['id']].append(issue(system, 'reported.evidence_state', row['source_business_id'],
                    'Reported evidence state ' + str(label) + '; missing verification or disagreement remains unresolved',
                    basis, ev, subjects, known_owner=known))
            for name in (f['field'] for f in dictionary['registers'][register]['fields']):
                value = fields.get(name)
                assertion(system, 'reported.' + name, 'EVIDENCE:' + row['source_business_id'], value, ev,
                    basis, row['id'], known, usable=value is not None,
                    reason=('Reported value is explicitly unknown' if name in fields else
                        'Missing/invalid reported value') if value is None else None,
                    retrieved_at=row.get('retrieved_at'))
        elif register == 'CALENDAR':
            accounting['calendar_context'].append(dict(source_row_id=row['id'], source_business_id=row['source_business_id'],
                system_id=system, fields=deepcopy(fields), evidence_ids=ev, locator=row['locator'],
                approval_status='pending', completion_status='unresolved', scope_expansion=None))
            for name in (f['field'] for f in dictionary['registers'][register]['fields']):
                value = fields.get(name)
                assertion(system, 'reported.' + name, 'CALENDAR:' + row['source_business_id'], value, ev,
                    basis, row['id'], known, usable=value is not None,
                    reason=('Reported value is explicitly unknown' if name in fields else
                        'Missing/invalid reported value') if value is None else None,
                    retrieved_at=row.get('retrieved_at'))
        if row['values']['validation_status'] != 'valid':
            outputs[row['id']].append(issue(system, 'normalization', register,
                'Normalized row has unresolved fields or identity; retained original values require correction', basis, ev, known_owner=known))

    # Duplicate business IDs crossing systems stay separate and get an identity
    # conflict. Field conflicts within a system are grouped below without winners.
    identities = defaultdict(list)
    for row in rows: identities[(row['source_id'],row['source_business_id'])].append(row)
    for (register,business), members in identities.items():
        if len(members) > 1:
            systems = sorted({r['system_id'] for r in members})
            conflict = issue(None, 'identity', register + ':' + business,
                'Overlapping source business identity: ' + json_bytes([dict(system_id=r['system_id'],
                    fields=r['values']['fields'], row_id=r['id']) for r in members]).decode(),
                [r['id'] for r in members], [i for r in members for i in r['evidence_ids']],
                conflict=True, known_owner='Operations')
            accounting['issues'][-1]['related_system_ids'] = systems
            for row in members: outputs[row['id']].append(conflict)

    supported_policy = defaultdict(list)
    for number, candidate, descriptor, attempt in assessments:
        system = candidate['system_ids'][0]
        eid = descriptor['evidence_id']; quote = descriptor['quote']
        basis = [eid, 'analysis/reconciliation candidate ' + str(number)]
        if descriptor['kind'] == 'fact':
            predicate = descriptor['predicate']
            usable = descriptor['value'] is not None and descriptor['review_date_quote'] is not None and \
                (descriptor['observed_on'] is None or descriptor['observed_on'] <= ASSIGNED_REVIEW_DATE)
            if predicate == 'exception_claim': usable = False
            if predicate in {'provider_role','deployer_role'} and not descriptor['role_current']: usable = False
            reason = (None if usable else 'Exception has no authorized Legal decision' if predicate == 'exception_claim' else
                'Role is stale or unverified' if predicate in {'provider_role','deployer_role'} and not descriptor['role_current'] else
                'Report value or suitability for assigned review date is unverified')
            assertion(system, predicate, descriptor['scope'], descriptor['value'], [eid], basis,
                'candidate:' + str(number), descriptor['owner'], usable, reason, descriptor['observed_on'],attempt['retrieved_at'])
        else:
            possibly_applicable = (descriptor['effective_from'] is None or
                descriptor['effective_from'] <= ASSIGNED_REVIEW_DATE) and (descriptor['effective_until'] is None or
                ASSIGNED_REVIEW_DATE < descriptor['effective_until'])
            active = descriptor['activation'] == 'active' and descriptor['effective_from'] is not None and possibly_applicable
            if not active:
                issue(None, 'policy', descriptor['basis_id'], 'Policy activation or review-date applicability unresolved',
                    basis, [eid], known_owner='Operations' if descriptor['activation'] != 'active' else 'Legal')
            if possibly_applicable:
                supported_policy[descriptor['basis_id']].append((number,candidate,descriptor,attempt))

    for basis_id, entries in supported_policy.items():
        # Multiple versions/meanings for one control need Legal; no latest winner.
        meanings = {json_bytes(dict(control=c['summary'], meaning=d['meaning_key'], systems=sorted(c['system_ids']),
            version=d['version'], activation=d['activation'], start=d['effective_from'], end=d['effective_until'])) for _,c,d,_ in entries}
        if len(meanings) != 1:
            issue(None, 'policy', basis_id, 'Conflicting internal control versions/scopes/activation: ' +
                json_bytes([d for _,_,d,_ in entries]).decode(), ['POLICY'],
                [d['evidence_id'] for _,_,d,_ in entries], conflict=True, known_owner='Legal')
            continue
        _, candidate, descriptor, attempt = entries[0]
        if descriptor['activation'] != 'active' or descriptor['effective_from'] is None:
            continue
        key = dict(basis_id='POLICY:' + basis_id, meaning_key=descriptor['meaning_key'])
        control = dict(record('policy-control',candidate['summary'],[d['evidence_id'] for _,_,d,_ in entries]),
            version_key=key, rule_version_id=rule_version_id(**key), supersedes_rule_version_id=None,
            basis_type='internal-control', control=descriptor['control'], system_ids=sorted(candidate['system_ids']),
            retrieved_at=attempt['retrieved_at'], effective_from=descriptor['effective_from'],
            effective_until=descriptor['effective_until'], effective_precision='date')
        state['policy_controls'].append(control)

    for (system,predicate,scope_key), assertions in sorted(groups.items()):
        distinct = {json_bytes(a['value']) for a in assertions if a['value'] is not None}
        # Even stale/uncertain assertions remain contradictory; usability does
        # not erase a disagreement. Resolution requires authorized correction.
        disposition = 'conflicting' if len(distinct) > 1 else 'supported' if all(a['usable'] for a in assertions) else 'unresolved'
        evidence = sorted({eid for a in assertions for eid in a['evidence_ids']})
        reason = ('Scoped assertions disagree; every value retained' if disposition == 'conflicting' else
            '; '.join(sorted({a['reason'] or 'Missing verification' for a in assertions if not a['usable']}))
                if disposition == 'unresolved' else
            'Captured source-reported field only; no verified predicate inferred' if predicate.startswith('reported.') else
            'Scoped draft report observation with explicit review-date basis')
        value = dict(scope=scope_key, resolved_value=assertions[0]['value'] if disposition == 'supported' else None,
            assertions=sorted(assertions,key=json_bytes))
        assertion_owners = {a['owner'] for a in assertions if a['owner'] is not None}
        known_owner = owner(system) or (next(iter(assertion_owners)) if len(assertion_owners)==1 else None)
        fact = dict(record('fact', system + ' ' + predicate + ' (' + scope_key + ')', evidence),
            system_id=system, predicate=predicate, value=value, state=disposition,
            source_basis=sorted({b for a in assertions for b in a['source_basis']}), reason=reason,
            owner=known_owner, resolution_need=None if disposition == 'supported' else
                'System owner must verify this field/scope and preserve contradictory records; Legal decides any final interpretation.')
        state['system_facts'].append(fact)
        accounting['fact_groups'].append(dict(record_id=fact['id'], system_id=system, predicate=predicate, scope=scope_key))
        for a in assertions:
            if a['origin'] in outputs: outputs[a['origin']].append(fact['id'])
        if disposition != 'supported':
            conflict_reason = reason + '; values and bases: ' + json_bytes(value).decode() if disposition == 'conflicting' else reason
            issue(system, predicate, scope_key, conflict_reason, fact['source_basis'], evidence, [fact['id']],
                conflict=disposition == 'conflicting',known_owner=known_owner)

    # No absence implies a false predicate. Each scoped system has explicit
    # register membership and unknown verification for uncovered fields.
    for system in scope:
        membership = {register:[r['id'] for r in rows if r['source_id']==register and r['system_id']==system] for register in REGISTERS}
        accounting['systems'].append(dict(system_id=system, registers=membership,
            owner_candidates=sorted(owners[system]), all_calendar_rows=[r['id'] for r in rows if r['source_id']=='CALENDAR' and r['system_id']=='ALL']))
        for register, members in membership.items():
            if not members:
                issue(system, 'membership', register, 'Scoped system absent from ' + register + '; ALL calendar context does not establish a system-specific row',
                    [sources[register]['id']], subjects=[sources[register]['id']])
        for predicate in PREDICATES:
            if not any(s == system and p == predicate for s,p,_ in groups):
                fact = dict(record('fact',system + ' unverified ' + predicate,[]), system_id=system, predicate=predicate,
                    value=None, state='unresolved', source_basis=[sources['SYSTEMS']['id'],sources['EVIDENCE']['id']],
                    reason='No verified scoped report assessment for this predicate; register labels and roles do not establish it',
                    owner=owner(system), resolution_need='System owner must supply scoped report/test evidence and confirm suitability for the assigned review date.')
                state['system_facts'].append(fact)
                accounting['fact_groups'].append(dict(record_id=fact['id'],system_id=system,predicate=predicate,scope='unverified'))
                issue(system, predicate, 'unverified', fact['reason'],fact['source_basis'],subjects=[fact['id']])

    # Every raw data row, including unnormalizable identities/header failures,
    # has a ledger entry and an output or explicit unresolved disposition.
    extension = second['state']['extensions'].get('u08_capture') or second['state']['extensions']['u07_capture']
    for table in extension['value']['raw_tables']:
        accounting['register_tables'].append(deepcopy(table))
        for number,cells in enumerate(table['rows'][1:],2):
            locator = f"{table['tab_title']} (gid {table['sheet_id']}) row {number}"
            matched = [r for r in rows if r['source_id'] == table['source_id'] and r['locator']['value'] == locator]
            ids = [r['id'] for r in matched]
            targets = sorted({i for r in matched for i in outputs[r['id']]})
            if not matched:
                targets = [issue(None,'raw-row',locator,'Raw register row could not be normalized; every original cell retained',
                    table['source_basis'] + [locator], known_owner='Operations')]
            accounting['register_rows'].append(dict(source_id=table['source_id'], locator=locator,
                raw_cells=deepcopy(cells), normalized_row_ids=ids, output_record_ids=targets,
                disposition='retained' if matched else 'unresolved'))
    for row in rows:
        require(any(row['id'] in entry['normalized_row_ids'] for entry in accounting['register_rows']),
                'normalized row missing raw accounting')
        accounting['normalized_rows'].append(dict(source_row_id=row['id'],output_record_ids=sorted(set(outputs[row['id']]))))
    for report in second['state'].get('extensions',{}).get('u08_reports',{}).get('value',{}).get('reports',[]):
        numbers = [n for n,_,d,_ in assessments if d['kind']=='fact' and d['evidence_id'] in report['evidence_ids']]
        gap = issue(report['system_id'],'report-review',report['source_business_id'],
            'Report retained for bounded assessment; completeness, identity/date and remaining meanings need owner review',
            [report['source_id'], report['reference'] or 'Missing reference'],report['evidence_ids'],known_owner=report['owner'])
        accounting['reports'].append(dict(report=deepcopy(report), candidate_numbers=numbers, gap_id=gap))
    policy_evidence = [e['id'] for e in second['state']['evidence'] if e['assertion'].startswith('Captured internal policy body')]
    accounting['policy_context'] = [dict(source_id='POLICY',evidence_ids=policy_evidence,
        candidate_numbers=[n for n,_,d,_ in assessments if d['kind']=='policy-control'])]
    if not state['policy_controls']:
        issue(None,'policy','POLICY','No established internal policy control; source access, version, scope or activation requires Legal/Operations review',
            [sources['POLICY']['id']],policy_evidence,subjects=[sources['POLICY']['id']],known_owner='Legal')
    for review in reviews:
        if review['disposition'] == 'unresolved':
            issue(None,'candidate-review','candidate:' + str(review['number']),review['reason'],
                [pointers['response']['path']],known_owner='Operations')
    if result is not None and result.disposition != 'proposed':
        issue(None,'interpretation',STAGE,result.reason or 'Unsupported company interpretation',
            [pointers['response']['path']],known_owner='Operations')
    for diagnostic in second['state']['diagnostics']:
        # Keep company normalization/report issues; authority limitations already
        # remain upstream and continue to control aggregate outcome.
        if any(register in diagnostic['source_basis'] for register in REGISTERS) or \
                any(diagnostic['summary'].startswith(register) for register in REGISTERS):
            issue(None,'capture-diagnostic','company',diagnostic['reason'],diagnostic['source_basis'],
                diagnostic['evidence_ids'],known_owner=diagnostic['owner'])
    consumed = {r['id'] for s in chain for r in stage_records(s)}
    # The whole upstream ledger is intentionally consumed: all records, including
    # capture diagnostics and rows with no usable fields, inform reconciliation.
    meaningful = any(r['system_id'] in scope for r in rows) or bool(state['policy_controls'])
    if not meaningful:
        issue(None,'deferral','company','No meaningful scoped company facts or established controls remain; defer reconciliation pending source-owner evidence',
            [sources[register]['id'] for register in REGISTERS]+[sources['POLICY']['id']],known_owner='Operations')
    _schema(accounting, 'reconciliation-accounting')
    state['extensions'] = {'u10_reconciliation':dict(schema_version=VERSION,value=accounting)}
    status = reduce_states([third['status'], 'blocked' if not meaningful else
        'partial' if state['evidence_gaps'] or state['conflicts'] else 'complete'])
    return chain,state,sorted(consumed),status,pointers,result


def freeze_reconciliation(store, *, write=True):
    from .runner import _snapshot
    chain,state,consumed,status,pointers,result = project(store)
    predecessor = dict(snapshot_id=chain[2]['snapshot_id'],path=SNAPSHOT_PATHS[2],
        sha256=sha256_bytes(_read(store.root,SNAPSHOT_PATHS[2])))
    fourth = _snapshot(store,4,state,status,store.providers,predecessor=predecessor,consumed=consumed)
    if result is not None and result.disposition == 'proposed': fourth['interpretation_bindings'] = [pointers]
    if write:
        write_snapshot(store.root,fourth,upstream=chain)
        validate_reconciliation(store)
    return fourth


def validate_reconciliation(store):
    """Rebuild from journal, rows and exchange; coherent on-disk edits still fail."""
    actual = read_chain(store.root,count=4)[3]
    expected = freeze_reconciliation(store,write=False)
    def canonical(snapshot):
        # Replace random current-stage IDs with their full substantive record.
        # Preserve multiplicity; no summary-key dictionary can collapse records.
        records = {r['id']:r for r in stage_records(snapshot)}
        def replace(value, trail=()):
            if isinstance(value,str) and value in records:
                require(value not in trail,'cyclic U10 accounting')
                return replace({k:v for k,v in records[value].items() if k!='id'},trail+(value,))
            if isinstance(value,dict): return {k:replace(v,trail) for k,v in value.items() if k!='id'}
            if isinstance(value,list): return sorted((replace(v,trail) for v in value),key=json_bytes)
            return value
        # Sorting is only for graph record sets/accounting references. Source
        # matrices, raw cells, candidate arrays and assertions keep exact order.
        state = deepcopy(snapshot['state'])
        extension = state['extensions']['u10_reconciliation']['value']
        raw_tables = extension.pop('register_tables')
        raw_cells = [entry.pop('raw_cells') for entry in extension['register_rows']]
        reviews = extension.pop('candidate_reviews')
        return json_bytes(dict(state=replace(state),raw_tables=raw_tables,raw_cells=raw_cells,reviews=reviews,
            status=snapshot['status'],consumed=snapshot['consumed_record_ids'],bindings=snapshot.get('interpretation_bindings',[])))
    require(actual['decisions']==expected['decisions'] and actual['unresolved']==expected['unresolved'] and
        canonical(actual)==canonical(expected), 'Stage 04 differs from verified reconciliation and row accounting')
    return actual


def interpret_reconciliation(store, config, *, timeout=180):
    """Restricted fresh host exchange, with separate logs from U09's invocation."""
    chain = _chain(store)
    second = chain[1]['state']
    if not second['normalized_rows'] and not any(e['assertion'].startswith('Captured internal policy body') for e in second['evidence']):
        return freeze_reconciliation(store)
    host,version = preflight(config)
    root = store.root
    if not (root/SKILL.name).exists():
        shutil.copytree(SKILL,root/SKILL.name,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(SKILL.parent/'snapshot.schema.json',root/'snapshot.schema.json')
        directory=root/'.agents/skills'; directory.mkdir(parents=True)
        (directory/SKILL.name).symlink_to('../../'+SKILL.name,target_is_directory=True)
    # The copied helper rebuilds U05/U06 acquisition, whose reviewed routes live
    # outside the skill package. Retain those declarations (not source evidence)
    # without overwriting any U09 inputs, and bind them as a packet reference.
    route_bytes = (SKILL.parent/'config/review.example.json').read_bytes()
    if (root/'config/review.example.json').exists():
        require(_read(root,'config/review.example.json')==route_bytes,'changed reviewed route declarations')
    else:
        _write(root,'config/review.example.json',route_bytes)
    def pointer(path): return dict(path=path,sha256=sha256_bytes(package_path(root,path).read_bytes()))
    metadata=dict(host_version=version,requested_model=config['host']['model'],requested_effort=config['host']['effort'],
        reported_model=None,reported_effort=None,usage=None,
        instruction_versions=[pointer(SKILL.name+'/SKILL.md'),pointer(SKILL.name+'/references/reconciliation.md')],
        reference_versions=[pointer(SKILL.name+'/references/schemas/reconciliation-basis.schema.json'),
                            pointer('config/review.example.json')])
    create_reconciliation_request(store,metadata)
    immutable=file_inventory(root)
    command=host_command(host,root,config['host']['model'],config['host']['effort'])
    prompt=(f'Use $regulatory-change-impact-brief U10 reconciliation branch. Run root: {root}. '
        f'Read {root/SKILL.name}/references/reconciliation.md and analysis/reconciliation/request.json. '
        f'Submit once: {sys.executable} {root/SKILL.name}/scripts/stage.py submit-reconciliation '
        f'--root {root} --proposal {root}/analysis/reconciliation/agent-proposal.json. '
        'Stop after submission. Supervisor writes Stage 04; no later units.')
    _write(root,'analysis/reconciliation/host-prompt.txt',prompt.encode())
    _write(root,'analysis/reconciliation/host-invocation.json',json_bytes(dict(command=command,metadata=metadata)))
    invoke_host(command,prompt,root,timeout,analysis_directory='analysis/reconciliation')
    verify_inventory(root,immutable)
    require((root/'analysis/reconciliation/submission.json').is_file(),'host did not submit reconciliation')
    _write(root,'analysis/reconciliation/host-outcome.json',json_bytes(dict(
        visible_usage=visible_usage(root,analysis_directory='analysis/reconciliation'),production_package=False)))
    return freeze_reconciliation(store)
