"""Developer controls for v2; these are not the independent review controls."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from agenttest import planning_lab
from tests.test_objective_identity import phase40_state


class ObjectiveExecutionGuardTests(unittest.TestCase):
    def test_invalid_chains_preserve_records_and_fallback_once(self):
        for failure in ('duplicate_or', 'duplicate_or_reversed', 'missing_goal', 'duplicate_goal', 'different_od'):
            with self.subTest(failure=failure):
                state = phase40_state()
                lab = state['planning_lab']
                planning_lab.step_planning_lab(state)
                if failure.startswith('duplicate_or'):
                    other = deepcopy(lab['objective_realization_decisions'][0])
                    other['action'] = 'south'
                    other['predicted_after'] = [-1, 0]
                    lab['objective_realization_decisions'].append(other)
                    if failure.endswith('reversed'):
                        lab['objective_realization_decisions'].reverse()
                elif failure == 'missing_goal':
                    lab['goals'] = []
                elif failure == 'duplicate_goal':
                    lab['goals'].append(deepcopy(lab['goals'][0]))
                else:
                    lab['objective_decisions'].append(dict(id='OD_OTHER', changed_choice=True))
                    lab['goals'][0]['selection']['objective_decision_id'] = 'OD_OTHER'
                records = deepcopy(lab['objective_realization_decisions'])
                state['cycles'] = 16
                with patch.object(planning_lab, 'apply_bounded_action', wraps=planning_lab.apply_bounded_action) as action:
                    result = planning_lab.step_planning_lab(state)
                self.assertEqual(action.call_count, 1)
                self.assertIn('objective_provenance_blocks', result)
                self.assertEqual(len(result['objective_provenance_blocks']), 1)
                self.assertEqual(lab['objective_realization_decisions'], records)
                self.assertEqual(lab['objective_realizations'], [])
                self.assertIsNone(lab['active_objective_realization_id'])


if __name__ == '__main__': unittest.main()
