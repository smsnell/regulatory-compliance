# Regulatory Change Impact & Compliance Actions — Project Requirements

## Scenario

Quillhaven Academy needs repeatable support preparing an evidence-backed review of AI use against EU AI Act Article 50 for Legal and Operations.

The assigned review date is **26 August 2026**. Actual source retrieval times must be recorded separately from the assigned review date and from source version or effective dates.

## Objective

Build and execute an Agent Skills-compliant skill named:

`regulatory-change-impact-brief`

The skill must:

- Read the current disclosed company sources.
- Obtain the required official online legal sources on every run.
- Produce a consistent, review-ready draft package.
- Preserve source provenance, uncertainty, conflicts, unresolved items, and human decision boundaries.
- Explain important automation choices and trade-offs.
- Remain read-only.

The automation must not:

- expose credentials;
- alter source systems;
- provide final legal advice;
- activate policy;
- change approved deadlines;
- close incidents;
- send official responses;
- write to a production calendar.

Legal and Operations retain final decision authority.

---

## Required Repository Outputs

The completed implementation must contain:

```text
regulatory-change-impact-brief/
├── SKILL.md
├── scripts/
└── references/

deliverables/
├── sources/
├── snapshots/
│   ├── 01-scope.json
│   ├── 02-source-capture.json
│   ├── 03-authority-and-timing.json
│   ├── 04-evidence-reconciliation.json
│   ├── 05-impact-analysis.json
│   ├── 06-actions-and-approvals.json
│   └── 07-publication-validation.json
├── impact-register.csv
├── compliance-brief.md
└── action-calendar.ics
```

The supplied `snapshot.schema.json` must remain unchanged.

---

# 1. Snapshot Requirements

Seven snapshots must be written at the corresponding workflow boundaries.

All snapshots in one run must:

- share the same `run_id`;
- conform to the supplied schema;
- contain meaningful summaries;
- contain the actual values required by downstream stages;
- maintain traceability between sources, rules, decisions, and artifacts.

From Stage 02 onward:

- `predecessor` must identify the immediately preceding snapshot;
- `predecessor` must include the hash of the immediately preceding snapshot.

Each record must contain:

- `id`;
- meaningful `summary`;
- `evidence_ids`;
- actual downstream-relevant field values.

`consumed_record_ids` must resolve to records available upstream.

`produced_record_ids` must identify records present in the current stage.

---

# 2. Stage 02 — Source Capture

Stage 02 must record **every source attempt**, including:

- successful attempts;
- failed attempts;
- unused attempts;
- unavailable sources;
- invalid sources;
- unverified sources;
- stale sources;
- unsuitable responses.

Each attempt must record:

- original URL or locator;
- content type;
- actual retrieval time;
- version;
- retrieval status;
- local evidence path;
- content hash.

When no content was obtained:

- content must be null;
- hash must be null.

A link or hash alone is insufficient evidence.

The system must preserve the actual bytes or permitted claim-bearing extracts used in:

`deliverables/sources/`

Captured evidence must include suitable locators such as:

- section;
- paragraph;
- tab;
- row.

The system must verify:

- returned document identity;
- version;
- suitability for the assigned review date.

A login page, landing page, or unrelated response is not equivalent to the requested document.

Interview-disclosed or otherwise authorized source routes may be accepted as runtime inputs.

Current company sources and required official legal sources must be retrieved on **every run**.

Unsuccessful or unsuitable reads must still be retained as evidence of the attempt.

A failed live read must not be silently replaced by an undisclosed local copy.

---

# 3. Required States

## Run State

Allowed values:

- `complete`
- `partial`
- `blocked`
- `failed`

## Retrieval State

Allowed values:

- `retrieved`
- `unavailable`
- `invalid`
- `unverified`
- `stale`

## Impact State

Allowed values:

- `supported-impact`
- `supported-no-impact`
- `conflicting`
- `unresolved`

## Approval State

Allowed values:

- `pending`
- `approved`
- `rejected`
- `not-required`

Required collections may be empty.

Unresolved or conflicting records must remain visible until:

- evidence changes; or
- an actual authorized decision resolves them.

For unresolved or conflicting items, preserve:

- source basis;
- reason;
- known owner;
- resolution need.

Actual field values, source revisions, effective dates, retrieval times, and the assigned review date must remain distinct.

The assigned review date must not be silently changed.

---

# 4. Final Draft Outputs

Stable identifiers and matching source/run references must be used across all final outputs.

## 4.1 `impact-register.csv`

Format:

- UTF-8 CSV;
- header required;
- one row per distinct system/rule impact or unresolved item.

Required columns:

- `impact_id`
- `system_id`
- `rule_ref`
- `state`
- `evidence_ids`
- `reason`
- `owner`
- `proposed_action`
- `proposed_due_date`
- `approval_status`

Rules:

- Evidence IDs may be semicolon-separated.
- Additional columns are allowed.
- Unknown or inapplicable owner, action, or date may be blank.
- If a field is blank because information is unknown or unresolved, the reason and resolution need must remain visible.
- Known dates must use `YYYY-MM-DD`.
- Different legal or policy rule bases must remain distinguishable.

---

## 4.2 `compliance-brief.md`

The brief must include:

- run ID;
- as-of date;
- recipients;
- draft status;
- run status;
- source quality;
- source limitations;
- supported observations;
- conflicts;
- unresolved scope;
- proposed actions;
- proposed dates;
- decisions requested from Legal and/or Operations.

The brief must cite relevant:

- impact IDs;
- action IDs;
- evidence IDs.

The scope of each conclusion must be explicit.

---

## 4.3 `action-calendar.ics`

Must be a valid RFC 5545 `VCALENDAR`.

Required calendar fields:

- `VERSION`
- `PRODID`

Each event requires:

- stable action-linked `UID`;
- `DTSTAMP`;
- `DTSTART`;
- `SUMMARY`;
- `DESCRIPTION`.

`DESCRIPTION` must contain:

- action ID;
- system ID;
- responsible role;
- source or decision basis;
- approval status.

Proposed events must use:

`STATUS:TENTATIVE`

Date-only inputs must use all-day `DATE` values.

If `DTEND` is present for a date-only event, it must be exclusive.

Undated events must not be written to the calendar.

Undated actions must instead be explained in the impact register and compliance brief.

If no dated proposal is supportable, the system must still produce an empty but valid calendar.

---

# 5. Stage 07 — Publication Validation

Stage 07 must record:

- exact final file paths;
- exact final file hashes;
- cross-file agreement against Stage 06.

Stage 07 represents **draft validation**, not:

- human approval;
- external publication;
- legal sign-off.

A bounded partial draft may be internally consistent.

However, an unresolved legal-authority blocker must not be represented as normal validated publication.

If required legal authority is unavailable or unsuitable:

- dependent formal conclusions must be withheld;
- the blocked or unresolved chain must be preserved;
- the impact register and compliance brief must reflect the issue;
- the calendar must be empty or limited to supportable items.

If other unsupported inputs are missing, the system must determine whether:

- the entire run must be deferred; or
- unaffected work can still proceed.

That choice must be explicit and consistent across all outputs.

Missing facts must remain visible.

The system must not manufacture evidence or approval in order to complete the package.

---

# 6. Review Evidence and Decision Records

Each project decision must record:

- concern;
- options considered;
- source basis;
- chosen behavior;
- rationale;
- trade-offs;
- downstream effect.

Review requests must be represented in Stage 06 and reflected in the compliance brief.

Each review request must contain:

- request ID;
- subject system, impact, or action;
- run/version information;
- source version;
- evidence;
- question;
- required reviewer.

Stage 07 must bind each request to the exact reviewed final draft using:

- final artifact path;
- exact artifact hash.

The compliance brief should refer to this detached binding rather than embedding the brief's own hash inside itself.

If actual reviewer feedback is available, retain:

- responder identity;
- responder role;
- subject;
- request ID;
- version;
- response time;
- outcome;
- reasons and/or conditions.

Before applying reviewer feedback, validate that it matches the intended request and version.

Unmatched or invalid feedback must remain unresolved.

The system must not:

- simulate reviewer responses;
- claim that an unsent request reached a reviewer.

The endpoint is a **review-ready draft**, not an automatically approved compliance package.

---

# 7. Changed Inputs and Input Compatibility

The system must tolerate:

- reordered source rows;
- reordered headers;
- unrelated extra columns;
- legitimate newer dates;
- legitimate newer versions.

It must preserve:

- required fields;
- stable IDs;
- disclosed field meanings.

The system must report, rather than guess:

- missing required fields;
- ambiguous required fields;
- conflicting identities;
- invalid values;
- unsuitable responses;
- renamed fields whose meaning is not established;
- changed business meanings.

Format compatibility does not establish legal applicability.

A newer source date or version does not change the assigned review date.

---

# 8. Run History

Before replacing current outputs, preserve the previous available run under:

`deliverables/history/<old-run-id>/`

The preserved history must include the previous available:

- source captures;
- snapshots;
- final draft artifacts.

Every retry must use:

- a new run ID;
- new snapshot IDs.

Stage 01 must record:

- `supersedes_run_id`;
- change or retry reason.

`supersedes_run_id` may be null or absent on the first run.

Version relationships between runs must remain explicit.

Snapshot predecessor relationships must remain within a single run.

Only history that actually exists may be preserved.

Missing or corrupt prior evidence must be recorded honestly.

---

# 9. Recalculation and Recovery

When an input changes:

1. identify the earliest stage whose basis changed;
2. recompute that stage;
3. recompute all dependent downstream stages;
4. regenerate affected final artifacts;
5. revalidate the resulting package.

Even when inputs appear unchanged, the system must inspect the actual current:

- seven snapshots;
- record relationships;
- run bindings;
- hashes;
- required source evidence;
- three final files.

The system must not report success solely because a previous successful run exists.

If outputs are:

- missing;
- damaged;
- stale;
- inconsistent;

the system must:

- repair them where possible;
- revalidate them;
- otherwise return an explicit incomplete or failure result.

Technical failures must be retained with:

- affected stage;
- affected source or output;
- recovery action;
- next owner where applicable.

After repair, the documented end-to-end command must be rerun with fresh required source attempts.

The failed occurrence and its evidence must remain preserved.

Recovery must not invent resolved facts or approvals.

---

# 10. Source and Evidence Reconciliation

The system must preserve traceability across:

- source attempts;
- source captures;
- evidence records;
- rule references;
- impacts;
- actions;
- approvals;
- review requests;
- final artifacts.

Conflicting source records must not be silently collapsed.

Unavailable evidence must remain unresolved.

Unsupported claims must not become formal conclusions.

Different legal, policy, factual, and operational bases must remain distinguishable.

---

# 11. Runtime and Reproduction Requirements

The implementation must provide one documented end-to-end command.

Documentation must identify:

- runtime;
- dependencies;
- setup requirements;
- execution command.

Any suitable implementation language and maintained libraries may be used.

The command must regenerate the current review package from the disclosed runtime inputs and fresh required source attempts.

---

# 12. Required Skill Package

The repository must contain an Agent Skills-compliant skill named:

`regulatory-change-impact-brief`

The skill package must include:

```text
regulatory-change-impact-brief/
├── SKILL.md
├── scripts/
└── references/
```

`SKILL.md` must describe how the skill is invoked and how it produces the required outputs.

Implementation-specific organization within `scripts/` and `references/` may be chosen during system design.

---

# 13. Core Behavioral Constraints

The implementation must follow these principles:

### Preserve uncertainty

Unknown, conflicting, missing, or unresolved information must remain explicit.

### Do not manufacture certainty

The system must not infer evidence, approval, source meaning, legal applicability, or decision outcomes that are not supported.

### Preserve provenance

Every material conclusion must remain traceable to its source and evidence basis.

### Separate retrieval from applicability

Successfully retrieving a document does not prove that it is the correct or applicable authority for the review date.

### Separate operational status from approval

A source status or workflow state must not automatically imply human approval unless an authorized decision explicitly establishes approval.

### Prefer bounded partial output over fabricated completeness

When some analysis remains supportable, the system may produce a partial draft while clearly identifying blockers and limitations.

### Fail closed for unsupported legal conclusions

If required legal authority cannot be verified, conclusions dependent on that authority must not be presented as supported.

### Keep the system read-only

All generated actions, dates, review requests, and calendar entries remain proposals until authorized humans decide otherwise.
