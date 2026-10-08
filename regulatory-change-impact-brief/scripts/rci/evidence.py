"""U04 local acquisition storage. No adapters, source interpretation or recovery.

One immutable start and one immutable terminal event per attempt. Callers hold
runtime.writer_lock for the isolated run root. Files are created exclusively,
fsynced, and never updated. A removable incomplete-write control guards terminal
persistence; its presence (even malformed) rejects inventory and claims.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import os
from pathlib import Path
from uuid import uuid4

from .contracts import (ContractError, json_bytes, package_path, parse_json,
                        require, sha256_bytes, validate_schema)
from .ids import check_record_id, new_record_id
from .runtime import Providers


@contextmanager
def _parent(root, relative, *, create=False):
    # Validate lexical paths with G1; use directory descriptors to also reject
    # internal symlinks and symlink replacement between validation and opening.
    package_path(root, relative)
    parts = relative.split('/')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd, parts[-1]
    finally:
        os.close(fd)


def _write(root, relative, data):
    """Exclusive durable write. Failed partial files remain unclaimed diagnostics."""
    with _parent(root, relative, create=True) as (parent, name):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent)


def _read(root, relative):
    with _parent(root, relative) as (parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            return stream.read()


def _instant(value):
    return datetime.fromisoformat(value.upper().replace('Z', '+00:00'))


def _representation_metadata(representation, metadata):
    require(isinstance(metadata, dict) and bool(metadata), 'representation metadata required')
    if representation == 'extract':
        require(all(isinstance(metadata.get(k), str) and metadata[k].strip()
                    for k in ('method', 'locator', 'permission')),
                'extract requires method, locator and permission basis')


class EvidenceStore:
    """Per-run store. Bytes passed to finish are the *permitted representation*.

    Extraction/redaction must happen before finish, with representation='extract'
    and explicit metadata. This writer does not claim fidelity to an unretained
    original. Identity, historical suitability and selection are caller decisions.
    """
    def __init__(self, root: Path, run_id: str, providers=None):
        self.root = Path(root)
        require(not self.root.is_symlink() and self.root.is_dir(), 'isolated root must exist')
        require(isinstance(run_id, str) and run_id.startswith('run-'), 'run ID required')
        self.run_id = run_id
        self.providers = providers or Providers()

    def _event_path(self, key, phase):
        require(isinstance(key, str) and len(key) == 32 and
                all(c in '0123456789abcdef' for c in key), 'invalid attempt key')
        return f'analysis/attempts/{key}.{phase}.json'

    def start(self, source_id, original_locator, adapter):
        """Durably persist before the caller dispatches any read."""
        key = uuid4().hex
        record = dict(id=new_record_id(self.run_id, 2, 'attempt'), record_type='attempt',
                      summary='Read attempt for ' + source_id, evidence_ids=[],
                      source_id=source_id, attempt_key=key, original_locator=original_locator,
                      effective_locator=None, adapter=adapter, started_at=self.providers.now(),
                      retrieved_at=self.providers.now(), outcome=None, retrieval_status='unavailable',
                      content_type='application/octet-stream', content_type_known=False,
                      version_metadata=None, content=None, content_hash=None, local_reference=None,
                      identity_check='unverified', date_suitability='unresolved', selected=False,
                      selection_reason='Attempt has not finished', recoverable_failure=None)
        validate_schema(record, 'attempt')
        event = dict(schema_version='rci-attempt-journal/1', run_id=self.run_id,
                     phase='start', attempt=record)
        _write(self.root, self._event_path(key, 'start'), json_bytes(event))
        return key

    def _load(self, key, phase):
        event = parse_json(_read(self.root, self._event_path(key, phase)))
        require(set(event) == {'schema_version', 'run_id', 'phase', 'attempt'} |
                ({'capture', 'diagnostic'} if phase == 'terminal' else set()), 'invalid journal fields')
        require(event['schema_version'] == 'rci-attempt-journal/1' and
                event['run_id'] == self.run_id and event['phase'] == phase, 'wrong journal binding')
        validate_schema(event['attempt'], 'attempt')
        require(event['attempt']['attempt_key'] == key, 'wrong attempt binding')
        check_record_id(event['attempt']['id'], self.run_id, 2, 'attempt')
        if phase == 'terminal':
            diagnostic = event['diagnostic']
            require((diagnostic is not None) == (event['attempt']['recoverable_failure'] is not None),
                    'failure diagnostic mismatch')
            if diagnostic is not None:
                require(isinstance(diagnostic, dict) and set(diagnostic) ==
                        {'stage', 'source_id', 'affected_output', 'failure_type', 'reason',
                         'recovery_action', 'next_owner'}, 'invalid technical diagnostic fields')
                require(diagnostic['stage'] == 'source-capture' and
                        diagnostic['source_id'] == event['attempt']['source_id'], 'wrong diagnostic subject')
                require(all(isinstance(diagnostic[k], str) and diagnostic[k].strip() for k in
                            ('failure_type', 'reason', 'recovery_action')), 'incomplete technical diagnostic')
                require(diagnostic['next_owner'] is None or
                        isinstance(diagnostic['next_owner'], str) and diagnostic['next_owner'].strip(),
                        'invalid next owner')
                if diagnostic['affected_output'] is not None:
                    require(diagnostic['affected_output'].startswith('sources/'), 'wrong diagnostic output')
                    package_path(self.root, diagnostic['affected_output'])
        return event

    def finish(self, key, *, data=None, representation='full', representation_metadata=None,
               content_type=None, retrieved_at=None, effective_locator=None, outcome=None,
               retrieval_status='unverified', version_metadata=None, identity_check='unverified',
               date_suitability='unresolved', selected=False, selection_reason='Not selected',
               recoverable_failure=None, scope_basis_id=None):
        """Close once. Storage failure yields null content and a technical diagnostic.

        If the terminal event itself cannot be persisted, raise; the durable start
        remains incomplete. Never dispatch again or substitute cached bytes.
        """
        start = self._load(key, 'start')['attempt']
        terminal_path = self._event_path(key, 'terminal')
        require(not package_path(self.root, terminal_path).exists(), 'attempt already closed')
        incomplete_path = self._event_path(key, 'incomplete')
        marker = self.root / incomplete_path
        require(not (marker.exists() or marker.is_symlink()),
                'incomplete attempt finalization; fresh run required')
        require(data is None or isinstance(data, bytes), 'retained representation must be bytes')
        require(representation in {'full', 'extract'}, 'invalid representation')
        if data is not None:
            _representation_metadata(representation, representation_metadata)
        json_bytes(representation_metadata)  # Reject nonserializable metadata before storing bytes.
        record = dict(start, retrieved_at=retrieved_at or self.providers.now(),
                      effective_locator=effective_locator, outcome=outcome,
                      retrieval_status=retrieval_status, version_metadata=version_metadata,
                      content_type='application/octet-stream' if content_type is None else content_type,
                      content_type_known=content_type is not None, identity_check=identity_check,
                      date_suitability=date_suitability, selected=selected,
                      selection_reason=selection_reason, recoverable_failure=recoverable_failure)
        if scope_basis_id is not None:
            record['scope_basis_id'] = scope_basis_id
        if data is not None:
            record.update(content=representation, local_reference=f'sources/{key}.bin',
                          content_hash=sha256_bytes(data))
        validate_schema(record, 'attempt')
        require(_instant(record['started_at']) <= _instant(record['retrieved_at']), 'attempt ends before start')
        require(retrieval_status != 'retrieved' or data is not None, 'retrieved requires obtained content')
        capture = None
        diagnostic = (dict(stage='source-capture', source_id=start['source_id'],
                           affected_output=None, failure_type='ReadFailure',
                           reason=recoverable_failure,
                           recovery_action='Preserve failed run; rerun with fresh source attempts',
                           next_owner=None) if recoverable_failure else None)
        interrupted = None
        # Persist the guard first. A fully written terminal JSON is not proof
        # that its file/directory fsync succeeded; any failure leaves this guard.
        _write(self.root, incomplete_path, json_bytes(dict(
            schema_version='rci-attempt-write/1', run_id=self.run_id, attempt_key=key,
            stage='source-capture', source_id=start['source_id'], affected_output=terminal_path,
            failure_type='IncompleteTerminalWrite', reason='Terminal persistence has not completed',
            recovery_action='Preserve failed run; rerun with fresh source attempts', next_owner=None)))
        if data is not None:
            try:
                _write(self.root, record['local_reference'], data)
                require(_read(self.root, record['local_reference']) == data, 'retained bytes differ')
                capture = dict(id=new_record_id(self.run_id, 2, 'capture'), record_type='capture',
                               summary='Retained representation for ' + start['source_id'], evidence_ids=[],
                               attempt_id=record['id'], representation=representation,
                               local_reference=record['local_reference'], content_hash=record['content_hash'],
                               content_type=record['content_type'], representation_metadata=deepcopy(representation_metadata))
                validate_schema(capture, 'capture')
            except (OSError, ContractError, KeyboardInterrupt, SystemExit) as error:
                # Partial files are preserved but never bound as complete source content.
                diagnostic = dict(stage='source-capture', source_id=start['source_id'],
                                  affected_output=record['local_reference'], failure_type=type(error).__name__,
                                  reason='Retained representation could not be durably verified',
                                  recovery_action='Preserve failed run; rerun with fresh source attempts',
                                  next_owner=None)
                record.update(content=None, content_hash=None, local_reference=None,
                              retrieval_status='unavailable', selected=False,
                              selection_reason='Representation storage failed',
                              recoverable_failure='Technical capture storage failure')
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    interrupted = error
        event = dict(schema_version='rci-attempt-journal/1', run_id=self.run_id, phase='terminal',
                     attempt=record, capture=capture, diagnostic=diagnostic)
        _write(self.root, terminal_path, json_bytes(event))
        with _parent(self.root, incomplete_path) as (parent, name):
            os.unlink(name, dir_fd=parent)
        # No fsync after removing the guard: the terminal and its directory are
        # already durable. A crash can only restore the guard and reject a
        # complete attempt conservatively, never admit an undurable terminal.
        if interrupted is not None:
            raise interrupted
        return deepcopy(event)

    def acquire(self, source_id, original_locator, adapter, read):
        """Dispatch only after start. read() returns keyword arguments for finish.

        Transport failures/interruptions close with no invented response; exception
        messages are omitted to avoid retaining credentials. Control exceptions
        are re-raised after recording the terminal outcome.
        """
        key = self.start(source_id, original_locator, adapter)
        try:
            response = read()
        except BaseException as error:
            self.finish(key, retrieval_status='unavailable', outcome=type(error).__name__,
                        recoverable_failure='Read failed or interrupted',
                        selection_reason='No response obtained')
            raise
        try:
            return self.finish(key, **response)
        except (Exception, KeyboardInterrupt, SystemExit) as error:
            # Invalid adapter output is a technical failure, not a source response.
            marker = self.root / self._event_path(key, 'incomplete')
            if not (package_path(self.root, self._event_path(key, 'terminal')).exists()
                    or marker.exists() or marker.is_symlink()):
                self.finish(key, outcome=type(error).__name__,
                            recoverable_failure='Adapter output or capture finalization failed',
                            selection_reason='No verifiable retained response')
            raise

    def inventory(self):
        """Independently verify every outcome. Pending/corrupt entries reject freeze."""
        try:
            with _parent(self.root, 'analysis/attempts/inventory') as (directory, _):
                names = set(os.listdir(directory))
        except FileNotFoundError:
            return []
        keys = set()
        for name in names:
            parts = name.split('.')
            require(not name.endswith('.incomplete.json'),
                    'incomplete terminal persistence; cannot freeze source capture')
            require(len(parts) == 3 and parts[1] in {'start', 'terminal'} and parts[2] == 'json',
                    'unexpected journal entry')
            self._event_path(parts[0], parts[1])
            keys.add(parts[0])
        results = []
        ids = set()
        for key in sorted(keys):
            require({f'{key}.start.json', f'{key}.terminal.json'} <= names,
                    'incomplete attempt journal; cannot freeze source capture')
            start = self._load(key, 'start')['attempt']
            event = self._load(key, 'terminal')
            attempt, capture = event['attempt'], event['capture']
            require(all(start[k] == attempt[k] for k in
                        ('id', 'source_id', 'attempt_key', 'original_locator', 'adapter', 'started_at')),
                    'terminal changes original attempt')
            require(attempt['id'] not in ids, 'duplicate attempt ID')
            ids.add(attempt['id'])
            require(_instant(start['started_at']) <= _instant(attempt['retrieved_at']), 'invalid chronology')
            present = attempt['content'] is not None
            require(present == (attempt['local_reference'] is not None) ==
                    (attempt['content_hash'] is not None) == (capture is not None), 'content/null mismatch')
            require(attempt['content_type_known'] or attempt['content_type'] == 'application/octet-stream',
                    'unknown MIME must be explicit')
            require(attempt['retrieval_status'] != 'retrieved' or present, 'retrieved without content')
            if capture is not None:
                validate_schema(capture, 'capture')
                check_record_id(capture['id'], self.run_id, 2, 'capture')
                require(capture['id'] not in ids, 'duplicate capture ID')
                ids.add(capture['id'])
                _representation_metadata(capture['representation'], capture['representation_metadata'])
                require(capture['attempt_id'] == attempt['id'] and capture['representation'] == attempt['content'] and
                        all(capture[k] == attempt[k] for k in ('local_reference', 'content_hash', 'content_type')),
                        'capture/attempt mismatch')
                require(capture['local_reference'].startswith('sources/'), 'capture outside sources')
                require(sha256_bytes(_read(self.root, capture['local_reference'])) == capture['content_hash'],
                        'retained hash mismatch')
            results.append(event)
        return results

    def claim(self, capture, *, locator, assertion, quoted_support):
        """Bind a claim to a verified capture; quotation checks do not prove meaning."""
        require(any(e['capture'] == capture for e in self.inventory()), 'capture not in verified journal')
        raw = _read(self.root, capture['local_reference'])
        require(sha256_bytes(raw) == capture['content_hash'], 'claim retained hash mismatch')
        if capture['content_type'].split(';', 1)[0].strip().lower().startswith('text/'):
            require(quoted_support in raw.decode('utf-8'), 'quote absent from retained text')
        record = dict(id=new_record_id(self.run_id, 2, 'evidence'), record_type='evidence',
                      summary=assertion, evidence_ids=[], capture_id=capture['id'],
                      local_reference=capture['local_reference'], content_hash=capture['content_hash'],
                      locator=deepcopy(locator), assertion=assertion, quoted_support=quoted_support)
        validate_schema(record, 'evidence')
        return record
