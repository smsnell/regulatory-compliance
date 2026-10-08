"""G1 contracts: schema validation, exact state dimensions and bounded exchanges.

These validate structure and provenance, not legal meaning or human authorization.
"""
from dataclasses import dataclass
from enum import StrEnum
from datetime import date, datetime
import re
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Literal, TypedDict

from jsonschema import Draft202012Validator, FormatChecker

STAGES = ("scope", "source-capture", "authority-and-timing", "evidence-reconciliation",
          "impact-analysis", "actions-and-approvals", "publication-validation")
SNAPSHOT_PATHS = tuple(f"snapshots/{i:02d}-{name}.json" for i, name in enumerate(STAGES, 1))
ASSIGNED_REVIEW_DATE = "2026-08-26"
AS_OF = "2026-08-26T00:00:00Z"
CONTRACT_VERSION = "rci-contracts/1"
PUBLIC_SCHEMA_HASH = "sha256:8de9874ded18fa97294e83012796e4c386aa60ccfd30f8eca89cabdf2a267ac3"
COLLECTIONS = (
    {"scope_basis": "scope-basis"},
    {"sources": "source", "attempts": "attempt", "captures": "capture", "evidence": "evidence",
     "normalized_rows": "normalized-row", "mappings": "mapping", "diagnostics": "diagnostic"},
    {"binding_rules": "rule", "timing_rules": "timing-rule", "guidance_context": "guidance",
     "authority_blockers": "blocker"},
    {"system_facts": "fact", "policy_controls": "policy-control", "incident_evidence": "incident",
     "conflicts": "conflict", "evidence_gaps": "gap"},
    {"impacts": "impact", "unaffected_items": "impact", "conflicts": "conflict",
     "unresolved_items": "impact"},
    {"proposed_actions": "action", "approval_requirements": "approval", "escalations": "escalation",
     "review_requests": "review-request", "feedback": "feedback"},
    {"artifacts": "artifact", "validation_checks": "validation-check"},
)


class RunState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class RetrievalState(StrEnum):
    RETRIEVED = "retrieved"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    UNVERIFIED = "unverified"
    STALE = "stale"


class ImpactState(StrEnum):
    SUPPORTED_IMPACT = "supported-impact"
    SUPPORTED_NO_IMPACT = "supported-no-impact"
    CONFLICTING = "conflicting"
    UNRESOLVED = "unresolved"


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not-required"


class PublicationState(StrEnum):
    VALIDATED = "validated"
    BLOCKED = "blocked"
    FAILED = "failed"


class Record(TypedDict):
    id: str
    record_type: str
    summary: str
    evidence_ids: list[str]


class GapRecord(Record):
    source_basis: list[str]
    reason: str
    owner: str | None
    resolution_need: str
    subject_ids: list[str]
    state: Literal["unresolved"]


class Predecessor(TypedDict):
    snapshot_id: str
    path: str
    sha256: str


class Snapshot(TypedDict):
    schema_version: str
    contract_version: str
    snapshot_id: str
    run_id: str
    stage: str
    sequence: int
    created_at: str
    status: str
    predecessor: Predecessor | None
    consumed_record_ids: list[str]
    produced_record_ids: list[str]
    state: dict
    unresolved: list[GapRecord]
    decisions: list[Record]


class ContractError(ValueError):
    """Integrity/structural failure; never silently downgrade to supported output."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha256_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("hash requires exact bytes")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def json_values_equal(left, right) -> bool:
    """Compare parsed values without Python's boolean/number coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(json_values_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(json_values_equal(a, b) for a, b in zip(left, right))
    return left == right


def json_bytes(value: object) -> bytes:
    """Serialization convention. Hash the returned/written bytes, not the object."""
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       sort_keys=True, indent=2) + "\n").encode("utf-8")


def parse_json(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def bad_constant(value):
        raise ContractError("non-finite JSON value: " + value)

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=bad_constant)
    except (UnicodeError, ValueError) as error:
        raise ContractError("invalid UTF-8 JSON: " + str(error)) from error
    require(isinstance(value, dict), "JSON root must be an object")
    require_finite_numbers(value)
    return value


def require_finite_numbers(value) -> None:
    """Reject parser overflow and nested non-finite caller-supplied values."""
    if isinstance(value, float):
        require(math.isfinite(value), 'non-finite JSON number')
    elif isinstance(value, dict):
        for item in value.values():
            require_finite_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            require_finite_numbers(item)


_SCHEMA_FILE = Path(__file__).resolve().parents[2] / "references/schemas/contracts.schema.json"
_SCHEMA = json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))
_PUBLIC_FILE = Path(__file__).resolve().parents[3] / "snapshot.schema.json"
_FORMATS = FormatChecker()


@_FORMATS.checks("date", raises=ValueError)
def _date_format(value):
    if not isinstance(value, str):
        return True
    return bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)) and bool(date.fromisoformat(value))


@_FORMATS.checks("date-time", raises=ValueError)
def _datetime_format(value):
    # FormatChecker silently skips unavailable optional format dependencies.
    # Register this instance's checker explicitly so conformance never depends
    # on whether jsonschema's RFC3339 optional extra happens to be installed.
    if not isinstance(value, str):
        return True
    match = re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:([0-9]{2})"
        r"(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})", value)
    if not match:
        return False
    if int(value[11:13]) > 23 or int(value[14:16]) > 59 or int(value[17:19]) > 60:
        return False
    if value[-1].upper() != "Z" and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        return False
    # RFC3339 permits leap seconds; calendar/clock bounds still get checked.
    seconds = match.group(1)
    checked = value[:17] + ("59" if seconds == "60" else seconds) + value[19:]
    return bool(datetime.fromisoformat(checked.upper().replace("Z", "+00:00")))



def validate_schema(value: dict, definition: str = "snapshot") -> None:
    require_finite_numbers(value)
    require(definition in _SCHEMA["$defs"], "unknown contract definition")
    schema = {**_SCHEMA, "$ref": "#/$defs/" + definition}
    errors = sorted(Draft202012Validator(schema, format_checker=_FORMATS).iter_errors(value),
                    key=lambda e: (str(list(e.path)), e.message))
    if errors:
        error = errors[0]
        raise ContractError(f"{definition} {list(error.path)}: {error.message}")
    if definition == "snapshot":
        raw = _PUBLIC_FILE.read_bytes()
        require(sha256_bytes(raw) == PUBLIC_SCHEMA_HASH, "supplied schema changed")
        errors = list(Draft202012Validator(parse_json(raw), format_checker=_FORMATS).iter_errors(value))
        require(not errors, "public snapshot schema: " + (errors[0].message if errors else ""))


def reduce_states(states) -> RunState:
    values = [RunState(state) for state in states]
    require(bool(values), "state reducer requires an explicit nonempty input")
    precedence = list(RunState)
    return max(values, key=precedence.index)


def package_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), "package path is required")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and "\\" not in relative and ":" not in relative
            and all(p not in {"", ".", ".."} for p in relative.split("/")),
            "invalid package-relative path")
    base = root.resolve()
    target = base.joinpath(*path.parts).resolve()
    require(target.is_relative_to(base) and target != base, "path escapes package root")
    return target


def verify_file(root: Path, pointer: dict, path_field="path", hash_field="sha256") -> bytes:
    path = package_path(root, pointer[path_field])
    require(path.is_file(), "missing retained file: " + pointer[path_field])
    data = path.read_bytes()
    require(sha256_bytes(data) == pointer[hash_field], "retained bytes/hash mismatch: " + pointer[path_field])
    return data


@dataclass(frozen=True)
class ExchangeResult:
    disposition: Literal["proposed", "unresolved"]
    response: dict
    reason: str | None = None


def validate_interpretation(request_bytes: bytes, response_bytes: bytes, *,
                            root: Path, run_id: str, stage: str, upstream: list[dict]) -> ExchangeResult:
    """Read-only binding check; caller retains exact bytes even on parse failure.

    `upstream` must come from a verified same-run snapshot prefix. No response is
    accepted as authoritative, nor does quote matching prove legal meaning.
    """
    request, response = parse_json(request_bytes), parse_json(response_bytes)
    validate_schema(request, "interpretation-request")
    # Envelope corruption is technical. Missing/malformed claim support is a
    # bounded unsupported proposal, retained unresolved without inventing fields.
    require(isinstance(response.get('candidates'), list), 'invalid response candidate container')
    validate_schema({**response, 'candidates': []}, "interpretation-response")
    candidate_error = None
    try:
        validate_schema(response, "interpretation-response")
    except ContractError as error:
        candidate_error = str(error)
    require(request["run_id"] == response["run_id"] == run_id, "cross-run interpretation")
    require(request["stage"] == response["stage"] == stage, "wrong interpretation stage")
    require(response["packet_id"] == request["packet_id"], "wrong interpretation packet")
    require(response["packet_sha256"] == sha256_bytes(request_bytes), "changed interpretation packet")
    require(bool(upstream) and len(upstream) == STAGES.index(stage), "wrong upstream prefix")
    from .snapshots import read_chain
    require(json_values_equal(read_chain(root, count=len(upstream)), upstream), 'invalid interpretation upstream chain')
    known = {}
    records = {}
    for seq, snapshot in enumerate(upstream, 1):
        require(snapshot["run_id"] == run_id and snapshot["sequence"] == seq, "unverified upstream identity")
        pointer = {"path": SNAPSHOT_PATHS[seq - 1], "sha256": sha256_bytes(
            package_path(root, SNAPSHOT_PATHS[seq - 1]).read_bytes())}
        require(json_values_equal(parse_json(verify_file(root, pointer)), snapshot), "upstream object differs from disk")
        known[snapshot["snapshot_id"]] = {**pointer, "snapshot_id": snapshot["snapshot_id"], "sequence": seq}
        for collection in COLLECTIONS[seq - 1]:
            for record in snapshot["state"][collection]:
                records[record["id"]] = record
    require(len({p['snapshot_id'] for p in request['upstream']}) == len(request['upstream']),
            "duplicate interpretation upstream binding")
    require(known[upstream[-1]['snapshot_id']] in request['upstream'], "missing immediate upstream binding")
    for pointer in request["upstream"]:
        require(known.get(pointer["snapshot_id"]) == pointer, "altered interpretation upstream binding")
    extracts = {}
    for extract in request["extracts"]:
        require(extract["evidence_id"] not in extracts, "duplicate interpretation extract")
        evidence = records.get(extract["evidence_id"])
        require(evidence is not None and evidence['record_type'] == 'evidence', "invented extract evidence")
        capture = records.get(extract["capture_id"])
        require(capture is not None and capture['record_type'] == 'capture', "invented extract capture")
        require(evidence['capture_id'] == extract['capture_id'] and
                evidence['local_reference'] == extract['path'] and
                evidence['content_hash'] == extract['sha256'] and
                evidence['locator'] == extract['locator'], "extract evidence binding mismatch")
        raw = verify_file(root, extract)
        require(extract['text_sha256'] == sha256_bytes(extract['text'].encode('utf-8')), "changed extracted text")
        require(extract['text'].encode('utf-8') in raw and
                evidence['quoted_support'] in extract['text'], "extract not grounded in retained text")
        extracts[extract['evidence_id']] = extract
    fields = request['field_dictionary']
    require(fields['sha256'] == sha256_bytes(json_bytes(fields['fields'])), "changed field dictionary")
    for field in ('instruction_versions', 'reference_versions', 'requested_model', 'requested_effort'):
        require(response['metadata'][field] == request['metadata'][field], 'changed interpretation execution basis')
    for packet in (request, response):
        for group in ('instruction_versions', 'reference_versions'):
            for pointer in packet['metadata'][group]:
                verify_file(root, pointer)
    if response['disposition'] != 'proposed':
        return ExchangeResult('unresolved', response, response['diagnostic'] or response['disposition'])
    if candidate_error is not None:
        return ExchangeResult('unresolved', response, 'unsupported candidate structure: ' + candidate_error)
    if not response['candidates']:
        return ExchangeResult('unresolved', response, 'no supported candidates')
    systems = set(upstream[0]['state']['systems_in_scope'])
    for candidate in response['candidates']:
        if not set(candidate['system_ids']) <= systems:
            return ExchangeResult('unresolved', response, 'candidate outside assigned scope')
        for citation in candidate['citations']:
            extract = extracts.get(citation['evidence_id'])
            if extract is None or citation['quote'] not in extract['text']:
                return ExchangeResult('unresolved', response, 'unsupported citation/quote')
        if candidate['uncertainty'] is not None:
            return ExchangeResult('unresolved', response, 'candidate meaning remains uncertain')
    return ExchangeResult('proposed', response)
