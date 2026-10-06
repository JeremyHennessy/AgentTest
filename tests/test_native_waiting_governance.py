"""Developer regression controls for native waiting versus closure defects."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from agenttest.core import AgentCore
from agenttest.state import StateStore
from agenttest.self_proposal import select_change_target, _learning_evidence_debt
from agenttest.proposal_review import _learning_loop_gap, review_change_proposal
from agenttest.change_control import make_change_manifest
from tests.test_native_inquiry_interface import seeded_state, temporal_candidate


class NativeWaitingGovernanceTests(unittest.TestCase):
    def pending_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp)/'state.json')
            store.save(seeded_state())
            core = AgentCore(store)
            native = core.propose_native_inquiry(temporal_candidate(), enabled=True, persist=True)
            observation = dict(branch='autonomous/growth', baseline_fingerprint='native-waiting-control',
                               tracked_files=100, python_files=20, python_source_lines=5000,
                               test_files=12, working_tree_clean=True)
            for i in range(5):
                core.cycle(observation=observation, strict_experiment_admission=True,
                           planning_lab=True, _now_override=f'2026-10-05T02:0{i}:00+00:00')
            state = store.load()
            experiment = next(x for x in state['experiments'] if x['id']==native['experiment']['id'])
            return state, experiment

    def test_unrelated_predictions_do_not_authorize_native_closure_patch(self):
        state, experiment = self.pending_state()
        self.assertEqual(experiment['readiness'], 'awaiting_native_evidence')
        self.assertEqual(experiment['status'], 'proposed')
        target = select_change_target(state)
        with self.subTest(stage='generation'):
            self.assertIsNone(_learning_evidence_debt(state))
            self.assertTrue(target is None or target.get('experiment_id') != experiment['id'])
        with self.subTest(stage='review_gap'):
            self.assertFalse(_learning_loop_gap(state)[0])
        proposal = make_change_manifest(state, title='Check pending native closure',
            target_dimension='learning', files=['src/agenttest/core.py'],
            hypothesis='Unrelated repository predictions demonstrate a closure defect.',
            expected_effect='Close pending work.', test_plan='Run evidence checks.',
            falsification='No directly evaluable native outcome.', rollback='Revert.',
            evidence_refs=[experiment['id']])
        proposal['id']='M_NATIVE'; state['change_proposals'].append(proposal)
        before = deepcopy(experiment)
        review, _ = review_change_proposal(state, proposal)
        self.assertEqual(review['verdict'], 'no_problem_observed')
        self.assertEqual(review['patch_authority'], 'none')
        self.assertIn('native', review['reason'])
        self.assertEqual(experiment, before)
        self.assertNotIn('native_resolution', experiment)
        self.assertFalse(any(x.get('source')=='native_inquiry' for x in state['reflections']))

    def test_evidence_ready_unresolved_work_remains_a_closure_gap(self):
        state, experiment = self.pending_state()
        experiment['readiness']='evidence_ready'
        self.assertEqual(_learning_evidence_debt(state)['experiment_id'], experiment['id'])
        self.assertTrue(_learning_loop_gap(state)[0])

    def test_waiting_native_does_not_hide_other_ready_closure_gap(self):
        state, experiment = self.pending_state()
        ready = dict(experiment, id='X_READY', readiness='evidence_ready')
        state['experiments'].append(ready)
        self.assertEqual(_learning_evidence_debt(state)['experiment_id'], 'X_READY')
        gap, refs = _learning_loop_gap(state)
        self.assertTrue(gap)
        self.assertIn('X_READY', refs)


if __name__=='__main__': unittest.main()
