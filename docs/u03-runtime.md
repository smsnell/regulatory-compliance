# U03 runtime setup and bounded host check

Tested: Python 3.14.4 on Linux, Codex CLI 0.161.0. Python 3.12+ is the
minimum; other host versions stop preflight for capability review. Dependencies,
including transitive packages, are pinned in `requirements.lock`; pip 26.0.1
was used for both isolated setup checks. No separate model SDK/API key exists.

With a Python installation providing venv/ensurepip:

```sh
python3 -m venv /tmp/rci-venv
/tmp/rci-venv/bin/python -m pip install -r requirements.lock
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-venv/bin/python -m pytest -q
```

This machine lacks ensurepip. Verification created venvs with `--without-pip`,
downloaded the official `https://bootstrap.pypa.io/get-pip.py` into `/tmp`, and
ran it with `pip==26.0.1` inside each venv. Nothing was installed into system
Python. Network/package installation needed the execution environment's approval.

Host setup: install the tested Codex CLI; authenticate through its existing
host-managed login and verify `codex login status`. Name the operator in the
sample config's host owner field. Source credential references designate an
external read-only login; U05 will establish actual source access. Config must
contain no credential values. The supervisor checks version/login before
creating output staging, and registers the supplied skill under the isolated
session's `.agents/skills/` directory. No global skill install is needed.

Output roots must be dedicated repository-relative directories, such as
`deliverables` or `review-output/pilot`. Before host preflight or any output
write, resolved paths are checked against the skill, configuration, documentation,
interview, reference, test and repository-tooling directories, and the active
config file. An output root cannot contain or sit inside those inputs; symlink
aliases do not bypass the check.

Source routes use credential-free HTTPS without userinfo or fragments. The only
supported query form in U03 is one decoded `uri` document selector on
`https://eur-lex.europa.eu/legal-content/EN/TXT/`, with an `OJ:` or `CELEX:`
identifier in the disclosed format. Encoded keys are decoded before validation;
unknown, duplicate or malformed query parameters reject setup without echoing
their values. Additional route/query forms require adapter review in U05; this
syntax check does not establish source identity, access or legal authority.

The one-command feasibility check is explicitly test-only:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-venv/bin/python tests/integration/u03_host.py --output /tmp/rci-u03-live
```

It creates a fresh synthetic run, rebinds a two-stage G1 prefix, invokes the
actual installed host, and independently verifies the agent's proposal and
Python-created response. The synthetic source includes an explicit system
mapping and notice content; it does not establish law or company facts. Fake
clock/run ID providers are confined to `tests/u03_harness.py`. Default tests
never invoke a paid host or live source. An integration error returns nonzero
and retains all available candidate analysis for inspection. Retrying creates
a new run; response files are exclusive and immutable after submission.

The public production command is:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-venv/bin/python regulatory-change-impact-brief/scripts/run.py --config config/review.json
```

Copy `config/review.example.json` to an operator config and name its host owner.
There is no production fixture/replay option. U03 invokes the loader, whose
helper reports the missing live engines. Expected outcome: `blocked`, exit 3,
with retained diagnostics in `deliverables/.staging/<run-id>/analysis/`.
This demonstrates the runtime boundary; full production R11/R12 acceptance
remains with U17/U19/U20. No current package is promoted by U03.

The supervisor holds an advisory Linux writer lock throughout invocation and
checks immutable input bytes after the host exits. It logs the invocation,
prompt, visible JSONL events, stderr and run outcome. Requested model/effort
are exact; unreported model/effort remain null. Usage reported by the host is
retained in events and the outcome. Packet metadata cannot retrospectively
claim information unavailable when the immutable request was made.

Host permission profile: fresh ephemeral session; ignore inherited user config
and execpolicy rules; workspace-write only in the isolated run; tool networking
disabled; approvals never; multi-agent and web-search features disabled. No
inherited MCP/source mutation or message delivery integrations are configured.
The helper uses `RCI_CHILD_RUN` to reject recursive supervisor launch. Shell
access is permitted for helpers; prompts alone are not a security boundary.
Immutable-byte checks and G1 exchange validation independently verify results.
Timeout/interruption terminates the process group and retains diagnostics.

Exit codes: 0 complete validated production draft; 2 partial validated draft;
3 blocked; 1 failed. Synthetic integration success is explicitly labelled
`production_package: false`. Host text or exit zero alone cannot establish a
production outcome. `verify_final` uses G1 package acceptance plus current-run,
fresh-attempt, required-source and aggregate-outcome checks; U17 adds business
and renderer acceptance. Archive/promotion/recovery remain U18 work.
