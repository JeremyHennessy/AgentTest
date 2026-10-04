from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.agenda import update_agenda
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state


class NoNewPredictionEvidenceCore(AgentCore):
    def _evaluate_prediction(self, state, observation, now):
        return None


class Phase42FullCycleResumptionCausalityPositiveControlTests(unittest.TestCase):
    def test_new_evidence_can_cause_resumption_upstream_even_when_score_bonus_is_not_decisive(self) -> None:
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 19
        state["metrics"].update(
            {
                "continuity": 1.0,
                "self_model": 1.0,
                "open_endedness": 1.0,
            }
        )

        resume_question = {
            "id": "Q_RESUME",
            "text": (
                "What observable, evidence source, and resolution rule would make "
                "experiment X_SPEC_1 evidence-ready?"
            ),
            "status": "open",
            "created_cycle": 1,
            "times_selected": 4,
            "last_selected_cycle": 19,
        }
        foreground_question = {
            "id": "Q_FOREGROUND",
            "text": "Which independent foreground inquiry should remain active?",
            "status": "open",
            "created_cycle": 2,
            "times_selected": 1,
            "last_selected_cycle": 18,
            "source": "repository_stability_prediction",
        }
        state["questions"] = [resume_question, foreground_question]

        first = update_agenda(state, legacy_question=resume_question, cycle=20)
        self.assertIsNotNone(first)
        resume_thread_id = first["selected_thread_id"]
        state["cycles"] = 21
        state["generation"] = 21
        second = update_agenda(
            state,
            legacy_question=foreground_question,
            cycle=21,
        )
        self.assertIsNotNone(second)
        self.assertIn(resume_thread_id, second["suspended_thread_ids"])

        # Two specification-backlog items produce 0.50 pressure. If the pending
        # prediction resolves, specification pressure wins the fixed-order tie
        # with novelty and the
        # existing suspended Q_RESUME becomes the legacy question. If that new
        # evidence is withheld, the still-pending evidence-ready prediction
        # produces 0.75 evidence hunger and a different legacy question.
        state["experiments"] = [
            {
                "id": f"X_SPEC_{index}",
                "cycle": 1,
                "question_id": foreground_question["id"],
                "status": "needs_specification",
                "readiness": "needs_specification",
                "specification": {"actionability": "actionable"},
            }
            for index in range(1, 3)
        ]
        observation = {
            "branch": "autonomous/growth",
            "baseline_fingerprint": "stable-baseline",
            "tracked_files": 100,
            "python_files": 20,
            "python_source_lines": 5000,
            "test_files": 12,
            "working_tree_clean": True,
        }
        state["environment_snapshots"] = [dict(observation, cycle=21)]

        with tempfile.TemporaryDirectory() as setup_temp:
            setup_core = AgentCore(StateStore(Path(setup_temp) / "organism.json"))
            prediction = setup_core._make_prediction(
                state,
                observation,
                "2026-10-04T00:00:00+00:00",
            )
            state["predictions"].append(prediction)
            prediction_experiment = setup_core._create_prediction_experiment(
                state,
                prediction,
                "2026-10-04T00:00:00+00:00",
            )
        prediction_experiment["question_id"] = resume_question["id"]

        with tempfile.TemporaryDirectory() as actual_temp, tempfile.TemporaryDirectory() as counterfactual_temp:
            actual_store = StateStore(Path(actual_temp) / "organism.json")
            counterfactual_store = StateStore(Path(counterfactual_temp) / "organism.json")
            actual_store.save(state)
            counterfactual_store.save(state)

            actual = AgentCore(actual_store).cycle(
                observation=observation,
                strict_experiment_admission=True,
            )
            counterfactual = NoNewPredictionEvidenceCore(counterfactual_store).cycle(
                observation=observation,
                strict_experiment_admission=True,
            )
            actual_after = actual_store.load()
            counterfactual_after = counterfactual_store.load()

        actual_decision = actual["agenda_decision"]
        counterfactual_decision = counterfactual["agenda_decision"]
        self.assertEqual(actual["intention"]["kind"], "specify_experiment")
        self.assertEqual(
            counterfactual["intention"]["kind"],
            "resolve_pending_evidence",
        )
        self.assertEqual(actual["question"]["id"], resume_question["id"])
        self.assertEqual(
            actual_decision["resumed_thread_id"],
            resume_thread_id,
        )
        self.assertTrue(actual_decision["selected"]["new_evidence_refs"])
        self.assertNotEqual(
            counterfactual_decision["selected_thread_id"],
            resume_thread_id,
        )

        # The direct 0.15 agenda bonus is not what makes the actual thread win:
        # evidence changed the upstream drive/intention/generated-question path.
        selected = actual_decision["selected"]
        runner_up = max(
            item["priority_score"]
            for item in actual_decision["candidate_summaries"]
            if item["question_id"] != selected["question_id"]
        )
        self.assertGreater(
            selected["priority_score"] - selected["evidence_change_value"],
            runner_up,
        )
        self.assertTrue(
            actual_decision["priority_change_supported_by_new_evidence"]
        )
        self.assertEqual(actual_after["agenda"]["genuine_resumption_count"], 1)
        self.assertEqual(
            counterfactual_after["agenda"]["genuine_resumption_count"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
