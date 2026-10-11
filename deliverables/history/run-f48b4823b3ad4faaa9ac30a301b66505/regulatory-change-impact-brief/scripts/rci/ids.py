"""Versioned semantic identities; no dates, wording or row positions in business keys."""
from dataclasses import dataclass
import hashlib
import json
from urllib.parse import quote
from uuid import uuid4


class IdentityConflict(ValueError):
    """Ambiguous identity must be preserved for resolution, never fuzzy joined."""


@dataclass(frozen=True)
class BusinessKey:
    system_id: str
    rule_basis: str
    kind: str
    distinguishing_scope: str
    version: str = "rci-business-key/1"

    def canonical_bytes(self) -> bytes:
        values = (self.version, self.system_id, self.rule_basis, self.kind,
                  self.distinguishing_scope)
        if self.version != "rci-business-key/1" or any(
                not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError("business key requires exact nonempty semantic components")
        return json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def stable_business_id(namespace: str, key: BusinessKey) -> str:
    if namespace not in {"impact", "action"}:
        raise ValueError("business namespace must be impact or action")
    return f"{namespace}:v1:{hashlib.sha256(key.canonical_bytes()).hexdigest()}"


def action_rule_basis(rule_bases) -> str:
    """Preserve one basis unchanged; bind a multi-basis action to an exact set."""
    bases = list(rule_bases)
    if not bases or any(not isinstance(b, str) or not b.strip() for b in bases):
        raise ValueError('action requires nonempty rule bases')
    unique = sorted(set(bases))
    if len(unique) == 1:
        return unique[0]
    raw = json.dumps(['rci-action-bases/1', unique], ensure_ascii=False,
                     separators=(',', ':')).encode('utf-8')
    return 'basis-set:v1:' + hashlib.sha256(raw).hexdigest()


def calendar_uid(action_id: str) -> str:
    if not action_id.startswith("action:v1:") or len(action_id) != 74:
        raise ValueError("calendar UID requires stable action identity")
    if any(c not in "0123456789abcdef" for c in action_id[10:]):
        raise ValueError("invalid action identity")
    return action_id + "@regulatory-change-impact-brief"


def new_run_id() -> str:
    return "run-" + uuid4().hex


def new_snapshot_id() -> str:
    return "snapshot-" + uuid4().hex


def new_record_id(run_id: str, sequence: int, record_type: str) -> str:
    if not isinstance(run_id, str) or not run_id.strip() or sequence not in range(1, 8):
        raise ValueError("record ID requires run and stage")
    if not record_type or not all(c.islower() or c == "-" for c in record_type):
        raise ValueError("invalid record type")
    return f"record:{quote(run_id, safe='')}:{sequence:02d}:{record_type}:{uuid4().hex}"


def check_record_id(record_id: str, run_id: str, sequence: int, record_type: str) -> None:
    prefix = f"record:{quote(run_id, safe='')}:{sequence:02d}:{record_type}:"
    suffix = record_id.removeprefix(prefix)
    if not record_id.startswith(prefix) or len(suffix) != 32 or any(
            c not in "0123456789abcdef" for c in suffix):
        raise IdentityConflict("record ID does not bind exact run/stage/type")


def rule_version_id(basis_id: str, meaning_key: str) -> str:
    """Caller supplies a reviewed semantic version key, never raw wording/date."""
    if not basis_id.strip() or not meaning_key.strip():
        raise ValueError("rule version requires basis and explicit meaning key")
    value = json.dumps(["rci-rule-version/1", basis_id, meaning_key], separators=(",", ":"))
    return "rule:v1:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


class IdentityRegistry:
    """Scoped to one run; caller retains conflicting input records on rejection."""

    def __init__(self) -> None:
        self._business: dict[str, bytes] = {}
        self._operational: set[tuple[str, str]] = set()

    def business(self, namespace: str, key: BusinessKey) -> str:
        identity = stable_business_id(namespace, key)
        canonical = key.canonical_bytes()
        if identity in self._business and self._business[identity] != canonical:
            raise IdentityConflict("different semantic keys collide")
        self._business[identity] = canonical
        return identity

    def operational(self, source_id: str, source_business_id: str) -> str:
        if not source_id.strip() or not source_business_id.strip():
            raise ValueError("source identity is required")
        key = (source_id, source_business_id)
        if key in self._operational:
            raise IdentityConflict("duplicate operational identity; retain both rows")
        self._operational.add(key)
        return source_business_id  # preserve exact source-native identity
