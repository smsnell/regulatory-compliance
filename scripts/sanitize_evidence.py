#!/usr/bin/env python3
"""Build explicitly derivative replay bundles from externally preserved originals.

Never edits originals. Output must not exist. No secret values are logged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


BUNDLES = {
    'u05': 'docs/verification/u05-anonymous-live',
    'u05-errors': 'docs/verification/u05-live',
    'u07': 'u07-verification',
}
KEY = re.compile(rb'AIza[0-9A-Za-z_-]{35}')
MARKER = b'REDACTED_GOOGLE_API_KEY'
FRONTEND_TOKEN = re.compile(rb'("maestro_container_token"\s*:\s*")[^"]+(")')


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()


def build(originals, output):
    if output.resolve().is_relative_to(originals.resolve()):
        raise ValueError('Derivative output must be outside original storage')
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'format': 'rci-sanitized-replay/1',
                'warning': 'TEST DERIVATIVES, not original HTTP evidence. Original record IDs and timestamps retain lineage only.',
                'transformation': 'Replace Google API key patterns with REDACTED_GOOGLE_API_KEY and maestro_container_token values with REDACTED; rebind hashes; label altered captures as extracts; rehash snapshot predecessors.',
                'files': []}
    for name, source in BUNDLES.items():
        base = originals / source
        if not base.is_dir():
            raise ValueError('Missing original bundle: ' + source)
        files = sorted(p for p in base.rglob('*') if p.is_file())
        hashes, changed_hashes, entries = {}, {}, {}
        for p in files:
            if p.is_symlink():
                raise ValueError('Symlink in original bundle')
            rel = p.relative_to(base)
            raw = p.read_bytes()
            clean, count = KEY.subn(MARKER, raw)
            clean, tokens = FRONTEND_TOKEN.subn(rb'\1REDACTED\2', clean)
            if (count or tokens) and p.suffix != '.bin':
                raise ValueError('Unexpected secret outside body; review before transforming')
            dest = output / name / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(clean)
            if count or tokens:
                hashes[digest(raw)] = digest(clean)
                changed_hashes[digest(clean)] = digest(raw)
            entry = dict(original_path=str(Path(source) / rel),
                         fixture_path=str(Path(name) / rel),
                         original_sha256=digest(raw), replacements=count,
                         frontend_token_replacements=tokens)
            entries[rel] = entry
            manifest['files'].append(entry)

        def annotate(value):
            if isinstance(value, list):
                return [annotate(v) for v in value]
            if not isinstance(value, dict):
                return value
            value = {k: annotate(v) for k, v in value.items()}
            original_hash = changed_hashes.get(value.get('content_hash'))
            if original_hash:
                if value.get('content') == 'full':
                    value['content'] = 'extract'
                if 'representation' in value:
                    value['representation'] = 'extract'
                    value['summary'] = 'Sanitized test derivative; see fixture manifest'
                    value['representation_metadata'] = {
                        'method': 'Test-only API key/frontend token redaction; not an untouched HTTP response',
                        'locator': value['local_reference'],
                        'permission': 'Repository security remediation for offline tests',
                        'original_sha256': original_hash,
                    }
            return value

        # Journals/reports first, then snapshots in chain order. Rebind immediate
        # predecessor hashes only after its exact derivative bytes are known.
        ordered = sorted((p for p in files if p.suffix == '.json'),
                         key=lambda p: ('snapshots' in p.parts, str(p)))
        for p in ordered:
            dest = output / name / p.relative_to(base)
            raw = dest.read_bytes()
            for old, new in hashes.items():
                raw = raw.replace(old.encode(), new.encode())
            value = annotate(json.loads(raw))
            # Preserve unrelated JSON bytes, especially hash-bound runtime config.
            clean = p.read_bytes() if value == json.loads(p.read_bytes()) else json_bytes(value)
            dest.write_bytes(clean)
            if 'snapshots' in p.parts:
                hashes[digest(p.read_bytes())] = digest(clean)
        for rel, entry in entries.items():
            entry['fixture_sha256'] = digest((output / name / rel).read_bytes())
    (output / 'manifest.json').write_bytes(json_bytes(manifest))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('originals', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = build(args.originals.resolve(), args.output.resolve())
    print(f"Created {len(result['files'])} derivative files; "
          f"{sum(f['replacements'] for f in result['files'])} key occurrences redacted.")
