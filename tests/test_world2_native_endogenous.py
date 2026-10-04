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
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]
consumer = sys.modules["world2_native_consumer"]
endogenous = sys.modules["world2_native_endogenous"]


def sample(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativeEndogenousTests(unittest.TestCase):
    def test_pending_evidence_creates_evidence_hunger(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        consumer.consume_native_observation(state, sample(world))
        intention = endogenous.choose_native_intention(state)
        self.assertEqual(intention["dominant_drive"], "evidence_hunger")
        self.assertEqual(intention["kind"], "resolve_native_prediction")
        self.assertIsNotNone(intention["target"])

    def test_refutation_changes_dominant_drive_and_focus(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, sample(world))
        before = endogenous.choose_native_intention(state)
        world, record = world2.transition_world2(world, "observe", cycle=2)
        consumer.consume_native_observation(state, sample(world, record))
        after = endogenous.choose_native_intention(state)
        self.assertEqual(after["dominant_drive"], "prediction_error")
        self.assertEqual(after["kind"], "explain_native_change")
        self.assertNotEqual(before, after)
        self.assertTrue(after["evidence_refs"])

    def test_endogenous_layer_has_no_world_or_action_authority(self):
        source = (EXPERIMENTS / "world2_native_endogenous.py").read_text(encoding="utf-8")
        for forbidden in (
            "transition_world2",
            "AgentCore",
            "action_lab",
            "planning_lab",
            "latent_mode",
            "pending_slow_effects",
            "subprocess",
            "requests",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
