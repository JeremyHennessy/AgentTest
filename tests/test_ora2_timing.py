"""Authored timing contracts and transactional replay; no learning-benefit claim."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ora2 import lifecycle, lifecycle_store as store
from ora2.baseline import blob_id, project, seeded_agent
from ora2.learner import Agent, Config, ProtocolError
from ora2.timing import context, decide
from test_ora2_control import fixture, stage


class Evidence:
    def __init__(self, gain=0.1): self.gain = gain
    def progress(self, action): return self.gain
    def summary(self): return {'pending': None}


def boundary():
    state = fixture()
    state['planning_lab']['active_plan_id'] = None
    state['planning_lab']['plans'][0]['status'] = 'invalidated'
    return state


def policy(current, previous=None, mode='progress', gain=0.1, sequence=1):
    return decide(Evidence(gain), current, previous_owner=previous,
                  policy=mode, seed=17, sequence=sequence)


class TimingPolicyTests(unittest.TestCase):
    def test_protects_referenced_plan_even_with_progress(self):
        value = context(fixture())
        for mode in ('progress', 'random', 'planner'):
            result = policy(value, mode=mode)
            self.assertFalse(result['eligible'])
            self.assertEqual(result['owner'], 'phase41')
            self.assertEqual(result['reason'], 'preserve_referenced_plan')

    def test_preserves_pending_commitment_at_boundary(self):
        state = boundary()
        state['planning_lab'].update(active_objective_realization_id='OR1',
            objective_realization_decisions=[{'id': 'OR1', 'status': 'precommitted'}])
        result = policy(context(state))
        self.assertEqual(result['reason'], 'preserve_pending_commitment')
        self.assertEqual(result['owner'], 'phase41')

    def test_goal_already_occupied_returns_to_bookkeeping(self):
        state = boundary(); state['planning_lab']['goals'][0]['target'] = [0, 0]
        result = policy(context(state))
        self.assertEqual(result['reason'], 'planner_goal_bookkeeping_due')
        self.assertEqual(result['owner'], 'phase41')

    def test_positive_evidence_changes_opportunity_at_same_boundary(self):
        value = context(boundary())
        self.assertEqual(policy(value, gain=0)['owner'], 'phase41')
        self.assertEqual(policy(value, gain=0.1)['owner'], 'ora2')
        self.assertEqual(policy(value, previous='ora2')['owner'], 'phase41')
        self.assertEqual(policy(value, previous='phase41')['owner'], 'ora2')

    def test_random_control_does_not_depend_on_progress(self):
        value = context(boundary())
        for seq in range(1, 20):
            a, b = policy(value, mode='random', gain=0, sequence=seq), policy(value, mode='random', gain=99, sequence=seq)
            self.assertEqual(a['owner'], b['owner'])
            self.assertEqual(a['random_draw'], b['random_draw'])
            self.assertGreaterEqual(a['random_draw'], 0)
            self.assertLess(a['random_draw'], 1)

    def test_missing_or_duplicate_commitment_fails_closed(self):
        for duplicate in (False, True):
            state = fixture()
            if duplicate: state['planning_lab']['plans'].append(copy.deepcopy(state['planning_lab']['plans'][0]))
            else: state['planning_lab']['active_plan_id'] = 'missing'
            with self.assertRaises(ProtocolError): context(state)

    def test_timing_preserves_predictor_action_rng_and_current_state(self):
        state = boundary(); before = copy.deepcopy(state)
        agent = seeded_agent(project(state), seed=17, config=Config())
        rng, summary = agent._random.getstate(), agent.summary()
        for mode in ('progress', 'random', 'planner'):
            decide(agent, context(state), previous_owner=None, policy=mode, seed=17, sequence=1)
        self.assertEqual(state, before)
        self.assertEqual(agent.summary(), summary)
        self.assertEqual(agent._random.getstate(), rng)

    def test_invalid_timing_values_and_outstanding_choice_reject(self):
        value = context(boundary())
        for gain in (float('nan'), float('inf'), -1, True):
            with self.assertRaises(ProtocolError): policy(value, gain=gain)
        agent = seeded_agent(project(boundary()), seed=17, config=Config())
        agent.choose(('north', 'east', 'south', 'west'))
        with self.assertRaises(ProtocolError):
            decide(agent, value, previous_owner=None, policy='progress', seed=17, sequence=1)


class TimedStorageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)/'source'; self.root.mkdir()
        self.path = Path(tmp.name)/'timed.sqlite'
        self.raw = json.dumps(boundary()).encode(); self.history = b'{"event":"fixture"}\n'
        self.snapshot, self.journal = self.root/'snapshot', self.root/'journal'
        self.snapshot.write_bytes(self.raw); self.journal.write_bytes(self.history)
        for module, name, value in ((store, 'STATE_BLOB', blob_id(self.raw)), (store, 'JOURNAL_BLOB', blob_id(self.history))):
            p = patch.object(module, name, value); p.start(); self.addCleanup(p.stop)
        for module in (store, lifecycle):
            p = patch.object(module, 'source_identity', return_value={'authored_fixture': True}); p.start(); self.addCleanup(p.stop)
        p = patch.object(store, 'read_origin', return_value=(self.raw,self.history,project(boundary())))
        p.start(); self.addCleanup(p.stop)
        p = patch.object(lifecycle, 'execute_phase41', side_effect=stage)
        self.execute = p.start(); self.addCleanup(p.stop)
        # Positive signal is authored for transaction coverage, not study evidence.
        p = patch.object(Agent, 'progress', return_value=0.1)
        p.start(); self.addCleanup(p.stop)

    def create(self, policy_name='progress', allow=True):
        return store.LifecycleSession.create(self.path, self.root, self.snapshot, self.journal,
            enabled=True, seed=17, cycle_limit=3, allow_ora2=allow, timing_policy=policy_name)

    def test_timing_replays_choices_and_enforces_return_to_planner(self):
        with self.create() as session:
            first = session.tick('a', enabled=True, owner='auto')['result']
            second = session.tick('b', enabled=True, owner='auto')['result']
            third = session.tick('c', enabled=True, owner='auto')['result']
            self.assertEqual([r['timing']['owner'] for r in (first,second,third)], ['ora2','phase41','ora2'])
            status = session.status()
            with patch.object(store, 'run_cycle', side_effect=AssertionError('no execution on reopen')):
                self.assertTrue(session.tick('a', enabled=True, owner='auto')['replayed'])
                with store.LifecycleSession(self.path, self.root) as reopened:
                    self.assertEqual(reopened.status(), status)
            self.assertEqual(session.db.execute('SELECT snapshot,journal FROM origin').fetchone(), (self.raw,self.history))
        self.assertEqual(self.execute.call_count, 3)

    def test_existing_manual_session_cannot_gain_timed_authority(self):
        with self.create('manual') as session:
            with self.assertRaises(ProtocolError): session.tick('a', enabled=True, owner='auto')
        self.execute.assert_not_called()

    def test_timed_session_cannot_accept_manual_owner_or_default_enablement(self):
        with self.create() as session:
            for owner in ('phase41','ora2'):
                with self.assertRaises(ProtocolError): session.tick('a',enabled=True,owner=owner)
            with self.assertRaises(ProtocolError): session.tick('a',owner='auto')
        self.execute.assert_not_called()

    def test_policy_requires_explicit_matching_authority(self):
        for mode,allow in [('progress',False),('random',False),('planner',True),('bad',False)]:
            with self.assertRaises(ProtocolError): self.create(mode,allow)
        self.assertFalse(self.path.exists())

    def test_timing_rollback_preserves_next_choice_and_context(self):
        with self.create() as session:
            before = session.status()
            session.db.execute("CREATE TRIGGER reject_update BEFORE UPDATE ON current BEGIN SELECT RAISE(ABORT,'fixture'); END")
            with self.assertRaises(sqlite3.DatabaseError): session.tick('a',enabled=True,owner='auto')
            self.assertEqual(session.status(),before)
            self.assertEqual(session.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
            session.db.execute('DROP TRIGGER reject_update')
            result=session.tick('a',enabled=True,owner='auto')['result']
            self.assertEqual(result['timing']['owner'],'ora2')

    def test_resealed_false_timing_is_rejected_semantically(self):
        with self.create() as session:
            session.tick('a',enabled=True,owner='auto')
            seq,body,prior=session.db.execute('SELECT seq,body,prior FROM events').fetchone()
            record=json.loads(body); record['timing']['retained_progress'][0]=999
            changed=store.encode(record); seal=store.seal(prior,changed)
            session.db.execute('DROP TRIGGER events_UPDATE')
            session.db.execute('UPDATE events SET body=?,seal=?',(changed,seal))
            session.db.execute('UPDATE current SET seal=?',(seal,))
            with self.assertRaises(ProtocolError): session.status()

    def test_current_commitment_drift_is_detected(self):
        with self.create() as session:
            session.tick('a',enabled=True,owner='auto')
            row=session.db.execute('SELECT snapshot FROM current').fetchone()[0]
            state=json.loads(row); state['planning_lab']['goals'][0]['target']=[2,1]
            changed=json.dumps(state).encode(); body,prior=session.db.execute('SELECT body,prior FROM events').fetchone()
            event=json.loads(body); event['after_snapshot_sha256']=store.sha(changed)
            body=store.encode(event); seal=store.seal(prior,body)
            session.db.execute('DROP TRIGGER events_UPDATE')
            session.db.execute('UPDATE events SET body=?,seal=?',(body,seal))
            session.db.execute('UPDATE current SET snapshot=?,seal=?',(changed,seal))
            with self.assertRaises(ProtocolError): session.status()


if __name__=='__main__': unittest.main()
