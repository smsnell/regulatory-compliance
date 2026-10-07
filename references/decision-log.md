# U01 design decision log

These decisions preserve the architecture reviewed in the
[plan](../TECHNICAL-DESIGN-AND-IMPLEMENTATION-PLAN.md); they are provisional
engineering choices, not Legal/Operations approvals. U02/G1 has not passed.
No frozen contract change is proposed. Runtime snapshot decisions must carry
the same required fields and reference their relevant durable basis.

Documentary evidence aliases (not runtime Stage 02 evidence IDs):

- B-REQ: [requirements](../REQUIREMENTS.md), SHA-256 `eed1f9d24fcdc9e86b95bd6235eb6e82ea62d915d01f28d6d409329df9cde2c3`.
- B-INT: [original interview](../interviews/interview-B-3.md), SHA-256 `c3c0167379d0beaeef9ddd88826c6b585017e66620aee43e2ca5a26f9480c7fd`.
- B-SCHEMA: [public schema](../snapshot.schema.json), SHA-256 `8de9874ded18fa97294e83012796e4c386aa60ccfd30f8eca89cabdf2a267ac3`.
- B-PLAN: [plan](../TECHNICAL-DESIGN-AND-IMPLEMENTATION-PLAN.md), SHA-256 `454480a0414f03816d1ebc6bb21a79f907a2d40ea8f176dc6a3c5762fe2e2963`.
- B-README: [starter README](../README.md), SHA-256 `1d72d3849dae49bdbbaeaebb1cc20c19f5a14e592094a0d8e4a506be425488b9`.

See [contracts and open questions](contracts.md), [matrix](../docs/requirements-traceability.csv)
and [acceptance cases](../docs/acceptance-cases.md).

## D001 — Authority and human decisions

- id: D001
- status: provisional engineering baseline
- summary: Authority and human decisions
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Source summaries or labels could appear to grant final authority.
- options_considered: Automatic sign-off; role-specific pending draft.
- source_basis: R0/R6/R10/R13 and interview 03:11–03:19.
- chosen_behavior: Keep verified binding, policy, guidance, facts and operational bases separate; route final interpretation/exception/conflict to Legal, dates/activation/closure to Operations and facts to owners.
- rationale: Preserves assigned human authority and avoids unsupported certainty.
- tradeoffs: Some packages remain blocked or pending.
- downstream_effect: U09/U10/U12/U13/U17; T20/T29.

## D002 — Attended local deployment

- id: D002
- status: provisional engineering baseline
- summary: Attended local deployment
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Scale and ownership must justify infrastructure.
- options_considered: Hosted service/database/queue; local attended Python and file evidence store.
- source_basis: Plan §2.1–§2.2; R11/R12.
- chosen_behavior: Use attended local supervisor, deterministic helpers and invoking skill, with isolated run candidates.
- rationale: Eight systems and ten sources fit inspectable local files.
- tradeoffs: Host filesystem access control and backup remain dependencies; unattended/shared use requires reconsideration.
- downstream_effect: U03/U18/U19; T21/T17.

## D003 — Skill-owned interpretation

- id: D003
- status: provisional engineering baseline
- summary: Skill-owned interpretation
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: One-command processing must preserve bounded model provenance.
- options_considered: Separate model API client; invoking skill with Python-validated packet exchange.
- source_basis: Plan §2.3–§2.4; R1/R6/R10/R11/R12.
- chosen_behavior: Adopt invoking skill interpretation, Python supervisor/stage helpers and independent final validator; no recursive run.py or manual interpretation transfer.
- rationale: Avoids separate credentials and duplicate inference while retaining provenance.
- tradeoffs: Host authentication/context/version dependencies; failed U03 feasibility stops integration and requires explicit alternative review.
- downstream_effect: U02/U03/U08/U17; T21/T22; G1/G4.

## D004 — Read-only access and credentials

- id: D004
- status: provisional engineering baseline
- summary: Read-only access and credentials
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Available credentials or source instructions could permit prohibited actions.
- options_considered: Broad connector access; allowlisted read adapters and restricted run profile.
- source_basis: R0/R2/R13; README; plan §2.2.
- chosen_behavior: Expose only permitted reads and local artifact writes; record credential principals/scopes/references, never values; hostile sources are data.
- rationale: A prompt is not a security boundary; enforce allowed operations and independently inspect results.
- tradeoffs: Some connectors/browser routes may be unusable; retain access blocker.
- downstream_effect: U03/U05/U08/U19; T18/T21/T25.

## D005 — Scope input discovery

- id: D005
- status: provisional engineering baseline
- summary: Scope input discovery
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Real IDs are unknown and public scope is nonempty.
- options_considered: Placeholders; retroactive Stage 01; silent previous capture; authorized declared IDs or constrained discovery.
- source_basis: R1/R2; interview 03:21; public schema scope/sequence branches; plan §4.3.
- chosen_behavior: Prefer actual authorized scope inputs. If absent, journal SYSTEMS discovery before dispatch and produce direct Stage 01 basis; import same attempt once in Stage 02. Failure is incomplete preflight with retained bytes, not conforming package.
- rationale: Meets real identity and zero-forward-dependency constraints without mandatory manual copying.
- tradeoffs: Cannot promise seven conforming snapshots when no actual identity exists; conditional Q07 clarification.
- downstream_effect: U02/U07; T19/T23; G1/G2.

## D006 — Date encoding

- id: D006
- status: provisional engineering baseline
- summary: Date encoding
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Public scope requires date-time while assignment provides only date.
- options_considered: Change schema; assert legal midnight cutover; document precision-preserving encoding.
- source_basis: R0/R3/R7; public schema as_of; plan §3.3.
- chosen_behavior: Use 2026-08-26T00:00:00Z with assigned_review_date 2026-08-26 and as_of_precision date; distinct actual retrieval/revision/effective/observation/due/response times.
- rationale: Schema conformance without inventing intraday legal facts.
- tradeoffs: Unknown timezone/intraday applicability remains unresolved.
- downstream_effect: U02/U07/U09/U16; T09/T28; G1/G3.

## D007 — Exact provenance and source attempts

- id: D007
- status: provisional engineering baseline
- summary: Exact provenance and source attempts
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: A link/hash/status alone could be mistaken for proof.
- options_considered: Metadata only; retained bytes/extracts with exact locators and separate attempt/capture/evidence.
- source_basis: R2/R10; interview 03:09/03:11/04:42–04:43; plan §3.2.
- chosen_behavior: Attempt ten sources fresh each run plus authorized reports/retries; retain all outcomes and actual permitted representations; content/hash/path null only without content; never silent fixture fallback.
- rationale: Allows independent verification of each claim and unsuccessful read.
- tradeoffs: Storage and permitted extraction limits; unsupported reports unresolved.
- downstream_effect: U04–U08; T25/T02/T04; G2.

## D008 — Stable identity and immutable graph

- id: D008
- status: provisional engineering baseline
- summary: Stable identity and immutable graph
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Reordering/date changes or collisions could sever cross-file history.
- options_considered: Row/text/date-derived identity; versioned business keys with run-specific records.
- source_basis: R1/R4/R7/R8/R10; plan §3.1–§3.2.
- chosen_behavior: Preserve source IDs; stable impact/action key excludes date/wording/order; changed rule meaning gets new version; immutable exact-byte same-run immediate predecessors and upstream consumed IDs.
- rationale: Maintains identity without conflating changed obligations or runs.
- tradeoffs: Identity ambiguity is exposed rather than fuzzy-joined; U02 still defines executable types.
- downstream_effect: U02/U11/U12/U17/U18; T07/T11/T24/T16; G1.

## D009 — Evidence conflict and status semantics

- id: D009
- status: provisional engineering baseline
- summary: Evidence conflict and status semantics
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Latest row, complete or closed labels could erase uncertainty.
- options_considered: Latest-row-wins/compliance defaults; preserve both values and explicit gaps.
- source_basis: R3/R10/R13; interview 04:35–04:46; plan §3.4.
- chosen_behavior: Keep contradicting evidence distinct with source basis/reason/known owner/resolution need. Verify each system role; visible notice is not provenance; status is neither approval nor completion.
- rationale: No formal conclusion without rule and factual predicates.
- tradeoffs: Additional owner/Legal review and unresolved impacts.
- downstream_effect: U06/U10/U11/U13; T03/T04/T05/T06/T29; G3.

## D010 — Partial versus blocked draft

- id: D010
- status: provisional engineering baseline
- summary: Partial versus blocked draft
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Missing inputs could lead to fabricated completeness or unnecessary loss of supported work.
- options_considered: Always complete; always defer; explicit bounded partial with legal fail-closed.
- source_basis: R3/R5/R13; plan §3.5.
- chosen_behavior: Use failed > blocked > partial > complete. Required authority failure blocks dependent conclusions and publication; company gaps permit consistent bounded partial only when meaningful unaffected work remains, otherwise defer.
- rationale: Preserves supported analysis without weakening authority prerequisites.
- tradeoffs: Partial draft needs explicit limitation/omission reconciliation; pending human review can still be complete draft.
- downstream_effect: U09/U11/U17; T02/T03/T24; G3/G4.

## D011 — Actions and shared export model

- id: D011
- status: provisional engineering baseline
- summary: Actions and shared export model
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Duplicate proposals or independent rendering could disagree or alter dates.
- options_considered: Per-renderer inference; frozen Stage 06 export model and exact action matching.
- source_basis: R4/R6; interview 03:17/03:26/04:44–04:46; plan §5.1.
- chosen_behavior: Freeze shared values; retain existing dates separately from proposed dates; exact matching preserves basis; ambiguous matches remain unresolved. CSV one row per impact; undated actions visible only in CSV/brief; dated tentative all-day ICS with stable UID/exclusive end.
- rationale: Deterministic rendering and no operational commitment changes.
- tradeoffs: Multi-action detail stays in Stage 06/brief; unsupported dates produce empty valid calendar.
- downstream_effect: U12/U14–U17; T11/T26/T27/T28/T10; G4.

## D012 — Exact review binding and authentication

- id: D012
- status: provisional engineering baseline
- summary: Exact review binding and authentication
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Prepared requests or self-asserted roles could manufacture delivery/approval.
- options_considered: Brief self-hash; trust role text; detached exact hashes and trusted feedback.
- source_basis: R6; interview 03:37; plan §5.2.
- chosen_behavior: Stage 06 requests remain not-sent; Stage 07 binds final paths/hashes; brief points outward. Match trusted identity, role, request, subject, run/draft/source versions and conditions before any new-run effect.
- rationale: Avoids self-hash cycle, stale approvals and unverified authority.
- tradeoffs: Unknown roster/channel leaves approval pending; feedback preserved unresolved.
- downstream_effect: U13/U17/U18; T12/T13/T27; G4.

## D013 — History, replacement and recovery

- id: D013
- status: provisional engineering baseline
- summary: History, replacement and recovery
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Interrupted multi-file replacement could destroy history or accept mixed runs.
- options_considered: Automatic transaction replay/rollback; verified archive/candidate, small markers and fresh rerun.
- source_basis: R8/R9; plan §2.4/§5.3.
- chosen_behavior: Archive available exact bytes before overwrite, resolve archive paths locally, use writer lock and incomplete/completion markers; incomplete always rejects package. Preserve failed occurrence; fresh new run repairs. Unknown old ID/archive or marker failure stops overwrite.
- rationale: Required preservation/detection without unnecessary transaction engine; never claim atomic multi-file replacement.
- tradeoffs: Interrupted fixed paths require attended rerun; automatic orphan repair/rollback and exhaustive fault campaigns deferred.
- downstream_effect: U02/U18; T15/T16/T17; G1/G5.

## D014 — Full recalculation and independent validation

- id: D014
- status: provisional engineering baseline
- summary: Full recalculation and independent validation
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Unchanged inputs or prior success could hide damaged current files.
- options_considered: Incremental reuse/cache; full fresh rerun with earliest-change audit.
- source_basis: R9/R11; plan §5.4.
- chosen_behavior: Record earliest changed basis; fully rerun seven stages after fresh required attempts, inspect all actual bytes/graphs/artifacts, retain failures and rerun documented command after repair.
- rationale: Small dataset makes conservative complete recomputation proportionate.
- tradeoffs: More reads and computation; content-identical retrieval metadata alone not substantive change; optimization deferred.
- downstream_effect: U17/U18/U20; T15/T30; G4/G5.

## D015 — Model effort and escalation

- id: D015
- status: provisional engineering baseline
- summary: Model effort and escalation
- evidence_ids: B-REQ; B-INT; B-SCHEMA; B-PLAN; B-README
- concern: Bounded units should avoid waste without weakening gates.
- options_considered: Uniform high effort; contract-based starting effort with specific escalation.
- source_basis: Plan §2.4/§7/U01 task card.
- chosen_behavior: Retain plan §7 allocation: U01 Sol medium; contradictions/uncovered acceptance → Sol high, unresolved invariant contradiction → Astra high. Do not switch model/spawn agents automatically.
- rationale: Architecture baseline bounds leaf mapping; cost includes retries/review.
- tradeoffs: A stronger model cannot supply missing access, facts or authorization.
- downstream_effect: U01 and later unit-specific gates; T32. Explicit escalation record at each handoff.

