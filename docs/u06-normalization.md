# U06 register normalization contract

`rci.normalize.normalize_registers(store)` consumes the independently checked
U05 anonymous register handoff. It revalidates immutable journal/capture bytes,
then returns `normalized_rows`, `mappings`, `diagnostics`, `evidence`, `raw_tables`
and a local normalization `status` (`complete` or `partial`). This status describes
normalization only; it does not determine legal authority, run publication or
approval. Individual unavailable registers yield diagnostics while usable
registers may still be normalized. Existing error captures remain in the U04
store, never interpreted as register content.

`normalize_table(...)` is the pure transformation seam for captured text matrices.
Its caller supplies validated acquisition context, evidence and run identity.
Production consumption uses `normalize_registers`; the pure seam does not verify
access or source identity by itself. Neither function writes snapshots or source
files. U07 owns subsequent stage wiring.

The reviewed [dictionary](../regulatory-change-impact-brief/references/field-dictionary.json)
binds the exact U05 CSV paths/hashes, headers, source columns, expected tab titles
and interview meanings. Version 1 declares no aliases. Every observed semantic
field is required; unrelated columns, including blank or duplicated extra headers,
are preserved positionally as raw cells and ignored semantically. Enum mappings
accept exact documented tokens only. New valid
date/version strings are accepted without changing the assigned date or asserting
historical/legal suitability. New aliases or changed meanings need documented
source/owner support and dictionary review; spelling similarity is insufficient.

## Frozen records and supplemental values

Every accepted identity has the unchanged G1 `normalized-row` envelope:
run-specific internal ID, exact `source_business_id`, exact `system_id`, source,
summary, evidence links and sheet row locator. Record identity never uses row
position. A conflicting source identity keeps both rows, marked unresolved;
there is no first/last winner. Missing/invalid identity or malformed row width
prevents a normalized envelope but retains the entire input in `raw_tables` and
creates a diagnostic. `raw_tables` is accounting, not a new graph collection;
future stage wiring must retain it through the frozen extension boundary or
equivalent validated accounting and keep substantive records in their collections.

The `values` object uses `rci-normalized-values/1`: register kind, exact raw
header/cell arrays, typed `fields`, field-level sheet locators and
`validation_status` (`valid` or `unresolved`). Supplemental
[schema](../regulatory-change-impact-brief/references/schemas/normalized-values.schema.json)
defines SYSTEMS/EVIDENCE/CALENDAR fields. Valid rows require every semantic
field. Invalid fields are omitted from typed values, with original raw cells
and diagnostics retained. All other valid fields survive. Both schemas reject
unexpected normalized properties/types. This extends `values` within the frozen
core contract; no G1/public schema changes are needed.

Mappings use the unchanged `mapping` envelope, with dictionary version and
source header → canonical field / actual column / meaning. Diagnostics use G1
fields, source/capture basis, row locator, known owner (otherwise null), reason
and resolution need. Header ambiguity prevents the entire table's semantic
mapping. Raw duplicates and unknown renames are retained without flattening them
into a lossy object.

Each verified CSV table gets one U04 claim-evidence record quoting the exact
retained CSV and binding its capture ID/path/hash. Rows and mappings cite that
record and carry precise row/cell locations. The assertion describes transcription
of source-reported values only. It does not establish linked report content,
compliance, notice timing, machine-readable provenance or authorized approval.

## Specific preserved meanings

| Source field | Normalized field/type | Meaning boundary |
|---|---|---|
| SYSTEMS provider_role / deployer_role | Same names; yes → true, no → false, unknown → null | Reported role assertions; no universal deployer default or final Legal interpretation |
| SYSTEMS current_notice | Exact enum token | visible_label remains visible_label; no provenance fact is created; yes does not establish notice timing |
| SYSTEMS evidence_status; EVIDENCE evidence_state | evidence_state; exact enum token | complete is supplied evidence, not compliance; conflicts/partial/missing/stale remain source assertions |
| SYSTEMS evidence_updated_at | evidence_updated_on; DATE string | Evidence update date; not retrieval/source revision/effective date |
| EVIDENCE record_type | source_record_type; exact enum token | Distinct from internal normalized-row record_type |
| EVIDENCE reported_at | reported_on; DATE string | Report date; no invented timestamp or observation date |
| EVIDENCE status; CALENDAR status | operational_status; exact enum token | No approval/completion/compliance result is created |
| CALENDAR due_date | existing_due_date; DATE string | Existing operational deadline; top-level existing_due_date agrees; never a proposed/approved/legal date |
| CALENDAR approval_required | required_reviewer; Legal / Operations | Required review path, not decision or authenticated identity |
| CALENDAR system_id ALL | Exact text ALL | Retained scope token; no system expansion or join is performed |

Names, use cases, owners, exposed-group text, human-review paths, report references,
notes, task text and row/source versions retain exact strings. Exposed groups
are not split using an invented delimiter. Linked report reads, identity/scope
verification across registers, conflict adjudication, impacts and approvals
remain their planned later units.
