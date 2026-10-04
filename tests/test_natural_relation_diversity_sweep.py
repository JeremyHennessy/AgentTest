from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class NaturalRelationDiversitySweepTests(unittest.TestCase):
    def test_sweep_is_deterministic_complete_and_truth_blind(self):
        root = Path(__file__).resolve().parents[1]
        command = [sys.executable, str(root / "scripts" / "natural_relation_diversity_sweep.py")]
        first = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["trajectory_count"], 45)
        self.assertEqual(sum(report["winner_counts"].values()), 45)
        self.assertEqual(report["held_out_feature"], "novel_signal")
        self.assertEqual(
            report["crossed_selection_boundary"],
            len(report["distinct_winners"]) > 1,
        )
        self.assertTrue(all("novel_signal" not in repr(item["family_memory"]) for item in report["results"]))

    def test_sweep_does_not_assert_that_diversity_must_succeed(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "natural_relation_diversity_sweep.py").read_text()
        self.assertIn('"crossed_selection_boundary": len(counts) > 1', source)
        self.assertNotIn("assert len(counts)", source)


if __name__ == "__main__":
    unittest.main()
