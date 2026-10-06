from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.agenda import update_agenda
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state


class NoNewPredictionEvidenceCore(AgentCore):
    """Test-only counterfactual: preserve the prior pending prediction for one cycle."""

    def _evaluate_prediction(self, state, observation, now):
        return None


class Phase42FullCycleResumptionCausalityTests(unittest.TestCase):
    def test_coincident_direct_evidence_does_not_prove_full_cycle_resumption_causality(self) -> None:
        """The same prior state must choose differently without the newly acquired evidence."""

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

        resume_text = (
            "What observable, evidence source, and resolution rule would make "
            "experiment X_SPEC_1 evidence-ready?"
        )
        resume_question = {
            "id": "Q_RESUME",
            "text": resume_text,
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

        first = update_agenda(
            state,
            legacy_question=resume_question,
            cycle=20,
        )
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
        self.assertEqual(
            second["selected"]["question_id"],
            foreground_question["id"],
        )
        self.assertIn(resume_thread_id, second["suspended_thread_ids"])

        # Four genuine specification-backlog items make specification pressure
        # 0.9, so both the real and no-new-evidence cycles generate Q_RESUME.
        # The prediction experiment below is separate: its completion only adds
        # coincident direct progress to Q_RESUME.
        state["experiments"] = [
            {
                "id": f"X_SPEC_{index}",
                "cycle": 1,
                "question_id": foreground_question["id"],
                "status": "needs_specification",
                "readiness": "needs_specification",
                "specification": {"actionability": "actionable"},
            }
            for index in range(1, 5)
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
            setup_core = AgentCore(
                StateStore(Path(setup_temp) / "organism.json")
            )
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

        # Test fixture only: keep the real prediction-status contract and
        # lifecycle, but attach its completed evidence to the already-suspended
        # inquiry so the complete cycle can test causal attribution.
        prediction_experiment["question_id"] = resume_question["id"]

        # Rejection must preserve prior durable accounting, not reset it to zero.
        prior_record = {"decision_id": "AD_PRIOR", "cycle": 18}
        state["agenda"]["genuine_resumption_count"] = 5
        state["agenda"]["last_genuine_resumption"] = prior_record

        with tempfile.TemporaryDirectory() as actual_temp, tempfile.TemporaryDirectory() as counterfactual_temp:
            actual_store = StateStore(Path(actual_temp) / "organism.json")
            counterfactual_store = StateStore(
                Path(counterfactual_temp) / "organism.json"
            )
            actual_store.save(state)
            counterfactual_store.save(state)

            actual = AgentCore(actual_store).cycle(
                observation=observation,
                strict_experiment_admission=True,
            )
            counterfactual = NoNewPredictionEvidenceCore(
                counterfactual_store
            ).cycle(
                observation=observation,
                strict_experiment_admission=True,
            )

            actual_after = actual_store.load()
            counterfactual_after = counterfactual_store.load()

        actual_decision = actual["agenda_decision"]
        counterfactual_decision = counterfactual["agenda_decision"]
        self.assertIsNotNone(actual_decision)
        self.assertIsNotNone(counterfactual_decision)

        self.assertEqual(actual["intention"]["kind"], "specify_experiment")
        self.assertEqual(
            counterfactual["intention"]["kind"],
            "specify_experiment",
        )
        self.assertEqual(
            actual["question"]["id"],
            counterfactual["question"]["id"],
        )
        self.assertEqual(actual["question"]["id"], resume_question["id"])

        self.assertEqual(
            actual_decision["selected"]["question_id"],
            resume_question["id"],
        )
        self.assertEqual(
            counterfactual_decision["selected"]["question_id"],
            resume_question["id"],
        )
        self.assertEqual(
            actual_decision["resumed_thread_id"],
            resume_thread_id,
        )
        self.assertEqual(
            counterfactual_decision["resumed_thread_id"],
            resume_thread_id,
        )
        self.assertTrue(actual_decision["selected"]["new_evidence_refs"])
        self.assertFalse(
            counterfactual_decision["selected"]["new_evidence_refs"]
        )

        # Current code marks the actual event evidence-backed merely because
        # direct evidence is present. The no-new-evidence full cycle proves the
        # same suspended thread would have resumed anyway.
        self.assertFalse(
            actual_decision["priority_change_supported_by_new_evidence"],
            {
                "actual_selected": actual_decision["selected"],
                "counterfactual_selected": counterfactual_decision["selected"],
                "actual_intention": actual["intention"],
                "counterfactual_intention": counterfactual["intention"],
            },
        )
        self.assertEqual(
            actual_after["agenda"]["genuine_resumption_count"],
            5,
        )
        self.assertEqual(
            counterfactual_after["agenda"]["genuine_resumption_count"],
            5,
        )
        self.assertEqual(actual_after["agenda"]["last_genuine_resumption"], prior_record)
        self.assertEqual(counterfactual_after["agenda"]["last_genuine_resumption"], prior_record)



if __name__ == "__main__":
    unittest.main()
