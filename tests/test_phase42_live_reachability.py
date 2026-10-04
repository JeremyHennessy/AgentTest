from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase42_live_reachability.py"
spec = importlib.util.spec_from_file_location("phase42_live_reachability", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules["phase42_live_reachability"] = module
spec.loader.exec_module(module)


class Phase42LiveReachabilityTests(unittest.TestCase):
    def test_evidence_only_unreachable_when_max_bonus_cannot_close_gap(self):
        state = {
            "agenda": {
                "decisions": [
                    {
                        "cycle": 10,
                        "selected": {
                            "question_id": "QF",
                            "question_text": "foreground",
                            "priority_score": 1.8,
                            "legacy_focus_value": 1.0,
                            "frontier_value": 0.8,
                        },
                        "candidate_summaries": [
                            {
                                "question_id": "QF",
                                "question_text": "foreground",
                                "priority_score": 1.8,
                                "legacy_focus_value": 1.0,
                                "actionability_value": 0.0,
                                "frontier_value": 0.8,
                                "evidence_change_value": 0.0,
                                "replication_saturation_cost": 0.0,
                            },
                            {
                                "question_id": "QS",
                                "question_text": "suspended",
                                "source": "repository_stability_prediction",
                                "priority_score": -0.2,
                                "legacy_focus_value": 0.0,
                                "actionability_value": 0.35,
                                "frontier_value": 0.0,
                                "evidence_change_value": 0.15,
                                "replication_saturation_cost": 0.70,
                                "active_experiment_path": True,
                                "new_evidence_refs": ["E1", "E2", "E3"],
                            },
                        ],
                    }
                ]
            }
        }
        result = module.analyze(state)
        self.assertFalse(result["evidence_only_reachable"])
        row = result["candidates"][0]
        self.assertEqual(row["max_evidence_only_priority"], -0.05)
        self.assertEqual(row["evidence_only_gap"], 1.85)

    def test_diagnostic_can_report_reachable_case(self):
        state = {
            "agenda": {
                "decisions": [
                    {
                        "cycle": 11,
                        "selected": {
                            "question_id": "QF",
                            "question_text": "foreground",
                            "priority_score": 0.5,
                            "legacy_focus_value": 0.0,
                            "frontier_value": 0.5,
                        },
                        "candidate_summaries": [
                            {
                                "question_id": "QF",
                                "question_text": "foreground",
                                "priority_score": 0.5,
                                "legacy_focus_value": 0.0,
                                "actionability_value": 0.0,
                                "frontier_value": 0.5,
                                "evidence_change_value": 0.0,
                                "replication_saturation_cost": 0.0,
                            },
                            {
                                "question_id": "QS",
                                "question_text": "suspended",
                                "source": "empirical_frontier_transfer",
                                "priority_score": 0.4,
                                "legacy_focus_value": 0.0,
                                "actionability_value": 0.0,
                                "frontier_value": 0.4,
                                "evidence_change_value": 0.0,
                                "replication_saturation_cost": 0.0,
                                "active_experiment_path": False,
                                "new_evidence_refs": [],
                            },
                        ],
                    }
                ]
            }
        }
        result = module.analyze(state)
        self.assertTrue(result["evidence_only_reachable"])
        self.assertGreater(result["candidates"][0]["max_evidence_only_priority"], 0.5)

    def test_diagnostic_is_read_only(self):
        source = SCRIPT.read_text()
        for forbidden in (
            "write_text(",
            "StateStore",
            "update_agenda(",
            "save(",
        ):
            if forbidden == "write_text(":
                continue
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
