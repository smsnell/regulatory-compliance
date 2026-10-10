# Operating the regulatory change impact draft

Run commands from the repository root. This guide describes the current public
launcher and retained evidence; verification results belong in `docs/verification/`.

## Setup and access

Use Python 3.12 or later on a host with POSIX file locking. Install the exact
dependency set in [requirements.lock](../requirements.lock) in an isolated environment:

```sh
python3 -m venv /tmp/rci-operator-venv
/tmp/rci-operator-venv/bin/python -m pip install -r requirements.lock
codex --version
codex login status
```

Preflight accepts `codex-cli 0.161.0` and `codex-cli 0.162.1`. The `codex` executable
must be on PATH and its managed login must already work. Configure the operator
name in `host.owner`; the example uses `gpt-6.1-sol` with `high` effort. If Python
lacks `ensurepip`, follow the isolated bootstrap procedure in
[the setup record](u03-runtime.md); installing into system Python is unnecessary.

Codex authentication permits model execution. Source access is a separate
authorization boundary. Configuration contains credential references, never
tokens or credential-bearing URLs. The public launcher currently uses the
default adapters with anonymous reads; a credential reference does not establish
a source login. The Sheets adapter's programmatic credential inventory is separate
from configuration and requires a read-only scope and token environment reference.
Unavailable private sources remain gaps or blockers. No source is written, and no
review request is sent. Interpretation hosts have networking disabled.

## Run the complete workflow

Copy [review.example.json](../config/review.example.json) to an operator-owned
configuration such as `config/review.json`. Set `host.owner` and a dedicated,
repository-relative `output_root`, such as `deliverables`. Keep the assigned
review date `2026-08-26` and the eight-system scope requirement. The output directory
must be separate from implementation, configuration, documentation and evidence inputs.

Run with discovered scope, or supply an authorized declared scope when needed:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-operator-venv/bin/python regulatory-change-impact-brief/scripts/run.py --config config/review.json --scope config/scope.json
```

`--scope` is optional. Its JSON has exactly `schema_version: rci-scope-input/1`,
`system_ids` containing eight distinct exact IDs, `basis_version`, `authorized_by`,
and a nonempty `source_basis` list. An authorized declared scope establishes the
scope basis; it does not establish company facts or source access. Without a valid
scope basis, drafting stops with an honest scope outcome.

The complete command captures sources and runs authority, reconciliation, impacts,
actions/reviews, rendering and independent artifact validation. It creates a fresh
run ID and fresh source attempts on every invocation. `--capture-slice` selects an
earlier capture workflow; `--linked-reports`, `--interpret-reports`, `--authority`
and `--reconcile` are slice options and require that flag. Feedback requires the
complete workflow. The public command has no fixture or replay option.

## Read the result

The launcher prints a JSON outcome. Preserve its `run_id`, `status`,
`publication_status`, `production_package`, `package_acceptance`, `candidate`,
`supersedes_run_id`, and missing-file lists where present. Preflight failures can
return a shorter failed outcome before a candidate exists.

| Status | Exit | Meaning |
|---|---:|---|
| `complete` | 0 | Required drafting stages completed; human decisions may still be pending. |
| `partial` | 2 | A bounded draft retains explicit gaps; independent validation can accept it. |
| `blocked` | 3 | Required scope or authority is unresolved. A seven-stage authority-blocked draft can be published with publication blocked; an earlier scope stop has no full package. |
| `failed` | 1 | Technical execution or integrity failed; inspect retained candidate evidence. |

`validated` publication establishes exact artifact consistency and provenance.
It does not approve policy, authorize changed dates, complete actions or deliver
requests. Blocked publication has no completion marker. Pending feedback alone
does not prevent drafting.

After promotion, a typical output directory contains:

```text
deliverables/
  impact-register.csv
  compliance-brief.md
  action-calendar.ics
  snapshots/01-scope.json ... 07-publication-validation.json
  sources/                         retained permitted captures/extracts
  analysis/                        attempts, interpretations, outcome and diagnostics
  .completion.json                 accepted complete/partial package only
  .incomplete-replacement.json      exists while replacement is incomplete
  .staging/<run-id>/                retained candidate, including failed candidates
  history/<prior-run-id>/           prior bytes and .history-inventory.json
  .writer.lock
```

Read the brief for scope, supported observations, conflicts, unresolved matters,
proposals, existing dates, required reviewers and evidence references. CSV has one
row per impact or unresolved coverage item, semicolon-separated action/evidence references and reversible
apostrophe display escaping for spreadsheet formula safety. ICS contains only
dated proposals: tentative all-day events, stable action UIDs and exclusive next-day
ends. An empty calendar is valid when no dated proposal is supported. Preview files
locally; creating them does not import a production calendar or send them.

Historical capture snapshots can remain partial after their exact pending inspection
issues are resolved. The brief identifies resolved diagnostic IDs and assessment
evidence. Stage 07 reconstructs that resolution from retained bytes; original
diagnostics remain visible. Other gaps and authority blockers still affect the
final outcome. A COMPLETE draft does not imply a human approval.

Stage 07 `review_bindings` maps every request to the exact paths and SHA-256 hashes
of all three artifacts. Read these bindings when collecting a response.

## Intake authenticated feedback

Use three separate operator-controlled files outside managed output:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-operator-venv/bin/python regulatory-change-impact-brief/scripts/run.py --config config/review.json --scope config/scope.json --feedback config/feedback.json --reviewer-policy config/reviewer-policy.json --authentication config/authentication.json
```

The feedback envelope has exactly two keys:

```json
{"feedback": [], "carry_forward": false}
```

Each response in `feedback` supplies `responder_identity`, `responder_role`,
`reviewer_response_at` in RFC3339, `outcome` (`approved`, `rejected`, `conditional`,
or `unresolved`), `reasons`, `conditions`, `claimed_request_id`, `claimed_subject_ids`,
`claimed_run_id`, `claimed_draft_version`, `claimed_source_versions`,
`claimed_artifacts`, and `reviewed_draft`. Use the actual authenticated response
and the reviewed package's Stage 06 request and Stage 07 binding. Artifact entries
are `{ "path": "...", "sha256": "sha256:<64 lowercase hex characters>" }` for
the three exact final files. `reviewed_draft` is:

```json
{
  "root": "history/<reviewed-run-id>",
  "stage06": {"snapshot_id": "<reviewed Stage 06 ID>", "path": "snapshots/06-actions-and-approvals.json", "sha256": "<hash of exact Stage 06 bytes>"},
  "stage07": {"snapshot_id": "<reviewed Stage 07 ID>", "path": "snapshots/07-publication-validation.json", "sha256": "<hash of exact Stage 07 bytes>"}
}
```

Replace every placeholder using the reviewed files. Responses must follow the
reviewed draft's creation time and precede intake. The launcher archives the current
draft when needed and copies referenced history into the new candidate.

The separate reviewer policy and authentication formats are:

```json
{"reviewers":[{"identity":"legal@example.test","roles":["Legal"],"channels":["authenticated-operator"],"system_ids":["S1"]}]}
```

```json
{"identity":"legal@example.test","channel":"authenticated-operator","basis":"verified operator session and retained identity proof reference"}
```

Supply the actual authorized identity, channel and full reviewed system scope.
Obtain authentication context through the trusted operator/channel session; copying
identity claims from the feedback file is not authentication. One context applies
to that intake batch; use separate batches for different authenticated responders.

`carry_forward: false` keeps feedback about the older draft pending current
revalidation. Set it to `true` only when explicitly asking the runtime to test
carry-forward. Exact relevant facts, dates, evidence hashes, source versions, scope
and semantic subjects must remain unchanged. Wrong identity/role/request/version,
hash, subject or conditions remain unresolved and cannot authorize a proposal.
Multiple competing responses keep the approval pending. Conditional decisions stay
pending through the current CLI: trusted condition-satisfaction evidence is supported
by the bounded Python API, but no CLI condition-resolution field is exposed.
See [review protocol](../regulatory-change-impact-brief/references/review-protocol.md).

## Fresh retry and recovery

Inspect `analysis/outcome.json`, any `analysis/failure-outcome.json`, host event/stderr
logs, missing lists and the current control markers. Preserve current files and
all failed candidates. Retry the same public command with a reason:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-operator-venv/bin/python regulatory-change-impact-brief/scripts/run.py --config config/review.json --scope config/scope.json --change-reason 'Fresh retry after resolving the recorded failure'
```

`--supersedes-run-id` optionally identifies an already retained prior occurrence;
it must agree with the recognized current run, or identify a retained failed
candidate when no current run exists. The runtime inspects current bytes, performs
fresh reads and recomputes all seven stages even if fingerprints are unchanged.
Fingerprint reports identify the earliest changed basis; they do not resume a stage.

Promotion archives prior bytes, writes the incomplete marker, replaces managed
files, validates copied bytes and only then completes the replacement. While the
incomplete marker exists, public acceptance fails even if an older completion
marker exists. A fresh retry preserves the interrupted occurrence and its previous
archive. Do not clear the marker to force acceptance. If the prior run ID is
ambiguous, files are preserved and replacement stops for operator investigation.
History inventories retain missing/corrupt/unreadable findings; an archive manifest
is not a statement that the archived draft passed validation.

## Reproduce evaluations

Deterministic tests exercise synthetic captures and proposals without live model
execution or production source reads:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-operator-venv/bin/python -m pytest -q
```

The opt-in selected-host evaluation invokes the actual logged-in Codex host through
the public launcher, with synthetic source transport supplied by its test harness:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-operator-venv/bin/python tests/integration/u19_host.py --output /tmp/rci-u19-operator-check
```

It retains configuration, scope, host logs, snapshots and artifacts beneath the
specified output. It can consume paid model usage. Synthetic outcomes do not
establish production source access or a legal/company conclusion. Retain failed
evaluations as evidence. These commands describe how to reproduce checks; this
guide does not assert that any acceptance gate has passed.
