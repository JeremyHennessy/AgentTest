from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from agenttest import objective_identity, planning_lab
from agenttest.objective_identity import (
    allocate_objective_decision_id, ensure_objective_identity,
    resolve_objective_decision,
)
from agenttest.planning_lab import ensure_planning_lab_state, initial_planning_lab_state, step_planning_lab
from agenttest.state import StateStore, initial_state, migrate_state
from tests import test_planning_lab as fixtures


def phase40_state():
    state = fixtures.PlanningLabTests()._phase32_ready_state()
    lab = ensure_planning_lab_state(state)
    assert planning_lab._bootstrap_from_action_lab(state, lab)
    lab['position'] = [0, 0]
    lab['visit_counts'] = {'0,0': 1}
    lab['goals'] = [dict(id='PG_P40', assigned_cycle=11, completed_cycle=14,
                         status='completed', target=[0,0],
                         selection={'kind': 'self_selected_bounded_objective', 'objective_decision_id': 'OD_P40'})]
    lab['objective_decisions'] = [dict(id='OD_P40', cycle=11, changed_choice=True, selected={'target':[0,0]})]
    lab['active_goal_id'] = lab['active_plan_id'] = None
    lab['objective_realization_started_cycle'] = 10
    lab['status'] = 'goal_reached'
    state['cycles'] = 15
    return state


class ObjectiveIdentityTests(unittest.TestCase):
    def test_empty_and_opaque_legacy_allocation(self):
        lab = {}
        self.assertEqual(allocate_objective_decision_id(lab), 'OD000001')
        self.assertEqual(allocate_objective_decision_id(lab), 'OD000002')
        lab = dict(objective_decisions=[{'id':'OD_OPAQUE'}])
        self.assertEqual(allocate_objective_decision_id(lab), 'OD000002')
        self.assertEqual(resolve_objective_decision(lab, 'OD_OPAQUE')['status'], 'unique')

    def test_floor_includes_surviving_citations_and_quarantine(self):
        lab = dict(objective_decisions=[{'id':'OD000129'}]*128,
                   goals=[{'selection':{'objective_decision_id':'OD001000'}}],
                   objective_realization_decisions=[{'objective_decision_id':'OD000200'}],
                   objective_realizations=[{'objective_decision_id':'OD000500'}],
                   objective_decision_ambiguous_ids=['OD002000'])
        self.assertEqual(allocate_objective_decision_id(lab), 'OD002001')
        self.assertEqual(lab['objective_decision_ambiguous_ids'], ['OD000129','OD002000'])
        for collection in ('goals','objective_realization_decisions','objective_realizations'):
            with self.subTest(collection=collection):
                citation = {'objective_decision_id':'OD000900'}
                record = {'selection':citation} if collection=='goals' else citation
                isolated = {collection:[record]}
                self.assertEqual(allocate_objective_decision_id(isolated),'OD000901')

    def test_checkpoint_shape_floor_is_130_not_lifetime_ordinal(self):
        lab = dict(objective_decisions=[{'id':'OD000129','cycle':i} for i in range(128)])
        old = deepcopy(lab['objective_decisions'])
        self.assertEqual(allocate_objective_decision_id(lab), 'OD000130')
        self.assertEqual(lab['objective_decisions'], old)
        self.assertEqual(resolve_objective_decision(lab, 'OD000129')['status'], 'ambiguous')

    def test_watermark_never_decreases_after_retention(self):
        lab = dict(next_objective_decision_index=500, objective_decisions=[])
        self.assertEqual(allocate_objective_decision_id(lab), 'OD000500')
        lab['objective_decisions'] = []
        self.assertEqual(allocate_objective_decision_id(lab), 'OD000501')

    def test_numeric_aliases_and_long_suffixes(self):
        lab = dict(objective_decisions=[{'id':'OD1'},{'id':'OD000001'},{'id':'OD1000001'}])
        self.assertEqual(allocate_objective_decision_id(lab), 'OD1000002')

    def test_invalid_watermarks_fail_before_allocation_mutation(self):
        for invalid in (None, True, False, 0, -1, 1.0, '10', [], {}):
            with self.subTest(value=invalid):
                lab = dict(next_objective_decision_index=invalid, objective_decisions=[{'id':'OD1'}])
                before = deepcopy(lab)
                with self.assertRaises(ValueError): allocate_objective_decision_id(lab)
                self.assertEqual(lab, before)

    def test_invalid_quarantine_is_not_silently_cleared(self):
        for invalid in (None, 'OD1', [None], ['']):
            lab = dict(objective_decision_ambiguous_ids=invalid)
            before = deepcopy(lab)
            with self.assertRaises(ValueError): ensure_objective_identity(lab)
            self.assertEqual(lab, before)

    def test_quarantine_survives_two_to_one_to_zero_rows_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json')
            state=initial_state()
            lab=state['planning_lab']
            lab['objective_decisions']=[{'id':'OD000129','changed_choice':True},{'id':'OD000129','changed_choice':False}]
            ensure_objective_identity(lab)
            for retained in (lab['objective_decisions'][:1], []):
                lab['objective_decisions']=retained
                store.save(state)
                state=store.load(); lab=state['planning_lab']
                self.assertEqual(resolve_objective_decision(lab,'OD000129')['status'],'ambiguous')
                self.assertGreaterEqual(lab['next_objective_decision_index'],130)
            self.assertEqual(allocate_objective_decision_id(lab),'OD000130')

    def test_lookup_is_readonly_and_equal_content_duplicates_are_ambiguous(self):
        lab=dict(objective_decisions=[{'id':'OD_X','changed_choice':True}]*2)
        before=deepcopy(lab)
        self.assertEqual(resolve_objective_decision(lab,'OD_X')['status'],'ambiguous')
        self.assertEqual(resolve_objective_decision(lab,'OD_GONE')['status'],'unavailable')
        self.assertEqual(resolve_objective_decision(lab,None)['status'],'invalid')
        self.assertEqual(lab,before)

    def test_migration_adds_only_metadata_preserves_histories_and_is_idempotent(self):
        state=phase40_state(); lab=state['planning_lab']
        lab.pop('next_objective_decision_index');lab.pop('objective_decision_ambiguous_ids')
        lab['objective_decisions']*=2
        before=deepcopy(lab)
        migrated=migrate_state(state)['planning_lab']
        historical={k:v for k,v in migrated.items() if k not in {'next_objective_decision_index','objective_decision_ambiguous_ids'}}
        self.assertEqual(historical,before)
        self.assertEqual(migrated['objective_decision_ambiguous_ids'],['OD_P40'])
        again=deepcopy(migrated)
        self.assertEqual(migrate_state(state)['planning_lab'],again)

    def test_real_selection_crosses_retention_boundary_and_reload(self):
        state=fixtures.PlanningLabTests()._phase32_ready_state();lab=ensure_planning_lab_state(state)
        planning_lab._bootstrap_from_action_lab(state,lab)
        lab['position']=[0,0];lab['visit_counts']={'0,0':1}
        lab['goals']=[{'id':'PG_A','status':'completed','target':[1,0]},{'id':'PG_B','status':'completed','target':[0,1]}]
        lab['self_experiments']=[{'id':'SE_A','goal_id':'PG_A','interpretation':'hypothesis_supported'},{'id':'SE_B','goal_id':'PG_B','interpretation':'hypothesis_refuted'}]
        lab['objective_selection_started_cycle']=8
        ids=[]
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json')
            for i in range(140):
                cycle=9+12*i;state['cycles']=cycle
                goal=planning_lab._choose_goal(lab,cycle)
                ids.append(lab['objective_decisions'][-1]['id'])
                self.assertEqual(goal['selection']['objective_decision_id'],ids[-1])
                goal['status']='completed';lab['active_goal_id']=None
                if i==129:
                    store.save(state);state=store.load();lab=state['planning_lab']
            self.assertEqual(ids[127:131],['OD000128','OD000129','OD000130','OD000131'])
            self.assertEqual(len(set(ids)),140)
            self.assertEqual(len(lab['objective_decisions']),128)
            self.assertEqual(lab['next_objective_decision_index'],141)

    def test_missing_selection_provenance_does_not_suppress_ordinary_planning(self):
        state=phase40_state();lab=state['planning_lab'];lab['objective_decisions']=[]
        with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as apply:
            result=step_planning_lab(state)
        self.assertEqual(apply.call_count,1)
        self.assertEqual(result['objective_provenance_blocks'][0]['provenance_status'],'unavailable')
        self.assertEqual(result['action'],apply.call_args.args[1])
        self.assertEqual(lab['objective_realizations'],[])
        self.assertEqual(lab['objective_realization_decisions'],[])

    def test_conflicting_duplicates_create_no_precommit_but_fallback_one_action(self):
        state=phase40_state();lab=state['planning_lab']
        lab['objective_decisions'].append(dict(lab['objective_decisions'][0],changed_choice=False))
        before=deepcopy(lab['objective_decisions'])
        with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as apply:
            result=step_planning_lab(state)
        self.assertEqual(apply.call_count,1)
        self.assertEqual(result['objective_provenance_blocks'][0]['provenance_status'],'ambiguous')
        self.assertEqual(lab['objective_decisions'],before)
        self.assertEqual(lab['objective_realization_decisions'],[])

    def test_old_missing_provenance_direct_handoff_fixture_is_negative_regression(self):
        state=phase40_state();lab=state['planning_lab'];lab['objective_decisions']=[]
        decision=dict(id='OR_H1',state=[0,0],action='north',predicted_after=[1,0],goal_id='PG_OR_H1',objective_decision_id='OD_OR_H1')
        before=deepcopy(decision);transitions=deepcopy(lab['transition_observations'])
        with patch.object(planning_lab,'apply_bounded_action',side_effect=AssertionError('unsupported Phase40 action')):
            result=planning_lab._execute_objective_realization(lab,decision,16)
        self.assertIsNone(result['action'])
        self.assertEqual(result['objective_provenance_block']['provenance_status'],'unavailable')
        self.assertEqual(decision,before)
        self.assertEqual(lab['transition_observations'],transitions)
        self.assertEqual(lab['objective_realizations'],[])

    def test_direct_block_records_quarantine_before_later_retention(self):
        state=phase40_state();lab=state['planning_lab'];lab['objective_decisions']*=2
        self.assertIsNone(planning_lab._select_objective_realization(lab,15))
        lab['objective_decisions']=lab['objective_decisions'][:1]
        self.assertEqual(resolve_objective_decision(lab,'OD_P40')['status'],'ambiguous')

    def test_direct_unsupported_record_cannot_clear_another_active_cursor(self):
        state=phase40_state();lab=state['planning_lab']
        lab['active_objective_realization_id']='OR_VALID'
        decision=dict(id='OR_OLD',objective_decision_id='OD_GONE',goal_id='PG_OLD')
        result=planning_lab._execute_objective_realization(lab,decision,16)
        self.assertIsNone(result['action'])
        self.assertEqual(lab['active_objective_realization_id'],'OR_VALID')

    def test_blocked_precommit_preserved_cursor_cleared_no_retry_or_double_action(self):
        for unavailable in (False,True):
            with self.subTest(unavailable=unavailable), tempfile.TemporaryDirectory() as tmp:
                state=phase40_state();lab=state['planning_lab']
                self.assertEqual(step_planning_lab(state)['execution_kind'],'objective_information_precommit')
                prior=deepcopy(lab['objective_realization_decisions'])
                lab['objective_decisions']=[] if unavailable else lab['objective_decisions']*2
                store=StateStore(Path(tmp)/'state.json');store.save(state);state=store.load();lab=state['planning_lab'];state['cycles']=16
                with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as apply:
                    result=step_planning_lab(state)
                self.assertEqual(apply.call_count,1)
                self.assertEqual(result['action'],apply.call_args.args[1])
                self.assertEqual(lab['objective_realization_decisions'],prior)
                self.assertIsNone(lab['active_objective_realization_id'])
                self.assertEqual(lab['objective_realizations'],[])
                self.assertEqual(result['objective_provenance_blocks'][0]['stage'],'precommit_execution')
                store.save(state);state=store.load();lab=state['planning_lab'];state['cycles']=17
                with patch.object(planning_lab,'_execute_objective_realization',side_effect=AssertionError('retry blocked precommit')):
                    step_planning_lab(state)
                self.assertEqual(lab['objective_realization_decisions'],prior)

    def test_valid_unique_phase40_behavior_remains_one_precommit_then_one_action(self):
        state=phase40_state();lab=state['planning_lab']
        with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as apply:
            precommit=step_planning_lab(state)
            self.assertEqual(apply.call_count,0)
            state['cycles']=16;realized=step_planning_lab(state)
            self.assertEqual(apply.call_count,1)
        self.assertEqual(precommit['execution_kind'],'objective_information_precommit')
        self.assertEqual(realized['execution_kind'],'objective_information_realization')
        self.assertEqual(realized['realized_information_gain'],1.0)
        self.assertNotIn('objective_provenance_blocks',realized)

    def test_receipts_bounded_and_do_not_change_completed_history_or_active_goal(self):
        state=phase40_state();lab=state['planning_lab'];lab['objective_decisions']=[]
        old_goal=deepcopy(lab['goals'][0]);lab['objective_realizations']=[dict(id='OI_OLD',objective_decision_id='OD_GONE',realized_information_gain=1.0)]
        old_receipts=deepcopy(lab['objective_realizations'])
        for cycle in range(16,160): planning_lab._select_objective_realization(lab,cycle)
        self.assertEqual(len(lab['objective_provenance_blocks']),128)
        self.assertEqual(lab['goals'][0],old_goal)
        self.assertEqual(lab['objective_realizations'],old_receipts)
        lab['active_goal_id']='PG_P40'
        count=len(lab['objective_provenance_blocks'])
        self.assertIsNone(planning_lab._select_objective_realization(lab,160))
        self.assertEqual(len(lab['objective_provenance_blocks']),count)

    def test_identity_helper_has_no_external_effect_imports(self):
        tree=ast.parse(inspect.getsource(objective_identity));imports=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.update(a.name.split('.')[0] for a in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:imports.add(node.module.split('.')[0])
        self.assertTrue(imports <= {'__future__','re','collections','typing'})


if __name__=='__main__': unittest.main()
