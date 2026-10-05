from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.agenda import (
    AGENDA_MAX_DECISIONS,
    AGENDA_MAX_THREADS,
    update_agenda,
)
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
            "source_evidence_refs": [
                "P000001",
                "R000001",
                "P000002",
                "R000002",
                "P000003",
                "R000003",
            ],
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
        frontier["source_evidence_refs"] = list(
            saturated_family()["evidence_refs"]
        )
        state["experiments"].append(
            {
                "id": "X_FRONTIER_RESULT",
                "question_id": frontier["id"],
                "status": "completed",
                "evidence_refs": ["E_FRONTIER_RESULT", "R_FRONTIER_RESULT"],
                "outcome": "supported",
            }
        )
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
        self.assertEqual(
            second["selected"]["new_evidence_refs"],
            ["X_FRONTIER_RESULT", "E_FRONTIER_RESULT", "R_FRONTIER_RESULT"],
        )
        self.assertEqual(state["agenda"]["genuine_resumption_count"], 1)
        self.assertEqual(
            state["agenda"]["last_genuine_resumption"]["decision_id"],
            second["id"],
        )
        self.assertIn(
            next(
                thread["id"]
                for thread in state["agenda"]["threads"]
                if thread["question_id"] == replication["id"]
            ),
            second["suspended_thread_ids"],
        )

    def test_genuine_resumption_survives_decision_history_rollover(self) -> None:
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

        update_agenda(state, legacy_question=replication, cycle=10)
        frontier_thread = next(
            thread
            for thread in state["agenda"]["threads"]
            if thread["question_id"] == frontier["id"]
        )
        frontier_thread_id = frontier_thread["id"]

        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = saturated_family()
        frontier["source_evidence_refs"] = list(
            saturated_family()["evidence_refs"]
        )
        state["experiments"].append(
            {
                "id": "X_FRONTIER_RESULT",
                "question_id": frontier["id"],
                "status": "completed",
                "evidence_refs": ["E_FRONTIER_RESULT", "R_FRONTIER_RESULT"],
                "outcome": "supported",
            }
        )
        second = update_agenda(
            state,
            legacy_question=replication,
            cycle=11,
        )
        self.assertEqual(second["resumed_thread_id"], frontier_thread_id)
        self.assertEqual(state["agenda"]["genuine_resumption_count"], 1)

        for cycle in range(12, 12 + AGENDA_MAX_DECISIONS + 2):
            state["cycles"] = cycle
            update_agenda(
                state,
                legacy_question=frontier,
                cycle=cycle,
            )

        self.assertEqual(
            len(state["agenda"]["decisions"]),
            AGENDA_MAX_DECISIONS,
        )
        self.assertNotIn(
            second["id"],
            [decision["id"] for decision in state["agenda"]["decisions"]],
        )
        self.assertEqual(state["agenda"]["genuine_resumption_count"], 1)
        self.assertEqual(
            state["agenda"]["last_genuine_resumption"]["decision_id"],
            second["id"],
        )

    def test_initial_thread_artifact_is_not_backfilled_as_genuine_resumption(self) -> None:
        state = self._state()
        state["agenda"].pop("genuine_resumption_count", None)
        state["agenda"].pop("last_genuine_resumption", None)
        state["agenda"]["decisions"] = [
            {
                "id": "AD000001",
                "cycle": 10,
                "foreground_changed": False,
                "previous_foreground_thread_id": None,
                "selected_thread_id": "AT000001",
                "resumed_thread_id": "AT000001",
                "priority_change_supported_by_new_evidence": True,
                "selected": {
                    "question_id": "Q000001",
                    "new_evidence_refs": ["P000001", "R000001"],
                },
            }
        ]

        agenda = migrate_state(state)["agenda"]

        self.assertEqual(agenda["genuine_resumption_count"], 0)
        self.assertIsNone(agenda["last_genuine_resumption"])

    def test_migration_backfills_retained_genuine_resumption(self) -> None:
        state = self._state()
        state["agenda"].pop("genuine_resumption_count", None)
        state["agenda"].pop("last_genuine_resumption", None)
        state["agenda"]["decisions"] = [
            {
                "id": "AD000007",
                "cycle": 16,
                "foreground_changed": True,
                "previous_foreground_thread_id": "AT000002",
                "selected_thread_id": "AT000001",
                "resumed_thread_id": "AT000001",
                "priority_change_supported_by_new_evidence": True,
                "selected": {
                    "question_id": "Q000001",
                    "new_evidence_refs": ["P000007", "R000007"],
                },
            }
        ]

        agenda = migrate_state(state)["agenda"]

        self.assertEqual(agenda["genuine_resumption_count"], 1)
        self.assertEqual(
            agenda["last_genuine_resumption"]["decision_id"],
            "AD000007",
        )
        self.assertEqual(
            agenda["last_genuine_resumption"]["new_evidence_refs"],
            ["P000007", "R000007"],
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

        frontier["source_evidence_refs"].extend(["P000004", "R000004"])
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
        third = update_agenda(
            state,
            legacy_question=frontier,
            cycle=12,
        )
        self.assertEqual(third["selected"]["question_id"], frontier["id"])
        self.assertEqual(third["resumed_thread_id"], frontier_thread_id)
        self.assertTrue(third["priority_change_supported_by_new_evidence"])
        self.assertNotIn("P000004", third["selected"]["new_evidence_refs"])
        self.assertIn("X_FRONTIER_PROGRESS", third["selected"]["new_evidence_refs"])

    def test_source_family_provenance_is_not_fresh_thread_progress(self) -> None:
        state = self._state()
        frontier = {
            "id": "Q000001",
            "text": FRONTIER_QUESTION,
            "status": "open",
            "created_cycle": 1,
            "times_selected": 5,
            "last_selected_cycle": 9,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": ["P_SOURCE_1", "R_SOURCE_1"],
        }
        replication = {
            "id": "Q000002",
            "text": "Will measured repository fields remain stable on the next observation?",
            "status": "open",
            "created_cycle": 2,
            "times_selected": 20,
            "last_selected_cycle": 8,
            "source": "repository_stability_prediction",
        }
        state["questions"] = [frontier, replication]

        first = update_agenda(
            state,
            legacy_question=frontier,
            cycle=10,
        )
        self.assertIsNotNone(first)
        self.assertEqual(first["selected"]["question_id"], frontier["id"])

        frontier["source_evidence_refs"].extend(["P_SOURCE_2", "R_SOURCE_2"])
        state["cycles"] = 11
        second = update_agenda(
            state,
            legacy_question=frontier,
            cycle=11,
        )

        self.assertIsNotNone(second)
        selected = second["selected"]
        self.assertEqual(selected["question_id"], frontier["id"])
        self.assertIn("P_SOURCE_2", selected["evidence_refs"])
        self.assertIn("R_SOURCE_2", selected["evidence_refs"])
        self.assertEqual(selected["new_evidence_refs"], [])
        self.assertEqual(selected["evidence_change_value"], 0.0)

    def test_v1_thread_progress_is_baselined_during_policy_migration(self) -> None:
        state = self._state()
        frontier = {
            "id": "Q000001",
            "text": FRONTIER_QUESTION,
            "status": "open",
            "created_cycle": 1,
            "times_selected": 5,
            "last_selected_cycle": 9,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": ["P_SOURCE_1", "R_SOURCE_1"],
        }
        replication = {
            "id": "Q000002",
            "text": "Will measured repository fields remain stable on the next observation?",
            "status": "open",
            "created_cycle": 2,
            "times_selected": 20,
            "last_selected_cycle": 8,
            "source": "repository_stability_prediction",
        }
        state["questions"] = [frontier, replication]
        state["experiments"] = [
            {
                "id": "X_OLD_PROGRESS",
                "question_id": frontier["id"],
                "status": "completed",
                "outcome": "supported",
                "evidence_refs": ["E_OLD_PROGRESS", "R_OLD_PROGRESS"],
            }
        ]
        state["agenda"]["version"] = "persistent-multithread-agenda-v1"
        state["agenda"]["foreground_thread_id"] = "AT000001"
        state["agenda"]["threads"] = [
            {
                "id": "AT000001",
                "question_id": frontier["id"],
                "created_cycle": 9,
                "status": "foreground",
                "priority_score": 0.8,
                "evidence_refs": ["P_SOURCE_1", "R_SOURCE_1"],
                "last_foreground_cycle": 9,
                "last_updated_cycle": 9,
                "history": [],
            },
            {
                "id": "AT000002",
                "question_id": replication["id"],
                "created_cycle": 9,
                "status": "suspended",
                "priority_score": 0.0,
                "evidence_refs": [],
                "last_foreground_cycle": None,
                "last_updated_cycle": 9,
                "history": [],
            },
        ]

        decision = update_agenda(
            state,
            legacy_question=frontier,
            cycle=10,
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision["selected"]["new_evidence_refs"], [])
        self.assertEqual(decision["selected"]["evidence_change_value"], 0.0)
        frontier_thread = next(
            thread
            for thread in state["agenda"]["threads"]
            if thread["question_id"] == frontier["id"]
        )
        self.assertIn(
            "X_OLD_PROGRESS",
            frontier_thread["thread_progress_evidence_refs"],
        )

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

    def test_bounded_thread_reentry_preserves_identity_and_suspended_status(self) -> None:
        state = self._state()
        state["agenda"]["next_thread_index"] = 5
        state["agenda"]["archived_threads"] = [
            {
                "id": "AT000002",
                "question_id": "Q000002",
                "created_cycle": 5,
                "status": "suspended",
                "priority_score": 0.2,
                "evidence_refs": [],
                "last_foreground_cycle": 5,
                "last_updated_cycle": 9,
                "history": [
                    {
                        "cycle": 9,
                        "from": "foreground",
                        "to": "suspended",
                        "reason": "lower_priority_but_executable",
                        "evidence_refs": [],
                    }
                ],
                "archived_cycle": 10,
                "archive_reason": "outside_current_bounded_agenda",
            }
        ]
        questions = [
            {
                "id": "Q000001",
                "text": "Foreground question",
                "status": "open",
                "created_cycle": 1,
                "times_selected": 10,
                "last_selected_cycle": 10,
            },
            {
                "id": "Q000002",
                "text": "Returning question",
                "status": "open",
                "created_cycle": 2,
                "times_selected": 2,
                "last_selected_cycle": 8,
                "source": "empirical_frontier_transfer",
                "source_learning_family": REPOSITORY_STABILITY_FAMILY,
                "source_evidence_refs": ["P_RETURN", "R_RETURN"],
            },
            {
                "id": "Q000003",
                "text": "Competing executable question",
                "status": "open",
                "created_cycle": 3,
                "times_selected": 1,
                "last_selected_cycle": 9,
            },
        ]
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
            "evidence_refs": ["P_RETURN", "R_RETURN"],
        }
        state["questions"] = questions
        state["experiments"] = [
            {
                "id": "X_RETURN",
                "question_id": "Q000002",
                "status": "completed",
                "evidence_refs": ["E_RETURN"],
            },
            {
                "id": "X_COMPETING",
                "question_id": "Q000003",
                "status": "proposed",
                "readiness": "evidence_ready",
            },
        ]

        decision = update_agenda(
            state,
            legacy_question=questions[1],
            cycle=11,
        )

        returning = next(
            item
            for item in state["agenda"]["threads"]
            if item["question_id"] == "Q000002"
        )
        self.assertEqual(returning["id"], "AT000002")
        self.assertEqual(decision["resumed_thread_id"], "AT000002")
        self.assertNotIn(
            "AT000002",
            [item.get("id") for item in state["agenda"]["archived_threads"]],
        )

    def test_decision_telemetry_records_suspended_new_evidence_opportunity(self) -> None:
        state = self._state()
        questions = [
            {"id": "Q000001", "text": "Foreground", "status": "open", "created_cycle": 1, "times_selected": 1, "last_selected_cycle": 9},
            {"id": "Q000002", "text": "Suspended", "status": "open", "created_cycle": 2, "times_selected": 1, "last_selected_cycle": 8},
        ]
        state["questions"] = questions
        state["experiments"] = [
            {"id": "X1", "question_id": "Q000001", "status": "proposed", "readiness": "evidence_ready"},
            {"id": "X2", "question_id": "Q000002", "status": "completed", "evidence_refs": ["E2"]},
        ]
        state["agenda"]["threads"] = [
            {"id": "AT000001", "question_id": "Q000001", "created_cycle": 8, "status": "foreground", "priority_score": 0.0, "evidence_refs": [], "last_foreground_cycle": 9, "last_updated_cycle": 9, "history": [], "active_experiment_path": True, "thread_progress_evidence_refs": []},
            {"id": "AT000002", "question_id": "Q000002", "created_cycle": 8, "status": "suspended", "priority_score": 0.0, "evidence_refs": [], "last_foreground_cycle": 8, "last_updated_cycle": 9, "history": [], "active_experiment_path": False, "thread_progress_evidence_refs": []},
        ]
        state["agenda"]["foreground_thread_id"] = "AT000001"

        decision = update_agenda(state, legacy_question=questions[0], cycle=10)
        item = next(x for x in decision["candidate_telemetry"] if x["thread_id"] == "AT000002")
        self.assertEqual(item["previous_status"], "suspended")
        self.assertTrue(item["resumption_opportunity"])
        self.assertIn("X2", item["new_evidence_refs"])

    def test_decision_telemetry_counts_new_executability_once(self) -> None:
        state = self._state()
        questions = [
            {"id": "Q000001", "text": "Foreground", "status": "open", "created_cycle": 1, "times_selected": 1, "last_selected_cycle": 9},
            {"id": "Q000002", "text": "Suspended", "status": "open", "created_cycle": 2, "times_selected": 1, "last_selected_cycle": 8},
        ]
        state["questions"] = questions
        state["experiments"] = [
            {"id": "X1", "question_id": "Q000001", "status": "proposed", "readiness": "evidence_ready"},
            {"id": "X2", "question_id": "Q000002", "status": "proposed", "readiness": "evidence_ready"},
        ]
        state["agenda"]["threads"] = [
            {"id": "AT000001", "question_id": "Q000001", "created_cycle": 8, "status": "foreground", "priority_score": 0.0, "evidence_refs": [], "last_foreground_cycle": 9, "last_updated_cycle": 9, "history": [], "active_experiment_path": True},
            {"id": "AT000002", "question_id": "Q000002", "created_cycle": 8, "status": "suspended", "priority_score": 0.0, "evidence_refs": [], "last_foreground_cycle": 8, "last_updated_cycle": 9, "history": [], "active_experiment_path": False},
        ]
        state["agenda"]["foreground_thread_id"] = "AT000001"

        first = update_agenda(state, legacy_question=questions[0], cycle=10)
        first_item = next(x for x in first["candidate_telemetry"] if x["thread_id"] == "AT000002")
        self.assertTrue(first_item["newly_executable"])
        self.assertTrue(first_item["resumption_opportunity"])

        second = update_agenda(state, legacy_question=questions[0], cycle=11)
        second_item = next(x for x in second["candidate_telemetry"] if x["thread_id"] == "AT000002")
        self.assertFalse(second_item["newly_executable"])
        self.assertFalse(second_item["resumption_opportunity"])

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
