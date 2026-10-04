from __future__ import annotations

import copy
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
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]
consumer = sys.modules["world2_native_consumer"]


def observe(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativeConsumerTests(unittest.TestCase):
    def test_consumer_does_not_mutate_production_collections(self):
        state = initial_state()
        before = copy.deepcopy(state)
        world = world2.initial_world2_state(seed=1)
        consumer.consume_native_observation(state, observe(world))
        for key in before:
            self.assertEqual(state[key], before[key])
        self.assertIn(consumer.NATIVE_STATE_KEY, state)

    def test_visible_object_prediction_survives_absence_elsewhere_and_refutes_on_return(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world, record = world2.transition_world2(world, "north", cycle=1)
        consumer.consume_native_observation(state, observe(world, record))
        native_state = state[consumer.NATIVE_STATE_KEY]
        object_prediction = next(
            item for item in native_state["predictions"]
            if item["prediction"]["kind"] == "object_visible_at_position"
        )

        world, record = world2.transition_world2(world, "south", cycle=2)
        consumer.consume_native_observation(state, observe(world, record))
        self.assertEqual(object_prediction["status"], "pending")

        world, record = world2.transition_world2(world, "north", cycle=3)
        world, record = world2.transition_world2(world, "interact", cycle=4)
        consumer.consume_native_observation(state, observe(world, record))
        self.assertEqual(object_prediction["status"], "refuted")
        self.assertTrue(object_prediction["result"]["direct_evidence"])

    def test_resource_hypothesis_revises_from_observed_change(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, observe(world))
        native_state = state[consumer.NATIVE_STATE_KEY]
        resource_prediction = next(
            item for item in native_state["predictions"]
            if item["prediction"]["kind"] == "resource_value_at_position"
        )
        world, record = world2.transition_world2(world, "observe", cycle=2)
        result = consumer.consume_native_observation(state, observe(world, record))
        self.assertIn(resource_prediction["evidence_id"], result["resolved_evidence_ids"])
        self.assertEqual(resource_prediction["status"], "refuted")
        key = consumer._prediction_key(resource_prediction["prediction"])
        self.assertEqual(native_state["hypotheses"][key]["stance"], "challenged")

    def test_slow_signal_persistence_prediction_is_revised_by_delayed_effect(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world, _ = world2.transition_world2(world, "north", cycle=1)
        world, record = world2.transition_world2(world, "interact", cycle=2)
        consumer.consume_native_observation(state, observe(world, record))
        native_state = state[consumer.NATIVE_STATE_KEY]
        initial_slow = next(
            item for item in native_state["predictions"]
            if item["prediction"]["kind"] == "slow_signal_value"
        )
        for cycle in (3, 4, 5):
            world, record = world2.transition_world2(world, "observe", cycle=cycle)
            consumer.consume_native_observation(state, observe(world, record))
        self.assertEqual(initial_slow["status"], "confirmed")

        pending_zero = next(
            item for item in native_state["predictions"]
            if item["status"] == "pending"
            and item["prediction"]["kind"] == "slow_signal_value"
            and item["prediction"]["expected"] == 0
        )
        world, record = world2.transition_world2(world, "observe", cycle=6)
        consumer.consume_native_observation(state, observe(world, record))
        self.assertEqual(pending_zero["status"], "refuted")

    def test_unavailable_resource_does_not_create_or_resolve_resource_evidence(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, observe(world))
        native_state = state[consumer.NATIVE_STATE_KEY]
        pred = next(
            item for item in native_state["predictions"]
            if item["prediction"]["kind"] == "resource_value_at_position"
        )
        unavailable = native.native_world2_observation(
            world2.observe_world2(world), resource_available=False
        )
        result = consumer.consume_native_observation(state, unavailable)
        self.assertEqual(pred["status"], "pending")
        self.assertEqual(result["resolved_evidence_ids"], [])
        self.assertFalse(
            any(
                item["prediction"]["kind"] == "resource_value_at_position"
                and item["prediction"]["created_observation_id"] == unavailable["observation_id"]
                for item in native_state["predictions"]
            )
        )

    def test_consumer_has_no_action_or_agentcore_authority(self):
        source = (EXPERIMENTS / "world2_native_consumer.py").read_text(encoding="utf-8")
        self.assertNotIn("AgentCore", source)
        self.assertNotIn("action_lab", source)
        self.assertNotIn("planning_lab", source)
        self.assertNotIn("transition_world2", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("requests", source)


if __name__ == "__main__":
    unittest.main()
