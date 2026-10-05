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


class OpenObjectWorldCopiedLoopResolutionTests(unittest.TestCase):
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

    def test_falsifying_world_outcome_resolves_native_experiment(self):
        core = self.make_core()
        result = loop.run_mature_copied_loop(
            core,
            seed=1,
            checkpoint=400,
        )
        self.assertTrue(result["falsified_hypothesis"])
        resolution = core.resolve_native_inquiry_outcome(
            result["experiment_id"],
            result["outcome_evidence_ref"],
            enabled=True,
            persist=True,
        )
        self.assertEqual(resolution["resolution"]["outcome"], "falsified")
        experiment = next(
            item for item in core.store.load()["experiments"]
            if item["id"] == result["experiment_id"]
        )
        self.assertEqual(experiment["status"], "completed")
        self.assertIn(
            result["outcome_evidence_ref"],
            experiment["evidence_refs"],
        )

    def test_resolver_never_executes_world_or_core_action_labs(self):
        import inspect
        source = inspect.getsource(AgentCore.resolve_native_inquiry_outcome)
        self.assertNotIn("step_action_lab", source)
        self.assertNotIn("step_planning_lab", source)
        self.assertNotIn("self.cycle(", source)


if __name__ == "__main__":
    unittest.main()
