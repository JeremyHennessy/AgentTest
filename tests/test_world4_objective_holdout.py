from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"

for name in ("world4_toggle_ecology", "world4_native_observation"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world4 = sys.modules["world4_toggle_ecology"]
native = sys.modules["world4_native_observation"]


class World4ObjectiveHoldoutTests(unittest.TestCase):
    def test_native_observation_excludes_hidden_lever_location_and_mode_names(self):
        for seed in range(1, 5):
            world = world4.initial_world4_state(seed=seed)
            envelope = native.native_world4_observation(world4.observe_world4(world))
            rendered = repr(envelope)
            self.assertNotIn("lever_position", rendered)
            self.assertNotIn("signal_mode", rendered)
            self.assertNotIn("interaction_count", rendered)
            self.assertNotIn("seed", rendered)

    def test_interact_only_toggles_signal_at_visible_lever(self):
        world = world4.initial_world4_state(seed=4)
        self.assertEqual(world["lever_position"], [1, 0])
        initial = world4.observe_world4(world)["slow_signal"]
        world, _ = world4.transition_world4(world, "interact", cycle=1)
        self.assertEqual(world4.observe_world4(world)["slow_signal"], initial)
        world, _ = world4.transition_world4(world, "north", cycle=2)
        self.assertEqual(world4.observe_world4(world)["visible_objects"], ["lever"])
        world, record = world4.transition_world4(world, "interact", cycle=3)
        self.assertEqual(record["interaction_effect"], "signal_toggled")
        self.assertNotEqual(world4.observe_world4(world)["slow_signal"], initial)

    def test_holdout_report_is_deterministic_and_uses_frozen_objectives(self):
        cmd = [sys.executable, str(ROOT / "scripts" / "world4_objective_holdout.py")]
        first = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertEqual(report["trajectory_count"], 24)
        self.assertEqual(report["objectives_frozen_from"], "normalized-inquiry-objectives-v1")
        self.assertEqual(report["split_protocols"], ["early", "midpoint", "late"])
        for split in report["split_protocols"]:
            self.assertEqual(len(report["splits"][split]), 5)
            for result in report["splits"][split].values():
                self.assertEqual(result["selected_count"], 24)

    def test_world4_study_does_not_modify_objective_module(self):
        objective_source = (EXPERIMENTS / "normalized_inquiry_objectives.py").read_text()
        self.assertNotIn("world4", objective_source)
        self.assertNotIn("toggle", objective_source)


if __name__ == "__main__":
    unittest.main()
