# U01 baseline contracts

This is the documentary baseline for U02, not an executable schema or a passed
G1 gate. Authority: [requirements](../REQUIREMENTS.md), the unedited
[interview](../interviews/interview-B-3.md), the immutable
[public schema](../snapshot.schema.json), and the
[implementation plan](../TECHNICAL-DESIGN-AND-IMPLEMENTATION-PLAN.md).
Requirement leaves and acceptance owners are in the
[matrix](../docs/requirements-traceability.csv); the
[cases](../docs/acceptance-cases.md) describe future observations, not test results.
Design choices are recorded in the [decision log](decision-log.md).

## Authority and scope

Quillhaven Academy's EU programme, eight actual AI systems, Legal and Operations
as recipients, assigned review date **2026-08-26**. Source routes are declarations,
not verified documents. Neither this baseline nor the interview establishes the
amendment's identity, applicability, legal deadlines, exact live IDs or headers.
Authoritative project requirements constrain the design. Verified binding text,
internal controls, guidance, facts and operational commitments remain distinct
bases at runtime; there is no newest-source-wins priority rule.

Legal decides final interpretations, exceptions and legal/policy conflicts.
Operations decides operational dates, activation and incident resolution.
System owners verify/correct facts; the tool prepares requests for them and does
not update their registers. A draft finding is never final legal advice.

Source access is read-only. Generated local files are permitted. Credentials,
source mutation, policy activation, approved deadline changes, incident closure,
official responses, request delivery and production calendar writes are excluded.
Source instructions are untrusted data, never tool authority.

## Identity, bytes and paths

Every execution/retry receives a new run ID and every snapshot a new snapshot ID.
Source business IDs survive unchanged. Stable impact/action identities use a
versioned key of system, rule basis, obligation/action kind and distinguishing
scope, excluding wording, row order and dates. Changed rule meaning creates a
new rule version with an explicit supersession relationship. Calendar UID derives
from action identity. Internal record IDs bind run and stage.

Serialize snapshots once as UTF-8 JSON. Hash exact written bytes using
`sha256:<64 lowercase hex digits>`. All snapshots belong to one run. Stage 01 has
null predecessor and no consumed IDs. Every later predecessor identifies the
immediate prior snapshot by ID, package-relative path and exact hash.
Consumed IDs resolve strictly upstream in that run; produced IDs enumerate
current-stage records. Same-stage evidence links are permitted in Stage 02 but
are not upstream consumption. Check uniqueness, type, direction and run binding.

Every substantive record carries `id`, meaningful `summary`, `evidence_ids` and
actual typed downstream values. Empty evidence may describe a primary scope
declaration or gap, never support an unverified factual conclusion. Artifact
records add summary/evidence extensions to their public required fields.
The supplied schema stays byte-for-byte unchanged; U02 supplies the stricter
internal contract. Required collections may be empty **where the public schema
permits**; scope, audiences, approval gates and Stage 02 sources are nonempty.

Resolve source/predecessor/analysis paths against the containing package root.
Archived references resolve against the archive root, never current deliverables.
Reject traversal and references outside the permitted package. Preserve exact
available historical bytes; do not repair archives in place.

## Time and state

Scope `as_of` is `2026-08-26T00:00:00Z`, with
`assigned_review_date: 2026-08-26` and `as_of_precision: date`. Midnight UTC is a
serialization convention, not a legal cutover instant. Keep review date,
retrieval time, revision/publication time, effective interval, observation time,
existing due date, proposed date and feedback time distinct. Unknown timezone or
intraday applicability stays unresolved. Newer inputs are accepted syntactically
and assessed separately for historical suitability; retrieval after review date
is not automatically stale.

| Dimension | Exact values |
|---|---|
| Run/stage | complete, partial, blocked, failed |
| Retrieval | retrieved, unavailable, invalid, unverified, stale |
| Impact | supported-impact, supported-no-impact, conflicting, unresolved |
| Approval | pending, approved, rejected, not-required |
| Stage 07 publication | validated, blocked, failed |

Aggregate precedence: failed > blocked > partial > complete. Record-specific
states survive aggregation. Pending human review permits complete/validated
**draft** output. Bounded company gaps permit partial/validated only with
consistent scope/omissions and a documented choice. Required authority failure
is blocked/blocked; withhold dependent formal conclusions. If nothing meaningful
remains, explicitly defer. Broken integrity is failed, even if formats pass.

Unknown predicates give unresolved; contradictory facts give conflicting.
Supported impact and supported no-impact both require affirmative scoped rule
and fact evidence. Missing evidence never implies compliance or non-compliance.
EVIDENCE complete means supplied, partial means missing verification, conflicting
means contradictory report/capture. CALENDAR planned/open/blocked/scheduled/closed
establish neither approval nor completion. Visible disclosure and machine-readable
provenance are separate predicates. Verify provider/deployer role per system;
“mostly deployer” is no default. Notice timing, exposed groups and actual generated
or modified content scope are facts to inspect. Human-review paths describe staff
verification before learner/public delivery under internal policy; interview
statements do not establish legal applicability by themselves.

## Sources and scope bootstrap

All ten disclosed routes in plan §4.1 are required production attempts every run:
LAW, OJ, AMEND, CONSOLIDATED, TIME, FAQ, POLICY, SYSTEMS, EVIDENCE, CALENDAR.
Use original interview locators; no silent fixture or undisclosed endpoint fallback.
Authorized linked reports and bounded retries create additional distinct attempts.
Capture underlying page images, export tests and owner statements, not just labels.

Persist attempt start before dispatch. An attempt retains source/attempt IDs,
original/effective locators, adapter, actual time, tool/HTTP outcome where known,
retrieval state, MIME type, version or explicit unknown, selection/use reason,
identity and historical suitability checks, failures, content/path/hash.
No obtained content means all three content/path/hash values null. An unsuitable
page with content still has retained bytes/hash. Zero-byte obtained content is
distinguished from no response. Unknown MIME uses an explicit unknown indicator.
Diagnostics are not source content. Retain permitted full bytes or exact extracts,
identify the representation and hash that representation. Claim evidence binds
capture, file/hash and section/paragraph/tab/row/cell locator. OCR is derived text
linked to retained images. A URL or hash alone proves no claim.

Prefer authorized predeclared real scope IDs with basis/version. Stage 02 compares
fresh SYSTEMS IDs to frozen scope and exposes discrepancies. An authorized scope
change starts a new run. Without established IDs, initialize the run/journal and
perform only SYSTEMS scope discovery. Successful unambiguous discovery becomes a
Stage 01 produced primary scope-basis record with direct attempt key, original
time/path/hash and no forward Stage 02 record IDs. Stage 02 imports the same
attempt exactly once; no invented second retrieval. Never edit hashed Stage 01.
Failed discovery preserves available bytes/journal and missing-stage inventory;
report incomplete preflight, with no conforming Stage 01/02 package and no R1/R2
package acceptance. Never use placeholders or fake predecessors.

## Stage boundaries

| Stage | State and boundary |
|---|---|
| 01 scope | as_of, review_type, systems_in_scope, audiences, approval_gates; scope/source basis, supersedes_run_id and change/retry reason, config/code fingerprints |
| 02 source-capture | sources plus attempts/captures/evidence/normalized rows/mappings/diagnostics; all required and linked attempts closed honestly before freezing |
| 03 authority-and-timing | binding_rules, timing_rules, guidance_context, authority_blockers; explicit rule versions, predicates, applicability and citations |
| 04 evidence-reconciliation | system_facts, policy_controls, incident_evidence, conflicts, evidence_gaps; retain calendar context and all relevant row accounting |
| 05 impact-analysis | impacts, unaffected_items, conflicts, unresolved_items; each candidate system/rule pair covered or explicitly unresolved |
| 06 actions-and-approvals | proposed_actions, approval_requirements, escalations; review requests/decisions and frozen shared export model |
| 07 publication-validation | artifacts, validation_checks, publication_status; independent on-disk validation, exact detached review bindings and missing-file inventory |

Files are exactly the seven numbered snapshot names specified in requirements.
Render all final artifacts only from the frozen Stage 06 export model, which
carries run/date/status, audience/draft marker, scope, source quality/limitations,
impacts, actions, decisions, review requests and evidence index. No renderer
reinterprets raw sources. Stage 07 independently re-reads disk and compares meaning,
graph, evidence and hashes; renderer success or host exit zero is insufficient.

## Interpretation and decisions

The invoking skill proposes bounded interpretations; Python owns IDs, hashes,
schema checks, joins, state transitions, snapshots and rendering. No separate
model API client. Immutable request packets bind run/stage, upstream snapshot
hashes, captured extracts/hash/locators, date, field dictionary and response schema.
Responses bind exact packet hash, citations/quoted support, conditions, role,
timing/exception candidates, uncertainty and scope. Preserve exact request/response
bytes, parse failures, project instruction/reference versions, visible host/model/
effort metadata, times and available usage under analysis, separate from sources.
Unreported provider state is unknown. No private reasoning is required. No accepted
response reuse across production runs; test replay is explicitly test-only.
Refusal/truncation/unsupported claim is unresolved; corrupt or cross-run exchange
is technical failure. Quote matching and schema checks are not proof of meaning.

Project decision fields: id, summary, evidence_ids, concern, options_considered,
source_basis, chosen_behavior, rationale, tradeoffs, downstream_effect. Label
engineering choices provisional; never present them as stakeholder approval.
Snapshot decisions reference the durable basis relevant to that stage.

Requests include request ID, subject IDs, run/draft version, source versions,
evidence, question, required reviewer and delivery_status (not-sent without actual
delivery evidence). Stage 07 binds each request to final artifact paths and exact
hashes. The brief points to that detached binding and never embeds its own hash.
Feedback retains identity/role, subject/request/version, time, outcome and reasons/
conditions. Apply only after trusted identity/channel authentication and exact
request/subject/version/artifact/role matching. Mismatches remain unresolved.
Older feedback remains tied to its old draft; any effect in a new run requires
facts/source/scope/conditions revalidation. No silent approval transfer.

## Outputs, runtime and recovery

CSV is UTF-8 with header and one row per distinct system/rule impact or unresolved
item. Required columns: impact_id, system_id, rule_ref, state, evidence_ids, reason,
owner, proposed_action, proposed_due_date, approval_status. Planned additions:
run_id, assigned_review_date, action_ids, resolution_need, basis_type, source_versions.
Multiple actions do not duplicate impact rows. Known dates use YYYY-MM-DD; unknown
blanks keep reason/resolution need. Preserve rule bases and explicit reversible
display escaping if formula protection is applied.

The brief includes all R4.2 fields, scoped conclusions and impact/action/evidence
citations, requested decisions and undated-action explanations. Calendar is RFC
5545 VCALENDAR with VERSION/PRODID. Supportable dated proposals only: stable UID,
UTC DTSTAMP, DTSTART, SUMMARY, DESCRIPTION containing action/system/role/basis/
approval plus run/evidence; STATUS:TENTATIVE. Date-only DTSTART is DATE; optional
DTEND is exclusive. Validate escaping, CRLF and UTF-8 folding independently.
Undated actions stay in CSV/brief. Zero dated actions yields a valid empty calendar.

The planned public command is Python run.py with config as in plan §2.1. Supervisor
holds one writer lock, creates an isolated candidate, invokes a fresh skill host
session and independently verifies current-run output. Agent invokes stage.py and
never recursively launches run.py. Configure read-only adapters/local artifact
writes, host login and credential references without secrets. Python 3.12+ and
exact tested dependencies are established in U03, not invented here. U03 must
prove the host exchange before downstream integration. Exit policy planned in
§5.4: 0 complete validated draft, 2 partial validated draft, 3 blocked, 1 failed.

Use isolated .staging/<new-run-id>. Inventory/copy/verify previous available sources,
snapshots, artifacts, analysis and failure metadata into history/<old-run-id> before
replacement. Unknown old run ID stops replacement. Persist incomplete marker with
old/new IDs and verified archive/candidate locations before first current change;
remove old completion marker first. Marker write failure stops overwrites.
Revalidate current files, then bind completion marker to run/Stage 07 hash and clear
incomplete marker last. Incomplete wins over completion. Exact marker schemas are
U02 work; recovery mechanics are U18 work. No multi-file atomicity claim.
Retain interrupted candidate/archive/marker/current bytes under the failed
occurrence before repair. No lost occurrence or mixed-run success. Do not delete
unrelated files. Missing artifacts go in a separate inventory/failed check, never
a fabricated hash; accepted success requires three real valid artifact records.

Record earliest changed dependency stage, then fully rerun all seven stages with
fresh attempts. Inspect actual current files even with unchanged inputs. Retain
failures with stage/source/output/recovery/next owner and storage limitations.
Repair is a fresh command execution with new IDs, not mid-run resume. Automatic
rollback/resume, orphan reconstruction, caching and exhaustive fault campaigns
are deferred. Representative write errors/interruption/second writer are required.

## Questions and gate ownership

| ID | Unknown | Conservative behavior | Owner / affected gate |
|---|---|---|---|
| Q01 | Actual eight IDs, headers, tabs, permissions | Discover authorized sources; expose ambiguous mappings; no guessed IDs/aliases; failed discovery is incomplete | Operator/source owners; U05–U07, G2 |
| Q02 | Linked-report formats/permissions | Retain failed attempt, unsupported representation and unresolved claim | Source owners; U08, G3 |
| Q03 | Reviewer roster/authentication channel | Retain feedback without approval transition; requests remain pending/not-sent | Legal/Operations and operator; U13, G4 |
| Q04 | Host/operator/credential ownership and callable access | Record principals/scopes/references only; failed preflight cannot return success | Operator; U03 feasibility, U05, G4/U19 |
| Q05 | Amendment identity, historical versions and timing | Verify captures; withhold dependent formal conclusions; Legal request | Legal; U09, G3/G4/U20 |
| Q06 | Date-only rule needs timezone/intraday facts | Preserve date precision and unresolved boundary | Legal/source owner; U09, G3 |
| Q07 | Seven snapshots demanded despite no real scope | Explicit incomplete preflight; seek authorized scope or clarified convention if that demand arises | Assignment owner; U07/G2 |

No concrete contradiction requires a frozen architecture change in U01. Generic
empty-collection permission does not override explicit public minItems. Scope
bootstrap does not create a downstream snapshot dependency. Final approval and
successful live retrieval are not prerequisites for documenting this baseline.
