from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
for name in (
    "world4_toggle_ecology",
    "world4_native_observation",
    "normalized_relation_evidence",
    "normalized_inquiry_objectives",
    "public_native_pipeline",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world4 = sys.modules["world4_toggle_ecology"]
native = sys.modules["world4_native_observation"]
pipeline = sys.modules["public_native_pipeline"]


def world4_observations():
    world = world4.initial_world4_state(seed=4)
    observations = [native.native_world4_observation(world4.observe_world4(world))]
    for cycle, action in enumerate(
        ("north", "interact", "observe", "south", "observe", "observe"),
        start=1,
    ):
        world, record = world4.transition_world4(world, action, cycle=cycle)
        observations.append(
            native.native_world4_observation(
                world4.observe_world4(world),
                action_receipt=record,
            )
        )
    return observations


class PublicNativePipelineTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 10
        state["generation"] = 10
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return store

    def test_real_world4_observations_stage_matching_public_evidence_and_inquiry(self):
        store = self.make_store()
        result = pipeline.stage_information_gain_inquiry(
            AgentCore(store),
            world4_observations(),
        )
        winner = result["winner"]["candidate"]
        self.assertEqual(winner["relation"], "same_next_observation")
        evidence = result["evidence_result"]
        inquiry = result["inquiry_result"]
        self.assertTrue(evidence["persisted"])
        self.assertTrue(inquiry["persisted"])
        self.assertEqual(
            evidence["evidence"]["relation"],
            inquiry["candidate"]["relation"],
        )
        self.assertEqual(
            inquiry["candidate"]["evidence_refs"],
            [evidence["evidence_ref"]],
        )
        self.assertEqual(
            inquiry["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertEqual(store.load()["cycles"], 10)

    def test_next_ordinary_cycle_sees_public_native_inquiry_without_action_authority(self):
        store = self.make_store()
        core = AgentCore(store)
        staged = pipeline.stage_information_gain_inquiry(
            core,
            world4_observations(),
        )
        question_id = staged["inquiry_result"]["question"]["id"]
        result = core.cycle(
            stimulus="continue ordinary operation",
            _now_override="2026-10-04T00:02:00+00:00",
        )
        self.assertIsNone(result["action_lab_result"])
        self.assertIsNone(result["planning_lab_result"])
        decision = result["agenda_decision"]
        self.assertIsNotNone(decision)
        native = next(
            item
            for item in decision["candidate_summaries"]
            if item["question_id"] == question_id
        )
        self.assertTrue(native["active_experiment_path"])
        self.assertEqual(store.load()["cycles"], 11)

    def test_bridge_consumes_observations_but_cannot_execute_world(self):
        source = (EXPERIMENTS / "public_native_pipeline.py").read_text()
        for forbidden in (
            "transition_world",
            "action_lab",
            "planning_lab",
            "subprocess",
            "requests",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
