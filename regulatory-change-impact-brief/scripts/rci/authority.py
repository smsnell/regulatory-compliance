"""U09 draft authority prerequisites and Stage 03. No legal truth engine.

The invoking skill supplies semantic assessments with captured support. These
checks verify provenance, coverage, authority classes and date prerequisites;
neither a passing schema nor this module grants final Legal interpretation.
"""
from copy import deepcopy
from collections import Counter
from datetime import date
import shutil
import sys
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from .adapters.reports import text_representation
from .contracts import (ASSIGNED_REVIEW_DATE, ContractError, ExchangeResult,
    SNAPSHOT_PATHS, json_bytes, package_path, parse_json, require, sha256_bytes,
    validate_interpretation, validate_schema, reduce_states)
from .evidence import EvidenceStore, _read, _write
from .ids import new_record_id, rule_version_id
from .runtime import (SKILL, Providers, file_inventory, host_command, invoke_host,
    preflight, verify_inventory, visible_usage)
from .snapshots import read_chain, stage_records, write_snapshot

LEGAL = ('LAW', 'OJ', 'AMEND', 'CONSOLIDATED')
GUIDANCE = ('TIME', 'FAQ')
SOURCES = LEGAL + GUIDANCE
FORMAL = {'OJ', 'AMEND', 'CONSOLIDATED'}
VERSION = 'rci-u09-authority/1'


def project_legal(store, *, persist=False, retained_captures=()):
    """Retain/recheck readable legal text before Stage 02 freeze in NEW runs."""
    captures, evidence = [], []
    for event in store.inventory():
        attempt, parent = event['attempt'], event['capture']
        if attempt['source_id'] not in SOURCES:
            continue
        text = text_representation(store, event)
        if text is None:
            continue
        capture = parent
        if parent['content_type'].split(';')[0].strip().lower() == 'text/html':
            path = 'sources/' + attempt['attempt_key'] + '.legal.txt'
            if persist:
                _write(store.root, path, text.encode('utf-8'))
                capture = dict(id=new_record_id(store.run_id, 2, 'capture'), record_type='capture',
                    summary='Derived legal page body text; authority and version remain unverified', evidence_ids=[],
                    attempt_id=parent['attempt_id'], representation='extract', local_reference=path,
                    content_hash=sha256_bytes(text.encode('utf-8')), content_type='text/plain',
                    derived_from_capture_id=parent['id'],
                    derivation=dict(method='HTMLParser visible text (no scripts/styles)', processed_at=store.providers.now()),
                    representation_metadata=dict(method='HTMLParser visible text (no scripts/styles)',
                        locator='whole visible page body', permission='Disclosed legal source retention'))
            else:
                matches = [c for c in retained_captures if c.get('derived_from_capture_id') == parent['id']]
                require(len(matches) == 1, 'missing or duplicated legal derivation')
                capture = deepcopy(matches[0])
                require(capture['local_reference'] == path and capture['content_hash'] == sha256_bytes(text.encode('utf-8'))
                        and capture['content_type'] == 'text/plain' and
                        capture['derivation']['method'] == 'HTMLParser visible text (no scripts/styles)',
                        'legal derivation differs from original')
                require(_read(store.root, path) == text.encode('utf-8'), 'legal extract bytes changed')
            validate_schema(capture, 'capture')
            captures.append(capture)
        claim = dict(id=new_record_id(store.run_id, 2, 'evidence'), record_type='evidence',
            summary='Captured legal/context page body for ' + attempt['source_id'], evidence_ids=[],
            capture_id=capture['id'], local_reference=capture['local_reference'], content_hash=capture['content_hash'],
            locator=dict(kind='extract', value='whole visible body of ' + attempt['source_id'] + '; quote locates paragraph'),
            assertion='Captured legal/context page body for ' + attempt['source_id'], quoted_support=text)
        validate_schema(claim, 'evidence')
        evidence.append(claim)
    return dict(captures=captures, evidence=evidence)


def _schema(value):
    schema = parse_json((SKILL/'references/schemas/authority-basis.schema.json').read_bytes())
    require(Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value),
            'missing or malformed U09 authority assessment')


def _index(chain):
    return {r['id']:r for s in chain for r in stage_records(s)}


def _source_for(eid, index):
    evidence = index[eid]
    capture = index[evidence['capture_id']]
    return index[capture['attempt_id']]


def prerequisites(chain):
    state = chain[1]['state']
    problems = []
    for source in SOURCES:
        attempts = [a for a in state['attempts'] if a['source_id'] == source]
        if not any(a['outcome'] == 'HTTP 200' and a['identity_check'] != 'mismatch'
                   and a['retrieval_status'] not in {'invalid', 'unavailable', 'stale'} for a in attempts):
            problems.append(source + ': required authority/context source unavailable or unsuitable')
        elif not any(e['assertion'] == 'Captured legal/context page body for ' + source for e in state['evidence']):
            problems.append(source + ': missing readable captured legal extract')
    if 'u09_legal' not in state.get('extensions', {}):
        problems.append('Legal extraction requires a fresh U09 capture run; frozen Stage 02 cannot be edited')
    return problems


def _assessment(candidate, chain):
    """Validate explicit semantic support; return descriptor or a visible blocker."""
    require(len(candidate['timing_candidates']) == 1, 'one structured U09 authority assessment required')
    value = parse_json(candidate['timing_candidates'][0].encode('utf-8'))
    _schema(value)
    require(candidate['role'] != 'unknown' and candidate['conditions'], 'role or legal predicates unknown')
    index = _index(chain)
    citations = {(c['evidence_id'], c['quote']) for c in candidate['citations']}
    def support(eid, quote, formal=False):
        require((eid, quote) in citations, 'authority component lacks candidate citation')
        attempt = _source_for(eid, index)
        require(attempt['source_id'] in (FORMAL if formal else set(SOURCES)), 'guidance cannot establish binding law')
        if attempt['source_id'] in FORMAL:
            for field in ('original_locator','effective_locator'):
                location = urlsplit(attempt[field] or '')
                require(location.scheme == 'https' and location.hostname == 'eur-lex.europa.eu',
                        'formal authority requires official EUR-Lex origin; a source label or authorized mirror is insufficient')
        require(attempt['outcome'] == 'HTTP 200' and attempt['identity_check'] != 'mismatch' and
                attempt['retrieval_status'] not in {'invalid','unavailable','stale'}, 'unsuitable component source')
        return attempt
    assessments = value['sources']
    require(len(assessments) == len(SOURCES) and {s['source_id'] for s in assessments} == set(SOURCES),
            'each required authority/context source needs an assessment')
    expected_relations = {'LAW': {'reproduction'}, 'OJ': {'base'}, 'AMEND': {'amends','unrelated','future'},
        'CONSOLIDATED': {'consolidates'}, 'TIME': {'context'}, 'FAQ': {'context'}}
    for source in assessments:
        attempt = support(source['evidence_id'], source['identity_quote'])
        require(attempt['source_id'] == source['source_id'], 'source assessment changes source identity')
        support(source['evidence_id'], source['version_quote'])
        support(source['evidence_id'], source['relationship_quote'])
        require(source['document_id'] in source['identity_quote'] and source['version'] in source['version_quote'],
                'document identity/version lacks literal captured support')
        require(source['relationship'] in expected_relations[source['source_id']], 'incompatible authority relationship')
        if source['source_id'] == 'OJ':
            require(source['document_id'] == '2024/1689', 'unrelated base act')
        if source['source_id'] in {'LAW','AMEND','CONSOLIDATED'} and source['relationship'] not in {'unrelated','future'}:
            require('2024/1689' in source['relationship_quote'], 'relationship to reviewed act unverified')
        if source['source_id'] in {'AMEND','CONSOLIDATED'}:
            selector = parse_qs(urlsplit(attempt['original_locator']).query).get('uri', [None])[0]
            require(selector == source['document_id'], 'returned act/version does not match requested selector')
        require(source['assessment'] == 'consistent', 'conflicting or unresolved authority/version/timing chain')
        if source['publication_date'] is not None:
            require(source['publication_date'] in source['version_quote'], 'publication date lacks literal evidence')
            require(source['source_id'] not in FORMAL or source['publication_date'] <= ASSIGNED_REVIEW_DATE or source['relationship'] in {'future','unrelated'},
                    'post-review version cannot silently supply historical authority')
        if source['relationship'] == 'future':
            require(source['effective_from'] is not None and source['effective_from'] > ASSIGNED_REVIEW_DATE and
                    source['effective_from'] in source['relationship_quote'], 'future amendment exclusion needs supported date')
        elif source['relationship'] == 'amends':
            require(source['effective_from'] is not None and source['effective_from'] <= ASSIGNED_REVIEW_DATE and
                    source['effective_from'] in source['relationship_quote'], 'amendment application needs supported date')
    components = [('obligation', candidate['summary']), ('role', candidate['role'])]
    components += [('predicate', p) for p in candidate['conditions']]
    components += [('exception', p) for p in candidate['exception_candidates']]
    components += [('exception-scope', value['exception_scope'])]
    components += [('timing', value['timing']['basis'])]
    actual = [(s['component'], s['value']) for s in value['support']]
    require(sorted(actual) == sorted(components), 'every predicate, role, exception and timing basis needs distinct support')
    excluded = {s['source_id'] for s in assessments if s['relationship'] in {'future','unrelated'}}
    assessed_evidence = {s['source_id']:s['evidence_id'] for s in assessments}
    for component in value['support']:
        attempt = support(component['evidence_id'], component['quote'], formal=True)
        require(component['evidence_id'] == assessed_evidence[attempt['source_id']],
                'legal component must use the assessed source capture and version')
        require(attempt['source_id'] not in excluded, 'excluded amendment cannot establish a rule')
        require(component['value'].casefold() in component['quote'].casefold(),
                'legal component is not stated in its captured binding quote')
    timing = value['timing']
    require(timing['precision'] == 'date', 'date-boundary ambiguity: assigned date does not establish an intraday cutover')
    require(timing['effective_from'] is not None, 'missing supported applicability date')
    timing_quotes = [s['quote'] for s in value['support'] if s['component'] == 'timing']
    for field in ('effective_from','effective_until'):
        if timing[field] is not None:
            require(any(timing[field] in q for q in timing_quotes), 'effective date not present in binding timing quote')
            date.fromisoformat(timing[field])
    require(timing['effective_until'] is None or timing['effective_from'] < timing['effective_until'], 'conflicting timing interval')
    require(timing['effective_from'] <= ASSIGNED_REVIEW_DATE and
            (timing['effective_until'] is None or ASSIGNED_REVIEW_DATE < timing['effective_until']),
            'rule is outside assigned review date')
    require(not any(s['publication_date'] is None for s in assessments if s['source_id'] in FORMAL
                    and s['relationship'] not in {'future','unrelated'}), 'formal source publication/version history unknown')
    require(value['supersedes_rule_version_id'] is None, 'supersession requires verified prior semantic history; no history inferred from a candidate')
    return value


def evaluate(root, request_bytes, response_bytes):
    chain = read_chain(root, count=2)
    require(isinstance(parse_json(request_bytes), dict) and isinstance(parse_json(response_bytes), dict), 'exchange must be objects')
    result = validate_interpretation(request_bytes, response_bytes, root=root, run_id=root.name,
        stage='authority-and-timing', upstream=chain)
    problems = prerequisites(chain)
    shared_failure = bool(problems)
    accepted, guidance = [], []
    claimed_bases = []
    source_claims = {source:[] for source in SOURCES}
    if result.disposition != 'proposed':
        problems.append(result.reason)
    else:
        for number, candidate in enumerate(result.response['candidates'], 1):
            if candidate['basis_type'] == 'guidance':
                index = _index(chain)
                if all(_source_for(c['evidence_id'], index)['source_id'] in GUIDANCE for c in candidate['citations']):
                    guidance.append(candidate)
                else:
                    problems.append(f'Candidate {number}: guidance has mismatched authority source')
            elif candidate['basis_type'] != 'binding-legal':
                problems.append(f'Candidate {number}: nonlegal candidate belongs to a later unit')
            else:
                # Preserve basis-specific failures without discarding independent
                # supported rules. Competing claims to one basis still withhold it.
                try:
                    claimed = parse_json(candidate['timing_candidates'][0].encode('utf-8'))
                    if isinstance(claimed, dict) and isinstance(claimed.get('basis_id'), str):
                        claimed_bases.append(claimed['basis_id'])
                    _schema(claimed)
                    for source in claimed['sources']:
                        source_claims[source['source_id']].append({k:source[k] for k in (
                            'document_id','version','publication_date','effective_from','relationship','assessment')})
                except (ValueError, IndexError):
                    pass
                try:
                    descriptor = _assessment(candidate, chain)
                    accepted.append((candidate, descriptor))
                except (ValueError, KeyError) as error:
                    problems.append(f'Candidate {number}: {error}')
    if not accepted:
        problems.append('No supported binding rule candidates; Legal must resolve the authority scope')
    duplicated = {basis for basis,count in Counter(claimed_bases).items() if count > 1}
    if duplicated:
        problems.append('Conflicting or duplicated candidate authority/version chain; Legal review required')
    for source, claims in source_claims.items():
        if any(c['assessment'] != 'consistent' for c in claims) or len({json_bytes(c) for c in claims}) > 1:
            shared_failure = True
            problems.append(source + ': conflicting or unresolved shared source assessments; withhold dependent rules')
    # Shared source failure blocks every dependent rule; an individual assessment
    # failure affects its own basis. Aggregate status remains blocked in both cases.
    rules = [] if shared_failure else [(c,d) for c,d in accepted if d['basis_id'] not in duplicated]
    return dict(exchange=result, rules=rules, guidance=guidance, problems=problems)


def submit_authority(root, proposal_bytes, *, providers=None):
    providers = providers or Providers()
    request_bytes = _read(root, 'analysis/authority/request.json')
    request = parse_json(request_bytes)
    directory = 'analysis/authority/exchanges/' + uuid4().hex
    _write(root, directory + '/request.json', request_bytes)
    _write(root, directory + '/proposal.json', proposal_bytes)
    status, reason = 'failed', 'Invalid proposal'
    try:
        proposal = parse_json(proposal_bytes)
        require(isinstance(proposal, dict) and set(proposal) == {'disposition','diagnostic','candidates'}, 'invalid authority proposal fields')
        metadata = deepcopy(request['metadata'])
        metadata.update(reported_model=None, reported_effort=None, usage=None)
        raw = json_bytes(dict(**proposal, schema_version='rci-interpretation-response/1',
            run_id=request['run_id'], stage=request['stage'], packet_id=request['packet_id'],
            packet_sha256=sha256_bytes(request_bytes), responded_at=providers.now(), metadata=metadata))
        _write(root, directory + '/response.json', raw)
        value = evaluate(root, request_bytes, raw)
        status = 'proposed' if not value['problems'] else 'unresolved'
        reason = '; '.join(value['problems']) or None
        pointers = {name:dict(path=directory + '/' + name + '.json', sha256=sha256_bytes(data))
                    for name,data in [('request',request_bytes),('response',raw)]}
        _write(root, 'analysis/authority/submission.json', json_bytes(pointers))
    except (ValueError, OSError) as error:
        reason = str(error)
        raise
    finally:
        _write(root, directory + '/validation.json', json_bytes(dict(status=status, reason=reason,
            source_evidence=False, semantic_proof=False)))
    return dict(disposition=status, reason=reason, production_package=False)


def freeze_authority(store, *, write=True):
    """Python writes Stage 03 after independently rereading the accepted exchange."""
    from .runner import _snapshot, validate_slice
    chain = list(validate_slice(store))
    root = store.root
    submission_path = root/'analysis/authority/submission.json'
    pointers, value = None, None
    if submission_path.exists():
        pointers = parse_json(_read(root, 'analysis/authority/submission.json'))
        require(isinstance(pointers, dict) and set(pointers) == {'request','response'}, 'invalid authority submission')
        raws = {}
        for name, pointer in pointers.items():
            require(set(pointer) == {'path','sha256'} and pointer['path'].startswith('analysis/authority/exchanges/'), 'invalid authority pointer')
            raws[name] = _read(root, pointer['path'])
            require(sha256_bytes(raws[name]) == pointer['sha256'], 'changed authority analysis bytes')
        require(raws['request'] == _read(root, 'analysis/authority/request.json'), 'authority submission belongs to another packet')
        value = evaluate(root, raws['request'], raws['response'])
    problems = prerequisites(chain) if value is None else value['problems']
    if value is None:
        problems.append('No authority interpretation submitted; Legal must inspect captured sources')
    state = dict(binding_rules=[], timing_rules=[], guidance_context=[], authority_blockers=[])
    accounting = dict(schema_version=VERSION, draft_only=True, final_interpretation_owner='Legal',
        assigned_review_date=ASSIGNED_REVIEW_DATE, candidates=[], problems=problems, interpretation=pointers)
    if value is not None:
        for candidate in value['guidance']:
            state['guidance_context'].append(dict(id=new_record_id(store.run_id,3,'guidance'), record_type='guidance',
                summary=candidate['summary'], evidence_ids=sorted({c['evidence_id'] for c in candidate['citations']}),
                basis_type='guidance', context=candidate['summary']))
        for candidate, descriptor in value['rules']:
            ids = sorted({c['evidence_id'] for c in candidate['citations']})
            key = {k:descriptor[k] for k in ('basis_id','meaning_key')}
            base = next(s for s in descriptor['sources'] if s['source_id'] == 'OJ')
            retrieved = _source_for(base['evidence_id'], _index(chain))['retrieved_at']
            rule = dict(id=new_record_id(store.run_id,3,'rule'), record_type='rule', summary=candidate['summary'],
                evidence_ids=ids, version_key=key, rule_version_id=rule_version_id(**key),
                supersedes_rule_version_id=descriptor['supersedes_rule_version_id'], basis_type='binding-legal',
                obligation=candidate['summary'], predicates=candidate['conditions'] + ['role=' + candidate['role']] +
                    ['exception scope: ' + descriptor['exception_scope']] + ['exception: ' + e for e in candidate['exception_candidates']],
                applicability='established', source_versions=[s['source_id'] + ':' + s['version'] for s in descriptor['sources']],
                retrieved_at=retrieved, source_publication_date=base['publication_date'],
                effective_precision='date', effective_from=descriptor['timing']['effective_from'],
                effective_until=descriptor['timing']['effective_until'])
            state['binding_rules'].append(rule)
            timing = descriptor['timing']
            state['timing_rules'].append(dict(id=new_record_id(store.run_id,3,'timing-rule'), record_type='timing-rule',
                summary='Draft applicability timing for ' + descriptor['basis_id'], evidence_ids=ids, rule_id=rule['id'],
                timing_basis=timing['basis'], precision=timing['precision'], boundary_timezone=timing['boundary_timezone'],
                applicability='established', effective_from=timing['effective_from'], effective_until=timing['effective_until']))
            state['timing_rules'][-1].update(retrieved_at=retrieved, source_publication_date=base['publication_date'])
            accounting['candidates'].append(dict(rule_id=rule['id'], system_ids=candidate['system_ids'],
                role=candidate['role'], exceptions=candidate['exception_candidates'], assessment=descriptor))
    for problem in problems:
        state['authority_blockers'].append(dict(id=new_record_id(store.run_id,3,'blocker'), record_type='blocker',
            summary=problem, evidence_ids=[], source_basis=list(SOURCES) + ([] if pointers is None else [pointers['response']['path']]),
            reason=problem, owner='Legal', resolution_need='Legal must verify the captured authority, version, scope and timing; withhold dependent formal conclusions. Retain this question in the later draft; no request has been sent.'))
    accounting['candidate_reviews'] = []
    if value is not None:
        for number, candidate in enumerate(value['exchange'].response['candidates'], 1):
            supported = any(candidate == c for c, _ in value['rules'])
            context = candidate in value['guidance']
            accounting['candidate_reviews'].append(dict(number=number,
                claimed_summary=candidate.get('summary') if isinstance(candidate, dict) else None,
                claimed_system_ids=candidate.get('system_ids') if isinstance(candidate, dict) else None,
                disposition='supported-draft-rule' if supported else 'guidance-context' if context else 'blocked',
                blocker_ids=[] if supported or context else [b['id'] for b in state['authority_blockers']]))
    state['extensions'] = {'u09_authority':dict(schema_version=VERSION, value=accounting)}
    consumed = {s['id'] for s in chain[1]['state']['sources'] if s['source_id'] in SOURCES}
    consumed.update(eid for collection in ('binding_rules','timing_rules','guidance_context')
                    for r in state[collection] for eid in r['evidence_ids'])
    predecessor = dict(snapshot_id=chain[1]['snapshot_id'], path=SNAPSHOT_PATHS[1], sha256=sha256_bytes(_read(root,SNAPSHOT_PATHS[1])))
    status = reduce_states([chain[1]['status'], 'blocked' if problems else 'complete'])
    third = _snapshot(store, 3, state, status, store.providers, predecessor=predecessor, consumed=sorted(consumed))
    if value is not None and value['exchange'].disposition == 'proposed':
        third['interpretation_bindings'] = [pointers]
    if write:
        write_snapshot(root, third, upstream=chain)
        validate_authority(store)
    return third


def validate_authority(store):
    """Reject semantic projection changes even after successor hashes are rebuilt."""
    actual = read_chain(store.root, count=3)[2]
    expected = freeze_authority(store, write=False)
    def canonical(snapshot):
        rule_ids = {r['id']:r['rule_version_id'] for r in snapshot['state']['binding_rules']}
        blocker_ids = {b['id']:b['reason'] for b in snapshot['state']['authority_blockers']}
        state = deepcopy(snapshot['state'])
        for collection in ('binding_rules','timing_rules','guidance_context','authority_blockers'):
            for record in state[collection]:
                record.pop('id')
                if 'rule_id' in record:
                    record['rule_id'] = rule_ids[record['rule_id']]
        for candidate in state['extensions']['u09_authority']['value']['candidates']:
            candidate['rule_id'] = rule_ids[candidate['rule_id']]
        for review in state['extensions']['u09_authority']['value']['candidate_reviews']:
            review['blocker_ids'] = [blocker_ids[i] for i in review['blocker_ids']]
        return json_bytes(dict(state=state, status=snapshot['status'], consumed=snapshot['consumed_record_ids'],
            bindings=snapshot.get('interpretation_bindings',[])))
    require(actual['decisions'] == expected['decisions'] and actual['unresolved'] == expected['unresolved'] and
            canonical(actual) == canonical(expected), 'Stage 03 differs from verified authority interpretation and prerequisites')
    return actual


def interpret_authority(store, config, *, timeout=180):
    """Single restricted skill invocation; no source retrieval or human transfer."""
    root = store.root
    from .runner import validate_slice
    chain = list(validate_slice(store))
    ids = [e['id'] for e in chain[1]['state']['evidence'] if e['assertion'].startswith('Captured legal/context page body for ')]
    if prerequisites(chain) or not ids:
        return freeze_authority(store)
    host, version = preflight(config)
    shutil.copytree(SKILL, root/SKILL.name, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(SKILL.parent/'snapshot.schema.json', root/'snapshot.schema.json')
    registration = root/'.agents/skills'
    registration.mkdir(parents=True)
    (registration/SKILL.name).symlink_to('../../' + SKILL.name, target_is_directory=True)
    def pointer(path):
        return dict(path=path, sha256=sha256_bytes(package_path(root,path).read_bytes()))
    metadata = dict(host_version=version, requested_model=config['host']['model'], requested_effort=config['host']['effort'],
        reported_model=None, reported_effort=None, usage=None,
        instruction_versions=[pointer(SKILL.name+'/SKILL.md'),pointer(SKILL.name+'/references/authority-policy.md')],
        reference_versions=[pointer(SKILL.name+'/references/contracts.md'),pointer(SKILL.name+'/references/schemas/authority-basis.schema.json')])
    create_authority_request(root, ids, metadata, providers=store.providers)
    immutable = file_inventory(root)
    helper = root/SKILL.name/'scripts/stage.py'
    command = host_command(host, root, config['host']['model'], config['host']['effort'])
    prompt = (f'Use $regulatory-change-impact-brief U09 authority branch. Run root: {root}. '
        f'Read {root/SKILL.name}/references/authority-policy.md and analysis/authority/request.json. '
        f'Submit once: {sys.executable} {helper} submit-authority --root {root} '
        f'--proposal {root}/analysis/authority/agent-proposal.json. Stop after submission; supervisor writes Stage 03. No later units.')
    _write(root,'analysis/host-prompt.txt',prompt.encode())
    _write(root,'analysis/host-invocation.json',json_bytes(dict(command=command,metadata=metadata)))
    invoke_host(command,prompt,root,timeout)
    verify_inventory(root,immutable)
    require((root/'analysis/authority/submission.json').is_file(), 'host did not submit authority')
    _write(root,'analysis/authority/host-outcome.json',json_bytes(dict(visible_usage=visible_usage(root),production_package=False)))
    return freeze_authority(store)


def create_authority_request(root, evidence_ids, metadata, *, providers=None):
    # Reuse the frozen U08 packet builder in a dedicated authority run; preserve
    # its original packet and a distinct authority submission path.
    from .interpretation import create_request
    require(not (root/'analysis/request.json').exists(), 'authority branch requires a fresh dedicated exchange run')
    request = create_request(root,evidence_ids=evidence_ids,metadata=metadata,providers=providers)
    _write(root,'analysis/authority/request.json',_read(root,'analysis/request.json'))
    return request
