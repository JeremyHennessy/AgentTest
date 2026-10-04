from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
spec = importlib.util.spec_from_file_location(
    "action_association_semantics",
    EXPERIMENTS / "action_association_semantics.py",
)
assert spec is not None and spec.loader is not None
semantics = importlib.util.module_from_spec(spec)
sys.modules["action_association_semantics"] = semantics
spec.loader.exec_module(semantics)


def candidate(*, p_changed, p_same, a_changed, a_same):
    return {
        "id": "NE1",
        "relation": "action_associated_with_change",
        "feature": "slow_signal",
        "action": "interact",
        "status": "association_observed",
        "action_present": {
            "changed": p_changed,
            "same": p_same,
            "evaluable": p_changed + p_same,
        },
        "action_absent": {
            "changed": a_changed,
            "same": a_same,
            "evaluable": a_changed + a_same,
        },
        "evaluable": p_changed + p_same + a_changed + a_same,
    }


class ActionAssociationSemanticsTests(unittest.TestCase):
    def test_material_difference_is_supported_association_not_causation(self):
        result = semantics.interpret_action_association(
            candidate(p_changed=3, p_same=1, a_changed=1, a_same=3)
        )
        self.assertEqual(result["status"], "supported_association")
        self.assertEqual(result["direction"], "higher_with_action")
        self.assertFalse(result["causal"])
        self.assertNotIn("cause", result["claim"].lower())

    def test_small_difference_is_contradicted_association(self):
        result = semantics.interpret_action_association(
            candidate(p_changed=5, p_same=5, a_changed=4, a_same=6)
        )
        self.assertEqual(result["status"], "contradicted_association")
        self.assertEqual(result["confirmations"], 0)
        self.assertEqual(result["refutations"], 20)

    def test_one_sided_exposure_is_insufficient_not_contradiction(self):
        item = candidate(p_changed=3, p_same=1, a_changed=0, a_same=0)
        item["status"] = "insufficient_comparison"
        result = semantics.interpret_action_association(item)
        self.assertEqual(result["status"], "insufficient_comparison")
        self.assertFalse(result["causal"])

    def test_held_out_support_requires_material_effect_and_same_direction(self):
        prefix = candidate(p_changed=3, p_same=1, a_changed=1, a_same=3)
        same = candidate(p_changed=4, p_same=1, a_changed=1, a_same=4)
        reverse = candidate(p_changed=1, p_same=4, a_changed=4, a_same=1)
        weak = candidate(p_changed=5, p_same=5, a_changed=4, a_same=6)
        self.assertEqual(
            semantics.compare_prefix_to_suffix(prefix, same)["status"],
            "held_out_supported",
        )
        self.assertEqual(
            semantics.compare_prefix_to_suffix(prefix, reverse)["status"],
            "held_out_contradicted",
        )
        self.assertEqual(
            semantics.compare_prefix_to_suffix(prefix, weak)["status"],
            "held_out_contradicted",
        )

    def test_public_mapping_preserves_two_exposure_table(self):
        interpreted = semantics.interpret_action_association(
            candidate(p_changed=3, p_same=1, a_changed=1, a_same=3)
        )
        payload = semantics.public_evidence_payload(
            interpreted,
            observation_refs=["o1", "o2", "o3", "o4"],
        )
        self.assertEqual(payload["version"], "native-inquiry-evidence-v2")
        self.assertEqual(payload["measurement_kind"], "comparative_action_exposure")
        self.assertEqual(
            payload["measurement"]["action_present"],
            {"changed": 3, "same": 1, "evaluable": 4},
        )
        self.assertEqual(
            payload["measurement"]["action_absent"],
            {"changed": 1, "same": 3, "evaluable": 4},
        )
        self.assertEqual(
            payload["measurement"]["observed_change_rate_difference"],
            0.5,
        )
        self.assertNotIn("confirmations", payload)
        self.assertNotIn("refutations", payload)

    def test_semantics_module_has_no_world_or_hidden_truth_access(self):
        source = (EXPERIMENTS / "action_association_semantics.py").read_text()
        for forbidden in (
            "world2",
            "world3",
            "world4",
            "seed",
            "latent_mode",
            "lever_position",
            "resource_phase",
            "cue_sites",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
