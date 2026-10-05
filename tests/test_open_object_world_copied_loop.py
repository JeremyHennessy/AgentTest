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
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(EXPERIMENTS))
sys.path.insert(0, str(SCRIPTS))

for name in (
    "open_object_world",
    "open_object_world_explorer",
    "normalized_inquiry_objectives",
    "open_object_world_native_bridge",
    "open_object_world_action_association",
    "open_object_world_epistemic_actions",
    "open_object_world_epistemic_action_study",
    "open_object_world_copied_loop",
):
    location = (
        SCRIPTS / f"{name}.py"
        if name == "open_object_world_epistemic_action_study"
        else EXPERIMENTS / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(name, location)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

loop = sys.modules["open_object_world_copied_loop"]


class OpenObjectWorldCopiedLoopTests(unittest.TestCase):
    def make_core(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return AgentCore(store)

    def test_mature_case_stages_question_executes_isolated_action_and_records_outcome(self):
        core = self.make_core()
        result = loop.run_mature_copied_loop(
            core,
            seed=1,
            checkpoint=400,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["epistemic_selection"]["mode"],
            "seek_disconfirming_observation",
        )
        self.assertTrue(result["evaluable"])
        self.assertIsNotNone(result["outcome_evidence_ref"])
        state = core.store.load()
        evidence = next(
            item
            for item in state["episodes"]
            if item["id"] == result["outcome_evidence_ref"]
        )
        self.assertEqual(evidence["kind"], "native_inquiry_evidence")
        self.assertEqual(state["cycles"], 20)

    def test_current_core_does_not_falsely_auto_resolve_native_outcome(self):
        core = self.make_core()
        result = loop.run_mature_copied_loop(
            core,
            seed=1,
            checkpoint=400,
        )
        self.assertFalse(result["native_outcome_auto_resolved"])
        self.assertEqual(
            result["experiment_status_after_outcome"],
            "proposed",
        )
        self.assertEqual(
            result["experiment_readiness_after_outcome"],
            "awaiting_native_evidence",
        )

    def test_loop_uses_no_core_action_authority(self):
        source = (
            EXPERIMENTS / "open_object_world_copied_loop.py"
        ).read_text()
        self.assertNotIn("action_lab=True", source)
        self.assertNotIn("planning_lab=True", source)
        for forbidden in (
            "_mass",
            'get("_kind")',
            "_latched",
            "reward",
            "solution",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
