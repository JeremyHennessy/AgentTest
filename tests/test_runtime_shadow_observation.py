from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "runtime_shadow_observation.py"
spec = importlib.util.spec_from_file_location("runtime_shadow_observation", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimeShadowObservationTests(unittest.TestCase):
    def test_normalize_run_uses_only_observable_workflow_metadata(self):
        run = {
            "id": 10,
            "run_number": 100,
            "head_sha": "abc",
            "conclusion": "success",
            "created_at": "2026-10-04T00:00:00Z",
            "run_started_at": "2026-10-04T00:00:02Z",
            "updated_at": "2026-10-04T00:00:40Z",
        }
        job = {
            "steps": [
                {
                    "name": "Run actions/checkout@v4",
                    "started_at": "2026-10-04T00:00:03Z",
                    "completed_at": "2026-10-04T00:00:05Z",
                },
                {
                    "name": "Observe and run one autonomous cycle",
                    "started_at": "2026-10-04T00:00:09Z",
                    "completed_at": "2026-10-04T00:00:18Z",
                },
            ]
        }
        obs = module.normalize_run(run, job)
        self.assertEqual(obs["queue_delay_s"], 2.0)
        self.assertEqual(obs["checkout_duration_s"], 2.0)
        self.assertEqual(obs["cycle_duration_s"], 9.0)
        self.assertEqual(obs["total_duration_s"], 38.0)
        self.assertNotIn("phase42_passed", obs)
        self.assertNotIn("selected_question", obs)

    def test_summary_reports_temporal_variation_without_truth_labels(self):
        observations = [
            {
                "run_id": 1,
                "run_number": 1,
                "conclusion": "success",
                "queue_delay_s": 2.0,
                "total_duration_s": 30.0,
                "checkout_duration_s": 1.0,
                "cycle_duration_s": 8.0,
                "preserve_duration_s": 7.0,
            },
            {
                "run_id": 2,
                "run_number": 2,
                "conclusion": "success",
                "queue_delay_s": 3.0,
                "total_duration_s": 34.0,
                "checkout_duration_s": 2.0,
                "cycle_duration_s": 9.0,
                "preserve_duration_s": 7.0,
            },
        ]
        summary = module.summarize(observations)
        self.assertTrue(summary["deduplicated"])
        self.assertTrue(summary["all_successful"])
        self.assertEqual(summary["fields"]["cycle_duration_s"]["distinct_count"], 2)
        self.assertEqual(summary["fields"]["cycle_duration_s"]["change_rate"], 1.0)

    def test_script_has_no_state_write_or_agent_core_access(self):
        source = SCRIPT.read_text()
        for forbidden in (
            "StateStore",
            "AgentCore",
            "state/organism.json",
            "update_agenda",
            "propose_native_inquiry",
            "record_native_evidence",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
