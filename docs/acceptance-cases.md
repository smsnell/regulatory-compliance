# Initial acceptance oracles — U01

These are test/inspection specifications only. No runtime fixture or production
workflow has been implemented or executed. T01–T23 retain the plan's scenario
identities; T24–T32 supplement format, leaf coverage and documentary acceptance.
All synthetic IDs, rule predicates and reviewer identities in future fixtures must
be clearly test-only; none is a claimed live system ID or legal determination.

Each matrix leaf is an individual subassertion within its linked case: use its
exact clause and context to check the relevant value/predicate, including each
listed enum/property/path separately. The case-level result alone never closes
all leaves. Record exact command/input, expected/observed result, evidence path,
verifier and versions per leaf at the owning unit, then reconcile at U20.
Acceptance owner means implementation/verification responsibility, not authority
to approve a legal or operational decision. A/I are not applicable in U01.
Conversational/non-normative matrix rows have explicit exclusion reasons and no
business acceptance obligations. The fixed, source-reviewed
[interview inventory](verification/interview-meaning-inventory.csv) accounts for
each meaning, repeated assertion, source reference and conversational segment.
Structural coverage against that inventory does not substitute for inspecting
the meaning, governing context and suitability of each linked acceptance case.

Source: [plan §9](../TECHNICAL-DESIGN-AND-IMPLEMENTATION-PLAN.md),
[requirements](../REQUIREMENTS.md), [interview](../interviews/interview-B-3.md),
[contracts](../references/contracts.md), [matrix](requirements-traceability.csv).

<a id="t01"></a>

## T01 — Supported eight-system draft

Owner: U07/U11/U12/U17/U20; implementation verifier. Status: not-demonstrated.

Stimulus: Use eight explicitly synthetic systems and verified test rule/fact predicates; omit reviewer feedback.

Expected records: Seven same-run snapshots; complete run, validated draft, full pair coverage; pending approvals and not-sent requests.

Independent observation: Parse all three files and compare IDs, evidence, scope, dates, audience and statuses to Stage 06; never assert live compliance.

<a id="t02"></a>

## T02 — Authority unavailable or unsuitable

Owner: U05/U09/U17; implementation verifier. Status: not-demonstrated.

Stimulus: Separately inject no response, wrong act and login HTML for required legal authority.

Expected records: Every attempt retained; null content/hash/path only for no content; wrong pages retained with identity issue; authority blocker and dependent chain.

Independent observation: Run/publication blocked; CSV/brief name affected scope; no dependent supported legal conclusion; ICS empty or independently supportable proposals only.

<a id="t03"></a>

## T03 — Company evidence gap and deferral

Owner: U10/U11/U17; implementation verifier. Status: not-demonstrated.

Stimulus: Remove one factual predicate for one system; also run a variant where no meaningful analysis remains.

Expected records: Gap with source basis, reason, known owner and resolution need; unresolved pair; first variant partial with unaffected supported pairs, second explicitly deferred/blocked.

Independent observation: Consistent limitation/run status in CSV/brief/calendar; missing evidence gives neither supported-impact nor supported-no-impact.

<a id="t04"></a>

## T04 — Owner/capture contradiction

Owner: U08/U10/U15; implementation verifier. Status: not-demonstrated.

Stimulus: Provide an owner statement that notice exists and a page capture contradicting it.

Expected records: Retain both values/captures/locators; conflicting fact/impact; owner correction and authorized interpretation requests.

Independent observation: CSV and brief expose both bases and resolution need; no latest-row-wins or automatic resolution.

<a id="t05"></a>

## T05 — Source status is not approval

Owner: U06/U10/U12/U13; implementation verifier. Status: not-demonstrated.

Stimulus: Exercise EVIDENCE complete/partial/conflicting and each CALENDAR planned/open/blocked/scheduled/closed label with no decision.

Expected records: Keep native labels; complete means supplied only, partial missing verification, conflicting contradiction; no label grants approval/completion.

Independent observation: Pending/unresolved state remains visible; never claim compliant, approved or completed solely from these labels.

<a id="t06"></a>

## T06 — Disclosure and provenance differ

Owner: U06/U10/U11; implementation verifier. Status: not-demonstrated.

Stimulus: Supply visible AI label evidence but no machine-readable export provenance evidence.

Expected records: Separate notice and provenance predicates; supported notice scope only where rule/facts support it; provenance unresolved.

Independent observation: CSV/brief distinguish findings and evidence; no visible-label-to-provenance conversion.

<a id="t07"></a>

## T07 — Benign input transformation

Owner: U06/U11/U12; implementation verifier. Status: not-demonstrated.

Stimulus: Independently reorder rows and headers and add an unrelated column to the same semantic input.

Expected records: Preserve source IDs, semantic fields and stable impact/action IDs; retained raw locators track the new positions.

Independent observation: Semantic draft values and action UIDs unchanged except run/retrieval metadata; compare parsed records, not full byte equality.

<a id="t08"></a>

## T08 — Unknown mapping or identity

Owner: U06/U10; implementation verifier. Status: not-demonstrated.

Stimulus: Inject missing/duplicated required headers, unestablished rename, changed meaning, invalid values and colliding IDs separately.

Expected records: Explicit mapping/value/identity issues with original values/locators; no guessed alias or fuzzy identity join.

Independent observation: Affected scopes unresolved/blocked as justified; no unsupported formal claim; independent source inspection establishes any accepted mapping.

<a id="t09"></a>

## T09 — Newer source and date precision

Owner: U06/U09; implementation verifier. Status: not-demonstrated.

Stimulus: Capture legitimate post-review revision; include unknown intraday boundary and a historically adequate version variant. Repeat date checks in complete, partial and blocked drafts, including supported records with no conflict or gap.

Expected records: Retrieval, revision, effective interval and observation distinct; as_of midnight encoding plus date precision; applicability adequate or unresolved by evidence.

Independent observation: Assigned date remains 2026-08-26 in Stage 01, Stage 06 and all final artifacts regardless of disposition. Retrieval time, revision, effective interval and factual observation stay distinct, also for supported records. Scope as_of is 2026-08-26T00:00:00Z with date precision, not an asserted legal cutover instant. Newer syntax accepted; no automatic staleness or invented historical fact/timezone.

<a id="t10"></a>

## T10 — No dated proposals

Owner: U12/U16; implementation verifier. Status: not-demonstrated.

Stimulus: Provide supportable actions with no supported dates and a variant with no actions.

Expected records: Undated actions with reason/resolution need, no guessed deadline.

Independent observation: Independent parser accepts VCALENDAR with VERSION/PRODID and zero VEVENT; CSV/brief explain undated actions.

<a id="t11"></a>

## T11 — Action matching and dates

Owner: U12; implementation verifier. Status: not-demonstrated.

Stimulus: Use exact existing action, ambiguous duplicate, different rule bases, contradictory dates and changed proposed date variants.

Expected records: Same unchanged business action keeps ID; ambiguity retained; no lost obligation; existing source/approved date separate from proposed date and basis.

Independent observation: One CSV row per impact even with multiple actions; brief lists action details; dated proposals match Stage 06 without source deadline modification.

<a id="t12"></a>

## T12 — Invalid reviewer feedback

Owner: U13/U17; implementation verifier. Status: not-demonstrated.

Stimulus: Vary request, subject, source version, run/draft, artifact hash, identity proof and role one at a time.

Expected records: Retain responder/time/outcome/reasons/conditions; unmatched or unauthenticated feedback unresolved; no approval transition.

Independent observation: Requests remain not-sent absent delivery evidence; exact draft bindings independently rehashed; no simulated response.

<a id="t13"></a>

## T13 — Authenticated conditional decision

Owner: U13/U17/U18; implementation verifier. Status: not-demonstrated.

Stimulus: Provide trusted identity/channel evidence and exact request/subject/version/hash match; vary conditions and later source/draft meaning.

Expected records: Only matching subject affected in new run; reasons/conditions retained; rejected outcome distinct; changed basis revalidated and pending when no longer authorized.

Independent observation: All drafts reflect the same permitted result; old feedback remains bound to old draft and never approves changed content automatically.

<a id="t14"></a>

## T14 — Artifact corruption

Owner: U17; implementation verifier. Status: not-demonstrated.

Stimulus: After valid rendering change CSV date, ICS UID, brief claim or requested decision separately; also change an artifact hash.

Expected records: Independent disk validator records exact mismatch/failure; no accepted publication.

Independent observation: Re-read actual files and compare against Stage 06 and exact Stage 07 hashes; renderer success objects cannot mask corruption.

<a id="t15"></a>

## T15 — Current integrity and fresh repair

Owner: U17/U18; implementation verifier. Status: not-demonstrated.

Stimulus: With unchanged source inputs remove capture, corrupt snapshot/predecessor or remove/stale a final file.

Expected records: Detect actual missing/damaged/stale relationships, run IDs and hashes; retain failed occurrence and available bytes; identify recovery owner/action.

Independent observation: Fresh documented command with new IDs and required source attempts regenerates/revalidates package; cached success cannot pass.

<a id="t16"></a>

## T16 — History and supersession

Owner: U07/U18; implementation verifier. Status: not-demonstrated.

Stimulus: Run twice with a changed input and then retry recovery.

Expected records: New run/snapshot IDs each time; explicit supersedes/reason; exact available prior bytes archived; missing/corrupt prior evidence inventoried honestly.

Independent observation: Resolve every historical path against archive root, compare byte hashes, reject cross-run predecessor; no invented archived file.

<a id="t17"></a>

## T17 — Replacement and storage failure

Owner: U04/U18; implementation verifier. Status: not-demonstrated.

Stimulus: Inject archive failure, marker write failure, interrupted copy, representative disk write failure, unknown prior run ID and second writer.

Expected records: Stop before overwrite if archive/marker unavailable; retain candidate/archive/marker/current occurrence where available; unknown prior ID preserves current; second writer rejected.

Independent observation: Incomplete marker wins over completion; no mixed-run acceptance; fresh run repairs; report surviving-storage limits; no unrelated files deleted.

<a id="t18"></a>

## T18 — Hostile instructions and read-only boundary

Owner: U05/U08/U19; implementation verifier. Status: not-demonstrated.

Stimulus: Captured source asks to send message, change register, reveal credentials or import into production calendar.

Expected records: Treat text as data; retain provenance without granting authority; tool profile/adapters expose permitted reads only.

Independent observation: Inspect operation log and public artifacts for no secret disclosure, mutations, deliveries, activation, approved deadline change or incident closure.

<a id="t19"></a>

## T19 — Scope unavailable

Owner: U07; implementation verifier. Status: not-demonstrated.

Stimulus: No established IDs; SYSTEMS discovery unavailable or ambiguous.

Expected records: Journal before dispatch, retain actual bytes/diagnostic and missing stage inventory; no fabricated ID or predecessor.

Independent observation: Explicit incomplete preflight; no claimed seven-snapshot or R1/R2 package acceptance; retry has new run ID.

<a id="t20"></a>

## T20 — Authority priority and exception

Owner: U09/U12/U13; implementation verifier. Status: not-demonstrated.

Stimulus: Guidance/timeline conflicts with captured binding timing or an exception lacks authorized Legal approval.

Expected records: Distinct legal/policy/guidance bases and versions; conflict/blocker retained; Legal request with evidence.

Independent observation: No FAQ/TIME/newest-URL override, invented legal deadline or exception approval; dependent conclusions withheld.

<a id="t21"></a>

## T21 — Host and reproduction

Owner: U03/U19/U20; implementation verifier. Status: not-demonstrated.

Stimulus: Clean environment invokes the documented command; variants: unavailable/auth-failed/truncated host and exit zero with missing/old outputs.

Expected records: Record runtime/dependencies/setup, host profile/version, permitted credential references, exchange and current run; explicit failure/incomplete variants.

Independent observation: One command regenerates package without manual interpretation transfer or separate project API key; inspect actual new files/fresh attempts; old package/host text cannot pass.

<a id="t22"></a>

## T22 — Interpretation binding

Owner: U02/U08; implementation verifier. Status: not-demonstrated.

Stimulus: Inject wrong run/stage, altered packet/upstream/extract hash, invented citation, missing provenance, malformed/truncated/refused response.

Expected records: Reject invalid exchange and retain exact request/response/diagnostics; semantic unsupported/refused candidates unresolved; corrupt exchange fails technically.

Independent observation: No stage advances using bad bindings; captures unchanged; analysis separate from primary sources; inspect actual quote/locator meaning.

<a id="t23"></a>

## T23 — Declared or discovered scope

Owner: U07/U10; implementation verifier. Status: not-demonstrated.

Stimulus: Declared actual scope with fresh missing/additional IDs; separate successful first-run discovery variant.

Expected records: Frozen declared scope with discrepancy; discovery basis has direct capture/attempt provenance, no forward record IDs; Stage 02 imports same attempt once with original time/path/hash.

Independent observation: Eight-system expectation and audience checked; no mutation of hashed Stage 01 or fictitious second read; inspect predecessor exact bytes.

<a id="t24"></a>

## T24 — Public snapshot contract and graph

Owner: U02/U17; implementation verifier. Status: not-demonstrated.

Stimulus: Create seven minimal allowed snapshots and variants with bad enums/date/sequence, duplicate IDs, dangling/current-stage consumption and tampered bytes.

Expected records: Public schema with format checking and stricter record types; meaningful downstream values; immediate same-run predecessor; permitted empty collections only.

Independent observation: Reject every violation; supplied schema hash unchanged; independently resolve graph and evidence paths; artifact record summary/evidence extensions present.

<a id="t25"></a>

## T25 — Attempt inventory and retained representation

Owner: U04/U05/U08; implementation verifier. Status: not-demonstrated.

Stimulus: Exercise all five retrieval states, unused success, bounded retries, linked report, bytes/zero bytes/no response, unknown MIME and permitted extract.

Expected records: Each attempted read has terminal outcome with every R2 field; ten declared sources attempted fresh; linked/retry attempts additional; actual representation/path/hash and locators.

Independent observation: Rehash retained bytes/extracts independently; extract hash never claims uncaptured original; diagnostics not content; no URL/hash-only claim or silent fixture fallback.

<a id="t26"></a>

## T26 — CSV field and format oracle

Owner: U14/U17; implementation verifier. Status: not-demonstrated.

Stimulus: Render Unicode, commas/quotes/newlines, known dates, unknown/inapplicable blanks, semicolon evidence and multiple actions.

Expected records: Frozen export rows preserve distinct legal/policy bases and IDs; unknown blanks retain reason/resolution need.

Independent observation: Parse UTF-8 CSV: header with all eleven required columns, allowed additions, one row per impact/unresolved item, YYYY-MM-DD known dates; documented display escaping round-trips meaning.

<a id="t27"></a>

## T27 — Brief content and human authority

Owner: U12/U15/U17; implementation verifier. Status: not-demonstrated.

Stimulus: Render complete, partial and blocked drafts with gaps, conflicts, undated actions and Legal/Operations questions.

Expected records: Requests contain all subject/run/source/evidence/question/reviewer fields; project decisions contain every R6 field.

Independent observation: Inspect every R4.2 field and impact/action/evidence citation; scoped conclusions; no new renderer claims; detached Stage 07 exact hashes, no self-hash or delivery/approval claim.

<a id="t28"></a>

## T28 — Calendar RFC and matching oracle

Owner: U16/U17; implementation verifier. Status: not-demonstrated.

Stimulus: Render supported date-only proposals with optional end, Unicode/escaping/long lines and stable action across reruns.

Expected records: Action identities, dates, roles, bases, approvals and evidence come from Stage 06.

Independent observation: Independent RFC parser plus raw CRLF/folding checks: VERSION/PRODID, UID/DTSTAMP/DTSTART/SUMMARY/DESCRIPTION; all required description values; tentative, DATE, exclusive end, stable UID, no undated events.

<a id="t29"></a>

## T29 — System facts and authority routing

Owner: U06/U10/U11/U13; implementation verifier. Status: not-demonstrated.

Stimulus: Use different roles/uses/exposed learner/applicant/staff/public groups, generated/modified content, notice at/before first interaction and staff review path; stale roles and unapproved exceptions variants. Vary SYSTEMS yes/no notice labels against matching and contradictory retained captures.

Expected records: Retain actual fields and evidence references; yes/no labels require matching evidence, with contradictions preserved. Verify role per system. Owners supply factual corrections; unresolved factual/operational matters escalate to Operations, and interpretation/exception questions to Legal.

Independent observation: Compare report/capture/export/owner evidence to scoped draft; “mostly deployer” never universal; interview notice statements do not substitute for verified rule authority.

<a id="t30"></a>

## T30 — Dependency change and full recomputation

Owner: U18; implementation verifier. Status: not-demonstrated.

Stimulus: Change scope/config, source/mapping, authority logic, reconciliation, impacts, actions/feedback and rendering/validation separately.

Expected records: Record earliest affected stage 01/02/03/04/05/06/07 respectively and recompute all dependent work; first implementation fully reruns all stages.

Independent observation: Fresh required attempts and new IDs; actual regenerated files revalidated, failures preserved; retrieval times/new IDs alone not substantive changes.

<a id="t31"></a>

## T31 — Required delivery and skill documentation

Owner: U19/U20; implementation verifier. Status: not-demonstrated.

Stimulus: Inspect final repository and reproduce documented setup/evaluation in clean environment.

Expected records: Named Agent Skills package with SKILL.md/scripts/references and invocation/output/status/recovery instructions; dependency/runtime/config records.

Independent observation: Required deliverables tree exists with exact names; source/interview/schema provenance unchanged; canonical evaluations and scan dispositions; live blockers distinct from fixture evidence.

<a id="t32"></a>

## T32 — Design decision audit

Owner: U01/U12/U20; implementation verifier. Status: not-demonstrated.

Stimulus: Inspect every documentary engineering decision and each stage-relevant runtime decision.

Expected records: Unique ID, summary/evidence basis, concern, options, chosen behavior, rationale, tradeoffs and downstream effect; provisional status explicit.

Independent observation: No decision is implied human approval; questions specify conservative behavior/owner/gate; every normative leaf has component, acceptance owner/assertion/evidence type, status and evidence location.
