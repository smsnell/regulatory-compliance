# U05 source connection preflight

> Security remediation (2026-10-08): original live bundles referenced below
> are now in controlled storage outside Git. Offline tests use labeled
> `tests/fixtures/sanitized/` derivatives. Links to retained material now open labeled sanitized derivatives.
> Historical verification statements describe the originals; see [evidence access and verification](secret-safety.md).

U05 supplies callable read adapters and a separate connection check. It does not
produce snapshots or implement U06 normalization, scope discovery or later engines.
The production supervisor's U03 skeleton still reports blocked until those units
exist. This spike is not an end-to-end production package.

Use the U03 Python 3.12+ environment with the unchanged dependency lock:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-u03-clean/bin/python regulatory-change-impact-brief/scripts/check_sources.py --output /tmp/rci-source-check --require-registers
```

The command creates a new run beneath the dedicated external output directory,
holds the writer lock, attempts all ten disclosed routes, checks the complete
journal, and writes `analysis/source-access.json`. With `--require-registers`, exit zero additionally requires all three register
captures to pass the independent handoff check; exit 3 means register readiness
is blocked. Without that flag, exit zero only means the report was written.
Inspect `register_readiness`, each result and its journal before accepting access. Interrupted/storage-failed runs remain retained
and must not be described as completed connection reports. Retry uses a new run.
There is no fixture or local-cache fallback. Anonymous access is an explicit
read path, not a fallback from the authenticated Sheets API.

`source_manifest.manifest(config)` also accepts the existing validated runtime
configuration for future stage wiring. The spike uses the ten reviewed interview
routes in `config/review.example.json`; it never treats those declarations as
verified facts. `ReadAdapters.read(Source)` returns the ordered U04 terminal events;
the caller owns the isolated store and writer lock. The adapter is sequential.

## Supported connections and credentials

`http-read` uses GET against the disclosed HTTPS host. Each redirect and retry is
journaled before dispatch; redirects remain on the original host, exclude login
hosts and credential-shaped queries, and are capped at three hops. Attempts retain
their original locator and actual dispatch locator. One retry is permitted for
transport failures, 429 and selected 5xx responses; the configurable ceiling is
two retries, with bounded one/two-second backoff. HTTPX timeout is 20 seconds per
network operation, not a total run deadline. Unbounded Retry-After is not followed.
Only completed response bodies are claimed as content. Completed malformed redirect
responses are retained before HTTPX processes their Location. Body bytes are the
HTTPX decoded response representation, identified in capture metadata; its hash
never claims compressed wire bytes. Unsupported formats and challenge/login/landing
pages remain captured and unusable. No executable source instructions are followed.
Identity parser failures also retain the completed body and a terminal unverified
outcome; parser diagnostics cannot interrupt accounting for the remaining routes.

`google-sheets-read` now defaults to **anonymous** access, as instructed. It uses
GET on the disclosed Google Sheets URL and its observed same-document redirects
through `/` to `/edit`. No Authorization header, token or credential inventory
is used. No source sharing settings are changed.

The retained HTML's returned `og:url` establishes spreadsheet ID; `og:title`
establishes title. The observed, inert `bootstrapData` JSON supplies the complete
tab inventory, grid bounds and revision counter. Two observed native grid encodings
are supported; JavaScript is never executed. Unknown layouts, missing/hidden tabs,
partial native ranges, truncated tables and ambiguous identities remain unverified.
Grid row/column bounds must be positive integers; null, string, boolean and
nonpositive bounds are rejected before tab export.
This HTML layout is not a stable API contract; an upstream change must fail visibly.

Every discovered tab is read separately using Google's documented
[anonymous Visualization connection](https://developers.google.com/chart/interactive/docs/spreadsheets):
`/gviz/tq?gid=<discovered-id>&headers=1&tqx=out:csv`. There is no filter, range,
limit or first-tab default. When a tab's native table is not present in the first
page, `/edit?gid=<discovered-id>` is read and retained before its CSV. All rows
and headers must match the native HTML cells exactly; type inference must never
silently erase headers, values or dates. Missing data makes the handoff blocked.
The CSV request uses one header row only where the actual native row is retained
and verified; no semantic field mappings are established in U05.

A fresh final `/edit` read brackets the tab captures. Spreadsheet ID, title,
tab inventory, native values and revision must remain consistent. HTML retains
links and visual/source context; CSV retains the verified raw text cell matrix
with row/column locators. Each redirect, metadata read, tab read and final check
has its own immutable U04 attempt/capture. The independent readiness check reopens
and hashes the bodies, reparses native HTML, and compares all CSV values again.
It requires data rows from every declared tab; empty/unsupported tabs remain blocked
for this handoff. It does not establish source meanings or legal applicability.

The original authenticated API adapter remains available only through explicit
`--sheets-access api`. That route uses
[spreadsheets.get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/get)
with `includeGridData=true` and no ranges/field mask. Its previous unauthenticated
403s established missing API caller identity, not spreadsheet permission denial.
API report success is separate from this anonymous register-readiness gate.

For a future explicitly requested API read, an external nonsecret credential
inventory may declare owner, principal, exact `spreadsheets.readonly` scope, and an
`RCI_*` environment-variable reference. Token values remain outside repository
files and reports. Example inventory entry:

```json
{
  "external-readonly-source-login": {
    "owner": "actual credential owner",
    "principal": "actual source account",
    "scopes": ["https://www.googleapis.com/auth/spreadsheets.readonly"],
    "token_env": "RCI_SHEETS_ACCESS_TOKEN"
  }
}
```

Supply that file with `--credential-inventory /external/path/inventory.json` only
when selecting API mode. Broad/mutation scopes and secret-valued inventory fields
are rejected. Inventory records the operator's declared scope; it is not independent
OAuth scope attestation. Anonymous mode ignores API credentials entirely.
The Notion HTTP adapter still supports public reads, not authentication/rendering.

## Identity and historical suitability

Title, visible heading and document content checks establish limited route identity for
LAW, TIME and FAQ. OJ additionally needs the regulation identifier in returned
text/title. The amendment's act identity/relevance and consolidated historical
version require inspection; the adapters do not infer those from the request URL.
Returned title/document ID/tab inventory, ETag and Last-Modified are recorded where
available. `version: null` is explicit unknown. The immutable assigned review date
remains 2026-08-26; historical suitability is unresolved until an authorized basis
is available. A successful read is unselected pending later-stage assessment.

## Original API access spike (2026-10-08; historical)

Retained [machine report](../tests/fixtures/sanitized/u05-errors/analysis/source-access.json),
[journals](../tests/fixtures/sanitized/u05-errors/analysis/attempts/) and
[response bodies](../tests/fixtures/sanitized/u05-errors/sources/) are an access spike, not fixtures
or a production package. Every success claim below has a retained body/hash.

| Route | Observed result | Identity/version and blocker | Next owner |
|---|---|---|---|
| LAW | HTTP 200, retrieved | Article 50 title and document content match; historical version unknown | Legal for historical authority assessment |
| OJ | HTTP 202, invalid | JavaScript/WAF challenge body, no returned title/act identity | Operator for permitted browser/rendered access |
| AMEND | HTTP 202, invalid | JavaScript/WAF challenge body, amendment identity and relationship unverified | Operator, then Legal |
| CONSOLIDATED | HTTP 202, invalid | JavaScript/WAF challenge body, disclosed historical version unverified | Operator, then Legal |
| TIME | HTTP 200, retrieved | Timeline title/content match; historical version unknown | Legal for timing assessment |
| FAQ | HTTP 200, retrieved | Article 50 transparency FAQ title/content match; version unknown | Legal for contextual assessment |
| POLICY | HTTP 200, unverified | Title “Notion”; application shell does not establish policy content/identity/version | Policy owner/operator for authorized readable representation |
| SYSTEMS | HTTP 403, unavailable | No Sheets credential supplied; no returned spreadsheet ID/title/tabs | Source owner/operator for read-only access |
| EVIDENCE | HTTP 403, unavailable | Same authorization blocker | Source owner/operator |
| CALENDAR | HTTP 403, unavailable | Same authorization blocker | Source owner/operator |

No blocked route is a successful retrieval. Browser/rendering, private credentials
and substantive legal relevance cannot be supplied by stronger reasoning. A
chat-only connector is not configured as a CLI integration; its availability
would not demonstrate this repeatable command. Any additional adapter/endpoint
must be documented and authorized before use.


## Anonymous register handoff (2026-10-08)

The [fresh report](../tests/fixtures/sanitized/u05/analysis/source-access.json)
supersedes the original API spike for register access. Original failures remain
preserved. All ten core routes were attempted; the run contains 22 distinct
attempts, including register redirects, per-tab CSV reads and final identity reads.

| Source | Returned tab | Columns | Data rows | Handoff |
|---|---|---|---|---|
| SYSTEMS | AI System Register (gid 0) | 13 | 8 | ready |
| EVIDENCE | Incident Evidence Register (gid 0) | 9 | 10 | ready |
| CALENDAR | Compliance Calendar (gid 0) | 8 | 8 | ready |

All returned IDs match the disclosed IDs. Raw first rows include the formerly lost
`evidence_updated_at`, `reported_at`, and `due_date` headers. Full cell text,
source record IDs, report references, states and review labels are retained
without normalization. SYSTEMS contains the eight actual IDs AI-001 through AI-008.
Every native value matches its tab CSV; hashes independently verify. Observed HTML
revision counters are 8, 8 and 9 respectively, with consistent final reads. Those
counters and row-level `record_version` values are distinct from historical legal
suitability, which remains unresolved. `authenticated: false` now accompanies
successful anonymous reads; no credential is needed for these registers.

U06 can consume these retained header/row captures to establish mappings. This
resolves its register-data blocker; U06 implementation was not started. EUR-Lex
and Notion limitations remain as previously documented and do not block this handoff.
