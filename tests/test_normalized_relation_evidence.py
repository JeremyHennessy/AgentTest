from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology", "world2_native_observation",
    "world3_ecology", "world3_native_observation",
    "normalized_relation_evidence",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

w2 = sys.modules["world2_ecology"]
w2n = sys.modules["world2_native_observation"]
w3 = sys.modules["world3_ecology"]
w3n = sys.modules["world3_native_observation"]
normalized = sys.modules["normalized_relation_evidence"]


class NormalizedRelationEvidenceTests(unittest.TestCase):
    def test_action_exposure_partitions_same_evaluable_pairs(self):
        world = w2.initial_world2_state(seed=1)
        samples = [w2n.native_world2_observation(w2.observe_world2(world))]
        for cycle, action in enumerate(("north", "interact", "observe", "observe"), start=1):
            world, record = w2.transition_world2(world, action, cycle=cycle)
            samples.append(w2n.native_world2_observation(w2.observe_world2(world), action_receipt=record))
        evidence = normalized.normalized_evidence(samples)
        for feature in evidence["features"].values():
            total = feature["transitions"]["evaluable"]
            for exposure in feature["action_exposures"].values():
                self.assertEqual(
                    exposure["action_present"]["evaluable"] + exposure["action_absent"]["evaluable"],
                    total,
                )

    def test_action_candidate_requires_both_exposure_groups(self):
        world = w3.initial_world3_state(seed=1)
        samples = [w3n.native_world3_observation(w3.observe_world3(world))]
        for cycle in range(1, 4):
            world, record = w3.transition_world3(world, "observe", cycle=cycle)
            samples.append(w3n.native_world3_observation(w3.observe_world3(world), action_receipt=record))
        candidates = normalized.normalized_relation_candidates(normalized.normalized_evidence(samples))
        action_candidates = [x for x in candidates if x["relation"] == "action_associated_with_change"]
        self.assertTrue(action_candidates)
        self.assertTrue(all(x["status"] == "insufficient_comparison" for x in action_candidates))

    def test_object_interaction_reports_association_not_causation(self):
        world = w3.initial_world3_state(seed=1)
        world["position"] = [1, 1]
        samples = [w3n.native_world3_observation(w3.observe_world3(world))]
        for cycle, action in enumerate(("interact", "observe", "observe"), start=1):
            world, record = w3.transition_world3(world, action, cycle=cycle)
            samples.append(w3n.native_world3_observation(w3.observe_world3(world), action_receipt=record))
        candidates = normalized.normalized_relation_candidates(normalized.normalized_evidence(samples))
        rendered = repr(candidates).lower()
        self.assertIn("association", rendered)
        self.assertNotIn("causal", rendered)

    def test_normalizer_has_no_hidden_truth_access(self):
        source = (EXPERIMENTS / "normalized_relation_evidence.py").read_text()
        for forbidden in ("world2", "world3", "seed", "latent_mode", "resource_phase", "cue_sites", "pending_slow_effects"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
