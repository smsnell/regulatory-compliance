# Proposed completion-state amendment for fully assessed reports

Status: approved and implemented. The complete-state, negative guard, archived
review and forged-ledger checkpoint passed 27 checks; broader gate outcomes are
recorded in [the coordinated verification record](u11-u19.md).
The owner separately approved the narrow U10 exception/report-gap correction,
the bounded status amendment, and the two AMEND/CONSOLIDATED verified-source cases.

## Remaining contradiction

U08 creates a capture diagnostic for every linked report. U07 derives Stage 02
partial from any such diagnostic; U09 and U10 carry that status forward, and Stage
07 independently reduces all earlier statuses. Linked reports are the required
basis for verified G3 facts. Consequently even a complete, supported assessment
of every report cannot produce a COMPLETE run under the current propagation rule.

The narrow U10 correction can resolve its own exception/report-review gaps. It
cannot remove or rewrite the immutable Stage 02 diagnostic, nor silently redefine
what an inherited partial status means.

## Proposed bounded change

Retain the original Stage 02/03 snapshots and their actual partial statuses.
Allow Stage 04 and final publication to account for a specifically resolved pending
report-inspection issue, using an explicit ledger of the exact original diagnostic
IDs and each report's validated completeness assessment.

The exception to raw status reduction would apply only when all of these hold:

- Every affected report has retained readable bytes, exact system/scope/date
  support, explicit completeness evidence, and supported assessment coverage.
- Every capture diagnostic contributing to the inherited partial status is the
  known pending-inspection diagnostic for one of those fully assessed reports.
- No missing, failed, unverified identity, stale, malformed, contradictory or
  unassessed input remains; unsupported transport/identity must not be relabelled
  as a pending semantic inspection merely to qualify.
- Stage 03 has established authority and timing with no unresolved authority
  blocker. Blocked and failed outcomes can never be improved by this exception.
- Stage 04–06 have no other unresolved issues. Pending human approval remains
  pending and does not become an approval or completed operational action.
- Stage 07 independently reconstructs the resolution from retained bytes and
  exact IDs. It does not trust a success flag or a declared final status.

If these conditions cannot be established using the existing evidence, the run
remains partial/blocked. All original diagnostics remain visible with explicit
resolution links. No earlier snapshot is rewritten. Public schema/enums, snapshot
hash chaining, source read boundaries and human authority stay unchanged.

## Expected implementation and acceptance

Affected components: U10 report-resolution accounting/reference, the bounded
status calculation used by reconciliation and Stage 07, and focused tests.
No acquisition subsystem, automatic recovery mechanism or external service is
added. Before implementation, confirm that the existing report identity evidence
can satisfy the guard; otherwise stop rather than pretend the amendment suffices.

Required positives: an eight-system fully assessed synthetic package reaches
COMPLETE, with seven valid immutable snapshots, three consistent artifacts and
pending human decisions. Required negatives: incomplete declaration, missing
predicate/scope, unverified identity/date, conflict, unsupported report, any other
source diagnostic, authority blocker and technical corruption cannot qualify.
Existing partial/blocked G4 cases, feedback bindings and G5 recovery must continue
to validate. The original early-stage partial diagnostics remain inspectable.

## Implementation audit: exact additional boundary

The owner approved the bounded status amendment. Auditing all relevant reducers
and an eight-system source fixture then isolated exactly 18 unavoidable pending
inspection diagnostics: eight readable report transport/identity inspections,
eight report semantic inspections, and two formal-document inspections for AMEND
and CONSOLIDATED. All avoidable source/normalization errors were removed from the
fixture; the source check retains 24 valid register rows.

Report transport may qualify only through its own accepted G3 report identity,
date and complete scoped assessment plus readable retained bytes. A generic
unverified/unsupported source cannot qualify by diagnostic wording alone.

The additional decision concerns AMEND and CONSOLIDATED only: the read adapter
always marks their identity/version/relevance unverified, even when exact selectors
are present. U09 separately validates captured identity, version, publication and
relationship support. To make COMPLETE reachable, allow those two exact pending
inspection diagnostics to resolve only when U09 has validated their explicit
source assessments and no authority blocker remains. An unrelated amendment must
stay excluded from substantive support; source identity resolution never supplies
an obligation. Missing/wrong/uncertain source assessments remain partial/blocked.

The approved status rule also has to replace the two raw reduction checks in
`snapshots.py` (current Stage07 and retained reviewed drafts), using the same strict
resolution predicate. That is enforcement of the approved status exception;
record IDs, source hashes, predecessor chains, review bindings, public schema and
all other snapshot checks remain unchanged. A later validator must reconstruct
resolution, never accept a forged resolution flag or omitted diagnostic.

The owner approved these two additional verified-source cases before implementation.
The report-only scope was insufficient even with every report fully assessed.
The retained proposal documents why each approval was necessary; it is not an
outstanding permission request.

## Frozen-boundary hash record

Only two aggregate-status guards in `scripts/rci/snapshots.py` changed under the
explicit approval. Their independent reconstruction preserves other graph/hash
checks. Original SHA-256:
`35052f18b4dce2dc9c728f32ddbdd62d74e63d0055b21290bafaff8679733510`.
Approved amended SHA-256:
`a9b14e8ebed869dbdc4cc0952ed36eba1468bb28246559f09be7e28f2b7ff2e0`.
The U09/U10 tests pin the amended exact bytes; the old fingerprint failure remains
retained as evidence. Public `snapshot.schema.json` and internal
`contracts.schema.json` hashes remain unchanged, as do requirements and interview
bytes. Earlier gate records retain their original hashes.
