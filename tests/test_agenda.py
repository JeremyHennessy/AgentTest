from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.agenda import AGENDA_MAX_THREADS, update_agenda
from agenttest.core import AgentCore
from agenttest.learning import REPOSITORY_STABILITY_FAMILY
from agenttest.state import StateStore, initial_state, migrate_state


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


class PersistentAgendaTests(unittest.TestCase):
    def _state(self) -> dict:
        state = initial_state()
        state["cycles"] = 10
        state["generation"] = 10
        state["agenda"]["started_cycle"] = 9
        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = saturated_family()
        return state

    def test_outcome_of_mature_replication_can_yield_foreground_to_frontier(self) -> None:
        state = self._state()
        replication = {
            "id": "Q000001",
            "text": "Will measured repository fields remain stable on the next observation?",
            "status": "open",
            "created_cycle": 1,
            "times_selected": 20,
            "last_selected_cycle": 9,
            "source": "repository_stability_prediction",
        }
        frontier = {
            "id": "Q000002",
            "text": FRONTIER_QUESTION,
            "status": "open",
            "created_cycle": 2,
            "times_selected": 4,
            "last_selected_cycle": 8,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": ["P000001", "R000001"],
        }
        state["questions"] = [replication, frontier]
        state["experiments"] = [
            {
                "id": "X000001",
                "question_id": replication["id"],
                "status": "proposed",
                "readiness": "evidence_ready",
                "learning_family": REPOSITORY_STABILITY_FAMILY,
                "empirical_basis": saturated_family(),
            }
        ]

        before_questions = len(state["questions"])
        before_experiments = len(state["experiments"])
        decision = update_agenda(
            state,
            legacy_question=replication,
            cycle=10,
        )

        self.assertIsNotNone(decision)
        self.assertEqual(
            decision["legacy_counterfactual"]["question_id"],
            replication["id"],
        )
        self.assertEqual(decision["selected"]["question_id"], frontier["id"])
        self.assertTrue(decision["changed_choice"])
        self.assertGreater(decision["decision_margin"], 0.0)
        self.assertIsNone(decision["resumed_thread_id"])
        self.assertFalse(decision["priority_change_supported_by_new_evidence"])
        self.assertEqual(len(state["agenda"]["threads"]), 2)
        self.assertEqual(len(state["questions"]), before_questions)
        self.assertEqual(len(state["experiments"]), before_experiments)

        by_question = {
            thread["question_id"]: thread
            for thread in state["agenda"]["threads"]
        }
        self.assertEqual(by_question[frontier["id"]]["status"], "foreground")
        self.assertEqual(by_question[replication["id"]]["status"], "suspended")
        self.assertEqual(
            by_question[replication["id"]]["suspension_reason"],
            "mature_replication_can_continue_without_foreground_attention",
        )

    def test_suspended_thread_resumes_when_new_evidence_raises_priority(self) -> None:
        state = initial_state()
        state["cycles"] = 10
        state["generation"] = 10
        state["agenda"]["started_cycle"] = 1
        frontier = {
            "id": "Q000001",
            "text": FRONTIER_QUESTION,
            "status": "open",
            "created_cycle": 1,
            "times_selected": 0,
            "last_selected_cycle": None,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": [],
        }
        replication = {
            "id": "Q000002",
            "text": "Will the current measured repository fields remain unchanged?",
            "status": "open",
            "created_cycle": 2,
            "times_selected": 1,
            "last_selected_cycle": 9,
            "source": "repository_stability_prediction",
        }
        state["questions"] = [frontier, replication]
        state["experiments"] = [
            {
                "id": "X000001",
                "question_id": replication["id"],
                "status": "proposed",
                "readiness": "evidence_ready",
            }
        ]

        first = update_agenda(
            state,
            legacy_question=replication,
            cycle=10,
        )
        self.assertEqual(first["selected"]["question_id"], replication["id"])
        frontier_thread = next(
            thread
            for thread in state["agenda"]["threads"]
            if thread["question_id"] == frontier["id"]
        )
        self.assertEqual(frontier_thread["status"], "suspended")
        frontier_thread_id = frontier_thread["id"]

        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = saturated_family()
        frontier["source_evidence_refs"] = [
            "P000001",
            "R000001",
            "P000002",
            "R000002",
            "P000003",
            "R000003",
        ]
        state["cycles"] = 11
        second = update_agenda(
            state,
            legacy_question=replication,
            cycle=11,
        )

        self.assertEqual(second["selected"]["question_id"], frontier["id"])
        self.assertEqual(second["resumed_thread_id"], frontier_thread_id)
        self.assertTrue(second["foreground_changed"])
        self.assertTrue(second["priority_change_supported_by_new_evidence"])
        self.assertIn(
            next(
                thread["id"]
                for thread in state["agenda"]["threads"]
                if thread["question_id"] == replication["id"]
            ),
            second["suspended_thread_ids"],
        )

    def test_new_evidence_backed_core_question_can_interrupt_and_frontier_can_resume(self) -> None:
        state = self._state()
        frontier = {
            "id": "Q000001",
            "text": FRONTIER_QUESTION,
            "status": "open",
            "created_cycle": 1,
            "times_selected": 8,
            "last_selected_cycle": 9,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": [
                "P000001",
                "R000001",
                "P000002",
                "R000002",
                "P000003",
                "R000003",
            ],
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

        first = update_agenda(
            state,
            legacy_question=frontier,
            cycle=10,
        )
        self.assertEqual(first["selected"]["question_id"], frontier["id"])
        frontier_thread_id = first["selected_thread_id"]

        state["cycles"] = 11
        second = update_agenda(
            state,
            legacy_question=interrupt,
            cycle=11,
        )
        self.assertEqual(second["selected"]["question_id"], interrupt["id"])
        self.assertTrue(second["foreground_changed"])
        self.assertIn(frontier_thread_id, second["suspended_thread_ids"])

        frontier["source_evidence_refs"] = [
            "P000002",
            "R000002",
            "P000003",
            "R000003",
            "P000004",
            "R000004",
        ]
        state["cycles"] = 12
        third = update_agenda(
            state,
            legacy_question=frontier,
            cycle=12,
        )
        self.assertEqual(third["selected"]["question_id"], frontier["id"])
        self.assertEqual(third["resumed_thread_id"], frontier_thread_id)
        self.assertTrue(third["priority_change_supported_by_new_evidence"])

    def test_agenda_is_bounded(self) -> None:
        state = self._state()
        questions = []
        experiments = []
        for index in range(6):
            question = {
                "id": f"Q{index + 1:06d}",
                "text": f"Question {index + 1}",
                "status": "open",
                "created_cycle": index + 1,
                "times_selected": index,
                "last_selected_cycle": index,
            }
            questions.append(question)
            experiments.append(
                {
                    "id": f"X{index + 1:06d}",
                    "question_id": question["id"],
                    "status": "proposed",
                    "readiness": "evidence_ready",
                }
            )
        state["questions"] = questions
        state["experiments"] = experiments

        decision = update_agenda(
            state,
            legacy_question=questions[0],
            cycle=10,
        )

        self.assertIsNotNone(decision)
        self.assertLessEqual(len(state["agenda"]["threads"]), AGENDA_MAX_THREADS)
        self.assertLessEqual(
            len(decision["candidate_summaries"]),
            AGENDA_MAX_THREADS,
        )

    def test_schema25_migration_activates_agenda_prospectively(self) -> None:
        state = initial_state()
        state["schema_version"] = 24
        state["cycles"] = 50
        state["generation"] = 50
        state["agenda"]["started_cycle"] = None

        migrated = migrate_state(state)

        self.assertEqual(migrated["schema_version"], 25)
        self.assertEqual(migrated["agenda"]["started_cycle"], 50)

    def test_core_emits_agenda_decision_without_new_action_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = self._state()
            state["questions"] = [
                {
                    "id": "Q000001",
                    "text": "Will measured repository fields remain unchanged?",
                    "status": "open",
                    "created_cycle": 1,
                    "times_selected": 20,
                    "last_selected_cycle": 9,
                    "source": "repository_stability_prediction",
                },
                {
                    "id": "Q000002",
                    "text": FRONTIER_QUESTION,
                    "status": "open",
                    "created_cycle": 2,
                    "times_selected": 5,
                    "last_selected_cycle": 8,
                    "source": "empirical_frontier_transfer",
                    "source_learning_family": REPOSITORY_STABILITY_FAMILY,
                    "source_evidence_refs": ["P000001", "R000001"],
                },
            ]
            store.save(state)
            core = AgentCore(store)

            result = core.cycle()
            reloaded = store.load()

            self.assertIsNotNone(result["agenda_decision"])
            self.assertEqual(
                result["question"]["id"],
                result["agenda_decision"]["selected"]["question_id"],
            )
            self.assertIsNone(result["action_lab_result"])
            self.assertIsNone(result["planning_lab_result"])
            self.assertEqual(
                reloaded["agenda"]["foreground_thread_id"],
                result["agenda_decision"]["selected_thread_id"],
            )


if __name__ == "__main__":
    unittest.main()
