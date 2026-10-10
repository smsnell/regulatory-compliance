"""U08 immutable skill exchange and derived-analysis logging; no model client.

The G1 validator is authoritative. This module retains even rejected bytes and
supplies only validated draft candidates to downstream deterministic helpers.
"""
from copy import deepcopy
import shutil
import sys
from uuid import uuid4

from .contracts import (ASSIGNED_REVIEW_DATE, SNAPSHOT_PATHS, STAGES, ContractError,
    json_bytes, package_path, parse_json, require, sha256_bytes, validate_schema,
    validate_interpretation, ExchangeResult)
from .evidence import _read, _write
from .normalize import load_dictionary
from .runtime import (SKILL, Providers, file_inventory, host_command, invoke_host,
    preflight, verify_inventory, visible_usage)
from .snapshots import read_chain


def validate_report_exchange(request_bytes, response_bytes, *, root, run_id, stage):
    require(isinstance(parse_json(request_bytes), dict) and isinstance(parse_json(response_bytes), dict),
            'interpretation envelope must be an object')
    upstream = read_chain(root, count=STAGES.index(stage))
    result = validate_interpretation(request_bytes, response_bytes, root=root,
        run_id=run_id, stage=stage, upstream=upstream)
    if result.disposition != 'proposed':
        return result
    reports = upstream[1]['state'].get('extensions', {}).get('u08_reports')
    require(reports is not None, 'report exchange requires U08 capture accounting')
    scope = {eid:r['system_id'] for r in reports['value']['reports'] for eid in r['evidence_ids']}
    for candidate in result.response['candidates']:
        cited_systems = {scope[c['evidence_id']] for c in candidate['citations'] if c['evidence_id'] in scope}
        if not set(candidate['system_ids']) <= cited_systems:
            return ExchangeResult('unresolved', result.response, 'No captured report support for candidate system; register status alone is insufficient')
    return result


def create_request(root, *, evidence_ids, stage='authority-and-timing', metadata,
                   providers=None):
    providers = providers or Providers()
    upstream = read_chain(root, count=STAGES.index(stage))
    records = {r['id']:r for s in upstream for values in s['state'].values()
               if isinstance(values, list) for r in values if isinstance(r, dict) and 'id' in r}
    extracts = []
    require(len(set(evidence_ids)) == len(evidence_ids) and evidence_ids, 'distinct captured evidence required')
    for eid in evidence_ids:
        evidence = records.get(eid)
        require(evidence is not None and evidence['record_type'] == 'evidence', 'invented request evidence')
        capture = records[evidence['capture_id']]
        if 'derived_from_capture_id' in capture:
            parent = records[capture['derived_from_capture_id']]
            require(capture['derivation']['method'] == 'HTMLParser visible text (no scripts/styles)' and
                    parent['content_type'].split(';')[0].strip().lower() == 'text/html',
                    'OCR or other derived representation requires verified fidelity; no original text assumed')
        require(capture['content_type'].split(';')[0].strip().lower() in {'text/plain','text/csv'},
                'interpretation requires retained UTF-8 text; binary/OCR fidelity is unresolved')
        text = _read(root, evidence['local_reference']).decode('utf-8')
        extracts.append(dict(evidence_id=eid, capture_id=capture['id'], path=evidence['local_reference'],
            sha256=evidence['content_hash'], locator=evidence['locator'], text=text,
            text_sha256=sha256_bytes(text.encode('utf-8'))))
    dictionary = load_dictionary()
    request = dict(schema_version='rci-interpretation-request/1', packet_id='packet-' + uuid4().hex,
        run_id=upstream[0]['run_id'], stage=stage, created_at=providers.now(),
        assigned_review_date=ASSIGNED_REVIEW_DATE, expected_response_schema='rci-interpretation-response/1',
        upstream=[dict(snapshot_id=s['snapshot_id'], sequence=s['sequence'], path=SNAPSHOT_PATHS[s['sequence']-1],
            sha256=sha256_bytes(_read(root, SNAPSHOT_PATHS[s['sequence']-1]))) for s in upstream],
        extracts=extracts, field_dictionary=dict(version=dictionary['schema_version'], fields=dictionary,
            sha256=sha256_bytes(json_bytes(dictionary))), metadata=deepcopy(metadata))
    validate_schema(request, 'interpretation-request')
    raw = json_bytes(request)
    _write(root, 'analysis/request.json', raw)
    return request


def retain_exchange(root, request_bytes, response_bytes, *, run_id, stage, providers=None):
    """Persist exact input/output BEFORE parsing or validation, on every outcome."""
    providers = providers or Providers()
    directory = 'analysis/exchanges/' + uuid4().hex
    _write(root, directory + '/request.json', request_bytes)
    _write(root, directory + '/response.json', response_bytes)
    pointers = {name:{'path':directory + '/' + name + '.json', 'sha256':sha256_bytes(raw)}
                for name,raw in [('request',request_bytes),('response',response_bytes)]}
    result = None
    try:
        result = validate_report_exchange(request_bytes, response_bytes, root=root, run_id=run_id, stage=stage)
        status, reason = result.disposition, result.reason
    except (ValueError, OSError) as error:
        status, reason = 'failed', str(error)
        raise
    finally:
        _write(root, directory + '/validation.json', json_bytes(dict(run_id=run_id, stage=stage,
            checked_at=providers.now(), status=status, reason=reason, **pointers,
            source_evidence=False, semantic_proof=False)))
    return result, pointers


def submit_report(root, proposal_bytes, *, providers=None):
    providers = providers or Providers()
    _write(root, 'analysis/proposal.json', proposal_bytes)
    request_bytes = _read(root, 'analysis/request.json')
    request = parse_json(request_bytes)
    try:
        proposal = parse_json(proposal_bytes)
        require(isinstance(proposal, dict) and set(proposal) == {'disposition','diagnostic','candidates'}, 'invalid proposal fields')
    except ContractError:
        # A malformed agent proposal is a technical parse failure, with its exact
        # bytes retained as the rejected response, never repaired into certainty.
        retain_exchange(root, request_bytes, proposal_bytes, run_id=root.name, stage=request['stage'], providers=providers)
        raise
    metadata = deepcopy(request['metadata'])
    metadata.update(reported_model=None, reported_effort=None, usage=None)
    raw = json_bytes(dict(**proposal, schema_version='rci-interpretation-response/1',
        run_id=request['run_id'], stage=request['stage'], packet_id=request['packet_id'],
        packet_sha256=sha256_bytes(request_bytes), responded_at=providers.now(), metadata=metadata))
    _write(root, 'analysis/response.json', raw)
    result, pointers = retain_exchange(root, request_bytes, raw, run_id=root.name,
        stage=request['stage'], providers=providers)
    # This is a derived handoff, not a primary claim or a Stage 03 authority record.
    _write(root, 'analysis/accepted-candidates.json', json_bytes(dict(run_id=root.name,
        disposition=result.disposition, reason=result.reason, **pointers,
        candidates=result.response['candidates'] if result.disposition == 'proposed' else [],
        authority='draft-candidates-only')))
    return dict(disposition=result.disposition, reason=result.reason, response_sha256=sha256_bytes(raw),
                production_package=False)


def read_candidates(root):
    """Independent deterministic consumption; a generated handoff is no authority."""
    handoff = parse_json(_read(root, 'analysis/accepted-candidates.json'))
    require(isinstance(handoff, dict) and set(handoff) ==
            {'run_id','disposition','reason','request','response','candidates','authority'}, 'invalid derived handoff')
    for name in ('request','response'):
        pointer = handoff[name]
        require(isinstance(pointer, dict) and set(pointer) == {'path','sha256'} and
                isinstance(pointer['path'], str) and pointer['path'].startswith('analysis/'), 'invalid analysis pointer')
    request = _read(root, handoff['request']['path'])
    response = _read(root, handoff['response']['path'])
    require(sha256_bytes(request) == handoff['request']['sha256'] and
            sha256_bytes(response) == handoff['response']['sha256'], 'changed derived analysis bytes')
    packet = parse_json(request)
    result = validate_report_exchange(request, response, root=root, run_id=root.name, stage=packet['stage'])
    candidates = result.response['candidates'] if result.disposition == 'proposed' else []
    expected = dict(run_id=root.name, disposition=result.disposition, reason=result.reason,
        request=handoff['request'], response=handoff['response'], candidates=candidates, authority='draft-candidates-only')
    require(json_bytes(handoff) == json_bytes(expected), 'derived candidate handoff differs from validated exchange')
    require(request == _read(root, 'analysis/request.json') and
            response == _read(root, 'analysis/response.json'), 'derived handoff points to another exchange')
    return candidates


def interpret_reports(root, config, *, timeout=180):
    chain = read_chain(root, count=2)
    reports = chain[1]['state']['extensions']['u08_reports']['value']['reports']
    ids = [eid for r in reports for eid in r['evidence_ids']]
    if not ids:
        _write(root, 'analysis/interpretation-outcome.json', json_bytes(dict(status='unresolved',
            reason='No captured readable linked reports; report labels cannot support an interpretation',
            candidates=[], production_package=False)))
        return 'unresolved'
    host, version = preflight(config)
    shutil.copytree(SKILL, root/SKILL.name, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(SKILL.parent/'snapshot.schema.json', root/'snapshot.schema.json')
    registration = root/'.agents/skills'
    registration.mkdir(parents=True)
    (registration/SKILL.name).symlink_to('../../' + SKILL.name, target_is_directory=True)
    # Include the captured register table so owner assertions and labels remain
    # available alongside actual report extracts; neither establishes approval.
    ids += [e['id'] for e in chain[1]['state']['evidence'] if 'EVIDENCE' in e['assertion']]
    def pointer(path):
        return dict(path=path, sha256=sha256_bytes(package_path(root, path).read_bytes()))
    metadata = dict(host_version=version, requested_model=config['host']['model'],
        requested_effort=config['host']['effort'], reported_model=None, reported_effort=None, usage=None,
        instruction_versions=[pointer(SKILL.name+'/SKILL.md'),pointer(SKILL.name+'/references/interpretation.md')],
        reference_versions=[pointer(SKILL.name+'/references/contracts.md')])
    create_request(root, evidence_ids=ids, metadata=metadata)
    immutable = file_inventory(root)
    command = host_command(host, root, config['host']['model'], config['host']['effort'])
    helper = root/SKILL.name/'scripts/stage.py'
    prompt = (f'Use $regulatory-change-impact-brief and its U08 report branch. Run root: {root}. '
        f'Read {root/SKILL.name}/references/interpretation.md. Interpret captured reports only. '
        f'Submit once: {sys.executable} {helper} submit-report --root {root} '
        f'--proposal {root}/analysis/agent-proposal.json. Stop after submission; no later units or snapshots.')
    _write(root, 'analysis/host-prompt.txt', prompt.encode('utf-8'))
    _write(root, 'analysis/host-invocation.json', json_bytes(dict(command=command, metadata=metadata)))
    try:
        invoke_host(command, prompt, root, timeout)
        verify_inventory(root, immutable)
        raw = _read(root, 'analysis/response.json')
        result = validate_report_exchange(_read(root, 'analysis/request.json'), raw, root=root,
            run_id=root.name, stage='authority-and-timing')
        read_candidates(root)
        status, reason = result.disposition, result.reason
    except (ValueError, OSError) as error:
        status, reason = 'failed', str(error)
    _write(root, 'analysis/interpretation-outcome.json', json_bytes(dict(status=status, reason=reason,
        visible_usage=visible_usage(root), production_package=False)))
    return status
