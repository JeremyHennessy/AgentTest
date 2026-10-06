"""Developer v3 controls; independent reviewer controls remain separate."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from agenttest import planning_lab
from tests.test_objective_identity import phase40_state


class ObjectiveDirectDuplicateTests(unittest.TestCase):
    def test_duplicates_block_regardless_of_cursor_order_or_record(self):
        for cursor in (None, 'OR_UNRELATED', 'OR000001'):
            for reverse in (False, True):
                for index in (0, 1):
                    with self.subTest(cursor=cursor, reverse=reverse, index=index):
                        state = phase40_state(); lab = state['planning_lab']
                        planning_lab.step_planning_lab(state)
                        other = deepcopy(lab['objective_realization_decisions'][0])
                        other.update(action='south', predicted_after=[-1, 0])
                        lab['objective_realization_decisions'].append(other)
                        if reverse: lab['objective_realization_decisions'].reverse()
                        lab['active_objective_realization_id'] = cursor
                        rows = deepcopy(lab['objective_realization_decisions'])
                        transitions = deepcopy(lab['transition_observations'])
                        position = deepcopy(lab['position'])
                        decision = lab['objective_realization_decisions'][index]
                        with patch.object(planning_lab, 'apply_bounded_action', wraps=planning_lab.apply_bounded_action) as action:
                            result = planning_lab._execute_objective_realization(lab, decision, 16)
                        self.assertEqual(action.call_count, 0)
                        self.assertIsNone(result['action'])
                        self.assertEqual(result['objective_provenance_block']['provenance_status'], 'ambiguous')
                        self.assertEqual(result['objective_provenance_block']['provenance_scope'], 'active_precommit')
                        self.assertEqual(lab['active_objective_realization_id'], None if cursor==decision['id'] else cursor)
                        self.assertEqual(lab['objective_realization_decisions'], rows)
                        self.assertEqual(lab['objective_realizations'], [])
                        self.assertEqual(lab['transition_observations'], transitions)
                        self.assertEqual(lab['position'], position)
                        self.assertEqual(lab['objective_decision_ambiguous_ids'], [])

    def test_unique_direct_handoffs_with_null_or_unrelated_cursor_remain_valid(self):
        for cursor in (None, 'OR_UNRELATED'):
            with self.subTest(cursor=cursor):
                state=phase40_state(); lab=state['planning_lab']
                planning_lab.step_planning_lab(state)
                decision=lab['objective_realization_decisions'][0]
                lab['active_objective_realization_id']=cursor
                with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as action:
                    result=planning_lab._execute_objective_realization(lab,decision,16)
                self.assertEqual(action.call_count,1)
                self.assertEqual(result['execution_kind'],'objective_information_realization')
                self.assertEqual(len(lab['objective_realizations']),1)


if __name__=='__main__': unittest.main()
