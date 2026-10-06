from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from agenttest import planning_lab
from agenttest.action_lab import step_action_lab
from agenttest.planning_lab import ensure_planning_lab_state, step_planning_lab
from agenttest.state import StateStore, initial_state


def add_source_actions(state, through):
    for cycle in range(len(state['action_lab']['history']) + 1, through + 1):
        state['cycles'] = state['generation'] = cycle
        step_action_lab(state)


class BootstrapRecoveryTests(unittest.TestCase):
    def test_zero_and_three_record_retry_ingests_later_eight_and_matches_fresh(self):
        for first_count in (0, 3):
            with self.subTest(first_count=first_count):
                state=initial_state();add_source_actions(state,first_count)
                self.assertEqual(step_planning_lab(state)['status'],'waiting_for_model')
                old=deepcopy(state['planning_lab']['transition_observations'])
                add_source_actions(state,8)
                with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as apply:
                    result=step_planning_lab(state)
                self.assertEqual(apply.call_count,1)
                self.assertEqual(result['action'],'east')
                self.assertEqual(result['action'],apply.call_args.args[1])
                copied=[r for r in state['planning_lab']['transition_observations'] if r.get('source')=='action_lab']
                self.assertEqual(len(copied),8)
                self.assertEqual(copied[:first_count],old)
                fresh=initial_state();add_source_actions(fresh,8)
                control=step_planning_lab(fresh)
                self.assertEqual(result,control)

    def test_repeated_partial_retries_are_idempotent_and_no_actions(self):
        state=initial_state();add_source_actions(state,3)
        step_planning_lab(state)
        before=deepcopy(state['planning_lab'])
        with patch.object(planning_lab,'apply_bounded_action',side_effect=AssertionError('waiting action')):
            for _ in range(4):
                self.assertEqual(step_planning_lab(state)['status'],'waiting_for_model')
                self.assertEqual(state['planning_lab'],before)

    def test_retry_survives_reload_and_preserves_copied_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json');state=initial_state();add_source_actions(state,3)
            step_planning_lab(state);old=deepcopy(state['planning_lab']['transition_observations'])
            store.save(state);state=store.load();add_source_actions(state,8)
            result=step_planning_lab(state)
            self.assertEqual(result['action'],'east')
            self.assertEqual(state['planning_lab']['transition_observations'][:3],old)
            store.save(state);state=store.load()
            self.assertEqual(len([r for r in state['planning_lab']['transition_observations'] if r.get('source')=='action_lab']),8)

    def test_invalid_later_source_is_rejected_before_ingestion(self):
        state=initial_state();add_source_actions(state,3);step_planning_lab(state);add_source_actions(state,8)
        state['action_lab']['history'][-1]['after']=[99,99]
        before=deepcopy(state['planning_lab'])
        with self.assertRaises(ValueError):step_planning_lab(state)
        self.assertEqual(state['planning_lab'],before)

    def test_valid_but_replaced_source_prefix_is_not_overwritten(self):
        state=initial_state();add_source_actions(state,3);step_planning_lab(state)
        # A independently valid replacement ledger has different cycles under
        # the same source IDs; this must not rewrite previously copied evidence.
        replacement=initial_state();add_source_actions(replacement,8)
        for r in replacement['action_lab']['history']:r['cycle']+=20
        state['action_lab']=replacement['action_lab'];state['cycles']=28
        before=deepcopy(state['planning_lab'])
        with self.assertRaises(ValueError):step_planning_lab(state)
        self.assertEqual(state['planning_lab'],before)

    def test_source_retraction_and_duplicate_copied_ids_fail_closed(self):
        for duplicate in (False,True):
            state=initial_state();add_source_actions(state,3);step_planning_lab(state)
            if duplicate:
                state['planning_lab']['transition_observations'].append(deepcopy(state['planning_lab']['transition_observations'][0]))
            else:
                state['action_lab']=initial_state()['action_lab']
            before=deepcopy(state['planning_lab'])
            with self.assertRaises(ValueError):step_planning_lab(state)
            self.assertEqual(state['planning_lab'],before)

    def test_non_source_records_and_existing_annotation_are_preserved(self):
        state=initial_state();add_source_actions(state,3);step_planning_lab(state)
        lab=state['planning_lab'];lab['transition_observations'][0]['annotation']='retained'
        other=dict(source='historical_note',source_id='LA000001',action='not_an_action',payload='original')
        lab['transition_observations'].append(other)
        before=deepcopy(lab['transition_observations'])
        add_source_actions(state,8);step_planning_lab(state)
        self.assertEqual(lab['transition_observations'][:len(before)],before)
        self.assertEqual(len([r for r in lab['transition_observations'] if r.get('source')=='action_lab']),8)

    def test_executing_planner_does_not_reimport_or_reset(self):
        state=initial_state();add_source_actions(state,8);step_planning_lab(state)
        lab=state['planning_lab'];before=deepcopy(lab)
        add_source_actions(state,10)
        self.assertTrue(planning_lab._bootstrap_from_action_lab(state,lab))
        self.assertEqual(lab,before)

    def test_degraded_existing_planner_waits_without_resetting_goals_or_source_import(self):
        state=initial_state();add_source_actions(state,8);step_planning_lab(state)
        lab=state['planning_lab'];lab['transition_observations']=[]
        old_goals=deepcopy(lab['goals']);old_plans=deepcopy(lab['plans'])
        with patch.object(planning_lab,'apply_bounded_action',side_effect=AssertionError('degraded action')):
            for _ in range(2):
                self.assertIsNone(step_planning_lab(state)['action'])
        self.assertEqual(lab['transition_observations'],[])
        self.assertEqual(lab['goals'],old_goals)
        self.assertEqual(lab['plans'],old_plans)


if __name__=='__main__':unittest.main()
