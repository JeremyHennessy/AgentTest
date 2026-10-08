"""Authored edge-case and transaction tests, not evidence of learning benefit."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, Mock

from ora2 import lifecycle, lifecycle_store as store
from ora2.baseline import ACTIONS, WORLD, blob_id, project, public_observation, seeded_agent, strict_json
from ora2.control import apply_selected, learn_selected, validate_effects
from ora2.learner import Config, ProtocolError, CapacityError


def fixture():
    rows = [dict(source='planning_lab', source_id='old1', cycle=1, world_version=WORLD,
                 before=[0, 0], action='north', after=[1, 0], delta=[1, 0], blocked=False),
            dict(source='planning_lab', source_id='old2', cycle=2, world_version=WORLD,
                 before=[1, 0], action='south', after=[0, 0], delta=[-1, 0], blocked=False)]
    return dict(schema_version=24, cycles=2, identity=dict(designation='fixture-only', chosen_name=None),
                episodes=[], planning_lab=dict(world_version=WORLD, bounds=2, position=[0, 0],
                transition_observations=rows, visit_counts={'0,0': 2, '1,0': 1},
                goals=[dict(id='G1', status='active', target=[2, 2])],
                plans=[dict(id='P1', goal_id='G1', status='active', next_step_index=1,
                            actions=['north', 'east'], predicted_states=[[1, 0], [1, -1]])],
                active_plan_id='P1', active_goal_id='G1', executions=[], objective_realizations=[],
                active_objective_realization_id=None, objective_realization_decisions=[]))


def fake_actuator(before, action, **kwargs):
    dx, dy = dict(north=(1, 0), east=(0, -1), south=(-1, 0), west=(0, 1))[action]
    after = [before[0]+dx, before[1]+dy]
    blocked = any(abs(x) > 2 for x in after)
    if blocked:
        after = list(before)
    return dict(before=list(before), after=after, action=action, blocked=blocked,
                delta=[after[0]-before[0], after[1]-before[1]])


def make_choice(state):
    agent = seeded_agent(project(state), seed=17, config=Config())
    predictions = lifecycle.forecast_menu(agent)
    choice = agent.choose(ACTIONS)
    payload = dict(before=public_observation(state['planning_lab']['position']),
                   choice=choice.public(), choice_record=choice.record())
    return agent, predictions, choice, payload


def stage(raw, root, *, decision=None):
    state = strict_json(raw)
    state['cycles'] += 1
    if decision is not None:
        event = apply_selected(state, decision, fake_actuator, lambda lab: None)
        event['episode_id'] = f"E{len(state['episodes'])+1:06d}"
        state['episodes'].append(dict(id=event['episode_id'], kind='ora2_action',
                                      cycle=state['cycles'], content=json.dumps(event)))
    else:
        event = None  # a valid authored idle planner cycle
    result = dict(snapshot=json.dumps(state).encode(),
                  journal=(json.dumps(dict(event='cycle', cycle=state['cycles']))+'\n').encode(),
                  outputs={}, sidecars={})
    if event is not None:
        result['control'] = event
    return result


class OwnedActionTests(unittest.TestCase):
    def test_selected_command_executes_once_and_prediction_is_used(self):
        before = fixture()
        agent, predictions, choice, payload = make_choice(before)
        after = copy.deepcopy(before);after['cycles'] += 1
        execute = Mock(side_effect=fake_actuator)
        event = apply_selected(after, payload, execute, lambda lab: None)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(event['action'], choice.action)
        result = learn_selected(agent, before, after, predictions, choice)
        self.assertEqual(result['ora2_choices'], 1)
        self.assertEqual(result['learning_event']['choice'], choice.record())
        self.assertNotEqual(result['learning_event']['choice']['reason'], 'inherited_observation_not_agent_choice')

    def test_active_plan_is_invalidated_without_false_step_or_goal_credit(self):
        before = fixture();_, _, _, payload = make_choice(before)
        result = stage(json.dumps(before).encode(), None, decision=payload)
        after = strict_json(result['snapshot']); event = result['control']
        validate_effects(before, after, payload, event)
        plan = after['planning_lab']['plans'][0]
        self.assertEqual(plan['next_step_index'], 1)
        self.assertEqual(plan['status'], 'invalidated')
        self.assertIsNone(after['planning_lab']['active_plan_id'])
        self.assertEqual(after['planning_lab']['goals'], before['planning_lab']['goals'])
        self.assertEqual(after['planning_lab']['executions'], [])
        self.assertNotIn('completed_plan_id', after['planning_lab']['goals'][0])

    def test_arrival_is_owned_by_new_action_not_old_plan(self):
        before = fixture();_, _, choice, _ = make_choice(before)
        before['planning_lab']['goals'][0]['target'] = fake_actuator([0, 0], choice.action)['after']
        _, _, _, payload = make_choice(before)
        result = stage(json.dumps(before).encode(), None, decision=payload)
        after = strict_json(result['snapshot']); validate_effects(before, after, payload, result['control'])
        goal = after['planning_lab']['goals'][0]
        self.assertEqual(goal['status'], 'completed')
        self.assertEqual(goal['completion_source'], 'ora2_control')
        self.assertNotIn('completed_plan_id', goal)
        self.assertEqual(after['planning_lab']['plans'][0]['status'], 'invalidated')
        self.assertEqual(after['planning_lab']['plans'][0]['next_step_index'], 1)

    def test_already_occupied_goal_is_not_new_arrival_credit(self):
        state = fixture()
        state['planning_lab']['goals'][0]['target'] = [0, 0]
        _, _, _, payload = make_choice(state)
        state['cycles'] += 1
        event = apply_selected(state, payload,
            lambda before, action, **k: dict(before=before, after=before, action=action,
                                             delta=[0, 0], blocked=True), lambda lab: None)
        self.assertFalse(event['goal_reached'])
        self.assertEqual(state['planning_lab']['goals'][0]['status'], 'active')
        self.assertNotIn('completion_source', state['planning_lab']['goals'][0])
        self.assertEqual(state['planning_lab']['plans'][0]['next_step_index'], 1)

    def test_pending_precommit_is_cancelled_not_realized(self):
        before = fixture();lab = before['planning_lab']
        lab['active_objective_realization_id'] = 'OR1'
        lab['objective_realization_decisions'] = [dict(id='OR1', status='precommitted', state=[0, 0])]
        _, _, _, payload = make_choice(before)
        result = stage(json.dumps(before).encode(), None, decision=payload)
        after = strict_json(result['snapshot']);validate_effects(before, after, payload, result['control'])
        self.assertIsNone(after['planning_lab']['active_objective_realization_id'])
        self.assertEqual(after['planning_lab']['objective_realization_decisions'][0]['status'], 'cancelled_ora2_action')
        self.assertEqual(after['planning_lab']['objective_realizations'], [])

    def test_invalid_reference_rejects_before_any_action(self):
        state = fixture();_, _, _, payload = make_choice(state)
        state['planning_lab']['active_plan_id'] = 'missing'
        prior = copy.deepcopy(state);execute = Mock(side_effect=fake_actuator)
        with self.assertRaises(ProtocolError):apply_selected(state, payload, execute, lambda lab: None)
        execute.assert_not_called();self.assertEqual(prior, state)

    def test_changed_receipt_rejected_and_no_partial_state(self):
        state = fixture();_, _, _, payload = make_choice(state);prior = copy.deepcopy(state)
        with self.assertRaises(ProtocolError):
            apply_selected(state, payload, lambda *a, **k:dict(before=[0, 0],after=[0, 0],action='bad',delta=[0, 0],blocked=False),lambda lab:None)
        self.assertEqual(prior, state)

    def test_rebuild_failure_leaves_old_lab_untouched(self):
        state = fixture();_, _, _, payload = make_choice(state);prior = copy.deepcopy(state)
        with self.assertRaises(RuntimeError):
            apply_selected(state, payload, fake_actuator, Mock(side_effect=RuntimeError('fixture failure')))
        self.assertEqual(prior, state)

    def test_falsely_advanced_plan_and_misattributed_episode_reject(self):
        before = fixture();_, _, _, payload = make_choice(before)
        result = stage(json.dumps(before).encode(), None, decision=payload)
        for field in ('plan', 'episode'):
            after = strict_json(result['snapshot'])
            if field == 'plan':after['planning_lab']['plans'][0]['next_step_index'] += 1
            else:after['episodes'][-1]['kind'] = 'planning_lab'
            with self.assertRaises(ProtocolError):validate_effects(before, after, payload, result['control'])

    def test_forged_forecast_or_wrong_current_position_rejects(self):
        state=fixture();_,_,_,payload=make_choice(state)
        for which in ('forecast', 'position'):
            damaged=copy.deepcopy(payload)
            if which=='forecast':damaged['choice_record']['forecast_sha256']='bad'
            else:damaged['before']['position']=[1,1]
            execute=Mock(side_effect=fake_actuator)
            with self.assertRaises(ProtocolError):apply_selected(state,damaged,execute,lambda lab:None)
            execute.assert_not_called()


class OwnedStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name);self.root=self.directory/'root';self.root.mkdir()
        self.snapshot=self.root/'organism.json';self.journal=self.root/'journal.jsonl'
        self.raw=json.dumps(fixture()).encode();self.history=b'{"event":"history"}\n'
        self.snapshot.write_bytes(self.raw);self.journal.write_bytes(self.history)
        self.path=self.directory/'session.sqlite'
        for module, key, value in ((store,'STATE_BLOB',blob_id(self.raw)),(store,'JOURNAL_BLOB',blob_id(self.history))):
            p=patch.object(module,key,value);p.start();self.addCleanup(p.stop)
        for module in (lifecycle, store):
            p=patch.object(module,'source_identity',return_value={'fixture':True});p.start();self.addCleanup(p.stop)
        p=patch.object(store,'read_origin',return_value=(self.raw,self.history,project(fixture())))
        p.start();self.addCleanup(p.stop)
        p=patch.object(lifecycle,'execute_phase41',side_effect=stage)
        self.execute=p.start();self.addCleanup(p.stop)

    def create(self, enabled=True):
        return store.LifecycleSession.create(self.path,self.root,self.snapshot,self.journal,
                     enabled=True,seed=17,cycle_limit=3,allow_ora2=enabled)

    def test_mixed_ownership_reopens_without_action_and_exact_retry(self):
        with self.create() as s:
            first=s.tick('a',enabled=True,owner='ora2')['result']
            s.tick('b',enabled=True)
            s.tick('c',enabled=True,owner='ora2')
            status=s.status();self.assertEqual(status['ora2_choices'],2)
            self.assertEqual(status['completed_cycles'],3)
            self.assertEqual(s.tick('a',enabled=True,owner='ora2')['result'],first)
            with self.assertRaises(ProtocolError):s.tick('a',enabled=True,owner='phase41')
            self.assertEqual(s.db.execute('SELECT snapshot,journal FROM origin').fetchone(),(self.raw,self.history))
        with store.LifecycleSession(self.path,self.root) as s:self.assertEqual(s.status(),status)
        self.assertEqual(self.execute.call_count,3)
        self.assertEqual(self.snapshot.read_bytes(),self.raw)

    def test_passive_session_cannot_gain_control_at_tick(self):
        with self.create(False) as s:
            with self.assertRaises(ProtocolError):s.tick('a',enabled=True,owner='ora2')
            self.assertEqual(s.status()['completed_cycles'],0)
        self.execute.assert_not_called()

    def test_owned_write_failure_rolls_back_learning_action_and_plan(self):
        with self.create() as s:
            before=s.status()
            s.db.execute("CREATE TRIGGER reject_update BEFORE UPDATE ON current BEGIN SELECT RAISE(ABORT,'test rollback'); END")
            with self.assertRaises(sqlite3.DatabaseError):s.tick('a',enabled=True,owner='ora2')
            self.assertEqual(before,s.status());self.assertEqual(s.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
            s.db.execute('DROP TRIGGER reject_update')
            s.tick('a',enabled=True,owner='ora2')
            self.assertEqual(s.status()['ora2_choices'],1)

    def test_one_forecast_before_execution_and_no_input_mutation(self):
        original=seeded_agent(project(fixture()),seed=17,config=Config())
        old=original.summary();rng=original._random.getstate()
        result=lifecycle.run_cycle(self.raw,original,self.root,enabled=True,owner='ora2')
        self.assertEqual(original.summary(),old);self.assertEqual(original._random.getstate(),rng)
        self.assertEqual(result['temporal']['ora2_choices'],1)
        self.assertNotEqual(result['learner']._random.getstate(),rng)

    def test_wrong_owner_and_default_off_never_execute(self):
        with self.create() as s:
            for owner in ('bad',None,1):
                with self.assertRaises(ProtocolError):s.tick('a',enabled=True,owner=owner)
            with self.assertRaises(ProtocolError):s.tick('a',owner='ora2')
        self.execute.assert_not_called()


if __name__ == '__main__':unittest.main()
