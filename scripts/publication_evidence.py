#!/usr/bin/env python3
"""Build/verify an explicitly labeled publication derivative, never a new run.

Originals must be an external, preserved index export with preservation.json.
Uses existing extract metadata, package validators and artifact renderers.
No network, acquisition, interpretation, review delivery or credential output.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile

from sanitize_evidence import KEY, MARKER, FRONTEND_TOKEN, digest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'regulatory-change-impact-brief/scripts'))
from rci.contracts import json_bytes, require, SNAPSHOT_PATHS
from rci.actions import build_export_model
from rci.adapters.anonymous_sheets import discover
from rci.adapters.reads import Page
from rci.evidence import EvidenceStore
from rci.history import verify_archive
from rci.source_manifest import disclosed_manifest
from rci.validate import validate_package
from rci.renderers.brief import render as render_brief
from rci.renderers.csv_register import render as render_csv
from rci.renderers.calendar import render as render_calendar

VERSION = 'rci-publication-derivative/1'
NOTICE = ('PUBLICATION DERIVATIVE: sanitized retained evidence, not untouched HTTP responses or a new execution. '
          'Run/record/snapshot IDs and acquisition times identify the original occurrence only. '
          'See PUBLICATION.json and the submission-root publication-manifest.json for original/derivative hashes and limitations.')
SCRIPT = re.compile(rb'<script\b[^>]*>.*?</script\s*>', re.I | re.S)
# These are observations of the original execution, not assertions about the
# derivative's bytes or a claim that local candidate paths are published.
HISTORICAL = {'analysis/prior-inspection.json', 'analysis/stage-fingerprints.json',
              'analysis/recomputation.json', 'analysis/run-context.json', 'analysis/outcome.json'}


def original_files(originals):
    require(not originals.resolve().is_relative_to(REPO), 'Original storage must be outside repository')
    inventory = originals / 'preservation.json'
    require(inventory.is_file(), 'LIMITATION: original preservation inventory unavailable')
    rows = json.loads(inventory.read_bytes())['files']
    files = {}
    for row in rows:
        if not row['path'].startswith('deliverables/'):
            continue
        path = Path(row['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'Unsafe preservation path')
        source = originals / path
        require(source.is_file() and not source.is_symlink(), 'LIMITATION: original file unavailable: ' + str(path))
        data = source.read_bytes()
        require(digest(data) == row['sha256'] and len(data) == row['size'], 'Original preservation mismatch: ' + str(path))
        files[path.relative_to('deliverables').as_posix()] = data
    require(files, 'No original deliverables')
    return files


def clean_capture(raw):
    clean, keys = KEY.subn(MARKER, raw)
    clean, tokens = FRONTEND_TOKEN.subn(rb'\1REDACTED\2', clean)
    scripts = 0
    if b'gokuProps' in raw:
        clean, scripts = SCRIPT.subn(b'<!-- WAF challenge script omitted in publication extract -->', clean)
        require(scripts > 0 and b'gokuProps' not in clean, 'WAF extraction incomplete')
    if clean != raw:
        a, b = Page(raw), Page(clean)
        require((a.title, a.text, a.headings) == (b.title, b.text, b.headings), 'Visible source content changed')
    return clean, dict(google_occurrences=keys, maestro_fields=tokens, waf_script_elements=scripts)


def rewrite(value, hashes, altered):
    if isinstance(value, str):
        for old, new in hashes.items():
            value = value.replace(old, new)
        for old in altered:
            value = value.replace(':full:' + hashes[old], ':extract:' + hashes[old])
        return value
    if isinstance(value, list):
        result = [rewrite(v, hashes, altered) for v in value]
        # Source versions are constructed as a sorted set by the existing exporter.
        if result and all(isinstance(v, str) and v.startswith('captured-source:') for v in result):
            result = sorted(set(result))
        return result
    if not isinstance(value, dict):
        return value
    old_hash = value.get('content_hash')
    result = {k: rewrite(v, hashes, altered) for k, v in value.items()}
    if old_hash in altered:
        if result.get('content') == 'full':
            result['content'] = 'extract'
        if result.get('record_type') == 'capture':
            result['representation'] = 'extract'
            result['representation_metadata'] = {
                'method': 'Publication extraction: credential fields redacted; WAF scripts omitted where present',
                'locator': result['local_reference'],
                'permission': 'Owner-authorized publication remediation; no redistribution of credential values',
                'original_sha256': old_hash,
                'original_availability': 'Restricted local storage; not included in public repository',
                'publication_notice': NOTICE,
            }
    return result


def build(originals, output):
    require(not output.exists(), 'Output must be a new directory')
    files = original_files(originals)
    require(not output.resolve().is_relative_to(originals.resolve()), 'Output overlaps original storage')
    output.mkdir(parents=True)
    hashes, altered, counts = {}, set(), {}
    for name, raw in files.items():
        clean, count = clean_capture(raw) if '/sources/' in '/' + name and name.endswith('.bin') else (raw, {})
        if clean != raw:
            hashes[digest(raw)] = digest(clean)
            altered.add(digest(raw))
            counts[name] = count
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(clean)

    roots = sorted({str(Path(name).parent.parent) for name in files if name.endswith('/snapshots/01-scope.json')}) + ['.']
    roots = list(dict.fromkeys(roots))
    for relative in roots:
        base = output / relative
        prefix = '' if relative == '.' else relative + '/'
        local = {name[len(prefix):]: raw for name, raw in files.items()
                 if name.startswith(prefix) and not name[len(prefix):].startswith('history/')}

        def write(name, data):
            path = base / name
            path.write_bytes(data)
            if name in local and local[name] != data:
                hashes[digest(local[name])] = digest(data)

        require(not any('feedback-input' in n for n in local), 'Feedback cannot be rebound')

        def rebind_analysis():
            # Requests depend on prior snapshots; responses/submission envelopes
            # depend on exact request bytes. Always derive from originals, never
            # claim the rebound envelopes were actually sent to the original host.
            for _ in range(12):
                before = dict(hashes)
                for name, raw in local.items():
                    if not name.startswith('analysis/') or not name.endswith('.json') or name in HISTORICAL:
                        continue
                    if name in {'analysis/config.json', 'analysis/producer-code.json'}:
                        continue
                    obj = json.loads(raw)
                    updated = rewrite(obj, hashes, altered)
                    write(name, raw if obj == updated else json_bytes(updated))
                if before == hashes:
                    return
            raise ValueError('Analysis hash dependencies did not converge')

        chain = []
        for seq, name in enumerate(SNAPSHOT_PATHS, 1):
            rebind_analysis()
            raw = local[name]
            old = json.loads(raw)
            snap = rewrite(old, hashes, altered)
            if seq == 6:
                state = snap['state']
                require(not state['feedback'] and not state['proposed_actions'] and not state['approval_requirements'],
                        'Publication plan limited to existing blocked draft without actions/feedback')
                require(all(r['delivery_status'] == 'not-sent' for r in state['review_requests']), 'Delivered review cannot be rebound')
                model = build_export_model(chain, state, snap['status'])
                for request in state['review_requests']:
                    request['source_versions'] = model['source_versions']
                    request['draft_version'] = model['draft_version']
                state['export_model'] = build_export_model(chain, state, snap['status'])
                hashes[old['state']['export_model']['draft_version']] = state['export_model']['draft_version']
            if seq == 7:
                model = chain[5]['state']['export_model']
                rendered = {'compliance-brief.md': render_brief(model),
                            'impact-register.csv': render_csv(model),
                            'action-calendar.ics': render_calendar(model)}
                for path, data in rendered.items():
                    if isinstance(data, str): data = data.encode()
                    write(path, data)
                snap = rewrite(old, hashes, altered)
                snap['state']['extensions']['publication_model']['value']['export_fingerprint'] = digest(json_bytes(model))
            write(name, raw if old == snap else json_bytes(snap))
            chain.append(snap)
        rebind_analysis()

        # The inventory describes this derivative history view. Original archive
        # inventory remains byte-exact in external storage and the lineage manifest.
        if '.history-inventory.json' in local:
            inv = rewrite(json.loads(local['.history-inventory.json']), hashes, altered)
            for row in inv['inventory']:
                if row['sha256'] is not None:
                    data = (base / row['path']).read_bytes()
                    row['sha256'], row['size'] = digest(data), len(data)
            write('.history-inventory.json', json_bytes(inv))

        (base / 'PUBLICATION.json').write_bytes(json_bytes({
            'schema_version': VERSION, 'notice': NOTICE, 'original_run_id': chain[0]['run_id'],
            'new_execution': False, 'originals_published': False,
            'original_storage': str(originals),
            'lineage_manifest_relative_path': 'publication-manifest.json' if relative == '.' else '../../publication-manifest.json',
            'historical_execution_records': sorted(HISTORICAL & local.keys()),
            'history_semantics': 'Sanitized publication view; original exact-byte archive is restricted, not this directory',
            'interpretation_semantics': 'Rebound request/response envelopes are publication derivatives only; no new host execution. Original prompts/events/times describe restricted original inputs. Candidate meanings and quoted extracts are unchanged.',
            'verification_boundary': 'Public bytes support derivative validation. Full original-to-derivative lineage requires restricted originals; missing originals is a LIMITATION.',
        }))
        (base / 'PUBLICATION.md').write_text(
            '# Publication derivative\n\n' + NOTICE + '\n\n'
            'All files in this package must be read with this notice. The brief, CSV and calendar are '
            'regenerated artifacts of the sanitized representation. Their exact format is enforced by the existing validator. '
            'The original execution remains blocked; no human approval is implied. '
            'Original execution records and host logs describe the original inputs, not a new execution of this derivative.\n')

    rows = []
    for name, raw in files.items():
        new = (output / name).read_bytes()
        rows.append(dict(path=name, original_sha256=digest(raw), derivative_sha256=digest(new),
                         original_size=len(raw), derivative_size=len(new), transformed=raw != new,
                         redactions=counts.get(name, {})))
    generated = {str(p.relative_to(output)): digest(p.read_bytes())
                 for p in output.rglob('PUBLICATION.*')}
    manifest = dict(schema_version=VERSION, notice=NOTICE, files=rows, generated_files=generated,
                    preserved_inventory_sha256=digest((originals / 'preservation.json').read_bytes()),
                    original_storage=str(originals), originals_published=False)
    (output / 'publication-manifest.json').write_bytes(json_bytes(manifest))
    return manifest


def verify(originals, output):
    # Do not let tempfile silently fall back to the nearly-full /tmp volume.
    tempfile.tempdir = str(Path.home() / '.cache/rci-secret-scan')
    files = original_files(originals)
    manifest = json.loads((output / 'publication-manifest.json').read_bytes())
    require(manifest['preserved_inventory_sha256'] == digest((originals / 'preservation.json').read_bytes()), 'Preservation manifest changed')
    require({r['path'] for r in manifest['files']} == set(files), 'Missing publication evidence')
    for row in manifest['files']:
        require(digest(files[row['path']]) == row['original_sha256'], 'Original hash mismatch')
        require(digest((output / row['path']).read_bytes()) == row['derivative_sha256'], 'Derivative hash mismatch: ' + row['path'])
    mapping = {r['original_sha256']: r['derivative_sha256'] for r in manifest['files'] if r['transformed']}
    for name, expected in manifest['generated_files'].items():
        require(digest((output / name).read_bytes()) == expected, 'Publication notice changed')
    with tempfile.TemporaryDirectory(prefix='rci-publication-rebuild-') as temp:
        rebuilt = Path(temp) / 'derivative'
        require(build(originals, rebuilt) == manifest, 'Deterministic derivative regeneration differs')
        for path in rebuilt.rglob('*'):
            if path.is_file():
                require(path.read_bytes() == (output / path.relative_to(rebuilt)).read_bytes(), 'Regenerated bytes differ')
    sources = {s.id: s for s in disclosed_manifest()}
    results = []
    for base in sorted(output.glob('history/run-*')) + [output]:
        relative = base.relative_to(output)
        original = originals / 'deliverables' / relative
        chain = validate_package(base)
        old_chain = validate_package(original)
        store = EvidenceStore(base, chain[0]['run_id'])
        events = store.inventory()
        old_events = EvidenceStore(original, chain[0]['run_id']).inventory()
        require(len(events) == len(old_events), 'Attempt omitted')
        for new, old in zip(events, old_events):
            for key in old['attempt']:
                if key not in {'content', 'content_hash'}:
                    require(new['attempt'][key] == old['attempt'][key], 'Attempt outcome/identity/time changed: ' + key)
            attempt = old['attempt']
            if (attempt['source_id'] in {'SYSTEMS', 'EVIDENCE', 'CALENDAR'} and
                    attempt['content_type'].startswith('text/html') and attempt['retrieval_status'] == 'retrieved'):
                path = attempt['local_reference']
                require(discover((original / path).read_bytes(), sources[attempt['source_id']]) ==
                        discover((base / path).read_bytes(), sources[attempt['source_id']]), 'Native spreadsheet semantics changed')
        for old, new in zip(old_chain, chain):
            require(old['status'] == new['status'] and old['unresolved'] == new['unresolved'], 'Findings or state changed')
        require(chain[1]['state']['normalized_rows'] == old_chain[1]['state']['normalized_rows'], 'Normalized findings changed')
        require(chain[2]['state']['authority_blockers'] == old_chain[2]['state']['authority_blockers'], 'Authority blockers changed')
        require(chain[3]['state'] == rewrite(old_chain[3]['state'], mapping, set()) and
                chain[4]['state'] == rewrite(old_chain[4]['state'], mapping, set()), 'Reconciliation/impact findings changed')
        require(chain[5]['state']['export_model']['unresolved_coverage'] == old_chain[5]['state']['export_model']['unresolved_coverage'], 'Unresolved coverage changed')
        for path in original.glob('analysis/**/request.json'):
            old_request = json.loads(path.read_bytes())
            new_request = json.loads((base / path.relative_to(original)).read_bytes())
            if old_request.get('schema_version') == 'rci-interpretation-request/1':
                require(old_request['extracts'] == new_request['extracts'], 'Interpretation claim-bearing text changed')
        for path in original.glob('analysis/**/response.json'):
            old_response = json.loads(path.read_bytes())
            new_response = json.loads((base / path.relative_to(original)).read_bytes())
            require({k:v for k,v in old_response.items() if k != 'packet_sha256'} ==
                    {k:v for k,v in new_response.items() if k != 'packet_sha256'}, 'Interpretation meaning changed')
        if relative != Path('.'):
            verify_archive(base)
        results.append(dict(root=str(relative), run_id=chain[0]['run_id'], status=chain[-1]['status'],
                            publication_status=chain[-1]['state']['publication_status'],
                            attempts=len(events), captures=len(chain[1]['state']['captures']),
                            unresolved_coverage=len(chain[5]['state']['export_model']['unresolved_coverage']),
                            review_requests=len(chain[5]['state']['review_requests'])))
    return dict(original_lineage='verified with restricted originals', derivative_packages='verified', packages=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['build', 'verify'])
    parser.add_argument('--originals', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.operation == 'build':
        result = build(args.originals.resolve(), args.output.resolve())
        print(json.dumps({'files': len(result['files']), 'transformed': sum(r['transformed'] for r in result['files'])}))
    else:
        print(json.dumps(verify(args.originals.resolve(), args.output.resolve()), indent=2))
