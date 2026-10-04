from __future__ import annotations

import unittest

from agenttest.agenda import update_agenda
from agenttest.learning import REPOSITORY_STABILITY_FAMILY
from agenttest.state import initial_state


FRONTIER_QUESTION = (
    "Which distinct measurable relationship should be tested next to challenge or "
    "extend the learned repository_stability_without_intervention pattern?"
)


def saturated_family() -> dict:
    return {
        "family": REPOSITORY_STABILITY_FAMILY,
        "completed_trials": 6,
        "evaluable_trials": 6,
        "stable_observations": 6,
        "change_observations": 0,
        "inconclusive_trials": 0,
        "stability_rate": 1.0,
        "next_expected_status": "confirmed",
        "experiment_refs": [],
        "evidence_refs": [
            "P000001",
            "R000001",
            "P000002",
            "R000002",
            "P000003",
            "R000003",
        ],
    }


class Phase42ResumptionCausalAttributionTests(unittest.TestCase):
    def test_new_evidence_must_change_the_winner_to_count_as_evidence_backed_resumption(self) -> None:
        """A coincident evidence ref must not make an otherwise inevitable resume genuine."""

        state = initial_state()
        state["cycles"] = 10
        state["generation"] = 10
        state["agenda"]["started_cycle"] = 9
        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = saturated_family()

        frontier = {
            "id": "Q000001",
            "text": FRONTIER_QUESTION,
            "status": "open",
            "created_cycle": 1,
            "times_selected": 8,
            "last_selected_cycle": 9,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": list(saturated_family()["evidence_refs"]),
        }
        interrupt = {
            "id": "Q000002",
            "text": "What caused the newly observed prediction error?",
            "status": "open",
            "created_cycle": 10,
            "times_selected": 0,
            "last_selected_cycle": None,
            "source_evidence_refs": ["S_INTERRUPT", "R_INTERRUPT"],
        }
        state["questions"] = [frontier, interrupt]
        state["experiments"] = [
            {
                "id": "X_INTERRUPT",
                "question_id": interrupt["id"],
                "status": "proposed",
                "readiness": "evidence_ready",
            }
        ]

        first = update_agenda(state, legacy_question=frontier, cycle=10)
        self.assertEqual(first["selected"]["question_id"], frontier["id"])
        frontier_thread_id = first["selected_thread_id"]

        state["cycles"] = 11
        second = update_agenda(state, legacy_question=interrupt, cycle=11)
        self.assertEqual(second["selected"]["question_id"], interrupt["id"])
        self.assertIn(frontier_thread_id, second["suspended_thread_ids"])

        state["experiments"].append(
            {
                "id": "X_FRONTIER_PROGRESS",
                "question_id": frontier["id"],
                "status": "completed",
                "evidence_refs": ["E_FRONTIER_PROGRESS", "R_FRONTIER_PROGRESS"],
                "outcome": "supported",
            }
        )
        state["cycles"] = 12
        third = update_agenda(state, legacy_question=frontier, cycle=12)

        self.assertEqual(third["resumed_thread_id"], frontier_thread_id)
        self.assertIn("X_FRONTIER_PROGRESS", third["selected"]["new_evidence_refs"])

        selected = third["selected"]
        runner_up = max(
            item["priority_score"]
            for item in third["candidate_summaries"]
            if item["question_id"] != selected["question_id"]
        )
        without_new_evidence = (
            selected["priority_score"] - selected["evidence_change_value"]
        )
        self.assertGreater(
            without_new_evidence,
            runner_up,
            "fixture must prove the thread would resume even without the new-evidence bonus",
        )

        # Desired scientific contract: only call the priority change evidence-backed
        # if removing the new-evidence contribution would change the winner.
        self.assertFalse(
            third["priority_change_supported_by_new_evidence"],
            {
                "selected_priority": selected["priority_score"],
                "evidence_change_value": selected["evidence_change_value"],
                "counterfactual_priority": without_new_evidence,
                "runner_up_priority": runner_up,
                "new_evidence_refs": selected["new_evidence_refs"],
            },
        )


if __name__ == "__main__":
    unittest.main()
