"""Deterministic engineering choices projected from this run's durable records.

Stage 01 marks mandatory decisions for new producers. Production validation
preserves verified legacy packages and rejects unproven markerless producers.
The stable snapshot schema is unchanged. Decisions grant no Legal or Operations approval.
"""
from urllib.parse import quote
import re

from .contracts import ContractError, json_bytes, package_path, parse_json, require, sha256_bytes


PROFILE = {'schema_version': 'rci-engineering-decisions/1', 'value': {'stages': [1, 2, 5]}}
PRODUCER_PATH = 'analysis/producer-code.json'
CAPABILITY_PATH = 'scripts/rci/decisions.py'

# Fixed compatibility evidence for pre-remediation producers whose early
# captures did not retain a code inventory/bundle. These are exact producer
# hashes, never an exemption for unknown markerless packages. Witness bytes
# are checked by the remediation regression; runtime does not read outside
# the package or execute historical source code.
LEGACY_PRODUCERS = {
    'sha256:af991973fcec2f42e34089aa574079bebedd774ee94e4739eb4807efcb30f85f': (
        'deliverables/snapshots/01-scope.json',
        'sha256:86a0da272f5a1ed2d3aee182a9398887e6880a5181c1ce5338610b739a0ff0ad'),
    'sha256:92ba7c690fc4f4b46ae3cffcdbec471de77a5188e22a96af292c38559732f3ee': (
        'tests/fixtures/sanitized/u07/.staging/run-6bec153b2d1343a5a43cc2f333798c4d/snapshots/01-scope.json',
        'sha256:2dc92be6a0858ada45e9d37a6de689305a2ae5c5ee5d13fffb36ddcdff90ed5a'),
    'sha256:250a1e3454a4093c0e348f4dee89f55e9ba9d640b80b6acf44986c2f7a24d34e': (
        '.evidence/u20/metamorphic/test_register_reordering_and_e0/original/out/snapshots/01-scope.json',
        'sha256:3982bc3502fd537613d4d0799cb9b9eb1ad7d257a75039d36b911fb09ca3a17f'),
    'sha256:c70dc6959400e5973ae42e0fbb7c3e2c91a179a1ced59f417e4e7001ae5ac271': (
        '.evidence/u20/suite/test_independent_package_corru5/draft/snapshots/01-scope.json',
        'sha256:6f29b824e48c412c2fabff1c0f603d6943f961a813716ca9ad445ce544171a68'),
}


def producer_inventory(skill):
    """Retain the existing code fingerprint's preimage, without executing it."""
    inventory = {}
    for path in sorted(skill.rglob('*')):
        require(not path.is_symlink(), 'unsafe producer code bundle link')
        if path.is_file() and path.suffix in {'.py', '.json', '.md'}:
            inventory[path.relative_to(skill).as_posix()] = sha256_bytes(path.read_bytes())
    return inventory


def validate_producer(root, first):
    """Production provenance guard; generic historical graph checks stay separate.

    Absence of a removable profile never proves a legacy producer. Unknown
    markerless packages need a verified old bundle before production reuse.
    """
    fingerprint = first['state']['code_fingerprint']
    path = package_path(root, PRODUCER_PATH)
    inventory = None
    if path.exists():
        try:
            inventory = parse_json(path.read_bytes())
        except ContractError as exc:
            raise ContractError(f'malformed producer code inventory ({PRODUCER_PATH}): {exc}') from exc
        require(isinstance(inventory, dict) and bool(inventory) and all(
            isinstance(k, str) and bool(k.strip()) and isinstance(v, str) and
            re.fullmatch(r'sha256:[0-9a-f]{64}', v) for k, v in inventory.items()),
            'malformed producer code inventory')
        require(sha256_bytes(json_bytes(inventory)) == fingerprint,
                'producer code inventory fingerprint mismatch')
    if enabled(first):
        # Earlier E04 packages already contain mandatory reconstructed decisions
        # and predate inventory retention. They need no retroactive rewrite.
        return
    require(inventory is None or CAPABILITY_PATH not in inventory,
            'engineering decision profile omitted for decision-capable producer')
    from .runtime import SKILL
    bundle = package_path(root, SKILL.name)
    require(not bundle.exists() or bundle.is_dir(), 'retained producer bundle is not a directory')
    if bundle.is_dir():
        retained = producer_inventory(bundle)
        require(sha256_bytes(json_bytes(retained)) == fingerprint,
                'producer code fingerprint differs from retained bundle')
        require(CAPABILITY_PATH not in retained,
                'engineering decision profile omitted for retained decision-capable producer')
        return
    require(fingerprint in LEGACY_PRODUCERS,
            'unmarked producer lacks verified legacy provenance; decision profile or retained producer evidence required')
    require(sha256_bytes(json_bytes(first)) == LEGACY_PRODUCERS[fingerprint][1],
            'unmarked producer scope differs from exact legacy witness')


def enabled(first):
    profile = first['state'].get('extensions', {}).get('u20_decisions')
    if profile is None:
        return False
    require(profile == PROFILE, 'unsupported engineering decision profile')
    return True


def _decision(snapshot, key, *, summary, evidence_ids=(), source_basis, concern,
              options, chosen, rationale, tradeoffs, downstream):
    # A semantic choice key, scoped to the execution and stage, produces the
    # same ID during independent reconstruction without consuming randomness.
    suffix = sha256_bytes(json_bytes(['rci-engineering-decisions/1', key])).split(':', 1)[1][:32]
    return dict(id=f"record:{quote(snapshot['run_id'], safe='')}:{snapshot['sequence']:02d}:decision:{suffix}",
        record_type='decision', summary=summary, evidence_ids=sorted(set(evidence_ids)),
        concern=concern, options_considered=options, source_basis=list(dict.fromkeys(source_basis)),
        chosen_behavior=chosen, rationale=rationale, tradeoffs=tradeoffs,
        downstream_effect=downstream, decision_basis='rci-engineering-decisions/1:' + key,
        status='provisional-engineering')


def _scope(snapshot):
    state = snapshot['state']
    basis, = state['scope_basis']
    discovered = basis['basis_kind'] == 'discovered'
    provenance = [basis['id'], *basis['source_basis']]
    if discovered:
        provenance += [basis[k] for k in ('attempt_key', 'local_reference', 'content_hash')]
    decisions = [_decision(snapshot, 'scope', summary='Scope input selection',
        source_basis=provenance,
        concern='Scope must use actual authorized system IDs before downstream evidence exists.',
        options=['Use an authorized scope declaration', 'Discover identity from the authorized SYSTEMS route',
                 'Defer when neither can establish actual identities'],
        chosen=f"Freeze {basis['basis_kind']} scope for {', '.join(state['systems_in_scope'])}; " +
            ('import the original SYSTEMS discovery attempt exactly once in Stage 02.' if discovered else
             'corroborate these requested identities against fresh SYSTEMS acquisition in Stage 02.'),
        rationale='The retained ' + ('identity-verified SYSTEMS capture' if discovered else 'authorized declaration') +
            ' establishes the requested identities without claiming current operational facts.',
        tradeoffs=['Identity selection alone does not establish system facts or legal applicability.'],
        downstream='All later stages use this frozen scope; unresolved corroboration remains visible.'),
        _decision(snapshot, 'date', summary='Assigned date precision encoding',
        source_basis=['REQUIREMENTS.md R0/R3/R7', 'snapshot.schema.json as_of',
                      state['assigned_review_date'], state['as_of_precision'], state['as_of']],
        concern='The date-time schema must not invent an intraday legal cutover.',
        options=['Encode the assigned review date with explicit date precision', 'Assert an unsupported intraday cutover'],
        chosen=f"Encode {state['assigned_review_date']} as {state['as_of']} with as_of_precision={state['as_of_precision']}.",
        rationale='Preserves the assigned review date while satisfying the existing date-time contract.',
        tradeoffs=['Timezone and intraday applicability remain unresolved unless separately evidenced.'],
        downstream='Retrieval, observation, legal effective dates and proposed action dates retain their separate bases.')]
    if state['supersedes_run_id'] is not None:
        decisions.append(_decision(snapshot, 'recovery', summary='Fresh run supersession and recovery',
            source_basis=[state['supersedes_run_id'], state['change_reason'], 'analysis/run-context.json'],
            concern='Replacing a previous occurrence must preserve its evidence and avoid reusing stale conclusions.',
            options=['Retain the prior occurrence and fully recompute in a fresh run', 'Reuse earlier stage conclusions'],
            chosen=f"Start fresh run {snapshot['run_id']} superseding {state['supersedes_run_id']}; reason: {state['change_reason']}.",
            rationale='The supervisor identified a retained prior occurrence; fresh acquisition and complete recalculation preserve run isolation.',
            tradeoffs=['All source reads and stage calculations repeat; promotion and archival still require their own successful checks.'],
            downstream='Keep the prior occurrence and any failure evidence; validate the new candidate before replacing current outputs.'))
    return decisions


def _access(snapshot):
    state = snapshot['state']
    decisions = []
    for source in sorted(state['sources'], key=lambda s: s['source_id']):
        attempts = [a for a in state['attempts'] if a['id'] in source['attempt_ids']]
        captures = {c['id'] for c in state['captures'] if c['attempt_id'] in source['attempt_ids']}
        evidence = [e['id'] for e in state['evidence'] if e['capture_id'] in captures]
        outcomes = '; '.join(f"{a['adapter']} {a['effective_locator']}: {a['outcome']} "
                            f"(retrieval={a['retrieval_status']}, identity={a['identity_check']}, "
                            f"selected={str(a['selected']).lower()}); selection reason: {a['selection_reason']}"
                            for a in attempts)
        provenance = [source['id'], source['locator'], *source['attempt_ids']]
        for attempt in attempts:
            provenance.extend(attempt[k] for k in ('attempt_key', 'local_reference', 'content_hash') if attempt[k] is not None)
        decisions.append(_decision(snapshot, 'source:' + source['source_id'],
            summary='Source access: ' + source['source_id'], evidence_ids=evidence, source_basis=provenance,
            concern='An available route or retained response does not establish authoritative usable content.',
            options=['Use configured read adapters and retain every actual outcome',
                     'Defer dependent claims when authorized reads cannot provide suitable evidence'],
            chosen='Retain the actual read attempts and selection decisions: ' + outcomes + '.',
            rationale='Configured reads, retries and permitted access handoffs are recorded by the immutable attempt journal; usable meaning requires later verification.',
            tradeoffs=['Unavailable, partial or unsuitable representations leave dependent facts or authority unresolved.'],
            downstream='Use the linked retained evidence for later assessment; do not infer identity, authority or completion from access success.'))
    return decisions


def _disposition(snapshot):
    state, status = snapshot['state'], snapshot['status']
    coverage = state['extensions']['u11_impacts']['value']['coverage']
    supported = [c for c in coverage if c['state'] in {'supported-impact', 'supported-no-impact'}]
    unresolved = [c for c in coverage if c['state'] in {'unresolved', 'conflicting'}]
    if status in {'blocked', 'failed'}:
        chosen = f'Defer publication and dependent formal conclusions because the run is {status}; retain the assessed and unresolved coverage for repair.'
    elif status == 'partial':
        chosen = ('Continue a bounded partial draft with supported assessments and explicit unresolved scope.' if supported else
                  'Defer unresolved formal conclusions; retain a partial draft of evidence gaps for owner review.')
    else:
        chosen = 'Continue a complete draft of the assessed scope; Legal and Operations decisions remain subject to their separate approval requirements.'
    records = state['impacts'] + state['unaffected_items'] + state['unresolved_items'] + state['conflicts']
    provenance = [r['id'] for r in records]
    provenance += [basis for c in coverage for basis in c.get('source_basis', [])]
    provenance += ['Stage 05 status=' + status,
                   'Supported scope: ' + ', '.join(sorted({c['system_id'] for c in supported})),
                   'Unresolved scope: ' + ', '.join(sorted({c['system_id'] for c in unresolved}))]
    evidence = [e for r in records for e in r['evidence_ids']]
    evidence += [e for c in coverage for e in c['evidence_ids']]
    return [_decision(snapshot, 'disposition', summary='Draft continuation or deferral',
        evidence_ids=evidence, source_basis=provenance,
        concern='Incomplete authority or company evidence must not become an unsupported formal conclusion.',
        options=['Continue a complete assessed draft', 'Continue bounded partial work with visible omissions',
                 'Defer publication and dependent conclusions for authority blockers or technical failure'],
        chosen=chosen,
        rationale=f"The impact stage retained {len(supported)} supported and {len(unresolved)} unresolved scope assessments with status={status}; prior capture limitations remain in their original snapshots.",
        tradeoffs=['A draft status is neither human approval nor evidence that an operational action is complete.'],
        downstream='Stage 06 exports this decision and its basis; Stage 07 independently gates publication and checks rendered artifacts.')]


def project(snapshot):
    """Reconstruct actual choices solely from the snapshot's retained inputs."""
    return {1: _scope, 2: _access, 5: _disposition}.get(snapshot['sequence'], lambda _: [])(snapshot)


def validate(snapshot, upstream):
    first = snapshot if snapshot['sequence'] == 1 else upstream[0]
    if enabled(first):
        require(snapshot['decisions'] == project(snapshot),
                'engineering decisions differ from retained scope, access or disposition basis')
