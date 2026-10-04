from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class ActionAssociationProspectiveStudyTests(unittest.TestCase):
    def test_study_is_deterministic_and_covers_three_ecologies(self):
        root = Path(__file__).resolve().parents[1]
        cmd = [sys.executable, str(root / "scripts" / "action_association_prospective_study.py")]
        first = subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["trajectory_count"], 34)
        self.assertEqual(len(report["rows"]), 34)
        worlds = {row["world"] for row in report["rows"]}
        self.assertEqual(worlds, {"world2", "world3", "world4"})
        self.assertEqual(
            sum(report["status_counts"].values()),
            report["trajectory_count"],
        )

    def test_study_does_not_require_support_to_win(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "scripts" / "action_association_prospective_study.py").read_text()
        self.assertNotIn("assert held_out_supported", source)
        self.assertNotIn("best_semantics", source)
        self.assertNotIn("causal", source.lower())


if __name__ == "__main__":
    unittest.main()
