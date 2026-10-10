"""Fully assessed synthetic reports preserve immutable capture limitations.

All company tables, reports, policy and law below are synthetic test inputs.
The real supervisor, submission helpers, snapshots and validators run normally.
"""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import httpx
import pytest

from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes
from rci.history import archive_current, managed_paths, verify_archive
from rci.reconcile import PREDICATES, _capture_resolution, resolved_run_status
from rci.runtime import SKILL
from rci.snapshots import _reviewed_request, accept_package, read_chain
from rci.validate import validate_package
from runtime.test_u07 import CAPTURES, CONFIG, DECLARED, RESPONSES
from runtime.test_u09 import SOURCE_TEXT, proposal as authority_proposal
from runtime.test_u10 import CompanyReplay


SCOPE = 'synthetic public output'
PREDICATE = 'notice is absent'
EXCEPTION = 'No exception claimed'
OBLIGATION = 'Deployers disclose synthetic AI output when notice is absent and no exception is claimed.'
TIMING = 'Synthetic rule applies from 2026-08-02 until 2027-01-01 exclusively.'
CONTROL = 'Provide a notice for synthetic public output; absence of notice triggers review.'
POLICY = ('SYNTHETIC POLICY ONLY. Quillhaven ALL systems internal policy P-v1 effective from '
          '2026-08-01 active through 2027-01-01 exclusively. ' + CONTROL)
OWNER = 'Synthetic Operations'
VALUES = dict(notice_present=False, notice_before_first_interaction=False,
              machine_readable_provenance=True, provider_role=False, deployer_role=True,
              output_scope=SCOPE, exposed_group='public', human_review_path='staff review',
              exception_claim=EXCEPTION)


def route(system):
    return 'https://reports.example.org/full-' + system.lower()


def report(system):
    declaration = 'This report completely covers ' + SCOPE + ' on 2026-08-26.'
    lines = ['SYNTHETIC TEST ONLY. ' + system + '; owner ' + OWNER + '.', declaration]
    for predicate, value in VALUES.items():
        text = str(value).lower() if isinstance(value, bool) else value
        lines.append(system + ' ' + SCOPE + ' ' + predicate + ': ' + text + ' on 2026-08-26.')
    return '\n'.join(lines)


class FullReplay(CompanyReplay):
    # CompanyReplay applies this same transformation to native preview and CSV.
    mutation = 'fully-assessed-synthetic'

    def table(self, table):
        headers = table[0]
        if headers[0] == 'system_id':
            rows = [dict(system_id=s, system_name='Synthetic ' + s, use_case='Synthetic public interaction',
                         owner=OWNER, provider_role='no', deployer_role='yes', exposed_group='public',
                         output_type='direct_interaction', current_notice='no', human_review='staff review',
                         evidence_status='complete', evidence_updated_at='2026-08-26',
                         record_version='synthetic-full-v1') for s in DECLARED['system_ids']]
        elif headers[0] == 'record_id':
            rows = [dict(record_id='REC-' + s[3:], system_id=s, record_type='evidence', reported_at='2026-08-26',
                         owner=OWNER, status='closed', evidence_ref=route(s), evidence_state='complete',
                         notes='Synthetic reviewed report, no exception requested') for s in DECLARED['system_ids']]
        elif headers[0] == 'action_id':
            rows = [dict(action_id='ACT-' + s[3:], system_id=s, action='Review synthetic disclosure evidence',
                         owner=OWNER, due_date='2026-09-04', status='planned', approval_required='legal',
                         source_version='synthetic-full-v1') for s in DECLARED['system_ids']]
        else:
            return table
        return [headers] + [[row[h] for h in headers] for row in rows]

    def handler(self, request):
        url = str(request.url)
        system = next((s for s in DECLARED['system_ids'] if url == route(s)), None)
        if system:
            self.calls.append(url)
            return httpx.Response(200, content=report(system).encode(), headers={'Content-Type':'text/plain'})
        source = next((s['id'] for s in CONFIG['sources'] if s['route'] == url and s['id'] in SOURCE_TEXT), None)
        if source:
            self.calls.append(url)
            title = {'LAW':'Article 50', 'OJ':'Regulation 2024/1689', 'TIME':'Implementation timeline',
                     'FAQ':'Transparency obligations under Article 50'}.get(source, source)
            text = [*SOURCE_TEXT[source], 'SYNTHETIC TEST ONLY, NOT LEGISLATION.',
                    OBLIGATION, PREDICATE, SCOPE, EXCEPTION, TIMING]
            raw = '<html><title>' + title + '</title><h1>' + title + '</h1>' + ''.join(
                '<p>' + line + '</p>' for line in text) + '</html>'
            return httpx.Response(200, content=raw.encode(), headers={'Content-Type':'text/html'})
        policy = next(s['route'] for s in CONFIG['sources'] if s['id'] == 'POLICY')
        if url == policy:
            self.calls.append(url)
            title = 'Project 2 Regulatory Compliance Current Internal Policies'
            return httpx.Response(200, content=('<html><title>' + title + '</title><h1>' + title +
                '</h1><p>' + POLICY + '</p></html>').encode(), headers={'Content-Type':'text/html'})
        sheet = next((s for s in CONFIG['sources'] if s['adapter'] == 'google-sheets-read' and
                      url in {s['route'], s['route'] + '/', s['route'] + '/edit'}), None)
        if sheet:
            self.calls.append(url)
            # All three authorized anonymous entry routes serve a proper native
            # document directly in this synthetic source, without access pages.
            event = RESPONSES[sheet['route'] + '/edit']
            raw = (CAPTURES / event['attempt']['local_reference']).read_bytes()
            return httpx.Response(200, content=self.native_page(raw, sheet),
                                  headers={'Content-Type':'text/html'})
        return super().handler(request)


def factual_candidate(system, descriptor):
    return dict(summary='Synthetic ' + descriptor['kind'], basis_type='factual',
                citations=[dict(evidence_id=descriptor['evidence_id'], quote=descriptor['quote'])],
                conditions=[json_bytes(descriptor).decode()], role='unknown', timing_candidates=[],
                exception_candidates=[], uncertainty=None, system_ids=[system])


def reconciliation_proposal(request):
    candidates = []
    for system in DECLARED['system_ids']:
        quote = report(system)
        evidence = next(e['evidence_id'] for e in request['extracts'] if e['text'] == quote)
        for predicate, value in VALUES.items():
            descriptor = dict(schema_version='rci-u10-basis/1', kind='fact', evidence_id=evidence, quote=quote,
                identity_quote=system, predicate=predicate, scope=SCOPE, value=value,
                value_quote=EXCEPTION if predicate == 'exception_claim' else quote, observed_on='2026-08-26',
                review_date_quote='2026-08-26', observation_kind='export-test' if predicate ==
                'machine_readable_provenance' else 'page-capture', role_current=True, owner=OWNER)
            if predicate == 'exception_claim':
                descriptor['exception_disposition'] = 'none-claimed'
            candidates.append(factual_candidate(system, descriptor))
        descriptor = dict(schema_version='rci-u10-basis/1', kind='report-review', evidence_id=evidence,
            quote=quote, identity_quote=system, scopes=[SCOPE], review_date_quote='2026-08-26', complete=True,
            completeness_quote='This report completely covers ' + SCOPE + ' on 2026-08-26.', owner=OWNER)
        candidates.append(factual_candidate(system, descriptor))
    evidence = next(e['evidence_id'] for e in request['extracts'] if POLICY in e['text'])
    descriptor = dict(schema_version='rci-u10-basis/1', kind='policy-control', evidence_id=evidence, quote=POLICY,
        identity_quote='Quillhaven', basis_id='synthetic-public-notice', meaning_key='synthetic-public-notice/v1',
        control=CONTROL, version='P-v1', version_quote='P-v1', activation='active', activation_quote='active',
        effective_from='2026-08-01', effective_until='2027-01-01', scope_kind='all-scoped', scope_quote='ALL')
    candidates.append(dict(summary=CONTROL, basis_type='internal-control',
        citations=[dict(evidence_id=evidence, quote=POLICY)], conditions=[json_bytes(descriptor).decode()],
        role='unknown', timing_candidates=[], exception_candidates=[], uncertainty=None,
        system_ids=DECLARED['system_ids']))
    return dict(disposition='proposed', diagnostic=None, candidates=candidates)


def legal_proposal(request):
    # Reuse only the six-source identity/version relationship evidence builder.
    with patch('runtime.test_u09.OBLIGATION', OBLIGATION), patch('runtime.test_u09.PREDICATE', PREDICATE), \
            patch('runtime.test_u09.EXCEPTION', EXCEPTION):
        value = authority_proposal(request)
    candidate = value['candidates'][0]
    candidate['system_ids'] = DECLARED['system_ids']
    descriptor = parse_json(candidate['timing_candidates'][0].encode())
    descriptor['exception_scope'] = SCOPE
    term = next(t for t in descriptor['support'] if t['component'] == 'exception-scope')
    term.update(value=SCOPE, quote=SCOPE)
    candidate['citations'].append(dict(evidence_id=term['evidence_id'], quote=SCOPE))
    candidate['timing_candidates'] = [json_bytes(descriptor).decode()]
    return value


def impact_proposal(root):
    chain = read_chain(root, count=4)
    legal, = chain[2]['state']['binding_rules']
    policy, = chain[3]['state']['policy_controls']
    oj = next(e['id'] for e in chain[1]['state']['evidence'] if e['assertion'].startswith(
        'Captured legal/context page body') and 'body of OJ;' in e['locator']['value'])
    candidates = []
    for system in DECLARED['system_ids']:
        for rule in (legal, policy):
            evidence = oj if rule['basis_type'] == 'binding-legal' else rule['evidence_ids'][0]
            def term(predicate, equals, rule_predicate, quote):
                return dict(predicate=predicate, equals=equals, rule_predicate=rule_predicate,
                            evidence_id=evidence, quote=quote)
            necessary = [term('deployer_role', True, 'role=deployer', OBLIGATION),
                         term('output_scope', SCOPE, 'exception scope: ' + SCOPE, SCOPE),
                         term('exception_claim', EXCEPTION, 'exception: ' + EXCEPTION, EXCEPTION)] if rule is legal else []
            impact = term('notice_present', False, PREDICATE if rule is legal else CONTROL,
                          PREDICATE if rule is legal else POLICY)
            descriptor = dict(schema_version='rci-impact-binding/1', rule_id=rule['id'], system_id=system,
                              scope=SCOPE, necessary=necessary, impact=impact)
            citations = [dict(evidence_id=t['evidence_id'], quote=t['quote']) for t in necessary + [impact]]
            candidates.append(dict(summary='Synthetic scoped notice-absence binding', basis_type=rule['basis_type'],
                citations=citations, conditions=[json_bytes(descriptor).decode()], role='unknown',
                timing_candidates=[], exception_candidates=[], uncertainty=None, system_ids=[system]))
    return dict(disposition='proposed', diagnostic=None, candidates=candidates)


def execute_full(tmp_path):
    config = deepcopy(CONFIG)
    config['output_root'] = 'out'
    config_path, scope_path = tmp_path / 'config.json', tmp_path / 'scope.json'
    config_path.write_bytes(json_bytes(config))
    scope_path.write_bytes(json_bytes(DECLARED))
    host_calls = []
    early_hashes = {}

    def host(command, prompt, root, timeout, *, analysis_directory='analysis'):
        root = Path(root)
        logs = root / analysis_directory
        logs.mkdir(parents=True, exist_ok=True)
        (logs / 'host-events.jsonl').write_bytes(b'{"type":"turn.completed","usage":{"synthetic_test_only":true}}\n')
        (logs / 'host-stderr.txt').write_bytes(b'')
        stage = {'analysis':'authority', 'analysis/reconciliation':'reconciliation',
                 'analysis/impacts':'impacts'}[analysis_directory]
        host_calls.append(stage)
        if stage == 'reconciliation':
            early_hashes.update({path:sha256_bytes((root / path).read_bytes()) for path in SNAPSHOT_PATHS[:3]})
        request = parse_json((root / ('analysis/' + stage + '/request.json')).read_bytes())
        value = legal_proposal(request) if stage == 'authority' else reconciliation_proposal(request) if \
            stage == 'reconciliation' else impact_proposal(root)
        proposal = logs / 'test-proposal.json'
        proposal.write_bytes(json_bytes(value))
        operation = {'authority':'submit-authority', 'reconciliation':'submit-reconciliation', 'impacts':'submit-impact'}[stage]
        process = subprocess.run([sys.executable, str(root / SKILL.name / 'scripts/stage.py'), operation,
            '--root', str(root), '--proposal', str(proposal)], capture_output=True, text=True,
            env={**os.environ, 'RCI_CHILD_RUN':root.name, 'PYTHONDONTWRITEBYTECODE':'1'})
        assert process.returncode == 0, process.stdout + process.stderr
        assert json.loads(process.stdout)['disposition'] == 'proposed', process.stdout

    with ExitStack() as stack:
        stack.enter_context(patch('rci.runtime.REPO', tmp_path))
        stack.enter_context(patch('rci.pipeline.ReadAdapters', FullReplay))
        for module in ('runtime', 'authority', 'reconcile', 'impacts'):
            stack.enter_context(patch('rci.' + module + '.preflight', return_value=('synthetic-host', 'test-v1')))
        for module in ('authority', 'reconcile', 'impacts'):
            stack.enter_context(patch('rci.' + module + '.invoke_host', side_effect=host))
        spec = importlib.util.spec_from_file_location('full_public_launcher', SKILL / 'scripts/run.py')
        public = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(public)
        stdout = io.StringIO()
        with patch.object(sys, 'argv', ['run.py', '--config', str(config_path), '--scope', str(scope_path)]), \
                redirect_stdout(stdout):
            exit_code = public.main()
    outcome = json.loads(stdout.getvalue())
    outcome['test_early_hashes'] = early_hashes
    return outcome, tmp_path / 'out', exit_code, host_calls


@pytest.fixture(scope='module')
def full_package(tmp_path_factory):
    outcome, root, exit_code, host_calls = execute_full(tmp_path_factory.mktemp('fully-assessed-eight'))
    assert outcome['package_acceptance'] and outcome['production_package'], outcome
    chain = validate_package(root)
    return outcome, root, exit_code, host_calls, chain


def test_fully_assessed_sources_complete_with_original_capture_partial(full_package):
    outcome, root, exit_code, host_calls, chain = full_package
    assert outcome['package_acceptance'] and outcome['production_package'], outcome
    assert outcome['status'] == 'complete' and exit_code == 0, outcome
    assert host_calls == ['authority', 'reconciliation', 'impacts']
    assert accept_package(root) == chain and len(chain) == 7
    assert {path:sha256_bytes((root / path).read_bytes()) for path in SNAPSHOT_PATHS[:3]} == outcome['test_early_hashes']
    assert chain[0]['status'] == 'complete'
    assert [s['status'] for s in chain] == ['complete', 'partial', 'partial', 'complete', 'complete', 'complete', 'complete']
    fourth = chain[3]['state']
    assert not fourth['evidence_gaps'] and not fourth['conflicts']
    facts = [f for f in fourth['system_facts'] if f['predicate'] in PREDICATES]
    assert len(facts) == len(PREDICATES) * 8
    assert all(f['state'] == 'supported' and f['value']['scope'] == SCOPE for f in facts)
    reports = fourth['extensions']['u10_reconciliation']['value']['reports']
    assert len(reports) == 8
    assert all(r['gap_id'] is None and r['resolution']['scopes'] == [SCOPE] for r in reports)
    assert all(r['resolution']['evidence_ids'] == r['report']['evidence_ids'] for r in reports)
    resolution = fourth['extensions']['u10_reconciliation']['value']['capture_resolution']
    assert resolution['original_upstream_status'] == 'partial'
    assert resolution['effective_upstream_status'] == 'complete'
    assert not resolution['unresolved_diagnostic_ids']
    assert set(resolution['resolved_diagnostic_ids']) == {d['id'] for d in chain[1]['state']['diagnostics']}
    assert len(resolution['resolved_diagnostic_ids']) == 18 and len(resolution['report_source_ids']) == 8
    assert {a['source_id'] for a in resolution['legal_assessments']} == {'AMEND', 'CONSOLIDATED'}
    fifth = chain[4]['state']
    coverage = fifth['extensions']['u11_impacts']['value']['coverage']
    assert len(coverage) == 16 and all(c['state'] == 'supported-impact' for c in coverage)
    assert {c['system_id'] for c in coverage} == set(DECLARED['system_ids'])
    assert not fifth['unresolved_items'] and not fifth['unaffected_items']
    model = chain[5]['state']['export_model']
    assert not model['unresolved_coverage']
    assert {k:v for k,v in model['source_resolution'].items() if k != 'report_resolutions'} == resolution
    assert model['source_resolution']['report_resolutions'] == reports
    brief = (root / 'compliance-brief.md').read_text()
    assert '## Source inspection resolution' in brief
    assert 'Original capture diagnostics and historical source statuses remain recorded above.' in brief
    assert all(r['delivery_status'] == 'not-sent' for r in model['review_requests'])
    assert model['approval_requirements'] and all(q['status'] == 'pending' for q in model['approval_requirements'])
    assert all(a['approval_status'] == 'pending' for a in model['actions'])
    assert chain[6]['state']['publication_status'] == 'validated'
    assert len(chain[6]['state']['artifacts']) == 3 and (root / '.completion.json').is_file()
    # U08's original report observations remain exact and independently partial.
    retained = chain[1]['state']['extensions']['u08_reports']['value']['reports']
    assert len(retained) == 8 and all(r['result'] == 'captured-unverified' for r in retained)
    assert any(d['reason'].startswith('Report bytes retained; identity, date')
               for d in chain[1]['state']['diagnostics'])


def test_complete_archive_retains_independent_review_aggregate_guard(full_package):
    outcome, root, _, _, chain = full_package
    originals = {path:(root / path).read_bytes() for path in managed_paths(root)}
    archive = archive_current(root, outcome['run_id'], created_at=chain[6]['created_at'])
    assert all((archive.root / path).read_bytes() == raw for path,raw in originals.items())
    assert verify_archive(archive.root).inventory_sha256 == archive.inventory_sha256
    assert validate_package(archive.root) == chain
    request = next(r for r in chain[5]['state']['review_requests'] if r['required_reviewer'] == 'Legal')
    binding = next(b for b in chain[6]['state']['review_bindings'] if b['request_id'] == request['request_id'])
    reference = dict(root='history/' + outcome['run_id'], **{
        label:dict(snapshot_id=chain[i]['snapshot_id'], path=SNAPSHOT_PATHS[i],
                   sha256=sha256_bytes((archive.root / SNAPSHOT_PATHS[i]).read_bytes()))
        for label, i in (('stage06', 5), ('stage07', 6))})
    feedback = dict(reviewed_draft=reference, claimed_run_id=outcome['run_id'],
        claimed_request_id=request['request_id'], claimed_draft_version=request['draft_version'],
        claimed_source_versions=request['source_versions'], claimed_subject_ids=request['subject_ids'][:1],
        claimed_artifacts=binding['artifacts'], responder_role='Legal',
        reviewer_response_at=chain[6]['created_at'])
    # Raw historical status reduction is partial. The actual retained-review
    # verifier must independently reconstruct its guarded COMPLETE resolution.
    _, reviewed_request = _reviewed_request(feedback, root, 'run-' + 'f' * 32)
    assert reviewed_request == request
    assert all(a['status'] == 'pending' for a in chain[5]['state']['approval_requirements'])
    invalid = deepcopy(feedback)
    invalid['claimed_artifacts'][0]['sha256'] = 'sha256:' + '0' * 64
    with pytest.raises(ContractError, match='artifact claims disagree'):
        _reviewed_request(invalid, root, 'run-' + 'f' * 32)


def test_forged_resolution_cannot_improve_historical_partial(full_package, tmp_path):
    root = tmp_path / 'forged-resolution'
    shutil.copytree(full_package[1], root, ignore=shutil.ignore_patterns('.staging', 'history', '.writer.lock'))
    forged = deepcopy(full_package[4])
    resolution = forged[3]['state']['extensions']['u10_reconciliation']['value']['capture_resolution']
    resolution['resolved_diagnostic_ids'][0] = 'unit-forged-diagnostic'
    # Preserve the seven-stage hash chain so the reconstruction guard sees a
    # structurally valid COMPLETE claim with original early partial statuses.
    (root / SNAPSHOT_PATHS[3]).write_bytes(json_bytes(forged[3]))
    for i in range(4, 7):
        forged[i]['predecessor']['sha256'] = sha256_bytes((root / SNAPSHOT_PATHS[i - 1]).read_bytes())
        (root / SNAPSHOT_PATHS[i]).write_bytes(json_bytes(forged[i]))
    assert read_chain(root, count=4) == forged[:4]
    with pytest.raises(ContractError, match='Stage 04 differs'):
        resolved_run_status(root, forged[:6])


@pytest.mark.parametrize('case', ['other-diagnostic', 'unavailable-report', 'identity-mismatch',
    'missing-report-resolution', 'unreadable-report', 'authority-blocker', 'missing-legal-rule',
    'missing-legal-timing', 'unassessed-legal-source', 'reconciliation-gap', 'reconciliation-conflict',
    'upstream-failed', 'upstream-blocked'])
def test_capture_resolution_guard_cannot_improve_other_failures(full_package, case):
    # These are unit inputs derived from a genuinely validated package. No
    # mutated snapshot or source is written into a retained evidence graph.
    chain = deepcopy(full_package[4][:3])
    state = deepcopy(full_package[4][3]['state'])
    accounting = state['extensions']['u10_reconciliation']['value']
    assert _capture_resolution(chain, state, accounting)['effective_upstream_status'] == 'complete'
    if case == 'other-diagnostic':
        diagnostic = deepcopy(chain[1]['state']['diagnostics'][0])
        diagnostic.update(id='unit-extra-diagnostic', summary='Unrelated unresolved source',
                          reason='Unrelated unresolved source', source_basis=['other-source'])
        chain[1]['state']['diagnostics'].append(diagnostic)
    elif case in {'unavailable-report', 'identity-mismatch'}:
        attempt_id = accounting['reports'][0]['report']['attempt_ids'][0]
        attempt = next(a for a in chain[1]['state']['attempts'] if a['id'] == attempt_id)
        if case == 'unavailable-report':
            attempt['outcome'] = 'ConnectError'
        else:
            attempt['identity_check'] = 'mismatch'
    elif case == 'missing-report-resolution':
        accounting['reports'][0].pop('resolution')
    elif case == 'unreadable-report':
        accounting['reports'][0]['report']['evidence_ids'] = []
    elif case == 'authority-blocker':
        chain[2]['status'] = 'blocked'
        chain[2]['state']['authority_blockers'].append({'reason':'Unresolved authority'})
    elif case == 'missing-legal-rule':
        chain[2]['state']['binding_rules'] = []
    elif case == 'missing-legal-timing':
        chain[2]['state']['timing_rules'] = []
    elif case == 'unassessed-legal-source':
        for candidate in chain[2]['state']['extensions']['u09_authority']['value']['candidates']:
            for source in candidate['assessment']['sources']:
                if source['source_id'] == 'AMEND':
                    source['assessment'] = 'unresolved'
    elif case == 'reconciliation-gap':
        state['evidence_gaps'].append({'reason':'Unresolved company evidence'})
    elif case == 'reconciliation-conflict':
        state['conflicts'].append({'reason':'Contradictory company evidence'})
    elif case == 'upstream-failed':
        chain[1]['status'] = 'failed'
    elif case == 'upstream-blocked':
        chain[1]['status'] = 'blocked'
    result = _capture_resolution(chain, state, accounting)
    expected = 'failed' if case == 'upstream-failed' else 'blocked' if case in {
        'authority-blocker', 'upstream-blocked'} else 'partial'
    assert result['effective_upstream_status'] == expected
