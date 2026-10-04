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
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]
consumer = sys.modules["world2_native_consumer"]
opportunity = sys.modules["world2_native_opportunity"]


def sample(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativeOpportunityTests(unittest.TestCase):
    def test_selection_prefers_challenged_local_hypothesis(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, sample(world))
        world, record = world2.transition_world2(world, "observe", cycle=2)
        consumer.consume_native_observation(state, sample(world, record))
        selected = opportunity.select_native_inquiry(state)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["target_position"], [-1, 0])
        self.assertIn(
            selected["kind"],
            {"retest_challenged_hypothesis", "test_pending_prediction"},
        )
        self.assertEqual(
            selected["selection_basis"],
            "persisted_native_uncertainty_and_evidence",
        )

    def test_selection_does_not_contain_action_or_hidden_world_truth(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=4)
        consumer.consume_native_observation(state, sample(world))
        selected = opportunity.select_native_inquiry(state)
        rendered = repr(selected)
        for forbidden in (
            "latent_mode",
            "resource_phase",
            "pending_slow_effects",
            "matures_cycle",
            "'action'",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_selection_changes_after_direct_refutation(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world, record = world2.transition_world2(world, "north", cycle=1)
        consumer.consume_native_observation(state, sample(world, record))
        before = opportunity.select_native_inquiry(state)
        self.assertIsNotNone(before)
        world, record = world2.transition_world2(world, "interact", cycle=2)
        consumer.consume_native_observation(state, sample(world, record))
        after = opportunity.select_native_inquiry(state)
        self.assertIsNotNone(after)
        self.assertNotEqual(before, after)
        self.assertTrue(after["evidence_refs"])

    def test_bridge_has_no_world_transition_or_agentcore_authority(self):
        source = (EXPERIMENTS / "world2_native_opportunity.py").read_text(encoding="utf-8")
        for forbidden in (
            "AgentCore",
            "transition_world2",
            "action_lab",
            "planning_lab",
            "subprocess",
            "requests",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
