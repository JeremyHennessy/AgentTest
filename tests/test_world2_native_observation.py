from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in ("world2_ecology", "world2_native_observation"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]


class World2NativeObservationTests(unittest.TestCase):
    def _envelope(self, *, seed: int = 1):
        world = world2.initial_world2_state(seed=seed)
        return native.native_world2_observation(world2.observe_world2(world))

    def test_preserves_native_position_and_visible_object_identity(self):
        world = world2.initial_world2_state(seed=1)
        world, record = world2.transition_world2(world, "north", cycle=1)
        envelope = native.native_world2_observation(
            world2.observe_world2(world), action_receipt=record
        )
        self.assertEqual(envelope["position"], [1, 0])
        self.assertEqual(envelope["visible_object_ids"], ["O1"])
        self.assertEqual(envelope["action_receipt"]["after"], [1, 0])

    def test_measured_zero_is_not_no_channel_or_unavailable(self):
        observation = world2.observe_world2(world2.initial_world2_state(seed=1))
        observation["local_resource"] = 0
        measured = native.native_world2_observation(observation)
        no_channel_observation = copy.deepcopy(observation)
        no_channel_observation["local_resource"] = None
        no_channel = native.native_world2_observation(no_channel_observation)
        unavailable = native.native_world2_observation(
            observation, resource_available=False
        )
        self.assertEqual(
            measured["local_resource"],
            {"status": "measured", "scope": "local", "value": 0},
        )
        self.assertEqual(
            no_channel["local_resource"],
            {"status": "not_present_here", "scope": "local"},
        )
        self.assertEqual(
            unavailable["local_resource"],
            {"status": "unavailable", "scope": "local"},
        )

    def test_slow_signal_scope_is_explicitly_broadcast(self):
        self.assertEqual(
            self._envelope()["slow_signal"],
            {"status": "measured", "scope": "broadcast", "value": 0},
        )

    def test_object_displacement_receipt_does_not_expose_destination(self):
        world = world2.initial_world2_state(seed=1)
        world, _ = world2.transition_world2(world, "north", cycle=1)
        world, record = world2.transition_world2(world, "interact", cycle=2)
        envelope = native.native_world2_observation(
            world2.observe_world2(world), action_receipt=record
        )
        self.assertEqual(envelope["visible_object_ids"], [])
        self.assertEqual(
            envelope["action_receipt"]["observed_effect"], "object_displaced"
        )
        self.assertNotIn("object_position", envelope["action_receipt"])
        self.assertNotIn("matures_cycle", repr(envelope))

    def test_hidden_world_configuration_never_appears(self):
        world = world2.initial_world2_state(seed=4)
        world["latent_mode"] = 1
        world["pending_slow_effects"] = [{"matures_cycle": 9, "delta": 2}]
        envelope = native.native_world2_observation(world2.observe_world2(world))
        rendered = repr(envelope)
        for forbidden in (
            "seed",
            "resource_phase",
            "latent_mode",
            "pending_slow_effects",
            "matures_cycle",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_translation_is_deterministic_and_does_not_mutate_input(self):
        observation = world2.observe_world2(world2.initial_world2_state(seed=3))
        before = copy.deepcopy(observation)
        first = native.native_world2_observation(observation)
        second = native.native_world2_observation(observation)
        self.assertEqual(first, second)
        self.assertEqual(observation, before)

    def test_world_step_changes_sample_identity_not_contract_identity(self):
        first = world2.observe_world2(world2.initial_world2_state(seed=1))
        second = copy.deepcopy(first)
        second["cycle"] = 1
        before = native.native_world2_observation(first)
        after = native.native_world2_observation(second)
        self.assertEqual(before["contract_id"], after["contract_id"])
        self.assertNotEqual(before["observation_id"], after["observation_id"])

    def test_validator_rejects_unknown_fields(self):
        envelope = self._envelope()
        envelope["latent_mode"] = 1
        with self.assertRaises(ValueError):
            native.validate_native_world2_observation(envelope)

    def test_validator_rejects_value_on_non_measured_resource(self):
        envelope = self._envelope()
        envelope["local_resource"] = {
            "status": "not_present_here",
            "scope": "local",
            "value": 0,
        }
        with self.assertRaises(ValueError):
            native.validate_native_world2_observation(envelope)

    def test_validator_rejects_out_of_range_and_boolean_measurements(self):
        for value in (-1, 5, True):
            envelope = self._envelope()
            envelope["local_resource"] = {
                "status": "measured",
                "scope": "local",
                "value": value,
            }
            with self.assertRaises(ValueError):
                native.validate_native_world2_observation(envelope)

    def test_validator_rejects_wrong_broadcast_scope(self):
        envelope = self._envelope()
        envelope["slow_signal"]["scope"] = "local"
        with self.assertRaises(ValueError):
            native.validate_native_world2_observation(envelope)

    def test_real_sequence_preserves_object_reappearance_without_remote_leak(self):
        world = world2.initial_world2_state(seed=1)
        records = []
        for cycle, action in enumerate(
            ("north", "interact", "west", "east", "south", "north", "west"), start=1
        ):
            world, record = world2.transition_world2(world, action, cycle=cycle)
            records.append(
                native.native_world2_observation(
                    world2.observe_world2(world), action_receipt=record
                )
            )
        self.assertEqual(records[0]["visible_object_ids"], ["O1"])
        self.assertEqual(records[1]["visible_object_ids"], [])
        self.assertEqual(records[-1]["visible_object_ids"], ["O1"])
        for envelope in records:
            self.assertNotIn("object_position", repr(envelope))
            self.assertNotIn("pending_slow_effects", repr(envelope))

    def test_delayed_signal_is_observed_only_when_it_matures(self):
        world = world2.initial_world2_state(seed=1)
        envelopes = []
        for cycle, action in enumerate(
            ("north", "interact", "observe", "observe", "observe", "observe"), start=1
        ):
            world, record = world2.transition_world2(world, action, cycle=cycle)
            envelopes.append(
                native.native_world2_observation(
                    world2.observe_world2(world), action_receipt=record
                )
            )
        self.assertEqual([item["slow_signal"]["value"] for item in envelopes], [0, 0, 0, 0, 0, 2])
        self.assertNotIn("matures_cycle", repr(envelopes))

    def test_resource_changes_are_measurements_not_contract_changes(self):
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        first = native.native_world2_observation(world2.observe_world2(world))
        world, record = world2.transition_world2(world, "observe", cycle=1)
        second = native.native_world2_observation(
            world2.observe_world2(world), action_receipt=record
        )
        self.assertEqual(first["contract_id"], second["contract_id"])
        self.assertNotEqual(first["local_resource"], second["local_resource"])

    def test_malformed_receipts_fail_closed_instead_of_coercing(self):
        world = world2.initial_world2_state(seed=1)
        observation = world2.observe_world2(world)
        bad = {
            "action": "observe",
            "before": [0, 0],
            "after": [0, 0],
            "blocked": "false",
            "interaction_effect": "observation_only",
        }
        with self.assertRaises(ValueError):
            native.native_world2_observation(observation, action_receipt=bad)

    def test_receipt_cannot_smuggle_arbitrary_effect_or_remote_position(self):
        world = world2.initial_world2_state(seed=1)
        observation = world2.observe_world2(world)
        bad_effect = {
            "action": "observe",
            "before": [0, 0],
            "after": [0, 0],
            "blocked": False,
            "interaction_effect": "latent_mode=1",
        }
        with self.assertRaises(ValueError):
            native.native_world2_observation(observation, action_receipt=bad_effect)
        bad_position = {
            "action": "interact",
            "before": [0, 0],
            "after": [0, 1],
            "blocked": False,
            "interaction_effect": "no_visible_target",
        }
        with self.assertRaises(ValueError):
            native.native_world2_observation(observation, action_receipt=bad_position)

    def test_receipt_must_end_at_observed_actor_position(self):
        envelope = self._envelope()
        envelope["action_receipt"] = {
            "action": "north",
            "before": [0, 0],
            "after": [1, 0],
            "blocked": False,
            "observed_effect": None,
        }
        with self.assertRaises(ValueError):
            native.validate_native_world2_observation(envelope)

    def test_validator_rejects_contract_or_world_drift(self):
        for key, value in (
            ("contract_id", "other-contract"),
            ("world_version", "other-world"),
            ("schema_version", "other-schema"),
        ):
            envelope = self._envelope()
            envelope[key] = value
            with self.assertRaises(ValueError):
                native.validate_native_world2_observation(envelope)


if __name__ == "__main__":
    unittest.main()
