from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class TrajectoryRelationTransferReportTests(unittest.TestCase):
    def test_report_is_deterministic_and_records_actual_profiles(self):
        root = Path(__file__).resolve().parents[1]
        command = [sys.executable, str(root / "scripts" / "trajectory_relation_transfer_report.py")]
        first = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["held_out_feature"], "novel_signal")
        self.assertEqual(set(report["profiles"]), {"stability", "change", "action"})
        for profile in report["profiles"].values():
            self.assertGreater(profile["sample_count"], 1)
            self.assertIn(
                profile["selected_relation"],
                {"same_next_observation", "changes_next_observation", "action_precedes_change"},
            )
            self.assertGreater(profile["selected_score"], 0.3)


if __name__ == "__main__":
    unittest.main()
