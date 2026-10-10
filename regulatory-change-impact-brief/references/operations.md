# Operator handoff

Use the [operating guide](../../docs/operating-guide.md) for setup, public commands,
feedback formats, output interpretation and fresh recovery. The guide follows the
current launcher APIs; earlier unit records describe their historical bounded scope.

The public entrypoint is `scripts/run.py --config <operator-config>`. Its default
workflow runs seven stages with fresh source reads. Optional `--scope` supplies an
authorized eight-system declared scope. `--feedback`, `--reviewer-policy` and
`--authentication` are supplied together; feedback uses exactly the envelope
`{"feedback": [...], "carry_forward": false}`. Explicit `true` requests exact
revalidation against retained history. Prepared requests remain unsent.

Operators maintain Codex login separately from source permissions and reviewer
identity authorization. Python 3.12+, the repository's `requirements.lock`, and
Codex CLI 0.161.0 or 0.162.1 are the current runtime requirements. The public default
source adapters use anonymous reads; credential references alone provide no login.
The interpretation host has networking disabled and writes bounded proposals;
Python validates evidence and creates snapshots and artifacts.

Review the printed outcome, Stage 07 status and exact detached artifact bindings.
Complete/partial packages can have validated draft publication and pending human
decisions. Authority-blocked publication remains blocked. Technical failure retains
its candidate. Exit codes are complete 0, partial 2, blocked 3 and failed 1.

Recovery is a new public invocation with `--change-reason`, optionally naming a
compatible retained `--supersedes-run-id`. Every stage and source read is repeated.
The incomplete-replacement marker prevents acceptance until copied current bytes
validate. Preserve candidates, history inventories, missing/corrupt findings and
control markers. No operator step sends feedback requests, changes source policy,
imports calendars or turns proposals into external approvals.

Use deterministic pytest separately from the opt-in real-host synthetic evaluation
`tests/integration/u19_host.py`. Keep their evidence distinct from production
source access and company/legal findings. Gate status is maintained in verification
records, not asserted by this operator reference.
