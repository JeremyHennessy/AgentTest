from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "runtime_shadow_temporal_eval.py"
spec = importlib.util.spec_from_file_location("runtime_shadow_temporal_eval", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules["runtime_shadow_temporal_eval"] = module
spec.loader.exec_module(module)


class RuntimeShadowTemporalEvalTests(unittest.TestCase):
    def test_prefix_selection_is_scored_only_on_held_out_half(self):
        observations = []
        totals = [30, 31, 32, 33, 34, 35, 36, 37]
        cycles = [8, 8, 8, 8, 9, 8, 9, 8]
        checkouts = [1, 1, 2, 1, 2, 1, 2, 1]
        preserves = [7, 7, 7, 7, 7, 8, 7, 8]
        for index in range(8):
            observations.append(
                {
                    "run_number": index + 1,
                    "total_duration_s": totals[index],
                    "cycle_duration_s": cycles[index],
                    "checkout_duration_s": checkouts[index],
                    "preserve_duration_s": preserves[index],
                }
            )
        report = {"observations": observations}
        result = module.evaluate(report)
        total = result["results"]["total_duration_s"]
        self.assertEqual(total["selected_relation"], "changes_next_observation")
        self.assertEqual(total["held_out_support_rate"], 1.0)
        cycle = result["results"]["cycle_duration_s"]
        self.assertEqual(cycle["selected_relation"], "same_next_observation")
        self.assertLess(cycle["held_out_support_rate"], 1.0)

    def test_evaluator_is_shadow_only(self):
        source = SCRIPT.read_text()
        for forbidden in (
            "AgentCore",
            "StateStore",
            "propose_native_inquiry",
            "record_native_evidence",
            "state/organism.json",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
