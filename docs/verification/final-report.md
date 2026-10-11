# U20 whole-system verification

> Historical audit. Its live-package observations refer to the prior run now
> represented under `deliverables/history/run-f48b4823b3ad4faaa9ac30a301b66505/`.
> Both current and historical published packages are [sanitized publication
> derivatives](publication-remediation.md); exact original bytes and hashes remain
> in restricted storage. Audit findings below are unchanged.

Review date: 2026-10-10. Assigned business review date: **2026-08-26**.

**The U20 audit is complete with explicit exceptions; full implementation and
successful live-review acceptance are not demonstrated.** The documented live
command produced seven snapshots and all three draft files, with publication
correctly **blocked**. Authority compatibility, inaccessible policy content and
unfetchable report references remain unresolved. The audit also found that the
runtime emits no decision records, despite having a decision schema and a static
design log. Some early setup failures also lose run-specific diagnostic context. Dependency-change
and conditional-feedback integration coverage is incomplete. See the [exception register](u20/exception-register.md).

The live [brief](../../deliverables/compliance-brief.md),
[register](../../deliverables/impact-register.csv), and
[calendar](../../deliverables/action-calendar.ics) belong to
`run-f48b4823b3ad4faaa9ac30a301b66505`. They are review drafts: 56 unresolved
coverage rows, no supported legal conclusions, no proposed actions or calendar
events, and two unsent requests for Legal and Operations. Exact
[Stage 07 bindings](../../deliverables/snapshots/07-publication-validation.json)
match all three files. There is no completion marker or claim of human approval.

## Frozen basis and reproducibility

The starting checkout was clean at commit
`e0b8ccd3eb2cefdf680102bb123b0576b275ffaa`. The
[baseline inventory](u20/basis.json) hashes all 443 tracked files.
[Final code/configuration/dependency fingerprints](u20/final-basis.json) and the
[amendment record](u20/amendment.json) identify the subsequent U20 changes.
No commit or push was performed.

| Input | SHA-256 |
|---|---|
| Requirements | `eed1f9d24fcdc9e86b95bd6235eb6e82ea62d915d01f28d6d409329df9cde2c3` |
| Original interview | `c3c0167379d0beaeef9ddd88826c6b585017e66620aee43e2ca5a26f9480c7fd` |
| Supplied snapshot schema | `8de9874ded18fa97294e83012796e4c386aa60ccfd30f8eca89cabdf2a267ac3` |
| Dependency lock | `fce5cce273a15b5578bf11d7d0a0a6fede14e0aafb78aeff5f984cb0f126d47e` |
| Live U20 config | `44985ebc099e94d447960c610a09f94f8b973bd6ea41275bc7746853ca6c2be0` |

The first three hashes equal the planning baseline. The requirements, interview
and supplied schema were not edited. Implementation and documentation changes
since planning are in the committed U01–U19 history and earlier verification
records; this report verifies their actual current behavior.

Runtime: Python 3.14.4, Codex CLI 0.162.1, and all 21 exact lockfile dependencies.
A fresh environment in `.evidence/u20/venv` was created without system-package
access; its installed distribution set exactly equals the lock. Because this
host lacks ensurepip, the existing isolated pip driver installed into that new
environment using `pip --python`. The clean source copy contains the exact
tracked baseline bytes. It has no unpublished implementation files from the
working tree.

Both actual-host evaluations requested `gpt-6.1-sol` with `high` effort and used
the existing managed login. No separate model API key or manual interpretation
transfer was used. [Execution metadata](u20/execution-record.json) records exact
instruction/reference/config hashes and visible usage. Reported model/effort are
null where the host did not expose them; hidden provider state is not claimed.

## Ordered final checks

| Plan §10 step | Expected and observed result | Evidence |
|---|---|---|
| 1. Freeze basis | Original inputs unchanged; code, config, dependencies and interpretation templates fingerprinted. | `basis.json`, `final-basis.json`, `execution-record.json` |
| 2. Automated logic/property/metamorphic checks | Full collected regression coverage, bounded failure repair checks and a new complete-workflow register permutation case. See exact results below. | Test XML/logs and `executed-checks.json` |
| 3. Separate schema/format/hash/graph check | Seven public schemas with format checking; typed reconstruction; same-run graph; exact source/artifact hashes; CSV cardinality; ICS dates; detached review bindings. Live, clean-host and COMPLETE synthetic packages pass these mechanical checks. | [Live inspection](u20/live-inspection.json), [clean host](u20/clean-host-inspection.json), [COMPLETE fixture](u20/complete-inspection.json), [checker](check-u20.py) |
| 4. Integration/live command | Fresh live reads of all ten core sources; 22 distinct attempts; original discovery time retained. Actual host completes the seven-stage command. Clean environment independently completes a partial synthetic package. | `execution-record.json`; retained candidates, host events and packets |
| 5. Change/recovery | Controlled synthetic source change identifies Stage 02; prior bytes retained; corrupt current brief detected with unchanged inputs; public command creates fresh attempts/new IDs and repairs; both archives resolve against their own roots. | [Recovery inspection](u20/recovery-inspection.json), G5 test in the full suite |
| 6. Meaning/human boundary | All eight systems and representative capture/row meanings inspected. No supported live legal rule can be certified; missing policy/report meaning remains blocked. Runtime decisions are absent (E04); early setup diagnostics are incomplete (E05). | [Source inspection](u20/source-inspection.md), [exceptions](u20/exception-register.md) |
| 7. Review binding | Every live Stage 06 request has one Stage 07 binding to all three exact final files; question, subject, source versions and unsent state inspected. Brief points to detached binding and contains no self-hash. | `live-inspection.json` |
| 8. Leaf closure | All 502 original matrix rows receive an explicit permitted status and evidence/basis. No pass is inferred solely from a test name, aggregate count or file presence. | [Matrix](../requirements-traceability.csv), [leaf evidence](u20/leaf-evidence.json) |
| 9. Final report | Software evidence is separated from actual source-dependent acceptance; each unclosed leaf maps to an owner and next action. | This report and exception register |

Mechanical checks ran independently while the longer regression tests completed.
Raw primary captures are retained locally in `deliverables/`; synthetic packages,
failed attempts, clean setup, logs and scanner records are in `.evidence/u20/`.
The latter is intentionally excluded by the existing repository evidence policy.
Portable verification summaries and test XML are under `docs/verification/u20/`.
Pytest echoed deliberately synthetic credential fixtures into five parameter IDs.
The portable collection/XML/check-index copies redact those exact values; original
hashed results remain local. [Redaction lineage](u20/portable-evidence-redaction.json)
records both hashes, unchanged outcomes, the initial 21 scan findings and a clean
rescan of the portable copies.
The [final integrity check](u20/final-integrity.json) verifies matrix status/evidence
references, copied test-result hashes, inspected artifact bytes and unchanged inputs.

## Commands and actual results

`PYTHONDONTWRITEBYTECODE=1` was used for Python checks; large temporary test trees
were placed under `.evidence/u20/` because `/tmp` had only about 91 MB free.
The U05 external-directory/loopback checks used unique external basetemps.

| Check | Actual result |
|---|---|
| Full suite, excluding the three U05 environment-specific cases | 725 passed, 3 deselected, 42 subtests passed; 2506.23 seconds (41m46s). |
| U05 external path/loopback checks in sandbox | 2 passed, 1 permission failure; original failure retained. |
| Same loopback case with required permission | 1 passed, 0.82 seconds. No assertion changed. |
| Initial failure-diagnostic regressions | 2 passed, 0.73 seconds. |
| Post-amendment supervisor integration and failure tests | 13 passed, 384.63 seconds. |
| Final launcher/preflight and U03 regression | 54 passed, 2.65 seconds. |
| New T07 complete-workflow metamorphic test | 1 passed, 224.28 seconds; two complete eight-system runs retain matching final meanings/IDs after row/header reversal and an extra column. |
| Clean actual-host evaluation | Harness exit 0; public launcher exit 2, partial/validated; 24 CSV rows, empty ICS. Synthetic source transport only. |
| Live command | Exit 3, blocked/blocked; all seven snapshots and three final artifacts; exact files mechanically validate. |
| Local secret scan of live deliverables | Gitleaks 8.24.2, exit 0, zero findings. This is bounded scan evidence, not a universal secrecy guarantee. |
| Final skill scan | Cisco scanner 2.0.13, exit 1 at high threshold; five findings with reviewed dispositions below. |

The broad suite started before the diagnostic amendment. Already imported
supervisor code used the baseline; copied helper bundles record their own hashes.
The separate supervisor and launcher runs check the final changed behavior.
The live and clean-host packages were produced from the baseline implementation;
the amendment only adds failure reporting fields. Their partial/blocking
package behavior is independently checked by the current unchanged validators.

Principal command strings, supplemental reproduction invocations, output paths,
retained result XML and final collection coverage are recorded in [command results](u20/command-results.json). Reconciliation against final collection confirms **732 of 732 collected tests**
have an actual passing execution. Overlapping runs and the 42 successful subtests
are not added as additional unique tests.

The initial live sandbox occurrence
`run-1578f8eaddcf40e98aa788f6d1f53e35` could not discover SYSTEMS and honestly
produced no snapshots/artifacts. The network-enabled retry used new IDs, retained
that occurrence and recorded supersession. Package-index access and loopback
binding likewise required environment permission; their failed initial records
remain preserved. The first version of the supplementary U20 inspector failed
to decode the brief's documented HTML entity escaping when checking request IDs;
that inspection-tool error was corrected with `html.unescape` and rerun. No
package bytes were changed to satisfy the check.

The actual production invocation was:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/mike/regulatory-compliance/.evidence/u20/tmp /tmp/rci-u03-clean/bin/python regulatory-change-impact-brief/scripts/run.py --config config/review.u20.json --supersedes-run-id run-1578f8eaddcf40e98aa788f6d1f53e35 --change-reason 'U20 fresh live retry with network access after sandbox source-read failure'
```

For a subsequent attended run, follow the [operating guide](../operating-guide.md)
and use the current recognized run as predecessor; the historical explicit ID
above is an execution record, not a command to overwrite newer history.

## Findings, security review and closure

The U20 repair adds affected-stage/output context, a concrete fresh-rerun recovery
action and Operator ownership to retained supervisor failures. Launcher-caught
failures report preflight/recovery context in stdout, although early candidate
setup failures are misclassified and lack a run/candidate reference (E05).
New tests verify retained/archived failure records and that invalid preflight
configuration creates no output. The change does not grant approval or alter
source/authority interpretation. A separate controlled setup-write counterexample
is retained in [failure inspection](u20/failure-gap-inspection.json). A bounded
[independent read-only review](u20/review-notes.md) confirmed E04/E05 and led to the conservative
R0-010 and R9-024–028 statuses.

The skill's name, frontmatter lengths, directory, command and relative references
were [explicitly inspected](u20/documentation-inspection.json) against the [Agent Skills specification](https://agentskills.io/specification).
The short loader dispatches to bounded references; the real-host evaluations
demonstrate that it is invokable. Legacy slice/skeleton branches remain explicit.
The security scan's high finding at `adapters/reads.py:168` is a bounded retry/
redirect loop: counters increment and terminal branches exit. Three medium
findings at `snapshots.py:318`, `:323`, `:556` are dictionary lookups named
`requests.get`, not HTTP calls. The informational missing-license finding is
accepted without inventing a license. No external scanner analyzer or upload
was enabled. These dispositions do not establish that arbitrary model execution
is free of security risk.

Final matrix totals: **453 demonstrated, 28 blocked, 17 not demonstrated, and
4 not applicable with an explicit basis**. “Demonstrated” means the bounded
software assertion or inspection named in that leaf; it does not mean the
organization complies with the law. E01–E03 block successful source-dependent
acceptance. E04 leaves runtime decision emission unimplemented; E05 leaves early setup failure diagnosis incomplete.
E06/E07 record missing integration coverage for all dependency-change categories
and conditional feedback/date propagation. No requirement
is blank. The 32 acceptance scenarios have 26 demonstrated, five not-demonstrated
and one blocked scoped results in
[scenario results](u20/scenario-results.json).

The [hostile-source inspection](u20/hostile-source-inspection.json) records the
actual host processing one malicious external-transfer instruction without
following it; this is bounded evidence, not a universal injection-resistance claim.

Human review, actual approvals, policy activation, approved deadline changes,
incident closure, source-system writes, delivery and production-calendar changes
were not performed. Legal and Operations retain those decisions.
