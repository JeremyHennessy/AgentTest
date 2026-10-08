"""Pre-integration contract test: source guard logic is not yet applied to main.

The two real main scripts need identical minimal inline checks; their exact
GitHub files and integration tests must still run on a source-pinned candidate.
"""
from pathlib import Path
import tempfile
import unittest

from agenttest.journal_tail_rotation import ACTIVE, MANIFEST, export_logical, rotate, verify


def guard_source_records(path: Path) -> Path:
    source = path.resolve()
    if source.name == ACTIVE and ((source.parent / MANIFEST).exists() or (source.parent / MANIFEST).is_symlink()):
        raise ValueError("active journal tail is not full history; use a verified logical export")
    return source


class ReaderGuardLogicTests(unittest.TestCase):
    def test_no_archive_legacy_journal_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            active = Path(d) / ACTIVE
            active.write_bytes(b'{"event":"cycle","cycle":10}\n')
            self.assertEqual(guard_source_records(active), active.resolve())

    def test_rotated_active_tail_is_not_full_history(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / 'state'
            state.mkdir()
            active = state / ACTIVE
            old = b'{"event":"cycle","cycle":10}\n'
            active.write_bytes(old)
            (state/'heartbeat_operation.json').write_text('{"status":"completed","result_cycle":10}')
            (state/'organism.json').write_text('{"cycles":10}')
            rotate(state, expected_active_sha256=verify(state)['active_sha256'], expected_cycle=10, min_bytes=1)
            active.write_bytes(b'{"event":"cycle","cycle":11}\n')
            with self.assertRaisesRegex(ValueError, 'not full history'):
                guard_source_records(active)
            # A verified, immutable complete-history export has an ordinary
            # name and contains both events; it remains a valid audit input.
            complete = Path(d)/'complete.jsonl'
            export_logical(state, complete)
            self.assertEqual(complete.read_bytes(), old + active.read_bytes())
            self.assertEqual(guard_source_records(complete), complete.resolve())

    def test_dangling_manifest_symlink_also_blocks_tail_input(self):
        # Path.exists() alone would miss the pathname and fail open.
        with tempfile.TemporaryDirectory() as d:
            state = Path(d)/'state'; state.mkdir()
            (state / ACTIVE).write_bytes(b'')
            (state / MANIFEST).symlink_to('missing-manifest.json')
            with self.assertRaisesRegex(ValueError, 'not full history'):
                guard_source_records(state / ACTIVE)

    def test_symlink_to_rotated_tail_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d)/'state'; state.mkdir()
            (state / MANIFEST).write_text('{"version":"ora-journal-tail-v1","archives":[]}')
            (state / ACTIVE).write_bytes(b'')
            alias = Path(d)/'records.jsonl'
            alias.symlink_to(state/ACTIVE)
            with self.assertRaisesRegex(ValueError, 'not full history'):
                guard_source_records(alias)

if __name__ == '__main__': unittest.main()
