from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.native_evidence import (
    NATIVE_EVIDENCE_VERSION,
    NATIVE_EVIDENCE_V2_VERSION,
)
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION
from agenttest.state import StateStore, initial_state


def temporal_evidence():
    return {
        "version": NATIVE_EVIDENCE_VERSION,
        "relation": {
            "kind": "same_next_observation",
            "feature": "slow_signal",
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": ["obs-1", "obs-2", "obs-3"],
        "evaluable": 2,
        "confirmations": 1,
        "refutations": 1,
        "action_present": None,
        "action_absent": None,
    }


def association_evidence():
    return {
        "version": NATIVE_EVIDENCE_VERSION,
        "relation": {
            "kind": "action_associated_with_change",
            "feature": "slow_signal",
            "action": "interact",
            "comparison_status": "comparable",
        },
        "observation_refs": ["obs-a", "obs-b", "obs-c", "obs-d", "obs-e"],
        "evaluable": 4,
        "confirmations": 2,
        "refutations": 2,
        "action_present": {"evaluable": 2, "changed": 2, "same": 0},
        "action_absent": {"evaluable": 2, "changed": 0, "same": 2},
    }


def candidate(evidence_ref):
    return {
        "version": NATIVE_INQUIRY_VERSION,
        "id": "NIC:test:public-path",
        "objective": "information_gain",
        "objective_score": 0.7,
        "relation": {
            "kind": "same_next_observation",
            "feature": "slow_signal",
            "action": None,
            "comparison_status": "not_applicable",
        },
        "question": "What next observation would most directly test whether slow_signal remains stable?",
        "hypothesis": "Observed slow_signal tends to remain stable across consecutive evaluable observations.",
        "method": "Collect another legitimate slow_signal observation and compare it with the prior measured value.",
        "falsification": "A later evaluable slow_signal value that differs counts against stability.",
        "predicted_observation": "The next evaluable slow_signal reading matches the prior reading.",
        "evidence_refs": [evidence_ref],
    }


def association_evidence_v2():
    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": "action_associated_with_change",
            "feature": "slow_signal",
            "action": "interact",
            "comparison_status": "comparable",
        },
        "observation_refs": ["obs-a", "obs-b", "obs-c", "obs-d", "obs-e"],
        "measurement_kind": "comparative_action_exposure",
        "measurement": {
            "action_present": {"evaluable": 2, "changed": 2, "same": 0},
            "action_absent": {"evaluable": 2, "changed": 0, "same": 2},
            "observed_change_rate_action_present": 1.0,
            "observed_change_rate_action_absent": 0.0,
            "observed_change_rate_difference": 1.0,
        },
    }


def association_candidate_v2(evidence_ref):
    return {
        "version": NATIVE_INQUIRY_VERSION,
        "id": "NIC:test:association-v2",
        "objective": "information_gain",
        "objective_score": 0.65,
        "relation": {
            "kind": "action_associated_with_change",
            "feature": "slow_signal",
            "action": "interact",
            "comparison_status": "comparable",
        },
        "question": "What next comparable observation would test whether interact is associated with a different slow_signal change rate?",
        "hypothesis": "Observed interact is associated with a different subsequent slow_signal change rate than observations without interact.",
        "method": "Collect additional comparable action-present and action-absent slow_signal transitions.",
        "falsification": "Additional comparable observations reduce the observed change-rate difference toward zero.",
        "predicted_observation": "Comparable exposure groups provide another slow_signal change-rate comparison.",
        "evidence_refs": [evidence_ref],
    }


class NativeEvidenceInterfaceTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 4
        state["generation"] = 4
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return store

    def test_evidence_interface_is_disabled_and_nonpersisting_by_default(self):
        store = self.make_store()
        before = store.load()
        with self.assertRaises(RuntimeError):
            AgentCore(store).record_native_evidence(temporal_evidence())
        self.assertEqual(store.load(), before)

    def test_nonpersisting_record_returns_evidence_ref_without_store_change(self):
        store = self.make_store()
        before = store.load()
        result = AgentCore(store).record_native_evidence(
            temporal_evidence(),
            enabled=True,
            _now_override="2026-10-04T00:00:00+00:00",
        )
        self.assertFalse(result["persisted"])
        self.assertEqual(result["evidence_ref"], "E000001")
        self.assertEqual(result["episode"]["kind"], "native_inquiry_evidence")
        self.assertEqual(store.load(), before)

    def test_persisted_evidence_survives_reload_without_advancing_cycle(self):
        store = self.make_store()
        before = store.load()
        result = AgentCore(store).record_native_evidence(
            temporal_evidence(),
            enabled=True,
            persist=True,
            _now_override="2026-10-04T00:00:00+00:00",
        )
        after = store.load()
        self.assertEqual(after["cycles"], before["cycles"])
        self.assertEqual(result["evidence_ref"], after["episodes"][-1]["id"])
        payload = json.loads(after["episodes"][-1]["content"])
        self.assertEqual(payload["evaluable"], 2)
        self.assertEqual(payload["relation"]["kind"], "same_next_observation")

    def test_invalid_partition_is_rejected_before_store_change(self):
        store = self.make_store()
        before = store.load()
        evidence = temporal_evidence()
        evidence["confirmations"] = 2
        with self.assertRaises(ValueError):
            AgentCore(store).record_native_evidence(
                evidence,
                enabled=True,
                persist=True,
            )
        self.assertEqual(store.load(), before)

    def test_v1_action_association_is_rejected_in_favor_of_v2(self):
        store = self.make_store()
        with self.assertRaisesRegex(ValueError, "use v2"):
            AgentCore(store).record_native_evidence(
                association_evidence(),
                enabled=True,
                persist=True,
            )

    def test_v2_action_association_requires_both_exposure_groups(self):
        store = self.make_store()
        evidence = association_evidence_v2()
        evidence["measurement"]["action_absent"] = {
            "evaluable": 0,
            "changed": 0,
            "same": 0,
        }
        with self.assertRaises(ValueError):
            AgentCore(store).record_native_evidence(
                evidence,
                enabled=True,
                persist=True,
            )

    def test_inquiry_relation_must_match_persisted_normalized_evidence(self):
        store = self.make_store()
        core = AgentCore(store)
        evidence_result = core.record_native_evidence(
            temporal_evidence(),
            enabled=True,
            persist=True,
            _now_override="2026-10-04T00:00:00+00:00",
        )
        mismatched = candidate(evidence_result["evidence_ref"])
        mismatched["relation"]["kind"] = "changes_next_observation"
        with self.assertRaises(ValueError):
            core.propose_native_inquiry(
                mismatched,
                enabled=True,
                persist=True,
            )

    def test_v2_comparative_association_records_without_fake_truth_labels(self):
        store = self.make_store()
        result = AgentCore(store).record_native_evidence(
            association_evidence_v2(),
            enabled=True,
            persist=True,
            _now_override="2026-10-04T00:00:00+00:00",
        )
        payload = json.loads(result["episode"]["content"])
        self.assertEqual(payload["version"], NATIVE_EVIDENCE_V2_VERSION)
        self.assertEqual(payload["measurement_kind"], "comparative_action_exposure")
        rendered = json.dumps(payload, sort_keys=True)
        self.assertNotIn("confirmations", rendered)
        self.assertNotIn("refutations", rendered)
        self.assertEqual(
            payload["measurement"]["observed_change_rate_difference"],
            1.0,
        )

    def test_v2_comparative_association_can_ground_matching_public_inquiry(self):
        store = self.make_store()
        core = AgentCore(store)
        evidence = core.record_native_evidence(
            association_evidence_v2(),
            enabled=True,
            persist=True,
            _now_override="2026-10-04T00:00:00+00:00",
        )
        inquiry = core.propose_native_inquiry(
            association_candidate_v2(evidence["evidence_ref"]),
            enabled=True,
            persist=True,
        )
        self.assertEqual(
            inquiry["candidate"]["relation"]["kind"],
            "action_associated_with_change",
        )
        self.assertEqual(
            inquiry["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertNotIn(
            " causes ",
            json.dumps(inquiry["experiment"], sort_keys=True).lower(),
        )

    def test_v2_rejects_inconsistent_derived_change_rates(self):
        store = self.make_store()
        evidence = association_evidence_v2()
        evidence["measurement"]["observed_change_rate_difference"] = 0.5
        with self.assertRaises(ValueError):
            AgentCore(store).record_native_evidence(
                evidence,
                enabled=True,
                persist=True,
            )

    def test_full_public_path_evidence_to_inquiry_to_agenda_reload(self):
        store = self.make_store()
        core = AgentCore(store)
        evidence_result = core.record_native_evidence(
            temporal_evidence(),
            enabled=True,
            persist=True,
            _now_override="2026-10-04T00:00:00+00:00",
        )
        inquiry_result = core.propose_native_inquiry(
            candidate(evidence_result["evidence_ref"]),
            enabled=True,
            persist=True,
        )
        native_question_id = inquiry_result["question"]["id"]
        staged = store.load()
        self.assertEqual(staged["cycles"], 4)
        self.assertEqual(
            inquiry_result["experiment"]["specification"]["actionability"],
            "actionable",
        )
        normal_cycle = AgentCore(store).cycle(
            stimulus="continue ordinary operation",
            _now_override="2026-10-04T00:01:00+00:00",
        )
        after = store.load()
        self.assertEqual(after["cycles"], 5)
        self.assertIsNotNone(normal_cycle["agenda_decision"])
        summaries = normal_cycle["agenda_decision"]["candidate_summaries"]
        native = next(
            item for item in summaries if item["question_id"] == native_question_id
        )
        self.assertTrue(native["active_experiment_path"])
        experiment = next(
            item for item in after["experiments"]
            if item.get("native_inquiry_candidate_id") == "NIC:test:public-path"
        )
        self.assertEqual(
            experiment["specification"]["actionability"],
            "actionable",
        )


if __name__ == "__main__":
    unittest.main()
