U04 test-only response representations. No live law/company data or authentication.
`text: ""` means an obtained zero-byte response; `text: null` means no response.
Tests supply explicit synthetic metadata and deterministic times. No production
code imports this fixture or chooses fallback content. Extract cases are built
from exact UTF-8 permitted text inside the tests; the original is not retained.

`inspection/` is a retained synthetic end-to-end example: immutable start and
terminal events, a permitted paragraph extract, and its `analysis/claim.json`.
All run/record/source identities and verification statements are synthetic.
A regression independently rehashes the extract and resolves the claim locator.
