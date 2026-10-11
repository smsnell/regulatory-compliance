# Publication-safe evidence remediation — 2026-10-11

> Subsequent owner instruction: preserve the fellowship's Entire session history
> exactly as recorded, including the mistake and its correction, and commit and
> push with Entire synchronization. This explicit instruction supersedes the
> synchronization hold below. The 18 possible-sensitive findings remain recorded;
> authorization to upload does not establish that those historical bytes are
> sanitized. No Entire log, checkpoint, or detection rule is altered for this push.
> The no-commit/no-push statements below describe the completed remediation phase.

This is an owner-authorized **publication derivative**, not a new regulatory
review, live retrieval, host interpretation, or human approval. **The staged
submission is ready for the owner's final commit.** This is separate from the
unchanged **blocked** regulatory draft and the **Entire synchronization hold**.
No commit or push was performed.

## Originals and authority for the transformation

The full pre-transformation index was copied to
`/home/mike/regulatory-compliance-evidence/2026-10-11-publication/`:
**977 indexed files**, including all **332 deliverable files**, verified byte for
byte. Directories are owner-only (0700), files 0600. `preservation.json` records
paths, sizes, original SHA-256 hashes and original index object IDs. This is
restricted local storage, not a remote backup. Original source captures,
journals, snapshots, interpretation envelopes, artifacts and the exact original
history inventory remain available there. No original was edited in that storage.

[R2 source evidence](../../REQUIREMENTS.md) permits actual bytes **or permitted
claim-bearing extracts**. The [provenance contract](../../references/contracts.md)
requires the representation to be identified and its own bytes hashed. The
[existing extract contract](../../regulatory-change-impact-brief/references/contracts.md)
provides primary `extract` representations with method, locator and permission
metadata. The owner explicitly authorized this publication transformation. There
is no requirement here to publish credential-bearing full responses. No schema,
runtime acceptance check, secret rule, allowlist, or hook was relaxed.

The [history contract](../../regulatory-change-impact-brief/references/history-recovery.md)
requires exact originals for actual archive/recovery operations. That original
archive is preserved externally. The directory published at
`deliverables/history/run-f48b4823b3ad4faaa9ac30a301b66505/` is explicitly a
**sanitized history representation**, not a claim that the original archive
inventory still describes its altered bytes. Its derivative inventory is rebuilt
against the derivative files. This is the authorized publication boundary; it
does not amend the production archive contract or establish a fresh execution.

Treat this as a static submission view, not an acquisition cache or a recovery
candidate. Future production work requires fresh attempts in a separate output
root outside the checkout; original-occurrence investigations use the restricted
baseline. Do not reuse a derivative's rebound envelope as an actual host response
to a new run.

## What was transformed

The [deterministic builder/verifier](../../scripts/publication_evidence.py) reuses
the U05 redaction expressions, existing capture representation fields, renderers,
and independent package validators. It builds in a new directory and rejects a
missing or corrupt preserved original. It does not acquire sources or deliver
review requests.

- All **15 flagged captures** are retained at their existing evidence locators as
  explicitly labeled extracts. Twelve retain spreadsheet HTML with **228 Google
  key occurrences** and **12 Maestro field values** redacted. Three WAF pages
  retain their visible challenge/failure content with executable script elements
  removed. No value was used, tested against a service, or printed.
- Extract hashes describe the actual sanitized bytes. `original_sha256` is
  explicitly provenance metadata referring to the restricted original, never the
  extract's `content_hash`. Method, permission, locator and original availability
  are explicit. Unaltered captures and existing visible-text derivatives retain
  their exact bytes.
- Dependent terminal journals, source references, decisions' source bindings,
  interpretation packet/response bindings, snapshot predecessor hashes, draft
  versions, review source versions, artifacts and Stage 07 bindings are rebuilt.
  The historical inventory hashes and sizes are rebuilt too. **58 of 332**
  original deliverable paths are transformed; no required path is omitted.
- Interpretation request/response envelopes with changed hashes are **publication
  derivatives only**. Their quoted extracts and response meanings are unchanged.
  They were not sent back to the host. Original prompts, host event logs,
  invocation metadata and timestamps describe the original inputs. The manifest
  identifies the exact original and derivative envelope hashes.
- Original run, record, snapshot and packet IDs/times are retained solely to
  identify the historical occurrence. The sidecars state `new_execution: false`.
  There is no reuse claim for a new production run, no fabricated retrieval, and
  no newly inferred interpretation. Review requests remain unsent.

The [publication manifest](../../deliverables/publication-manifest.json) accounts
for every original deliverable path and both hashes, plus hashed publication
notices. Each package has `PUBLICATION.md` and `PUBLICATION.json`; the historical
notice explicitly points to the submission-root lineage manifest. Artifact
format remains exactly what the existing semantic validator permits, so these
notices accompany the three draft artifacts and must travel with them.

## Preserved findings and historical records

| Published representation | Attempts | Captures | Unresolved coverage | Actions | Unsent requests | Run/publication |
|---|---:|---:|---:|---:|---:|---|
| Current `run-b38ca2b36e1044bbba572399b41bf5ae` | 22 | 26 | 8 | 0 | 2 | blocked / blocked |
| History `run-f48b4823b3ad4faaa9ac30a301b66505` | 22 | 29 | 56 | 0 | 2 | blocked / blocked |

The current draft retains all four Legal blockers, ten unresolved underlying
report labels, fourteen engineering decisions, source identity/date limitations,
zero supported impacts and zero calendar events. Existing operational calendar
context is not promoted into actions. Neither package gains a completion marker,
human approval, sent request, or an accepted compliance conclusion.

The verifier compares original and derivative visible HTML, returned spreadsheet
identity/tabs/native cells, attempt outcomes/times/selection, normalized rows,
authority blockers, reconciliation and impact findings, unresolved coverage and
interpretation content. It validates both original and derivative packages using
the unchanged on-disk validator, including all seven snapshots, artifact semantics
and review bindings. It verifies every journal and the derivative history inventory.

`analysis/prior-inspection.json`, `stage-fingerprints.json`, `recomputation.json`,
`run-context.json` and `outcome.json` remain exact **original execution records**.
They do not assert current derivative hashes or a new successful execution. The
package notice enumerates those present in each package. A candidate path in the
original outcome identifies the private original candidate; it is not a promise
that `.staging/` is published. Existing ignored local candidates/audit working
data were not promoted into this submission.

The earlier U20 audit, refresh and secret-guard reports remain historical, with
prominent links to this remediation. Their original hashes and candidate-equality
observations apply to the restricted baseline, not the current derivative bytes.
The prior refresh checker checks that original occurrence and must not be used to
claim that the publication derivative is byte-identical to its private candidate.

## Verification and remaining limits

[Lineage/package verification](publication-verification.json) records local
verification with restricted originals, including byte-exact deterministic
regeneration. Public readers can independently verify derivative hashes, journals,
snapshot chains, retained claim text, artifacts and historical inventory using
the published files. **They cannot independently prove the original-to-derivative
transformation without access to the restricted originals.** The explicit verifier
returns a nonzero `LIMITATION` if those originals are absent; a hash or public
package validation alone never establishes full original lineage.

Reproduce locally with the project's pinned environment:

```sh
TMPDIR="$HOME/.cache/rci-secret-scan" PYTHONDONTWRITEBYTECODE=1 \
  /tmp/rci-u03-clean/bin/python scripts/publication_evidence.py verify \
  --originals /home/mike/regulatory-compliance-evidence/2026-10-11-publication \
  --output deliverables
```

The interpreter path above is the existing environment, not a temporary-data
destination. The new verifier and checkpoint scanner explicitly require the
requested cache and do not fall back to `/tmp`. An early sandboxed invocation
despite `TMPDIR` did fall back to `/tmp`; it was stopped, the cause corrected,
and the authoritative checks rerun with cache write access. No unrelated
temporary files were deleted.

Targeted tests: **88 passed, 2 deselected**, 60.75 seconds; see the
[test log](publication-tests.log) and [JUnit report](publication-tests.xml).
The existing derived-capture/packet-lineage contract test also passed (**1 test**,
0.70 seconds; [log](publication-derived-contract.log)), for **89 passed** total.
These cover publication lineage/missing originals, both derivative packages,
artifact tampering, extract/quote provenance, journal integration, normalized
provenance, history preservation and guard safeguards. The two deselected tests
perform disposable commits; no commit was performed here. The complete regression
suite was not run. The [initial hook/full-index scans](publication-security-initial.json)
both rejected only the new JUnit XML: pytest embedded five generated synthetic
credential parameter IDs. The original XML is retained in private cache storage;
the published XML replaces only those five parameter labels with numbered cases.
All results, counts and timings are unchanged. The [report lineage](publication-test-report-lineage.json)
records distinct original/derivative hashes. The corrected report and lineage
record pass the unchanged scanner.

Final [security results](publication-security.json): the actual installed
`.git/hooks/pre-commit` passed (**exit 0**, **218.589 seconds**, **574 changed staged
files**); `python3 scripts/secret_guard.py --all` passed (**exit 0**, **320.097
seconds**, **995 indexed files**). Both emitted zero diagnostics, and the index
was byte-identical before/after both scans. The [hook log](publication-pre-commit.log)
and [full-index log](publication-full-index.log) are consequently empty. Rules,
guard code and hook installation scripts match the preserved baseline.

After adding these results, the four final staged verification-note files were
scanned with the identical guard scan function and configuration: all passed.
Every other staged object ID was checked unchanged from the successful full-index
scan. No package, source, runtime, rule, or test code changed afterward. Scoped
new-code/verification-document whitespace checks passed; historical generated
artifacts and audit logs retain their existing formatting.
Existing credential detection remains enabled, including binary
stdin scanning, decode depth, default rules, Google/private-key rules and inline
allowance rejection. No commit or push is part of this remediation.

## Entire checkpoint boundary

The [read-only checkpoint scanner](../../scripts/check_publication_checkpoints.py)
checks all blobs reachable from local Entire checkpoint refs and the Entire
branch that are not reachable from locally known remote refs, including ancestors.
It uses the unchanged guard scan function, four bounded workers, redacted output
and isolated private temporary directories. It records object IDs, paths and
dispositions only. Remote state is not refreshed and synchronization is not
attempted. [Checkpoint results](publication-checkpoints.json) are point-in-time
evidence; future checkpoints and changing refs need a new scan.

The scan covered **979 pending blobs** and flagged **18** for possible sensitive
content: the 15 original capture blobs and three transcript blobs. Scanner
diagnostics and detected values were suppressed. Those objects
remain unchanged and are **not safe to authorize for synchronization**. A clean
submission guard cannot clear this separate checkpoint hold.

**Entire synchronization is not authorized by this task.** Any possible-sensitive
finding keeps those checkpoints on hold. Cleaning the staged publication does not
sanitize old Git objects or Entire transcripts. Existing detection safeguards and
capture hooks remain enabled; no destructive checkpoint/history rewriting is
attempted or implied. A future synchronization must resolve its recorded findings
and scan the actual outgoing content first.
