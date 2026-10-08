import contextlib
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from ora2.baseline import WORLD, blob_id, project
from ora2.learner import CapacityError, ProtocolError
from ora2.session import Session
from test_ora2_inheritance import fixture


# A storage/control fixture, NOT the actual protected Phase 41 environment.
def fixture_actuator(before, action, *, bounds, world_version):
    step = {'north': (1, 0), 'east': (0, 1), 'south': (-1, 0), 'west': (0, -1)}[action]
    candidate = [before[i] + step[i] for i in (0, 1)]
    blocked = any(abs(v) > bounds for v in candidate)
    after = list(before) if blocked else candidate
    return {'before': list(before), 'after': after, 'action': action, 'blocked': blocked,
            'delta': [after[i] - before[i] for i in (0, 1)]}


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = json.dumps(fixture()).encode()
        self.journal = b'{"authored_fixture":true}\n'
        self.snapshot = self.root / 'origin.json'
        self.history = self.root / 'origin.jsonl'
        self.snapshot.write_bytes(self.raw)
        self.history.write_bytes(self.journal)
        self.path = self.root / 'session.sqlite'
        self.patches = contextlib.ExitStack()
        for module in ('ora2.baseline', 'ora2.session'):
            self.patches.enter_context(patch(module + '.STATE_BLOB', blob_id(self.raw)))
            self.patches.enter_context(patch(module + '.JOURNAL_BLOB', blob_id(self.journal)))
        self.calls = self.patches.enter_context(patch('ora2.session.actuator', return_value=fixture_actuator))

    def tearDown(self):
        self.patches.close()
        self.temp.cleanup()

    def create(self, limit=8):
        return Session.create(self.path, self.snapshot, self.history, enabled=True, seed=17, action_limit=limit)

    def test_origin_bytes_identity_and_history_preserved(self):
        with self.create() as session:
            self.assertEqual(session.db.execute('SELECT snapshot,journal FROM origin').fetchone(), (self.raw, self.journal))
            status = session.status()
            self.assertEqual(status['origin_cycle'], 12)
            self.assertEqual(status['inherited_observations'], 12)
            self.assertEqual(status['new_actions'], 0)
        self.assertEqual(self.snapshot.read_bytes(), self.raw)
        self.assertEqual(self.history.read_bytes(), self.journal)

    def test_all_commands_free_choice_then_single_committed_action(self):
        with self.create() as session:
            result = session.tick('step-1', enabled=True)['result']
            self.assertEqual(len(result['experience']['choice']['menu']), 4)
            self.assertEqual(session.status()['new_actions'], 1)
            self.assertEqual(self.calls.call_count, 1)

    def test_old_request_retry_is_noop_after_later_actions(self):
        with self.create() as session:
            first = session.tick('one', enabled=True)
            session.tick('two', enabled=True)
            before = session.status()
            replay = session.tick('one', enabled=True)
            self.assertTrue(replay['replayed'])
            self.assertEqual(replay['result'], first['result'])
            self.assertEqual(session.status(), before)
            self.assertEqual(self.calls.call_count, 2)

    def test_restart_replays_without_actuating_and_next_choice_matches(self):
        with self.create() as session:
            for i in range(3): session.tick(f'step-{i}', enabled=True)
            expected = session.status()
            agent = session._restore()[0]
            choice = agent.choose(['north', 'east', 'south', 'west'])
        with Session(self.path) as session:
            self.assertEqual(session.status(), expected)
            self.assertEqual(self.calls.call_count, 3)
            result = session.tick('next', enabled=True)['result']
            self.assertEqual(result['experience']['choice'], choice.record())

    def test_default_off_and_budget_exhaustion_preserve_history(self):
        with self.assertRaises(ProtocolError):
            Session.create(self.path, self.snapshot, self.history)
        with self.create(limit=1) as session:
            with self.assertRaises(ProtocolError): session.tick('off')
            session.tick('one', enabled=True)
            before = session.status()
            with self.assertRaises(CapacityError): session.tick('two', enabled=True)
            self.assertEqual(session.status(), before)
            self.assertEqual(self.calls.call_count, 1)

    def test_unexpected_source_or_state_rejects_before_actuation(self):
        with self.create() as session:
            with patch('ora2.session.source_identity', return_value={'wrong': 'source'}):
                with self.assertRaises(ProtocolError): session.tick('one', enabled=True)
        self.assertEqual(self.calls.call_count, 0)

    def test_missing_and_existing_database_never_bootstrapped_or_overwritten(self):
        with self.assertRaises(ProtocolError): Session(self.path)
        with self.create(): pass
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError): self.create()
        self.assertEqual(before, self.path.read_bytes())

    def test_origin_source_mismatch_never_creates_database(self):
        self.snapshot.write_bytes(self.raw + b' ')
        with self.assertRaises(ProtocolError): self.create()
        self.assertFalse(self.path.exists())

    def test_write_failure_rolls_back_world_and_learning(self):
        with self.create() as session:
            before = session.status()
            session.db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'test fault'); END")
            with self.assertRaises(sqlite3.IntegrityError): session.tick('one', enabled=True)
            self.assertEqual(session.status(), before)
            session.db.execute('DROP TRIGGER fail_event')
            self.assertFalse(session.tick('one', enabled=True)['replayed'])
            self.assertEqual(session.status()['new_actions'], 1)

    def test_corrupt_chain_and_immutable_history(self):
        with self.create() as session:
            session.tick('one', enabled=True)
            with self.assertRaises(sqlite3.IntegrityError):
                session.db.execute("UPDATE events SET prior='bad'")
            session.db.execute("UPDATE head SET seal='bad'")
            with self.assertRaises(ProtocolError): session.status()

    def test_source_paths_and_invalid_request_reject(self):
        with self.assertRaises(ProtocolError):
            Session.create(self.snapshot, self.snapshot, self.history, enabled=True)
        with self.create() as session:
            for request in (None, '', '../x', 'a'*129, True):
                with self.assertRaises(ProtocolError): session.tick(request, enabled=True)
        self.assertEqual(self.calls.call_count, 0)
