"""Authored evaluator/accounting tests. These are not scientific study sessions."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tests'))
from test_ora2_control import fixture, make_choice, stage
from ora2.baseline import ACTIONS, WORLD
from ora2.learner import Agent, Config
from ora2.timing import context
from run import ARMS, CELLS, CYCLES, VERSION, audit_cycle, evaluate, summarize


def reports(advantage=0.1, goals=True):
    cohort=[{'id':'G1','target':[2,2]}] if goals else []
    values=[]
    for policy,seed in ARMS:
        learner=1 if policy!='planner' else 0
        values.append({'version':VERSION,'status':'valid','policy':policy,'seed':seed,'cycles':CYCLES,
            'live_actions':0,'oracle_calls':100,'source':{'head':'authored','base':'authored'},
            'origin_sha256':{'snapshot':'authored','journal':'authored'},
            'initial_active_goals':copy.deepcopy(cohort),'initial_cohort_empty':not cohort,
            'initial_goal_results':[dict(g,completed=True,completed_at_step=5) for g in cohort],
            'initial_loss_bits':2.,'endpoint_loss_bits':1.1-advantage if policy=='progress' else 1.1,
            'endpoint_top1_accuracy':0.9,'learner_actions':learner,'planner_actions':32-learner,
            'idle_cycles':0,'previously_observed_blocked_actions':0,'self_selected_goals_completed':2,
            'new_objective_realizations':0,'learner_then_planner':bool(learner),
            'protected_interruptions':0,'precommit_cancellations':0,'false_goal_credit':0,'duplicate_actions':0,
            'midrun_cold_resume':True,'final_cold_restart':True,'old_request_noop':True})
    return values


def owned_cycle():
    before=fixture();before['planning_lab']['active_plan_id']=None
    before['planning_lab']['plans'][0]['status']='invalidated'
    agent,predictions,choice,payload=make_choice(before)
    staged=stage(json.dumps(before).encode(),None,decision=payload)
    after=json.loads(staged['snapshot'])
    row=after['planning_lab']['transition_observations'][-1]
    return before,after,{'cycle':after['cycles'],'owner':'ora2','control':staged['control'],
        'timing':{'context':context(before),'owner':'ora2','previous_owner':None,'eligible':True,'reason':'authored'},
        'timing_context_after':context(after),
        'temporal':{'transition_records':[row],'learning_event':{'choice':choice.record()}}}


class StudyTests(unittest.TestCase):
    def test_evaluator_covers_all_cases_without_mutating_predictor(self):
        agent=Agent({'position':[0,0]},seed=7,config=Config())
        truths={(p,a):{'after':list(p)} for p in CELLS for a in ACTIONS}
        state=copy.deepcopy(agent.__dict__); rng=agent._random.getstate()
        result=evaluate(agent,truths)
        self.assertEqual(len(result['cases']),100)
        self.assertGreater(result['loss_bits'],0)
        self.assertEqual(agent._random.getstate(),rng)
        self.assertEqual(agent._tables,state['_tables'])

    def test_same_world_pairs_small_screen_is_explicit(self):
        result=summarize(reports())
        self.assertEqual(result['sessions'],9);self.assertEqual(result['copied_cycles'],288)
        self.assertEqual(result['oracle_calls'],900);self.assertEqual(result['live_actions'],0)
        self.assertTrue(result['keep_screen_met']);self.assertEqual(result['wins'],4)
        self.assertAlmostEqual(result['mean_advantage_bits'],.1)

    def test_negative_and_tied_results_do_not_activate(self):
        for advantage in (0,-.1):
            result=summarize(reports(advantage))
            self.assertFalse(result['keep_screen_met'])
            self.assertEqual(result['decision'],'do_not_activate_pilot')

    def test_fewer_than_three_wins_does_not_pass_despite_mean_gain(self):
        values=reports(.1)
        for r in values:
            if r['policy']=='progress':r['endpoint_loss_bits']=.1 if r['seed']==0 else 1.2
        result=summarize(values)
        self.assertGreater(result['mean_advantage_bits'],0);self.assertEqual(result['wins'],1)
        self.assertFalse(result['keep_screen_met'])

    def test_missing_duplicate_and_nonfinite_runs_are_invalid(self):
        values=reports()
        invalid=[values[:-1],values[:-1]+[copy.deepcopy(values[0])]]
        broken=copy.deepcopy(values);broken[0]['endpoint_loss_bits']=float('nan');invalid.append(broken)
        for data in invalid:
            with self.assertRaises(ValueError):summarize(data)

    def test_mixed_source_or_accounting_is_not_a_valid_comparison(self):
        for field,value in [('source',{'head':'different'}),('cycles',33),('planner_actions',100),('midrun_cold_resume',False),('protected_interruptions',1)]:
            values=reports();values[0][field]=value
            with self.assertRaises(ValueError):summarize(values)

    def test_initial_commitment_failure_blocks_positive_prediction_result(self):
        values=reports();values[0]['initial_goal_results'][0]['completed']=False
        result=summarize(values)
        self.assertFalse(result['initial_commitments_preserved']);self.assertFalse(result['keep_screen_met'])

    def test_empty_initial_cohort_is_reported_not_fabricated(self):
        result=summarize(reports(goals=False))
        self.assertTrue(result['initial_cohort_empty'])
        self.assertTrue(result['initial_commitments_preserved'])

    def test_no_actual_control_or_return_blocks_pilot_screen(self):
        values=reports()
        for r in values:
            if r['policy']=='progress':
                r['learner_actions']=0;r['planner_actions']=32;r['learner_then_planner']=False
        self.assertFalse(summarize(values)['keep_screen_met'])

    def test_audit_uses_actual_action_and_preserves_old_goal(self):
        before,after,record=owned_cycle()
        result=audit_cycle(before,after,record,None,set())
        self.assertEqual(result['owner'],'ora2');self.assertEqual(result['completed_goals'],[])
        self.assertEqual(result['action'],record['control']['action'])

    def test_reused_action_and_protected_plan_are_rejected(self):
        before,after,record=owned_cycle();row=record['temporal']['transition_records'][0]
        with self.assertRaises(ValueError):audit_cycle(before,after,record,None,{(row['source'],row['source_id'])})
        before['planning_lab']['active_plan_id']='P1';before['planning_lab']['plans'][0]['status']='active'
        record['timing']['context']=context(before)
        with self.assertRaises(ValueError):audit_cycle(before,after,record,None,set())

    def test_false_arrival_at_already_occupied_target_is_rejected(self):
        before,after,record=owned_cycle()
        target=after['planning_lab']['position'];before['planning_lab']['position']=target
        before['planning_lab']['goals'][0]['target']=target
        after['planning_lab']['goals'][0].update(target=target,status='completed',completion_source='ora2_control',
            completed_execution_id=record['control']['id'])
        record['control']['before']=target;record['timing']['context']=context(before)
        record['timing_context_after']=context(after)
        with self.assertRaises(ValueError):audit_cycle(before,after,record,None,set())


if __name__=='__main__':unittest.main()
