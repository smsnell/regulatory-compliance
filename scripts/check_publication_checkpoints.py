#!/usr/bin/env python3
"""Read-only scan of locally pending Entire objects; never synchronize or show values."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from secret_guard import scan, ROOT


def git(*args):
    return subprocess.check_output(['git', *args])


def main(report):
    tempfile.tempdir = str(Path.home() / '.cache/rci-secret-scan')
    refs = git('for-each-ref', '--format=%(refname)', 'refs/entire', 'refs/heads/entire').decode().splitlines()
    require_scanner = shutil.which('gitleaks')
    if not require_scanner:
        raise RuntimeError('Scanner unavailable')
    # No fetch or remote contact. All objects not reachable from locally known
    # remote refs are potentially pending, including ancestors, not just tips.
    lines = git('rev-list', '--objects', *refs, '--not', '--remotes').splitlines() if refs else []
    objects = {line.split(b' ', 1)[0].decode(): line.split(b' ', 1)[1].decode('utf-8', 'replace') if b' ' in line else '' for line in lines}
    kinds = subprocess.check_output(['git', 'cat-file', '--batch-check=%(objectname) %(objecttype)'],
                                    input=('\n'.join(objects) + '\n').encode()).decode().splitlines()
    blobs = [line.split()[0] for line in kinds if line.endswith(' blob')]
    def inspect(oid):
        code = scan(git('cat-file', 'blob', oid), require_scanner, ROOT / '.gitleaks.toml')
        return dict(oid=oid, path=objects[oid], result='possible-sensitive-content' if code == 1 else 'scanner-error' if code else 'clean')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(inspect, blobs))
    findings = [row for row in results if row['result'] != 'clean']
    value = dict(scope='Entire refs and branch; all locally pending reachable blobs, excluding locally known remote reachability',
                 remote_state='Not refreshed; no network or synchronization performed', refs=refs,
                 ref_tips={ref:git('rev-parse', ref).decode().strip() for ref in refs},
                 blob_count=len(blobs), findings=findings,
                 synchronization_authorized=False,
                 disposition='HOLD: potential sensitive content or scanner errors' if findings else 'Scanned bytes clean; synchronization not requested or authorized',
                 limitation='Local objects and refs may change after this scan; no claim about unseen or future checkpoints')
    Path(report).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(dict(blob_count=len(blobs), flagged_blob_count=len(findings), synchronization_authorized=False)))


if __name__ == '__main__':
    main(sys.argv[1])
