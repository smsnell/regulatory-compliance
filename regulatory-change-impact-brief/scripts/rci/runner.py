"""U07 immutable scope/capture slice. Later stage engines remain separate units."""
from copy import deepcopy
import csv
import os
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from .adapters import ReadAdapters
from .adapters.anonymous_sheets import csv_rows
from .adapters.readiness import register_readiness
from .contracts import (AS_OF, ASSIGNED_REVIEW_DATE, CONTRACT_VERSION, SNAPSHOT_PATHS,
                        STAGES, ContractError, json_bytes, package_path, parse_json, require, sha256_bytes)
from .evidence import EvidenceStore, _write
from .ids import new_record_id, new_snapshot_id
from .normalize import load_dictionary, normalize_registers, validate_values
from .runtime import Providers, SKILL, output_directory, validate_config, writer_lock
from .snapshots import read_chain, stage_records, write_snapshot
from .source_manifest import disclosed_manifest, manifest


SCOPE_SCHEMA = SKILL / 'references/schemas/scope-input.schema.json'


class ScopeUnavailable(ContractError):
    """Source content cannot establish scope; distinct from broken integrity."""


def _scope_require(condition, reason):
    if not condition:
        raise ScopeUnavailable(reason)


def declared_scope(raw):
    value = parse_json(raw)
    schema = parse_json(SCOPE_SCHEMA.read_bytes())
    require(Draft202012Validator(schema).is_valid(value), 'invalid authorized scope input')
    return value


def discover_scope(store, *, require_eight=True):
    """Establish only identity from a complete U05 SYSTEMS acquisition."""
    register = next(r for r in register_readiness(store)['registers'] if r['source_id'] == 'SYSTEMS')
    _scope_require(register['ready'], 'SYSTEMS scope discovery unavailable or identity unverified')
    spec = load_dictionary()['registers']['SYSTEMS']
    _scope_require(len(register['tabs']) == 1, 'ambiguous SYSTEMS scope tabs')
    tab, = register['tabs']
    _scope_require(tab['title'] == spec['tab_title'], 'unknown SYSTEMS scope tab meaning')
    raw = package_path(store.root, tab['local_reference']).read_bytes()
    try:
        table = csv_rows(raw)
    except (ValueError, csv.Error) as error:
        raise ScopeUnavailable('Unreadable SYSTEMS scope table') from error
    header = spec['identity_header']
    _scope_require(table[0].count(header) == 1, 'missing or ambiguous system ID header')
    column = table[0].index(header)
    _scope_require(all(len(row) == len(table[0]) for row in table[1:]), 'malformed SYSTEMS scope rows')
    ids = [row[column] for row in table[1:]]
    _scope_require(ids and len(ids) == len(set(ids)) and all(i.strip() for i in ids),
            'scope discovery requires distinct nonempty actual IDs')
    _scope_require(not require_eight or len(ids) == 8, 'scope discovery requires eight actual IDs')
    event = next(e for e in store.inventory() if e['attempt']['id'] == tab['attempt_id'])
    return sorted(ids), event


def _snapshot(store, sequence, state, status, providers, predecessor=None, consumed=()):
    snapshot = dict(schema_version='regulatory-compliance-stage-snapshot/2',
        contract_version=CONTRACT_VERSION, snapshot_id=new_snapshot_id(), run_id=store.run_id,
        stage=STAGES[sequence - 1], sequence=sequence, created_at=providers.now(), status=status,
        predecessor=predecessor, consumed_record_ids=list(consumed), produced_record_ids=[],
        state=state, decisions=[], unresolved=[])
    snapshot['produced_record_ids'] = [r['id'] for r in stage_records(snapshot)]
    return snapshot


def _diagnostic(store, reason, basis, evidence=()):
    return dict(id=new_record_id(store.run_id, 2, 'diagnostic'), record_type='diagnostic',
        summary=reason, evidence_ids=list(evidence), source_basis=list(basis), reason=reason,
        owner=None, resolution_need='Source owner must verify scope or provide suitable current evidence; use a new run for any scope change.')


def _technical_failures(events):
    # U04 uses ReadFailure for unsuitable/unavailable source responses. Storage
    # failures carry their actual exception type; interruptions are technical.
    return [e for e in events if e['diagnostic'] is not None and (
        e['diagnostic']['failure_type'] != 'ReadFailure' or
        e['attempt']['outcome'] in {'Interrupted', 'KeyboardInterrupt', 'SystemExit'} or
        e['attempt']['recoverable_failure'] == 'Adapter output or capture finalization failed')]


def _scope_comparison(ids, current):
    return dict(requested_ids=ids, current_ids=current,
        missing_ids=sorted(set(ids) - set(current)) if current is not None else None,
        additional_ids=sorted(set(current) - set(ids)) if current is not None else None,
        result='unverified' if current is None else 'matched' if set(ids) == set(current) else 'different')


def _capture_diagnostics(store, normalized, events, basis, comparison, scope_reason):
    diagnostics = list(normalized['diagnostics'])
    technical_keys = {e['attempt']['attempt_key'] for e in _technical_failures(events)}
    for event in events:
        attempt = event['attempt']
        if attempt['retrieval_status'] != 'retrieved':
            diagnostic = _diagnostic(store,
                f"{attempt['source_id']}: {attempt['selection_reason']} ({attempt['retrieval_status']})",
                [attempt['original_locator'], attempt['attempt_key']])
            if attempt['attempt_key'] in technical_keys:
                diagnostic['resolution_need'] = 'Operator must preserve this failed occurrence, repair the technical failure and rerun with fresh source attempts.'
            diagnostics.append(diagnostic)
    if comparison['result'] == 'unverified':
        diagnostics.append(_diagnostic(store, 'Current SYSTEMS scope cannot be corroborated: ' + scope_reason, ['SYSTEMS']))
    elif comparison['result'] == 'different':
        diagnostics.append(_diagnostic(store, 'Current SYSTEMS IDs differ from frozen requested scope', ['SYSTEMS', basis['id']],
            [e['id'] for e in normalized['evidence'] if 'SYSTEMS' in e['assertion']]))
    return diagnostics


def _capture_status(events, diagnostics):
    return 'failed' if _technical_failures(events) else 'partial' if diagnostics else 'complete'


def _source_role(source_id):
    return ('operational-record' if source_id in {'SYSTEMS', 'EVIDENCE', 'CALENDAR'} else
            'internal-policy' if source_id == 'POLICY' else
            'official-guidance' if source_id in {'TIME', 'FAQ'} else 'binding-regulation')


def _record_values(records, evidence):
    """Compare complete records independent of freshly generated execution IDs.

    Resolve evidence IDs to exact capture/claim values before comparison. JSON
    bytes preserve type distinctions (true != 1) and duplicate cardinality.
    """
    index = {e['id']: e for e in evidence}
    values = []
    for record in records:
        value = {k: v for k, v in record.items() if k not in {'id', 'evidence_ids'}}
        value['evidence_ids'] = sorted(json_bytes({k: v for k, v in index[i].items() if k != 'id'}).decode('utf-8')
                                       for i in record['evidence_ids'])
        values.append(json_bytes(value))
    return sorted(values)


def run_stages(store, config, sources, reader, *, config_bytes, providers,
               scope_bytes=None, supersedes_run_id=None, change_reason=None):
    """Injectable execution seam; production supplies live adapters only."""
    discovery = None
    if scope_bytes is None:
        reader.read(next(s for s in sources if s.id == 'SYSTEMS'))
        require(not _technical_failures(store.inventory()), 'Technical scope discovery capture failure; fresh run required')
        ids, discovery = discover_scope(store)
        basis = dict(basis_kind='discovered', system_ids=ids,
            basis_version='rci-scope-discovery/1', authorized_by='Interview 03:08/03:21 and authorized SYSTEMS route',
            source_basis=['interviews/interview-B-3.md 03:08/03:21', discovery['attempt']['original_locator'],
                          'SYSTEMS system_id column; complete identity-verified tab'],
            **{k: discovery['attempt'][k] for k in ('attempt_key','retrieved_at','local_reference','content_hash')})
    else:
        declaration = declared_scope(scope_bytes)
        ids = declaration['system_ids']
        basis = dict(declaration, basis_kind='declared', attempt_key=None, retrieved_at=None,
                     local_reference=None, content_hash=None)
        basis.pop('schema_version')
        basis['source_basis'] = basis['source_basis'] + ['analysis/scope-input.json', sha256_bytes(scope_bytes)]
    basis.update(id=new_record_id(store.run_id, 1, 'scope-basis'), record_type='scope-basis',
                 summary='Eight actual requested system IDs; current operational facts require fresh corroboration.', evidence_ids=[])
    state = dict(as_of=AS_OF, as_of_precision='date', assigned_review_date=ASSIGNED_REVIEW_DATE,
        review_type='Article 50 EU programme draft review', systems_in_scope=ids,
        audiences=config['recipients'], approval_gates=['Legal final interpretations and exceptions',
        'Operations dates, activation and incident closure'], scope_basis=[basis],
        supersedes_run_id=supersedes_run_id, change_reason=change_reason,
        config_fingerprint=sha256_bytes(config_bytes), code_fingerprint=_code_fingerprint(),
        extensions={'u07_sources': {'schema_version':'rci-source-declarations/1',
                                  'value':{'sources':deepcopy(config['sources'])}}})
    first = _snapshot(store, 1, state, 'complete', providers)
    pointer = write_snapshot(store.root, first, upstream=[])
    for source in sources:
        if discovery is None or source.id != 'SYSTEMS':
            reader.read(source)
    events = store.inventory()  # Every start must be terminal and bytes independently verified.
    require({e['attempt']['source_id'] for e in events} == {s.id for s in sources}, 'missing core source attempts')
    normalized = normalize_registers(store)
    attempts = [deepcopy(e['attempt']) for e in events]
    if discovery is not None:
        attempt = next(a for a in attempts if a['attempt_key'] == basis['attempt_key'])
        attempt['scope_basis_id'] = basis['id']  # Projection only; immutable original journal stays unchanged.
    captures = [e['capture'] for e in events if e['capture'] is not None]
    records = []
    for source in sources:
        reads = sorted((a for a in attempts if a['source_id'] == source.id), key=lambda a: a['started_at'])
        last = reads[-1]
        # Route role is a declaration; actual authority is deliberately unknown until U09.
        records.append(dict(id=new_record_id(store.run_id, 2, 'source'), record_type='source',
            summary=f'{source.id}: {len(reads)} fresh attempts retained; identity and date checks remain separate.',
            evidence_ids=[], source_id=source.id, source_role=_source_role(source.id), authority='unknown', locator=source.route,
            attempt_ids=[a['id'] for a in reads], **{k:last[k] for k in (
                'retrieved_at','retrieval_status','content_type','version_metadata','local_reference','content_hash')}))
    scope_reason = None
    try:
        current, _ = discover_scope(store, require_eight=False)
    except ScopeUnavailable as error:
        current = None
        scope_reason = str(error)
    comparison = _scope_comparison(ids, current)
    diagnostics = _capture_diagnostics(store, normalized, events, basis, comparison, scope_reason)
    state = dict(sources=records, attempts=attempts, captures=captures,
        **{k:normalized[k] for k in ('evidence','normalized_rows','mappings')}, diagnostics=diagnostics,
        extensions={'u07_capture': {'schema_version':'rci-capture-accounting/1', 'value':{
            'required_source_ids':[s.id for s in sources], 'scope_comparison':comparison,
            'raw_tables':normalized['raw_tables'], 'technical_diagnostics':[e['diagnostic'] for e in events if e['diagnostic']],
            'boundary':'U07 core capture only; linked reports and interpretation require a subsequent U08 run'}}})
    second = _snapshot(store, 2, state, _capture_status(events, diagnostics), providers,
                       predecessor={k:pointer[k] for k in ('snapshot_id','path','sha256')}, consumed=[basis['id']])
    write_snapshot(store.root, second, upstream=read_chain(store.root, count=1))
    validate_slice(store)
    return comparison, second['status']


def validate_slice(store):
    """Re-read frozen files and check U07's supplemental accounting against the journal."""
    first, second = read_chain(store.root, count=2)
    config_bytes = (store.root / 'analysis/config.json').read_bytes()
    config = validate_config(parse_json(config_bytes))
    require(first['state']['config_fingerprint'] == sha256_bytes(config_bytes), 'config fingerprint changed')
    declared = first['state']['extensions']['u07_sources']
    require(declared == {'schema_version':'rci-source-declarations/1', 'value':{'sources':config['sources']}},
            'source declaration accounting changed')
    extension = second['state']['extensions']['u07_capture']
    schema = parse_json((SKILL / 'references/schemas/capture-accounting.schema.json').read_bytes())
    require(extension['schema_version'] == 'rci-capture-accounting/1' and
            Draft202012Validator(schema).is_valid(extension['value']), 'invalid capture accounting')
    accounting = extension['value']
    require(accounting['required_source_ids'] == [s['id'] for s in config['sources']], 'required source inventory changed')
    events = store.inventory()
    sources = {s['id']: s for s in config['sources']}
    require({s['source_id'] for s in second['state']['sources']} == set(sources) and
            {e['attempt']['source_id'] for e in events} == set(sources), 'missing required source attempts')
    for source in second['state']['sources']:
        declaration = sources[source['source_id']]
        require(source['locator'] == declaration['route'] and source['authority'] == 'unknown' and
                source['source_role'] == _source_role(source['source_id']), 'source record differs from authorized declaration')
    for event in events:
        attempt = event['attempt']
        declaration = sources[attempt['source_id']]
        adapters = {declaration['adapter']}
        if declaration['adapter'] == 'google-sheets-read':
            adapters.add('http-read')  # U05 anonymous Sheets handoff.
        require(attempt['original_locator'] == declaration['route'] and attempt['adapter'] in adapters,
                'attempt differs from authorized source route or adapter')
    originals = {e['attempt']['id']:e for e in events}
    require(set(originals) == {a['id'] for a in second['state']['attempts']}, 'journal attempt inventory differs')
    for attempt in second['state']['attempts']:
        projection = dict(attempt)
        projection.pop('scope_basis_id', None)
        require(projection == originals[attempt['id']]['attempt'], 'original journal provenance changed')
    require(second['state']['captures'] == [e['capture'] for e in events if e['capture']],
            'journal capture inventory differs')
    require(accounting['technical_diagnostics'] == [e['diagnostic'] for e in events if e['diagnostic']],
            'technical diagnostic accounting differs')
    for table in accounting['raw_tables']:
        require(len(table['source_basis']) == 3, 'invalid raw table source basis')
        path, digest = table['source_basis'][1:3]
        require(any(e['attempt']['source_id'] == table['source_id'] and e['capture'] is not None and
                    e['capture']['local_reference'] == path and e['capture']['content_hash'] == digest for e in events),
                'raw table basis is not an original register capture')
        raw = package_path(store.root, path).read_bytes()
        require(sha256_bytes(raw) == digest and csv_rows(raw) == table['rows'], 'raw table accounting differs from capture')
    normalized = normalize_registers(store)  # Recompute from independently reread, identity-verified capture bytes.
    require(sorted(map(json_bytes, accounting['raw_tables'])) == sorted(map(json_bytes, normalized['raw_tables'])),
            'raw table accounting incomplete or changed')
    for row in second['state']['normalized_rows']:
        validate_values(row['values'])
    for collection in ('evidence', 'normalized_rows', 'mappings'):
        require(_record_values(second['state'][collection], second['state']['evidence']) ==
                _record_values(normalized[collection], normalized['evidence']),
                collection + ' differ from retained register normalization')
    scope_reason = None
    try:
        current, _ = discover_scope(store, require_eight=False)
    except ScopeUnavailable as error:
        current = None
        scope_reason = str(error)
    ids = first['state']['systems_in_scope']
    basis, = first['state']['scope_basis']
    if basis['basis_kind'] == 'discovered':
        require(current == ids, 'discovered scope differs from captured IDs')
    else:
        scope_bytes = (store.root / 'analysis/scope-input.json').read_bytes()
        declaration = declared_scope(scope_bytes)
        require(all(basis[k] == declaration[k] for k in ('system_ids','basis_version','authorized_by')) and
                basis['source_basis'] == declaration['source_basis'] + ['analysis/scope-input.json',sha256_bytes(scope_bytes)],
                'declared scope differs from retained authorization input')
    expected = _scope_comparison(ids, current)
    require(accounting['scope_comparison'] == expected, 'scope comparison differs from retained IDs')
    diagnostics = _capture_diagnostics(store, normalized, events, basis, expected, scope_reason)
    require(_record_values(second['state']['diagnostics'], second['state']['evidence']) ==
            _record_values(diagnostics, normalized['evidence']), 'capture diagnostics differ from retained inputs')
    require(second['status'] == _capture_status(events, diagnostics), 'capture stage conceals failure or limitations')
    return first, second


def _code_fingerprint():
    return sha256_bytes(json_bytes({p.relative_to(SKILL).as_posix():sha256_bytes(p.read_bytes())
        for p in sorted(SKILL.rglob('*')) if p.is_file() and p.suffix in {'.py','.json','.md'}}))


def capture_slice(config_path, *, scope_path=None, supersedes_run_id=None, change_reason=None,
                  providers=None, reader_factory=ReadAdapters):
    require(not os.environ.get('RCI_CHILD_RUN'), 'recursive supervisor launch rejected')
    config_bytes = config_path.read_bytes()
    config = validate_config(parse_json(config_bytes))
    root = output_directory(config['output_root'], config_path)
    sources = manifest(config)
    # U05/U06 currently verify only the disclosed register routes; fail explicitly for alternatives.
    supported = {s.id:s for s in disclosed_manifest() if s.adapter == 'google-sheets-read'}
    require(all(s.id not in supported or s == supported[s.id] for s in sources), 'unsupported register route for U05/U06 handoff')
    scope_bytes = scope_path.read_bytes() if scope_path is not None else None
    if scope_bytes is not None:
        declared_scope(scope_bytes)
        require(not scope_path.resolve().is_relative_to(root), 'scope input overlaps output root')
    current_scope = root / SNAPSHOT_PATHS[0]
    if current_scope.exists() or current_scope.is_symlink():
        previous = read_chain(root, count=1)[0]
        require(supersedes_run_id in {None, previous['run_id']}, 'retry disagrees with current run')
        supersedes_run_id = previous['run_id']
    if supersedes_run_id is not None:
        require(re.fullmatch(r'run-[A-Za-z0-9-]+', supersedes_run_id) and change_reason and change_reason.strip(),
                'retry requires retained run ID and change reason')
    providers = providers or Providers()
    with writer_lock(root):
        if supersedes_run_id is not None:
            old = root / '.staging' / supersedes_run_id / 'analysis/outcome.json'
            require((current_scope.is_file() and read_chain(root, count=1)[0]['run_id'] == supersedes_run_id) or
                    (old.is_file() and not old.is_symlink() and parse_json(old.read_bytes())['run_id'] == supersedes_run_id),
                    'superseded occurrence not retained in this output root')
        staging = root / '.staging'
        require(not staging.is_symlink(), 'unsafe staging root')
        run_id = providers.run_id()
        candidate = staging / run_id
        candidate.mkdir(parents=True, exist_ok=False)
        store = EvidenceStore(candidate, run_id, providers)
        _write(candidate, 'analysis/config.json', config_bytes)
        if scope_bytes is not None:
            _write(candidate, 'analysis/scope-input.json', scope_bytes)
        started_at = providers.now()
        _write(candidate, 'analysis/run-context.json', json_bytes(dict(run_id=run_id,
            mode='u07-capture-slice', started_at=started_at, supersedes_run_id=supersedes_run_id,
            change_reason=change_reason)))
        reader = reader_factory(store)
        try:
            comparison, status = run_stages(store, config, sources, reader, config_bytes=config_bytes,
                providers=providers, scope_bytes=scope_bytes, supersedes_run_id=supersedes_run_id, change_reason=change_reason)
            outcome = dict(status='failed' if status == 'failed' else 'blocked',
                reason='Technical source capture failure; preserve this occurrence and rerun after repair' if status == 'failed' else
                       'U07 slice finished; stages 03–07 and final artifacts are not implemented',
                capture_slice_complete=status != 'failed', scope_comparison=comparison)
        except ScopeUnavailable as error:
            outcome = dict(status='blocked', reason=str(error), capture_slice_complete=False)
        except (ValueError, OSError, KeyboardInterrupt) as error:
            outcome = dict(status='failed',
                reason='Capture interrupted' if isinstance(error, KeyboardInterrupt) else str(error), capture_slice_complete=False)
        finally:
            reader.close()
        outcome.update(run_id=run_id, candidate=candidate.relative_to(root.parent).as_posix(),
            production_package=False, package_acceptance=False,
            missing_snapshots=[p for p in SNAPSHOT_PATHS if not (candidate/p).is_file()],
            missing_artifacts=['impact-register.csv','compliance-brief.md','action-calendar.ics'])
        _write(candidate, 'analysis/outcome.json', json_bytes(outcome))
        return outcome
