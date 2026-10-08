# U02 / G1 executable contracts — version 1

This is the U02 implementation of the unchanged [U01 baseline](../../references/contracts.md)
and [decisions](../../references/decision-log.md), especially D003/D005–D010/D012–D014.
The [internal schema](schemas/contracts.schema.json) supplements the unchanged
[public schema](../../snapshot.schema.json). It does not relax public requirements.
The core interfaces below are the G1 handoff; gate results and limitations are in
[U02 verification](../../docs/verification/u02.md). No adapters, stage business
engines, model client, renderer, supervisor or recovery procedure is implemented.

## Validation and records

`rci.contracts.validate_schema(value, definition="snapshot")` checks Draft 2020-12
with an explicitly registered date/date-time checker. Snapshot validation also
checks the public schema and its original exact-byte fingerprint. A schema-only
pass is insufficient: `rci.snapshots.validate_snapshot(snapshot, root=..., upstream=...)`
checks typed records, provenance, actual retained bytes and graph relationships.
Use a verified, ordered upstream prefix from `read_chain`; a caller-supplied dict
is not independent evidence of a file's integrity. Validation never modifies input.

Every snapshot carries `contract_version: rci-contracts/1`. Every record has an
`id`, `record_type`, meaningful `summary`, `evidence_ids` and the type-specific
required values declared in `$defs`. The collection/type/stage correspondence
is in `COLLECTIONS`. Records in `unresolved` are typed gaps; `decisions` are typed
engineering decisions with every R6 field, durable decision basis and explicit
provisional status. Unknown owners are null, with visible reason/resolution need.
Unknown fields in these core records are rejected.

Record collections may be empty except scope basis and the publicly nonempty
scope/audience/gate/source collections. This review identifies eight distinct
system IDs and the two audiences Legal/Operations. A synthetic fixture is never
proof of actual company identity. U07 verifies authorized identity and scope.

Record IDs must be unique and bind their run, stage and type. Produced IDs
enumerate all current records, including gaps and decisions. Consumed IDs exist
strictly upstream in the same run. Every upstream record link appears in consumed
IDs. Link types and direction are checked; same-stage relationships follow the
explicit `LINKS` table and may not form cycles. Stage 02 source→attempt,
capture→attempt and evidence→capture links are current-stage provenance, never
upstream consumption. Evidence IDs resolve specifically to claim evidence, not
URLs, source declarations, hashes, gaps or decisions. All substantive claims need
evidence. Direct declarations/captures, explicit gaps and administrative records
(decisions, pending requests/approvals, retained feedback, validation checks and
artifact byte bindings) can have empty evidence; that does not support a factual
conclusion. Text quotations must occur in retained text bytes. Binary/visual
meaning requires U08 evidence inspection; a byte check cannot verify it.

Attempts are distinct from sources and captures. `attempt_key` is a journal key,
not a snapshot record ID. Every attempt belongs to exactly one source declaration;
each obtained representation has exactly one primary capture. `content` is `full`,
`extract`, or null: it describes the retained representation, not inline source
bytes. No obtained content means content/hash/path all null. An obtained empty
file has a real path and SHA-256 of zero bytes. Unknown MIME is
`application/octet-stream` with `content_type_known: false`. Captures carry
representation metadata. A primary capture agrees with the attempt's retained
representation, exact path/hash and MIME. The attempt MIME describes retained
bytes; adapters preserve an original response MIME separately in version metadata
when they retain only an extract. Relabeling a full text capture as binary cannot
bypass quotation checks; text MIME matching ignores case and parameters.

A derived capture has `representation: extract`, `derived_from_capture_id` and
typed `derivation: {method, processed_at}` metadata. It retains its own separate
file/hash/MIME while sharing the parent's original `attempt_id`. Its processing
time is at or after the parent's retrieval/processing time; it is never a new
retrieval. Multiple derived captures are allowed, with acyclic lineage to the one
primary capture for that acquisition. For OCR, retain both the image and derived
UTF-8 text. The contract verifies lineage and bytes; U08 establishes whether the
derived text faithfully represents the image. Evidence binds assertion/quote, locator,
capture, exact path and exact representation hash. Attempt/capture/evidence store
mechanics and source authorization remain U04/U05/U08 work.

`extensions` is an optional versioned map in each state. Each entry has
`schema_version` and object `value`; later units must validate their own accounting
values. It is not another record collection and creates no accepted graph nodes
or graph links. Substantive records still belong in the typed collections.
Stage 06's optional `export_model` is a projection whose detailed schema is owned
by U12; it does not produce duplicate graph records. This extension boundary
allows later-unit detail without changing the frozen core contract.

## Identity and state

`new_run_id()` and `new_snapshot_id()` create fresh UUID-based IDs on every
execution/retry. `new_record_id(run_id, sequence, record_type)` encodes exact run,
two-digit stage and type plus a fresh UUID suffix. Never use synthetic fixture
IDs or reuse earlier production IDs.

`BusinessKey(system_id, rule_basis, kind, distinguishing_scope)` has fixed
`version: rci-business-key/1`. Canonical bytes are UTF-8 JSON of that ordered
five-element tuple, without extra whitespace and without ASCII escaping. IDs are
`impact:v1:<digest>` or `action:v1:<digest>` over those bytes. Dates, wording,
row positions and retrieval metadata are excluded by the constructor. Each
impact/action records its `identity_key`. An impact's rule basis is its exact
rule-version reference, and its authority type agrees with that rule/control.
Concrete factual predicates belong to the impacted system; scoped conflict/gap
subjects cannot introduce another system. A supported impact still requires
supported facts, rather than an unscoped gap. A control also covers that system.
An action's impacts belong to its own system, and its key binds every originating
rule basis. `action_rule_basis(bases)` preserves a single unique basis unchanged;
for multiple bases it returns `basis-set:v1:<sha256>` of the UTF-8 compact JSON
tuple `["rci-action-bases/1", sorted_unique_bases]`, without ASCII escaping.
Removing or changing a basis changes identity; reordering impacts does not.
The linked impacts retain each separate legal/policy basis and its authority type.
Action kind and distinguishing scope remain independent identity components.
Source business IDs are preserved exactly. `IdentityRegistry.operational` rejects
duplicate identities in a source namespace, retaining the need to resolve both
inputs. `IdentityRegistry.business` permits the same semantic key and rejects a
hash collision involving different keys. Callers retain conflicting rows; these
APIs never fuzzy join them.

`rule_version_id(basis_id, meaning_key)` hashes a reviewed semantic version key.
Both rules and policy controls require `version_key`, `rule_version_id` and
`supersedes_rule_version_id` (null if none). Changed meaning changes the key/ID;
raw wording/date is not a meaning key. Impact/action identity always uses that
stable version reference; a policy-control record ID is never a business basis.
Historical supersession is a business
reference, not fake same-run upstream consumption. `calendar_uid(action_id)` is
the stable action identity plus `@regulatory-change-impact-brief`.

Run, retrieval, impact, approval and publication are separate exact enums.
`reduce_states(nonempty_states)` uses failed > blocked > partial > complete; it
does not convert source-native states or approval into run states. A Stage 03
required-authority blocker cannot be complete/partial. Stage 07 cannot discard an
upstream blocked/failed/partial outcome. Supported impacts and supported no-impact
both require affirmative evidence, an established rule and supported facts.
Predicate completeness and authority meaning remain U09/U11 responsibilities.

Approvals cannot be inferred from labels. An approved action needs an explicit
approval record and no pending or rejected requirement for that action. An
explicit `not-required` requirement does not prevent approval. An
action marked `not-required` must have at least one explicit requirement and all
its requirements must be `not-required`; an empty list does not establish an
exemption. An action marked `rejected` needs at least one explicit rejected
requirement. `pending` remains a conservative action state and asserts neither
a decision nor an exemption. Each request,
subject and reviewer tuple identifies one approval requirement; overlapping
requirements for the same decision are rejected, including identical duplicates.
Different reviewers remain separate decisions. Approval request IDs resolve uniquely to typed review requests;
subjects and required reviewer agree with that request. Linked feedback covers
those subjects and the same request/reviewer. An approved approval record needs
authenticated, matched feedback with an approved or satisfied conditional outcome.
A rejected approval record likewise needs a request and nonempty authenticated,
matched feedback whose outcomes are all `rejected`. The same subject, reviewer,
retained-draft and current revalidation checks apply to both decision outcomes.
Technical validation failures remain failures or unresolved feedback and cannot
manufacture a reviewer rejection.
Matched feedback requires `reviewed_draft` and `revalidation`; empty artifact
claims cannot authorize approval. The exact schemas are `$defs/reviewed-draft`
and `$defs/review-revalidation`.

`reviewed_draft` identifies `history/<claimed_run_id>` and exact Stage 06/07
snapshot ID/path/hash pointers from that prior run. Validation rereads the
retained snapshot chain, checks schemas, predecessor bytes, record identities,
and the reviewed request's run/draft/source versions and authorized role. It
checks all three detached artifact pointers against both the retained inventory
and actual artifact bytes. All paths within that review context resolve against
its archive root. An incomplete marker rejects the context. All seven retained stages receive the same core schema, evidence, graph,
identity and publication checks as current stages. Historical feedback is checked
for local structure and relationships, but its prior-draft revalidation is never
recursively applied. This mode is internal to retained-context validation;
public snapshot/package validation always applies current feedback checks. These context checks do not claim complete historical renderer/business
acceptance or create an archive; U17/U18 retain those responsibilities.

`revalidation` separately binds the current run/request/draft/source versions,
reviewed Stage 07 hash, and every current upstream snapshot's exact bytes. Its
one-to-one `subject_bindings` map historical claimed subjects to current resolved
subjects using stable semantic identities. Action/impact/rule/control/source IDs,
system/predicate factual keys, native incident/row identities and explicit scope
IDs support correspondence; an unverifiable or changed subject stays unresolved.
Four explicit reports cover `facts`, `source_versions`, `scope` and `conditions`.
Each needs a result, reason and nonempty consumed current-run evidence. Only
four passed reports permit matching. Unknown or failed reports remain retained
unresolved, with empty resolved subject/request links and no approval effect.
The actual reviewer response time must follow the reviewed draft and cannot be
later than the current snapshot.

U13 must establish trusted identity/channel, role authority and substantive
applicability, and produce the evidenced revalidation reports. U02 checks their
structure, byte bindings and identity/provenance consistency; a passed report is
not automatic legal proof. `claimed_*` fields continue to describe the original
reviewed request/run/draft/source/artifact bytes. They are never rewritten to
make old feedback look current. Resolved `subject_ids`/`request_id` identify the
new draft only after the explicit current revalidation.

Every approval-bearing response with nonempty conditions, including
`outcome: approved`, needs `conditions_satisfied: true` and nonempty
`condition_evidence_ids` on the approval. Conditional outcomes also require
actual conditions. U13 establishes satisfaction against the authenticated
conditions; neither an outcome label nor a bare satisfaction flag suffices.

Requests preserve every R6 field, including source versions, subject systems,
question, reviewer, draft/run and delivery status. `sent` requires delivery
evidence; tool permission to send is never established by a record.

## Scope, time and immutable snapshots

Scope uses assigned date `2026-08-26`, `as_of: 2026-08-26T00:00:00Z` and
`as_of_precision: date`. The encoded midnight is not a legal cutover. Actual
retrieval, source revision/publication, effective interval, factual observation,
existing due date, proposed due date and reviewer response time have separate
fields. Date-only revision/observation use `source_revision_date`/`observed_on`;
do not invent midnight timestamps. Instant effective intervals use
`effective_from_at`/`effective_until_at`, distinct from date intervals; precision
is explicit where available. Newer valid dates are accepted syntactically.
An established instant boundary requires an explicit known timezone: `UTC`, a
numeric `±HH:MM` offset within RFC3339 bounds (excluding unknown `-00:00`), or an
IANA name resolvable through Python `zoneinfo`. Ambiguous abbreviations, unknown
labels, invalid offsets and unavailable zones remain unresolved; no host timezone
is inferred. Unknown precision also cannot establish applicability. Date-only
boundaries do not require an invented timezone. Applicability and historical
suitability are separate from successful retrieval and schema conformance.

Stage 01 primary `scope-basis` records are either:

- `declared`: authorized actual IDs, basis/version, no invented attempt/time;
- `discovered`: actual IDs, authorization/basis/version and direct original
  attempt key/retrieval time/source path/hash, with no forward Stage 02 IDs.

Stage 02 imports each discovered attempt exactly once with the original
key/time/path/hash and a `scope_basis_id` link. Discovery must finish at or before
Stage 01 creation, comparing timestamp instants across explicit UTC offsets;
equal timestamps are allowed at the recorded precision. A genuine extra read
uses a new attempt key. Failed scope discovery
produces an incomplete preflight inventory, not a conforming scope snapshot.

`write_snapshot(root, snapshot, upstream=...)` validates, serializes once to
UTF-8 JSON, writes the exact numbered path exclusively, and returns the
snapshot/path/`sha256:<64 lowercase hex>` binding. Existing files are not
rewritten. `json_bytes` is deterministic serialization, but hashes are always
computed from actual serialized/written bytes, never a separately normalized
object. Caller-supplied upstream objects must match retained parsed values with
types preserved recursively: boolean `false` is not numeric `0`, and `true` is
not `1`. This check also applies to interpretation inputs. Stage 01 has no predecessor or consumed IDs. Each later snapshot binds
the immediately previous file's ID/path/exact bytes in the same run.
`read_chain(root, count=7)` independently rereads a prefix and checks it in order.
Paths resolve against that package root (including archived roots); absolute,
traversing, noncanonical or escaping symlink paths are rejected. Duplicate JSON
keys, non-finite JSON values and malformed UTF-8 are rejected. Numeric exponent
overflow (for example `1e999`) is rejected recursively after parsing. Schema
validation also rejects nested non-finite caller-supplied float values before
record acceptance; ordinary large finite numbers remain valid.

## Skill/Python interpretation exchange

`validate_interpretation(request_bytes, response_bytes, root=..., run_id=...,
stage=..., upstream=...)` returns `ExchangeResult`. The exact shapes are
`interpretation-request` and `interpretation-response` in the internal schema:
`rci-interpretation-request/1` and `rci-interpretation-response/1`.

The immutable request binds packet/run/stage, assigned date, upstream IDs/paths/
exact hashes (including immediate input), captured extracts/locators/evidence/
capture IDs, exact extracted text/hash, versioned field dictionary and expected
response schema. The field dictionary hash is over `json_bytes(fields)`.
Text extracts bind retained UTF-8 text representations; OCR must first bind a
retained derived text capture to the underlying image. The response binds the
exact request-byte hash and packet/run/stage, then returns candidates with scoped
systems, basis type, citations/quotes, conditions, role, timing/exception
candidates and explicit uncertainty. Both carry times and visible execution
metadata. Instruction/reference file hashes and requested model/effort must
match; unreported host/model/effort/usage are null, not fabricated. The invoking
skill is the interpreter; Python performs validation. No API client is present.

Corrupt JSON/envelope schema, changed bytes/basis or cross-run/stage bindings raise
`ContractError` (technical failure). Well-formed refusal/truncation/unsupported/
ambiguous output, missing/malformed candidate support, unsupported citations, unknown meaning or outside-scope
candidates return `unresolved` with original response and reason. `proposed`
is a bounded draft candidate, not Legal sign-off. Quote matching never proves
legal meaning. A snapshot's optional `interpretation_bindings` requires separate
`analysis/` request/response pointers with real hashes and a valid proposed
exchange; duplicates are rejected. U08 retains every exact packet/response and
parse failure diagnostic, including rejected attempts, before invoking validation.
Production response reuse across runs fails run binding; replay fixtures here
are explicitly test-only. U03 establishes the actual host invocation boundary.

## Replacement markers and package readers

Marker basenames are `.incomplete-replacement.json` and `.completion.json`.
The exact schemas are `incomplete-marker` / `completion-marker`.

Incomplete marker (`rci-incomplete-replacement/1`) fields:

- `old_run_id` (null only on first run), different `new_run_id`, `created_at`;
- `archive` (null only on first run), otherwise
  `root: history/<old-run-id>`, exact `inventory_sha256`, `verified: true`;
- `candidate`: `root: .staging/<new-run-id>`, exact `stage07_sha256`,
  `verified: true`.

Completion marker (`rci-completion/1`) fields: `run_id`, `completed_at`,
`stage07: {snapshot_id, path: snapshots/07-publication-validation.json, sha256}`.
`validate_marker` validates shape, root-relative locations and distinct identities.
The executor in U18 must establish archive/candidate verification from real disk
before setting `verified`; this shape is not proof of successful archival. U18
owns inventory contents, lock, marker persistence before overwrite, archive
verification, replacement and clearing incomplete last. No atomic multi-file
replacement or recovery procedure is claimed here.

Any incomplete marker, even malformed or a broken symlink, wins over completion
and makes `read_chain`/`accept_package` reject the package. `accept_package` also
rereads all snapshots, verifies completion's current run/Stage 07 ID/hash and
requires validated publication. Validated publication needs exactly three
retained artifact records with real hashes and passed checks. Requests have
unique detached bindings to all three exact artifact paths/hashes; the brief
never needs its own hash embedded. Missing artifacts have no artifact record or
invented hash: failed publication retains a separate path/reason inventory.
Artifact grammar and semantic cross-file checks remain U14–U17 work; U02 accepts
contract bindings, not a renderer's assertion of real-world compliance.
