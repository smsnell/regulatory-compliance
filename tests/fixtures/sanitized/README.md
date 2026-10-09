# Sanitized replay fixtures — not original HTTP evidence

These derivatives support offline U05/U06/U07 regression tests. Google API key
patterns were replaced with a fixed marker in 18 HTML bodies (342 occurrences).
The 18 embedded maestro_container_token values were also redacted after broad
secret scanning flagged that additional frontend configuration field.
The manifest links every derivative to the original hash and records exactly
which files changed. CSV bodies are unchanged. Modified capture representations
are labeled extracts; their journals and snapshot hash chains bind the new bytes.
Historical record IDs and timestamps express lineage, not a new live retrieval.

See [secret safety](../../../docs/secret-safety.md) for controlled original storage,
deterministic regeneration and the separate original-evidence verification command.
Sanitized replay success does not assert that original evidence is available.
