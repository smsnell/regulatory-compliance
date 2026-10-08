"""U05 register capture handoff check; no semantic mappings or normalization."""
import json

from .anonymous_sheets import csv_rows, discover
from ..source_manifest import disclosed_manifest


def register_readiness(store):
    events = store.inventory()  # Validate journals and exact captured bytes first.
    results = []
    for source in disclosed_manifest():
        if source.adapter != 'google-sheets-read': continue
        reads = sorted((e for e in events if e['attempt']['source_id'] == source.id),
                       key=lambda e: e['attempt']['started_at'])
        row = {'source_id':source.id, 'ready':False, 'blocker':'no-register-capture',
               'permission_status':'not-established', 'tabs':[]}
        results.append(row)
        if not reads: continue
        final = reads[-1]['attempt']
        version = final['version_metadata'] or {}
        details = version.get('returned_identity') or {}
        if final['retrieval_status'] != 'retrieved' or details.get('document_id') != source.document_id:
            row['blocker'] = 'source-unavailable-or-identity-unverified'
            if final['local_reference']:
                try:
                    error = json.loads((store.root/final['local_reference']).read_bytes()).get('error', {})
                    if not version.get('authenticated') and 'unregistered callers' in error.get('message', ''):
                        row['blocker'] = 'missing-caller-authentication'
                except (ValueError, AttributeError): pass
            continue
        if version.get('access_mode') != 'anonymous':
            row['blocker'] = 'anonymous-register-capture-required'
            continue
        pages = [e['attempt'] for e in reads if e['attempt']['content_type'].startswith('text/html')
                 and e['attempt']['retrieval_status'] == 'retrieved']
        if len(pages) < 2 or pages[-1]['version_metadata']['returned_identity'] != pages[0]['version_metadata']['returned_identity']:
            row['blocker'] = 'unverified-capture-consistency'
            continue
        native = {}
        consistent = True
        for page in pages:
            actual = discover((store.root/page['local_reference']).read_bytes(), source)
            if actual != page['version_metadata']['returned_identity'] or any(
                    actual[k] != details[k] for k in ('document_id','title','tabs','revision')):
                consistent = False
            for gid, values in actual['native_rows'].items():
                if gid in native and native[gid] != values: consistent = False
                native[gid] = values
        if not consistent:
            row['blocker'] = 'unverified-capture-consistency'
            continue
        row['permission_status'] = 'anonymous-read-demonstrated'
        expected = details['tabs']
        tab_reads = [e for e in reads if e['attempt']['content_type'].split(';')[0].lower() in {'text/csv','application/csv'}]
        captured = []
        for event in tab_reads:
            a = event['attempt']
            info = (a['version_metadata'] or {}).get('returned_identity', {})
            if a['retrieval_status'] != 'retrieved' or info.get('document_id') != source.document_id: continue
            if info.get('revision') != details.get('revision') or not info.get('native_values_verified'): continue
            tab, = info['tabs']
            rows = csv_rows((store.root/a['local_reference']).read_bytes())
            expected_url = source.route + f"/gviz/tq?gid={tab['sheetId']}&headers=1&tqx=out:csv"
            if a['effective_locator'] != expected_url or rows != native.get(str(tab['sheetId'])): continue
            if len(rows) < 2 or not all(isinstance(cell,str) for cell in rows[0]): continue
            captured.append(tab['sheetId'])
            row['tabs'].append({'sheet_id':tab['sheetId'], 'title':tab['title'],
                'raw_first_row':rows[0], 'data_row_count':len(rows)-1,
                'local_reference':a['local_reference'], 'content_hash':a['content_hash'],
                'locator':'CSV row 1 = raw first row; subsequent rows/cells retain source order',
                'attempt_id':a['id']})
        if sorted(captured) != sorted(t['sheetId'] for t in expected):
            row['blocker'] = 'missing-tab-or-register-row-data'
            continue
        row.update(ready=True, blocker=None, document_id=source.document_id,
                   title=details['title'], revision=details['revision'])
    return {'schema_version':'rci-register-readiness/1',
            'status':'ready' if all(r['ready'] for r in results) else 'blocked',
            'registers':results}
