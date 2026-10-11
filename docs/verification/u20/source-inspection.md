# U20 source meaning and human-boundary inspection

Verifier: Codex, attended U20 review, 2026-10-10. Live occurrence:
`run-f48b4823b3ad4faaa9ac30a301b66505`. The original candidate remains in
`deliverables/.staging/<run-id>/`. These are observations about retained source
representations and the software's handling of them, not legal determinations.

## Scope and company evidence

Inspected Stage 02's 8 SYSTEMS rows, 10 EVIDENCE rows, 8 CALENDAR rows and
the corresponding retained CSV captures. Exact IDs are AI-001 through AI-008;
the calendar's `ALL` row does not create a ninth system. Scope was discovered
from the current SYSTEMS route, not supplied by a synthetic fixture. The assigned
date remains 2026-08-26; October retrieval times do not replace it.

| System | Register assertions inspected | Acceptance boundary |
|---|---|---|
| AI-001 | Learner chat; notice `yes`; `complete`; staff escalation; closed evidence record | The notice/release report is only the label `notice-screen-v3`. Neither label establishes independently verified notice or compliance. |
| AI-002 | Applicant email drafting; notice `unknown`; partial/missing evidence; advisor approval path | Missing disclosure evidence stays unresolved; the named human review path is a source assertion. |
| AI-003 | Public synthetic images; `visible_label`; complete SYSTEMS versus conflicting EVIDENCE | Visible disclosure and exported machine-readable provenance are separate predicates. The possible metadata loss needs the underlying export. |
| AI-004 | Learner interaction; notice `no`; evidence note reports no first-interaction notice | Preserve the reported absence and existing September 4 task date; no invented legal finding or approval. |
| AI-005 | Learner assessment flags; provider role unknown; stale role questionnaire; human adjudication | A deployer field does not resolve the missing provider role. The report that flags never decide assessments is not an inspected SOP. |
| AI-006 | Staff summaries; notice not applicable; staff-only assertion; closed evidence record | Restricted use and operational closure do not prove a legal exclusion or completed compliance action. |
| AI-007 | Public avatar; notice `no`; owner/banner versus capture contradiction; Marketing owner | `avatar-page-capture` is a label, not available underlying bytes. Retain the reported conflict and ask for the capture/owner evidence. |
| AI-008 | Public audio/video; visible label; provenance not checked; exception draft lacks approval/expiry | `localisation-export-test` and `exception-draft-008` supply no fetchable route. No provenance inference, approved exception or invented expiry. |

All ten EVIDENCE references are plain labels. Stage 02's
`extensions.u08_reports.value.reports` records each as unresolved, with its row
locator, system, owner and empty attempt/capture lists. Those lists are honest:
there is no authorized URL to dispatch. The required report inspection is **blocked**,
not demonstrated by a register note describing a report. System owners must supply
authorized fetchable routes or the permitted evidence through a supported adapter.

CALENDAR's eight rows retain task, owner, fixed existing date, source version,
native status and required reviewer. ACT-008 applies to ALL. Native planned/open/
blocked/scheduled/closed values do not authorize dates or establish completion.
No feedback or authenticated reviewer roster was supplied for this live run.

## Authority and policy

Inspected each legal/context extract by its Stage 02 evidence ID in
`analysis/authority/request.json`, including identity/version passages and
the surrounding commencement paragraphs. The complete request and host proposal
are retained; this note does not reproduce the legislation.

| Capture | Inspection and remaining limitation |
|---|---|
| OJ | Body identifies Regulation 2024/1689 and the original journal publication. Written calendar dates in the binding paragraphs are not literal ISO date strings. |
| AMEND | Body identifies 2026/1744 and expressly describes amendments to 2024/1689. The adapter's unverified state is not proof of an unrelated act. The exact encoded route selector required by the current interpretation contract is absent from the visible body. |
| CONSOLIDATED | Body identifies `02024R1689 — EN — 27.07.2026 — 001.001`, lists the amendment relationship and warns that the consolidation is a documentation tool. It cannot acquire independent binding authority from successful retrieval. |
| LAW | Reproduction identifies the July 27 consolidation. Its current captured content does not independently authenticate its historical content at the assigned date. |
| TIME | Explanatory timeline contains amendment context. Current retrieval does not establish a historical page version or override binding paragraphs. |
| FAQ | Body carries a July 24 update label. Its explanations remain context; the host flagged numbering/qualification differences for Legal rather than converting them into binding predicates. |
| POLICY | HTTP returned content but the requested policy identity/content was not verified. No internal control can be established from the route title alone. |

The host returned an ambiguous authority exchange. Stage 03 retains two blockers
and **zero supported binding rules**. Accordingly, there are no accepted material
legal predicates whose semantic accuracy could be certified by this review.
The five textual candidate bases are retained proposals; they are not delivered
formal conclusions. The host returned `ambiguous` under the contract's literal ISO-date and selector
requirements; this inspection did not separately submit a positive exchange to
exercise a validator rejection of those readable representations. That is an
implementation compatibility limitation requiring a reviewed mapping change,
not evidence that the source lacks a commencement rule. Historical applicability
and final interpretation remain Legal's decisions.

## Synthetic semantic witnesses

The T01 fixture states its own synthetic rule, scope, exception, dates and all
ten factual predicates for each of eight systems. Its expected 16 impacts refer
separately to the legal fixture and internal control. `test_u17_complete.py`
checks that complete analysis leaves all approvals pending, all requests unsent,
and the original partial capture snapshots unchanged. Its resolution ledger
must account for each of the 18 specific original diagnostics; forged or
unassessed resolution cannot improve the result.

`test_u11.py::test_four_states_evidence_scopes_and_coverage` independently varies
the notice evidence: supported absence, supported presence, contradictory values
and unknown. The expected impact states differ; wrong scope and reported-only
predicates cannot establish a supported exclusion. These test explicit supplied
meanings, not the current company's compliance.

`test_u13.py` uses separate synthetic identity policy and authentication evidence;
wrong role, subject, source version, artifact or date cannot authorize a decision.
Its conditional case stays pending until separate condition evidence is supplied.
The live package contains no such human decision, and no request was sent.

The clean-environment actual host also encountered a captured instruction to
send source files to an external server. The [bounded hostile-source inspection](hostile-source-inspection.json)
binds the exact request/capture/proposal and twelve completed reconciliation
commands. The proposal rejects the instruction; observed commands only read/check
local material, write an analysis proposal and submit it to the helper.
