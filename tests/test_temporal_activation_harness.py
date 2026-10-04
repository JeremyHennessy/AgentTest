from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.native_activation import (
    DEFAULT_NATIVE_ACTIVATION_POLICY,
    temporal_activation_policy,
)
from agenttest.state import StateStore, initial_state

from temporal_activation_harness import (
    activate_temporal_inquiry,
    rollback_temporal_activation_state,
)


class TemporalActivationHarnessTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 30
        state["generation"] = 30
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return store

    def test_default_off_policy_cannot_activate(self):
        store = self.make_store()
        before = store.load()
        with self.assertRaises(RuntimeError):
            activate_temporal_inquiry(
                AgentCore(store),
                policy=DEFAULT_NATIVE_ACTIVATION_POLICY,
                relation="same_next_observation",
                feature="slow_signal",
                observation_refs=["o1", "o2"],
                evaluable=1,
                confirmations=1,
                refutations=0,
                objective_score=0.5,
            )
        self.assertEqual(store.load(), before)

    def test_explicit_temporal_policy_stages_public_v2_evidence_and_inquiry(self):
        store = self.make_store()
        result = activate_temporal_inquiry(
            AgentCore(store),
            policy=temporal_activation_policy(),
            relation="same_next_observation",
            feature="slow_signal",
            observation_refs=["o1", "o2", "o3"],
            evaluable=2,
            confirmations=1,
            refutations=1,
            objective_score=0.55,
        )
        evidence = result["evidence_result"]
        inquiry = result["inquiry_result"]
        self.assertEqual(evidence["evidence"]["version"], "native-inquiry-evidence-v2")
        self.assertEqual(evidence["evidence"]["measurement_kind"], "binary_transition_outcomes")
        self.assertEqual(
            evidence["evidence"]["relation"],
            inquiry["candidate"]["relation"],
        )
        self.assertEqual(
            inquiry["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertEqual(store.load()["cycles"], 30)

    def test_next_ordinary_cycle_sees_inquiry_but_action_authority_remains_off(self):
        store = self.make_store()
        core = AgentCore(store)
        staged = activate_temporal_inquiry(
            core,
            policy=temporal_activation_policy(),
            relation="same_next_observation",
            feature="slow_signal",
            observation_refs=["o1", "o2"],
            evaluable=1,
            confirmations=1,
            refutations=0,
            objective_score=0.6,
        )
        question_id = staged["inquiry_result"]["question"]["id"]
        result = core.cycle(
            stimulus="continue ordinary operation",
            _now_override="2026-10-04T00:04:00+00:00",
        )
        self.assertIsNone(result["action_lab_result"])
        self.assertIsNone(result["planning_lab_result"])
        summary = next(
            item for item in result["agenda_decision"]["candidate_summaries"]
            if item["question_id"] == question_id
        )
        self.assertTrue(summary["active_experiment_path"])
        self.assertEqual(store.load()["cycles"], 31)

    def test_rollback_removes_only_staged_native_artifacts_from_copy(self):
        store = self.make_store()
        before = store.load()
        staged = activate_temporal_inquiry(
            AgentCore(store),
            policy=temporal_activation_policy(),
            relation="same_next_observation",
            feature="slow_signal",
            observation_refs=["o1", "o2"],
            evaluable=1,
            confirmations=1,
            refutations=0,
            objective_score=0.6,
        )
        after = store.load()
        candidate_id = staged["inquiry_result"]["candidate"]["id"]
        evidence_ref = staged["evidence_result"]["evidence_ref"]
        rolled = rollback_temporal_activation_state(
            after,
            candidate_id=candidate_id,
            evidence_ref=evidence_ref,
        )
        self.assertEqual(rolled["cycles"], before["cycles"])
        self.assertEqual(rolled["episodes"], before["episodes"])
        self.assertEqual(rolled["questions"], before["questions"])
        self.assertEqual(rolled["experiments"], before["experiments"])
        self.assertEqual(rolled["intentions"], before["intentions"])
        self.assertNotEqual(after, rolled)
        self.assertEqual(store.load(), after)

    def test_harness_cannot_execute_world_or_enable_action_labs(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "experiments" / "temporal_activation_harness.py").read_text()
        for forbidden in (
            "transition_world",
            "action_lab=True",
            "planning_lab=True",
            "subprocess",
            "requests",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
