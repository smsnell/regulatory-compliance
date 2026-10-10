# U10 Stage 04 factual and policy reconciliation

U10 ends at immutable `04-evidence-reconciliation.json`. It reconciles company
records, retained reports and policy assessments, exposes conflicts/gaps and
accounts for every row. It creates no impacts, actions or final artifacts.

```sh
python3 regulatory-change-impact-brief/scripts/run.py --config config/review.json --capture-slice --reconcile
```

This fresh isolated slice implies U08 report capture and U09 authority. Policy
visible text is captured before Stage 02 freezes using the additive `u10_policy`
extension; earlier runs/snapshots remain unchanged. Stage 03 may be blocked;
factual accounting still runs, and that blocker propagates to Stage 04. The slice
always reports blocked package acceptance because stages 05–07 are absent.

The invoking skill receives a separate `analysis/reconciliation/request.json`
using G1's existing evidence-reconciliation packet envelope. Its exact request,
proposal, response, parse/binding diagnostics and submission pointers are retained
under `analysis/reconciliation/`. Host stdout/stderr/usage have their own directory;
U09's packet/logs remain immutable. Existing runtime host functions retain their
default behavior with an optional local analysis-directory argument. Networking,
external mutations/sends, recursive launch and inherited multi-agent tools stay
restricted as in U03/U08/U09.

The copied submission helper also receives the exact reviewed route declarations
from `config/review.example.json`, bound as a packet reference. These declarations
allow independent capture reconstruction; they supply no company facts.

`reconciliation-basis.schema.json` provides typed factual/policy assessments
inside G1's existing `conditions` string array. Python validates system/report,
citation, scope, dates, provenance-test and policy prerequisites; accepted model
output remains a draft semantic interpretation. Schema/quote matching is not proof
of factual truth. Missing identity/date/meaning stays unresolved, without a
freshness threshold or historical inference from retrieval time.

`freeze_reconciliation` independently verifies the U09 projection, company capture
ledger and exchange, then writes G1 fact/control/incident/conflict/gap records with
exact Stage 03 predecessor and upstream consumption. Reported register fields use
`reported.<field>`; verified factual predicates are separate. Each fact retains
all assertions. Conflicts group by exact system, field and output/interaction scope;
conflict records carry both values/bases and the linked fact, evidence, known owner
and resolution need. Missing owners remain null unless another known source owner
supports the field. Multiple SYSTEMS owner assertions route ambiguity to Operations.

EVIDENCE occurrences with a nonempty native status become separate source-reported
incident/evidence records. The original status survives even when normalization
rejects its meaning; a missing status produces an explicit gap and raw occurrence,
without an invented incident status.
Closed status grants no incident resolution. CALENDAR occurrences retain all fields,
IDs, dates, status, reviewer and upstream locators; pending approval and unresolved
completion remain explicit. ALL stays a scope token with no invented per-system
rows. Duplicate identities and dates retain all occurrences, without newest wins.

Policy controls require captured POLICY identity/version/control/activation and
historically suitable dates/scope. Pending/unknown controls stay as retained
candidate issues; conflicting meanings/versions stay for Legal. Controls retain
internal-control basis and version keys; they never become law or approved
exceptions. U09 legal applicability remains upstream, not reinterpreted here.

The additive `u10_reconciliation` extension has an eight-system membership ledger,
raw tables/data rows, normalized row/output links, report accounting, candidate
reviews, policy context, calendar context and field scopes. Unnormalizable rows
retain original cells and an explicit gap. The ledger covers every scoped system
in every register; missing membership, extra IDs and ALL context remain visible.
The whole verified upstream ledger is consumed because even invalid inputs inform
uncertainty. Primary source bytes and all earlier snapshots remain unchanged.

`validate_reconciliation` rebuilds the projection from journal/rows/exchange and
compares full substantive records, scopes, values, multiplicity, status and bindings.
It replaces random current-stage IDs only for comparison; it preserves ordered
source matrices/cells and exact candidate arrays. Coherent edits to Stage 04 fail
even if structural schemas and predecessor hashes pass. Retry uses a fresh run;
existing snapshot writes are rejected.

The [G3 fact/disposition contract](../regulatory-change-impact-brief/references/g3-fact-and-impact-contract.md)
freezes predicate semantics, unknown/conflict propagation and the four-state
truth table for U11. U10 does not implement that engine. Verification, limitations,
independent inspection and scanner disposition are in [the U10 report](verification/u10.md).
