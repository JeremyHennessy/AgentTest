from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"

for name in (
    "normalized_inquiry_objectives",
    "normalized_relation_evidence",
    "prospective_inquiry_benchmark",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

benchmark = sys.modules["prospective_inquiry_benchmark"]


class ProspectiveInquiryBenchmarkTests(unittest.TestCase):
    def test_action_absent_suffix_still_updates_selected_association(self):
        prefix_candidate = {
            "id": "NE1",
            "relation": "action_associated_with_change",
            "feature": "slow_signal",
            "action": "interact",
            "status": "association_observed",
            "effect_difference": 0.5,
            "action_present": {"same": 1, "changed": 1, "evaluable": 2},
            "action_absent": {"same": 2, "changed": 0, "evaluable": 2},
            "evaluable": 4,
        }
        suffix = [
            {
                "visible_object_ids": [],
                "slow_signal": {"status": "measured", "scope": "broadcast", "value": 0},
                "action_receipt": None,
            },
            {
                "visible_object_ids": [],
                "slow_signal": {"status": "measured", "scope": "broadcast", "value": 0},
                "action_receipt": {"action": "observe"},
            },
            {
                "visible_object_ids": [],
                "slow_signal": {"status": "measured", "scope": "broadcast", "value": 1},
                "action_receipt": {"action": "observe"},
            },
        ]
        held = benchmark._evaluate_action_association(prefix_candidate, suffix)
        self.assertTrue(held["evaluable"])
        self.assertEqual(held["action_present_evidence"], 0)
        self.assertEqual(held["action_absent_evidence"], 2)
        self.assertEqual(held["status"], "partial_exposure")

    def test_full_study_is_deterministic_and_prefix_suffix_separated(self):
        command = [sys.executable, str(ROOT / "scripts" / "prospective_inquiry_benchmark.py")]
        first = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["trajectory_count"], 45)
        self.assertEqual(report["selection_protocol"], "prefix_only_then_held_out_suffix")
        for row in report["rows"]:
            bench = row["benchmark"]
            self.assertGreater(bench["held_out_new_sample_count"], 0)
            self.assertNotEqual(
                bench["prefix_last_observation_id"],
                bench["first_unseen_observation_id"],
            )
        for result in report["objectives"].values():
            self.assertEqual(result["selected_count"], 45)
            self.assertLessEqual(result["held_out_evaluable_count"], 45)

    def test_benchmark_does_not_choose_a_best_objective(self):
        source = (ROOT / "scripts" / "prospective_inquiry_benchmark.py").read_text()
        self.assertNotIn("best_objective", source)
        self.assertNotIn("winner_objective", source)


if __name__ == "__main__":
    unittest.main()
