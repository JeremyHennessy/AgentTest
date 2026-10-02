from __future__ import annotations

import unittest

from agenttest.agenda import update_agenda
from agenttest.learning import REPOSITORY_STABILITY_FAMILY
from agenttest.semantic import question_has_active_experiment_path
from agenttest.state import initial_state


class Phase42IntegrityTests(unittest.TestCase):
    def _replication_question(self) -> dict:
        return {
            "id": "Q_REPLICATION",
            "text": (
                "Will measured repository fields remain unchanged until the next "
                "self-observation unless an intervening code change alters the baseline?"
            ),
            "status": "open",
            "created_cycle": 1,
            "times_selected": 20,
            "last_selected_cycle": 9,
            "source": "repository_stability_prediction",
        }

    def test_only_proposed_linked_work_is_an_active_experiment_path(self) -> None:
        state = initial_state()
        state["cycles"] = 10
        question = self._replication_question()
        state["questions"] = [question]
        state["experiments"] = [
            {
                "id": "X000001",
                "question_id": question["id"],
                "status": "completed",
                "status_history": [
                    {
                        "cycle": 10,
                        "from": "proposed",
                        "to": "completed",
                        "reason": "prediction_status_contract_resolved",
                    }
                ],
            }
        ]

        self.assertFalse(question_has_active_experiment_path(state, question))

        state["experiments"].append(
            {
                "id": "X000002",
                "question_id": question["id"],
                "status": "proposed",
                "readiness": "evidence_ready",
            }
        )

        self.assertTrue(question_has_active_experiment_path(state, question))

    def test_source_provenance_cannot_create_progress_bonus(self) -> None:
        state = initial_state()
        state["cycles"] = 10
        state["generation"] = 10
        state["agenda"]["started_cycle"] = 9
        state["empirical_learning"]["families"][REPOSITORY_STABILITY_FAMILY] = {
            "family": REPOSITORY_STABILITY_FAMILY,
            "completed_trials": 6,
            "evaluable_trials": 6,
            "stable_observations": 6,
            "change_observations": 0,
            "inconclusive_trials": 0,
            "stability_rate": 1.0,
            "next_expected_status": "confirmed",
            "experiment_refs": [],
            "evidence_refs": ["P_SOURCE_1", "R_SOURCE_1"],
        }
        frontier = {
            "id": "Q_FRONTIER",
            "text": "Which distinct measurable relationship should be tested next?",
            "status": "open",
            "created_cycle": 1,
            "times_selected": 5,
            "last_selected_cycle": 9,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": ["P_SOURCE_1", "R_SOURCE_1"],
        }
        replication = self._replication_question()
        state["questions"] = [frontier, replication]

        first = update_agenda(state, legacy_question=frontier, cycle=10)
        self.assertIsNotNone(first)

        frontier["source_evidence_refs"].extend(["P_SOURCE_2", "R_SOURCE_2"])
        state["cycles"] = 11
        second = update_agenda(state, legacy_question=frontier, cycle=11)

        selected = second["selected"]
        self.assertEqual(selected["new_evidence_refs"], [])
        self.assertEqual(selected["evidence_change_value"], 0.0)


if __name__ == "__main__":
    unittest.main()
