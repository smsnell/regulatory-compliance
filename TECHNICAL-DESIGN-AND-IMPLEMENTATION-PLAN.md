# Regulatory change impact brief: technical design and implementation plan

Prepared 2026-10-07. **Planning document only; implementation has not started.**

This plan recommends a local, attended Agent Skill workflow with seven immutable stage snapshots, captured source evidence, deterministic Python processing and validation, and bounded interpretation by the invoking agent. Its endpoint is a review-ready draft for Legal and Operations. The architecture does not include source-system writes, message delivery, policy activation, incident closure, or production-calendar access.

Architecture review revision: the skill owns semantic interpretation; a separate model API client is deferred. Recovery uses verified history, isolated run directories and detectable incomplete replacement, with fresh reruns instead of automatic transaction repair. Model starting efforts are recalibrated in §7. Scope inputs are preferred; the narrowly constrained bootstrap exception is justified in §4.3. The seven stages, G1–G5, requirements traceability, human authority and fail-closed rules are retained.

## 1. Authority, scope, and unresolved design inputs

The authoritative project inputs are [REQUIREMENTS.md](REQUIREMENTS.md) and the original [interview export](interviews/interview-B-3.md). The supplied [snapshot schema](snapshot.schema.json) is the immutable public format contract. The README supplies repository/skill delivery context. External technical documentation supports engineering choices; it does not replace these project inputs or establish the applicable law.

Input fingerprints for this planning baseline:

| Input | SHA-256 |
|---|---|
| REQUIREMENTS.md | `eed1f9d24fcdc9e86b95bd6235eb6e82ea62d915d01f28d6d409329df9cde2c3` |
| interviews/interview-B-3.md | `c3c0167379d0beaeef9ddd88826c6b585017e66620aee43e2ca5a26f9480c7fd` |
| snapshot.schema.json | `8de9874ded18fa97294e83012796e4c386aa60ccfd30f8eca89cabdf2a267ac3` |

Requirements are referenced below as R1–R13, corresponding to their numbered sections, plus R0 for the objective, prohibitions, assigned date, and required output tree. Interview references use the recorded times, which are locators within the export rather than independently authenticated event timestamps.

Fixed scope:

- Organization: Quillhaven Academy, EU programme, eight AI systems.
- Assigned review date: **2026-08-26**, even when the run occurs later.
- Recipients: Legal and Operations. System owners supply and correct system facts.
- Legal decides final interpretations, policy/legal conflicts, and exceptions. Operations decides operational dates, activation, and incident resolutions. These decisions are not performed by the software.
- Source registers and status labels are evidence inputs, not automatic approval signals.
- All required sources are attempted live on every production run. Test fixtures are never a silent production fallback.

Three unresolved inputs affect implementation detail, but do not prevent this plan:

1. **Live access and schemas:** the interview provides routes and field meanings, not the actual eight system IDs, exact headers, tab layout, permissions, or all linked report formats. U05–U08 must discover these through the intended routes and document supported mappings. Do not invent them.
2. **Verified decision channel:** authorized roles are known, but the identity roster and feedback authentication route are not. Until configured, feedback may be retained but cannot change approval state. This does not prevent a pending-review draft.
3. **Runtime credentials and ownership:** use the present attended workspace as a provisional pilot environment. The operator, permitted model service, and read-only source credentials must be named during setup without recording secret values. A blocked live access path produces a visible blocker.

This plan does not assert that the interview's amendment route is valid, that its claimed document exists, or that any particular legal timing rule applies. Those are runtime verification tasks. The source URLs below are declared inputs, not evidence of successful retrieval.

## 2. Architecture and deployment decision

### 2.1 Proposed execution model

Use one Python launcher command, a local filesystem evidence store, an invoking skill/agent, and deterministic stage helpers. Use JSON/CSV/Markdown/iCalendar as the durable interchange formats. Eight systems and ten core sources do not warrant a database, vector index, queue, web application, or hosted scheduler for the first version.

Proposed command, to be implemented and documented:

```bash
python3 regulatory-change-impact-brief/scripts/run.py --config config/review.json
```

The config declares the assigned date, required source routes, permitted access adapters, recipients, expected system count or authorized IDs with scope basis, an agent profile, and references to credentials held outside the repository. It does not contain tokens. The production command always makes fresh required source attempts. Separate test commands may use fixtures and isolated temporary output directories; production cannot accept a fixture-mode fallback.

`run.py` is a thin deterministic supervisor: create the run, hold its writer lock, invoke the installed skill in a fresh agent session, retain its visible execution metadata, and independently validate the resulting on-disk package before returning a run outcome. For this environment the proposed host is `codex exec`; local inspection found Codex CLI 0.161.0 with noninteractive execution support. Setup must register the supplied skill and configure read access plus local artifact-write permissions. The agent uses `scripts/stage.py` to acquire sources, request bounded interpretation packets, submit structured interpretation, and advance the Python state machine. It never recursively launches `run.py`. No separate Python model SDK or project-specific model API key is required.

One invocation must reach the final package or an explicit partial/blocked/failed outcome without an operator copying interpretations between commands. An agent's successful exit or reassuring text is insufficient: the supervisor verifies the new run ID, fresh attempts, stage chain, package status and actual files. U03 proves host invocation and protocol feasibility early; G4 and U19 prove the complete command. If the installed host cannot do this with the permitted access and recorded interpretation contract, stop that gate and reconsider a direct API adapter; do not describe a two-command manual handoff as compliance with R11. Existing host authentication and usage limits remain runtime dependencies. [Codex noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode); [skill invocation](https://learn.chatgpt.com/docs/build-skills).

Recommended runtime: Python 3.12 or later, with one tested minor version and exact dependency versions recorded in the eventual lockfile. Use standard-library `csv`, `json`, `hashlib`, `datetime`, `pathlib`, and `argparse`; a maintained HTTP client; `jsonschema`; `icalendar`; and `pytest`. Add HTML/PDF extraction only for formats actually observed. Pin released dependencies during U03 rather than inventing version pins now. Explicit JSON Schema format checking is required; validation libraries do not necessarily check date formats by default. [jsonschema validation documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/).

### 2.2 Access and trust boundaries

| Boundary | Primary recommendation | Cost/trade-off and fallback |
|---|---|---|
| Public legal pages and public policy | Read-only HTTP against the disclosed routes, preserving redirects, bytes, identity, and retrieval metadata | Lowest operational burden. If an intended page needs rendering, use a documented browser adapter; retain failed HTTP attempts too. |
| Google source registers | Official read-only sheet access that the CLI can invoke, using the disclosed document IDs; discover tabs before reading | Exact ranges and structured values are preferable. An existing connector/MCP is acceptable if callable from the end-to-end command with equivalent evidence retention. A chat-only connector cannot satisfy unattended script execution by itself. |
| Public sheet exports | Use only if the export route is authorized, identifies the requested document/tab, and preserves needed values and locators | Low setup; may lose revision metadata or tabs. Do not assume the first tab contains everything. |
| Linked underlying reports | Follow disclosed evidence links with an allowlisted read adapter; capture page images/export tests/text as needed | Extra reads are necessary because register labels alone do not prove the claims. Unsupported formats stay unresolved. |
| Source text to model | The invoking agent interprets bounded captured evidence and submits structured candidates to Python | Source text is data. The run profile excludes source mutation and message/calendar tools; read credentials stay in adapters. Local file tools remain available, so a prompt alone is not a security boundary. Hash checks, allowed operations and independent final validation enforce the package contract. Only necessary permitted extracts enter model context. |
| Draft storage | Local `deliverables/`, with history and staging beneath it | Simple to inspect and hand off. Access control and backup inherit the host's arrangements; avoid logging secrets or publishing evidence implicitly. |

Do not introduce undocumented service endpoints as a shortcut. Prefer an adequate existing source connection; add an official API integration only where the repeatable command requires it. Browser fallback must expose failures and retain evidence, not convert a login screen into a successful source read.

Credential inventory at setup: public web reads need none; private source OAuth credentials have owner/principal/scope/storage recorded; the agent reuses its existing host-managed login. Record the host/account owner and credential reference, never auth-file contents. Use an existing OS or platform credential store. Unknown permissions are not treated as read-only merely because the task says so: adapters expose only reads, and tests reject mutation methods. Local artifact writes are explicitly permitted by the project.

These are **provisional recommendations**, not claimed stakeholder approvals. The stated read-only/human-authority limits are project constraints. A move to unattended or shared operation triggers reconsideration of hosting, ownership, credential lifecycle, concurrency, and retention. A request to send or activate anything would be a separate scope change.

### 2.3 Deterministic code versus model work

Deterministic code owns IDs, hashes, schemas, time normalization, attempt accounting, exact joins, approved field mappings, decision-version matching, state transitions, history, CSV/ICS rendering, and validation. No model call is needed for those tasks.

A bounded interpretation exchange lets the invoking skill propose legal/policy rules or claim extractions when document structure alone is insufficient. Python creates an immutable request packet with run/stage identity, upstream snapshot hashes, captured extract hashes/locators, assigned date, field dictionary and expected response schema. The agent returns a response bound to that packet hash, including quoted support, evidence IDs, conditions, role, timing/exception candidates, uncertainty and scope. `interpretation.py` validates the exchange; it is not an API client. Python alone computes hashes, writes accepted snapshots, applies state transitions and renders artifacts. Candidate interpretations cannot approve decisions or rewrite captures.

For the initial live skill invocation, use `gpt-6.1-sol` at `high` because authority/timing interpretation and ambiguous policy semantics are its substantive model work. Known tabular mappings, established impact predicates and all rendering run in code; do not add separate wording calls or per-row model calls. Model refusal, truncation, unsupported output, missing citations, or ambiguous meaning yields unresolved records; a corrupt or cross-run exchange is a technical failure. Stronger model reasoning cannot resolve missing facts or grant human authority. Structural validation and quote matching do not prove legal meaning; U09's evidence inspection and Legal's final interpretation boundary remain necessary.

Retain exact request/response bytes, parse failures, skill/reference/instruction versions, input hashes, visible host version/configuration, requested and reported model/effort, timestamps and available usage. Provider-hidden prompts/model snapshots or unreported usage are explicitly unknown. Store this derived analysis in `deliverables/analysis/` separately from primary sources and include it in run history; stage records bind the accepted exchange by path/hash. No private chain of thought is needed. Do not reuse accepted responses across runs; test-only replay with fixed inputs verifies deterministic downstream behavior. A fresh production run need not produce byte-identical semantic judgments. Keep interpretation exchanges narrow and log bounded format-correction attempts; a failed-run retry gets a new run ID.

### 2.4 Architecture review decisions

| Current design | Considered alternative | Decision | Rationale and affected requirement/invariant | Trade-off |
|---|---|---|---|---|
| Python calls a separate model API | Invoking skill interprets captured evidence through a validated exchange | Adopt skill-owned interpretation; keep Python supervisor/stage helpers | R11 demands one reproducible command, not a standalone model client; R12 explicitly requires a skill. Packet provenance preserves R1/R6/R10/R13. | Depends on host authentication, version and context discipline; API adapter only if command/provenance feasibility fails or unattended service operation later requires it. |
| Promotion transaction journal, backups and automatic resume/rollback | Isolated candidate, verified archive, incomplete marker, rejection and fresh rerun | Adopt the simpler recovery procedure in §5.3 | R8/R9 require preservation, detection, repair or explicit failure; they do not require automatic resumption at the interrupted instruction. | Interrupted replacement may need an attended fresh rerun; no claim of multi-file atomicity. |
| Several bounded units start at Sol high | Frozen contracts plus lower starting effort and targeted escalation | Change U01/U08/U11/U12 to medium; raise U03 to medium for the host boundary | Expected total cost includes retries and review. Retain high for graph/provenance, legal authority, reconciliation, approval/version binding, final validation and recovery. | More explicit escalation criteria; no reduction in tests or gate strength. |
| Implicit bootstrap read before scope | Declared scope IDs as normal input; narrowly justified first-run discovery fallback | Prefer documented scope input; retain constrained fallback with explicit provenance and incomplete-run rules | Schema requires nonempty scope and no upstream consumed records; it does not forbid input discovery before snapshot 01. R1/R2 require truthful boundaries and all attempts. | Failed discovery cannot yield seven conforming snapshots; it must be reported as incomplete, never accepted as a compliant draft. |

Runtime comparison supporting the first decision:

| Dimension | Separate API in Python | Invoking skill/agent |
|---|---|---|
| Reproducibility | Explicit request parameters and narrow prompts; still stochastic and subject to service/model changes | Same deterministic replay after a recorded response; fresh-session profile and packet discipline reduce context drift; exact semantic replay is not promised |
| Auditability | Request/response logging is straightforward | Must explicitly persist the exchange; conversation history or Entire logs alone are insufficient |
| Credentials | Project API secret, SDK/configuration, provider billing setup, in addition to source access | Existing host login; source credentials still needed; host access is not free or universally available |
| Failure modes | API auth, rate limits, transport, schema errors and interpretation mistakes | Host/session failure, context contamination, skipped helper calls, malformed interpretation and host limits; supervisor must detect incomplete/mismatched output |
| Token/usage cost | Can be cheaper for repeated narrow calls, but may duplicate source context already loaded by a skill | Avoids a second inference path and credential setup; a bloated session could cost more, so use fresh invocation, focused packets and measured usage rather than assuming savings |
| Prompt/version provenance | Application can record its full request, with provider internals still unknown | Record all project-controlled instructions and host-visible metadata; disclose hidden or unavailable host state rather than inventing it |
| Unattended execution | Natural fit for a service once all access is configured | A noninteractive host can run a skill, but persistent unattended service operation is not required here and remains unproven until tested |
| One-command compliance | Python orchestrates everything | Python invokes the skill and independently validates completion; multiple internal helper calls are allowed, manual copy/paste is not |

## 3. Core contracts and invariants

The supplied schema is intentionally permissive. A second, project-owned contract layer must enforce the behavioral constraints it cannot express. Keep that layer in the skill package; do not modify `snapshot.schema.json`.

### 3.1 Identity and record graph

- A new execution or recovery retry gets a new `run_id`; every snapshot gets a new `snapshot_id`. Never recycle a previous run's identifiers.
- Separate stable business IDs from run-specific record IDs. Preserve source system/action/incident IDs. Derive new impact/action business IDs from a versioned canonical key: system, rule basis, obligation or action kind, and distinguishing scope. Dates, text wording, and row order are not identity components.
- A material change in the meaning of a rule creates a new rule-version reference. Link superseded meanings explicitly rather than silently reusing their identity.
- Internal record IDs include run and stage identity. Cross-file `impact_id` and `action_id` remain stable when the business item is unchanged. Calendar UID derives from stable action identity; the run is carried separately.
- Every substantive record has `id`, meaningful `summary`, and `evidence_ids`, plus typed downstream values. Empty evidence is allowed for an explicitly unverified scope declaration or gap, not as support for a factual conclusion.
- Snapshot `consumed_record_ids` resolve to earlier stages in the same run. `produced_record_ids` enumerate the records produced in that stage. Evidence links can reference Stage 02 evidence records, including records created within Stage 02, without pretending they are upstream consumption.
- A graph validator checks uniqueness, existence, permitted direction, type, and run binding. Operational IDs that collide or disagree become identity conflicts; no fuzzy join resolves them automatically.

### 3.2 Byte integrity and source evidence

Snapshots are serialized once as UTF-8 JSON and then treated as immutable. The successor hashes the **exact bytes written**, using `sha256:<64 lowercase hex digits>`. Hashes are not computed over a separately normalized object. Stage 01 has null predecessor and no consumed IDs; Stages 02–07 point to the immediately previous snapshot in the same run.

Stage 02 distinguishes source declarations, attempts, captures, and claim-bearing evidence. One source can have many attempts and captures. A request returning an unsuitable HTML page still has captured bytes and a hash; a request returning no content has `content: null`, `content_hash: null`, and `local_reference: null`. A separate diagnostic file is not mislabeled as source content. A transport that returns no MIME type records an explicit unknown content type such as `application/octet-stream` plus `content_type_known: false`.

Each attempt includes source ID, attempt ID, original locator, effective locator, adapter, start/end or retrieval time, HTTP/tool outcome where available, retrieval status, content type, version metadata or explicit unknown, content/hash/path, identity checks, date-suitability assessment, selected/unused flag and reason, and any recoverable failure. Store full bytes where permitted or the exact permitted extract used with its location and representation metadata. Hash the retained representation and identify it as full content or extract. Do not claim an extract hash is a hash of an uncaptured original document.

Evidence records bind an assertion or quoted passage to capture ID, local file, hash, and section/paragraph or sheet/tab/row/cell locator. Preserve original row positions even though joins are independent of order. Underlying screenshots or exports need their own captured evidence; OCR is derived text with a locator back to the retained image. A bare URL, status label, or content hash is not claim evidence.

### 3.3 Time and applicability

Keep separate fields for assigned review date, actual retrieval time, source revision/publication time, source effective interval, factual observation time, existing operational due date, proposed due date, and reviewer response time.

Because the supplied scope schema requires a date-time, encode `as_of` as `2026-08-26T00:00:00Z` and add `assigned_review_date: 2026-08-26` and `as_of_precision: date`. This is a documented serialization convention, not a newly asserted legal cutover instant. Date-only applicability is evaluated at date precision; any rule requiring an unknown timezone or intraday boundary remains unresolved.

Accept legitimate newer versions and dates syntactically. Separately evaluate whether a source supports the historical assigned date. A current register can be captured successfully but fail to establish a fact on 2026-08-26. Do not label all post-review retrievals stale, move the assigned date, or invent historical facts. Staleness is based on a documented relevant revision/supersession problem, not an arbitrary age threshold.

### 3.4 Domain state and authority

Keep these independent enums exactly as required:

| Dimension | Values |
|---|---|
| Run/stage | `complete`, `partial`, `blocked`, `failed` |
| Retrieval | `retrieved`, `unavailable`, `invalid`, `unverified`, `stale` |
| Impact | `supported-impact`, `supported-no-impact`, `conflicting`, `unresolved` |
| Approval | `pending`, `approved`, `rejected`, `not-required` |
| Stage 07 publication status | `validated`, `blocked`, `failed` |

Source-native labels are additional fields. Interview meanings are explicit: EVIDENCE `complete` means supplied evidence, not compliance; `partial` indicates missing verification; `conflicting` indicates contradictory reports/captures. CALENDAR `planned`, `open`, `blocked`, `scheduled`, and `closed` do not establish approval or completion. A visible label is distinct from machine-readable provenance. A provider/deployer role must be verified for each system; “mostly a deployer” is not a universal assignment.

Rule records separate binding legal basis, internal control, explanatory guidance, factual assertions, and operational commitments. LAW/OJ/AMEND declarations are candidates whose returned identity and applicable legal content must be checked. CONSOLIDATED is a navigation/version reference until authority is established; TIME and FAQ cannot independently override binding text. An apparent conflict between sources is preserved for Legal; the software cannot fix it by selecting the newest URL or a convenient summary.

Impact evaluation requires both an established rule basis and the necessary factual predicates. `supported-no-impact` needs affirmative support for the stated scope; absence of evidence does not qualify. Unknown predicates produce `unresolved`; contradictory facts produce `conflicting`; supported impact is a reasoned draft finding, not final legal sign-off. A single system may have several distinguishable legal and policy impacts.

### 3.5 Run outcomes

| Situation | Run outcome | Stage 07 | Artifact treatment |
|---|---|---|---|
| All required analysis supported; review requests awaiting humans | `complete` | `validated` | Clearly marked draft; approvals still pending. |
| Bounded missing company facts, with unaffected supported work | `partial` | `validated` only if the limitation and all omissions reconcile | Include gaps and scoped findings; only supportable dated proposals. |
| Unverified/unavailable required legal authority for the review | `blocked` | `blocked` | Withhold dependent formal conclusions; retain blocker chain, requests, and only independently supportable proposals. |
| Missing inputs prevent meaningful remaining work | `blocked` | `blocked` | Explicit deferral decision and bounded diagnostic draft where possible. |
| Broken integrity, unsafe write, or unrecoverable technical failure | `failed` | `failed` if Stage 07 can be written honestly | Preserve available evidence; do not claim a complete package. |

Use a documented reducer: technical failure takes precedence over blocked, blocked over partial, and partial over complete. Individual records retain their own outcomes even when the aggregate run is blocked. A missing optional context source may yield partial output; the basis for treating it as optional must be explicit. The interview's ten sources are all required attempts; attempt requirement and legal-authority prerequisite are different concepts. Absent required authority cannot be reclassified as optional to get a green result.

## 4. Source inventory and seven stage boundaries

### 4.1 Disclosed source routes

| ID | Disclosed route | Intended use, subject to verification |
|---|---|---|
| LAW | `https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50` | Official paragraph text |
| OJ | `https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng` | Original regulation identity and binding text |
| AMEND | `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL_202601744` | Claimed amendment route; validate returned act and relevance |
| CONSOLIDATED | `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02024R1689-20260727` | Disclosed navigation/version reference |
| TIME | `https://ai-act-service-desk.ec.europa.eu/en/ai-act/eu-ai-act-implementation-timeline` | Implementation context checked against applicable authority |
| FAQ | `https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act` | Explanatory context |
| POLICY | `https://private-pecorino-70e.notion.site/Project-2-Regulatory-Compliance-Current-Internal-Policies-3ba0b700541e81f09998d48f3b1c2856` | Internal controls and their version/activation evidence |
| SYSTEMS | `https://docs.google.com/spreadsheets/d/10ky745H_1h9XbGCXPJsiRp5yfdeU08TZtmrsCMinGgU` | System identities, uses, roles, users, notice and review facts |
| EVIDENCE | `https://docs.google.com/spreadsheets/d/19BYZ68OSbsa1i9OfF6MzthrdC6q6mt6IWk6ucI8u7Rk` | Evidence/incident records and links to underlying reports |
| CALENDAR | `https://docs.google.com/spreadsheets/d/1xtXl_P7Yb9LaECZjjgtlyI-idoAJTAhH-1gQ4vQaCGA` | Existing action identities, owners, dates, states and review paths |

Record additional authorized routes with their authorization basis; never replace the disclosed attempt record. Record each bounded retry separately. A follow-up document reached from an authorized evidence link is an additional source, with its originating record retained. Do not crawl unrelated links.

### 4.2 Stage interfaces

| Stage/file | Inputs | Required and additional state | Boundary verification |
|---|---|---|---|
| 01 `01-scope.json` | Config, assigned request, declared scope IDs with their basis (or constrained discovery under §4.3), previous-run inspection | Required `as_of`, `review_type`, `systems_in_scope`, `audiences`, `approval_gates`; scope/basis records, source declarations, `supersedes_run_id`, retry/change reason, config/code fingerprints | Date fixed; eight-system expectation explicit; authority roles; unique run IDs; no predecessor or downstream record dependency |
| 02 `02-source-capture.json` | Frozen scope/source declarations; all current-run attempts, including any §4.3 discovery attempt | Required `sources`; additional captures, evidence records, normalized rows, field mappings, diagnostics | Every attempt represented exactly once with original times/bytes; linked report acquisition complete or failure explicit; hashes/identity checked; all ten attempts accounted for |
| 03 `03-authority-and-timing.json` | Scope and captured legal/policy evidence | `binding_rules`, `timing_rules`, `guidance_context`, `authority_blockers`; rule versions, conditions, timing basis | No legal rule supported by guidance alone; assigned-date applicability established or blocked |
| 04 `04-evidence-reconciliation.json` | Captured company facts/reports, scope, Stage 03 constraints | `system_facts`, `policy_controls`, `incident_evidence`, `conflicts`, `evidence_gaps`; retained calendar records and scope reconciliation | All relevant rows and linked report attempts accounted for; contradictory values remain distinct |
| 05 `05-impact-analysis.json` | Rules, timing, reconciled facts and unresolved chains | `impacts`, `unaffected_items`, `conflicts`, `unresolved_items`; a system/rule coverage ledger | Each applicable candidate pair has a supported disposition or explicit gap; no missing-fact default to no-impact |
| 06 `06-actions-and-approvals.json` | Impacts, existing actions, verified optional feedback | `proposed_actions`, `approval_requirements`, `escalations`; review requests, decision records, frozen export model | Stable IDs; actions deduplicated without losing basis; dates and role approvals distinguished; all request fields present |
| 07 `07-publication-validation.json` | Frozen Stage 06 export model and exact rendered file bytes | `artifacts`, `validation_checks`, `publication_status`; review-request/artifact bindings and completeness inventory | Independent re-read of three files, all seven snapshots, graph, evidence and hashes; status policy enforced |

Stage 01 fixes the requested scope; Stage 02 verifies current sources against it. Supplied scope IDs do not establish present or historical system facts. Missing/additional/conflicting live IDs remain scope issues; do not silently change a frozen scope list. An authorized change in scope starts a new run. The normal and discovery paths are specified below.

Final artifacts are rendered from Stage 06 only. Earlier-stage information needed by a renderer must be explicitly carried into the frozen Stage 06 export model with source references, preventing renderers from reinterpreting raw sources independently.

### 4.3 Scope bootstrap review and selected interpretation

**Schema evidence:** `allOf` for sequence 1 requires `predecessor: null` and `consumed_record_ids` of length zero. The scope branch requires a nonempty `systems_in_scope` list of strings; the source-capture branch requires nonempty `sources`. No clause constrains the time of a source read relative to `created_at` of Stage 01, or prohibits input acquisition before it. R1 requires snapshots at workflow boundaries; R2 requires every attempt in Stage 02 with actual retrieval time. Interview 03:21 requires confirming relevant IDs. These support a scope-input discovery operation, not a dependency on a future Stage 02 record. Schema validity alone does not establish this workflow interpretation.

**Normal path:** config contains actual, documented scope IDs from an authorized request or retained, explicitly identified scope input. Stage 01 records the input's basis/version and makes no claim that old operational facts are current. Stage 02 freshly reads SYSTEMS and every other required source, compares IDs, and preserves discrepancies. This is the simplest conforming path and eliminates routine bootstrap work. Do not create a second setup workflow solely to move an untracked live read out of the run.

**Fallback when no IDs are established:** initialize the new run and attempt ledger first, then perform only the SYSTEMS identity/scope discovery needed to establish scope. Before network dispatch, persist an attempt-start record; as content arrives, retain bytes under that run's candidate `sources/` and persist original locator, actual time, version, status, hash/path and locators. Incomplete capture is an interrupted/unsuitable attempt, never a fabricated success. If source identity and the in-scope IDs are unambiguous, write Stage 01 with those actual IDs and a produced `scope_basis` record containing the attempt key, capture path/hash and original retrieval time. Its `evidence_ids` may be empty as a primary scope-input record with direct capture provenance. It consumes no upstream snapshot records and contains no forward Stage 02 record ID. The attempt key is a journal identity, not a `consumed_record_id`.

Stage 02 imports that same attempt as a source record exactly once, links it to the upstream scope-basis record and the same captured bytes, and retains its original retrieval time. It does not pretend a second retrieval occurred or move the time after Stage 01. A required additional read is a separate attempt, and conflicting results remain visible. Stage 01 is never edited after Stage 02 references its hash. Stage 02 closes only after required and discovered linked-report attempts are complete or explicitly unsuccessful; discovering a necessary source later requires a new run, not appending to a hashed snapshot.

**Failure path:** when IDs cannot be established, retain the journal, bytes that exist, failure reason and missing stage inventory under the failed run. No fabricated IDs, `TBD` scope item, empty schema override, or Stage 02 with a fake predecessor is allowed. There is no conforming Stage 01/02 package in this branch; explicitly report an incomplete preflight occurrence and do not claim R1/R2 package acceptance. If a separately established scope list exists, it permits Stage 01 and a truthful Stage 02 even when the live read fails; gaps/blockers propagate normally. A retry uses a new run ID and fresh attempts.

**Rejected alternatives:** retroactively populate Stage 01 after Stage 02 (breaks order/hash provenance); use descriptive placeholders just because the schema accepts strings (does not establish actual system IDs); treat a previous capture as an undisclosed live fallback (R2 violation). Predeclared IDs are preferred, but requiring manual entry of facts the authorized SYSTEMS route can unambiguously disclose is unnecessary.

The only boundary ambiguity requiring stakeholder clarification is conditional: if the assignment is intended to require seven conforming snapshots even when no real system identity can be established, that expectation conflicts with the schema's nonempty scope and the prohibition on invented facts. Request an authorized scope list or a clarified preflight-failure convention; until then the incomplete failure is explicit. Successful bootstrap needs no additional human approval merely because it precedes snapshot 01.

## 5. Output, review, history, and recovery design

### 5.1 Shared export model

Freeze one export model containing run/date/status, recipients/draft marker, limitations, impacts, actions, decisions, review requests, and evidence index. Store its fingerprint in Stage 06. All three renderers receive that model; Stage 07 independently checks their parsed meaning against it.

CSV uses the eleven required columns, plus `run_id`, `assigned_review_date`, `action_ids`, `resolution_need`, `basis_type`, and `source_versions`. Keep one row per distinct system/rule impact or unresolved item. Multiple actions attach through stable action IDs; do not duplicate an impact row merely to enumerate actions. Keep detailed action data in the brief/Stage 06. Unknown values can be blank only with visible reason and resolution need. Preserve source strings in evidence; any spreadsheet formula-safety escaping in the display CSV must be explicit and round-trip tested so it cannot silently alter IDs or meaning.

The Markdown brief is template-driven and cites IDs for every substantive observation/action. It states draft/run status, date, recipients, source quality and limitations, supported scope, conflicts, unknowns, proposals, proposed dates, and decisions requested. It points to detached Stage 07 review bindings. It never embeds its own hash.

The ICS renderer creates `VCALENDAR`, `VERSION`, and `PRODID`; each dated proposal has stable action-linked UID, UTC DTSTAMP, DTSTART, SUMMARY, DESCRIPTION, and `STATUS:TENTATIVE`. DESCRIPTION includes action/system IDs, responsible role, source/decision basis, approval status, plus run/evidence references. Date-only inputs become all-day DATE values; optional DTEND is exclusive. Undated actions stay in CSV/brief only. An empty valid calendar is required when no dates are supportable. Validate escaping, CRLF, UTF-8 line folding, and date types using RFC rules and a parser in addition to semantic comparisons. [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545); [icalendar library](https://icalendar.readthedocs.io/en/latest/).

### 5.2 Review and feedback

Every project decision uses an explicit record with `id`, `summary`, `evidence_ids`, `concern`, `options_considered`, `source_basis`, `chosen_behavior`, `rationale`, `tradeoffs`, and `downstream_effect`. This includes engineering choices such as access route, date encoding, full recomputation, partial-versus-deferred output, and how conflicting evidence is handled. A provisional design choice is labelled provisional; it is not an authorized Legal or Operations decision. Snapshot `decisions` carry the decisions relevant to that stage and reference their durable design basis.

A review request has request ID, subject IDs, run/draft version, source version(s), evidence, question, required reviewer role, and `delivery_status: not-sent` unless actual external evidence says otherwise. Creating a request is not sending one.

After final bytes are rendered, Stage 07 maps each request to exact artifact paths and hashes. The binding is detached, so no self-hash cycle exists. Feedback must match request, subject, reviewed run/version, artifact binding, authorized identity/role, response time, outcome, and conditions. A role string inside untrusted feedback is not identity verification; require the configured trusted channel or explicitly authenticated operator input. Reject/quarantine mismatches and preserve them as unresolved.

Verified feedback to an older draft remains evidence about that draft. Carry its effect into a new run only after testing whether the relevant facts, source versions, scope, and conditions remain applicable. Never transfer an old approval automatically to changed content. Record which matters remain pending. Incorporating feedback changes draft records, not external policy, approved source dates, or incident status.

### 5.3 History and safe replacement

Use `deliverables/.staging/<new-run-id>/` for work in progress and one OS-managed writer lock for this local runtime. Before replacing current managed outputs, inventory and copy the previous available `sources/`, `snapshots/`, three artifacts and interpretation/failure metadata into `deliverables/history/<old-run-id>/`, preserving bytes and relative paths. Verify the archive before replacement; an existing archive is never overwritten with different bytes. Retain missing/corrupt-item findings separately; never repair historical bytes in place or claim nonexistent files were archived. If no trustworthy prior run ID can be recovered, preserve the current files in place and stop replacement with an explicit diagnostic. Automated orphan identification/reconstruction is deferred.

Paths in snapshots are package-root-relative. Resolve a history package against its archived root, not current `deliverables/`, so a historical predecessor or source reference cannot accidentally resolve to newer files. Store the resolution convention in the manifest.

A multi-file replacement is not an atomic filesystem transaction. Use a small incomplete-replacement marker with old/new run IDs and the verified archive/candidate locations; remove any old completion marker before the first current-file change. If that marker cannot be persisted, do not start replacement. Copy only the known managed files from the verified candidate, independently validate the current paths, then write a completion marker bound to the new run/Stage 07 hash and clear the incomplete marker last. A leftover incomplete marker always wins over a completion marker. Readers/validators and the launcher reject the current package during replacement; direct manual readers must wait for completion. No mixed-run package may be accepted or handed over as output, although interruption can leave incomplete files at the fixed paths. Supporting concurrent manual reads with atomic generation switching is outside this attended scope.

An interrupted replacement is a failed occurrence. Keep the candidate, previous archive, marker and available current bytes; preserve the latter under the failed new run's occurrence area before a repair overwrites them. Use the same failure inventory format rather than a transaction replay engine. The recovery path is a fresh end-to-end run with new IDs and new source attempts, followed by verified replacement. It does not resume interrupted acquisition or reuse an old interpretation as new evidence. The intact previous archive remains inspectable. Basic write-error/interruption and second-writer rejection tests are required; automatic rollback, automatic mid-promotion resumption and exhaustive power-loss fault simulation are deferred. Do not delete unrelated files under `deliverables/`.

Archive every failed attempt with its journal and available outputs. If the public artifact schema cannot describe a missing file without a hash, omit its artifact record, record it in a separate `missing_artifacts` inventory and failed validation check, and mark publication failed. Do not use a fabricated or empty hash. The success contract still requires exactly three valid artifact records with real hashes.

Recovery classification (a required guarantee does not mandate every possible resilience mechanism):

| Classification | Mechanisms kept or deferred | Requirement/invariant or concrete failure |
|---|---|---|
| Required | Verify and preserve previous available bytes before replacement; record missing/corrupt evidence; retain failed occurrences and interpretation exchange; new IDs/supersession; fresh rerun; inspect actual files and dependency changes | R8/R9, with provenance and honest status under R1/R10/R13 |
| Required correctness behavior | Isolate unfinished work from current output; reject incomplete or mixed-run packages; detect stale/damaged files; never overwrite history on archive failure | Otherwise a failed attempt can destroy the required history or falsely claim completion |
| Strongly justified, included | One candidate directory per run; existing byte hashes; one small replacement/completion marker pair; one OS writer lock; archive-relative resolution; targeted write-error and interruption tests | Two accidental launches and an interrupted local copy are plausible; these are small implementations of the required guarantees |
| Optional/stretch, deferred | Detailed transaction journal, automatic rollback/resume, additional backups beyond required history, exhaustive disk-full/power-loss interleavings, distributed locks, automatic orphan repair, incremental computation cache | No persistent service, parallel writers or zero-downtime requirement; fresh rerun and explicit incomplete result suffice here |

Disk-full **handling** remains required as a write error: stop, keep whatever evidence was actually written, and report storage limitations. Creating a full filesystem and testing every write position is optional. Likewise, an unknown prior run ID requires a truthful stop/preserved files, not an orphan-repair subsystem.

### 5.4 Recalculation and repair

Record stage input fingerprints, contract/code versions, and dependencies. Detect the earliest changed basis: scope/config → 01; source content/mapping → 02; authority logic → 03; reconciliation → 04; impact rules → 05; actions/feedback → 06; rendering/validation → 07 and affected outputs.

For the first implementation, fully rerun all seven stages for every execution after fresh required reads. This is simpler and cheap at this scale, meets the dependency rule conservatively, and avoids reusing stale source claims. Record the earliest changed stage for audit even though recomputation is broader. New IDs and retrieval times alone are not treated as substantive source changes. Optimization may later reuse pure computations keyed by content and contract hashes; it must still regenerate the run-bound snapshots and fresh source attempts.

Even when content is unchanged, validate actual current files, not a prior success flag. A repair creates a new run, preserves the failed occurrence, regenerates dependent work, and reruns the documented command with fresh attempts. Failed storage itself may prevent a full journal; report that limitation directly on stderr and in any surviving journal. Proposed exit codes: 0 complete/validated draft; 2 partial/validated draft; 3 blocked; 1 failed. Partial is usable but cannot be mistaken for complete by a caller.

## 6. Proposed repository organization

These paths are planned components, not files created by this design task.

```text
regulatory-change-impact-brief/
  SKILL.md
  scripts/
    run.py
    stage.py             # deterministic helper invoked by the skill
    rci/
      contracts.py       ids.py             snapshots.py
      evidence.py        source_manifest.py adapters/
      normalize.py       authority.py       reconcile.py
      impacts.py         actions.py         reviews.py
      export_model.py    renderers/         validate.py
      history.py         recovery.py        runner.py
      interpretation.py  # request/response contract validation; no model API client
  references/
    contracts.md         source-manifest.json
    field-dictionary.json authority-policy.md
    decision-log.md      review-protocol.md
    failure-policy.md    gotchas.md
    schemas/             templates/
  eval/
    README.md            cases/             expected/
config/
  review.example.json
tests/
  unit/ contracts/ integration/ acceptance/ fixtures/
docs/
  requirements-traceability.csv
  verification/         operating-guide.md
pyproject.toml
requirements.lock
snapshot.schema.json    # unchanged
deliverables/
  sources/
  analysis/              # derived interpretation packets and visible execution metadata
  snapshots/01-scope.json ... 07-publication-validation.json
  impact-register.csv
  compliance-brief.md
  action-calendar.ics
  history/<old-run-id>/
```

The skill should be a short invocation/workflow loader with references loaded on demand. Its frontmatter name matches the directory; description explains when to invoke it. The body identifies prerequisites, command, seven stages, output/status semantics, recovery, and human boundaries. Detailed contracts and prompts belong in references. Validate against the [Agent Skills specification](https://agentskills.io/specification). Use a security scan and canonical evaluation cases when authoring the actual skill; a clean scan does not prove semantic correctness.

## 7. Model allocation and minimum-context policy

These recommendations concern the **implementation worker for each unit**, separately from the invoking runtime agent described above. Available session choices include GPT-6 Luna, GPT-6.1 Sol, GPT-6 Sol, GPT-5.6 Sol, and GPT-6 Astra. Prefer the first, second, and last for this project; there is no demonstrated project-specific advantage to using older Sol variants.

Current official documentation positions [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) for efficient focused work, [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) for complex work at lower cost than Astra, and [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) for demanding reasoning. The recommendations below are engineering judgments that must be checked against actual task outcomes.

For cost scale, published standard short-context API rates per million input/output tokens are Luna $0.10/$0.50, Sol 6.1 $2/$10, and Astra $10/$50. These are API prices, not a claim about this session's subscription usage accounting. Context tier, processing mode, cache behavior, tools, and reasoning affect actual cost. Verify prices and availability before execution. [Official pricing](https://developers.openai.com/api/docs/pricing).

Use low effort for mechanical work, medium for localized semantics, high for cross-stage reasoning. Escalate only the failing/ambiguous unit. Default escalation ladder: Luna low → Sol medium; Sol medium → Sol high; Sol high → Astra high. Use Astra xhigh only for unresolved system-wide contradictions after a minimized reproduction. Do not default to max effort or repeat whole-project reviews for formatting changes.

Architecture-review recalibration, assessed against frozen contracts and expected rework rather than cheapest single attempt. `Sol` below means `gpt-6.1-sol`, `Luna` means `gpt-6-luna`, and `Astra` means `gpt-6-astra`.

| Units | Previous → starting model/effort | Why sufficient / reason to retain | Escalation trigger → target |
|---|---|---|---|
| U01 | Sol high → **Sol medium** | Architecture decisions now exist; leaf mapping and acceptance-oracle drafting are bounded | A requirement contradicts a frozen decision or cannot be assigned a truthful acceptance case → Sol high; unresolved cross-stage contradiction → Astra high |
| U02 | Sol high, retained | Graph, IDs, scope basis and interpretation binding failures propagate across all stages | Incompatible invariants or an unresolved provenance counterexample → Astra high |
| U03 | Luna low → **Sol medium** | Adds a real host invocation boundary and independent outcome checking; more than scaffolding | Host permissions, recursive invocation, or completion/version ambiguity → Sol high |
| U04–U07 | Sol medium, retained | Local provenance implementation, source identity, field mappings and scope have fixed contracts but need careful integration | Lost attempt/bytes, ambiguous identity/meaning, or scope/boundary mismatch → Sol high; missing access/meaning → source owner |
| U08 | Sol high → **Sol medium** | Implements the G1-frozen interpretation exchange and report capture; no API client or new semantic authority policy | Cross-run packet accepted, unverifiable extract binding, or ambiguous report representation → Sol high; unresolved provenance flaw → Astra high |
| U09 | Sol high, retained | Legal authority and historical applicability remain interpretive and high consequence | Conflicting authority/version chain → Astra high; final interpretation → Legal |
| U10 | Sol high, retained | Reconciliation can silently erase contradictory facts across sources | Overlapping identities or unresolved many-record contradiction → Astra high |
| U11 | Sol high → **Sol medium** | Implements the truth table and coverage ledger already frozen at G3 | A new rule predicate, exception interaction or incorrect scope propagation → Sol high; unresolved cross-rule contradiction → Astra high |
| U12 | Sol high → **Sol medium** | Exact deduplication and proposal rules can be specified before coding; ambiguous matches stay unresolved; approval application stays in U13 | Deduplication loses a rule basis, date provenance disagrees, or a rule needs multi-role interpretation → Sol high |
| U13 | Sol high, retained | Identity, version and conditional authorization mistakes can manufacture approval | Unclear conditional approval/version applicability → Astra high; missing authentication → human owner |
| U14–U16 | Luna low, retained | Render frozen values using format libraries and round-trip cases | Export contract ambiguity, wording changes meaning, or parser/date disagreement → Sol medium |
| U17 | Sol high, retained | Independent disk validation must catch correlated cross-file and provenance errors | Renderer/validator agree on a demonstrably wrong package → Astra high |
| U18 | Sol high, retained | Simpler recovery still protects irreplaceable history and failure evidence | An interruption can lose history or accept a mixed run → Astra high |
| U19 | Luna medium, retained | Package/document tested behavior; use U03's proven loader | Invocation mismatch or interpretation regression → Sol high |
| U20 | Astra high, retained | One final independent system-wide review for omissions and correlated errors | Concrete unresolved cross-stage counterexample → Astra xhigh |

For lower starting efforts, supply the frozen interface, truth table and negative fixtures before implementation. If they do not exist or the task requires changing their meaning, escalate before coding. This is not permission to lower effort on an unsolved provenance or authorization problem. Measure usage plus corrective attempts; one unexplained invariant failure is sufficient to escalate, rather than repeatedly retrying a cheaper setting.

Each unit receives: its task card; named requirement clauses/interview excerpts; directly used contracts/interfaces; files it will edit; relevant fixtures and failing test output; applicable decisions. It does not need the full transcript or all source captures unless explicitly listed. On handoff, return changed files, exact checks/results, unresolved issues, and contract changes. Reopen foundational decisions only with a documented counterexample.

Use deterministic tools to count/hash/validate rather than asking models to inspect everything. Give high-cost reviews the dependency graph, changed contracts, traceability matrix, and targeted evidence first. Expand context only where a concrete discrepancy requires it. Model recommendations do not authorize spawning agents or switching this conversation's model automatically.

## 8. Ordered implementation units and verification gates

Test labels below are deliberately separate:

- **A — Automated logic tests:** unit, property, and metamorphic tests of behavior.
- **S — Schema/format validation:** supplied and internal contracts, dates, hashes, CSV/ICS syntax.
- **I — Integration tests:** real component boundaries, local HTTP simulations, storage and end-to-end command.
- **R — Requirement acceptance:** assertions tied to the R/Interview matrix, including live execution where specified.
- **M — Manual inspection:** source identity/meaning, draft clarity, and authorized decision evidence where code cannot establish them.

Every unit stops on its failed completion criteria. A later unit cannot compensate by weakening an earlier invariant. A gate can pass by correctly demonstrating a blocked/partial scenario; this does not change that scenario's run outcome. Human review requests may remain pending because approval is not the delivery endpoint.

**Revised required critical path:** U01–U02/G1 (contracts and interpretation/scope boundary) → U03 (single-command host feasibility and minimal skill loader) → U04–U07/G2 (evidence and source capture) → U08–U10/G3 (bounded interpretation, authority and reconciliation) → U11–U13 (impacts, proposals and review binding) → U14–U16 → U17/G4 (three artifacts and independent validation) → U18/G5 (truthful history, interruption rejection and fresh recovery) → U19 (complete skill documentation/evaluation) → U20 (every requirement closed or explicitly undemonstrated). Each renderer can be verified independently once Stage 06 is frozen; no parallel agent work is implied.

**Optional, outside the completion gates:** a separate model API backend, unattended scheduling/service hosting, automatic promotion rollback/resume, exhaustive filesystem fault campaigns, automatic orphan repair and incremental caching. Add one only when a documented failure or changed operating requirement warrants it. These do not excuse required write-error handling, failure preservation or full rerun verification.

### U01 — Baseline requirements, decisions, and acceptance oracles

**Purpose:** turn all normative clauses and interview meanings into an auditable implementation contract before code.

**Inputs/minimum context:** both authoritative documents in full, supplied schema, README, this plan. **Dependencies:** none. **Outputs/components:** `docs/requirements-traceability.csv`, `references/decision-log.md`, `references/contracts.md`, initial acceptance case descriptions. Every requirement bullet receives a leaf ID, source locator, intended component, acceptance assertion, and evidence type; section-only coverage is insufficient.

**Checks:** A/I: not applicable yet. S: unique requirement/decision IDs and valid local references. R: each normative bullet and interview-specific meaning has an acceptance owner. M: inspect requirement conflicts, unknown IDs/headers, scope-date convention, and human boundaries.

**Failure cases:** omitted clauses, invented source fields, implied approval, conflicting source priority. **Completion:** no orphan requirement; unresolved design questions have explicit conservative behavior and affected gates.

**Model:** `gpt-6.1-sol`, **medium**. This review fixes the architecture; requirement mapping and acceptance cases are now bounded. **Escalate:** Sol high for a contradiction or uncovered acceptance case; Astra high if the contradiction cannot be resolved without weakening an invariant.

### U02 — Typed records, identifiers, states, and snapshot contracts

**Purpose:** establish the foundation all stages share. **Dependencies:** U01.

**Inputs/minimum context:** R1/R3/R6/R10, supplied schema, §2.3/§3/§4.3/§5.3 of this plan, requirement leaf IDs and approved decisions. **Outputs/components:** `contracts.py`, `ids.py`, `snapshots.py`, internal schemas and contract fixtures. Implement typed extensions, byte hashing, upstream graph rules, exact enums, stage sequence, stable versus run-specific identity, interpretation packet binding and primary scope-basis records. Specify the incomplete-replacement marker contract here; actual recovery is U18.

**Checks:** A: stable IDs across row/date reordering; identity collisions; state reducer truth table. S: all seven minimal valid snapshots plus invalid enum/date/predecessor cases, with format checking enabled. I: write/re-read a two-stage chain and mutate predecessor bytes. R: R1/R3 traceability assertions. M: inspect useful downstream values rather than empty summaries.

**Failure cases:** dangling consumed IDs, current-stage records claimed as upstream, cross-run predecessor, fabricated content hashes, timezone conflation. **Completion:** all contract cases pass and every deliberate violation is detected. Supplied schema hash unchanged.

**Model:** `gpt-6.1-sol`, **high**; cross-stage integrity deserves more reasoning than serialization alone. **Escalate:** Astra high for unresolved graph/identity contradictions.

**Gate G1:** freeze these interfaces before adapters, business rules, or renderers are implemented. Include the skill/Python exchange, zero-forward-reference scope basis, original attempt-time preservation, and incomplete-package rejection. A cheaper downstream unit must not invent these contracts.

### U03 — Runtime skeleton and deterministic test harness

**Purpose:** make the approved contracts executable in a reproducible environment. **Dependencies:** U02.

**Inputs/minimum context:** G1 contracts, §2.1/§2.3, planned file tree, R11/R12, installed host capabilities. **Outputs/components:** `pyproject.toml`, dependency lock, `run.py` supervisor/config validation, `stage.py` interface, minimal actual skill loader, test configuration, fake clock/ID provider and isolated output roots. U19 completes the loader and documentation; no production workflow completion is claimed here.

**Checks:** A: config validation, no recursive launch, false-success/missing-final-files rejection. S: packet/config schemas and package imports. I: clean virtual environment plus installed host launches the minimal skill and completes one recorded synthetic interpretation exchange through a deterministic helper; no manual transfer. Test host unavailable/auth failure/interruption explicitly. R: one-command feasibility and retained packet/model metadata. M: inspect host permission/tool profile and credential-free sample config.

**Failure cases:** unsupported Python/host, missing dependencies/auth, secret values in config, fixtures selected by production command, treating host exit zero as package success. **Completion:** clean setup reproduces the bounded host exchange and failure checks; CLI rejects invalid setup before replacing current outputs. Stop downstream integration if host feasibility is not demonstrated; reconsider the API alternative explicitly rather than adding manual steps.

**Model:** `gpt-6.1-sol`, **medium**; host invocation and independent outcome checking exceed mechanical scaffolding. **Escalate:** Sol high for permission, recursion, or completion/version ambiguity.

### U04 — Evidence store and append-only attempt journal

**Purpose:** make every read attempt auditable before live adapters exist. **Dependencies:** U02/U03.

**Inputs/minimum context:** R2/R9/R10, attempt/capture/evidence contracts. **Outputs/components:** `evidence.py`, safe path handling, journal and retained-content writer, synthetic response fixtures.

**Checks:** A: attempts with bytes, zero bytes, no response, unused success, failed response, and permitted extracts; hashes match retained representations. S: required metadata/null behavior. I: simulated disk failure and interrupted capture preserve truthful diagnostics. R: no URL/hash-only evidence claim. M: inspect one capture and locator end to end.

**Failure cases:** path traversal, source content mistaken for diagnostics, redacted content retaining original hash, incomplete evidence presented as full. **Completion:** each attempted read has exactly one terminal attempt outcome; retained content is independently verifiable.

**Model:** `gpt-6.1-sol`, **medium**; storage correctness and provenance need judgment but scope is local. **Escalate:** Sol high for interruption/recovery interactions or unverifiable representation changes.

### U05 — Read adapters and source identity checks

**Purpose:** prove intended access routes work or fail honestly. **Dependencies:** U04.

**Inputs/minimum context:** ten-route manifest, R2/R7/R11, adapter interface, credential-reference policy. **Outputs/components:** `adapters/`, `source_manifest.py`, documented connection preflight, identity checks and route-specific diagnostics. Use the smallest callable integration that preserves evidence.

**Checks:** A: bounded retry accounting, redirects, timeouts, 403/404/429, wrong document and login/landing page detection. S: complete metadata for every result. I: local HTTP server plus read-only live access spike for all core routes. R: each core source is attempted; failures retained; no hidden local fallback. M: compare returned title/document ID/version to the requested source.

**Failure cases:** connector unavailable to CLI, silent first-tab export, authorization failure, unrelated amendment, unreadable format. **Completion:** source access report describes each supported adapter and each blocker; all success claims have captured content. A blocked source is an acceptable adapter test outcome, not a successful retrieval.

**Model:** `gpt-6.1-sol`, **medium**; heterogeneous access needs integration reasoning. **Escalate:** Sol high for browser/API discrepancies or ambiguous identity; human source owner for access authority, not a stronger model.

### U06 — Field dictionaries and register normalization

**Purpose:** support benign layout changes without guessing meanings. **Dependencies:** U05.

**Inputs/minimum context:** captured register headers/rows, interview 04:35–04:46, R7, normalization/identity contracts. **Outputs/components:** `normalize.py`, `field-dictionary.json`, normalized SYSTEMS/EVIDENCE/CALENDAR record contracts. Required semantic fields are established from actual sources; aliases need an explicit documented mapping.

**Checks:** A: shuffled rows/headers, extra columns, newer valid dates/versions, duplicated headers, renamed unknown fields, invalid values, conflicting IDs. S: raw and normalized fields retain valid types and locators. I: read adapter → capture → normalizer. R: meaningful source labels survive unchanged alongside normalized values. M: confirm mappings against source text and disclosed meanings.

**Failure cases:** fuzzy rename guesses, date string accepted as approval, row position as identity, “visible label” mapped to provenance. **Completion:** benign transformations preserve semantic records; every ambiguous required mapping yields a visible issue.

**Model:** `gpt-6.1-sol`, **medium**; semantic mappings outweigh mechanical parsing. **Escalate:** Sol high when sources use conflicting meanings; obtain owner clarification if meaning cannot be established.

### U07 — Stage 01 scope and Stage 02 capture slice

**Purpose:** produce the first two real snapshots through the command. **Dependencies:** U02–U06.

**Inputs/minimum context:** R0/R1/R2/R8, G1 scope/attempt contracts and §4.3, source manifest, eight-system scope rule. **Outputs/components:** scope/source helpers in `runner.py`; actual snapshots in isolated new test runs; declared-scope comparison and constrained discovery import. U08 extends capture in subsequent new runs, never by editing these frozen snapshots.

**Checks:** A: declared scope with failed live corroboration; discovered IDs; wrong count/ambiguous IDs; missing IDs and failed discovery; preserved assigned date. S: nonempty real scope, no forward consumed/evidence record IDs, exact Stage 01 hash. I: one command journals discovery before dispatch and imports the original attempt exactly once into Stage 02 with unchanged retrieval time/path/hash; interruption preserves the incomplete attempt. R: all ten fresh attempts on a package-producing run and supersession fields accounted for; a preflight abort explicitly fails package acceptance. M: inspect primary scope basis and current-vs-declared IDs.

**Failure cases:** untracked discovery read, invented IDs, Stage 01 linked to a future record, duplicated/re-timed attempt, mutation of hashed scope. **Completion:** both conforming scope paths pass and failed-discovery behavior is separately demonstrated as incomplete; evidence of that failure never counts as a valid two-stage package.

**Model:** `gpt-6.1-sol`, **medium**; it joins established components with a small number of scope edge cases. **Escalate:** Sol high for stage-order/bootstrap contradictions.

**Gate G2 / vertical slice A:** inspect source locator → bytes → evidence → source record → Stage 02 predecessor, with successful/unsuccessful reads and declared/discovered scope. Verify original timestamps, no forward record reference and honest failure when scope is unavailable.

### U08 — Linked report capture and bounded interpretation interface

**Purpose:** inspect the evidence behind register labels and constrain model-derived claims. **Dependencies:** U07.

**Inputs/minimum context:** interview 04:41–04:43, linked report records, R2/R10/R13, G1 evidence/interpretation contracts and U03 host exchange. **Outputs/components:** report adapters, `interpretation.py` packet validator, skill interpretation instructions and derived-analysis logging. Complete authorized linked-report reads before freezing Stage 02 in each new run; no separate model API client.

**Checks:** A: unsupported report format, unavailable link, hostile source instructions, invented citation, cross-run/wrong-hash packet, truncated/refused response and malformed output. S: claim fields and evidence pointers valid. I: invoking skill processes a captured report through the packet contract; accepted output drives the deterministic helper and is retained with the exact request. R: no status-only conclusion or untracked agent web retrieval. M: compare interpretation to the report, including contradictory owner/capture evidence; format validity is not semantic proof.

**Failure cases:** OCR text treated as original, agent response treated as primary evidence, arbitrary link crawl, evidence text controlling tools, changed upstream bytes during interpretation. **Completion:** accepted candidates match packet/run/evidence bindings, unsupported claims stay unresolved, and the run profile exposes no external mutation/send tools; U09 still evaluates authority and meaning.

**Model:** `gpt-6.1-sol`, **medium**; G1 freezes the provenance/exchange contract and U03 proves the host path. **Escalate:** Sol high for cross-run acceptance, unverifiable extract bindings or ambiguous report representation; Astra high for an unresolved provenance flaw. No model can substitute for unreadable content.

### U09 — Stage 03 authority and timing

**Purpose:** establish rule applicability before impact conclusions. **Dependencies:** U08 and G1/G2.

**Inputs/minimum context:** Stage 01/02, exact legal extracts and version metadata, R3/R5/R13, interview 03:14/03:22, authority policy and the accepted interpretation exchange. **Outputs/components:** skill-owned authority interpretation instructions, `authority.py` evidence/prerequisite checks, `authority-policy.md`, rule/timing records and blocker records in Stage 03. Python rejects invalid bindings and missing prerequisites; it does not infer legal truth merely from a well-formed agent response.

**Checks:** A: guidance versus binding basis, newer amendment outside review date, unrelated act, conflicting timing, missing authority, date-boundary ambiguity. S: rule versions, citations and Stage 03 predecessor. I: source failure propagates to an authority blocker. R: unsupported formal legal conclusions impossible. M: inspect each extracted legal predicate, exception, role and timing basis against captured paragraphs; unresolved interpretation is sent to Legal in the draft.

**Failure cases:** FAQ overriding law, conflating retrieved/current with applicable, hardcoded remembered Article 50 obligations. **Completion:** each candidate rule has explicit supported scope/timing or a blocker; no invented deadlines.

**Model:** `gpt-6.1-sol`, **high**; bounded legal-source reconciliation needs strong reasoning and evidence. **Escalate:** Astra high for genuinely conflicting authority/version chains; Legal for unresolved final interpretation.

### U10 — Stage 04 factual and policy reconciliation

**Purpose:** preserve every relevant record while identifying conflicts and gaps. **Dependencies:** U09.

**Inputs/minimum context:** normalized company records and report evidence, Stage 03 contract, R10/R13, interview label/role meanings. **Outputs/components:** `reconcile.py`, Stage 04 facts/controls/incidents/conflicts/gaps and retained calendar context.

**Checks:** A: missing owner, stale role, unsupported provenance, unapproved exception, mismatched IDs, contradictory owner/capture, absent system in one register. S: conflict records preserve both values, evidence, known owner and resolution need. I: reconcile multiple registers/reports by stable IDs. R: all eight scoped systems and all relevant rows accounted for. M: inspect conflict grouping and field-specific scope.

**Failure cases:** latest-row-wins, universal deployer assumption, closed incident inferred resolved, deduplication discarding contradictions. **Completion:** accounting ledger has no silently dropped records; each disagreement is supported or explicitly unresolved.

**Model:** `gpt-6.1-sol`, **high**; cross-source reconciliation is a principal correctness risk. **Escalate:** Astra high if overlapping identities or multi-record dependencies cannot be represented consistently.

**Gate G3:** authority and fact contracts pass adversarial cases before any impact engine is enabled. Freeze the four-state impact truth table, predicate/unknown propagation and source-label distinctions so U11 can implement established behavior. Semantic cases still need evidence inspection; passing a schema is insufficient.

### U11 — Stage 05 impact engine and coverage ledger

**Purpose:** derive scoped, evidence-backed draft dispositions. **Dependencies:** U10/G3.

**Inputs/minimum context:** Stage 03/04 records, impact decision table, R3/R4.1/R5/R10/R13. **Outputs/components:** `impacts.py`, Stage 05 and candidate system/rule coverage ledger.

**Checks:** A: all four states; missing fact never becomes no-impact; policy/legal bases distinct; one supported rule and one blocked rule on the same system; stable impact ID under row reorder. S: impact/coverage graph validity. I: rule+fact changes recompute affected dispositions. R: every in-scope system has an explicit disposition for each relevant candidate rule, with independently supportable findings retained. M: inspect one example of each state.

**Failure cases:** overbroad compliance statement, unsupported exclusion, guidance-only legal finding, lost unresolved scope. **Completion:** no unexplained coverage holes; each supported disposition has established predicates and citations.

**Model:** `gpt-6.1-sol`, **medium**; G3 has frozen the truth table, predicate meanings and coverage contract. **Escalate:** Sol high for a new predicate, exception interaction or incorrect scope propagation; Astra high for an unresolved cross-rule contradiction.

### U12 — Stage 06 action proposals and deduplication

**Purpose:** turn findings into reviewable proposals without changing operational commitments. **Dependencies:** U11.

**Inputs/minimum context:** impacts, existing CALENDAR records, R4/R6, interview 03:17–03:18/03:26/04:44–04:46. **Outputs/components:** `actions.py`, Stage 06 action/approval/escalation records and draft export model.

**Checks:** A: exact existing-action match, ambiguous duplicate, multiple impacts per action, undated proposal, conflicting dates, closed-but-unapproved status. S: IDs/roles/date types/approval enums. I: impact changes propagate to proposals and unresolved requirements. R: existing approved/source dates retained separately; proposal dates have explicit basis; undated actions remain visible. M: inspect owner/reviewer responsibilities and deduplication rationale.

**Failure cases:** inventing a due date from “urgent,” merging different rule bases, operational state promoted to approval. **Completion:** all actionable findings have proposal or explicit no-action reason; dates and approval requirements reconcile.

**Model:** `gpt-6.1-sol`, **medium**; implement explicit exact-match/proposal rules, preserve ambiguous matches, and leave approval application to U13. **Escalate:** Sol high if deduplication loses a rule basis, date provenance disagrees, or multi-role interpretation is required; Astra high only for an unresolved cross-stage conflict.

### U13 — Review requests and authentic feedback matching

**Purpose:** implement the human decision boundary and version checks. **Dependencies:** U12.

**Inputs/minimum context:** R6, interview 03:37–03:38, request/binding contracts, configured reviewer identity policy. **Outputs/components:** `reviews.py`, `review-protocol.md`, review requests in Stage 06, feedback records and matching rules. U17 supplies real artifact bindings; tests here use explicit binding fixtures.

**Checks:** A: wrong request, subject, source version, role, artifact hash, missing identity proof, superseded draft, conditional/rejected approval. S: all feedback/request fields and relations. I: fixture binding → feedback → new-run proposed outcome. R: unsent requests stay unsent; unmatched feedback unresolved. M: inspect configured identity/channel evidence and authority mapping.

**Failure cases:** trusting a typed role name, applying old approval to new source content, treating preparation as delivery. **Completion:** only matching authenticated decisions affect the intended subject; absence of feedback yields pending requests, not a blocker to drafting.

**Model:** `gpt-6.1-sol`, **high**; authorization and version binding are sensitive invariants. **Escalate:** Astra high for complex conditional approval scope; human operator for missing identity authorization.

### U14 — CSV register renderer

**Purpose:** emit a deterministic review table from the frozen export model. **Dependencies:** U12/U13.

**Inputs/minimum context:** R4.1, export-model schema, CSV column definitions and fixtures. **Outputs/components:** `renderers/csv_register.py`, `impact-register.csv` test outputs.

**Checks:** A: one row per impact/unresolved item, unknown blanks with reasons, semicolon evidence IDs, multi-action references, special characters. S: UTF-8, exact required headers, valid known dates, proper CSV quoting. I: parse output back and compare IDs/values to Stage 06. R: distinguish rule bases and preserve gaps. M: open a sample in a text viewer or safe spreadsheet preview.

**Failure cases:** duplicated impact rows, dropped Unicode, blank reason, accidental spreadsheet formula execution. **Completion:** round-trip semantic equality for all fixture rows with documented display escaping.

**Model:** `gpt-6-luna`, **low**; format and behavior are fully specified. **Escalate:** Sol medium if renderer requirements expose ambiguity in multi-action or escaping contracts.

### U15 — Markdown compliance brief renderer

**Purpose:** present scope, support, uncertainty and decisions clearly. **Dependencies:** U12/U13.

**Inputs/minimum context:** R4.2/R6, export-model schema, approved template and bounded fixtures. **Outputs/components:** `renderers/brief.py`, brief template and test outputs.

**Checks:** A: mandatory content present for complete/partial/blocked outcomes; IDs attached to claims; undated actions explained. S: Markdown links/IDs valid and no self-hash field. I: compare brief sections to Stage 06. R: explicitly scoped conclusions, source limitations, recipients and decisions requested. M: read complete and blocked examples for misleading certainty.

**Failure cases:** unsupported prose, hidden blockers, invented recipient names, claim of sent/approved package. **Completion:** all required sections and references reconcile with no new factual assertions from rendering.

**Model:** `gpt-6-luna`, **low**; template assembly is mechanical. **Escalate:** Sol medium when wording changes meaning or obscures a scoped limitation.

### U16 — iCalendar renderer and empty-calendar behavior

**Purpose:** encode only supportable dated proposals. **Dependencies:** U12/U13.

**Inputs/minimum context:** R4.3, action schema, date conventions, RFC serialization rules and fixtures. **Outputs/components:** `renderers/calendar.py`, `action-calendar.ics` test outputs.

**Checks:** A: stable UIDs, undated exclusion, empty calendar, tentative status, all-day dates, exclusive end, Unicode/escaping/folding. S: independent parser and targeted RFC assertions. I: parsed event values exactly match Stage 06 actions. R: required description fields and no production calendar mutation. M: preview one all-day event locally without importing it into a production calendar.

**Failure cases:** one-day timezone shift, inclusive DTEND, duplicated UID, loss of approval status. **Completion:** both empty and populated calendars pass syntax and semantic checks.

**Model:** `gpt-6-luna`, **low**; a maintained library and explicit cases contain complexity. **Escalate:** Sol medium for parser disagreement or timezone/serialization edge cases.

### U17 — Stage 07 independent package validation and review bindings

**Purpose:** verify exact final bytes and cross-file meaning. **Dependencies:** U14–U16.

**Inputs/minimum context:** R1/R4/R5/R6, Stage 06/07 contracts, actual renderer files and outcome table. **Outputs/components:** `validate.py`, Stage 07, detached request→artifact bindings and validation report. The validator re-reads disk; it does not trust renderer success objects.

**Checks:** A: alter action/date/evidence/run/status in one artifact, delete source bytes, corrupt predecessor, change final hash, omit brief decision request. S: all seven snapshots and three artifacts. I: complete, bounded-partial and authority-blocked end-to-end fixtures. R: partial can validate honestly; legal-authority blocker always remains publication-blocked. M: inspect one request against the exact final artifact bytes.

**Failure cases:** valid formats masking conflicting content, circular brief hash, unsupported “validated” status. **Completion:** every targeted corruption is detected and all exact bindings match. Every artifact record includes meaningful summary/evidence extensions as well as its required fields.

**Model:** `gpt-6.1-sol`, **high**; cross-artifact consistency is a system invariant. **Escalate:** Astra high for validator/renderer correlated mistakes or unresolved status semantics.

**Gate G4 / vertical slice B:** one representative system across all seven stages to three artifacts, then all eight fixture systems. Include at least one conflict, missing fact, undated action and unavailable-authority case before advancing. Use the public launcher → skill → deterministic helpers → independent validator path; a manually supplied interpretation does not demonstrate the one-command requirement. Check that a truncated/failed host cannot return package success.

### U18 — Run history, promotion, recalculation and recovery

**Purpose:** make repeat executions safe and auditable. **Dependencies:** U17/G4; apply the provisional staging isolation from U03 throughout earlier tests.

**Inputs/minimum context:** R8/R9, G1 byte/path/run/marker contracts, §5.3 recovery classification, stage dependency fingerprints. **Outputs/components:** `history.py`, `recovery.py`, verified copy/replacement with small markers and local lock, failure inventory and current-package inspector. Automatic rollback/resume and a detailed transaction journal are outside this unit.

**Checks:** A: earliest-change classification, new IDs, old missing/corrupt evidence inventory, unknown prior ID stops replacement. S: archived chains and interpretation packets resolve within archive root. I: two live-like runs; injected archive/write failure and one interrupted replacement; marker creation failure stops before overwrite; second writer rejected; missing/damaged current files with unchanged inputs. R: all available old/failed bytes retained; fresh command rerun repairs with new source attempts. M: inspect archive/current/failure relationships. Exhaustive disk-full/power-loss injection is optional; truthful handling of representative write failures is required.

**Failure cases:** overwriting unarchived outputs, accepting mixed-run files, fabricated history, success from cached flag, lost interpretation provenance, recovery inventing approval. **Completion:** each required fault preserves available evidence and yields an intact previous archive or explicit incomplete result; a fresh rerun repairs and validates with a new run ID. No accepted package spans runs.

**Model:** `gpt-6.1-sol`, **high**; crash behavior and provenance require careful reasoning. **Escalate:** Astra high for failure interleavings or inability to reproduce integrity loss.

**Gate G5 / vertical slice C:** run → changed source → new run → preserved history → injected corruption → recorded failure → fresh recovery run. Stop if any occurrence disappears or any historical link resolves to current data.

### U19 — Skill package, operating documentation and evaluations

**Purpose:** make the tested workflow invokable and reproducible by another operator. **Dependencies:** U18/G5.

**Inputs/minimum context:** R11/R12/R13, public command/status contract, tested host setup, failure/review/interpretation protocols, Agent Skills specification. **Outputs/components:** completed `SKILL.md` and references built on U03's minimal loader, `docs/operating-guide.md`, example config, canonical eval cases and expected results. Document source and host auth separately, permitted tools, interpretation provenance, preflight failure and attended fresh recovery. Apply skill-authoring instructions when that future work begins.

**Checks:** A: canonical evaluations on the selected invoking model; compare another model only when changing that selection. S: skill metadata/name/paths and references; immutable supplied schema. I: fresh clone/venv plus documented host setup executes the public command with no manual interpretation transfer or separate project API key. R: required tree, setup, outputs and read-only boundaries explained. M: operator walkthrough of blocked run and fresh recovery. Scan the authored skill and inspect findings.

**Failure cases:** hidden local paths, undocumented credentials, a fixture shown as live output, oversized skill context, ambiguous exit codes. **Completion:** another operator can reproduce the fixture evaluation and understand live prerequisites; all references resolve and scan findings have dispositions.

**Model:** `gpt-6-luna`, **medium**; documentation is contract-driven but must preserve behavioral boundaries. **Escalate:** Sol high for invocation mismatches, model evaluation regressions or newly exposed workflow ambiguity.

### U20 — Whole-system verification and requirement closure

**Purpose:** demonstrate every requirement and identify anything still undemonstrated. **Dependencies:** U01–U19; all gates passed.

**Inputs/minimum context:** complete requirement matrix and invariants, original authoritative inputs, schema, code/interface index, exact test results, current package/history and targeted supporting captures. This is the second justified full-project review; load raw evidence by cited ID rather than all captures at once.

**Outputs/components:** `docs/verification/final-report.md`, completed leaf-level traceability matrix, live execution record, exception register, and final seven-stage draft package produced by the documented command. The verification report states exact commit/config/dependency/model fingerprints and actual commands/results.

**Checks:** A: all unit/property/metamorphic scenarios; S: schema/format/hash/graph validation; I: live reads and clean-environment end-to-end run plus recovery sequence; R: every normative leaf has a passed test or explicit inspection record; M: source identity/meaning, scoped conclusions, all eight systems, human decision boundary, exact review bindings. Follow §10's final validation protocol.

**Failure cases:** all tests green but live sources inaccessible, untested interview semantics, a requirement marked passed by implementation presence alone, ambiguous source applicability, stale approvals. **Completion:** every leaf is `demonstrated`, `not-demonstrated`, `blocked`, or `not-applicable-with-basis`; none is blank. No unverified requirement is represented as delivered. A valid blocked run can demonstrate fail-closed behavior while leaving live successful-review acceptance blocked.

**Model:** `gpt-6-astra`, **high** for the final independent review; its cost is reserved for architecture-wide omissions and correlated failures. Mechanical test execution/report assembly uses code, not repeated Astra calls. **Escalate:** Astra xhigh only for a concrete unresolved cross-stage counterexample; missing access/facts/authorization goes to the named human owner.

## 9. Acceptance traceability and adversarial scenario catalogue

This section is the initial section-level map. U01 must expand every requirement bullet into leaf-level rows. Planned coverage is not evidence that a requirement has passed.

| Source requirement | Implementation units | Required acceptance evidence |
|---|---|---|
| R0 objective, date, read-only and output tree | U01/U03/U07/U09/U17/U19/U20 | Fixed assigned date; eight-system scope; fresh reads; required paths; draft/human limits; attempted source writes/messages/calendar writes prohibited |
| R1 seven snapshots and record relationships | U02/U07/U09–U13/U17 | Seven schemas, meaningful typed values, same run, immediate predecessor hashes, resolved consumed/produced IDs, tamper failures |
| R2 every source attempt and retained evidence | U04–U08/U20 | All ten attempts plus retries/linked reports; all retrieval states; actual bytes/extracts; null-without-content; identity/version/date checks; no silent fallback |
| R3 states, uncertainty and time separation | U02/U06/U09–U13/U17 | All enum cases, empty permitted collections, gaps with owner/reason/need, distinct dates, unchanged as-of |
| R4.1 CSV | U11/U12/U14/U17 | UTF-8/header/columns/row cardinality/IDs/dates; unknown reasons; distinguish rule bases |
| R4.2 brief | U15/U17/U20 | All required content and ID citations; scope/uncertainty/proposals/decisions visible |
| R4.3 ICS | U16/U17 | Required properties/descriptions, stable UID, tentative, DATE/exclusive end, no undated event, empty calendar |
| R5 publication validation and blockers | U09/U11/U17/U20 | Exact paths/hashes and Stage 06 agreement; blocked authority chain; partial/defer decision; draft-only status |
| R6 decisions/reviews/feedback | U01/U12/U13/U17 | Full decision fields; full requests; exact detached bindings; authenticated matching feedback; mismatches unresolved; no simulated delivery |
| R7 input compatibility | U06/U09/U18 | Reorder/extra-column metamorphic tests; legitimate versions accepted; ambiguity/identity/meaning changes reported |
| R8 history/retry relationships | U07/U18 | Archived actual bytes; new run/snapshot IDs; supersedes/reason; in-run chains; honest missing/corrupt inventory |
| R9 recomputation/repair | U17/U18/U20 | Inspect actual unchanged package; dependency changes; missing/damaged/stale output faults; preserved failed occurrence; fresh end-to-end repair run |
| R10 source/evidence reconciliation | U02/U08–U13/U17 | Attempt→capture→evidence→rule→impact→action→approval/request→artifact graph; retained conflicts; distinct bases |
| R11 runtime/reproduction | U03/U05/U08/U17/U19/U20 | Clean environment setup; one live launcher/skill command from disclosed inputs; no manual interpretation transfer; independent completion check |
| R12 required skill | U19/U20 | Compliant skill name/tree, invocation and output instructions, validation and evaluation evidence |
| R13 core behavioral constraints | U02/U09–U13/U17/U20 | Negative cases for fabricated certainty, approval/status confusion, legal fail-open, and source mutation |
| Interview 03:08/03:21 scope and recipients | U07/U10/U20 | Eight systems reconciled across registers; Legal/Operations audience |
| Interview 03:11–03:19 authority and escalation | U09/U12/U13 | Role-specific review routing; legal/policy conflicts preserved; factual correction requests to owners |
| Interview 03:26 duplication avoidance | U12 | Existing actions matched without collapsing different obligations or contradictory dates |
| Interview 03:37–03:38 feedback authenticity | U13/U17/U18 | Identity, role, request, subject, version and conditions all checked |
| Interview 04:35–04:40 system facts | U06/U10/U11 | Use/exposed groups/notices/review paths/roles retained; visible label not provenance; no universal deployer default |
| Interview 04:41–04:43 evidence and reports | U08/U10 | Complete ≠ compliance; partial/conflicting meanings; page captures/export tests/owner statements inspected; contradictions need authorized resolution |
| Interview 04:44–04:46 calendar meanings | U12/U13/U16 | Fixed existing dates, required review path, operational labels distinct from approval/completion |

Required scenario families, each with explicit expected records and artifact assertions:

| Case | Scenario | Objective expected behavior |
|---|---|---|
| T01 | Fully supported eight-system synthetic dataset | Seven valid snapshots, covered system/rule pairs, consistent draft artifacts; pending review does not become approved |
| T02 | Required authority unavailable, wrong act, or login page | Retain attempt/content if present; authority blocker; dependent conclusions withheld; Stage 07 blocked |
| T03 | Missing company evidence for one system | Bounded partial or explicit deferral with rationale; no inferred compliance; unaffected supported analysis survives |
| T04 | Owner statement conflicts with page capture | Both values/evidence retained, conflict owner and resolution need visible through brief |
| T05 | Evidence says complete; action says closed | Neither field establishes compliance, approval or completed action |
| T06 | Visible disclosure but no export provenance evidence | Separate findings for separate predicates; missing provenance unresolved |
| T07 | Rows/headers shuffled, unrelated column added | Stable business IDs and unchanged semantic findings |
| T08 | Required header renamed or meaning changed | Explicit mapping issue, no guessed synonym |
| T09 | New source revision after review date | Captured as current; historical suitability assessed separately; review date unchanged |
| T10 | No supportable dated actions | Valid empty ICS; undated proposals and reasons remain in CSV/brief |
| T11 | Duplicate existing action or changed proposed date | Stable identity if same action, ambiguity visible otherwise; no alteration of approved source deadline |
| T12 | Wrong/stale/unauthenticated reviewer feedback | Preserved unresolved feedback; no approval transition |
| T13 | Verified conditional feedback for exact draft | Conditions retained, matching subject only affected in new run, changed draft not automatically approved |
| T14 | Change one CSV date, ICS UID, or brief claim | Independent Stage 07 mismatch; no validated result |
| T15 | Remove source capture or damage snapshot | Detect even with unchanged inputs; preserve occurrence, repair via new fresh run |
| T16 | Two successive runs and recovery retry | Exact available history, explicit supersession, distinct run/snapshot IDs, no cross-run predecessor |
| T17 | Archive/write failure, interrupted replacement, marker failure or second writer | Current package not accepted while incomplete; old/failed bytes preserved; new fresh run repairs; exhaustive power-loss/disk-full campaigns optional |
| T18 | Source contains instructions to send/update/exfiltrate | Treated as source data; no privileged tool invocation or credential leakage |
| T19 | SYSTEMS unavailable and no established scope IDs | Preserved discovery attempt and honest preflight incomplete result; no invented IDs, forward Stage 02 dependency or claim of seven-stage package acceptance |
| T20 | Guidance contradicts binding timing or exception request lacks approval | Distinct bases and Legal review request; no silent override or manufactured exception |
| T21 | Skill host unavailable, truncated or exits successfully without valid outputs | Supervisor returns explicit incomplete/failure; old package or host text cannot satisfy new-run success |
| T22 | Wrong-run interpretation response, changed packet/evidence hash or missing response provenance | Reject response and preserve diagnostics; no advancement from an invalid exchange |
| T23 | Declared scope with live ID mismatch, or successful first-run discovery | Scope stays frozen; discrepancy visible; discovery attempt imported once with original time/path/hash and no forward record IDs |

Synthetic fixtures are labelled test-only and have predetermined expected states. They demonstrate behavior, not the actual legal applicability or current company facts. Live results must identify actual retrieval times and remain blocked when required evidence cannot be verified.

## 10. Final whole-system validation phase

U20 ends implementation with the following ordered checks. Each check records exact inputs, command/inspection, expected result, observed result, evidence location, and verifier identity or tool version.

1. **Freeze the review basis.** Rehash the original requirements, interview, schema, code, config, lockfile and interpretation templates. Explain changes from this planning baseline. Confirm the public schema is byte-for-byte unchanged and interview export unedited.
2. **Execute automated tests.** Run logic, property and metamorphic tests; capture failures as well as results after repair. Exercise T01–T23 at the required scope above; optional exhaustive fault campaigns do not block completion. Assertions must test externally meaningful outcomes, not merely mirror implementation functions.
3. **Run schema/format validation separately.** Validate seven snapshots with format checking, typed extensions, exact hash syntax, source paths/content, graph edges, record/run bindings, CSV headers/encoding/cardinality, and ICS syntax/date behavior. A schema pass is never a semantic pass.
4. **Run integration tests.** Exercise adapters against simulated failures, then the complete launcher/skill command with live required sources. Check that all ten core sources have new attempts, linked evidence is captured, and interpretation input/output provenance resolves. Verify that original bootstrap times are retained if that path is used. Validate the exact current on-disk package independently of the agent's final message. Network/host unavailability is recorded as blocked or failed acceptance as appropriate, not skipped success.
5. **Exercise change and recovery end to end.** Run a second controlled input version, inspect preserved history, corrupt a current artifact, detect it despite unchanged source values, preserve the failed occurrence, and rerun the documented command with new IDs and fresh source attempts. Verify the repaired package and archive-relative links.
6. **Inspect source meaning and the human boundary.** Manually compare representative captures to extracted facts and every material authority/timing predicate to its supporting paragraphs. Inspect all eight system dispositions for scope. Check that final interpretations/exceptions remain Legal decisions and dates/activation/closure remain Operations decisions. Unresolved judgments generate requests; they are not declared resolved by the verifier.
7. **Verify review binding.** Select each Stage 06 request, locate its Stage 07 path/hash binding, rehash the exact draft, and check the requested question/subject/source versions. Confirm that the brief points to the detached binding and makes no delivery or approval claim without evidence.
8. **Close requirement traceability leaf by leaf.** For every normative requirement bullet and interview rule, record implementing components plus passing test or explicit inspection evidence. Use statuses `demonstrated`, `not-demonstrated`, `blocked`, or `not-applicable-with-basis`. Do not infer coverage from a test name, a green aggregate suite, or file presence.
9. **Issue the final verification report.** List every undemonstrated requirement, reason, affected outputs, required next action and owner. Separate software correctness from the outcome of the actual source-dependent run. A correctly blocked package demonstrates safe failure but does not demonstrate successful authority retrieval or a fully supported review.

At planning time **all implementation acceptance requirements are not yet demonstrated**. The supplied documents and schema have been inspected; no source-dependent review package, implementation tests, live source compatibility, authentic reviewer channel, or recovery behavior has been demonstrated by this task. Final implementation completion requires all applicable engineering acceptance checks to pass and every remaining source/authority limitation to be explicitly recorded. Legal and Operations approval is a downstream human activity, not an implementation completion claim.
