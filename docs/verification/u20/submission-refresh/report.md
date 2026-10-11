# Final submission-artifact refresh

> Historical execution record. The published package is now an explicitly labeled
> [publication derivative](../../publication-remediation.md). The original hashes,
> candidate equality, and preservation claims below describe restricted original
> bytes, not the derivative currently at `deliverables/`.

One fresh live execution completed on 2026-10-10 under the final U20 implementation.
The assigned business review date remains **2026-08-26**. The current
`config/review.u20.json` is unchanged, SHA-256
`44985ebc099e94d447960c610a09f94f8b973bd6ea41275bc7746853ca6c2be0`.

**New run:** `run-b38ca2b36e1044bbba572399b41bf5ae`.
**Predecessor:** `run-f48b4823b3ad4faaa9ac30a301b66505`, identified from the
validated current package before execution. The launcher used its established
supersession, archive and promotion mechanism. The older failed discovery run was
not substituted for the current predecessor.

**Result:** launcher exit **3**, run **blocked**, publication **blocked**,
`production_package: true`, `package_acceptance: false`. All seven snapshots and
three draft artifacts exist; both missing-file lists are empty. There is no
completion marker or incomplete-replacement marker.

The public launcher invocation was:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/mike/regulatory-compliance/.evidence/u20/tmp /tmp/rci-u03-clean/bin/python regulatory-change-impact-brief/scripts/run.py --config config/review.u20.json --supersedes-run-id run-f48b4823b3ad4faaa9ac30a301b66505 --change-reason 'Final submission-artifact refresh after verified U20 remediation and E04 runtime decision-emission repair'
```

The execution had the required external source access and existing authenticated
Codex host. Preflight confirmed `codex-cli 0.162.1`; the configuration requested
`gpt-6.1-sol` with `high` effort. This does not claim hidden provider state.
The [launcher outcome](launcher.log) and empty stderr are retained here.

Current submission artifacts:

- [Compliance brief](../../../../deliverables/compliance-brief.md)
- [Impact register](../../../../deliverables/impact-register.csv)
- [Tentative action calendar](../../../../deliverables/action-calendar.ics)
- [Seven snapshots](../../../../deliverables/snapshots/), from `01-scope.json`
  through `07-publication-validation.json`
- [Run outcome](../../../../deliverables/analysis/outcome.json) and retained
  candidate `deliverables/.staging/run-b38ca2b36e1044bbba572399b41bf5ae/`

**Decision emission:** 14 genuine, unique, run-bound engineering decisions:
Stage 01 **3** (scope, date precision, supersession), Stage 02 **10** (actual source
access and selection outcomes), Stage 05 **1** (blocked draft deferral).
Stage counts are `[3, 10, 0, 0, 1, 0, 0]`. All 14 reach the Stage 06 export model
and compliance brief. Independent reconstruction matches each decision to its
retained inputs, including source basis, evidence links, choice and rationale.
The retained producer inventory matches the final implementation. Engineering
decisions do not represent human approvals.

**Fresh source outcome:** 22 distinct core-source attempts and 26 retained captures
were checked. Attempt IDs are disjoint from the predecessor. OJ, AMEND and
CONSOLIDATED returned HTTP 202 representations without verified usable identity;
POLICY returned HTTP 200 with unverified requested-document identity. Stage 03
retains four Legal blockers, including the absence of an authority interpretation.
No binding rules or supported impacts were accepted. Ten underlying report labels
remain unresolved: their locators identify spreadsheet reference cells, without
authorized fetchable report routes, attempts or captures.

The register contains **8 unresolved coverage rows**, one for each scoped system.
There are **0 proposed actions**, **0 calendar events**, and **2 unsent requests**
for Legal and Operations. Existing calendar records in the brief retain their
source context; they are not promoted into new proposals. Legal must verify usable
authority, version, scope and timing. Policy/source owners must establish policy
identity through authorized access; system owners and Operations must supply
underlying report routes and evidence. No inaccessible evidence, legal meaning,
approval or action was invented.

**Validation passed:** all seven public schemas and format checks; typed and
semantic package reconstruction; snapshot predecessor hashes and same-run graph
links; exact capture and artifact hashes; CSV coverage/cardinality; ICS format;
exact Stage 07 bindings to all three artifacts for both unsent review requests;
decision reconstruction/export/brief propagation; blocked-state and marker
consistency; and byte equality of all ten candidate/published snapshots and
artifacts. The [live inspection](live-inspection.json),
[supplemental validation](validation.json), and
[occurrence consistency](occurrence-consistency.json) retain results and hashes.
The [refresh checker](validate-refresh.py) invokes the existing read-only U20
package checker; no regression suite was rerun.

**Historical preservation passed:** all **100,903** pre-refresh protected files
remain byte-identical. **172** prior managed files are preserved in
[`deliverables/history/run-f48b4823b3ad4faaa9ac30a301b66505/`](../../../../deliverables/history/run-f48b4823b3ad4faaa9ac30a301b66505/);
**100,731** files remain unchanged at their original paths, including original
audit records, prior candidates and raw verification evidence. The archive
inventory and archived package validate against the archive's own root. Original
audit references to the old live package should be read against this archive;
the original audit text and results were not rewritten.
The [before record](before.json) identifies the controlled full preservation
inventory and its hash. No historical bound package was retroactively amended.

**READY FOR COMMIT WITH DOCUMENTED EXTERNAL BLOCKERS.** The fresh submission is an
integrity-validated blocked review draft, not accepted compliance or human
approval. No concrete runtime defect was demonstrated, so no implementation code
was changed. `git diff --check` passed. No broad audit, regression rerun, commit,
push, source write or review delivery was performed. The original
[U20 audit](../../final-report.md) and [remediation report](../remediation-report.md)
remain historical evidence; this report supplements them with the final occurrence.
