from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class NormalizedInquiryObjectiveTests(unittest.TestCase):
    def test_study_is_deterministic_and_complete(self):
        root = Path(__file__).resolve().parents[1]
        cmd = [sys.executable, str(root / "scripts" / "normalized_inquiry_objective_study.py")]
        first = subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["trajectory_count"], 45)
        self.assertEqual(len(report["objectives"]), 5)
        for result in report["objectives"].values():
            self.assertEqual(sum(result["winner_counts"].values()), 45)

    def test_objectives_do_not_score_insufficient_action_comparison_as_eligible(self):
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "experiments"))
        from normalized_inquiry_objectives import rank_normalized_candidates
        candidate = {
            "id": "NE1", "relation": "action_associated_with_change",
            "feature": "x", "action": "observe", "status": "insufficient_comparison",
            "action_present": {"same": 2, "changed": 0, "evaluable": 2},
            "action_absent": {"same": 0, "changed": 0, "evaluable": 0},
            "evaluable": 2,
        }
        for objective in ("information_gain", "discrimination", "falsifiability", "uncertainty_reduction", "evidence_balance"):
            ranked = rank_normalized_candidates([candidate], objective)
            self.assertFalse(ranked[0]["eligible"])
            self.assertIsNone(ranked[0]["score"])

    def test_objective_module_is_world_and_truth_blind(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "experiments" / "normalized_inquiry_objectives.py").read_text()
        for forbidden in ("world2", "world3", "seed", "latent_mode", "novel_signal", "cue_sites"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
