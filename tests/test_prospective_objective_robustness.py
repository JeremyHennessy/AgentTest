from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class ProspectiveObjectiveRobustnessTests(unittest.TestCase):
    def test_report_is_deterministic_and_covers_all_splits(self):
        root = Path(__file__).resolve().parents[1]
        cmd = [sys.executable, str(root / "scripts" / "prospective_objective_robustness.py")]
        first = subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["trajectory_count"], 45)
        self.assertEqual(
            report["split_protocols"],
            ["early", "midpoint", "late"],
        )
        for split in report["split_protocols"]:
            self.assertEqual(len(report["split_reports"][split]), 5)
            for result in report["split_reports"][split].values():
                self.assertEqual(result["selected_count"], 45)
                self.assertLessEqual(result["held_out_evaluable_count"], 45)

    def test_split_strategy_is_predeclared_not_outcome_dependent(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "scripts" / "prospective_objective_robustness.py").read_text()
        self.assertIn('SPLITS = ("early", "midpoint", "late")', source)
        self.assertNotIn("best_split", source)
        self.assertNotIn("best_objective", source)

    def test_default_midpoint_behavior_remains_available(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "experiments" / "prospective_inquiry_benchmark.py").read_text()
        self.assertIn("split_index: int | None = None", source)


if __name__ == "__main__":
    unittest.main()
