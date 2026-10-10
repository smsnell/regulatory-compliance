# Implementation experiment: unit decomposition and coordinated execution

## Original hypothesis

This project was deliberately decomposed into approximately twenty independently
implementable, testable units, with major verification gates. The hypothesis was
that less expensive models could do straightforward work while stronger reasoning
handled architecture and difficult semantics. Smaller session contexts, stable
contracts, and early detection at unit boundaries were expected to reduce total
token consumption and potentially implementation time and downstream rework.

## Initial execution strategy

Astra handled architectural planning; Sol and Luna were assigned bounded
implementation. Independent diff reviews, correction cycles and formal gates
provided checks between units. This was intended to contain local complexity,
make requirements traceable and prevent downstream components from inheriting
unnoticed mistakes.

## Observations through G3

The user reports substantial context reacquisition and coordination between units,
repeated reading of interfaces and related code, costly independent review and
correction cycles, and an approximately 80-minute initial U10 implementation.
That timing is approximate and user-reported, not an instrumented benchmark.
The assessment that orchestration overhead was excessive is qualitative.

Repository verification records supply narrower measured evidence:

- U10's combined run: 256 tests, 2,560.25 seconds, initially 246 passes and ten
  failures; focused corrections and reruns are recorded in `docs/verification/u10.md`.
- G3's unit run: 141 passes in 2,475.70 seconds; other focused gate and prerequisite
  runs are separately documented in `docs/verification/g3.md`.
- At the start of coordinated work, `.evidence` occupied approximately 1.6 GB.
  Its contents include retained test runs and gate evidence, not just disposable
  caches. Session/checkpoint data and earlier evidence were preserved.

Strong contracts, early verification, explicit failure handling and traceability
provided a useful foundation. They also exposed authority, source identity,
conflict and feedback risks before final integration. There are no reliable
aggregate token counts here, so this document makes no token-cost comparison.

## Assessment

By G3 the initial approach had not demonstrated the anticipated reduction in total
implementation time or resource consumption. Smaller implementation tasks may
reduce local complexity while increasing orchestration, context transfer,
verification and integration overhead. Neither this project nor alternative
workflows were evaluated under controlled conditions; this is a qualitative
engineering assessment, not a definitive benchmark or a comparison of developers.

## Revised strategy after G3

The user selected Astra-led orchestration, bounded delegation, coherent phases,
targeted tests and integrated verification. The existing architecture, accepted
stakeholder decisions, frozen schemas and gates remain authoritative. The change
concerns execution: implement related work together, give agents clear file
ownership, test isolated changes locally, and broaden verification at integration
checkpoints. U20 remains a separate independent audit.

The current orchestrator used available delegation tools with explicit Sol high
assignments for impact/action semantics, review authentication and history/recovery.
Observed model allocations are reported; no unobservable underlying orchestrator
model identity or resource savings are asserted. Renderer verification reused the
review agent after its first task, avoiding another context transfer.

## Measurements during coordinated work

A profiled validation of the same retained G3 Stage 04 specimen took 18.28 seconds
before optimization and 7.35 seconds afterward (about 60% lower in this sample).
The profile showed 78 normalization value validations repeatedly checking the
schema itself, consuming 9.11 cumulative profiled seconds. Checked validators are
now reused by exact schema bytes. A bounded structural-success cache reuses checks
on exact JSON values. Disk reads, hashes, evidence quotation checks and graph
validation still run; altered values and changed schema bytes are checked anew.
These elapsed measurements include profiler overhead and are not whole-suite benchmarks.
The retained `.evidence/u11-u19/profiling/` records contain 20.95 million calls
before and 8.55 million afterward; summed profiler times are 18.24 and
7.34 seconds, slightly below the measured elapsed values above.

After this change, 58 contract tests plus 39 subtests passed in 6.21 seconds;
71 G3/normalization cases passed in 98.33 seconds. These are different workloads
from the historical totals and must not be used as a direct speedup comparison.
The first attempted full G3 profile was interrupted before completion; it is not
counted as a test pass. An older temporary venv lacked pytest; verification used
the already documented pinned `/tmp/rci-u03-clean` environment.

## Outcome and lessons

Coherent phases made cross-module integration easier to coordinate: the same agents
retained ownership through action/export and feedback/history repairs. That is an
engineering assessment, not a measured time saving. Strong frozen contracts caught
concrete errors: unresolved items omitted from CSV, a missing notice incorrectly
used as exclusion, historical feedback paths mistaken for current dependencies,
retrieval timestamps mistaken for substantive changes, and empty source-version
bindings when all formal rules were withheld.

Overhead remained substantial. Broad tests still reconstruct many evidence graphs;
real invoking-host evaluations reread skill and retained inputs. Four earlier host
evaluations failed or were interrupted during environment/integration repair; their
logs and candidates remain preserved. One G5 run detected implementation changes
made while the test was running (earliest changed stage 5), correctly invalidating
its unchanged-input assertion. Its 710.96-second combined run is not counted as a
passing gate. Final integration was moved to a fixed source copy. An overlapping
expanded unit run was stopped once existing and focused regression results covered
its changes; its partial output is not reported as a pass.

The temporary filesystem filled. Confirmed bytecode caches were removed, while
test evidence was relocated with hash verification into retained repository storage.
Future work should establish disk capacity and immutable verification source copies
before lengthy runs, use focused change-based tests, and give complete-state
acceptance fixtures attention when freezing early contracts.

A complete-state fixture exposed an accepted-contract contradiction: U10 always
created exception and report-review gaps, while early source inspection diagnostics
kept partial status forever. The owner approved narrow evidence-backed resolution
rules and a bounded aggregate-status amendment, including two exact formal-source
inspection cases. Earlier snapshots and diagnostics remain immutable; final
validation independently reconstructs the resolution. This required architectural
reasoning and explicit authorization despite the consolidated execution strategy.
It reinforces the value of testing genuinely complete scenarios before freezing
status propagation contracts. The final complete-state checkpoint passed 27 checks, including archived review,
forged-resolution rejection and output consistency. The eight-system package keeps
its original partial capture snapshots while its independently validated final
status is complete. Approval requests remain unsent and human decisions pending.
The final G4/G5, feedback and artifact checkpoint passed 86 tests in 893.42 seconds.
G4 and G5 passed; U11–U19 are ready for the separate U20 audit. The slowest final
cases remained multi-run verification: G5 took 273.17 seconds and authenticated
feedback took 261.85 seconds, including setup. Repeated complete evidence-graph
validation still dominates those cases despite the measured local schema savings.
Detailed evidence is recorded in the coordinated verification record.

The successful real-host evaluation recorded 686291 input tokens
(including 599680 cached input tokens), 7328 output tokens and
1154 reasoning output tokens across 2 completed host stages. These are
host-reported categories, not unique context size, billed cost or the total project
usage; categories should not be added together as independent consumption. The
per-stage logs and summary are retained.

There is no reliable aggregate project token total or controlled comparison. The observed
strategy change has not established a numerical reduction in total time or resource
consumption. Final gate/host outcomes are recorded in `docs/verification/u11-u19.md`.
U20's independent audit, live acceptance and final requirement closure remain outside
this work. The results do not establish that one model allocation is universally better.
