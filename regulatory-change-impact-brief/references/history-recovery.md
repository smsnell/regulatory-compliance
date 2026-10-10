# History, replacement and fresh recovery

The launcher holds `runtime.writer_lock(output_root)` for the entire fresh run.
It writes the candidate under `.staging/<new-run-id>/`. All seven stages rerun
with new run/snapshot/record identities and fresh required source attempts.
An interrupted candidate is retained for inspection; it is never resumed as a
new acquisition or interpreted as new evidence.

## Inspecting current files

`history.inspect_current(root, validator=validate.validate_package)` reads
actual managed bytes and checks their referenced hashes on every invocation.
It returns `run_id`, `accepted`, `status`, `inventory`, and `diagnostics`.
Unchanged input fingerprints do not skip this inspection. A completion flag
alone cannot establish acceptance. The incomplete marker rejects current even
when a completion marker also exists.

The managed directories are `sources/`, `snapshots/`, `analysis/`, the copied
`regulatory-change-impact-brief/` skill, and `config/`. Managed files are the
three artifacts, `snapshot.schema.json`, and the two package markers. The
copied skill, schema and config bytes retain the interpretation execution
basis. Unrelated output-root files, `.staging/`, and global `history/` are
outside current-package replacement ownership.

## Archiving exact available bytes

`history.archive_current(root, run_id, created_at)` creates
`history/<run-id>/.history-inventory.json` and preserves the available managed
files at their original relative paths. The inventory records each path,
actual hash and size, expected hashes, availability (`present`, `missing`,
`corrupt`, or `unreadable`), and findings. Missing files are explicitly listed
and are never claimed as retained. Corrupt files retain their original bytes.
Unsafe or unreadable items have findings and no claimed byte hash.

An archive describes a historical occurrence; archive byte verification does
not assert that its business conclusions or publication were valid. The
manifest's `reference_resolution` is `archive-root-relative`: historical
snapshots, sources, interpretation packets and metadata resolve against the
archived package root. Explicit `history/<run-id>` dependencies found in
reviewed draft pointers are retained inside that root. The entire global
history is never recursively copied.

Copying uses a new `history/.pending-*` directory. The manifest and every
claimed retained byte must verify before the directory becomes the canonical
archive. Partial copies remain inspectable after a write error. The current
bytes are checked again after copying. Existing canonical archives are
verified and reused only when the inventory matches; differing bytes stop
replacement. `occurrence=True` instead creates a separately inventoried
`history/<run-id>/occurrences/<unique-id>/` without changing the prior archive.

`history.verify_archive(archive_root, expected_sha256=None)` always resolves
the manifest's paths within `archive_root`. It returns an `Archive` whose
`marker_reference(output_root)` binds the archive root and exact inventory
hash to the frozen incomplete marker contract.

## Promotion order

Call `recovery.promote_candidate(root, candidate, new_run_id=..., created_at=...,
validator=validate.validate_package, lock_held=True)` while holding the launcher
lock. Standalone callers can omit `lock_held` to acquire the same OS lock.
The independent validator takes a package root and returns seven validated
snapshot dictionaries. Production uses the U17 validator; `read_chain` is
only the default primitive for isolated contract fixtures.

1. Independently validate the candidate and bind its Stage 07 hash and run.
2. Recover an unambiguous contract-valid prior run ID. If managed current files
   exist but no trustworthy ID is available, preserve them and stop.
3. Archive the prior available bytes and verify the archive. Merge explicit
   candidate history dependencies using identical bytes; conflicts stop.
4. Persist and reread the frozen incomplete marker before changing current
   managed files. Remove the old completion marker before the first such
   change.
5. Replace managed files from the verified candidate. Every file copy checks
   its candidate hash; global history and unrelated top-level files survive.
6. Independently validate a temporary view containing the actual copied
   current bytes. This view omits the control markers so the frozen reader can
   validate it while public current readers continue to reject replacement.
   Recheck the actual current inventory, candidate inventory, chain and Stage
   07 hash after validation.
7. Write completion only for a permitted `validated` publication with
   `complete` or `partial` status. Blocked packages retain their real Stage 07
   status and receive no completion marker. Clear the incomplete marker last.

This sequence detects multi-file interruption; it does not provide atomic
generation switching or automatic rollback. A write error propagates to the
launcher with the candidate, any archive/partial copy, control marker, and
available current bytes retained. The launcher reports the failure and any
storage limitation in its surviving journal and stderr.

## Interrupted replacement

`recovery.preserve_interrupted(root, created_at)` verifies the marker's prior
archive, then preserves the marker and available current bytes under the
failed marker's `new_run_id`. The original candidate and previous archive
remain in place. The failed package is truthfully incomplete and may contain
mixed stages; it cannot be accepted.

A fresh launcher execution obtains new IDs and performs all fresh reads and
stage computations. Promotion detects a remaining marker and preserves the
failed occurrence before replacing it with the new marker. Its archive
reference points to `history/<failed-run-id>` as required by the frozen
contract. Additional preservation calls use the failed run's occurrences
area. A malformed marker or unknown prior identity yields an explicit stop;
automatic orphan reconstruction is outside this procedure.

## Stage input fingerprints

`recovery.stage_fingerprints(bases)` requires one JSON basis per stage name in
`contracts.STAGES`. Each basis includes its scoped config, code/contract
version and substantive source/mapping/rule dependencies. Exclude new run and
record IDs, retrieval times, and occurrence-only paths from substantive bases.
Retain the result at `analysis/stage-fingerprints.json`.

`recovery.classify_change(previous, current)` reports the earliest changed
stage, or null when all substantive bases match. Scope/config maps to 01;
source content/mapping to 02; authority to 03; reconciliation to 04; impact
rules to 05; actions/feedback to 06; rendering/validation to 07. A contract
version change or missing prior fingerprint set begins at 01. Every result
still requires recomputation of stages 01–07, fresh source attempts, and actual
current-file inspection. These fingerprints are audit classification, not a
computation cache.

## Focused fault evidence

`tests/runtime/test_u18.py` uses synthetic U02 packages to exercise exact-byte
history, corrupt/missing inventories, unknown prior identity, archive errors,
marker errors, interruption, independent validation errors, partial completion
writes, second-writer rejection, blocked publication, explicit history
dependencies, and earliest-stage classification. These isolated tests do not
establish the G5 live vertical slice. G5 also requires the integrated launcher
sequence: run, changed source, new run, preserved history, injected corruption,
recorded failed occurrence, and fresh recovery with new source attempts.
