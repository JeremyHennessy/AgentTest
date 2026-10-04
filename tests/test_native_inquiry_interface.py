from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION
from agenttest.state import StateStore, initial_state


def seeded_state():
    state = initial_state()
    state["cycles"] = 1
    state["generation"] = 1
    state["agenda"]["started_cycle"] = 0
    state["episodes"].extend(
        [
            {
                "id": "E000001",
                "cycle": 1,
                "time": "2026-10-04T00:00:00+00:00",
                "kind": "native_inquiry_evidence",
                "content": json.dumps(
                    {
                        "version": "native-inquiry-evidence-v1",
                        "relation": {
                            "kind": "same_next_observation",
                            "feature": "slow_signal",
                            "action": None,
                            "comparison_status": "not_applicable",
                        },
                        "observation_refs": ["obs-1", "obs-2"],
                        "evaluable": 1,
                        "confirmations": 1,
                        "refutations": 0,
                        "action_present": None,
                        "action_absent": None,
                    },
                    sort_keys=True,
                ),
                "concepts": ["native", "observation", "evidence"],
            },
            {
                "id": "E000002",
                "cycle": 1,
                "time": "2026-10-04T00:00:00+00:00",
                "kind": "native_inquiry_evidence",
                "content": json.dumps(
                    {
                        "version": "native-inquiry-evidence-v1",
                        "relation": {
                            "kind": "action_associated_with_change",
                            "feature": "slow_signal",
                            "action": "interact",
                            "comparison_status": "comparable",
                        },
                        "observation_refs": ["obs-a", "obs-b", "obs-c"],
                        "evaluable": 2,
                        "confirmations": 1,
                        "refutations": 1,
                        "action_present": {"evaluable": 1, "changed": 1, "same": 0},
                        "action_absent": {"evaluable": 1, "changed": 0, "same": 1},
                    },
                    sort_keys=True,
                ),
                "concepts": ["native", "association", "evidence"],
            },
        ]
    )
    return state


def temporal_candidate():
    return {
        "version": NATIVE_INQUIRY_VERSION,
        "id": "NIC:test:stable-signal",
        "objective": "information_gain",
        "objective_score": 0.62,
        "relation": {
            "kind": "same_next_observation",
            "feature": "slow_signal",
            "action": None,
            "comparison_status": "not_applicable",
        },
        "question": "What next observation would most directly test whether slow_signal remains stable?",
        "hypothesis": "Observed slow_signal tends to remain stable across consecutive evaluable observations.",
        "method": "Collect one later legitimate slow_signal observation and compare it with the prior measured value.",
        "falsification": "A later evaluable slow_signal value that differs counts against stability.",
        "predicted_observation": "The next evaluable slow_signal reading matches the prior reading.",
        "evidence_refs": ["E000001"],
    }


def association_candidate():
    candidate = temporal_candidate()
    candidate["id"] = "NIC:test:association"
    candidate["relation"] = {
        "kind": "action_associated_with_change",
        "feature": "slow_signal",
        "action": "interact",
        "comparison_status": "comparable",
    }
    candidate["question"] = "What next comparable observation would test whether interact is associated with a different slow_signal change rate?"
    candidate["hypothesis"] = "Observed interact is associated with a different subsequent slow_signal change rate than observations without interact."
    candidate["method"] = "Collect additional comparable action-present and action-absent slow_signal transitions."
    candidate["falsification"] = "Additional comparable observations reduce the observed change-rate difference toward zero."
    candidate["predicted_observation"] = "Comparable action-present and action-absent transitions provide another change-rate comparison."
    candidate["evidence_refs"] = ["E000002"]
    return candidate


class NativeInquiryInterfaceTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        store.save(seeded_state())
        return store

    def test_interface_is_disabled_and_nonpersisting_by_default(self):
        store = self.make_store()
        before = store.load()
        core = AgentCore(store)
        with self.assertRaises(RuntimeError):
            core.propose_native_inquiry(temporal_candidate())
        self.assertEqual(store.load(), before)

    def test_enabled_nonpersisting_path_only_changes_returned_copy(self):
        store = self.make_store()
        before = store.load()
        result = AgentCore(store).propose_native_inquiry(
            temporal_candidate(),
            enabled=True,
        )
        self.assertFalse(result["persisted"])
        self.assertEqual(store.load(), before)
        self.assertEqual(result["question"]["source"], "native_inquiry")
        self.assertEqual(
            result["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertEqual(
            result["experiment"]["readiness"],
            "awaiting_native_evidence",
        )

    def test_persisted_native_inquiry_survives_reload_without_advancing_cycle(self):
        store = self.make_store()
        before = store.load()
        result = AgentCore(store).propose_native_inquiry(
            temporal_candidate(),
            enabled=True,
            persist=True,
        )
        after = store.load()
        self.assertTrue(result["persisted"])
        self.assertEqual(after["cycles"], before["cycles"])
        self.assertEqual(
            after["agenda"]["decisions"],
            before["agenda"]["decisions"],
        )
        self.assertEqual(
            after["agenda"]["last_decision_cycle"],
            before["agenda"]["last_decision_cycle"],
        )
        question = next(
            item for item in after["questions"]
            if item.get("native_inquiry_candidate_id") == "NIC:test:stable-signal"
        )
        experiment = next(
            item for item in after["experiments"]
            if item.get("native_inquiry_candidate_id") == "NIC:test:stable-signal"
        )
        self.assertEqual(question["source_evidence_refs"], ["E000001"])
        self.assertEqual(experiment["cognition_candidate_id"], None)
        self.assertEqual(
            experiment["specification"]["evidence_source"],
            {"kind": "native_inquiry_evidence", "refs": ["E000001"]},
        )
        self.assertEqual(
            experiment["specification"]["actionability"],
            "actionable",
        )

    def test_next_normal_cycle_keeps_native_inquiry_actionable_and_agenda_visible(self):
        store = self.make_store()
        core = AgentCore(store)
        staged = core.propose_native_inquiry(
            temporal_candidate(),
            enabled=True,
            persist=True,
        )
        native_question_id = staged["question"]["id"]
        result = core.cycle(stimulus="continue ordinary inquiry")
        after = store.load()
        experiment = next(
            item for item in after["experiments"]
            if item.get("native_inquiry_candidate_id") == "NIC:test:stable-signal"
        )
        self.assertEqual(
            experiment["specification"]["actionability"],
            "actionable",
        )
        decision = result["agenda_decision"]
        self.assertIsNotNone(decision)
        candidate_ids = {
            item["question_id"]
            for item in decision["candidate_summaries"]
        }
        self.assertIn(native_question_id, candidate_ids)
        native_summary = next(
            item for item in decision["candidate_summaries"]
            if item["question_id"] == native_question_id
        )
        self.assertTrue(native_summary["active_experiment_path"])
        self.assertEqual(after["cycles"], 2)

    def test_unknown_evidence_is_rejected_before_any_state_change(self):
        store = self.make_store()
        before = store.load()
        candidate = temporal_candidate()
        candidate["evidence_refs"] = ["UNKNOWN"]
        with self.assertRaises(ValueError):
            AgentCore(store).propose_native_inquiry(
                candidate,
                enabled=True,
                persist=True,
            )
        self.assertEqual(store.load(), before)

    def test_insufficient_action_comparison_cannot_enter_core(self):
        store = self.make_store()
        candidate = association_candidate()
        candidate["relation"]["comparison_status"] = "insufficient_comparison"
        with self.assertRaises(ValueError):
            AgentCore(store).propose_native_inquiry(
                candidate,
                enabled=True,
                persist=True,
            )

    def test_action_association_cannot_overclaim_causation(self):
        store = self.make_store()
        candidate = association_candidate()
        candidate["hypothesis"] = "Interacting causes slow_signal to change."
        with self.assertRaises(ValueError):
            AgentCore(store).propose_native_inquiry(
                candidate,
                enabled=True,
                persist=True,
            )

    def test_valid_comparable_association_is_staged_as_association(self):
        store = self.make_store()
        result = AgentCore(store).propose_native_inquiry(
            association_candidate(),
            enabled=True,
            persist=False,
        )
        self.assertEqual(
            result["candidate"]["relation"]["kind"],
            "action_associated_with_change",
        )
        rendered = json.dumps(result["experiment"], sort_keys=True).lower()
        self.assertNotIn(" causes ", rendered)
        self.assertEqual(
            result["experiment"]["specification"]["actionability"],
            "actionable",
        )


if __name__ == "__main__":
    unittest.main()
