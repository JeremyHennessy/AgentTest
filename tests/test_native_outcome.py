from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state


RELATION = {
    "kind": "same_next_observation",
    "feature": "entity.M001.state",
    "action": None,
    "comparison_status": "not_applicable",
}


class NativeOutcomeTests(unittest.TestCase):
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

    def stage(self, core):
        initial_evidence = core.record_native_evidence(
            {
                "version": "native-inquiry-evidence-v2",
                "relation": RELATION,
                "observation_refs": ["ow-000001", "ow-000002"],
                "measurement_kind": "binary_transition_outcomes",
                "measurement": {
                    "evaluable": 2,
                    "confirmations": 1,
                    "refutations": 1,
                },
            },
            enabled=True,
            persist=True,
            _now_override="2026-10-05T00:00:00+00:00",
        )
        inquiry = core.propose_native_inquiry(
            {
                "version": "native-inquiry-v1",
                "id": "NIC:test:state",
                "objective": "information_gain",
                "objective_score": 0.5,
                "relation": RELATION,
                "question": "Will the visible state remain stable?",
                "hypothesis": "The visible state remains stable.",
                "method": "Observe the visible state again.",
                "falsification": "A changed visible state counts against it.",
                "predicted_observation": "The visible state matches.",
                "evidence_refs": [initial_evidence["evidence_ref"]],
            },
            enabled=True,
            persist=True,
        )
        return inquiry["experiment"]["id"]

    def outcome_evidence(self, core, *, confirmations, refutations, relation=None):
        return core.record_native_evidence(
            {
                "version": "native-inquiry-evidence-v2",
                "relation": relation or RELATION,
                "observation_refs": ["ow-000010", "ow-000011"],
                "measurement_kind": "binary_transition_outcomes",
                "measurement": {
                    "evaluable": confirmations + refutations,
                    "confirmations": confirmations,
                    "refutations": refutations,
                },
            },
            enabled=True,
            persist=True,
            _now_override="2026-10-05T00:01:00+00:00",
        )

    def test_disabled_by_default(self):
        core = self.make_core()
        experiment_id = self.stage(core)
        evidence = self.outcome_evidence(core, confirmations=1, refutations=0)
        with self.assertRaises(RuntimeError):
            core.resolve_native_inquiry_outcome(
                experiment_id,
                evidence["evidence_ref"],
            )

    def test_matching_confirmations_resolve_supported(self):
        core = self.make_core()
        experiment_id = self.stage(core)
        evidence = self.outcome_evidence(core, confirmations=1, refutations=0)
        result = core.resolve_native_inquiry_outcome(
            experiment_id,
            evidence["evidence_ref"],
            enabled=True,
            persist=True,
            _now_override="2026-10-05T00:02:00+00:00",
        )
        self.assertEqual(result["resolution"]["outcome"], "supported")
        experiment = next(
            item for item in core.store.load()["experiments"]
            if item["id"] == experiment_id
        )
        self.assertEqual(experiment["status"], "completed")
        self.assertEqual(experiment["readiness"], "resolved")
        self.assertEqual(
            experiment["completion_source"],
            "native_inquiry_evidence_contract",
        )

    def test_matching_refutation_resolves_falsified(self):
        core = self.make_core()
        experiment_id = self.stage(core)
        evidence = self.outcome_evidence(core, confirmations=0, refutations=1)
        result = core.resolve_native_inquiry_outcome(
            experiment_id,
            evidence["evidence_ref"],
            enabled=True,
            persist=False,
        )
        self.assertEqual(result["resolution"]["outcome"], "falsified")
        persisted = next(
            item for item in core.store.load()["experiments"]
            if item["id"] == experiment_id
        )
        self.assertEqual(persisted["status"], "proposed")

    def test_mixed_evidence_does_not_resolve(self):
        core = self.make_core()
        experiment_id = self.stage(core)
        evidence = self.outcome_evidence(core, confirmations=1, refutations=1)
        with self.assertRaisesRegex(ValueError, "mixed"):
            core.resolve_native_inquiry_outcome(
                experiment_id,
                evidence["evidence_ref"],
                enabled=True,
            )

    def test_relation_mismatch_is_rejected(self):
        core = self.make_core()
        experiment_id = self.stage(core)
        mismatch = dict(RELATION)
        mismatch["feature"] = "position"
        evidence = self.outcome_evidence(
            core,
            confirmations=1,
            refutations=0,
            relation=mismatch,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            core.resolve_native_inquiry_outcome(
                experiment_id,
                evidence["evidence_ref"],
                enabled=True,
            )

    def test_non_native_episode_is_rejected(self):
        core = self.make_core()
        experiment_id = self.stage(core)
        state = core.store.load()
        state["episodes"].append(
            {
                "id": "E999999",
                "cycle": 20,
                "time": "2026-10-05T00:01:00+00:00",
                "kind": "stimulus",
                "content": "not native evidence",
                "concepts": [],
            }
        )
        core.store.save(state)
        with self.assertRaisesRegex(ValueError, "not native"):
            core.resolve_native_inquiry_outcome(
                experiment_id,
                "E999999",
                enabled=True,
            )

    def test_completed_native_experiment_cannot_be_resolved_twice(self):
        core = self.make_core()
        experiment_id = self.stage(core)
        evidence = self.outcome_evidence(core, confirmations=1, refutations=0)
        core.resolve_native_inquiry_outcome(
            experiment_id,
            evidence["evidence_ref"],
            enabled=True,
            persist=True,
        )
        with self.assertRaisesRegex(ValueError, "already completed"):
            core.resolve_native_inquiry_outcome(
                experiment_id,
                evidence["evidence_ref"],
                enabled=True,
            )


if __name__ == "__main__":
    unittest.main()
