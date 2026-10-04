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
endogenous = sys.modules["world2_native_endogenous"]
choice = sys.modules["world2_native_action_choice"]


def sample(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativeMultiConfigTests(unittest.TestCase):
    def test_resource_phase_change_produces_direct_evidence_in_each_configuration(self):
        for seed in range(1, 6):
            with self.subTest(seed=seed):
                state = initial_state()
                world = world2.initial_world2_state(seed=seed)
                world["position"] = [-1, 0]
                consumer.consume_native_observation(state, sample(world))
                initial = world["resources"]["-1,0"]
                changed = False
                for cycle in range(1, 7):
                    world, record = world2.transition_world2(world, "observe", cycle=cycle)
                    consumer.consume_native_observation(state, sample(world, record))
                    if world["resources"]["-1,0"] != initial:
                        changed = True
                        break
                self.assertTrue(changed)
                native_state = state[consumer.NATIVE_STATE_KEY]
                predictions_by_id = {
                    item["prediction"]["prediction_id"]: item["prediction"]
                    for item in native_state["predictions"]
                }
                self.assertTrue(
                    any(
                        item["status"] == "refuted"
                        and predictions_by_id[item["prediction_id"]]["kind"]
                        == "resource_value_at_position"
                        for item in native_state["evidence"]
                    )
                )
                intention = endogenous.choose_native_intention(state)
                self.assertGreater(intention["drives"]["prediction_error"], 0.0)
                proposal = choice.propose_action_for_inquiry(state, world["position"])
                self.assertIn(
                    proposal["action"],
                    {"observe", "north", "east", "south", "west"},
                )

    def test_no_seed_or_phase_enters_native_memory(self):
        for seed in range(1, 6):
            state = initial_state()
            world = world2.initial_world2_state(seed=seed)
            consumer.consume_native_observation(state, sample(world))
            rendered = repr(state[consumer.NATIVE_STATE_KEY])
            self.assertNotIn("'seed'", rendered)
            self.assertNotIn("resource_phase", rendered)
            self.assertNotIn("latent_mode", rendered)


if __name__ == "__main__":
    unittest.main()
