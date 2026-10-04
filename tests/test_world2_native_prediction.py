from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in ("world2_ecology", "world2_native_observation", "world2_native_prediction"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]
prediction = sys.modules["world2_native_prediction"]


def envelope(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativePredictionTests(unittest.TestCase):
    def test_object_prediction_waits_for_same_position_then_confirms(self):
        world = world2.initial_world2_state(seed=1)
        world, record = world2.transition_world2(world, "north", cycle=1)
        seen = envelope(world, record)
        pred = prediction.make_prediction(
            prediction_id="NP1",
            kind="object_visible_at_position",
            created_observation=seen,
            target_position=[1, 0],
            object_id="O1",
            expected=True,
        )
        world, record = world2.transition_world2(world, "south", cycle=2)
        away = envelope(world, record)
        result = prediction.evaluate_prediction(pred, away)
        self.assertEqual(result["status"], "unevaluable")
        self.assertFalse(result["direct_evidence"])
        world, record = world2.transition_world2(world, "north", cycle=3)
        returned = envelope(world, record)
        result = prediction.evaluate_prediction(pred, returned)
        self.assertEqual(result["status"], "confirmed")
        self.assertTrue(result["direct_evidence"])

    def test_object_displacement_refutes_prior_visibility_prediction(self):
        world = world2.initial_world2_state(seed=1)
        world, record = world2.transition_world2(world, "north", cycle=1)
        seen = envelope(world, record)
        pred = prediction.make_prediction(
            prediction_id="NP2",
            kind="object_visible_at_position",
            created_observation=seen,
            target_position=[1, 0],
            object_id="O1",
            expected=True,
        )
        world, record = world2.transition_world2(world, "interact", cycle=2)
        after = envelope(world, record)
        result = prediction.evaluate_prediction(pred, after)
        self.assertEqual(result["status"], "refuted")
        self.assertEqual(result["actual"], False)

    def test_resource_prediction_requires_same_position_and_measured_channel(self):
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        seen = envelope(world)
        pred = prediction.make_prediction(
            prediction_id="NP3",
            kind="resource_value_at_position",
            created_observation=seen,
            target_position=[-1, 0],
            expected=2,
        )
        world, record = world2.transition_world2(world, "south", cycle=1)
        away = envelope(world, record)
        self.assertEqual(prediction.evaluate_prediction(pred, away)["status"], "unevaluable")

        unavailable = native.native_world2_observation(
            {**world2.observe_world2(world), "position": [-1, 0], "local_resource": 2},
            resource_available=False,
        )
        result = prediction.evaluate_prediction(pred, unavailable)
        self.assertEqual(result["status"], "unevaluable")
        self.assertEqual(result["reason"], "resource_unavailable")

    def test_resource_change_can_refute_without_contract_intervention(self):
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        first = envelope(world)
        pred = prediction.make_prediction(
            prediction_id="NP4",
            kind="resource_value_at_position",
            created_observation=first,
            target_position=[-1, 0],
            expected=2,
        )
        world, record = world2.transition_world2(world, "observe", cycle=2)
        second = envelope(world, record)
        result = prediction.evaluate_prediction(pred, second)
        self.assertEqual(result["status"], "refuted")
        self.assertEqual(result["actual"], 3)
        self.assertTrue(result["direct_evidence"])

    def test_delayed_signal_prediction_is_refuted_until_effect_matures(self):
        world = world2.initial_world2_state(seed=1)
        world, _ = world2.transition_world2(world, "north", cycle=1)
        world, record = world2.transition_world2(world, "interact", cycle=2)
        after_interaction = envelope(world, record)
        pred = prediction.make_prediction(
            prediction_id="NP5",
            kind="slow_signal_value",
            created_observation=after_interaction,
            expected=2,
        )
        world, record = world2.transition_world2(world, "observe", cycle=3)
        early = prediction.evaluate_prediction(pred, envelope(world, record))
        self.assertEqual(early["status"], "refuted")
        world, record = world2.transition_world2(world, "observe", cycle=6)
        mature = prediction.evaluate_prediction(pred, envelope(world, record))
        self.assertEqual(mature["status"], "confirmed")

    def test_prediction_carries_no_hidden_truth_or_action_selection(self):
        world = world2.initial_world2_state(seed=4)
        observed = envelope(world)
        pred = prediction.make_prediction(
            prediction_id="NP6",
            kind="slow_signal_value",
            created_observation=observed,
            expected=0,
        )
        rendered = repr(pred)
        for forbidden in ("seed", "latent_mode", "resource_phase", "matures_cycle", "action"):
            self.assertNotIn(forbidden, rendered)

    def test_prediction_validation_fails_closed(self):
        world = world2.initial_world2_state(seed=1)
        observed = envelope(world)
        pred = prediction.make_prediction(
            prediction_id="NP7",
            kind="slow_signal_value",
            created_observation=observed,
            expected=0,
        )
        pred["hidden_truth"] = True
        with self.assertRaises(ValueError):
            prediction.validate_prediction(pred)


if __name__ == "__main__":
    unittest.main()
