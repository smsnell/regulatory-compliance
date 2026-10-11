# U20 remediation and final acceptance closure

> Publication update: references to original submission bytes remain historical.
> The current public package uses [sanitized derivatives](../publication-remediation.md);
> exact originals are restricted outside Git. This does not change audit findings.

## Scope and evidence boundary

This is a focused closure of E01–E07 in the original [U20 report](../final-report.md)
and [exception register](exception-register.md). Those files, their underlying
verification records, captured source bytes, and historical runs remain the audit
baseline. This report supplements them; it does not amend their observed results.
The [remediation baseline](remediation/baseline.json) records the pre-remediation
working tree, including changes already present before this work.

No application redesign, new architecture audit, project commit, or push was performed.
Astra performed cross-stage reasoning and E04 implementation; Sol handled isolated
E01 and E07 repairs. The primary agent handled E05/E06, integration, and closure.
External and synthetic content was treated as untrusted data. Synthetic reviewer
identities and responses demonstrate software behavior only.

**Final verdict: READY FOR COMMIT WITH DOCUMENTED EXTERNAL BLOCKERS.**

Implementation filenames below are under
`regulatory-change-impact-brief/scripts/rci/`; test filenames are under
`tests/runtime/`. The three renderer files are `renderers/brief.py`,
`renderers/csv_register.py`, and `renderers/calendar.py`. The
[changed-file inventory](remediation/implementation-files.json) records exact baseline
and final hashes for implementation, tests and current-facing documentation.

## Exception closure

### E01 — PARTIALLY RESOLVED

**Original:** Official written dates and document identifiers failed literal ISO
and selector prerequisites; historical applicability and the live authority
exchange remained ambiguous.

**Correction:** Bounded representation mappings accept complete ISO dates, full
English calendar dates with ordinary/NBSP spaces, EUR-Lex dotted calendar dates,
and the observed OJ/CELEX identity forms. They check selector identity, captured
version headers and contradictory aliases. Exact quotes and offsets, source and
capture IDs/hashes, original/effective locators, version identity, and encoded
dates are retained in the existing authority accounting extension.

**Files:** `authority.py`, new `authority_representations.py`,
`references/authority-policy.md`, new `test_u20_authority_remediation.py`;
`test_u09.py` and `test_u10.py` retain both frozen schema hashes and explicitly amend
the implementation hash. The latter pin was corrected after the full regression
identified its old value.

**Evidence:** The original observed `12.7.2024` failed before repair. Positive tests
use retained official formats, including `2 August 2026`; adversarial tests reject
invalid, unsupported, ambiguous, contradictory and mismatched representations.
A new synthetic submission/freezing case verifies mapping provenance and untouched
upstream bytes. Focused result: **57 passed**. Initial U09 regression: **52 passed,
2 failed**; a concurrently changed decision producer caused the CLI failure and
an expected implementation fingerprint amendment caused the other. Both exact
cases passed under final code. Original logs remain retained.

**Residual owner/action:** Legal must determine paragraph-specific qualifications,
historical applicability and the ambiguous exchange. Relative commencement
formulas remain unresolved. A mapping does not upgrade source authority or assert
legal meaning. The original live exchange still yields zero accepted binding rules.
Obtain authentic review, then reacquire in a new occurrence. Technical mapping is
closed; legal interpretation is not.

### E02 — EXTERNALLY BLOCKED

**Original:** POLICY returned HTTP content without verified requested document identity.

**Investigation:** Rechecked the retained response hash, title and identity metadata,
and the supported read mechanisms. The captured title is `Notion`; the requested
policy identity/version/activation is not established. POLICY's generic reader
supports public GET; the existing authenticated credential flow is for Sheets.
No additional authorized route/content was supplied. Repeating the same request
would not establish identity or authorization.

**Files/evidence:** No adapter change. [Source-access investigation](remediation/source-blockers.json)
records exact retained source/capture references and the supported mechanism boundary.

**Owner/action:** Policy/source owner and operator must supply identifiable content
through an authorized supported read route, followed by fresh acquisition.

### E03 — EXTERNALLY BLOCKED

**Original:** All ten underlying EVIDENCE reports are labels with no fetchable routes.

**Investigation:** The report adapter requires explicitly supplied permitted HTTPS
URLs. Each retained reference still has a null route and no attempt/capture IDs.
No URL, report body, access permission, or read success was invented.

**Files/evidence:** No adapter change. All ten entries are retained in the
[source-access investigation](remediation/source-blockers.json).

**Owner/action:** Named system owners, coordinated by Operations, must provide
authorized fetchable report routes and supporting evidence, including avatar,
localisation, owner statements and exception basis. Then use a fresh public run.

### E04 — RESOLVED

**Original:** Runtime snapshots and exported brief had no engineering decisions.

**Correction:** Actual scope/declaration/discovery, date precision, source attempts
and selection outcomes, complete/partial/defer disposition, and supersession/recovery
choices now produce deterministic run-bound records. They include required concern,
options, source basis, choice, rationale, trade-offs and downstream effects. Their
record/evidence links participate in normal graph validation and Stage 06 export;
published briefs render the decision trail. No count-only synthetic decisions were
inserted. New Stage 01 occurrences opt into `rci-engineering-decisions/1`; old bound
packages with verified legacy provenance remain readable.

**Additional validation repair:** A stripping regression demonstrated that removing
the decision profile and records could masquerade as legacy. New runs retain
`analysis/producer-code.json`, the preimage of the existing code hash. Production
validation rejects profile removal, malformed/mismatched inventories and contradictory
bundles, including simulated later producer versions with the marker and inventory
both removed. Markerless production inputs need a verified old bundle or one of
four exact evidenced legacy scope snapshots and their producer fingerprints; unknown unproven legacy prefixes fail
closed. A final copied-prefix regression exposed that merely claiming one of the
known producer hashes could bypass the guard after stripping metadata. The unbundled
fallback now also requires the exact canonical Stage 01 witness hash. Four new
adversarial cases cover all claimed legacy pins. Verified old bundles retain their
existing validation path. Generic schema/graph validation is unchanged, and intermediate packages
already containing reconstructed decisions need no retroactive rewrite. Exact
legacy witness copies and inventories are in [legacy producer evidence](remediation/legacy-producers).

**Files:** New `decisions.py`; `runner.py`, `snapshots.py`; new
`test_u20_decisions.py`; the new legacy witness README documents the exact fallback.
No frozen JSON schema was changed.

**Evidence:** Two scope witnesses failed before repair. Seven scope/access/tamper
cases, 57 existing U07 cases, and 58 contract cases plus 39 subtests pass. Fresh
public COMPLETE/PARTIAL/BLOCKED/recovery cases passed. A test assumption that
BLOCKED meant no brief was corrected to require the blocked brief and its decisions;
its exact rerun passed. Initial final projection/provenance adversarial checks: **20 passed**.
After the claimed-legacy correction: **24 passed**, including four new impersonation
cases; all original legacy readability checks also passed.
Legacy U02/U03/U07 regression: **166 passed, 39 subtests passed**. All original
verified packages remain readable. The first recovery test scratch directory was
automatically pruned by pytest retention; its passing log remains, and final full
regression uses a durable basetemp for new recovery artifacts.

### E05 — RESOLVED

**Original:** Initial candidate/context write failures escaped as launcher-preflight
without run/candidate context; feedback/archive setup inherited the capture label.

**Correction:** Lock acquisition, current inspection, candidate initialization,
individual input writes, feedback archival and retention now sit inside accurately
labelled failure handling. Outcomes identify the planned run/candidate even when
storage is unavailable. Only a successfully created owned candidate is writable;
`diagnostic_persistence` and `diagnostic_record` distinguish retained evidence from
stdout-only diagnostics. A failed persistence attempt cannot claim a saved record.

**Files:** `pipeline.py`; new `test_u20_failure_remediation.py`.

**Evidence:** Ten controlled witnesses failed before repair. Initial focused result:
**64 passed** across the new failures, U20 diagnostics and U03 launcher checks.
Includes config/scope/context/inspection writes, unwritable storage, mkdir, current
inspection, feedback/archive setup, and a competing writer. Prior bytes survive.
Operator guidance identifies affected paths, owner and fresh-run recovery action.

### E06 — RESOLVED

**Original:** Only source changes had actual producer integration coverage; other
seven-position comparisons used manually assembled fingerprint dictionaries.

**Correction:** Real `_fingerprints` now includes declared-scope provenance and
previously omitted helper/reference dependencies, including the new authority and
decision modules. Stage-specific dependencies remain stage-specific. Shared runtime,
graph and recovery machinery conservatively affects Stage 01. Occurrence IDs,
retrieval timestamps and output-root relocation do not manufacture substantive changes.

**Files:** `pipeline.py`; new `test_u20_dependency_remediation.py`.

**Evidence:** Seven missing-input witnesses failed before repair. The final bounded
integration uses fresh, independently validated Stage 01/02 captures and isolated
actual copied code/reference/config/scope/feedback changes through the production
fingerprint producer and classifier. It checks the earliest stage, unchanged earlier
fingerprints, all-seven recomputation and fresh-read requirements. **55 tests plus
3 subtests passed**, including U18 and E05 regressions. An initial fixture wiring
mistake passed a Path instead of EvidenceStore; its 25 setup errors are retained
and the corrected fixture passed without changing assertions.

G5 supplies the actual changed-source, fresh IDs/outputs, supersession, byte-exact
archive and corrupt-current recovery half of this composite evidence. E07 adds
actual changed-date/content/feedback public workflows. Repeating an identical full
workflow for every code whitespace mutation would add cost without testing another
branch: the supervisor always recomputes every stage. Unchanged fingerprints never
mean reused source attempts or outputs.

### E07 — RESOLVED

**Original:** Conditional feedback and changed date/content had no complete-workflow,
independently parsed artifact evidence.

**Correction:** Stable date-binding comparison resolves only the generated source-row
pointer through retained content, while preserving actual dates, explanation and
source semantics. Valid conditions remain explicitly unmet and approvals pending. A changed-date
public run exposed a second defect: quarantining feedback dropped the verified
prior-draft pointer. Intake now retains that exact historical binding before
current-basis revalidation, without authorizing a current subject.
The export includes the feedback ledger; matched feedback appears in the register,
brief and calendar, and unmatched prior feedback stays visible without approving
changed subjects. Independent validators reconstruct those displays from records.

**Files:** `reviews.py`, `actions.py`, the three renderers, `validate.py`; new
`test_feedback_remediation.py`; the old source-resolution export fixture now explicitly
includes its required empty `feedback` collection, with an added omission assertion.

**Evidence:** The dated-basis regression failed before repair. Focused review,
renderer and validation checks: **106 passed**. A minimized disk-backed regression reproduced the lost-pointer defect and
passed after correction; 107 focused cases then passed. The preliminary broad
regression was interrupted before applying this production change, and its
partial evidence remains retained rather than counted as a completed run.
A new four-occurrence public fixture
uses authenticated synthetic reviewer feedback, unchanged scope, changed date,
and changed report content. The retained-baseline replay passed all unchanged
permanent assertions for all three variants, including independent artifact parsing,
exact history/binding checks and three semantic condition-tamper checks. A separate
public rejection witness passed scoped-rejection checks across all three files,
with unrelated approvals still pending.
No synthetic response is organizational authorization. The CLI still leaves unmet
conditions pending; it does not invent condition satisfaction.

## Requirement and scenario traceability

The original not-demonstrated set is exactly **17 leaves**:

| Exception | Requirement leaves | Fresh acceptance evidence required |
|---|---|---|
| E04 | R0-010; R6-001–R6-008 (9) | T27, T32 |
| E05 | R9-024–R9-028 (5) | T17 |
| E06 | R9-001–R9-002 (2) | T30 |
| E07 | INT-082 (1) | T13 |

T29 and the original 28 source/authority-blocked leaves are not closed by synthetic
engineering verification. The original 453 demonstrated and four not-applicable
leaves remain the historical baseline. The [new leaf closure](remediation/leaf-closure.json)
and [new scenario results](remediation/scenario-results.json) demonstrate all 17
previously not-demonstrated leaves and T13/T17/T27/T30/T32. Current totals:
**470 demonstrated, 28 blocked, four not applicable with basis**; **31 demonstrated
scenarios and T29 blocked**. No actionable leaf or scenario remains unverified.
See [closure counts](remediation/closure-counts.json).

Current-facing `README.md`, `docs/operating-guide.md`, `docs/acceptance-cases.md`
and `docs/requirements-traceability.csv` now link the new evidence. The original
U20 report, exception register, leaf observations, scenario observations and hashes
remain unchanged. The closure helper initially checked the abbreviated status name
`not-applicable`; it was corrected to the matrix's existing
`not-applicable-with-basis` value without changing any of those four rows.

## Contract and history preservation

The public snapshot schema, typed contracts schema, requirements and dependency lock
are unchanged. The amended `snapshots.py` implementation fingerprint is
`sha256:cbb640b9cf165851fd5675b55a246a2f7b5fc1b2545717c7b12c8b6e95ad1ee8`;
the prior implementation hash remains in the baseline and E01 evidence. Additive
accounting/export data uses existing extensibility. There is no new legal authority
or approval contract.

Read-only validation under the amended implementation accepted original live run
`run-f48b4823b3ad4faaa9ac30a301b66505` (blocked) and clean-host synthetic run
`run-a7b50ae23a714c07aaa101ec88f3d70e` (partial/validated). No captured run or signed/bound
artifact was rewritten. New executions use distinct IDs and normal history mechanisms.

## Independent package inspection

[Consolidated inspection](remediation/consolidated-inspection.json) passed for nine
retained packages under the final production code: COMPLETE, PARTIAL, BLOCKED,
conditional, changed date, changed content, rejection, original live, and original
clean-host synthetic. The independent original U20 checker verifies seven-stage
schema/graph identities, source/capture and artifact hashes, CSV rows, brief entries,
calendar events and bindings; production package validation also passes. BLOCKED
remains blocked and legacy packages retain their original zero-decision observation.

| New retained witness | Run ID |
|---|---|
| COMPLETE decisions | `run-25dfc8518d384594b11d1ee460626971` |
| PARTIAL decisions | `run-6d852e3dee914a238c1bdb549338f6c0` |
| BLOCKED decisions | `run-07c8a3ec84034f2ab14ceab46e9c0cb3` |
| Conditional feedback | `run-20294d3f0df84da4896e17e0dff1d741` |
| Changed date | `run-d385e16d20894c8cb59153a0526680c6` |
| Changed content | `run-caba25c8903b49c9a2f9555bef6bd498` |
| Rejected feedback | `run-445e7f696781415684f2201e827b9e16` |

The feedback baseline is `run-59af6d47ffd14563bdbe9844951843ea`.
[Replay results](remediation/replay-results.json) and [rejection results](remediation/rejection-results.json)
record paths and exact prior artifact bindings. These are synthetic witnesses; the
original blocked live deliverables are preserved for review.

The final full regression also retains two independently inspected recovery
occurrences: `run-bef7f09352174464b7f0b2fa223b8221` supersedes
`run-4c88d37233f24340bee31eb9b2b01196`; changed-source recovery
`run-67adf0d3b9434a8ea71b88a52c3618ec` supersedes
`run-47c85e98276242029923990c78042946`. [Recovery evidence](remediation/recovery-results.json)
records the new decision, disjoint attempt identities, all seven snapshots, and
hashes of the deliberately damaged briefs retained in history. Both independent
inspections pass, bringing the consolidated package checks to **11**. The initial
inspection helper used an overly long pytest directory prefix; that bookkeeping
failure was corrected to the actual retained path before successful inspection.

## Verification and scanner evidence

One consolidated full regression is warranted because decisions, snapshot
validation, supervisor failure handling and feedback rendering affect shared core
behavior. It is partitioned by disjoint whole test files, preserving module fixtures;
three U05 checks requiring external paths/loopback are recorded separately. Original
clean-environment installation, actual managed host investigation and inaccessible
live source attempts are intentionally not repeated: their unchanged boundaries
remain evidenced by the original audit, while repairs receive deterministic integration
and legacy compatibility checks.

### Executed commands and counts

[Exact commands, exit codes and JUnit/log links](remediation/command-results.json)
and the [per-node execution inventory](remediation/executed-checks.json) reconcile
**872 collected tests: 866 distinct tests passed, six intentionally skipped, zero
unresolved failures or missing executions**. The full run also passed **42 subtests**.
Focused counts overlap the full suite and are not added to the distinct-test total.

| Execution | Observed result |
|---|---|
| Full regression shard 1 | 237 passed, 2 failed, 6 skipped; 3 subtests passed |
| Full regression shard 2 | 299 passed |
| Full regression shard 3 | 320 passed, 1 failed, 3 environment tests excluded; 39 subtests passed |
| Three environment tests | 2 passed; loopback socket denied by sandbox |
| Authorized loopback rerun | 1 passed |
| Final source-resolution export module + exact U10 pin/CLI case | 12 passed; all three full-run failures resolved |
| Final E04 provenance/tamper checks | 24 passed, including four newly added claimed-legacy cases |
| Independent package inspections under final code | 11 passed |

The broad regression ran once to completion, through this actual driver invocation:

```sh
PYTHONDONTWRITEBYTECODE=1 .evidence/u20/venv/bin/python .evidence/u20-remediation/run-regression.py regression-final
```

The [driver copy](remediation/run-regression.py) and [partition manifest](remediation/regression-commands.json)
record every disjoint pytest file list, interpreter, environment and durable basetemp.
The run kept production/test hashes fixed for its entire duration. Afterwards, the
old U10 implementation pin and incomplete export fixture were corrected; assertions
were retained and an empty-feedback omission assertion added. Their exact rerun was:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/mike/regulatory-compliance/.evidence/u20-remediation/tmp .evidence/u20/venv/bin/python -m pytest -q tests/runtime/test_source_resolution_export.py tests/runtime/test_u10.py::test_cli_submission_separate_packet_and_schema_fingerprints --basetemp=.evidence/u20-remediation/final-maintenance --junitxml=.evidence/u20-remediation/final-maintenance.xml
```

The final E04 fallback correction additionally compares an already recorded exact
scope hash; its [source delta](remediation/final-source-delta.json) is explicit.
All 24 affected provenance cases, original legacy witnesses and 11 retained full
packages passed under this final code. A second full workflow regression was not
repeated: the changed predicate is confined to the unbundled, markerless legacy
fallback, while current marked workflows and verified bundles use unchanged paths.
The four new cases are included in the final 872-test collection and execution union.

The six skips are duplicate matched-condition tamper combinations for changed-date
and changed-content feedback, which is quarantined rather than matched. Each
artifact's matched-condition tamper check executes for the unchanged variant;
independent artifact/date/content/history assertions execute for all three variants.
No failure was converted into a skip.

The earlier preliminary broad run was interrupted to fix the demonstrated E07
prior-binding defect; its partial logs are preserved and not counted as a completed
regression. All red/green investigations and environment failures remain visible.

The [local skill scan](remediation/skill-scan-exact-legacy.md) exits **1** with the same five
findings: one bounded retry loop (HIGH false positive), three local dictionary
`requests.get` calls (MEDIUM false positives), and absent optional license metadata
(INFO accepted without inventing a license). [Dispositions](remediation/skill-scan-disposition.json)
record manual review. No cloud scanner or upload was enabled.

The [portable evidence secret scan](remediation/portable-secret-scan-result.json)
passed with **zero findings**. Raw evidence is retained untouched. Portable logs
redact only three exact deliberately synthetic credential labels; the
[lineage inventory](remediation/portable-lineage.json) records both hashes and
substitution counts. Test outcomes and counts are unchanged.

## Evidence retention and final checks

The [history integrity check](remediation/history-integrity.json) confirms all
**226 protected pre-remediation files remain byte-identical**, including original
U20 observations, original deliverables, frozen requirements/contracts and retained
Entire settings. Ignored original audit evidence was not modified. New final
regression artifacts remain under `.evidence/u20-remediation/regression-final/`;
new portable records are under `docs/verification/u20/remediation/`.
`git diff --check` and local report-link checks pass.
Existing pre-remediation changes, including `scripts/run.py`, are not represented
as new fixes in this report. No project commit, push or unrelated cleanup occurred.

## Final verdict

**READY FOR COMMIT WITH DOCUMENTED EXTERNAL BLOCKERS**

E04–E07 and E01's technical representation gap are closed with implementation and
verification evidence. Legal interpretation remains assigned to authorized Legal
review; identifiable POLICY content and underlying reports remain assigned to
source/system owners and Operations. No live compliance approval, policy activation,
source-dependent conclusion, or synthetic organizational authorization is claimed.

