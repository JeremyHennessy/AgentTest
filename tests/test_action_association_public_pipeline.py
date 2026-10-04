from __future__ import annotations

import importlib.util
import tempfile
import sys
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
for name in (
    "action_association_semantics",
    "action_association_public_pipeline",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

pipeline = sys.modules["action_association_public_pipeline"]


def supported_candidate():
    return {
        "id": "NE-assoc",
        "relation": "action_associated_with_change",
        "feature": "slow_signal",
        "action": "interact",
        "status": "association_observed",
        "action_present": {"changed": 3, "same": 1, "evaluable": 4},
        "action_absent": {"changed": 1, "same": 3, "evaluable": 4},
        "evaluable": 8,
    }


class ActionAssociationPublicPipelineTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return store

    def test_supported_association_stages_through_public_apis(self):
        store = self.make_store()
        result = pipeline.stage_association_inquiry(
            AgentCore(store),
            supported_candidate(),
            observation_refs=[f"obs-{i}" for i in range(1, 9)],
        )
        evidence = result["evidence_result"]
        inquiry = result["inquiry_result"]
        self.assertEqual(
            evidence["evidence"]["relation"],
            inquiry["candidate"]["relation"],
        )
        self.assertEqual(
            evidence["evidence"]["confirmations"],
            8,
        )
        self.assertEqual(
            evidence["evidence"]["refutations"],
            0,
        )
        self.assertEqual(
            inquiry["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertNotIn(
            "causes",
            inquiry["candidate"]["hypothesis"].lower(),
        )
        self.assertEqual(store.load()["cycles"], 20)

    def test_next_ordinary_cycle_sees_association_inquiry_without_action_authority(self):
        store = self.make_store()
        core = AgentCore(store)
        staged = pipeline.stage_association_inquiry(
            core,
            supported_candidate(),
            observation_refs=[f"obs-{i}" for i in range(1, 9)],
        )
        question_id = staged["inquiry_result"]["question"]["id"]
        cycle = core.cycle(
            stimulus="continue ordinary operation",
            _now_override="2026-10-04T00:03:00+00:00",
        )
        self.assertIsNone(cycle["action_lab_result"])
        self.assertIsNone(cycle["planning_lab_result"])
        summary = next(
            item for item in cycle["agenda_decision"]["candidate_summaries"]
            if item["question_id"] == question_id
        )
        self.assertTrue(summary["active_experiment_path"])
        self.assertEqual(store.load()["cycles"], 21)

    def test_pipeline_cannot_execute_world_or_use_network(self):
        source = (EXPERIMENTS / "action_association_public_pipeline.py").read_text()
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
