# U08 linked reports and interpretation

Extend Stage 02 in a **new isolated run**, with fresh core reads:

```sh
python regulatory-change-impact-brief/scripts/run.py --config config/review.json --capture-slice --linked-reports
```

Add `--interpret-reports` to invoke the existing authenticated, restricted U03
host after freezing Stage 02. It implies linked report capture. Scope/retry
options retain their U07 meanings. The command returns blocked exit 3 because
Stages 03–07 and the final package remain outside this implementation. Technical
failures return 1. A completed U08 exchange is never full package acceptance.

Report routes come only from valid normalized EVIDENCE `evidence_ref` cells.
Direct credential-free HTTPS URLs with no query/fragment are supported. Labels,
relative references, ambiguous rows and unsupported routes remain diagnostics;
no endpoint is invented. Each authorized row gets its own report declaration
and journaled GET/retries. Redirect bodies are retained without following them.
The adapter follows no embedded links or assets and supplies no report credentials.

UTF-8 plain text, CSV and derived visible HTML text are supported for bounded
text inspection. The full HTML body remains primary; the separate text file has
its own hash and capture with derivation/parent/time. Text parsing establishes
neither layout nor visual absence. Images, PDF, unknown MIME, invalid UTF-8,
access pages and unavailable links remain retained/unresolved. No OCR engine is
implemented, and request construction rejects unverified OCR derivations.

The current retained source fixtures have ten report labels and no usable report
URLs. This establishes a missing-route limitation, not a successful report read.
U08 tests explicitly use synthetic report URLs/bodies and sanitized core replay.
Native hyperlink-only labels and authenticated/binary report workflows require
source-owner access and a reviewed representation; they are not silently guessed.

`u08_capture` and `u08_reports` use the existing G1 versioned extension boundary.
The independent slice validator reconstructs report routes from retained register
bytes, checks every dispatched attempt, rederives HTML text, checks report evidence
and report accounting, and retains all U07 normalization/scope/journal checks.
All linked reads finish before Stage 02 freezes. Existing U07 snapshots and
schemas remain unchanged. `--capture-slice` alone retains its explicit U07 boundary.

`rci.interpretation.create_request` constructs the frozen G1 packet from a verified
upstream prefix, retained evidence, assigned date, field dictionary and instruction
versions. The U08 host packet includes readable reports and the captured EVIDENCE
table, so owner assertions are available beside captures. Source data never grants
tool authority. The helper `stage.py submit-report` writes exact proposal bytes
before parsing and exact request/response copies before validation. Every rejected
exchange gets an analysis diagnostic. Refusal, truncation, unsupported citations,
uncertainty and missing report support remain unresolved; corrupt bindings fail.

G1 remains the envelope/provenance validator. U08 additionally requires captured
report support for each candidate system: register status alone cannot support it.
`analysis/accepted-candidates.json` is derived analysis, never primary evidence.
`read_candidates` independently revalidates its exact request/response and rejects
altered handoffs. Candidate structure, exact quotes and valid bindings do not prove
semantic truth or authority. Final interpretation/conflict resolution remains with
owners and Legal; authority evaluation belongs to U09.

The host keeps U03's fresh session, ignored inherited configuration/rules,
disabled web/connectors/multi-agent/networking, and local writes. No message,
source mutation or production calendar tool is exposed. The frozen runtime config
requests Sol high for the host; U08's implementation effort recommendation does
not change that interface. Visible host events/usage and exact prompt/invocation
are retained, while unreported model/effort/provider state remain unknown.

Automated checks:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-u03-clean/bin/python -m pytest tests/runtime/test_u08.py -q
PYTHONDONTWRITEBYTECODE=1 /tmp/rci-u03-clean/bin/python tests/integration/u08_host.py --output /tmp/rci-u08-host
```

The latter is opt-in and uses the actual authenticated host with synthetic report
transport, not live report evidence. Exact results, manual comparison and scanner
dispositions are in [U08 verification](verification/u08.md).
