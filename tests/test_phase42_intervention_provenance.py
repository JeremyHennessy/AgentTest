from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

from agenttest.agenda import _thread_progress_evidence_refs
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase42_integrity_under_test", ROOT / "scripts" / "phase42_integrity_eval.py"
)
assert SPEC is not None and SPEC.loader is not None
INTEGRITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INTEGRITY)


class Phase42InterventionProvenanceTests(unittest.TestCase):
    """Primary regression uses only normal cycles, sensor inputs and disk reloads.

    The agenda start is capability activation, not an injected evidence trigger.
    No experiments, predictions, reflections or question priorities are seeded.
    Corrupted-ledger tests below are explicit evaluator negative controls only.
    """

    def _run_prediction_case(self, *, intervention=False, violation=False):
        observation = {
            "branch": "autonomous/growth",
            "baseline_fingerprint": "baseline-a",
            "tracked_files": 100,
            "python_files": 20,
            "python_source_lines": 5000,
            "test_files": 12,
            "working_tree_clean": True,
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "organism.json"
            initial = initial_state()
            initial["agenda"]["started_cycle"] = 0
            StateStore(path).save(initial)
            # Build primary empirical history through the same cycle options as
            # growth.yml. Recreate both store and core on every heartbeat.
            for _ in range(12):
                event = AgentCore(StateStore(path)).cycle(
                    observation=dict(observation),
                    stimulus="autonomous heartbeat",
                    strict_experiment_admission=True,
                    planning_lab=True,
                )
            before = StateStore(path).load()
            prediction_id = event["prediction"]["id"]
            experiment_id = event["prediction_experiment"]["id"]
            question_id = event["prediction_experiment"]["question_id"]
            self.assertIsNotNone(event["agenda_decision"])
            self.assertEqual(event["prediction"]["status"], "pending")
            self.assertEqual(event["prediction_experiment"]["status"], "proposed")
            self.assertFalse(before["cognition_events"])

            next_observation = dict(observation)
            if intervention:
                next_observation["baseline_fingerprint"] = "baseline-b"
            if violation:
                next_observation["test_files"] += 1
            event = AgentCore(StateStore(path)).cycle(
                observation=next_observation,
                stimulus="autonomous heartbeat",
                strict_experiment_admission=True,
                planning_lab=True,
            )
            after = StateStore(path).load()
            completed = next(
                item for item in after["experiments"] if item["id"] == experiment_id
            )
            reflection = next(
                item for item in after["reflections"]
                if item.get("prediction_id") == prediction_id
            )
            candidate = next(
                item for item in event["agenda_decision"]["candidate_summaries"]
                if item["question_id"] == question_id
            )
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(after["agenda"]["decisions"][-1], event["agenda_decision"])
            # Verify one more full reload, not only a returned event dictionary.
            StateStore(path).save(after)
            self.assertEqual(StateStore(path).load()["agenda"], after["agenda"])
            refs = {experiment_id, prediction_id, reflection["id"]}
            return after, candidate, completed, refs

    def test_intervention_invalidated_completion_is_history_not_thread_progress(self):
        after, candidate, completed, refs = self._run_prediction_case(intervention=True)
        self.assertEqual(completed["observed_prediction_status"], "invalidated_by_intervention")
        self.assertEqual(completed["outcome"], "inconclusive")
        self.assertEqual(
            completed["completion_source"], "prediction_contract_invalidated_by_intervention"
        )
        self.assertTrue(refs.isdisjoint(candidate["thread_progress_evidence_refs"]), candidate)
        self.assertTrue(refs.isdisjoint(candidate["new_evidence_refs"]), candidate)
        self.assertEqual(candidate["evidence_change_value"], 0.0)
        self.assertFalse(after["agenda"]["decisions"][-1]["priority_change_supported_by_new_evidence"])
        # Exclusion must not erase the original historical records.
        history_ids = {
            item["id"] for key in ("experiments", "predictions", "reflections")
            for item in after[key]
        }
        self.assertTrue(refs <= history_ids)
        self.assertTrue(INTEGRITY.evaluate(after)["ok"])

    def test_confirmed_and_violated_predictions_still_produce_progress(self):
        for violation, expected in ((False, "confirmed"), (True, "violated")):
            with self.subTest(expected=expected):
                after, candidate, completed, refs = self._run_prediction_case(violation=violation)
                self.assertEqual(completed["observed_prediction_status"], expected)
                self.assertTrue(refs <= set(candidate["thread_progress_evidence_refs"]))
                self.assertTrue(refs <= set(candidate["new_evidence_refs"]))
                self.assertGreater(candidate["evidence_change_value"], 0.0)
                self.assertTrue(INTEGRITY.evaluate(after)["ok"])

    def test_integrity_independently_rejects_invalidated_refs_in_any_candidate(self):
        after, candidate, completed, refs = self._run_prediction_case(intervention=True)
        for surface in ("selected", "candidate_summaries"):
            with self.subTest(surface=surface):
                corrupted = copy.deepcopy(after)
                latest = corrupted["agenda"]["decisions"][-1]
                bad = copy.deepcopy(candidate)
                bad["thread_progress_evidence_refs"] = sorted(refs)
                bad["new_evidence_refs"] = sorted(refs)
                if surface == "selected":
                    latest["selected"] = bad
                else:
                    latest["candidate_summaries"] = [bad]
                result = INTEGRITY.evaluate(corrupted)
                self.assertFalse(result["ok"], result)
                self.assertTrue(any(
                    item["kind"] == "intervention_invalidated_thread_progress"
                    for item in result["failures"]
                ), result)

    def test_non_intervention_inconclusive_evidence_is_not_blanket_excluded(self):
        # Local classification positive control, not natural capability proof.
        state = initial_state()
        question = {"id": "Q_CONTROL"}
        state["experiments"] = [{
            "id": "X_CONTROL", "question_id": question["id"],
            "status": "completed", "outcome": "inconclusive",
            "completion_source": "bounded_observation",
            "evidence_refs": ["E_CONTROL"],
        }]
        state["reflections"] = [{
            "id": "R_CONTROL", "experiment_id": "X_CONTROL",
            "outcome": "inconclusive",
        }]
        self.assertEqual(
            set(_thread_progress_evidence_refs(state, question)),
            {"X_CONTROL", "E_CONTROL", "R_CONTROL"},
        )


if __name__ == "__main__":
    unittest.main()
