from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "open_object_world_epistemic_replication.py"
spec = importlib.util.spec_from_file_location(
    "open_object_world_epistemic_replication",
    SCRIPT,
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules["open_object_world_epistemic_replication"] = module
spec.loader.exec_module(module)


class OpenObjectWorldEpistemicReplicationTests(unittest.TestCase):
    def test_checkpoint_protocol_is_dense_and_predeclared(self):
        self.assertEqual(module.CHECKPOINTS[0], 200)
        self.assertEqual(module.CHECKPOINTS[-1], 950)
        self.assertEqual(len(module.CHECKPOINTS), 16)
        self.assertTrue(
            all(
                right - left == 50
                for left, right in zip(
                    module.CHECKPOINTS,
                    module.CHECKPOINTS[1:],
                )
            )
        )

    def test_replication_script_does_not_define_new_policy_thresholds(self):
        source = SCRIPT.read_text()
        for forbidden in (
            "MIN_EFFECT_SAMPLES =",
            "falsification_probability =",
            "epistemic_score =",
            "reward",
            "solution",
            "goal",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
