# Independent U20 review

Verifier: bounded read-only reviewer `/root/u20_review`, 2026-10-10, current
session model. This was not a separate Astra evaluation. The scanner skill's
referenced quality guidelines supplied the instruction to delegate this review.
The reviewer did not edit files or run tests.

| Finding | Final disposition |
|---|---|
| Every live snapshot and the clean-host package have empty runtime decision lists; export and brief contain no engineering decisions. | E04 remains open. Decision-shape tests are not runtime-emission evidence. |
| R0-010 initially inherited a shape-only passing decision assertion. | Changed to not-demonstrated alongside R6-001–008. |
| Candidate initialization precedes the diagnostic handler; setup errors can lose run/candidate context. Archive/feedback failures inherit the capture-stage label. | Reproduced the initial write failure through the launcher. E05 remains open for R9-024–028; operating guidance and amendment claims qualified. |
| Authority notes could imply a validator rejected a positive mapping. | Clarified that the actual host returned `ambiguous` under the literal-date/selector contract. Mapping alone would not establish historical applicability. |
| R2 identity/applicability leaves and R11 successful live regeneration require explicit source exceptions. | Preserved blocked statuses for R2-029–032, R2-035 and R11-008. Documentation inspection and real-host invocation are stated separately from the import/profile tests. |

The reviewer confirmed the source-inspection account of ten label-only report
references, unverified policy content, captured amendment/consolidation identifiers,
and unresolved authority qualification. These are bounded audit observations;
Legal's final interpretation remains outstanding.

## Coverage mapping follow-up

The reviewer checked the proposed leaf/scenario evidence associations. Added
E06 for missing actual category-to-stage mutation coverage (R9-001–002/T30) and
E07 for conditional feedback/date propagation across drafts (INT-082/T13).
G5 still demonstrates fresh source-change recomputation and revalidation.

An initial concern about hostile-source coverage was resolved by the real-host
[inspection](hostile-source-inspection.json): the captured transfer instruction
was read and explicitly rejected; all 12 completed reconciliation commands were
local reads/checks, an analysis write and a helper submission. The earlier unit
profile/escaping checks alone would not have established this result.

The previously omitted two-run feedback integration test demonstrates ordinary
scoped Legal approval and invalid-binding quarantine. It does not close E07's
conditional-outcome/date-change propagation requirement.
