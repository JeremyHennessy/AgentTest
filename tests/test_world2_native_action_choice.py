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
    "world2_native_action_choice",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]
consumer = sys.modules["world2_native_consumer"]
choice = sys.modules["world2_native_action_choice"]


def sample(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativeActionChoiceTests(unittest.TestCase):
    def test_broadcast_inquiry_proposes_observe(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        consumer.consume_native_observation(state, sample(world))
        proposal = choice.propose_action_for_inquiry(state, [0, 0])
        self.assertEqual(proposal["status"], "proposed")
        self.assertIn(proposal["action"], {"observe", "north", "east", "south", "west"})

    def test_local_challenge_can_propose_return_toward_target(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, sample(world))
        world, record = world2.transition_world2(world, "observe", cycle=2)
        consumer.consume_native_observation(state, sample(world, record))
        proposal = choice.propose_action_for_inquiry(state, [0, 0])
        if proposal["inquiry"]["target_position"] == [-1, 0]:
            self.assertEqual(proposal["action"], "south")

    def test_action_choice_cannot_execute_or_access_world_truth(self):
        source = (EXPERIMENTS / "world2_native_action_choice.py").read_text(encoding="utf-8")
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
