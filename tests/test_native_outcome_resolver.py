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


def evidence(confirmations=1, refutations=0):
    return {
        "version": "native-inquiry-evidence-v2",
        "relation": dict(RELATION),
        "observation_refs": ["OW-1", "OW-2"],
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": confirmations + refutations,
            "confirmations": confirmations,
            "refutations": refutations,
        },
    }


class NativeOutcomeResolverTests(unittest.TestCase):
    def make_core(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 42
        state["generation"] = 42
        state["experiments"].append(
            {
                "id": "X900001",
                "cycle": 42,
                "question_id": "Q900001",
                "status": "proposed",
                "readiness": "awaiting_native_evidence",
                "native_inquiry": {
                    "relation": dict(RELATION),
                },
                "status_history": [],
            }
        )
        store.save(state)
        return AgentCore(store)

    def test_disabled_by_default(self):
        with self.assertRaises(RuntimeError):
            self.make_core().resolve_native_inquiry_outcome(evidence())

    def test_supported_exact_match_resolves_on_copy_without_persisting(self):
        core = self.make_core()
        result = core.resolve_native_inquiry_outcome(
            evidence(),
            enabled=True,
            persist=False,
            _now_override="2026-10-05T01:00:00+00:00",
        )
        self.assertEqual(result["outcome"], "supported")
        self.assertEqual(result["resolved_experiment_id"], "X900001")
        resolved = result["state"]["experiments"][-1]
        self.assertEqual(resolved["status"], "completed")
        self.assertEqual(resolved["readiness"], "resolved")
        self.assertEqual(resolved["outcome"], "supported")
        self.assertEqual(core.store.load()["experiments"][-1]["status"], "proposed")
        self.assertEqual(core.store.load()["cycles"], 42)

    def test_refutation_resolves_when_persist_explicitly_enabled(self):
        core = self.make_core()
        result = core.resolve_native_inquiry_outcome(
            evidence(confirmations=0, refutations=1),
            enabled=True,
            persist=True,
        )
        self.assertEqual(result["outcome"], "falsified")
        saved = core.store.load()["experiments"][-1]
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["outcome"], "falsified")
        self.assertEqual(saved["completion_source"], "native_temporal_evidence")

    def test_mixed_evidence_remains_unresolved(self):
        core = self.make_core()
        result = core.resolve_native_inquiry_outcome(
            evidence(confirmations=1, refutations=1),
            enabled=True,
            persist=True,
        )
        self.assertIsNone(result["outcome"])
        self.assertIsNone(result["resolved_experiment_id"])
        self.assertEqual(core.store.load()["experiments"][-1]["status"], "proposed")

    def test_relation_mismatch_does_not_resolve(self):
        core = self.make_core()
        payload = evidence()
        payload["relation"]["feature"] = "position"
        result = core.resolve_native_inquiry_outcome(
            payload,
            enabled=True,
            persist=True,
        )
        self.assertEqual(result["matched_experiment_count"], 0)
        self.assertIsNone(result["resolved_experiment_id"])
        self.assertEqual(core.store.load()["experiments"][-1]["status"], "proposed")

    def test_resolver_has_no_action_authority(self):
        source = Path(__file__).resolve().parents[1].joinpath(
            "src", "agenttest", "core.py"
        ).read_text()
        start = source.index("    def resolve_native_inquiry_outcome(")
        end = source.index("    def propose_native_inquiry(", start)
        resolver = source[start:end]
        self.assertNotIn("step_action_lab", resolver)
        self.assertNotIn("step_planning_lab", resolver)
        self.assertNotIn("state[\"cycles\"] +=", resolver)


if __name__ == "__main__":
    unittest.main()
