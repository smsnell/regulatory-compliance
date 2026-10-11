"""Publication provenance boundaries, using safe bytes and actual public derivatives."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from publication_evidence import clean_capture, digest, original_files
from rci.contracts import ContractError
from rci.evidence import EvidenceStore
from rci.history import verify_archive
from rci.validate import validate_package


def test_missing_originals_never_reports_complete_lineage(tmp_path):
    with pytest.raises(ContractError, match='LIMITATION: original preservation inventory unavailable'):
        original_files(tmp_path)


def test_corrupt_original_fails_before_transformation(tmp_path):
    original = tmp_path / 'deliverables/sources/source.bin'
    original.parent.mkdir(parents=True)
    original.write_bytes(b'changed')
    (tmp_path / 'preservation.json').write_text(json.dumps({'files': [dict(
        path='deliverables/sources/source.bin', sha256=digest(b'original'), size=8)]}))
    with pytest.raises(ContractError, match='Original preservation mismatch'):
        original_files(tmp_path)


def test_waf_extract_retains_failure_text_and_removes_executable_challenge():
    raw = (b'<html><title>Challenge</title><script>window.gokuProps={"key":"' +
           b'synthetic-test-data' + b'"};</script><body><h1>Access challenge</h1>'
           b'<p>JavaScript is required.</p></body></html>')
    clean, counts = clean_capture(raw)
    assert b'Access challenge' in clean and b'JavaScript is required.' in clean
    assert b'gokuProps' not in clean and b'<script' not in clean
    assert counts['waf_script_elements'] == 1
    assert digest(clean) != digest(raw)


def test_unbounded_waf_removal_fails_closed():
    with pytest.raises(ContractError, match='WAF extraction incomplete'):
        clean_capture(b'<p>gokuProps outside script; requires manual review</p>')


def test_public_manifest_hashes_and_extract_lineage():
    root = ROOT / 'deliverables'
    manifest = json.loads((root / 'publication-manifest.json').read_bytes())
    assert len(manifest['files']) == 332
    assert len({r['path'] for r in manifest['files']}) == len(manifest['files'])
    changed_sources = [r for r in manifest['files'] if r['redactions']]
    assert len(changed_sources) == 15
    assert sum(r['redactions']['google_occurrences'] for r in changed_sources) == 228
    assert sum(r['redactions']['maestro_fields'] for r in changed_sources) == 12
    assert sum(bool(r['redactions']['waf_script_elements']) for r in changed_sources) == 3
    for row in manifest['files']:
        assert digest((root / row['path']).read_bytes()) == row['derivative_sha256']
        assert row['transformed'] == (row['original_sha256'] != row['derivative_sha256'])
    for name, expected in manifest['generated_files'].items():
        assert digest((root / name).read_bytes()) == expected
    for row in changed_sources:
        path = Path(row['path'])
        package = root / path.parent.parent
        terminal = json.loads((package / 'analysis/attempts' / (path.stem + '.terminal.json')).read_bytes())
        capture = terminal['capture']
        assert terminal['attempt']['content'] == capture['representation'] == 'extract'
        assert capture['content_hash'] == row['derivative_sha256']
        assert capture['representation_metadata']['original_sha256'] == row['original_sha256']


@pytest.mark.parametrize('relative,coverage,captures', [('.', 8, 26),
    ('history/run-f48b4823b3ad4faaa9ac30a301b66505', 56, 29)])
def test_public_derivative_full_integration_without_private_originals(relative, coverage, captures):
    root = ROOT / 'deliverables' / relative
    chain = validate_package(root)
    assert len(EvidenceStore(root, chain[0]['run_id']).inventory()) == 22
    assert len(chain[1]['state']['captures']) == captures
    assert chain[-1]['status'] == chain[-1]['state']['publication_status'] == 'blocked'
    model = chain[5]['state']['export_model']
    assert len(model['unresolved_coverage']) == coverage
    assert not model['actions']
    assert len(model['review_requests']) == 2
    assert all(r['delivery_status'] == 'not-sent' for r in model['review_requests'])
    assert not (root / '.completion.json').exists()
    assert not (root / '.incomplete-replacement.json').exists()
    if relative != '.':
        verify_archive(root)
