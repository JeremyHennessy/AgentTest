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
    "open_object_world_resolved_loop",
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

resolved = sys.modules["open_object_world_resolved_loop"]


class OpenObjectWorldResolvedLoopTests(unittest.TestCase):
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

    def test_falsifying_post_action_evidence_resolves_experiment(self):
        core = self.make_core()
        result = resolved.run_resolved_loop(
            core,
            seed=1,
            checkpoint=400,
        )
        self.assertEqual(result["resolution_status"], "resolved")
        self.assertTrue(result["falsified_hypothesis"])
        self.assertEqual(result["resolved_experiment_status"], "completed")
        self.assertEqual(result["resolved_experiment_readiness"], "resolved")
        self.assertEqual(result["resolved_experiment_outcome"], "falsified")
        self.assertTrue(result["resolution_matches_observation"])
        self.assertEqual(
            result["resolution_evidence_refs"],
            [result["outcome_evidence_ref"]],
        )
        self.assertEqual(core.store.load()["cycles"], 20)

    def test_supporting_post_action_evidence_resolves_supported(self):
        core = self.make_core()
        result = resolved.run_resolved_loop(
            core,
            seed=1,
            checkpoint=600,
        )
        self.assertEqual(result["resolution_status"], "resolved")
        self.assertFalse(result["falsified_hypothesis"])
        self.assertEqual(result["resolved_experiment_outcome"], "supported")
        self.assertTrue(result["resolution_matches_observation"])
        self.assertEqual(
            result["resolution_reflection"]["source"],
            "native_inquiry",
        )

    def test_resolved_loop_never_uses_core_action_labs(self):
        source = (
            EXPERIMENTS / "open_object_world_resolved_loop.py"
        ).read_text()
        self.assertNotIn("action_lab=True", source)
        self.assertNotIn("planning_lab=True", source)


if __name__ == "__main__":
    unittest.main()
