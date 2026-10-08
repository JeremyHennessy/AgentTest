import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

from agenttest.journal_tail_rotation import (
    ACTIVE, MANIFEST, JournalIntegrityError, logical_bytes, logical_lines, export_logical,
    logical_digest, logical_events, rotate, verify, publication_preflight, SAFE_MAX_BLOB_BYTES,
)

# This optional heavy local fixture is not part of the source repository.
import os
CHECKPOINT = Path(os.environ['ORA_PHASE41_CHECKPOINT_ARCHIVE']) if os.environ.get('ORA_PHASE41_CHECKPOINT_ARCHIVE') else None


class TestJournalTailRotation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / 'state'
        self.state.mkdir()
        self.orig = (b'{"event":"seed", "utf8":"caf\xc3\xa9"}\r\n'
                     b'{"event":"diagnostic", "x":2}\n')
        (self.state / ACTIVE).write_bytes(self.orig)
        self.cycle = 10
        self.receipt()

    def receipt(self, status='completed', result_cycle=None, state_cycle=None):
        (self.state / 'heartbeat_operation.json').write_text(json.dumps({
            'status': status, 'result_cycle': self.cycle if result_cycle is None else result_cycle}))
        (self.state / 'organism.json').write_text(json.dumps({
            'cycles': self.cycle if state_cycle is None else state_cycle}))

    def rotate(self, **kwargs):
        return rotate(self.state, expected_active_sha256=verify(self.state)['active_sha256'],
                      expected_cycle=self.cycle, min_bytes=1, **kwargs)

    def event(self, cycle):
        return json.dumps({'event': 'cycle', 'cycle': cycle}, separators=(',', ':')).encode() + b'\n'

    def test_keeps_every_historical_byte_exactly_and_resets_active_tail(self):
        before = logical_digest(self.state)
        report = self.rotate()
        self.assertEqual((self.state / 'journal-sealed-000001.jsonl').read_bytes(), self.orig)
        self.assertEqual((self.state / ACTIVE).read_bytes(), b'')
        self.assertEqual(logical_digest(self.state), before)
        self.assertEqual(report['archive_count'], 1)
        self.assertFalse(report['published'])
        self.assertTrue(report['requires_remote_cas'])
        self.assertEqual(len(list(logical_events(self.state))), 2)

    def test_atomic_complete_export_refuses_overwrite(self):
        self.rotate()
        (self.state / ACTIVE).write_bytes(self.event(11))
        export = self.state.parent / 'complete.jsonl'
        receipt = export_logical(self.state, export)
        self.assertEqual(receipt['sha256'], hashlib.sha256(self.orig+self.event(11)).hexdigest())
        self.assertEqual(export.read_bytes(), self.orig+self.event(11))
        with self.assertRaisesRegex(JournalIntegrityError, 'export_target_exists'):
            export_logical(self.state, export)

    def test_export_cannot_create_complete_history_blob_inside_live_state(self):
        self.rotate()
        before = logical_digest(self.state)
        forbidden = self.state / 'whole-history.jsonl'
        with self.assertRaisesRegex(JournalIntegrityError, 'export_target_inside_live_state'):
            export_logical(self.state, forbidden)
        self.assertFalse(forbidden.exists())
        self.assertEqual(logical_digest(self.state), before)

    def test_raw_logical_lines_preserve_strict_receipt_verification_bytes(self):
        # A legacy verifier uses strict_json(line), not the permissive decoded
        # events iterator. It must see the exact same per-event bytes after
        # sealing and after a later append, including CRLF and duplicates.
        before = list(logical_lines(self.state))
        self.rotate()
        self.assertEqual(list(logical_lines(self.state)), before)
        appended = b'{"event":"new", "cycle":11}\n'
        with (self.state / ACTIVE).open('ab') as f:
            f.write(appended)
        self.assertEqual(list(logical_lines(self.state)), before + [appended])
        self.assertEqual(hashlib.sha256(b''.join(logical_lines(self.state))).hexdigest(),
                         logical_digest(self.state)[1])

    def test_historical_bounded_claim_remains_addressable_after_two_rotations(self):
        # The previous physical-reader implementation would fail this after
        # rotation: it would see only the empty active tail. This asserts the
        # new raw-line iterator's history visibility, NOT full integration.
        old=b'{"event":"cycle","cycle":10,"heartbeat_request_id":"heartbeat:old"}\n'
        (self.state / ACTIVE).write_bytes(old)
        self.rotate()
        newer=b'{"event":"cycle","cycle":11,"heartbeat_request_id":"heartbeat:new"}\n'
        (self.state / ACTIVE).write_bytes(newer)
        self.receipt(result_cycle=11, state_cycle=11)
        self.cycle=11
        self.rotate()
        records=[json.loads(line) for line in logical_lines(self.state) if line.strip()]
        self.assertEqual({e['heartbeat_request_id'] for e in records},
                         {'heartbeat:old','heartbeat:new'})
        self.assertEqual(b''.join(logical_bytes(self.state)),old+newer)
        self.assertEqual((self.state / ACTIVE).read_bytes(),b'')

    def test_duplicate_keys_remain_visible_to_original_strict_decoder(self):
        # Do not deserialize and reserialize history before a strict decoder
        # can reject duplicates; preserving the raw lines is essential.
        duplicate=b'{"event":"cycle","cycle":1,"cycle":2}\n'
        (self.state / ACTIVE).write_bytes(duplicate)
        self.rotate()
        self.assertEqual(list(logical_lines(self.state)), [duplicate])

    def test_logical_decoder_rejects_ambiguous_keys_but_preserves_raw_history(self):
        original = b'{"event":"cycle","cycle":1,"cycle":2}\n'
        (self.state / ACTIVE).write_bytes(original)
        self.rotate()
        self.assertEqual(b"".join(logical_lines(self.state)), original)
        with self.assertRaisesRegex(JournalIntegrityError, "duplicate_event_key"):
            list(logical_events(self.state))

    def test_logical_decoder_rejects_nonfinite_but_preserves_raw_history(self):
        original = b'{"event":"cycle","reward":NaN}\n'
        (self.state / ACTIVE).write_bytes(original)
        self.rotate()
        self.assertEqual(b"".join(logical_bytes(self.state)), original)
        with self.assertRaisesRegex(JournalIntegrityError, "nonfinite_event_value"):
            list(logical_events(self.state))

    def test_logical_decoder_rejects_overflowing_exponent_and_keeps_bytes(self):
        # JSON's parse_constant callback alone misses 1e10000, which Python's
        # default float decoder converts silently to infinity.
        original = b'{"event":"cycle","reward":1e10000}\n'
        (self.state / ACTIVE).write_bytes(original)
        self.rotate()
        self.assertEqual(b"".join(logical_lines(self.state)), original)
        with self.assertRaisesRegex(JournalIntegrityError, "nonfinite_event_value"):
            list(logical_events(self.state))

    def test_original_heartbeat_physical_tail_logic_still_valid(self):
        self.rotate()
        # After an idle cutover, claim snapshots the active tail, still at the same
        # physical file name used by heartbeat_transport.complete.
        before = (self.state / ACTIVE).read_bytes()
        self.assertEqual(before, b'')
        (self.state / ACTIVE).write_bytes(before + self.event(11) + b'{"event":"diagnostic"}\n')
        after = (self.state / ACTIVE).read_bytes()
        self.assertTrue(after.startswith(before))
        recent = [json.loads(line) for line in after[len(before):].splitlines() if line.strip()]
        cycles = [row for row in recent if row.get('event') == 'cycle']
        self.assertEqual(cycles, [{'event': 'cycle', 'cycle': 11}])
        self.assertEqual([row['event'] for row in logical_events(self.state)],
                         ['seed', 'diagnostic', 'cycle', 'diagnostic'])
        self.assertEqual(b''.join(logical_bytes(self.state)), self.orig + after)

    def test_second_rotation_preserves_order_and_all_bytes(self):
        self.rotate()
        add = self.event(11) + b'{"event":"foo"}\n'
        (self.state / ACTIVE).write_bytes(add)
        self.receipt(result_cycle=11, state_cycle=11)
        self.cycle = 11
        self.rotate()
        self.assertEqual(verify(self.state)['archive_count'], 2)
        self.assertEqual(b''.join(logical_bytes(self.state)), self.orig + add)
        self.assertEqual(len(list(logical_events(self.state))), 4)

    def test_incomplete_tail_fails_closed_without_archive(self):
        (self.state / ACTIVE).write_bytes(self.orig + b'{"dangling":')
        with self.assertRaisesRegex(JournalIntegrityError, 'incomplete_event'):
            self.rotate()
        self.assertFalse((self.state / MANIFEST).exists())

    def test_malformed_json_event_fails_closed(self):
        (self.state / ACTIVE).write_bytes(self.orig + b'not-json\n')
        with self.assertRaisesRegex(JournalIntegrityError, 'invalid_event'):
            self.rotate()

    def test_heartbeat_pending_or_mismatched_cycle_fails_closed(self):
        for status, result_cycle, state_cycle in [('pending', 10, 10), ('completed', 9, 10), ('completed', 10, 11)]:
            self.receipt(status, result_cycle, state_cycle)
            with self.assertRaises(JournalIntegrityError):
                self.rotate()
            self.assertEqual((self.state / ACTIVE).read_bytes(), self.orig)

    def test_wrong_expected_cycle_and_digest_do_not_mutate(self):
        with self.assertRaisesRegex(JournalIntegrityError, 'stale_cycle'):
            rotate(self.state, expected_active_sha256=verify(self.state)['active_sha256'],
                   expected_cycle=self.cycle + 1, min_bytes=1)
        with self.assertRaisesRegex(JournalIntegrityError, 'stale_active_tail'):
            rotate(self.state, expected_active_sha256='a' * 64,
                   expected_cycle=self.cycle, min_bytes=1)
        self.assertEqual((self.state / ACTIVE).read_bytes(), self.orig)

    def test_rotating_below_threshold_rejected(self):
        with self.assertRaisesRegex(JournalIntegrityError, 'below_rotation_floor'):
            rotate(self.state, expected_active_sha256=verify(self.state)['active_sha256'],
                   expected_cycle=self.cycle, min_bytes=len(self.orig) + 1)

    def test_corrupt_or_missing_sealed_archive_fails_closed(self):
        self.rotate()
        archive = self.state / 'journal-sealed-000001.jsonl'
        archive.write_bytes(b'{"event":"other"}\n')
        with self.assertRaisesRegex(JournalIntegrityError, 'archive_changed'):
            list(logical_bytes(self.state))
        archive.unlink()
        with self.assertRaisesRegex(JournalIntegrityError, 'missing_file'):
            verify(self.state)

    def test_orphan_and_manifest_tampering_fails_closed(self):
        (self.state / 'journal-sealed-000001.jsonl').write_bytes(self.orig)
        with self.assertRaisesRegex(JournalIntegrityError, 'orphan_archive'):
            verify(self.state)
        (self.state / 'journal-sealed-000001.jsonl').unlink()
        self.rotate()
        data = json.loads((self.state / MANIFEST).read_text())
        data['archives'][0]['name'] = '../journal.jsonl'
        (self.state / MANIFEST).write_text(json.dumps(data))
        with self.assertRaisesRegex(JournalIntegrityError, 'noncanonical'):
            verify(self.state)

    def test_archive_symlink_rejected(self):
        self.rotate()
        old = self.state / 'journal-sealed-000001.jsonl'
        new = self.state / 'otherfile'
        old.rename(new)
        old.symlink_to(new)
        with self.assertRaisesRegex(JournalIntegrityError, 'unsafe_file'):
            verify(self.state)

    def test_before_rename_injected_failure_leaves_original(self):
        with self.assertRaisesRegex(JournalIntegrityError, 'injected_before'):
            self.rotate(fail_at='before_rename')
        self.assertEqual((self.state / ACTIVE).read_bytes(), self.orig)
        self.assertFalse((self.state / MANIFEST).exists())

    def test_after_rename_failure_is_unpublished_and_detectably_incomplete(self):
        with self.assertRaisesRegex(JournalIntegrityError, 'injected_after_rename'):
            self.rotate(fail_at='after_rename')
        self.assertEqual((self.state / 'journal-sealed-000001.jsonl').read_bytes(), self.orig)
        with self.assertRaises(JournalIntegrityError):
            verify(self.state)
        self.assertFalse((self.state / MANIFEST).exists())

    def test_after_new_tail_failure_is_unpublished_and_detectably_incomplete(self):
        with self.assertRaisesRegex(JournalIntegrityError, 'injected_after_new_tail'):
            self.rotate(fail_at='after_new_tail')
        with self.assertRaises(JournalIntegrityError):
            verify(self.state)
        self.assertFalse((self.state / MANIFEST).exists())

    def test_before_manifest_failure_is_unpublished_and_detectably_incomplete(self):
        with self.assertRaisesRegex(JournalIntegrityError, 'injected_before_manifest'):
            self.rotate(fail_at='before_manifest')
        with self.assertRaises(JournalIntegrityError):
            verify(self.state)

    def test_publication_preflight_rejects_oversize_unrelated_state(self):
        self.rotate()
        path = self.state / 'oversize.bin'
        with path.open('wb') as out:
            out.truncate(SAFE_MAX_BLOB_BYTES)
        with self.assertRaisesRegex(JournalIntegrityError, 'state_blob_exceeds_safe_budget'):
            publication_preflight(self.state)

    def test_sealed_archive_uses_identical_git_blob_identity(self):
        root = self.state.parent
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
        git('init', '-q')
        git('config', 'user.name', 'Ora Test')
        git('config', 'user.email', 'ora-test@example.invalid')
        git('add', 'state')
        git('commit', '-qm', 'original')
        before_oid = git('rev-parse', 'HEAD:state/journal.jsonl')
        self.rotate()
        git('add', 'state')
        git('commit', '-qm', 'archive with same blob and zero active tail')
        archive_oid = git('rev-parse', 'HEAD:state/journal-sealed-000001.jsonl')
        self.assertEqual(before_oid, archive_oid)
        self.assertEqual(git('cat-file', '-s', archive_oid), str(len(self.orig)))
        self.assertEqual(git('cat-file', '-s', git('rev-parse', 'HEAD:state/journal.jsonl')), '0')

    def test_real_copied_phase41_journal_keeps_digest_and_events(self):
        if CHECKPOINT is None or not CHECKPOINT.exists():
            self.skipTest('preserved checkpoint archive not mounted')
        with tarfile.open(CHECKPOINT, 'r:gz') as t:
            data = t.extractfile('COPIED_WORLD_ONLY/state/journal.jsonl').read()
        (self.state / ACTIVE).write_bytes(data)
        old = hashlib.sha256(data).hexdigest()
        row = self.rotate()
        self.assertEqual(row['logical_sha256'], old)
        self.assertEqual((self.state / 'journal-sealed-000001.jsonl').stat().st_size, len(data))
        self.assertEqual((self.state / ACTIVE).stat().st_size, 0)
        self.assertEqual(verify(self.state)['logical_events'], sum(bool(s.strip()) for s in data.splitlines()))
        self.assertEqual(hashlib.sha256(b''.join(logical_bytes(self.state))).hexdigest(), old)


if __name__ == '__main__':
    unittest.main()
