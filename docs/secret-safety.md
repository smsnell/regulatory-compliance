# Secret safety and evidence replay

Run `sh scripts/install-secret-hook.sh` once per clone after installing
[Gitleaks](https://github.com/gitleaks/gitleaks#installing) (tested with 8.24.2)
on PATH. Use an upstream release binary with its published checksum, or your
package manager. Python 3 and Git are the only other hook dependencies.
The installer preserves existing session-capture hooks and refuses to replace
an unrelated pre-commit hook. With a custom hook manager, invoke
`python3 scripts/secret_guard.py` from that existing hook.

The hook scans the complete **staged blobs**, including binary `.bin` files,
renames and partially staged files. It uses Gitleaks' maintained default rules
plus unconditional Google API key and private key header detection. It blocks
raw evidence and credential paths even when force-added. Missing tools, Git
errors and scanner errors fail closed; output includes paths, never values.
Inline `gitleaks:allow` comments and repository ignore fingerprints cannot hide
findings. No evidence directory is exempt from scanning. The only generic-rule exception
is the exact `attempt_key` field with a 32-character hexadecimal value: the
application generates it as a local capture filename, not a credential.

Run `python3 scripts/secret_guard.py --all` to scan the complete Git index.
The ordinary hook scans added/changed files only, so historical copies do not
prevent the cleanup commit. After editing a flagged file, stage the correction
and retry. For test credentials, construct synthetic values at runtime rather
than checking complete credential-shaped strings into fixtures.

Keep live output roots outside the checkout. Raw HTTP responses can contain
third-party credentials even for anonymous requests. `.gitignore` reduces
accidental staging; it does not remove tracked files or past commits.
Local hooks can be bypassed and scanners cannot detect every secret. Review
captures before retention/sharing and keep GitHub secret scanning enabled.

## Preserved originals and sanitized fixtures

The complete original bundles were copied to owner-only local storage at
`/home/mike/regulatory-compliance-evidence/2026-10-08/`, preserving their original
relative paths. All 249 files were verified byte-for-byte against the worktree
and HEAD before repository removal. This is local controlled storage, not an
off-machine backup. Obtain originals from the repository owner through an
approved private transfer; do not re-add them to Git.

`tests/fixtures/sanitized/manifest.json` records every original relative path,
original SHA-256, derivative path/SHA-256 and redaction count. It contains no key
values. Fixtures retain historical IDs/timestamps solely for lineage. Altered
captures are labeled `extract` and carry the original body hash; dependent
journals/snapshots use derivative hashes. The fixture directory and its manifest
explicitly identify these as test material, not untouched downloaded evidence.
The transformation removes 342 Google API key occurrences and 18 embedded
`maestro_container_token` values. All CSV bytes and the field dictionary basis
are unchanged.

Rebuild into a new, nonexistent directory:

```sh
python3 scripts/sanitize_evidence.py /path/to/originals /tmp/new-sanitized-fixtures
```

Verify originals and their exact relation to checked-in derivatives using the
project environment (`pip install -r requirements.lock`):

```sh
python3 scripts/verify_evidence.py --originals /path/to/originals
python3 -m pytest tests/runtime/test_u05.py tests/runtime/test_u06.py tests/runtime/test_u07.py tests/runtime/test_secret_guard.py -q
```

The explicit verifier checks all manifest hashes, deterministic regeneration,
Google identity/revision/tabs/native cells, CSV agreement, normalization, both
U07 slices and incomplete-package rejection. Missing originals yield a nonzero
`LIMITATION`, never a verification PASS. Offline tests use sanitized fixtures
and establish replay behavior only; production acquisition remains unchanged.

## Incident boundary

On 2026-10-08 all 19 GitHub Google API key alerts matched the captured frontend
keys in memory, without printing values or attempting key use. They were already
resolved as `used_in_tests`; that disposition is not evidence of ownership,
validity, restriction or revocation. No alert status was changed. The owner must
review that classification and rotate/revoke any project-owned credential.

The cleanup removes current repository copies, not historical Git objects.
History rewriting requires a separate coordinated decision; see
[GitHub's sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
