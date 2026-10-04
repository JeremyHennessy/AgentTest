from __future__ import annotations

import importlib.util
import json
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


class World2NativePersistenceTests(unittest.TestCase):
    def test_refutation_and_focus_survive_json_reload(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, sample(world))
        world, record = world2.transition_world2(world, "observe", cycle=2)
        consumer.consume_native_observation(state, sample(world, record))
        before = endogenous.choose_native_intention(state)
        restored = json.loads(json.dumps(state, sort_keys=True))
        after = endogenous.choose_native_intention(restored)
        self.assertEqual(after, before)
        self.assertEqual(after["dominant_drive"], "prediction_error")
        self.assertTrue(after["evidence_refs"])

    def test_pending_local_prediction_remains_pending_across_reload_and_remote_sample(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world, record = world2.transition_world2(world, "north", cycle=1)
        consumer.consume_native_observation(state, sample(world, record))
        restored = json.loads(json.dumps(state))
        native_state = restored[consumer.NATIVE_STATE_KEY]
        target = next(
            item for item in native_state["predictions"]
            if item["prediction"]["kind"] == "object_visible_at_position"
        )
        world, record = world2.transition_world2(world, "south", cycle=2)
        consumer.consume_native_observation(restored, sample(world, record))
        self.assertEqual(target["status"], "pending")


if __name__ == "__main__":
    unittest.main()
