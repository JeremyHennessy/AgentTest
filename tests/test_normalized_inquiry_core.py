from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in ("normalized_inquiry_objectives", "normalized_inquiry_core"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

core_path = sys.modules["normalized_inquiry_core"]


class NormalizedInquiryCoreTests(unittest.TestCase):
    def test_comparable_action_association_reaches_core_as_association(self):
        candidates = [{
            "id": "NE1", "relation": "action_associated_with_change",
            "feature": "local_cue", "action": "interact", "status": "association_observed",
            "effect_difference": 0.5,
            "action_present": {"same": 1, "changed": 3, "evaluable": 4},
            "action_absent": {"same": 3, "changed": 1, "evaluable": 4},
            "evaluable": 8,
        }]
        result = core_path.run_normalized_core_path(
            initial_state(), candidates, "discrimination"
        )
        self.assertEqual(result["status"], "proposed")
        self.assertIn("associated", result["candidate"]["hypothesis"])
        self.assertNotIn("causes", result["candidate"]["hypothesis"].lower())
        self.assertEqual(result["experiment"]["hypothesis"], result["candidate"]["hypothesis"])

    def test_insufficient_action_candidate_cannot_reach_core(self):
        candidates = [{
            "id": "NE1", "relation": "action_associated_with_change",
            "feature": "x", "action": "observe", "status": "insufficient_comparison",
            "action_present": {"same": 2, "changed": 0, "evaluable": 2},
            "action_absent": {"same": 0, "changed": 0, "evaluable": 0},
            "evaluable": 2,
        }]
        result = core_path.run_normalized_core_path(
            initial_state(), candidates, "information_gain"
        )
        self.assertEqual(result["status"], "no_candidate")

    def test_core_path_has_no_execution_or_live_store_authority(self):
        source = (EXPERIMENTS / "normalized_inquiry_core.py").read_text()
        for forbidden in ("transition_world", ".cycle(", ".save(", "StateStore", "subprocess", "requests"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
