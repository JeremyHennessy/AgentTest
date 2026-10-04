from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "runtime_shadow_robust_eval.py"
spec = importlib.util.spec_from_file_location("runtime_shadow_robust_eval", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules["runtime_shadow_robust_eval"] = module
spec.loader.exec_module(module)


class RuntimeShadowRobustEvalTests(unittest.TestCase):
    def test_band_is_frozen_median_relative_with_absolute_floor(self):
        history = [10.0] * 7
        self.assertEqual(module.classify(10.0, history), "normal")
        self.assertEqual(module.classify(12.0, history), "normal")
        self.assertEqual(module.classify(12.1, history), "slower")
        self.assertEqual(module.classify(7.9, history), "faster")

    def test_evaluation_uses_non_overlapping_windows(self):
        observations = []
        for run in range(1, 25):
            observations.append(
                {
                    "run_number": run,
                    "checkout_duration_s": 1.0 + (run % 3),
                    "cycle_duration_s": 8.0 + (run % 2),
                    "preserve_duration_s": 7.0,
                    "total_duration_s": 30.0 + run,
                }
            )
        result = module.evaluate({"observations": observations})
        self.assertEqual(result["complete_window_count"], 2)
        self.assertEqual(result["representation"]["relative_band"], 0.20)
        self.assertEqual(result["representation"]["minimum_absolute_band_s"], 1.0)
        self.assertTrue(result["representation"]["non_overlapping_windows"])

    def test_no_agent_or_state_access(self):
        source = SCRIPT.read_text()
        for forbidden in (
            "AgentCore",
            "StateStore",
            "state/organism.json",
            "propose_native_inquiry",
            "record_native_evidence",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
