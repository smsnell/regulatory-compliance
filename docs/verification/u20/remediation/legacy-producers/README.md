# Legacy producer witnesses

These are portable evidence copies for the four exact pre-remediation producer
fingerprints allowed by the E04 production provenance guard. `provenance.json`
records each original path, copied scope snapshot hash, and producer fingerprint.
The scope snapshots are byte-for-byte copies; original packages were not changed.

Three witnesses include the canonical code inventory reconstructed from their
retained skill bundle: relative `.py`, `.json`, and `.md` file paths mapped to
their SHA-256 hashes. The SHA-256 of each canonical inventory is the existing
Stage 01 `code_fingerprint`. None contains `scripts/rci/decisions.py`. Historical
source code was read and hashed, never executed. The remaining U07 capture is
anchored by its exact scope hash in the portable pre-remediation `../baseline.json`.

Fresh producers retain this same hash preimage at `analysis/producer-code.json`.
A package with the decision profile must contain the independently reconstructed
decisions. Without the profile, production validation requires a matching retained
legacy skill bundle or both an exact producer fingerprint and its canonical
Stage 01 scope witness hash listed here. Claiming a known fingerprint on a new
scope is insufficient. Contradictory available
inventories or bundles are rejected before fingerprint exceptions apply. Unknown
unmarked legacy prefixes without that proof cannot be distinguished from stripped
new producers and fail closed. Unbundled compatibility is limited to these exact
witnessed scopes. Generic schema/graph validation and the snapshot
JSON schema remain unchanged; existing marked packages need no retroactive inventory.
