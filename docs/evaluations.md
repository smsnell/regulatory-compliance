# Canonical implementation evaluations through U19

Run from the repository root with pinned dependencies and `PYTHONDONTWRITEBYTECODE=1`.
For large runs, set `TMPDIR` to an existing directory on a filesystem with sufficient
space; use a unique `--basetemp` for each retained verification run. Pytest's explicit
basetemp can delete an existing directory, so never point it at retained evidence.
Two U05 checks deliberately require temporary files outside the implementation
repository; run those with an external basetemp. Its local HTTP-server test also
requires permission to bind a loopback socket. Those environment conditions must
be supplied, rather than weakening the assertions.

| Case | Entry point | Expected result |
|---|---|---|
| Four-state scoped impacts | `tests/runtime/test_u11.py` | Supported true/false require rule and scoped fact support; unknown/conflict and blocked legal coverage survive. |
| Action/date identity | `tests/runtime/test_u12.py` | Exact task match retains source date separately, ambiguity stays unresolved, source status never grants approval. |
| Authenticated feedback | `tests/runtime/test_u13.py` | Exact identity/channel/request/subject/version/artifact checks; changed basis and absent proof quarantine feedback. |
| Output formats and corruption | `tests/runtime/test_u14_u16.py`, `test_u17_artifacts.py`, `test_source_resolution_export.py` | UTF-8/formula-safe CSV; scoped cited brief; tentative all-day RFC 5545 events; unsupported claims and discrepancies rejected. |
| Seven-stage launcher integration | `tests/runtime/test_u17.py` | Real helper subprocesses with deterministic host responses produce seven snapshots and three consistent artifacts; truncated hosts fail. Includes conflict and unavailable authority. |
| Fully assessed COMPLETE package | `tests/runtime/test_u17_complete.py`, `test_u10_resolution.py` | All eight systems fully assessed; original partial snapshots retained, exact resolution independently reconstructed; incomplete or unsupported assessments stay unresolved. |
| Changed source and recovery | `tests/runtime/test_g5.py` | New IDs/attempts, source change at Stage 02, prior bytes preserved, corrupt current inspected and fresh rerun repairs. |
| Storage and interrupted replacement | `tests/runtime/test_u18.py` | Archive/write/marker failures preserve available evidence; mixed output rejected; second writer rejected. |
| Optimization integrity | `tests/runtime/test_validation_cache.py` | Changed values/schema bytes/file inventories invalidate successful checks; failure never cached as success. |

The deterministic host callback in `tests/integration/pipeline_harness.py` invokes
the copied helper through the public launcher. It proves orchestration and failure
handling, not actual model interpretation. It never adds fixture switches to the CLI.

For the actual configured invoking model, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/integration/u19_host.py --output .evidence/operator-host-evaluation
```

This substitutes only synthetic source transport. The public launcher invokes the
real Codex host, which reads the skill and submits authority, reconciliation and
(when supported rules exist) impact packets. No interpretation is manually copied
between commands. Host login must work. The selected model is the example config's
`gpt-6.1-sol`, high effort; no alternate-model comparison is claimed. Inspect exact
prompts, responses, usage records and validation. A host exit of zero is not package
success. Synthetic input establishes no live company fact, law or approval.

The eight-system scope is frozen. The representative AI-007 trace is inspected
first within that package, followed by all eight members; a separate one-system
production scope would violate the accepted scope schema.

See [the coordinated verification record](verification/u11-u19.md) for actual
results and limitations. These evaluations prepare U20; they do not perform final
independent requirement closure.
