# Draft export model (U12)

Stage 06 `state.export_model` is an explicit JSON object with
`schema_version: rci-draft-export/1`. Renderers consume this model without
promoting operational assertions to approvals. All arrays retain full contract
records unless described below.

- `run_id`, `assigned_review_date`, `status`, `draft: true`, `recipients`
  (Stage 01 audiences), `systems_in_scope`, `created_at` (Stage 05 UTC timestamp).
- `draft_version`: SHA-256 of the canonical substantive draft before request
  identifiers and approval/request links are added. It binds source versions,
  evidence, coverage, findings, proposals, dates and limitations.
  Subsequent authenticated approval statuses do not change that substantive
  draft fingerprint; their exact records and feedback remain in the snapshot.
- `impacts`: Stage 05 supported-impact, supported-no-impact, conflicting and
  unresolved impact records; `rules`: Stage 03 rules and Stage 04 controls;
  `facts`: Stage 04 fact records. Resolve `rule_id` and `fact_ids` through these
  lists. `basis_type` and source versions remain on their originating records.
- `unresolved_coverage`: plain export objects for coverage entries without an
  impact record. Each has stable `impact_id`, `identity_key` with kind
  `coverage-review`, `system_id`, nullable real `rule_id`/`rule_basis`, original
  `basis_type`, `state`, nullable `scope`, `summary`, `evidence_ids`,
  `source_basis`, `source_versions`, `reason`, `owner`, `resolution_need`,
  `blocker_ids`, and `semantic_basis`. These objects have no graph record ID,
  record type, invented rule, action, date or fact references. Identity derives
  from the captured semantic candidate basis or real rule version and exact
  scope; candidate position and run UUIDs never supply identity. This list is
  included in the substantive draft fingerprint.
  Multiple withheld assessments of the same system, semantic basis and scope
  share one display row with all evidence/source/blocker links retained. Their
  separate original occurrences remain in `coverage`.
- `actions`, `approval_requirements`, `escalations`, `review_requests`,
  `decisions`: complete records with graph IDs and review responsibilities.
- `limitations`: complete upstream blocker, diagnostic, gap, conflict records,
  Stage 05 unresolved/conflicting impacts and Stage 06 escalations. These are
  objects, never inferred claims that a limitation has been resolved.
- `evidence_index`: Stage 02 evidence records, including retained path, hash,
  capture ID, locator and quotation. `source_quality`: Stage 02 source records.
- Optional `source_resolution`: read-only projection of Stage 04
  `u10_reconciliation.value.capture_resolution`, present only when that ledger
  exists. It retains `original_upstream_status`, `effective_upstream_status`,
  exact `resolved_diagnostic_ids` and `unresolved_diagnostic_ids`,
  `report_source_ids`, and `legal_assessments` (source, original diagnostic,
  rule and evidence IDs). `report_resolutions` adds full original report
  accounting entries with `gap_id: null` and an explicit `resolution`, retaining
  source row, system, reference, attempts, captures, evidence, fact candidates,
  declaration candidates, scopes and resolution reason. This object is included
  in the substantive draft fingerprint and displayed under Source inspection
  resolution in the brief. Original diagnostics remain in `limitations`; source
  quality and historical snapshot statuses are preserved. A scoped resolution
  can coexist with a partial effective status and remaining diagnostics.
  Legacy drafts without this ledger omit the key and section entirely.
- `source_versions`: distinct exact legal source versions and internal control
  rule-version identifiers, plus
  `captured-source:<source_id>:<representation>:<actual sha256>` tokens for all
  retained capture representations. These bind exact bytes without establishing
  authority, identity or historical suitability. If no captures or rule versions
  exist, `source-register-snapshot:<sha256>` binds the actual retained Stage 02
  source-register JSON. Unresolved display rows still have null rule references
  and empty rule-version lists when no rule exists. `coverage`: Stage 05 coverage entries (including
  withheld candidates). `action_accounting`: Stage 06 exact-match/dedup records.
  `calendar_context`: every original normalized calendar row, native identity,
  source date, source owner, source reviewer and operational status retained
  independently of approval, including unmatched tasks and shared ALL rows.

An undated proposal has `proposed_due_date: null`. An existing operational date
is held in `existing_due_date` and accounting. A sole exact system/task match
may propose reusing that source date with explicit source evidence and pending
Operations approval. Ambiguous matches remain undated.
No existing calendar label supplies approved status. `action_ids` can be joined
from action `impact_ids`; a multi-impact action retains the exact originating rule
basis set in its identity key. No renderer supplies missing facts or dates.

Exact calendar matching requires the generated task text and exact system ID.
Source tasks whose semantic equivalence has not been verified remain retained
in calendar context; they are not reported as deduplicated.
