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
sys.path.insert(0, str(EXPERIMENTS))

for name in (
    "open_object_world",
    "open_object_world_explorer",
    "normalized_inquiry_objectives",
    "open_object_world_native_bridge",
):
    spec = importlib.util.spec_from_file_location(
        name, EXPERIMENTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

bridge = sys.modules["open_object_world_native_bridge"]


class OpenObjectWorldNativeBridgeTests(unittest.TestCase):
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

    def test_public_features_contain_no_hidden_world_properties(self):
        trace = bridge.collect_trace(seed=1, steps=4)
        features = bridge.public_features(trace["observations"][0])
        rendered = repr(features)
        for forbidden in (
            "_kind",
            "_mass",
            "_carryable",
            "_movable",
            "_latched",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_selected_candidate_is_temporal_and_public(self):
        trace = bridge.collect_trace(seed=1, steps=80)
        selected = bridge.choose_information_gain_candidate(
            trace["observations"][:41]
        )
        candidate = selected["candidate"]
        self.assertIn(
            candidate["relation"],
            {"same_next_observation", "changes_next_observation"},
        )
        self.assertIsNone(candidate["action"])
        self.assertNotIn("_", candidate["feature"][:1])

    def test_grounded_question_reaches_real_copied_core(self):
        trace = bridge.collect_trace(seed=1, steps=120)
        prefix = trace["observations"][:61]
        selected = bridge.choose_information_gain_candidate(prefix)
        store = self.make_store()
        staged = bridge.stage_in_copied_core(
            AgentCore(store),
            selected,
            prefix,
        )
        inquiry = staged["inquiry_result"]
        self.assertTrue(inquiry["persisted"])
        self.assertEqual(inquiry["question"]["source"], "native_inquiry")
        self.assertEqual(
            inquiry["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertEqual(store.load()["cycles"], 10)

    def test_next_ordinary_cycle_keeps_question_in_agenda_without_world_action(self):
        trace = bridge.collect_trace(seed=1, steps=120)
        prefix = trace["observations"][:61]
        selected = bridge.choose_information_gain_candidate(prefix)
        store = self.make_store()
        core = AgentCore(store)
        staged = bridge.stage_in_copied_core(core, selected, prefix)
        question_id = staged["inquiry_result"]["question"]["id"]
        result = core.cycle(
            stimulus="continue ordinary operation",
            _now_override="2026-10-05T00:00:00+00:00",
        )
        self.assertIsNone(result["action_lab_result"])
        self.assertIsNone(result["planning_lab_result"])
        summaries = result["agenda_decision"]["candidate_summaries"]
        native = next(
            item for item in summaries
            if item["question_id"] == question_id
        )
        self.assertTrue(native["active_experiment_path"])

    def test_held_out_scoring_uses_only_public_feature(self):
        trace = bridge.collect_trace(seed=2, steps=120)
        prefix = trace["observations"][:61]
        held = trace["observations"][60:]
        selected = bridge.choose_information_gain_candidate(prefix)
        result = bridge.held_out_evaluation(
            selected["candidate"],
            held,
        )
        self.assertGreater(result["evaluable"], 0)
        self.assertGreaterEqual(result["support_rate"], 0.0)
        self.assertLessEqual(result["support_rate"], 1.0)

    def test_bridge_does_not_execute_world_actions_itself(self):
        source = (
            EXPERIMENTS / "open_object_world_native_bridge.py"
        ).read_text()
        self.assertNotIn("action_lab=True", source)
        self.assertNotIn("planning_lab=True", source)
        self.assertNotIn("_mass", source)
        self.assertNotIn('get("_kind")', source)
        self.assertNotIn("['_kind']", source)
        self.assertNotIn('["_kind"]', source)


if __name__ == "__main__":
    unittest.main()
