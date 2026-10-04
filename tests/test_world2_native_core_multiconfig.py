from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology",
    "world2_native_observation",
    "world2_native_prediction",
    "world2_native_consumer",
    "world2_native_opportunity",
    "world2_native_endogenous",
    "world2_native_agentcore_proposal",
    "world2_native_core_harness",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world2 = sys.modules["world2_ecology"]
native = sys.modules["world2_native_observation"]
consumer = sys.modules["world2_native_consumer"]
harness = sys.modules["world2_native_core_harness"]


def sample(world, record=None):
    return native.native_world2_observation(
        world2.observe_world2(world), action_receipt=record
    )


class World2NativeCoreMultiConfigTests(unittest.TestCase):
    def test_direct_resource_change_reaches_copied_core_in_all_phase_configs(self):
        for seed in range(1, 6):
            with self.subTest(seed=seed):
                state = initial_state()
                world = world2.initial_world2_state(seed=seed)
                world["position"] = [-1, 0]
                consumer.consume_native_observation(state, sample(world))
                initial = world["resources"]["-1,0"]
                for cycle in range(1, 7):
                    world, record = world2.transition_world2(world, "observe", cycle=cycle)
                    consumer.consume_native_observation(state, sample(world, record))
                    if world["resources"]["-1,0"] != initial:
                        break
                result = harness.run_native_core_proposal_path(state)
                self.assertEqual(result["status"], "proposed")
                self.assertEqual(result["intention"]["dominant_drive"], "prediction_error")
                self.assertTrue(result["question"]["source_evidence_refs"])
                self.assertEqual(
                    result["experiment"]["question_id"],
                    result["question"]["id"],
                )
                rendered = repr(result["candidate"])
                for forbidden in ("seed", "resource_phase", "latent_mode", "matures_cycle"):
                    self.assertNotIn(forbidden, rendered)

    def test_empty_native_memory_does_not_manufacture_grounded_candidate(self):
        state = initial_state()
        result = harness.run_native_core_proposal_path(state)
        self.assertEqual(result["status"], "no_candidate")


if __name__ == "__main__":
    unittest.main()
