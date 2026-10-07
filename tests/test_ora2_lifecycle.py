"""Authored bridge/storage controls; actual Phase 41 is tested separately."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ora2 import lifecycle as bridge
from ora2 import lifecycle_store as storage
from ora2.baseline import blob_id, project, seeded_agent, strict_json, WORLD
from ora2.learner import Config, ProtocolError, CapacityError


def data():
    return {'schema_version': 24, 'cycles': 2,
            'identity': {'designation': 'authored-test-only', 'chosen_name': None},
            'planning_lab': {'world_version': WORLD, 'bounds': 2, 'position': [0, 0],
                'transition_observations': [
                    {'source': 'planning_lab', 'source_id': 'old1', 'cycle': 1,
                     'action': 'north', 'before': [0, 0], 'after': [1, 0], 'delta': [1, 0],
                     'blocked': False, 'world_version': WORLD},
                    {'source': 'planning_lab', 'source_id': 'old2', 'cycle': 2,
                     'action': 'south', 'before': [1, 0], 'after': [0, 0], 'delta': [-1, 0],
                     'blocked': False, 'world_version': WORLD}]}}


def authored_cycle(raw, root):
    state = strict_json(raw)
    state['cycles'] += 1
    lab = state['planning_lab']
    row = {'source': 'planning_lab', 'source_id': 'new' + str(state['cycles']),
           'cycle': state['cycles'], 'world_version': WORLD, 'action': 'east',
           'before': list(lab['position']), 'after': list(lab['position']),
           'delta': [0, 0], 'blocked': True}
    lab['transition_observations'].append(row)
    journal = (json.dumps({'event': 'cycle', 'cycle': state['cycles']}) + '\n').encode()
    return {'snapshot': json.dumps(state).encode(), 'journal': journal,
            'outputs': {'authored_fixture': True}, 'sidecars': {}}


class CycleBridgeTests(unittest.TestCase):
    def setUp(self):
        self.state = data()
        self.raw = json.dumps(self.state).encode()
        self.agent = seeded_agent(project(self.state), seed=17, config=Config())

    def run_copy(self, execute=authored_cycle):
        with patch.object(bridge, 'source_identity', return_value={'authored': True}), \
             patch.object(bridge, 'execute_phase41', side_effect=execute):
            return bridge.run_cycle(self.raw, self.agent, Path('/not-real'), enabled=True)

    def test_six_original_commands_never_enable_cognition_or_extra_actor(self):
        plan = bridge.command_plan(Path('/isolated'), Path('/read-only-source'))
        self.assertEqual([x[0] for x in plan], ['cycle', 'propose', 'propose-change', 'review-before', 'diagnose-change', 'review-after'])
        self.assertEqual(sum('--planning-lab' in args for _, args in plan), 1)
        for _, args in plan:
            self.assertNotIn('--cognition', args)
            self.assertNotIn('--action-lab', args)
            self.assertEqual(args[args.index('--state') + 1], '/isolated/organism.json')

    def test_default_off_and_forecast_precedes_the_only_cycle(self):
        with self.assertRaises(ProtocolError):
            bridge.run_cycle(self.raw, self.agent, Path('/invalid'))
        def execute(raw, root):
            self.assertEqual(agent_predictions.call_count, 1)
            return authored_cycle(raw, root)
        with patch.object(bridge, 'forecast_menu', wraps=bridge.forecast_menu) as agent_predictions:
            result = self.run_copy(execute)
        self.assertTrue(result['temporal']['prospectively_scored'])
        self.assertEqual(result['temporal']['ora2_choices'], 0)
        self.assertEqual(result['temporal']['learning_event']['choice']['reason'], 'inherited_observation_not_agent_choice')

    def test_success_never_mutates_input_or_draws_action_rng(self):
        before = copy.deepcopy(self.agent.__dict__)
        result = self.run_copy()
        self.assertEqual(self.agent._random.getstate(), result['learner']._random.getstate())
        self.assertEqual(self.agent.steps, 2)
        self.assertEqual(result['learner'].steps, 3)
        self.assertEqual(self.agent.summary()['steps'], before['steps'])
        self.assertEqual(self.raw, json.dumps(data()).encode())

    def test_null_cycle_remains_real_cycle_without_learning(self):
        def execute(raw, root):
            result = authored_cycle(raw, root)
            state = strict_json(result['snapshot'])
            state['planning_lab']['transition_observations'].pop()
            result['snapshot'] = json.dumps(state).encode()
            return result
        result = self.run_copy(execute)
        self.assertEqual(result['learner'].steps, 2)
        self.assertEqual(result['temporal']['reason'], 'no_world_transition')

    def test_source_drift_blocks_uncommitted_result(self):
        with patch.object(bridge, 'source_identity', side_effect=[{'v': 1}, {'v': 2}]), \
             patch.object(bridge, 'execute_phase41', side_effect=authored_cycle):
            with self.assertRaises(ProtocolError):
                bridge.run_cycle(self.raw, self.agent, Path('/x'), enabled=True)
        self.assertEqual(self.agent.steps, 2)

    def test_multiple_or_reused_transition_ids_reject(self):
        for reuse in (False, True):
            def execute(raw, root):
                result = authored_cycle(raw, root)
                state = strict_json(result['snapshot'])
                rows = state['planning_lab']['transition_observations']
                if reuse:
                    rows[-1]['source_id'] = rows[0]['source_id']
                else:
                    rows.append(copy.deepcopy(rows[-1]))
                result['snapshot'] = json.dumps(state).encode()
                return result
            with self.assertRaises(ProtocolError):
                self.run_copy(execute)
        self.assertEqual(self.agent.steps, 2)

    def test_missing_journal_cycle_identity_and_cycle_count_reject(self):
        for field in ('journal', 'identity', 'cycles'):
            def execute(raw, root):
                result = authored_cycle(raw, root)
                if field == 'journal':
                    result['journal'] = b'{"event":"not_cycle"}\n'
                else:
                    state = strict_json(result['snapshot'])
                    state[field] = {} if field == 'identity' else 99
                    result['snapshot'] = json.dumps(state).encode()
                return result
            with self.assertRaises(ProtocolError):
                self.run_copy(execute)

    def test_other_world_not_learned_and_context_is_broken(self):
        def execute(raw, root):
            result = authored_cycle(raw, root)
            state = strict_json(result['snapshot'])
            state['planning_lab']['transition_observations'][-1]['world_version'] = 'bounded-transfer-world-v1'
            result['snapshot'] = json.dumps(state).encode()
            return result
        result = self.run_copy(execute)
        self.assertEqual(result['temporal']['reason'], 'other_world_not_trained')
        self.assertEqual(result['learner'].steps, 2)
        self.assertEqual(len(result['learner']._history), 0)


class LifecycleStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        self.root.mkdir()
        self.snapshot, self.journal = self.root / 'organism.json', self.root / 'journal.jsonl'
        self.raw, self.history = json.dumps(data()).encode(), b'{"event":"historical"}\n'
        self.snapshot.write_bytes(self.raw)
        self.journal.write_bytes(self.history)
        self.path = self.base / 'copy.sqlite'
        # Explicit fake source identity only for authored transaction tests.
        for target, attr, value in [(storage, 'STATE_BLOB', blob_id(self.raw)),
                                    (storage, 'JOURNAL_BLOB', blob_id(self.history))]:
            mock = patch.object(target, attr, value); mock.start(); self.addCleanup(mock.stop)
        for target in (storage, bridge):
            mock = patch.object(target, 'source_identity', return_value={'authored_fixture': True})
            mock.start(); self.addCleanup(mock.stop)
        mock = patch.object(storage, 'read_origin', return_value=(self.raw, self.history, project(data())))
        mock.start(); self.addCleanup(mock.stop)
        mock = patch.object(bridge, 'execute_phase41', side_effect=authored_cycle)
        self.execute = mock.start(); self.addCleanup(mock.stop)

    def create(self, limit=3):
        return storage.LifecycleSession.create(self.path, self.root, self.snapshot, self.journal,
                                               enabled=True, seed=17, cycle_limit=limit)

    def test_origin_bytes_full_cycle_saved_and_restart_no_execution(self):
        with self.create() as session:
            result = session.tick('one', enabled=True)
            self.assertFalse(result['replayed'])
            expected = session.status()
            archive = session.db.execute('SELECT snapshot,journal FROM origin').fetchone()
            self.assertEqual(archive, (self.raw, self.history))
        with storage.LifecycleSession(self.path, self.root) as session:
            self.assertEqual(session.status(), expected)
            self.assertTrue(session.tick('one', enabled=True)['replayed'])
        self.assertEqual(self.execute.call_count, 1)
        self.assertEqual(self.snapshot.read_bytes(), self.raw)
        self.assertEqual(self.journal.read_bytes(), self.history)

    def test_old_request_after_new_cycle_is_noop(self):
        with self.create() as session:
            first = session.tick('one', enabled=True)['result']
            session.tick('two', enabled=True)
            before = session.status()
            self.assertEqual(session.tick('one', enabled=True)['result'], first)
            self.assertEqual(before, session.status())
        self.assertEqual(self.execute.call_count, 2)

    def test_failure_after_staging_before_commit_rolls_back_both_state_and_event(self):
        with self.create() as session:
            before = session.status()
            session.db.execute("CREATE TRIGGER reject_head BEFORE UPDATE ON current BEGIN SELECT RAISE(ABORT,'test failure'); END")
            with self.assertRaises(sqlite3.DatabaseError):
                session.tick('one', enabled=True)
            self.assertEqual(session.status(), before)
            self.assertEqual(session.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)
            session.db.execute('DROP TRIGGER reject_head')
            session.tick('one', enabled=True)
            self.assertEqual(session.status()['completed_cycles'], 1)

    def test_history_update_delete_and_current_corruption_reject(self):
        with self.create() as session:
            session.tick('one', enabled=True)
            for query in ('DELETE FROM events', 'UPDATE origin SET meta="x"'):
                with self.assertRaises(sqlite3.DatabaseError):
                    session.db.execute(query)
            session.db.execute("UPDATE current SET snapshot='{}'")
            with self.assertRaises((ProtocolError, TypeError)):
                session.status()

    def test_capacity_and_default_off_do_not_mutate_or_run(self):
        with self.create(limit=1) as session:
            with self.assertRaises(ProtocolError):
                session.tick('one')
            session.tick('one', enabled=True)
            before = session.status()
            with self.assertRaises(CapacityError):
                session.tick('two', enabled=True)
            self.assertEqual(session.status(), before)
            self.assertTrue(session.tick('one', enabled=True)['replayed'])
        self.assertEqual(self.execute.call_count, 1)

    def test_creation_never_overwrites_and_cannot_target_source(self):
        with self.create():
            pass
        with self.assertRaises(FileExistsError):
            self.create()
        with self.assertRaises(ProtocolError):
            storage.LifecycleSession.create(self.root / 'bad.sqlite', self.root, self.snapshot, self.journal, enabled=True)
        with self.assertRaises(ProtocolError):
            storage.LifecycleSession(self.base / 'missing.sqlite', self.root)

    def test_bad_requests_are_rejected_without_running(self):
        with self.create() as session:
            for value in (None, '', '../x', 'x' * 129, True):
                with self.assertRaises(ProtocolError):
                    session.tick(value, enabled=True)
        self.assertEqual(self.execute.call_count, 0)


if __name__ == '__main__':
    unittest.main()
