from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION
from agenttest.state import StateStore, initial_state


def temporal_evidence(
    *,
    feature: str = "slow_signal",
    confirmations: int = 1,
    refutations: int = 0,
    refs: list[str] | None = None,
):
    evaluable = confirmations + refutations
    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": "same_next_observation",
            "feature": feature,
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": refs or ["obs-1", "obs-2"],
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": evaluable,
            "confirmations": confirmations,
            "refutations": refutations,
        },
    }


def temporal_candidate(evidence_ref: str):
    return {
        "version": NATIVE_INQUIRY_VERSION,
        "id": "NIC:test:resolution",
        "objective": "information_gain",
        "objective_score": 0.6,
        "relation": {
            "kind": "same_next_observation",
            "feature": "slow_signal",
            "action": None,
            "comparison_status": "not_applicable",
        },
        "question": "What next observation would test whether slow_signal remains stable?",
        "hypothesis": "Observed slow_signal tends to remain stable across consecutive evaluable observations.",
        "method": "Collect one later legitimate slow_signal observation and compare it with the prior value.",
        "falsification": "A later evaluable slow_signal value that differs counts against stability.",
        "predicted_observation": "The next evaluable slow_signal observation matches the prior value.",
        "evidence_refs": [evidence_ref],
    }


def action_evidence(refs: list[str] | None = None):
    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": "action_associated_with_change",
            "feature": "slow_signal",
            "action": "interact",
            "comparison_status": "comparable",
        },
        "observation_refs": refs or ["a1", "a2", "a3", "a4"],
        "measurement_kind": "comparative_action_exposure",
        "measurement": {
            "action_present": {"evaluable": 2, "changed": 2, "same": 0},
            "action_absent": {"evaluable": 2, "changed": 0, "same": 2},
            "observed_change_rate_action_present": 1.0,
            "observed_change_rate_action_absent": 0.0,
            "observed_change_rate_difference": 1.0,
        },
    }


def action_candidate(evidence_ref: str):
    return {
        "version": NATIVE_INQUIRY_VERSION,
        "id": "NIC:test:association-resolution",
        "objective": "information_gain",
        "objective_score": 0.7,
        "relation": {
            "kind": "action_associated_with_change",
            "feature": "slow_signal",
            "action": "interact",
            "comparison_status": "comparable",
        },
        "question": "What next comparable observation would test whether interact remains associated with a different slow_signal change rate?",
        "hypothesis": "Observed interact is associated with a different slow_signal change rate than observations without interact.",
        "method": "Collect another comparable action-present and action-absent transition.",
        "falsification": "Comparable evidence that removes the observed rate difference counts against the association.",
        "predicted_observation": "Comparable exposure groups preserve a material slow_signal change-rate difference.",
        "evidence_refs": [evidence_ref],
    }


class NativeInquiryResolutionTests(unittest.TestCase):
    def make_core(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 7
        state["generation"] = 7
        store.save(state)
        return AgentCore(store)

    def stage_temporal(self, core: AgentCore):
        grounding = core.record_native_evidence(
            temporal_evidence(),
            enabled=True,
            persist=True,
        )
        inquiry = core.propose_native_inquiry(
            temporal_candidate(grounding["evidence_ref"]),
            enabled=True,
            persist=True,
        )
        return inquiry["experiment"]["id"]

    def record_outcome(
        self,
        core: AgentCore,
        *,
        confirmations: int,
        refutations: int,
        feature: str = "slow_signal",
        refs: list[str] | None = None,
    ):
        return core.record_native_evidence(
            temporal_evidence(
                feature=feature,
                confirmations=confirmations,
                refutations=refutations,
                refs=refs or ["obs-2", "obs-3"],
            ),
            enabled=True,
            persist=True,
        )

    def test_resolver_is_disabled_by_default(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        outcome = self.record_outcome(core, confirmations=1, refutations=0)
        before = core.store.load()
        with self.assertRaises(RuntimeError):
            core.resolve_native_inquiry(
                experiment_id,
                outcome["evidence_ref"],
            )
        self.assertEqual(core.store.load(), before)

    def test_nonpersisting_resolution_changes_only_returned_copy(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        outcome = self.record_outcome(core, confirmations=1, refutations=0)
        before = core.store.load()
        result = core.resolve_native_inquiry(
            experiment_id,
            outcome["evidence_ref"],
            enabled=True,
        )
        self.assertFalse(result["persisted"])
        self.assertEqual(result["experiment"]["status"], "completed")
        self.assertEqual(result["experiment"]["outcome"], "supported")
        self.assertEqual(core.store.load(), before)

    def test_persisted_confirmation_resolves_without_advancing_cycle(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        outcome = self.record_outcome(core, confirmations=1, refutations=0)
        result = core.resolve_native_inquiry(
            experiment_id,
            outcome["evidence_ref"],
            enabled=True,
            persist=True,
            _now_override="2026-10-05T00:00:00+00:00",
        )
        after = core.store.load()
        experiment = next(
            item for item in after["experiments"]
            if item["id"] == experiment_id
        )
        self.assertTrue(result["resolved"])
        self.assertEqual(after["cycles"], 7)
        self.assertEqual(experiment["status"], "completed")
        self.assertEqual(experiment["readiness"], "resolved")
        self.assertEqual(experiment["outcome"], "supported")
        self.assertEqual(experiment["evidence_refs"], [outcome["evidence_ref"]])
        self.assertEqual(
            experiment["completion_source"],
            "native_evidence_contract",
        )
        self.assertEqual(result["reflection"]["source"], "native_inquiry")

    def test_persisted_refutation_resolves_as_falsified(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        outcome = self.record_outcome(core, confirmations=0, refutations=1)
        result = core.resolve_native_inquiry(
            experiment_id,
            outcome["evidence_ref"],
            enabled=True,
            persist=True,
        )
        self.assertEqual(result["experiment"]["outcome"], "falsified")
        self.assertIn("falsified", result["reflection"]["lesson"])

    def test_mismatched_relation_fails_without_state_change(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        outcome = self.record_outcome(
            core,
            confirmations=1,
            refutations=0,
            feature="other_signal",
        )
        before = core.store.load()
        with self.assertRaises(ValueError):
            core.resolve_native_inquiry(
                experiment_id,
                outcome["evidence_ref"],
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)

    def test_aggregate_or_mixed_temporal_evidence_cannot_resolve_single_next_observation(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        outcome = self.record_outcome(core, confirmations=1, refutations=1)
        before = core.store.load()
        with self.assertRaises(ValueError):
            core.resolve_native_inquiry(
                experiment_id,
                outcome["evidence_ref"],
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)

    def test_action_association_evidence_is_not_resolved_by_temporal_resolver(self):
        core = self.make_core()
        grounding = core.record_native_evidence(
            action_evidence(),
            enabled=True,
            persist=True,
        )
        inquiry = core.propose_native_inquiry(
            action_candidate(grounding["evidence_ref"]),
            enabled=True,
            persist=True,
        )
        outcome = core.record_native_evidence(
            action_evidence(["b1", "b2", "b3", "b4"]),
            enabled=True,
            persist=True,
        )
        before = core.store.load()
        with self.assertRaises(ValueError):
            core.resolve_native_inquiry(
                inquiry["experiment"]["id"],
                outcome["evidence_ref"],
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)

    def test_native_inquiry_records_resolution_evidence_floor(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        state = core.store.load()
        experiment = next(
            item for item in state["experiments"]
            if item["id"] == experiment_id
        )
        self.assertEqual(
            experiment["native_inquiry"]["resolution_evidence_floor_episode_count"],
            len(state["episodes"]),
        )

    def test_grounding_evidence_cannot_resolve_native_inquiry(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        state = core.store.load()
        experiment = next(
            item for item in state["experiments"]
            if item["id"] == experiment_id
        )
        grounding_ref = experiment["native_inquiry"]["evidence_refs"][0]
        before = core.store.load()
        with self.assertRaisesRegex(ValueError, "predates the inquiry"):
            core.resolve_native_inquiry(
                experiment_id,
                grounding_ref,
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)

    def test_matching_evidence_recorded_before_inquiry_cannot_resolve(self):
        core = self.make_core()
        grounding = core.record_native_evidence(
            temporal_evidence(refs=["obs-0", "obs-1"]),
            enabled=True,
            persist=True,
        )
        stale = core.record_native_evidence(
            temporal_evidence(refs=["obs-1", "obs-2"]),
            enabled=True,
            persist=True,
        )
        inquiry = core.propose_native_inquiry(
            temporal_candidate(grounding["evidence_ref"]),
            enabled=True,
            persist=True,
        )
        before = core.store.load()
        with self.assertRaisesRegex(ValueError, "predates the inquiry"):
            core.resolve_native_inquiry(
                inquiry["experiment"]["id"],
                stale["evidence_ref"],
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)

    def test_later_duplicate_grounding_observations_cannot_resolve(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        duplicate = self.record_outcome(
            core,
            confirmations=1,
            refutations=0,
            refs=["obs-1", "obs-2"],
        )
        before = core.store.load()
        with self.assertRaisesRegex(ValueError, "no post-inquiry observation"):
            core.resolve_native_inquiry(
                experiment_id,
                duplicate["evidence_ref"],
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)

    def test_missing_resolution_evidence_floor_fails_closed(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        state = core.store.load()
        experiment = next(
            item for item in state["experiments"]
            if item["id"] == experiment_id
        )
        del experiment["native_inquiry"]["resolution_evidence_floor_episode_count"]
        core.store.save(state)
        outcome = self.record_outcome(core, confirmations=1, refutations=0)
        before = core.store.load()
        with self.assertRaisesRegex(ValueError, "evidence floor is unavailable"):
            core.resolve_native_inquiry(
                experiment_id,
                outcome["evidence_ref"],
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)

    def test_completed_experiment_cannot_be_resolved_twice(self):
        core = self.make_core()
        experiment_id = self.stage_temporal(core)
        outcome = self.record_outcome(core, confirmations=1, refutations=0)
        core.resolve_native_inquiry(
            experiment_id,
            outcome["evidence_ref"],
            enabled=True,
            persist=True,
        )
        before = core.store.load()
        with self.assertRaises(ValueError):
            core.resolve_native_inquiry(
                experiment_id,
                outcome["evidence_ref"],
                enabled=True,
                persist=True,
            )
        self.assertEqual(core.store.load(), before)


if __name__ == "__main__":
    unittest.main()
