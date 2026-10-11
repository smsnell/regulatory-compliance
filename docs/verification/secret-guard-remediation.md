# Final pre-commit secret guard investigation — 2026-10-10

> Historical investigation of the original captures. The owner subsequently
> authorized a publication derivative; see [publication remediation](publication-remediation.md)
> for current submission hashes, verification, and checkpoint synchronization limits.
> Paths and hash observations below refer to the preserved originals.

Status: **BLOCKED pending an owner decision about sensitive source evidence.**
No credential exception was justified. No commit or push was performed by Codex.
Compliance implementation and the compliance test suite were not reopened.

## Operator history

The operator reports manually running, outside Codex:

~~~sh
TMPDIR="$HOME/.cache/rci-secret-scan" \
  /usr/bin/time -p git commit \
  -m "Finalize compliance pipeline and U20 remediation"
~~~

The hook took **367.62 seconds**, reported 15 possible-secret file findings
(six historical, nine current), suppressed detected values, and blocked the
commit. No commit or push occurred; intended submission changes remained staged.
This is an operator-reported manual attempt, not a Codex action or a newly
executed command in this investigation.

## Root cause and dispositions

A focused scan of the 44 staged .bin source captures reproduced exactly the
15 flagged paths. They are retained response bodies containing credential-shaped
frontend data and WAF challenge material, rather than an attempt_key heuristic
failure. The earlier portable U20 log scans covered another artifact scope and
did not establish that these source captures were safe to publish.

Twelve files each contain 19 Google API key occurrences, detected by both
gcp-api-key and rci-google-api-key, plus one maestro_container_token
detected by generic-api-key. Across them: 228 Google key occurrences, 12
Maestro token fields, 468 rule matches. All 19 distinct Google key values match
the preserved U05 original bundles, compared only in memory. No key was used
or sent to an external service. U05's prior used_in_tests alert status was
explicitly not evidence of ownership, restrictions, validity or revocation.

The other three files are EUR-Lex AWS WAF interstitials; their gokuProps.key
fields trigger generic-api-key once each. These are challenge-related data;
available evidence does not establish that the particular values are harmless
public identifiers or safe to redistribute. They remain uncertain sensitive
material. The 15 file findings comprise **471 individual rule matches**.

Google warns that public API key exposure can enable unexpected charges or
unauthorized access; browser visibility alone is not proof of safety:
[Google API key guidance](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices).
[AWS challenge documentation](https://docs.aws.amazon.com/waf/latest/developerguide/waf-js-challenge-api.html)
describes token-based challenge handling, but does not establish the safety
of the specific captured gokuProps.key values. The conservative disposition
is an investigation conclusion, not an assertion that every value is an active
credential.

History paths below have prefix
deliverables/history/run-f48b4823b3ad4faaa9ac30a301b66505/sources/;
current paths have prefix deliverables/sources/.

| Location | Capture filename | Category | Classification and disposition |
|---|---|---|---|
| History | 15ae719c1b5e462fa4d946d9bb91d920.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| History | 780f63e16d444eeea63f7ceeb7ef7a98.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| History | 8502670b407f4d88b184c689e08d6273.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| History | 9de475942a9d494aabaf3e1696cb0c8c.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| History | aac479ed5b5b4430a5f92ca87a4c3c70.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| History | da20552b9fc446cf9c0fde2b15b34cf3.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| Current | 098718c066874eee8f5eaa561b60c4f9.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| Current | 0c15679a9aa34cf599a1f2249f938dbd.bin | AWS WAF gokuProps.key | Uncertain sensitive; BLOCK |
| Current | 39c5b4e1e1704e838fba2512d4367979.bin | AWS WAF gokuProps.key | Uncertain sensitive; BLOCK |
| Current | 67eb8ff2ffc64f6bad2784591d1aa9a4.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| Current | a0cd77fbb3f7493888fd1dcb41dc45d3.bin | AWS WAF gokuProps.key | Uncertain sensitive; BLOCK |
| Current | a5a78fd5352b4e1882485f18fd68c38b.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| Current | eba44a84b7df47e4a241ac11d1bbbcb7.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| Current | f34f0793ba6847d2b693861ca1a07fde.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |
| Current | f9b436533cb94cab9def3ef60c892f44.bin | Google API keys + Maestro token | Uncertain sensitive; BLOCK |

Every rule match in each listed file inherits its stated disposition. None has
been demonstrated to be a non-sensitive public identifier; validity, ownership,
restrictions and expiration remain unverified. No allowlist, fingerprint ignore,
inline allowance, rule disablement or source edit was applied. The existing
--ignore-gitleaks-allow protection remains enabled; it concerns inline comments
and does not disable configured rule allowlists.

See [capture and integrity record](secret-guard-captures.json) for exact full
paths, rule locations/counts, source hashes, and matching terminal-journal hashes.
The focused repeat checked all 15 files in 4.125 seconds using four independent
scanner processes and confirmed redacted report Secret fields.

## Guard change and security safeguards

scripts/secret_guard.py now runs at most four independent per-file scans in
parallel, avoiding the previous serial latency. Each retains the exact original
stdin invocation and its own private temporary cwd. No concatenation, MIME
filter, extension skip, size exclusion, whole-file exception or report-based
suppression was introduced. Forbidden paths are checked before their bytes
are read. Diagnostics remain ordered and contain only escaped paths and fixed
reason text. Git errors, missing tools, scanner errors and secrets block.

A focused alternative that limited Gitleaks' Go concurrency showed no useful
improvement (about 0.81 seconds per call); it was not implemented.
Gitleaks version: **8.24.2**. .gitleaks.toml and the installed hook are unchanged.

Tests cover binary/NUL input, inline allowance rejection, partial staging,
unusual filenames, private keys, Google and GitHub key shapes, forbidden paths,
the narrow existing capture-ID exception, and a missing scanner. New cases
cover mixed concurrent blobs with an ignore file and a clean unstaged correction,
and suppression/failure of a scanner that emits diagnostics and exits 2.
Disposable commit tests are excluded so this investigation performs no commits.

## Execution record

All scanner and substantial temporary-data commands explicitly set
TMPDIR="$HOME/.cache/rci-secret-scan". The directory was ensured with
mkdir -p before scanning. No unrelated temporary files were removed and no
new scanner temporary data was written to /tmp. The existing test interpreter
resides there; its pathname does not determine where these tests create data.
A first targeted test invocation using system Python failed with
No module named pytest; it was replaced with the existing project interpreter.

Final targeted test command:

~~~sh
TMPDIR="$HOME/.cache/rci-secret-scan" PYTHONDONTWRITEBYTECODE=1 \
  /tmp/rci-u03-clean/bin/python -m pytest tests/runtime/test_secret_guard.py \
  -q -k 'not hook_blocks_actual_commit and not rename_deletion_and_full_index' \
  --basetemp="$HOME/.cache/rci-secret-scan/guard-focused-final"
~~~

Final focused result: **15 passed, 2 deselected**, 9.20 seconds; exit 0.
First installed pre-commit hook run: **exit 1**, **130.076 seconds**, **556
staged files**, index unchanged during scan. It reported the expected 15
captures plus one generic-rule false positive in the new investigation JSON:
a diagnostic sentence followed by a property name resembled an assignment.
The sentence was reworded; no scanner exception was introduced. A focused
scan of the corrected reports and final full hook run follow below.

Final installed pre-commit hook result: **exit 1**, **126.303 seconds**, **556
staged files**. Exactly the original **15 capture paths** were reported,
with no scanner errors or investigation-document findings. The index stayed
unchanged during scanning. Detected Google, Maestro and WAF values were compared
in memory against the captured hook diagnostics and were absent. The installed
hook was invoked directly with TMPDIR set, without invoking git commit.

The two reports were then updated with results, restaged, and checked separately
with the same scanner against their final staged bytes. This avoids repeating
the full scanner solely to add its execution record. Final staged report scans:
**exit 0 for both**. No guard code, rule, test or deliverable changed after the
final full scan. Scoped staged whitespace checks also pass.

**Pre-commit readiness: BLOCKED.** The guard is working and faster, but these
required source originals still contain unresolved sensitive material.

## Evidence integrity

A baseline records index object IDs and worktree SHA-256 hashes for all **332
indexed deliverable files**, including history, source bodies, snapshots,
journals, bindings and required artifacts. All 44 source captures initially
match their staged bytes; all 15 flagged capture SHA-256 values match their
staged terminal journals. Final byte/OID comparison: **PASS**, all 332 index object IDs and worktree hashes
unchanged; all 44 capture bodies still match staged bytes.

No source data is copied into the investigation record. Reports contain paths,
hashes, counts, fixed field labels and dispositions. Scanner diagnostics in
the guard are discarded. One early investigation probe that attempted to
extract assignment names erroneously emitted an encoded AWS WAF fragment
in tool output. That probe was replaced with fixed-label boolean checks.
The fragment is not repeated in notes or persisted investigation artifacts.
This incident means the investigation cannot claim that all exploratory
diagnostics were free of source fragments.

## Owner decision and safe options

1. Obtain owner/vendor evidence about the exact detected categories: documented
   non-secret role, ownership, restrictions and publication permission. Reassess
   only the specific values/contexts substantiated by that evidence; a general
   browser-exposure statement is insufficient.
2. Approve a separate evidence-publication plan: preserve originals in controlled
   storage, create explicitly labeled sanitized derivatives, and regenerate
   all affected hashes, journals, snapshots and bindings under an authorized
   evidence contract. U05 provides a precedent for derivatives, but changing
   this completed submission's required originals needs an explicit decision.
   Merely unstaging captures leaves incomplete required evidence and is not a fix.
3. Keep the submission blocked until safe publication of the required evidence
   is resolved. If genuine credentials are confirmed, have their owner rotate
   or revoke them; that alone does not authorize silently altering originals.

The guard must continue to reject these originals. No bypass is proposed.
The earlier U20 readiness statement is superseded for commit readiness by
this scoped security blocker.
