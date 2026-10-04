from __future__ import annotations

import importlib.util
import json
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


class World2NativeCoreHarnessTests(unittest.TestCase):
    def test_native_candidate_traverses_real_core_question_and_experiment_methods(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        consumer.consume_native_observation(state, sample(world))
        result = harness.run_native_core_proposal_path(state)
        self.assertEqual(result["status"], "proposed")
        self.assertEqual(result["question"]["source"], "world2_native_endogenous")
        self.assertEqual(result["experiment"]["hypothesis"], result["candidate"]["hypothesis"])
        self.assertEqual(result["experiment"]["method"], result["candidate"]["experiment"])
        self.assertEqual(result["experiment"]["falsification"], result["candidate"]["falsification"])

    def test_input_state_is_not_mutated_and_result_survives_json_reload(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        consumer.consume_native_observation(state, sample(world))
        before = json.loads(json.dumps(state))
        result = harness.run_native_core_proposal_path(state)
        self.assertEqual(state, before)
        restored = json.loads(json.dumps(result["state"], sort_keys=True))
        question_id = result["question"]["id"]
        self.assertTrue(any(item["id"] == question_id for item in restored["questions"]))
        self.assertTrue(any(item["question_id"] == question_id for item in restored["experiments"]))

    def test_direct_refutation_provenance_reaches_core_question_and_intention(self):
        state = initial_state()
        world = world2.initial_world2_state(seed=1)
        world["position"] = [-1, 0]
        consumer.consume_native_observation(state, sample(world))
        world, record = world2.transition_world2(world, "observe", cycle=2)
        consumer.consume_native_observation(state, sample(world, record))
        result = harness.run_native_core_proposal_path(state)
        self.assertEqual(result["intention"]["dominant_drive"], "prediction_error")
        self.assertTrue(result["intention"]["evidence_refs"])
        self.assertEqual(
            result["question"]["source_evidence_refs"],
            result["intention"]["evidence_refs"],
        )

    def test_harness_cannot_execute_world_or_modify_live_store(self):
        source = (EXPERIMENTS / "world2_native_core_harness.py").read_text(encoding="utf-8")
        for forbidden in (
            "transition_world2",
            ".cycle(",
            ".save(",
            "StateStore",
            "action_lab",
            "planning_lab",
            "subprocess",
            "requests",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
