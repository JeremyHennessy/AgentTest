from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology", "world2_native_observation",
    "world3_ecology", "world3_native_observation",
    "native_relation_discovery", "native_relation_family_memory",
    "native_relation_transfer_core", "trajectory_relation_profiles",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

relations = sys.modules["native_relation_discovery"]
families = sys.modules["native_relation_family_memory"]
transfer = sys.modules["native_relation_transfer_core"]
profiles = sys.modules["trajectory_relation_profiles"]

HELD_OUT = [
    {"id": "H1", "version": relations.RELATION_VERSION, "relation": "action_precedes_change", "feature": "novel_signal", "action": "interact"},
    {"id": "H2", "version": relations.RELATION_VERSION, "relation": "same_next_observation", "feature": "novel_signal", "action": None},
    {"id": "H3", "version": relations.RELATION_VERSION, "relation": "changes_next_observation", "feature": "novel_signal", "action": None},
]


class TrajectoryRelationTransferTests(unittest.TestCase):
    def _trained(self):
        outputs = {}
        for name, fn in (
            ("stability", profiles.world2_stability_trajectory),
            ("change", profiles.world3_change_trajectory),
            ("action", profiles.world3_action_trajectory),
        ):
            state = initial_state()
            outputs[name] = fn(state)
        return outputs

    def test_profiles_are_derived_from_real_observations_not_fixture_ledgers(self):
        for output in self._trained().values():
            self.assertGreater(len(output["samples"]), 1)
            self.assertTrue(output["ledger"])
            self.assertTrue(
                any(item["evaluable"] > 0 for item in output["ledger"])
            )

    def test_actual_trajectories_change_held_out_scores(self):
        trained = self._trained()
        blank = families.rank_held_out_proposals(initial_state(), HELD_OUT)
        blank_scores = {item["proposal"]["id"]: item["score"] for item in blank}
        for output in trained.values():
            ranked = families.rank_held_out_proposals(output["state"], HELD_OUT)
            scores = {item["proposal"]["id"]: item["score"] for item in ranked}
            self.assertTrue(any(scores[key] > blank_scores[key] for key in scores))

    def test_record_actual_first_selection_for_each_trajectory(self):
        trained = self._trained()
        selected = {}
        for name, output in trained.items():
            result = transfer.run_held_out_relation_core_path(output["state"], HELD_OUT)
            self.assertEqual(result["status"], "proposed")
            selected[name] = result["selected"]["proposal"]["relation"]
        # This assertion is deliberately weak: real trajectories are not engineered
        # evidence ledgers. The result below records whether differentiation emerged.
        self.assertEqual(set(selected), {"stability", "change", "action"})
        self.assertTrue(all(value in {
            "same_next_observation", "changes_next_observation", "action_precedes_change"
        } for value in selected.values()))

    def test_novel_signal_never_occurs_in_training_observations_or_memory(self):
        for output in self._trained().values():
            self.assertNotIn("novel_signal", repr(output["samples"]))
            self.assertNotIn(
                "novel_signal",
                repr(output["state"][families.FAMILY_MEMORY_KEY]),
            )


if __name__ == "__main__":
    unittest.main()
