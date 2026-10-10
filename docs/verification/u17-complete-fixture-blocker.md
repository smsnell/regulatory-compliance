# U17 COMPLETE fixture: accepted-contract contradiction

Status: historical contradiction; the owner approved a bounded correction and
status amendment. The complete-state checkpoint passed, and G4/G5 passed; verification is
recorded in [the coordinated record](u11-u19.md). The sections below preserve the
original diagnosis rather than describing an outstanding permission request.

The U17 task card requires complete, bounded-partial and authority-blocked
end-to-end fixtures. Honest partial and authority-blocked packages are implemented.
At diagnosis, a COMPLETE package could not be produced merely by improving the
synthetic source data. The authorized resolution below now passes its checkpoint.

## Reproduction by the original production rules

1. `reconcile.py` requires all nine G3 predicates for each of the eight systems.
   An absent predicate creates an unresolved fact and gap.
2. A supplied `exception_claim` is unconditionally unusable until an authorized
   Legal decision is verified. Stage 04 has no verification branch for that
   decision. Consequently, supplying or omitting this required predicate both
   leave an unresolved gap.
3. Every linked report receives an unresolved `report-review` gap, regardless
   of accepted assessments. Linked-report identity is mandatory for verified
   facts, so avoiding reports cannot establish complete evidence.
4. The G3 report-accounting schema requires a non-null `gap_id`; merely removing
   the unconditional gap in Python would violate that accepted contract.
5. Any Stage 04 gap yields partial status. Downstream reduction correctly retains
   it; changing only the final status would falsify the package.

## Why a routine fixture repair is insufficient

The frozen [G3 fact contract](../../regulatory-change-impact-brief/references/g3-fact-and-impact-contract.md)
uses Boolean/null values for five predicates, but text/null for exception claims.
Boolean `exception_claim=False` is not currently an authorized representation of
absence. A text sentinel such as “no exception” would also introduce new reviewed
meaning; it cannot silently establish exemption approval.

Counting nine submitted candidates would not establish report completeness.
Resolution must account for actual supported assertions, each report's own
identity/evidence/date/scope, contradictions and unassessed meanings. The current
packet has no explicit reviewed declaration that all report scopes were covered.

## Original decision request

Either preserve G3 and retain this U17 criterion as explicitly blocked, or approve
preparation of a concrete contract amendment for review. An amendment would need
to define absence of a claimed exception separately from approval of an exception,
define report-assessment completeness, update report accounting, and add positive
and negative regression cases. Existing textual claims, unknown facts, stale
roles, conflicts and unauthenticated approvals must remain unresolved.

Affected files would include G3/reconciliation/impact references, the reconciliation
accounting schema, `reconcile.py`, `impacts.py` and focused U10/U17 tests. The public
snapshot schema and G1 graph contracts need not change. This remains a material
accepted-boundary decision, not authorization inferred from a test requirement.

The owner was asked before changing these rules. Other U11–U19 implementation and
verification continued independently. No forged COMPLETE fixture, suppressed
assertion, gate waiver or U20 audit was used to bypass the contradiction.

## Authorized resolution

The correction preserves text/null exception claims: only an evidence-backed
exact `No exception claimed` value with the explicit `none-claimed` disposition
records absence of a claim. Actual claims remain subject to authenticated Legal
approval. Explicit own-report completeness declarations and all supported scoped
predicates may resolve the report review gap. Unknown, conflicting, unsupported
or incomplete assessments do not qualify.

A separately approved ledger resolves only the exact pending report inspections
and the AMEND/CONSOLIDATED inspections verified by U09. Earlier snapshots and
diagnostics stay unchanged. Stage 07 and retained review validation independently
reconstruct this ledger before accepting an improved aggregate status. See
[the bounded amendment](report-resolution-proposal.md) for the precise scope.
