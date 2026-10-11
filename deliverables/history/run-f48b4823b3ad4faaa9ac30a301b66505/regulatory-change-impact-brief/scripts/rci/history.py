"""Exact-byte history and truthful inventories; callers hold the output lock.

An archive is a record of what existed, including damaged files. Its manifest
does not assert that the historical package passed business validation.
"""
from dataclasses import dataclass
import os
from pathlib import Path
from uuid import uuid4

from .contracts import (ContractError, SNAPSHOT_PATHS, json_bytes, package_path,
                        parse_json, require, sha256_bytes, validate_schema)
from .evidence import _read, _write
from .snapshots import ARTIFACT_PATHS, COMPLETION_MARKER, INCOMPLETE_MARKER, accept_package

MANIFEST = '.history-inventory.json'
MANAGED_DIRECTORIES = ('sources', 'snapshots', 'analysis',
                       'regulatory-change-impact-brief', 'config')
MANAGED_FILES = tuple(sorted(ARTIFACT_PATHS)) + (COMPLETION_MARKER, INCOMPLETE_MARKER,
                                             'snapshot.schema.json')


@dataclass(frozen=True)
class Archive:
    root: Path
    inventory_sha256: str
    manifest: dict

    def marker_reference(self, output_root):
        return dict(root=self.root.relative_to(output_root).as_posix(),
                    inventory_sha256=self.inventory_sha256, verified=True)


def _safe_id(run_id):
    require(isinstance(run_id, str) and bool(run_id.strip()) and
            '/' not in run_id and '\\' not in run_id and ':' not in run_id and
            run_id not in {'.', '..'}, 'unsafe history run ID')
    return run_id


def managed_paths(root):
    """Enumerate existing managed leaves, including unsafe leaves for findings."""
    root = Path(root)
    result = set()
    def walk(directory):
        for item in sorted(directory.iterdir()):
            if item.is_symlink() or not item.is_dir():
                result.add(item.relative_to(root).as_posix())
            else:
                walk(item)
    for name in MANAGED_DIRECTORIES:
        item = root / name
        if item.is_symlink() or (item.exists() and not item.is_dir()):
            result.add(name)
        elif item.is_dir():
            walk(item)
    for name in MANAGED_FILES:
        if (root / name).exists() or (root / name).is_symlink():
            result.add(name)
    return result


def _references(value, expected, dependencies, *, prefix=''):
    if isinstance(value, dict):
        # A field dictionary contains retained *configuration* of the original
        # mapping basis. Those historical example paths are not references to
        # this run's acquisitions; the dictionary itself has a version/hash.
        if value.get('schema_version') == 'rci-field-dictionary/1':
            return
        # Intake payloads and quarantined feedback are evidence of claims,
        # not authority to declare archive or current-file dependencies. Only
        # a verified matched feedback record has accepted historical pointers.
        if 'claimed_artifacts' in value and not (
                value.get('record_type') == 'feedback' and
                value.get('match_status') == 'matched' and
                value.get('authentication') == 'verified'):
            return
        reference = value.get('root')
        child_prefix = prefix
        if isinstance(reference, str) and reference.startswith('history/'):
            # Paths inside reviewed_draft resolve against that retained root.
            # They cannot bind a prior Stage06/07 hash to current snapshots.
            child_prefix = prefix + reference + '/'
            dependencies.add(prefix + reference)
        for field, hash_field in (('path', 'sha256'), ('local_reference', 'content_hash')):
            path, digest = value.get(field), value.get(hash_field)
            if isinstance(path, str) and isinstance(digest, str) and digest.startswith('sha256:'):
                expected.setdefault(prefix + path, set()).add(digest)
        for key, child in value.items():
            # Failure/prior inspections embed an earlier occurrence inventory.
            # Its path/hash observations must not become current file claims.
            if key not in {'inventory', 'claimed_artifacts'}:
                _references(child, expected, dependencies, prefix=child_prefix)
    elif isinstance(value, list):
        for child in value:
            _references(child, expected, dependencies, prefix=prefix)


def inventory(root):
    """Read actual bytes on every call, without trusting a success marker."""
    root = Path(root)
    paths = managed_paths(root)
    expected = {path: set() for path in (*SNAPSHOT_PATHS, *sorted(ARTIFACT_PATHS))}
    dependencies, parse_findings = set(), {}
    for path in sorted(paths):
        if not path.endswith('.json') or path.startswith(('sources/', 'regulatory-change-impact-brief/')):
            continue
        try:
            value = parse_json(_read(root, path))
            # Every field in the original intake batch is untrusted, including
            # payloads that copy the shape of a verified feedback record. The
            # accepted Stage06 record supplies any historical dependencies.
            if path != 'analysis/feedback-input.json':
                _references(value, expected, dependencies)
        except (OSError, ContractError) as error:
            parse_findings[path] = str(error)
    # Historical review dependencies are immutable package trees, not the
    # output root's unrelated histories. Do not traverse directory symlinks.
    for reference in sorted(dependencies):
        package_path(root, reference)
        item = root / reference
        if item.is_symlink():
            paths.add(reference)
        elif item.is_dir():
            def dependency_walk(directory):
                for child in sorted(directory.iterdir()):
                    if child.is_symlink() or not child.is_dir():
                        paths.add(child.relative_to(root).as_posix())
                    else:
                        dependency_walk(child)
            dependency_walk(item)
        else:
            expected.setdefault(reference, set())
    rows = []
    for path in sorted(paths | set(expected)):
        row = dict(path=path, expected_sha256=sorted(expected.get(path, set())),
                   sha256=None, size=None, availability='missing', findings=[])
        try:
            data = _read(root, path)
            row.update(sha256=sha256_bytes(data), size=len(data), availability='present')
            if row['expected_sha256'] and (len(row['expected_sha256']) != 1 or
                                           row['sha256'] not in row['expected_sha256']):
                row['findings'].append('retained bytes/hash mismatch')
            if path in parse_findings:
                row['findings'].append(parse_findings[path])
            if row['findings']:
                row['availability'] = 'corrupt'
        except FileNotFoundError:
            row['findings'].append('file does not exist')
        except OSError as error:
            row.update(availability='unreadable')
            row['findings'].append(str(error))
        rows.append(row)
    return rows


def recover_run_id(root):
    """Only unambiguous contract-valid run identifiers can authorize replacement."""
    root = Path(root)
    identities = set()
    marker = root / INCOMPLETE_MARKER
    if marker.exists() or marker.is_symlink():
        from .snapshots import validate_marker
        value = parse_json(_read(root, INCOMPLETE_MARKER))
        validate_marker(value, 'incomplete-marker', root)
        return _safe_id(value['new_run_id'])
    for path, definition in ((COMPLETION_MARKER, 'completion-marker'),
                             *((p, 'snapshot') for p in SNAPSHOT_PATHS)):
        try:
            value = parse_json(_read(root, path))
            validate_schema(value, definition)
            identities.add(_safe_id(value['run_id']))
        except (FileNotFoundError, OSError, ContractError):
            continue
    require(len(identities) <= 1, 'ambiguous prior run ID; current files preserved')
    return next(iter(identities)) if identities else None


def inspect_current(root, validator=None):
    """Return integrity findings even when inputs and fingerprints are unchanged."""
    root = Path(root)
    rows = inventory(root)
    result = dict(run_id=None, accepted=False, status='empty' if not managed_paths(root)
                  else 'incomplete', inventory=rows, diagnostics=[])
    try:
        result['run_id'] = recover_run_id(root)
    except (OSError, ContractError) as error:
        result['diagnostics'].append(str(error))
    if result['status'] == 'empty':
        return result
    try:
        require(all(row['availability'] == 'present' for row in rows),
                'current inventory contains missing, corrupt or unreadable items')
        chain = accept_package(root)
        if validator is not None:
            validator(root)
        result.update(accepted=True, status=chain[-1]['status'])
    except (OSError, ContractError) as error:
        result['diagnostics'].append(str(error))
    return result


def verify_archive(archive_root, expected_sha256=None):
    """Verify every claimed retained byte against the archive's own root."""
    archive_root = Path(archive_root)
    raw = _read(archive_root, MANIFEST)
    if expected_sha256 is not None:
        require(sha256_bytes(raw) == expected_sha256, 'archive inventory hash mismatch')
    manifest = parse_json(raw)
    require(manifest.get('schema_version') == 'rci-history-inventory/1' and
            manifest.get('reference_resolution') == 'archive-root-relative', 'unknown history manifest')
    for row in manifest['inventory']:
        if row['sha256'] is not None:
            require(sha256_bytes(_read(archive_root, row['path'])) == row['sha256'],
                    'archive bytes mismatch: ' + row['path'])
        elif row['availability'] == 'missing':
            path = package_path(archive_root, row['path'])
            require(not path.exists() and not path.is_symlink(), 'archive fabricates missing file')
    return Archive(archive_root, sha256_bytes(raw), manifest)


def archive_current(root, run_id, created_at, *, occurrence=False):
    """Archive all available bytes, never overwrite a different existing archive.

    Partial copies remain in history/.pending-* on write error. Publication of
    the archive directory occurs only after its inventory and bytes verify.
    """
    root = Path(root)
    run_id = _safe_id(run_id)
    rows = inventory(root)
    relative = 'history/' + run_id
    if occurrence:
        relative += '/occurrences/' + uuid4().hex
    destination = package_path(root, relative)
    manifest = dict(schema_version='rci-history-inventory/1', run_id=run_id,
                    created_at=created_at, reference_resolution='archive-root-relative',
                    occurrence=occurrence, inventory=rows)
    if destination.exists():
        existing = verify_archive(destination)
        require(existing.manifest['inventory'] == rows,
                'existing archive differs; history preserved and replacement stopped')
        return existing
    pending = package_path(root, 'history/.pending-' + uuid4().hex)
    pending.mkdir(parents=True)
    for row in rows:
        if row['sha256'] is None:
            continue
        data = _read(root, row['path'])
        require(sha256_bytes(data) == row['sha256'], 'current bytes changed during archive')
        _write(pending, row['path'], data)
    _write(pending, MANIFEST, json_bytes(manifest))
    verify_archive(pending)
    # Recheck the source after the copy; a changing source never yields a
    # verified archive authorization for replacement.
    require(inventory(root) == rows, 'current files changed during archive')
    destination.parent.mkdir(parents=True, exist_ok=True)
    require(not destination.exists(), 'archive appeared during copy')
    os.rename(pending, destination)
    descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return verify_archive(destination)
