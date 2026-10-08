# U06 source fixtures and acceptance oracle

The tests use the explicitly retained U05 anonymous source observations in
`docs/verification/u05-anonymous-live/`, including their immutable journals and
response bodies. No new live reads or production local-file fallback are implied.
The original `docs/verification/u05-live/` API errors are negative fixtures.

Actual captured registers: SYSTEMS has 13 headers / 8 rows, EVIDENCE 9 / 10,
CALENDAR 8 / 8. Each has one tab, gid 0. Independently verified U05 native HTML
and CSV cell matrices agree. The dictionary binds exact CSV paths and hashes.

The positive oracle asserts all 26 business IDs/rows survive, source text remains
exact, and semantic fields/IDs stay identical after row/header permutation and
unrelated-column insertion. Raw cell and field locators follow the new positions.
Unrelated extra headers may be blank or duplicated; their cells remain positional,
while duplicated required semantic headers still block mapping.
New dates/versions affect only their corresponding values, not source identities.

Specific meaning oracles use source rows and interview 04:35–04:46: AI-003 and
AI-008 have visible labels, not proven provenance; AI-005 has unknown provider
role; REC-001's closed/complete labels do not create compliance or approval;
REC-010 remains a draft exception request; CALENDAR review labels identify
Legal/Operations, not decisions; ACT-008's ALL token is retained without expansion.

Negative cases mutate individual captured fields/layouts and require visible
diagnostics, unchanged raw cells, and unresolved/excluded normalized rows rather
than invented values. Both duplicate-identity rows remain unresolved. Missing
identity never receives a row-number identity. Unknown aliases are rejected for
every required header. The replay integration supplies actual captured HTTP
bodies through HTTPX MockTransport into U05's real adapter and a fresh U04 store;
it performs no network calls and binds new-run evidence through the normalizer.
