"""U18 isolated recovery faults. Synthetic U02 bytes are not G5 evidence."""
from copy import deepcopy
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'regulatory-change-impact-brief/scripts'))
from rci.contracts import (ContractError, SNAPSHOT_PATHS, STAGES, json_bytes,
                           parse_json, sha256_bytes)
from rci.history import (MANIFEST, archive_current, inspect_current, inventory,
                         recover_run_id, verify_archive)
from rci.ids import new_record_id, new_snapshot_id
from rci.recovery import (classify_change, preserve_interrupted, promote_candidate,
                          stage_fingerprints)
from rci.runtime import writer_lock
from rci.snapshots import (COMPLETION_MARKER, INCOMPLETE_MARKER, accept_package,
                           read_chain, stage_records)

FIXTURE = ROOT / 'tests/fixtures/u02/package'
WHEN = '2026-10-10T12:00:00Z'


def make_run(root, run_id):
    shutil.copytree(FIXTURE, root)
    chain = [parse_json((root / path).read_bytes()) for path in SNAPSHOT_PATHS]
    replacements = {chain[0]['run_id']:run_id}
    for snapshot in chain:
        replacements[snapshot['snapshot_id']] = new_snapshot_id()
        for record in stage_records(snapshot):
            replacements[record['id']] = new_record_id(run_id, snapshot['sequence'], record['record_type'])
    def remap(value):
        if isinstance(value, str):
            return replacements.get(value, value)
        if isinstance(value, list):
            return [remap(v) for v in value]
        if isinstance(value, dict):
            return {k:remap(v) for k, v in value.items()}
        return value
    chain = remap(chain)
    old_hashes = {path:sha256_bytes((root / path).read_bytes()) for path in SNAPSHOT_PATHS}
    for i, snapshot in enumerate(chain):
        if i:
            snapshot['predecessor']['sha256'] = sha256_bytes((root / SNAPSHOT_PATHS[i - 1]).read_bytes())
        (root / SNAPSHOT_PATHS[i]).write_bytes(json_bytes(snapshot))
    for path in SNAPSHOT_PATHS:
        replacements[old_hashes[path]] = sha256_bytes((root / path).read_bytes())
    request = remap(parse_json((root / 'analysis/request.json').read_bytes()))
    (root / 'analysis/request.json').write_bytes(json_bytes(request))
    response = remap(parse_json((root / 'analysis/response.json').read_bytes()))
    response['packet_sha256'] = sha256_bytes(json_bytes(request))
    (root / 'analysis/response.json').write_bytes(json_bytes(response))
    marker = parse_json((root / COMPLETION_MARKER).read_bytes())
    marker.update(run_id=run_id, stage07=dict(snapshot_id=chain[-1]['snapshot_id'],
                  path=SNAPSHOT_PATHS[-1], sha256=sha256_bytes((root / SNAPSHOT_PATHS[-1]).read_bytes())))
    (root / COMPLETION_MARKER).write_bytes(json_bytes(marker))
    return chain


class HistoryAndRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'deliverables'
        self.old = make_run(self.root, 'run-old')
        self.candidate = self.root / '.staging/run-new'
        self.new = make_run(self.candidate, 'run-new')

    def promote(self, **kwargs):
        return promote_candidate(self.root, self.candidate, new_run_id='run-new',
                                 created_at=WHEN, **kwargs)

    def test_success_preserves_exact_prior_bytes_and_unrelated_files(self):
        (self.root / 'operator-notes.txt').write_text('Keep these notes.')
        source = inventory(self.root)
        result = self.promote()
        self.assertTrue(result['completed'])
        self.assertEqual(accept_package(self.root), self.new)
        self.assertTrue(inspect_current(self.root)['accepted'])
        archived = verify_archive(self.root / 'history/run-old')
        self.assertEqual(archived.manifest['inventory'], source)
        self.assertEqual(accept_package(archived.root), self.old)
        self.assertEqual((self.root / 'operator-notes.txt').read_text(), 'Keep these notes.')
        self.assertFalse((self.root / INCOMPLETE_MARKER).exists())

    def test_first_run_has_no_fabricated_archive(self):
        empty = Path(self.temp.name) / 'first'
        candidate = empty / '.staging/run-first'
        chain = make_run(candidate, 'run-first')
        result = promote_candidate(empty, candidate, new_run_id='run-first', created_at=WHEN)
        self.assertIsNone(result['archive_root'])
        self.assertEqual(accept_package(empty), chain)

    def test_source_snapshot_analysis_and_reference_bytes_are_archived(self):
        reference = 'regulatory-change-impact-brief/references/interpretation.md'
        (self.root / reference).parent.mkdir(parents=True)
        (self.root / reference).write_bytes(b'Exact interpretation instructions.\n')
        (self.root / 'config').mkdir()
        (self.root / 'config/review.example.json').write_bytes(b'{"model":"synthetic"}\n')
        (self.root / 'snapshot.schema.json').write_bytes(b'{"type":"object"}\n')
        archived = archive_current(self.root, 'run-old', WHEN)
        for path in (reference, 'config/review.example.json', 'snapshot.schema.json',
                     'analysis/request.json', 'sources/systems.txt', SNAPSHOT_PATHS[0]):
            self.assertEqual((archived.root / path).read_bytes(), (self.root / path).read_bytes())
        # Historical source checks remain bound to the archived root.
        (self.root / 'sources/systems.txt').write_bytes(b'newer current content')
        self.assertEqual(accept_package(archived.root), self.old)

    def test_only_explicit_history_dependencies_are_copied_and_merged(self):
        reviewed = self.candidate / 'history/run-reviewed'
        make_run(reviewed, 'run-reviewed')
        (self.candidate / 'analysis/review-context.json').write_bytes(json_bytes(
            dict(reviewed_draft=dict(root='history/run-reviewed'))))
        make_run(self.root / 'history/run-unrelated', 'run-unrelated')
        self.promote()
        self.assertTrue((self.root / 'history/run-unrelated').exists())
        self.assertEqual((self.root / 'history/run-reviewed/sources/systems.txt').read_bytes(),
                         (reviewed / 'sources/systems.txt').read_bytes())
        archived = archive_current(self.root, 'run-new', WHEN)
        self.assertTrue((archived.root / 'history/run-reviewed').exists())
        self.assertFalse((archived.root / 'history/run-unrelated').exists())
        self.assertEqual(accept_package(archived.root / 'history/run-reviewed')[0]['run_id'], 'run-reviewed')

    def test_differing_history_dependency_stops_before_managed_overwrite(self):
        make_run(self.candidate / 'history/run-reviewed', 'run-reviewed')
        (self.candidate / 'analysis/review-context.json').write_bytes(json_bytes(
            dict(reviewed_draft=dict(root='history/run-reviewed'))))
        make_run(self.root / 'history/run-reviewed', 'run-reviewed')
        original = (self.root / 'compliance-brief.md').read_bytes()
        with self.assertRaisesRegex(ContractError, 'history dependency differs'):
            self.promote()
        self.assertEqual((self.root / 'compliance-brief.md').read_bytes(), original)
        self.assertFalse((self.root / INCOMPLETE_MARKER).exists())

    def test_missing_and_corrupt_files_are_honest_and_exact_bytes_survive(self):
        (self.root / 'action-calendar.ics').unlink()
        (self.root / 'compliance-brief.md').write_bytes(b'damaged available bytes')
        inspection = inspect_current(self.root)
        self.assertFalse(inspection['accepted'])
        rows = {r['path']:r for r in inspection['inventory']}
        self.assertEqual(rows['action-calendar.ics']['availability'], 'missing')
        self.assertEqual(rows['compliance-brief.md']['availability'], 'corrupt')
        self.promote()
        archived = verify_archive(self.root / 'history/run-old')
        self.assertEqual((archived.root / 'compliance-brief.md').read_bytes(), b'damaged available bytes')
        self.assertFalse((archived.root / 'action-calendar.ics').exists())
        self.assertEqual(accept_package(self.root), self.new)

    def test_unchanged_inputs_still_detect_damaged_source_snapshot_and_analysis(self):
        for path in ('sources/systems.txt', SNAPSHOT_PATHS[2], 'analysis/request.json'):
            with self.subTest(path=path):
                original = (self.root / path).read_bytes()
                (self.root / path).write_bytes(b'damage')
                self.assertFalse(inspect_current(self.root)['accepted'])
                (self.root / path).write_bytes(original)

    def test_historical_observations_and_dictionary_examples_are_not_current_pointers(self):
        (self.root / 'analysis/prior-inspection.json').write_bytes(json_bytes(dict(
            accepted=False, inventory=[dict(path='sources/prior-attempt.bin',
            sha256='sha256:' + 'a' * 64, availability='corrupt')])))
        (self.root / 'analysis/dictionary-packet.json').write_bytes(json_bytes(dict(
            field_dictionary=dict(fields=dict(schema_version='rci-field-dictionary/1',
                registers=dict(SYSTEMS=dict(basis=dict(path='sources/mapping-example.bin',
                sha256='sha256:' + 'b' * 64))))))))
        paths = {row['path'] for row in inventory(self.root)}
        self.assertNotIn('sources/prior-attempt.bin', paths)
        self.assertNotIn('sources/mapping-example.bin', paths)
        self.assertTrue(inspect_current(self.root)['accepted'])

    def test_feedback_claim_hashes_are_untrusted_and_review_pointers_use_archive_root(self):
        archived = archive_current(self.root, 'run-old', WHEN)
        reviewed = dict(root='history/run-old', **{
            key:dict(path=SNAPSHOT_PATHS[i], snapshot_id=self.old[i]['snapshot_id'],
                     sha256=sha256_bytes((archived.root / SNAPSHOT_PATHS[i]).read_bytes()))
            for key, i in (('stage06', 5), ('stage07', 6))})
        forged = dict(claimed_artifacts=[dict(path='compliance-brief.md', sha256='sha256:' + '0' * 64)],
                      reviewed_draft=deepcopy(reviewed))
        forged.update(record_type='feedback', match_status='matched', authentication='verified')
        forged['reviewed_draft']['stage07']['sha256'] = 'sha256:' + '1' * 64
        (self.root / 'analysis/feedback-input.json').write_bytes(json_bytes(dict(feedback=[forged])))
        matched = dict(record_type='feedback', match_status='matched', authentication='verified',
                       claimed_artifacts=forged['claimed_artifacts'], reviewed_draft=reviewed)
        (self.root / 'analysis/accepted-review-context.json').write_bytes(json_bytes(matched))
        rows = {row['path']:row for row in inventory(self.root)}
        self.assertEqual(rows['compliance-brief.md']['availability'], 'present')
        self.assertEqual(rows[SNAPSHOT_PATHS[6]]['availability'], 'present')
        historical = rows['history/run-old/' + SNAPSHOT_PATHS[6]]
        self.assertEqual(historical['availability'], 'present')
        self.assertEqual(historical['expected_sha256'], [reviewed['stage07']['sha256']])

    def test_existing_different_archive_is_never_overwritten(self):
        archived = archive_current(self.root, 'run-old', WHEN)
        original = (archived.root / 'compliance-brief.md').read_bytes()
        (self.root / 'compliance-brief.md').write_bytes(b'changed occurrence')
        with self.assertRaisesRegex(ContractError, 'existing archive differs'):
            self.promote()
        self.assertEqual((archived.root / 'compliance-brief.md').read_bytes(), original)
        self.assertFalse((self.root / INCOMPLETE_MARKER).exists())
        occurrence = archive_current(self.root, 'run-old', WHEN, occurrence=True)
        self.assertEqual((occurrence.root / 'compliance-brief.md').read_bytes(), b'changed occurrence')

    def test_unknown_or_mixed_prior_id_stops_without_changing_current(self):
        for path in SNAPSHOT_PATHS:
            (self.root / path).unlink()
        (self.root / COMPLETION_MARKER).unlink()
        original = inventory(self.root)
        with self.assertRaisesRegex(ContractError, 'no trustworthy prior run ID'):
            self.promote()
        self.assertEqual(inventory(self.root), original)
        self.assertFalse((self.root / INCOMPLETE_MARKER).exists())

    def test_archive_write_error_preserves_current_and_partial_evidence(self):
        original = inventory(self.root)
        from rci.history import _write as real_write
        counter = [0]
        def fail_archive(root, path, data):
            counter[0] += 1
            if counter[0] == 3:
                raise OSError('simulated storage full')
            return real_write(root, path, data)
        with patch('rci.history._write', side_effect=fail_archive):
            with self.assertRaisesRegex(OSError, 'storage full'):
                self.promote()
        self.assertEqual(inventory(self.root), original)
        self.assertFalse((self.root / INCOMPLETE_MARKER).exists())
        self.assertTrue(list((self.root / 'history').glob('.pending-*/*')))

    def test_marker_creation_failure_stops_before_overwrite(self):
        original = inventory(self.root)
        with patch('rci.recovery._write', side_effect=OSError('marker write denied')):
            with self.assertRaisesRegex(OSError, 'marker write denied'):
                self.promote()
        self.assertEqual(inventory(self.root), original)
        self.assertEqual(accept_package(self.root), self.old)
        self.assertEqual(accept_package(self.root / 'history/run-old'), self.old)

    def test_interrupted_copy_rejects_mixed_current_and_fresh_retry_preserves_it(self):
        from rci.recovery import _replace_file as real_replace
        count = [0]
        def interrupt(root, path, data):
            count[0] += 1
            if count[0] == 4:
                raise KeyboardInterrupt('simulated interrupted copy')
            return real_replace(root, path, data)
        with patch('rci.recovery._replace_file', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.promote()
        self.assertTrue((self.root / INCOMPLETE_MARKER).exists())
        self.assertFalse((self.root / COMPLETION_MARKER).exists())
        with self.assertRaisesRegex(ContractError, 'incomplete'):
            accept_package(self.root)
        failed_rows = inventory(self.root)
        retry = self.root / '.staging/run-retry'
        repaired = make_run(retry, 'run-retry')
        result = promote_candidate(self.root, retry, new_run_id='run-retry', created_at=WHEN)
        self.assertTrue(result['completed'])
        self.assertEqual(accept_package(self.root), repaired)
        self.assertEqual(verify_archive(self.root / 'history/run-new').manifest['inventory'], failed_rows)
        self.assertTrue((self.root / 'history/run-new' / INCOMPLETE_MARKER).exists())
        self.assertEqual(accept_package(self.root / 'history/run-old'), self.old)
        self.assertTrue(self.candidate.exists())

    def test_failed_independent_validation_keeps_incomplete_and_previous_archive(self):
        seen = []
        def independent(root):
            seen.append(root)
            if len(seen) == 2:
                self.assertNotEqual(root, self.candidate)
                self.assertEqual((root / 'compliance-brief.md').read_bytes(),
                                 (self.root / 'compliance-brief.md').read_bytes())
                raise ContractError('independent artifact check failed')
            return read_chain(root)
        with self.assertRaisesRegex(ContractError, 'artifact check failed'):
            self.promote(validator=independent)
        self.assertFalse(inspect_current(self.root)['accepted'])
        self.assertTrue((self.root / INCOMPLETE_MARKER).exists())
        self.assertFalse((self.root / COMPLETION_MARKER).exists())
        self.assertEqual(accept_package(self.root / 'history/run-old'), self.old)

    def test_partial_completion_write_remains_rejected(self):
        from rci.recovery import _write as real_write
        def write_failure(root, path, data):
            if path == COMPLETION_MARKER:
                (root / path).write_bytes(data[:30])
                raise OSError('completion storage error')
            return real_write(root, path, data)
        with patch('rci.recovery._write', side_effect=write_failure):
            with self.assertRaisesRegex(OSError, 'completion storage error'):
                self.promote()
        self.assertFalse(inspect_current(self.root)['accepted'])
        self.assertTrue((self.root / INCOMPLETE_MARKER).exists())
        failed = preserve_interrupted(self.root, WHEN)
        self.assertEqual((failed.root / COMPLETION_MARKER).read_bytes(),
                         (self.root / COMPLETION_MARKER).read_bytes())

    def test_second_writer_rejected_before_any_archive_or_marker(self):
        with writer_lock(self.root):
            with self.assertRaisesRegex(ContractError, 'another writer'):
                self.promote()
        self.assertFalse((self.root / 'history').exists())
        self.assertEqual(accept_package(self.root), self.old)

    def test_completion_can_be_withheld(self):
        result = self.promote(allow_completion=False)
        self.assertFalse(result['completed'])
        self.assertFalse((self.root / COMPLETION_MARKER).exists())
        self.assertFalse((self.root / INCOMPLETE_MARKER).exists())
        self.assertEqual(read_chain(self.root), self.new)
        self.assertFalse(inspect_current(self.root)['accepted'])

    def test_blocked_candidate_remains_blocked_without_completion(self):
        final = self.new[-1]
        final['status'] = 'blocked'
        final['state']['publication_status'] = 'blocked'
        (self.candidate / SNAPSHOT_PATHS[-1]).write_bytes(json_bytes(final))
        # Candidate completion is stale and is never copied or trusted.
        (self.candidate / COMPLETION_MARKER).unlink()
        result = self.promote()
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['completed'])
        self.assertFalse((self.root / COMPLETION_MARKER).exists())
        self.assertEqual(read_chain(self.root)[-1]['state']['publication_status'], 'blocked')

    def test_earliest_change_and_full_fresh_recompute(self):
        bases = {stage:dict(input='same', code='v1') for stage in STAGES}
        original = stage_fingerprints(bases)
        result = classify_change(original, original)
        self.assertIsNone(result['earliest_changed_sequence'])
        self.assertEqual(result['recompute_sequences'], list(range(1, 8)))
        for i, stage in enumerate(STAGES):
            changed = deepcopy(bases)
            changed[stage]['input'] = 'changed'
            result = classify_change(original, stage_fingerprints(changed))
            self.assertEqual(result['earliest_changed_sequence'], i + 1)
            self.assertTrue(result['fresh_source_attempts_required'])
            self.assertTrue(result['current_file_inspection_required'])
        changed = deepcopy(original)
        changed['contract_version'] = 'new'
        self.assertEqual(classify_change(original, changed)['earliest_changed_sequence'], 1)


if __name__ == '__main__':
    unittest.main()
