#!/usr/bin/env python3
"""U05 connection spike only; no snapshots or later stage engines."""
import argparse
import json
from pathlib import Path

from rci.adapters import ReadAdapters
from rci.adapters.readiness import register_readiness
from rci.contracts import json_bytes
from rci.evidence import EvidenceStore, _write
from rci.runtime import Providers, writer_lock
from rci.source_manifest import credential_inventory, disclosed_manifest


def check_sources(output, credentials=None, *, sheets_access='anonymous'):
    providers = Providers()
    run_id = providers.run_id()
    with writer_lock(output):
        root = output/run_id
        root.mkdir(mode=0o700)
        store = EvidenceStore(root, run_id, providers)
        reader = ReadAdapters(store, credentials=credentials, sheets_access=sheets_access)
        rows = []
        try:
            for source in disclosed_manifest():
                events = reader.read(source)
                last = events[-1]['attempt']
                rows.append({'source_id': source.id, 'requested_locator': source.route,
                             'adapter': source.adapter, 'attempt_ids': [e['attempt']['id'] for e in events],
                             'retrieval_status': last['retrieval_status'],
                             'identity_check': last['identity_check'],
                             'date_suitability': last['date_suitability'],
                             'version_metadata': last['version_metadata'],
                             'reason': last['recoverable_failure'],
                             'local_reference': last['local_reference'], 'content_hash': last['content_hash']})
            store.inventory()  # Independently check every stored representation.
            report = {'schema_version': 'rci-source-access/1', 'run_id': run_id,
                      'assigned_review_date': '2026-08-26', 'production_package': False,
                      'sources': rows, 'register_readiness': register_readiness(store)}
            _write(root, 'analysis/source-access.json', json_bytes(report))
        finally:
            reader.close()
    return root, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--credential-inventory', type=Path)
    parser.add_argument('--sheets-access', choices=['anonymous','api'], default='anonymous')
    parser.add_argument('--require-registers', action='store_true',
                        help='Exit 3 unless all three anonymous register captures are ready')
    args = parser.parse_args()
    # Connection checks use a dedicated new candidate root; never current outputs.
    from rci.runtime import REPO
    output = args.output.resolve()
    if output.is_relative_to(REPO.resolve()):
        parser.error('connection spike output must be outside repository inputs/current outputs')
    credentials = credential_inventory(args.credential_inventory)
    root, report = check_sources(output, credentials, sheets_access=args.sheets_access)
    print(json.dumps({'report': str(root/'analysis/source-access.json'),
                      'sources_attempted': len(report['sources']),
                      'register_readiness': report['register_readiness']['status'], 'production_package': False}))
    return 3 if args.require_registers and report['register_readiness']['status'] != 'ready' else 0


if __name__ == '__main__':
    raise SystemExit(main())
