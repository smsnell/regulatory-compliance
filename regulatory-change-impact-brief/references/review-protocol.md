# Review requests and authenticated feedback

Stage 06 prepares requests with a unique request ID, exact subject IDs and system
scope, run and draft version, source versions, evidence, question and reviewer
role. Every prepared request has `delivery_status: not-sent` and an empty delivery
evidence list. Drafting continues while review is pending. Preparing a request
does not deliver it; this runtime performs no external sending.

Stage 07 supplies detached bindings to the exact bytes of `impact-register.csv`,
`compliance-brief.md` and `action-calendar.ics`. Feedback claims must identify that
request, reviewed subjects, reviewed run/version, source versions, all three
artifact paths and hashes, response time, identity, role, outcome, reasons and
conditions. A response must follow publication of the reviewed draft and precede
the current intake time.

## Trusted identity boundary

Feedback files are untrusted. Fields such as `authentication: verified`, a typed
role, or a claimed identity provide no identity proof. Supply authorization policy
and authenticated operator/channel context separately to the intake API. The
caller must obtain that context through its trusted operator session or a channel
that authenticates the responder; merely copying claims from the feedback file
into the context defeats this boundary.

`ReviewerPolicy.from_dict` accepts:

```json
{"reviewers":[{"identity":"legal@example.test","roles":["Legal"],"channels":["authenticated-operator"],"system_ids":["S1"]}]}
```

`AuthenticationContext.from_dict` accepts separately authenticated input:

```json
{"identity":"legal@example.test","channel":"authenticated-operator","basis":"verified operator session and retained identity proof reference"}
```

Identity, configured channel, authorized role and complete subject system scope
must agree. Policy identities must be unambiguous. Authentication evidence is
retained in `authentication_basis`. A verified identity can still have unresolved
feedback when its version or subject claims fail.

## Older drafts and conditions

`process_feedback(store, requests, actions, inputs, policy=..., authentication=...,
carry_forward=True)` verifies the retained seven-snapshot chain, reviewed request,
detached binding and final artifact bytes in `history/<reviewed-run>`. Payloads
include a `reviewed_draft` pointer containing exact Stage 06 and 07 snapshot IDs,
paths and hashes. Missing archives, wrong hashes, ambiguous subjects, wrong roles,
wrong source versions and malformed claims are preserved as unresolved feedback
with no resolved request or subjects.

Carry-forward requires the caller's explicit `carry_forward=True`. The runtime
remaps subjects by exact semantic identity and compares their relevant graph
content, dates, rule basis and evidence hashes. Source versions and system scope
must remain exactly unchanged. Run-local record IDs and retained evidence paths
can differ when the relevant content is unchanged. The feedback record retains
the prior claims and reviewed snapshot pointers alongside current request,
subject correspondence, upstream snapshot hashes and four evidence-backed
revalidation checks. Its evidence IDs must be consumed by Stage 06.

Without explicit revalidation, feedback remains evidence about the older draft.
Changed facts, source content, dates, rule basis or scope require another review.
No approval transfers automatically.

`approval_for_feedback` yields pending when feedback is absent or unresolved,
rejected for an authenticated matching rejection, and approved only for a matching
approval whose conditions are satisfied. Conditional feedback requires actual
conditions. Supply `ConditionResolution(conditions, evidence_ids, satisfied)` as
separately trusted input; the conditions must match exactly, with current evidence
for satisfaction. Unsatisfied conditions remain attached to matched feedback and
the approval stays pending. An approval outcome that includes conditions follows
the same rule.

Feedback updates draft decisions. The matcher does not modify source policy,
existing approved dates, incidents, delivery state or action contents.

## APIs and verification

`create_review_request` builds a contract-valid unsent request.
`match_feedback` provides a pure matcher for explicit verified fixtures; its
request/binding/index inputs must already be trusted and verified.
`process_feedback` supplies disk-backed verification for production intake.
`approval_for_feedback` builds a contract-valid per-subject decision record.

`tests/runtime/test_u13.py` covers request fields, unsent and unanswered requests,
authenticated binding-to-new-run decisions, identity/channel/scope mismatch,
wrong request/subject/run/version/hash, response boundaries, explicit carry-forward,
changed relevant basis, rejection and conditional resolution.
