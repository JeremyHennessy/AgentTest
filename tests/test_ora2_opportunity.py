"""Pure tests for the new Ora 2 exact-action opportunity screen."""
import copy
import unittest

from ora2.baseline import ACTIONS, WORLD
from ora2.learner import Agent, Config, ProtocolError
from ora2.opportunity import propose


def state(position=(0, 0)):
    return {'planning_lab': {'world_version': WORLD, 'position': list(position),
            'plans': [], 'goals': [], 'objective_realization_decisions': [],
            'active_plan_id': None, 'active_goal_id': None,
            'active_objective_realization_id': None,
            'transition_observations': []}}


class JointOpportunityTests(unittest.TestCase):
    def setUp(self):
        self.agent = Agent({'position': [0, 0]}, seed=5, config=Config(max_steps=64))

    def test_preview_stability_and_exact_selected_action(self):
        old = copy.deepcopy(self.agent)
        first = propose(self.agent, state(), previous_owner=None)
        second = propose(self.agent, state(), previous_owner=None)
        self.assertEqual(first, second)
        self.assertEqual(first['action'], old.choose(ACTIONS).action)
        self.assertIsNone(self.agent.summary()['pending'])
        self.assertEqual(first['owner'], 'ora2')
        self.assertEqual(len(first['proposal_sha256']), 64)

    def test_each_inherited_commitment_protected(self):
        for key, collection in [
            ('active_goal_id','goals'), ('active_plan_id','plans'),
            ('active_objective_realization_id','objective_realization_decisions')
        ]:
            with self.subTest(key=key):
                snapshot = state()
                snapshot['planning_lab'][key] = 'KEEP'
                snapshot['planning_lab'][collection] = [{'id':'KEEP'}]
                self.assertEqual(propose(self.agent, snapshot, previous_owner=None)['owner'], 'phase41')

    def test_context_specific_evidence_not_other_actions(self):
        snapshot = state()
        action = propose(self.agent, snapshot, previous_owner=None)['action']
        snapshot['planning_lab']['transition_observations'] = [
            {'world_version': WORLD, 'before':[0,0], 'action':action, 'blocked':True}
            for _ in range(2)
        ]
        blocked = propose(self.agent, snapshot, previous_owner=None)
        self.assertEqual(blocked['reason'], 'observed_repeated_block_for_exact_action')
        self.assertEqual(blocked['owner'], 'phase41')
        snapshot['planning_lab']['transition_observations'][0]['action'] = next(x for x in ACTIONS if x!=action)
        self.assertEqual(propose(self.agent,snapshot,previous_owner=None)['owner'], 'ora2')

    def test_yield_to_original_planner_after_own_action(self):
        self.assertEqual(propose(self.agent,state(),previous_owner='ora2')['owner'],'phase41')

    def test_mismatched_public_state_and_missing_goal_fail_closed(self):
        with self.assertRaises(ProtocolError):
            propose(self.agent,state((1,1)),previous_owner=None)
        snapshot=state()
        snapshot['planning_lab']['active_goal_id']='missing'
        with self.assertRaises(ProtocolError):
            propose(self.agent,snapshot,previous_owner=None)


if __name__ == '__main__':
    unittest.main()
