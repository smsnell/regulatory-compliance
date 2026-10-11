"""Fresh rerun classification and detectable, non-atomic package promotion.

The launcher runs all stages with fresh reads before calling promotion. A
failed promotion is retained; this module never resumes an old computation.
"""
from contextlib import nullcontext
import os
from pathlib import Path
import shutil
from uuid import uuid4

from .contracts import (CONTRACT_VERSION, SNAPSHOT_PATHS, STAGES, json_bytes,
                        package_path, parse_json, require, sha256_bytes)
from .evidence import _read, _write
from .history import (MANAGED_DIRECTORIES, MANAGED_FILES, archive_current,
                      inventory, managed_paths, recover_run_id, verify_archive)
from .runtime import writer_lock
from .snapshots import (COMPLETION_MARKER, INCOMPLETE_MARKER, read_chain,
                        validate_marker)

FINGERPRINT_PATH = 'analysis/stage-fingerprints.json'


def stage_fingerprints(bases):
    """Hash substantive stage bases; caller excludes occurrence IDs/times.

    Each stage must declare its complete input basis, including its scoped
    config, code/contract version and upstream content/mapping dependencies.
    """
    require(set(bases) == set(STAGES), 'all seven stage fingerprint bases required')
    return dict(schema_version='rci-stage-fingerprints/1', contract_version=CONTRACT_VERSION,
                dependencies={stage:list(STAGES[:i]) for i, stage in enumerate(STAGES)},
                fingerprints={stage:sha256_bytes(json_bytes(bases[stage])) for stage in STAGES})


def classify_change(previous, current):
    """Classify the earliest changed basis while always requiring full rerun."""
    require(current.get('schema_version') == 'rci-stage-fingerprints/1' and
            set(current.get('fingerprints', {})) == set(STAGES), 'invalid current fingerprints')
    if previous is None:
        sequence, reason = 1, 'no prior stage fingerprints'
    elif previous.get('schema_version') != current['schema_version'] or \
            previous.get('contract_version') != current.get('contract_version'):
        sequence, reason = 1, 'contract/fingerprint version changed'
    else:
        changed = [i + 1 for i, stage in enumerate(STAGES)
                   if previous.get('fingerprints', {}).get(stage) != current['fingerprints'][stage] or
                   previous.get('dependencies', {}).get(stage) != current.get('dependencies', {}).get(stage)]
        sequence = min(changed) if changed else None
        reason = 'stage input basis changed' if sequence else 'substantive stage bases unchanged'
    return dict(earliest_changed_sequence=sequence,
                earliest_changed_stage=STAGES[sequence - 1] if sequence else None,
                reason=reason, recompute_sequences=list(range(1, 8)),
                fresh_source_attempts_required=True, current_file_inspection_required=True)


def _sync_parent(path):
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace_file(root, relative, data):
    """Persist one file; the incomplete marker guards the whole replacement."""
    target = package_path(root, relative)
    temporary = relative + '.promotion-' + uuid4().hex
    _write(root, temporary, data)
    os.replace(package_path(root, temporary), target)
    _sync_parent(target)


def _remove_managed(root):
    # This runs only after archive verification and durable marker creation.
    # Unrelated output-root files and .staging/history are outside ownership.
    for relative in sorted(managed_paths(root), reverse=True):
        if relative in {INCOMPLETE_MARKER, COMPLETION_MARKER}:
            continue
        target = root / relative
        target.unlink()
    for name in MANAGED_DIRECTORIES:
        directory = root / name
        if directory.is_dir():
            for child in sorted(directory.rglob('*'), key=lambda p:len(p.parts), reverse=True):
                if child.is_dir() and not child.is_symlink():
                    child.rmdir()
            directory.rmdir()


def _verification_view(root):
    """Copy actual current bytes for validators that reject control markers.

    The incomplete marker stays visible to every public reader. No candidate
    bytes are substituted for damaged current bytes in the verification view.
    """
    view = package_path(root, '.staging/.verification-' + uuid4().hex)
    view.mkdir(parents=True)
    rows = inventory(root)
    for row in rows:
        if row['sha256'] is None or row['path'] in {INCOMPLETE_MARKER, COMPLETION_MARKER}:
            continue
        data = _read(root, row['path'])
        require(sha256_bytes(data) == row['sha256'], 'current changed during independent verification')
        _write(view, row['path'], data)
    return view, rows


def _verify_chain_result(chain, new_run_id):
    require(isinstance(chain, list) and len(chain) == 7 and
            all(s['run_id'] == new_run_id and s['sequence'] == i + 1 and
                s['stage'] == STAGES[i] for i, s in enumerate(chain)),
            'validator did not return seven stages of the new run')


def _merge_history_dependencies(root, candidate, candidate_rows):
    """Install only explicitly referenced retained packages, by exact bytes."""
    for row in candidate_rows:
        path = row['path']
        if not path.startswith('history/') or row['sha256'] is None:
            continue
        data = _read(candidate, path)
        require(sha256_bytes(data) == row['sha256'], 'candidate history dependency changed')
        destination = package_path(root, path)
        if destination.exists() or destination.is_symlink():
            require(_read(root, path) == data,
                    'existing history dependency differs; history preserved: ' + path)
        else:
            _write(root, path, data)


def preserve_interrupted(root, created_at):
    """Preserve the marker, mixed current bytes and prior archive before retry.

    Returns a verified failed-occurrence archive. Never clears the marker.
    """
    root = Path(root)
    marker = parse_json(_read(root, INCOMPLETE_MARKER))
    validate_marker(marker, 'incomplete-marker', root)
    if marker['archive'] is not None:
        reference = marker['archive']
        verify_archive(package_path(root, reference['root']), reference['inventory_sha256'])
    run_id = marker['new_run_id']
    canonical = package_path(root, 'history/' + run_id)
    return archive_current(root, run_id, created_at, occurrence=canonical.exists())


def promote_candidate(root, candidate, *, new_run_id, created_at, validator=read_chain,
                      allow_completion=True, lock_held=False):
    """Promote a verified fresh candidate and validate copied current bytes.

    validator(Path) returns seven validated snapshot dictionaries; production
    callers pass the independent U17 artifact validator. If already running
    under runtime.writer_lock, set lock_held=True to keep one lock for the run.
    Every write exception propagates with evidence and control marker retained.
    """
    root, candidate = Path(root), Path(candidate)
    with nullcontext() if lock_held else writer_lock(root):
        require(candidate.resolve() == package_path(root, '.staging/' + new_run_id) and
                candidate.is_dir() and not candidate.is_symlink(), 'candidate must be isolated under new run ID')
        chain = validator(candidate)
        _verify_chain_result(chain, new_run_id)
        final = chain[-1]
        candidate_rows = inventory(candidate)
        require(all(row['availability'] == 'present' or
                    (row['availability'] == 'missing' and
                     final['state']['publication_status'] == 'blocked' and
                     row['path'] in {item['path'] for item in final['state']['missing_artifacts']})
                    for row in candidate_rows), 'candidate inventory contains damaged or unaccounted missing items')
        stage07_hash = sha256_bytes(_read(candidate, SNAPSHOT_PATHS[-1]))
        old_run_id = recover_run_id(root)
        require(old_run_id != new_run_id, 'replacement must use a fresh run ID')
        has_current = bool(managed_paths(root))
        require(not has_current or old_run_id is not None,
                'no trustworthy prior run ID; current files preserved and replacement stopped')
        interrupted = (root / INCOMPLETE_MARKER).exists() or (root / INCOMPLETE_MARKER).is_symlink()
        archive = None
        if interrupted:
            failed = preserve_interrupted(root, created_at)
            # The failed occurrence has a canonical package root for the frozen
            # marker contract. An existing canonical copy is also independently
            # verified; new changed occurrences live beneath it.
            archive = verify_archive(package_path(root, 'history/' + old_run_id))
            require(failed.root.exists(), 'failed occurrence was not preserved')
        elif old_run_id is not None:
            archive = archive_current(root, old_run_id, created_at)
        _merge_history_dependencies(root, candidate, candidate_rows)
        marker = dict(schema_version='rci-incomplete-replacement/1', old_run_id=old_run_id,
                      new_run_id=new_run_id, created_at=created_at,
                      archive=archive.marker_reference(root) if archive else None,
                      candidate=dict(root='.staging/' + new_run_id,
                                     stage07_sha256=stage07_hash, verified=True))
        validate_marker(marker, 'incomplete-marker', root)
        require(inventory(candidate) == candidate_rows, 'verified candidate changed before replacement')
        if interrupted:
            _replace_file(root, INCOMPLETE_MARKER, json_bytes(marker))
        else:
            _write(root, INCOMPLETE_MARKER, json_bytes(marker))
        # Re-read durable control before any managed output is changed.
        require(_read(root, INCOMPLETE_MARKER) == json_bytes(marker), 'incomplete marker persistence failed')
        completion = root / COMPLETION_MARKER
        if completion.exists() or completion.is_symlink():
            completion.unlink()
            _sync_parent(completion)
        _remove_managed(root)
        for row in candidate_rows:
            path = row['path']
            if row['sha256'] is None or path in {COMPLETION_MARKER, INCOMPLETE_MARKER} or path.startswith('history/'):
                continue
            data = _read(candidate, path)
            require(sha256_bytes(data) == row['sha256'], 'candidate changed during copy: ' + path)
            _replace_file(root, path, data)
        view, current_rows = _verification_view(root)
        verified_chain = validator(view)
        _verify_chain_result(verified_chain, new_run_id)
        require(verified_chain == chain, 'copied current chain differs from verified candidate')
        require(sha256_bytes(_read(root, SNAPSHOT_PATHS[-1])) == stage07_hash,
                'copied Stage 07 differs from candidate')
        require(inventory(root) == current_rows, 'current changed after independent verification')
        require(inventory(candidate) == candidate_rows, 'candidate changed during replacement')
        shutil.rmtree(view)
        completed = allow_completion and final['state']['publication_status'] == 'validated' and \
                    final['status'] in {'complete', 'partial'}
        if completed:
            completion_value = dict(schema_version='rci-completion/1', run_id=new_run_id,
                                    completed_at=created_at,
                                    stage07=dict(snapshot_id=final['snapshot_id'], path=SNAPSHOT_PATHS[-1],
                                                 sha256=stage07_hash))
            validate_marker(completion_value, 'completion-marker', root)
            _write(root, COMPLETION_MARKER, json_bytes(completion_value))
            require(_read(root, COMPLETION_MARKER) == json_bytes(completion_value),
                    'completion marker persistence failed')
        (root / INCOMPLETE_MARKER).unlink()
        _sync_parent(root / INCOMPLETE_MARKER)
        return dict(run_id=new_run_id, status=final['status'], completed=completed,
                    archive_root=archive.root.relative_to(root).as_posix() if archive else None,
                    candidate_root=candidate.relative_to(root).as_posix(), stage07_sha256=stage07_hash)
