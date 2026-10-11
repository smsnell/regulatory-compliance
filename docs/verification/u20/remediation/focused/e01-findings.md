# E01 representation remediation

The implementation compatibility portion is repaired. No historical applicability,
legal interpretation, or final Legal assessment is supplied. The retained U20 live
exchange remains ambiguous and yields zero accepted binding rules.

Changed implementation/instruction files:

- `regulatory-change-impact-brief/scripts/rci/authority.py`
- `regulatory-change-impact-brief/scripts/rci/authority_representations.py`
- `regulatory-change-impact-brief/references/authority-policy.md`
- `tests/runtime/test_u20_authority_remediation.py`

Supported date encoding is bounded to complete ISO dates, full English calendar
dates using ordinary space or NBSP, and EUR-Lex dotted day.month.year dates.
Mappings retain exact quoted text and character offsets. Invalid calendar dates,
slash dates, abbreviated/ordinal/nonstandard space representations, partial dates,
intraday ISO timestamps, and contradictory adjacent aliases fail closed. Multiple
valid dates in distinct clauses still require semantic review of scope and qualifiers.
Relative commencement formulas are deliberately unresolved: the amendment's
"third day following publication" is not converted into an applicability date.

AMEND's current OJ selector maps to an exact Regulation (EU) year/number header.
The current consolidation selector maps to its exact captured document identifier
and matching EN version header. Selector shape, requested/returned identifier,
version-header identifier/date and contradictory OJ version identifiers are checked.
Substring matches to longer or differently prefixed identifiers are rejected.
The read adapter remains conservatively unverified for amendment/consolidation;
representation matching does not upgrade authority or historical suitability.

Accepted nonliteral mappings are recorded in the existing U09 extension with
basis/source/evidence/capture IDs, capture hash, source version, original/effective
locators, exact quotes, encoded values and mapping details. Existing literal-only
or unresolved accounting remains unchanged. No frozen schemas/contracts changed.

Red command (exit 1, `red.txt`):

```
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/home/mike/regulatory-compliance/.evidence/u20-remediation/tmp .evidence/u20/venv/bin/python -m pytest -q tests/runtime/test_u20_authority_remediation.py
```

The observed `12.7.2024` publication failed the previous literal ISO prerequisite;
the exact retained `2 NBSP August 2026` quote was also present in the witness.

Final focused command (same command, exit 0, `green-focused.txt`): **57 passed in
14.95s**. These cover actual retained OJ/AMEND/CONSOLIDATED/FAQ byte-bound dates,
actual amendment/consolidation identity forms, adversarial dates/IDs, the retained
ambiguous exchange still withholding all rules, and a new synthetic capture through
quote validation/submission/freezing. The latter emits provenance while retaining
all earlier source bytes and first two snapshots; its legal semantics remain
explicitly synthetic and are not a real-law interpretation.

The reference update uses the writing-for-agents skill. A final package-wide local
scan is coordinated with the root agent after all concurrent implementation edits.

Read-only E02/E03 inspection: current HTTP POLICY reads have no authenticated
policy read flow; external credentials are consumed only for the Sheets adapter.
An identifiable authorized policy route/content or supported authenticated adapter
is still required. Report read dispatch requires an explicitly supplied HTTPS URL
without query/fragment/userinfo; existing EVIDENCE labels authorize no invented
route. No existing legitimate route closes those gaps from retained labels alone.

## Authorized implementation fingerprint amendment

The initial focused U09 regression command also ran `test_u09.py`,
`test_u09_timing.py`, and `test_u09_projection.py`: **52 passed, 2 failed in
306.09s**, retained in `green-initial.txt`. The two failures were the E04 decision
projection in the CLI subprocess and the deliberately pinned runtime implementation
hash; neither was a public-schema fingerprint change. The root agent authorized
updating the implementation assertion explicitly and preserving both schema
assertions. The subprocess issue is handed to the E04 owner.

`tests/runtime/test_u09.py::test_additive_schema_and_frozen_contract_fingerprints`
now asserts the E04 amended `snapshots.py` bytes rather than dropping the check:

- Previous U19 implementation hash:
  `sha256:a9b14e8ebed869dbdc4cc0952ed36eba1468bb28246559f09be7e28f2b7ff2e0`
- Amended U20 E04 implementation hash:
  `sha256:cbb640b9cf165851fd5675b55a246a2f7b5fc1b2545717c7b12c8b6e95ad1ee8`

The amendment is additive opt-in runtime decision validation authorized for E04.
The test comment points to the remediation report and this finding record. The
original `snapshot.schema.json` and typed contract schema assertions remain intact
with their original hashes.

Both initially failed regression cases now pass against frozen code:

- `test_u09.py::test_additive_schema_and_frozen_contract_fingerprints`: exit 0,
  1 passed in 0.40s (`green-fingerprint.txt`).
- `test_u09.py::test_helper_cli_and_independent_projection_tamper`: exit 0,
  1 passed in 13.34s (`green-cli-projection.txt`). The E04 owner identified the
  initial projection mismatch as an in-flight decision-text revision between
  the parent Python import and child import; the frozen-code rerun confirms
  parent/child agreement. No additional production correction was needed.

Each exact rerun used `PYTHONDONTWRITEBYTECODE=1
TMPDIR=/home/mike/regulatory-compliance/.evidence/u20-remediation/tmp
.evidence/u20/venv/bin/python -m pytest -q` followed by the named test selector.
The implementation assertion's report pointer is
`docs/verification/u20/remediation-report.md`, the user's requested location.
