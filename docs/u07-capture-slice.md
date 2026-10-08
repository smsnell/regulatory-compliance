# U07 scope and core capture command

Run the implemented two-stage slice using the pinned U03 environment:

```sh
python regulatory-change-impact-brief/scripts/run.py --config config/review.example.json --capture-slice
```

This uses the actual read-only U05 adapters. With no declared scope, it journals
SYSTEMS discovery before each GET, establishes eight distinct IDs from the
complete identity-verified register, then freezes Stage 01. Stage 02 imports all
original discovery attempts, adds the scope-basis link to the one CSV attempt
that supplied the IDs, and freshly reads the other nine core sources. Each
redirect, retry, native page, tab export and consistency check is its own attempt.
The journal is never rewritten or retimed. No model interpretation is needed
for this deterministic slice. The U03 host command/profile is unchanged; host
interpretation integration belongs to subsequent units.

For established scope, provide a separate authorized scope input:

```sh
python regulatory-change-impact-brief/scripts/run.py --config config/review.example.json --capture-slice --scope /path/to/authorized-scope.json
```

The input conforms to `references/schemas/scope-input.schema.json` inside the
skill package. It contains `schema_version: rci-scope-input/1`, exactly eight
unique actual `system_ids`, `basis_version`, `authorized_by`, and a nonempty
`source_basis` list. Authorization and IDs come from the request or an explicitly
identified retained scope input. No example substitutes placeholders for actual
IDs. The exact supplied bytes are retained as `analysis/scope-input.json`.
Declared scope permits both snapshots when live corroboration fails; current
missing/additional IDs and identity ambiguity remain diagnostics. The requested
list stays frozen. Source facts still require fresh reads.

Every invocation writes to `<output_root>/.staging/<new-run-id>/`. It preserves
existing current files and earlier candidates. The JSON outcome identifies the
candidate, whether `capture_slice_complete` is true, and missing stages/artifacts.
A successful slice exits **3**, with `status: blocked`, `production_package:
false` and `package_acceptance: false`, because stages 03–07 and final draft
artifacts are outside U07. A failed discovery has no fabricated Stage 01 or 02;
it retains the failed occurrence and missing inventory. Source-access failures,
unsuitable responses and ambiguous source scope are limitations, rather than
technical failures. Technical storage failures, broken integrity and interruption
exit **1**, with `status: failed` and `capture_slice_complete: false`. If scope is
already established and the journal can be honestly frozen, Stage 02 records
`failed` and retains the original technical diagnostics. If integrity or
discovery fails before that boundary, no conforming Stage 02 is fabricated.
Available captures, incomplete starts and failed occurrences remain preserved.

To retry a retained occurrence in the same output root:

```sh
python regulatory-change-impact-brief/scripts/run.py --config config/review.example.json --capture-slice --supersedes-run-id run-ACTUAL-RETAINED-ID --change-reason 'Source access restored'
```

The ID must resolve to an existing retained occurrence. If current Stage 01 exists,
its run is the superseded run and a change reason is required. A new run always
gets new snapshot/record IDs; predecessor links remain within that run. U07 does
not replace current outputs, so archival/replacement execution remains U18.

Stage 01 uses the G1 primary scope-basis record and a versioned extension for the
ten source declarations. Stage 02 uses G1 attempt/capture/evidence/source and U06
normalized-row/mapping/diagnostic records. Supplemental capture accounting retains
raw tables, original technical diagnostics, required sources and requested/current
scope comparison. `rci.runner.validate_slice(EvidenceStore(root, run_id))`
independently rereads both snapshots, verifies journal equality, retained input
bytes, actual ten-source coverage against declarations, authorized original
routes/adapters and scope comparison. It recomputes U06 normalization from
identity-verified retained captures and compares complete evidence, rows,
mappings, raw tables and diagnostics. Comparison resolves evidence links to
capture/claim values, preserves duplicate cardinality and distinguishes booleans
from numbers; only generated record IDs and collection ordering are ignored.
The supplemental normalized-value schema and failure/limitation state are also
checked on reread. G1 schemas, byte hashes and graph validation remain in force.
Generic G1 prefix acceptance alone does not validate these supplemental values.

U05/U06 currently support the disclosed anonymous register routes. An alternate
register route fails explicitly before dispatch; no invented mapping, API-to-CSV
conversion or local fallback is introduced. Historical suitability remains
unresolved separately from identity. AMEND/CONSOLIDATED/POLICY may be unverified;
that result is retained without asserting legal authority. All source authorities
remain unknown in this slice. Cross-register reconciliation, linked report reads,
interpretation and formal legal applicability remain their assigned later units.
U08 must extend capture in a new run before freezing its new Stage 02.
