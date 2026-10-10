# G3 fact and disposition contract

G3 freezes this boundary for U11; U10 implements no impact engine. Authority is
[U09's Stage 03](../../docs/u09-authority.md), facts are
[U10's Stage 04](../../docs/u10-reconciliation.md). Public/G1 enums and graph
contracts remain unchanged. References: plan §3.3–3.5 and U10/G3; R10/R13;
interview 03:16/03:20 and 04:35–04:46.

## Factual predicates and scope

`reported.<field>` facts establish captured register assertions only. Their
values, including null role tokens, labels, dates, owners and notes, never supply
verified predicates. Incident details and calendar context retain operational
bases separately. Every original row has accounting even if normalization fails.

Verified predicates are `notice_present`, `notice_before_first_interaction`,
`machine_readable_provenance`, `provider_role`, `deployer_role`, `output_scope`,
`exposed_group`, `human_review_path`, and `exception_claim`. The first five take
boolean/null values; output/group/review/exception descriptions take text/null.
The interpretation must identify an exact system and output/interaction scope.
Scope is an exact captured string, not a token to expand to other audiences.

| Predicate | Affirmative meaning in the stated system/scope |
|---|---|
| `notice_present` | A notice exists; this alone establishes neither its timing nor provenance. |
| `notice_before_first_interaction` | A notice is supplied before **or at** the first interaction, as specified in interview 04:38; the field name does not exclude notice at first interaction. |
| `machine_readable_provenance` | Export-test evidence establishes machine-readable provenance for that output. A visible label alone is insufficient. |
| `provider_role`, `deployer_role` | The respective role is affirmatively supported and current for the scoped activity. Evaluate each independently; neither is a default or the negation of the other. |
| `output_scope` | Captured description of the actual generated/modified output. |
| `exposed_group` | Captured description of the people exposed to the specified interaction/output. |
| `human_review_path` | Captured description of staff verification before delivery in that scope; the description alone does not establish compliance with a rule. |
| `exception_claim` | A retained claimed exception, unresolved until an authorized Legal decision is verified. |

False means evidence affirmatively supports the absence of the named boolean
property; null means unknown. These meanings require inspection of the captured
paragraph, including negation and qualifiers. Predicate names do not create law.

A fact with non-null `value` carries `scope`, `resolved_value`, and every original
assertion with value, evidence, source basis, origin, owner, observation date,
retrieval time, usability and reason. `resolved_value` exists only for supported
agreement. A missing predicate has null `value` and unresolved state. Scope
metadata is also enumerated in `u10_reconciliation.fact_groups`.

Group key is `(system_id, predicate, scope)`. Compare actual typed values using
canonical JSON: false differs from null. Different scopes are separate facts.
Two distinct non-null assertions produce conflicting state even when one is
stale/unusable; retain unknowns alongside the contradiction. One distinct value
plus an unusable/unknown assertion remains unresolved. Equal supported values
can agree, but all occurrences/evidence survive. Duplicate native identities,
cross-system identity claims and control version disagreements remain separate
issues. There is no date/row priority, fuzzy identity join or universal role.

Support requires linked report identity, field/scope/value quotations and explicit
suitability on the assigned date; schema/quote checks are binding checks only.
Machine-readable provenance requires export-test evidence. Notice timing needs
capture/interaction evidence. Source-reported stale roles and unapproved exceptions
stay unresolved. Final role interpretation and exceptions remain Legal decisions.
Any new predicate or scope interpretation is a U11 escalation trigger, not a
convenience extension to this frozen contract.

## Four-state disposition truth table

U11 must retain a coverage entry for every scoped system and candidate rule basis,
including withheld/unsupported bases. Legal and policy bases remain distinct.
Rule predicates/roles/exception conditions retain U09's exact captured meanings;
U11 must not invent a mapping from arbitrary rule prose to a field. An unbound
predicate remains unknown. `reported.*` never satisfies an affirmative predicate.
Only facts in the matching system/field/scope may supply a predicate.

| Established scoped rule/timing | Necessary fact/exception state | Evidence-backed impact predicate | Disposition |
|---|---|---|---|
| No / unknown | Any | Any | unresolved; retain authority blocker |
| Yes | At least one relevant contradictory value | Any | conflicting; retain every contradictory basis |
| Yes | No contradiction, at least one necessary unknown | Any | unresolved |
| Yes | All necessary predicates affirmatively supported | True | supported-impact |
| Yes | All necessary predicates affirmatively supported | False | supported-no-impact |

The impact predicate is the specific reviewed rule/change condition, not a
universal compliance flag. Its true/false semantics need captured rule support.
Supported-no-impact requires affirmative scoped exclusion/non-trigger evidence;
missing notices, unverified provenance or an unapproved exception cannot provide
it. Unknown role, historical suitability, timing or exception decisions propagate
unknown. A material contradiction takes precedence over an unknown within the
same evaluated scope, while absent authority still withholds formal disposition.
Do not transfer a conflict or supported observation to another field, system or
output scope. Preserve all reason/evidence/owner/resolution links in coverage.

Required authority blockers propagate blocked aggregate status. Company gaps or
conflicts propagate partial, unless nothing meaningful remains and later stages
must explicitly defer. Technical corruption is failed. Human review pending is
compatible with a supported draft; it does not authenticate approvals.
An individually blocked rule leaves independently supported rule bases intact;
a shared authority prerequisite failure or disputed source/version assessment
withholds every rule depending on it. Candidate-local predicate/timing uncertainty
does not by itself dispute another fully assessed rule's authority chain.
Competing assessments of the same rule basis require resolution. An active policy
assessment cannot override pending/unknown activation for that same control and
review-date scope. Distinct controls and explicitly future intervals remain
separate; no newest-version priority is implied.
Operations owns confirmation of pending/unknown policy activation. Legal owns
disputed policy meaning/version boundaries; neither a draft control nor a gap
records a new human approval or activation.

Source labels stay distinct: evidence complete is supplied, partial is missing
verification, conflicting is a reported contradiction to investigate. Calendar
planned/open/blocked/scheduled/closed grant neither completion nor approval.
Visible disclosure supplies neither provenance nor notice timing. CALENDAR ALL
is retained shared context and never invents a system-specific row or approved
calendar. Unsupported HTML layout/images/OCR remain unknown.
