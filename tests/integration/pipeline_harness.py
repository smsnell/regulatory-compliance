"""Deterministic source/skill seam for the actual seven-stage supervisor.

Transport and semantic host proposals are synthetic test inputs. Submission
uses the real helper subprocess; operators never move interpretation manually.
"""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import httpx

from rci.contracts import json_bytes, parse_json
from rci.pipeline import run
from rci.runtime import SKILL
from runtime.test_u07 import CONFIG, DECLARED
from runtime.test_u09 import proposal as authority_proposal
from runtime.test_u10 import CompanyReplay, REPORT, candidate, policy_candidate
from runtime.test_u11 import CONTROL, POLICY, binding


def execute(tmp_path, mutation=None, fail_host=None, *, launcher=False,
            conflict=False, unavailable_authority=False, feedback_path=None,
            reviewer_policy_path=None, authentication_path=None):
    """Return (outcome, current_root), retaining all real candidate evidence.

    Repeat against the same tmp_path to exercise history and fresh acquisition.
    fail_host identifies 'authority', 'reconciliation', or 'impacts' to omit
    that host's submission. No success result is fabricated by this harness.
    """
    tmp_path = Path(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = deepcopy(CONFIG)
    config['output_root'] = 'out'
    config_path = tmp_path / 'config.json'
    config_path.write_bytes(json_bytes(config))
    scope_path = tmp_path / 'scope.json'
    scope_path.write_bytes(json_bytes(DECLARED))
    host_calls = []
    class Replay(CompanyReplay):
        def handler(self, request):
            official = next(s['route'] for s in CONFIG['sources'] if s['id'] == 'OJ')
            if unavailable_authority and str(request.url) == official:
                self.calls.append(official)
                raise httpx.ConnectError('synthetic unavailable official source')
            return super().handler(request)
    Replay.mutation = mutation

    def host(command, prompt, root, timeout, *, analysis_directory='analysis'):
        root = Path(root)
        logs = root / analysis_directory
        logs.mkdir(parents=True, exist_ok=True)
        (logs / 'host-events.jsonl').write_bytes(
            b'{"type":"turn.completed","usage":{"synthetic_test_only":true}}\n')
        (logs / 'host-stderr.txt').write_bytes(b'')
        stage = {'analysis':'authority', 'analysis/reconciliation':'reconciliation',
                 'analysis/impacts':'impacts'}[analysis_directory]
        host_calls.append(stage)
        if fail_host == stage or (fail_host == 'no-submission' and stage == 'reconciliation'):
            return
        if stage == 'authority':
            request = parse_json((root / 'analysis/authority/request.json').read_bytes())
            value = authority_proposal(request)
            operation = 'submit-authority'
        elif stage == 'reconciliation':
            request = parse_json((root / 'analysis/reconciliation/request.json').read_bytes())
            candidates = [candidate(request, value=False, quote=REPORT.splitlines()[1], kind='page-capture'),
                          policy_candidate(request)]
            if conflict:
                candidates.insert(0, candidate(request))
            value = dict(disposition='proposed', diagnostic=None, candidates=candidates)
            operation = 'submit-reconciliation'
            if fail_host == 'changed-source':
                (root / request['extracts'][0]['path']).write_bytes(b'synthetic damaged source during host')
        else:
            value = dict(disposition='proposed', diagnostic=None, candidates=[binding(root)])
            operation = 'submit-impact'
        proposal = logs / 'test-proposal.json'
        proposal.write_bytes(json_bytes(value))
        process = subprocess.run([sys.executable, str(root / SKILL.name / 'scripts/stage.py'),
            operation, '--root', str(root), '--proposal', str(proposal)], capture_output=True,
            text=True, env={**os.environ, 'RCI_CHILD_RUN':root.name, 'PYTHONDONTWRITEBYTECODE':'1'})
        if fail_host == 'changed-source' and stage == 'reconciliation':
            assert process.returncode != 0, 'damaged retained source must reject the submission'
            return
        assert process.returncode == 0, process.stdout + process.stderr
        submitted = json.loads(process.stdout)
        assert submitted['disposition'] == 'proposed', submitted

    with ExitStack() as stack:
        stack.enter_context(patch('rci.runtime.REPO', tmp_path))
        stack.enter_context(patch('rci.pipeline.ReadAdapters', Replay))
        stack.enter_context(patch('runtime.test_u10.CONTROL', CONTROL))
        stack.enter_context(patch('runtime.test_u10.POLICY', POLICY))
        for module in ('runtime', 'authority', 'reconcile', 'impacts'):
            stack.enter_context(patch('rci.' + module + '.preflight',
                                      return_value=('synthetic-host', 'test-v1')))
        for module in ('authority', 'reconcile', 'impacts'):
            stack.enter_context(patch('rci.' + module + '.invoke_host', side_effect=host))
        if launcher:
            spec = importlib.util.spec_from_file_location('g5_public_launcher', SKILL / 'scripts/run.py')
            public = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(public)
            stdout = io.StringIO()
            arguments = ['run.py', '--config', str(config_path), '--scope', str(scope_path)]
            for flag, path in (('--feedback', feedback_path), ('--reviewer-policy', reviewer_policy_path),
                               ('--authentication', authentication_path)):
                if path is not None:
                    arguments.extend((flag, str(path)))
            with patch.object(sys, 'argv', arguments), \
                    redirect_stdout(stdout):
                exit_code = public.main()
            outcome = json.loads(stdout.getvalue())
            outcome['launcher_exit_code'] = exit_code
        else:
            outcome = run(config_path, scope_path=scope_path, feedback_path=feedback_path,
                          reviewer_policy_path=reviewer_policy_path,
                          authentication_path=authentication_path)
    outcome['test_host_calls'] = host_calls
    return outcome, tmp_path / 'out'
