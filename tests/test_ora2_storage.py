from __future__ import annotations
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from ora2.learner import Agent, ProtocolError
from ora2.storage import ExperienceLog


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'experience.sqlite'

    def test_missing_log_does_not_bootstrap(self):
        with self.assertRaises(ProtocolError):
            ExperienceLog(self.path)
        self.assertFalse(self.path.exists())

    def test_existing_file_is_never_overwritten(self):
        self.path.write_bytes(b'approved-history')
        with self.assertRaises(FileExistsError):
            ExperienceLog(self.path, create=Agent(0))
        self.assertEqual(self.path.read_bytes(), b'approved-history')

    def test_committed_history_replays_choices_and_next_decision(self):
        agent = Agent(0, seed=19)
        with ExperienceLog(self.path, create=agent) as log:
            for i in range(25):
                log.append(agent.observe(agent.choose(['x', 'y']), {'value': i % 4}))
        with ExperienceLog(self.path) as log:
            restored = log.restore()
            self.assertEqual(agent.summary(), restored.summary())
            self.assertEqual(agent.choose(['x', 'y']), restored.choose(['x', 'y']))

    def test_exact_duplicate_delivery_is_noop(self):
        agent = Agent(0)
        with ExperienceLog(self.path, create=agent) as log:
            event = agent.observe(agent.choose(['a']), 1)
            self.assertTrue(log.append(event))
            self.assertFalse(log.append(event))
            self.assertEqual(log.restore().steps, 1)

    def test_conflicting_delivery_is_rejected(self):
        agent = Agent(0)
        with ExperienceLog(self.path, create=agent) as log:
            event = agent.observe(agent.choose(['a']), 1)
            log.append(event)
            changed = copy.deepcopy(event)
            changed['after'] = 9
            with self.assertRaises(ProtocolError):
                log.append(changed)
            self.assertEqual(log.restore().summary(), agent.summary())

    def test_gap_is_not_accepted(self):
        agent = Agent(0)
        with ExperienceLog(self.path, create=agent) as log:
            event = agent.observe(agent.choose(['a']), 1)
            event['step'] = 2
            with self.assertRaises(ProtocolError):
                log.append(event)
            self.assertEqual(log.restore().steps, 0)

    def test_sqlite_failure_rolls_back_completed_record_and_head(self):
        agent = Agent(0)
        with ExperienceLog(self.path, create=agent) as log:
            event = agent.observe(agent.choose(['a']), 1)
            log._db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON experience BEGIN SELECT RAISE(ABORT,'fault'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                log.append(event)
            self.assertEqual(log.restore().steps, 0)
            log._db.execute('DROP TRIGGER fail_insert')
            self.assertTrue(log.append(event))
            self.assertEqual(log.restore().steps, 1)

    def test_corrupted_content_is_detected(self):
        agent = Agent(0)
        with ExperienceLog(self.path, create=agent) as log:
            log.append(agent.observe(agent.choose(['a']), 1))
            log._db.execute('DROP TRIGGER no_update')
            log._db.execute("UPDATE experience SET body='{}'")
            with self.assertRaises(ProtocolError):
                log.restore()

    def test_deleted_tail_is_detected_by_stored_head(self):
        agent = Agent(0)
        with ExperienceLog(self.path, create=agent) as log:
            log.append(agent.observe(agent.choose(['a']), 1))
            log._db.execute('DROP TRIGGER no_delete')
            log._db.execute('DELETE FROM experience')
            with self.assertRaises(ProtocolError):
                log.restore()

    def test_reading_corrupt_file_does_not_replace_it(self):
        self.path.write_bytes(b'not sqlite')
        with self.assertRaises(sqlite3.DatabaseError):
            ExperienceLog(self.path)
        self.assertEqual(self.path.read_bytes(), b'not sqlite')

    def test_ordinary_update_and_delete_are_refused(self):
        agent = Agent(0)
        with ExperienceLog(self.path, create=agent) as log:
            log.append(agent.observe(agent.choose(['a']), 1))
            for query in ('DELETE FROM experience', "UPDATE experience SET body='{}'"):
                with self.subTest(query=query), self.assertRaises(sqlite3.IntegrityError):
                    log._db.execute(query)
            self.assertEqual(log.restore().steps, 1)


if __name__ == '__main__':
    unittest.main()
