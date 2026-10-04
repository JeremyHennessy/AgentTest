from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
for name in (
    "world4_toggle_ecology",
    "world4_native_observation",
    "normalized_relation_evidence",
    "native_evidence_v2_design",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world4 = sys.modules["world4_toggle_ecology"]
native = sys.modules["world4_native_observation"]
normalized = sys.modules["normalized_relation_evidence"]
v2 = sys.modules["native_evidence_v2_design"]


def trajectory():
    world = world4.initial_world4_state(seed=4)
    samples = [native.native_world4_observation(world4.observe_world4(world))]
    for cycle, action in enumerate(
        ("north", "interact", "observe", "south", "observe"),
        start=1,
    ):
        world, record = world4.transition_world4(world, action, cycle=cycle)
        samples.append(
            native.native_world4_observation(
                world4.observe_world4(world),
                action_receipt=record,
            )
        )
    return samples


class NativeEvidenceV2DesignTests(unittest.TestCase):
    def test_real_world4_interact_signal_association_maps_without_false_truth_labels(self):
        samples = trajectory()
        candidates = normalized.normalized_relation_candidates(
            normalized.normalized_evidence(samples)
        )
        source = next(
            item for item in candidates
            if item["relation"] == "action_associated_with_change"
            and item["feature"] == "slow_signal"
            and item["action"] == "interact"
        )
        self.assertEqual(source["status"], "association_observed")
        self.assertGreater(source["action_present"]["evaluable"], 0)
        self.assertGreater(source["action_absent"]["evaluable"], 0)

        relation = {
            "kind": source["relation"],
            "feature": source["feature"],
            "action": source["action"],
            "comparison_status": "comparable",
        }
        evidence = v2.action_association_evidence_v2(
            relation=relation,
            observation_refs=[
                item["observation_id"] for item in samples
            ],
            action_present=source["action_present"],
            action_absent=source["action_absent"],
        )
        self.assertEqual(
            evidence["measurement_kind"],
            "comparative_action_exposure",
        )
        self.assertNotIn("confirmations", json.dumps(evidence))
        self.assertNotIn("refutations", json.dumps(evidence))
        self.assertEqual(
            evidence["measurement"]["observed_change_rate_difference"],
            source["effect_difference"],
        )
        self.assertEqual(v2.validate_evidence_v2(evidence), evidence)

    def test_temporal_v2_keeps_binary_confirmation_refutation_semantics(self):
        relation = {
            "kind": "same_next_observation",
            "feature": "slow_signal",
            "action": None,
            "comparison_status": "not_applicable",
        }
        evidence = v2.temporal_evidence_v2(
            relation=relation,
            observation_refs=["a", "b", "c"],
            evaluable=2,
            confirmations=1,
            refutations=1,
        )
        self.assertEqual(
            evidence["measurement_kind"],
            "binary_transition_outcomes",
        )
        self.assertEqual(evidence["measurement"]["confirmations"], 1)
        self.assertEqual(evidence["measurement"]["refutations"], 1)

    def test_action_v2_rejects_one_sided_exposure(self):
        relation = {
            "kind": "action_associated_with_change",
            "feature": "slow_signal",
            "action": "interact",
            "comparison_status": "comparable",
        }
        with self.assertRaises(ValueError):
            v2.action_association_evidence_v2(
                relation=relation,
                observation_refs=["a", "b"],
                action_present={"evaluable": 1, "changed": 1, "same": 0},
                action_absent={"evaluable": 0, "changed": 0, "same": 0},
            )

    def test_v2_design_is_world_agnostic(self):
        source = (EXPERIMENTS / "native_evidence_v2_design.py").read_text()
        for forbidden in (
            "world4",
            "world3",
            "world2",
            "lever",
            "seed",
            "latent_mode",
            "cause",
            "causal",
        ):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
