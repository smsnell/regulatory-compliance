#!/usr/bin/env python3
"""Explicit original-evidence verification; missing originals are a limitation."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

from sanitize_evidence import BUNDLES, build, digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'regulatory-change-impact-brief/scripts'))
from rci.adapters.anonymous_sheets import discover
from rci.adapters.readiness import register_readiness
from rci.contracts import ContractError, require
from rci.evidence import EvidenceStore
from rci.normalize import normalize_registers
from rci.runner import validate_slice
from rci.snapshots import accept_package
from rci.source_manifest import disclosed_manifest


def verify(originals, fixtures):
    manifest = json.loads((fixtures / 'manifest.json').read_bytes())
    for f in manifest['files']:
        original = originals / f['original_path']
        if not original.is_file():
            raise ValueError('LIMITATION: original evidence unavailable: ' + f['original_path'])
        if digest(original.read_bytes()) != f['original_sha256']:
            raise ValueError('Original manifest hash mismatch: ' + f['original_path'])
        if digest((fixtures / f['fixture_path']).read_bytes()) != f['fixture_sha256']:
            raise ValueError('Derivative manifest hash mismatch: ' + f['fixture_path'])
    with tempfile.TemporaryDirectory(prefix='rci-rebuild-') as tmp:
        rebuilt = Path(tmp) / 'fixtures'
        if build(originals, rebuilt) != manifest:
            raise ValueError('Derivative regeneration differs from committed manifest')
    sources = {s.id: s for s in disclosed_manifest()}
    for name, oldpath in BUNDLES.items():
        pairs = [(originals / oldpath, fixtures / name)]
        if name == 'u07':
            pairs = [(p, fixtures / name / '.staging' / p.name)
                     for p in sorted((originals / oldpath / '.staging').iterdir()) if p.is_dir()]
        for old, new in pairs:
            journal = next((old / 'analysis/attempts').glob('*.start.json'))
            run_id = json.loads(journal.read_bytes())['run_id']
            a, b = EvidenceStore(old, run_id), EvidenceStore(new, run_id)
            events = a.inventory()
            b.inventory()
            for e in events:
                attempt = e['attempt']
                if (attempt['content_type'].startswith('text/html')
                        and attempt['retrieval_status'] == 'retrieved'
                        and attempt['source_id'] in {'SYSTEMS', 'EVIDENCE', 'CALENDAR'}):
                    original = (old / attempt['local_reference']).read_bytes()
                    derivative = (new / attempt['local_reference']).read_bytes()
                    source = sources[attempt['source_id']]
                    require(discover(original, source) == discover(derivative, source) == attempt['version_metadata']['returned_identity'],
                            'Original/derivative discovery differs')
            require(register_readiness(a) == register_readiness(b), 'Register readiness differs')
            # Normalization mints IDs; compare semantic values, raw tables and status.
            na, nb = normalize_registers(a), normalize_registers(b)
            require(na['status'] == nb['status'], 'Normalization status differs')
            require(na['raw_tables'] == nb['raw_tables'], 'CSV basis differs')
            require([r['values'] for r in na['normalized_rows']] == [r['values'] for r in nb['normalized_rows']],
                    'Normalized values differ')
            if name == 'u07':
                for store in (a, b):
                    if (store.root / 'snapshots/02-source-capture.json').exists():
                        validate_slice(store)
                    else:
                        require(not list((store.root / 'snapshots').glob('*.json')), 'Failed discovery fabricated snapshots')
                    try:
                        accept_package(store.root)
                    except (ContractError, FileNotFoundError):
                        pass
                    else:
                        raise ValueError('Incomplete U07 unexpectedly accepted as full package')
    print('PASS: originals, derivative hashes, regeneration, discovery/native cells, CSV basis, normalization and U07 slice/failure boundaries.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', required=True, type=Path)
    args = parser.parse_args()
    try:
        verify(args.originals.resolve(), ROOT / 'tests/fixtures/sanitized')
    except (ValueError, AssertionError, OSError) as exc:
        sys.exit(str(exc) or 'Evidence verification failed')
