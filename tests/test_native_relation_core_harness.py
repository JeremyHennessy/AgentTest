from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology", "world2_native_observation",
    "world3_ecology", "world3_native_observation",
    "native_relation_discovery", "native_relation_core_harness",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

w2 = sys.modules["world2_ecology"]
w2n = sys.modules["world2_native_observation"]
w3 = sys.modules["world3_ecology"]
w3n = sys.modules["world3_native_observation"]
harness = sys.modules["native_relation_core_harness"]


class NativeRelationCoreHarnessTests(unittest.TestCase):
    def test_world2_relation_candidate_reaches_real_core(self):
        world = w2.initial_world2_state(seed=1)
        samples = [w2n.native_world2_observation(w2.observe_world2(world))]
        for cycle, action in enumerate(("north", "interact", "observe", "observe", "observe", "observe"), start=1):
            world, record = w2.transition_world2(world, action, cycle=cycle)
            samples.append(w2n.native_world2_observation(w2.observe_world2(world), action_receipt=record))
        result = harness.run_relation_core_path(initial_state(), samples)
        self.assertEqual(result["status"], "proposed")
        self.assertEqual(result["question"]["source"], "native_relation_discovery")
        self.assertEqual(result["experiment"]["hypothesis"], result["candidate"]["hypothesis"])

    def test_world3_relation_candidate_reaches_same_real_core_path(self):
        world = w3.initial_world3_state(seed=2)
        world["position"] = [0, 1]
        samples = [w3n.native_world3_observation(w3.observe_world3(world))]
        for cycle in range(1, 6):
            world, record = w3.transition_world3(world, "observe", cycle=cycle)
            samples.append(w3n.native_world3_observation(w3.observe_world3(world), action_receipt=record))
        result = harness.run_relation_core_path(initial_state(), samples)
        self.assertEqual(result["status"], "proposed")
        self.assertEqual(result["question"]["source"], "native_relation_discovery")
        self.assertIn(result["intention"]["dominant_drive"], {"prediction_error", "evidence_hunger"})

    def test_one_observation_has_no_evaluable_relation_and_no_core_candidate(self):
        world = w3.initial_world3_state(seed=1)
        samples = [w3n.native_world3_observation(w3.observe_world3(world))]
        result = harness.run_relation_core_path(initial_state(), samples)
        self.assertEqual(result["status"], "no_candidate")

    def test_core_harness_does_not_execute_or_save(self):
        source = (EXPERIMENTS / "native_relation_core_harness.py").read_text(encoding="utf-8")
        for forbidden in ("transition_world", ".cycle(", ".save(", "StateStore", "subprocess", "requests"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
