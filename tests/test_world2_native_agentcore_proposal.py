from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology",
    "world2_native_observation",
    "world2_native_prediction",
    "world2_native_consumer",
    "world2_native_opportunity",
    "world2_native_endogenous",
    "world2_native_agentcore_proposal",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]
consumer = sys.modules["world2_native_consumer"]
proposal = sys.modules["world2_native_agentcore_proposal"]


def sample(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativeAgentCoreProposalTests(unittest.TestCase):
    def test_candidate_uses_core_grounded_shape(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        consumer.consume_native_observation(state, sample(world))
        candidate = proposal.propose_native_question_candidate(state)
        self.assertIsNotNone(candidate)
        for field in ("question", "hypothesis", "experiment", "falsification", "predicted_observation"):
            self.assertIn(field, candidate)
        self.assertTrue(candidate["grounded"])

    def test_refutation_changes_candidate_through_endogenous_focus(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, sample(world))
        before = proposal.propose_native_question_candidate(state)
        world, record = world2.transition_world2(world, "observe", cycle=2)
        consumer.consume_native_observation(state, sample(world, record))
        after = proposal.propose_native_question_candidate(state)
        self.assertIsNotNone(after)
        self.assertNotEqual(before["native_intention"], after["native_intention"])
        self.assertEqual(after["native_intention"]["dominant_drive"], "prediction_error")
        self.assertTrue(after["evidence_refs"])

    def test_candidate_contains_no_hidden_truth_or_execution(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=4)
        consumer.consume_native_observation(state, sample(world))
        candidate = proposal.propose_native_question_candidate(state)
        rendered = repr(candidate)
        for forbidden in ("seed", "resource_phase", "latent_mode", "matures_cycle", "pending_slow_effects"):
            self.assertNotIn(forbidden, rendered)
        source = (EXPERIMENTS / "world2_native_agentcore_proposal.py").read_text(encoding="utf-8")
        for forbidden in ("AgentCore(", "transition_world2", "subprocess", "requests"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
