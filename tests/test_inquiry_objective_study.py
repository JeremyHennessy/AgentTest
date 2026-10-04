from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class InquiryObjectiveStudyTests(unittest.TestCase):
    def test_study_is_deterministic_and_covers_all_predeclared_objectives(self):
        root = Path(__file__).resolve().parents[1]
        command = [sys.executable, str(root / "scripts" / "inquiry_objective_study.py")]
        first = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["trajectory_count"], 45)
        self.assertEqual(
            set(report["objectives"]),
            {
                "baseline",
                "information_gain",
                "discrimination",
                "falsifiability",
                "uncertainty_reduction",
                "evidence_balance",
            },
        )
        for result in report["objectives"].values():
            self.assertEqual(sum(result["winner_counts"].values()), 45)
            self.assertEqual(result["selection_diversity"], len(result["distinct_winners"]))

    def test_study_does_not_assert_that_any_alternative_must_be_more_diverse(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "scripts" / "inquiry_objective_study.py").read_text()
        self.assertNotIn("assert selection_diversity", source)
        self.assertNotIn("best_objective", source)

    def test_objective_module_has_no_world_or_target_truth_access(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "experiments" / "inquiry_objectives.py").read_text()
        for forbidden in (
            "world2",
            "world3",
            "novel_signal",
            "latent_mode",
            "resource_phase",
            "cue_sites",
            "seed",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
