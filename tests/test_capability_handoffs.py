from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import agenttest.planning_lab as planning_lab
from agenttest.action_lab import ACTION_ORDER, BOUNDS, STATEFUL_WORLD_VERSION
from agenttest.agenda import update_agenda
from agenttest.core import AgentCore
from agenttest.drives import choose_intention, compute_drives
from agenttest.learning import REPOSITORY_STABILITY_FAMILY
from agenttest.planning_lab import initial_planning_lab_state
from agenttest.state import StateStore, initial_state


# Cross-phase sanity checks belong here. A new capability that consumes the
# output of an earlier phase should add a deterministic handoff test rather
# than proving only that the downstream function works in isolation.
_CANONICAL_EFFECTS = {
    "north": [1, 0],
    "east": [0, -1],
    "south": [-1, 0],
    "west": [0, 1],
}


def _in_bounds(position: list[int]) -> bool:
    return all(-BOUNDS <= value <= BOUNDS for value in position)


class CapabilityHandoffSanityTests(unittest.TestCase):
    def _phase39_boundary_goal_ready_for_phase40(
        self,
        target: list[int],
    ) -> dict:
        lab = initial_planning_lab_state()
        lab["status"] = "goal_reached"
        lab["bounds"] = BOUNDS
        lab["world_version"] = STATEFUL_WORLD_VERSION
        lab["position"] = list(target)
        lab["visit_counts"] = {f"{target[0]},{target[1]}": 1}

        observations: list[dict] = []
        observation_index = 0
        positions = [
            [x, y]
            for x in range(-BOUNDS, BOUNDS + 1)
            for y in range(-BOUNDS, BOUNDS + 1)
        ]

        # Give every action enough citable general evidence to satisfy Phase 40.
        # Keep those samples away from the selected target so local uncertainty
        # remains under explicit control below.
        for action in ACTION_ORDER:
            delta = _CANONICAL_EFFECTS[action]
            sources = [
                before
                for before in positions
                if before != target
                and _in_bounds(
                    [before[0] + delta[0], before[1] + delta[1]]
                )
            ][:2]
            self.assertEqual(len(sources), 2)
            for before in sources:
                observation_index += 1
                after = [
                    before[0] + delta[0],
                    before[1] + delta[1],
                ]
                observations.append(
                    {
                        "source": "handoff_sanity",
                        "source_id": f"HS_GENERAL_{observation_index}",
                        "cycle": 1,
                        "action": action,
                        "before": list(before),
                        "after": after,
                        "delta": list(delta),
                        "blocked": False,
                        "world_version": STATEFUL_WORLD_VERSION,
                    }
                )

        # At the Phase 39 target, mark every action whose learned effect stays
        # inside the world as already sampled. The only remaining uncertainty is
        # therefore a boundary-facing action whose learned effect predicts an
        # out-of-bounds result. This is the exact class of handoff that Phase 39
        # can value and Phase 40 must still be able to test.
        outward_actions: list[str] = []
        for action in ACTION_ORDER:
            delta = _CANONICAL_EFFECTS[action]
            predicted_after = [
                target[0] + delta[0],
                target[1] + delta[1],
            ]
            if not _in_bounds(predicted_after):
                outward_actions.append(action)
                continue
            observation_index += 1
            observations.append(
                {
                    "source": "handoff_sanity",
                    "source_id": f"HS_LOCAL_{observation_index}",
                    "cycle": 1,
                    "action": action,
                    "before": list(target),
                    "after": predicted_after,
                    "delta": list(delta),
                    "blocked": False,
                    "world_version": STATEFUL_WORLD_VERSION,
                }
            )

        self.assertTrue(outward_actions)
        lab["transition_observations"] = observations
        planning_lab._rebuild_model(lab)

        metrics = planning_lab._objective_candidate_metrics(
            lab,
            target=(target[0], target[1]),
            visit_count=1,
            distance=1,
        )
        self.assertEqual(
            metrics["unseen_target_actions"],
            len(outward_actions),
        )

        lab["objective_selection_started_cycle"] = 1
        lab["objective_realization_started_cycle"] = 1
        lab["objective_decisions"] = [
            {
                "id": "OD_HANDOFF",
                "cycle": 2,
                "changed_choice": True,
                "selected": metrics,
            }
        ]
        lab["goals"] = [
            {
                "id": "PG_HANDOFF",
                "assigned_cycle": 2,
                "completed_cycle": 2,
                "status": "completed",
                "target": list(target),
                "selection": {
                    "kind": "self_selected_bounded_objective",
                    "objective_decision_id": "OD_HANDOFF",
                },
            }
        ]
        lab["active_goal_id"] = None
        lab["active_plan_id"] = None
        lab["objective_realization_decisions"] = []
        lab["objective_realizations"] = []
        lab["active_objective_realization_id"] = None

        return {
            "lab": lab,
            "outward_actions": outward_actions,
        }

    def test_phase39_boundary_uncertainty_is_reachable_by_phase40(self) -> None:
        boundary_targets = [
            [x, y]
            for x in range(-BOUNDS, BOUNDS + 1)
            for y in range(-BOUNDS, BOUNDS + 1)
            if abs(x) == BOUNDS or abs(y) == BOUNDS
        ]

        self.assertTrue(boundary_targets)
        for target in boundary_targets:
            with self.subTest(target=target):
                fixture = self._phase39_boundary_goal_ready_for_phase40(target)
                lab = fixture["lab"]
                precommit = planning_lab._select_objective_realization(lab, 3)

                self.assertIsNotNone(
                    precommit,
                    msg=(
                        "Phase 39 valued unresolved boundary information, but "
                        f"Phase 40 could not precommit a test at {target}."
                    ),
                )
                assert precommit is not None
                self.assertIn(
                    precommit["action"],
                    fixture["outward_actions"],
                )
                self.assertFalse(
                    _in_bounds(precommit["predicted_after"]),
                    msg=(
                        "The sanity fixture should leave only boundary-facing "
                        "uncertainty for Phase 40 to test."
                    ),
                )
                self.assertTrue(precommit["source_observation_refs"])


    def test_phase40_realizations_feed_phase41_objective_valuation(self) -> None:
        lab = initial_planning_lab_state()
        lab["status"] = "ready"
        lab["bounds"] = BOUNDS
        lab["world_version"] = STATEFUL_WORLD_VERSION

        observations: list[dict] = []
        source_index = 0
        comparison_targets = {(-2, -1), (-2, 2)}
        positions = [
            [x, y]
            for x in range(-BOUNDS, BOUNDS + 1)
            for y in range(-BOUNDS, BOUNDS + 1)
        ]
        for action in ACTION_ORDER:
            delta = _CANONICAL_EFFECTS[action]
            sources = [
                before
                for before in positions
                if tuple(before) not in comparison_targets
                and _in_bounds(
                    [before[0] + delta[0], before[1] + delta[1]]
                )
            ][:2]
            self.assertEqual(len(sources), 2)
            for before in sources:
                source_index += 1
                observations.append(
                    {
                        "source": "handoff_sanity",
                        "source_id": f"P41_GENERAL_{source_index}",
                        "cycle": 1,
                        "action": action,
                        "before": list(before),
                        "after": [
                            before[0] + delta[0],
                            before[1] + delta[1],
                        ],
                        "delta": list(delta),
                        "blocked": False,
                        "world_version": STATEFUL_WORLD_VERSION,
                    }
                )

        observations.extend(
            [
                {
                    "source": "handoff_sanity",
                    "source_id": "P41_A_NORTH",
                    "cycle": 1,
                    "action": "north",
                    "before": [-2, -1],
                    "after": [-1, -1],
                    "delta": [1, 0],
                    "blocked": False,
                    "world_version": STATEFUL_WORLD_VERSION,
                },
                {
                    "source": "handoff_sanity",
                    "source_id": "P41_B_EAST",
                    "cycle": 1,
                    "action": "east",
                    "before": [-2, 2],
                    "after": [-2, 1],
                    "delta": [0, -1],
                    "blocked": False,
                    "world_version": STATEFUL_WORLD_VERSION,
                },
            ]
        )
        lab["transition_observations"] = observations
        planning_lab._rebuild_model(lab)

        phase40_cases = [
            ("OR_H1", [0, 0], "north", [1, 0]),
            ("OR_H2", [1, 0], "north", [2, 0]),
            ("OR_H3", [0, 0], "east", [0, -1]),
        ]
        for cycle, (decision_id, state, action, predicted_after) in enumerate(
            phase40_cases,
            start=2,
        ):
            lab["position"] = list(state)
            realized = planning_lab._execute_objective_realization(
                lab,
                {
                    "id": decision_id,
                    "state": list(state),
                    "action": action,
                    "predicted_after": list(predicted_after),
                    "goal_id": f"PG_{decision_id}",
                    "objective_decision_id": f"OD_{decision_id}",
                },
                cycle,
            )
            self.assertEqual(realized["realized_information_gain"], 1.0)

        self.assertEqual(
            [item["action"] for item in lab["objective_realizations"]],
            ["north", "north", "east"],
        )

        lab["position"] = [0, 0]
        lab["visit_counts"] = {
            f"{x},{y}": 100
            for x in range(-BOUNDS, BOUNDS + 1)
            for y in range(-BOUNDS, BOUNDS + 1)
        }
        lab["visit_counts"]["0,0"] = 1
        lab["visit_counts"]["-2,-1"] = 0
        lab["visit_counts"]["-2,2"] = 0
        lab["goals"] = [
            {"id": "PG_REC_A", "status": "completed", "target": [1, 0]},
            {"id": "PG_REC_B", "status": "completed", "target": [0, 1]},
        ]
        lab["self_experiments"] = [
            {
                "id": "SE_REC_A",
                "goal_id": "PG_REC_A",
                "interpretation": "hypothesis_supported",
            },
            {
                "id": "SE_REC_B",
                "goal_id": "PG_REC_B",
                "interpretation": "hypothesis_refuted",
            },
        ]
        lab["plans"] = []
        lab["active_goal_id"] = None
        lab["active_plan_id"] = None
        lab["objective_selection_started_cycle"] = 4
        lab["outcome_valuation_started_cycle"] = 4
        lab["last_objective_selection_cycle"] = None
        lab["objective_decisions"] = []

        goal = planning_lab._choose_goal(lab, 5)
        decision = lab["objective_decisions"][0]

        self.assertIsNotNone(goal)
        self.assertEqual(
            decision["phase39_counterfactual"]["target"],
            [-2, -1],
        )
        self.assertEqual(decision["selected"]["target"], [-2, 2])
        self.assertTrue(decision["outcome_changed_choice"])
        self.assertEqual(
            decision["selected"]["phase40_outcome_refs"],
            [
                lab["objective_realizations"][0]["id"],
                lab["objective_realizations"][1]["id"],
            ],
        )
        self.assertEqual(
            goal["selection"]["kind"],
            "outcome_aware_bounded_objective",
        )

    def test_phase42_evidence_ready_interrupt_reaches_agenda_and_frontier_can_resume(self) -> None:
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 19
        state["metrics"].update(
            {
                "continuity": 1.0,
                "self_model": 1.0,
                "open_endedness": 0.1,
            }
        )
        family = {
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
                "P_HANDOFF_1",
                "R_HANDOFF_1",
                "P_HANDOFF_2",
                "R_HANDOFF_2",
                "P_HANDOFF_3",
                "R_HANDOFF_3",
            ],
        }
        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = family
        replication = {
            "id": "Q_HANDOFF_REPLICATION",
            "text": "Will another comparable observation preserve the stable pattern?",
            "status": "open",
            "created_cycle": 1,
            "times_selected": 20,
            "last_selected_cycle": 19,
            "source": "repository_stability_prediction",
        }
        frontier = {
            "id": "Q_HANDOFF_FRONTIER",
            "text": (
                "Which distinct measurable relationship should be tested next to "
                "challenge or extend the learned "
                "repository_stability_without_intervention pattern?"
            ),
            "status": "open",
            "created_cycle": 2,
            "times_selected": 5,
            "last_selected_cycle": 18,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": list(family["evidence_refs"]),
        }
        state["questions"] = [replication, frontier]

        first = update_agenda(
            state,
            legacy_question=frontier,
            cycle=20,
        )
        self.assertIsNotNone(first)
        self.assertEqual(first["selected"]["question_id"], frontier["id"])
        frontier_thread_id = first["selected_thread_id"]

        interrupt = {
            "id": "Q_HANDOFF_INTERRUPT",
            "text": "What evidence-ready work should be resolved next?",
            "status": "open",
            "created_cycle": 21,
            "times_selected": 0,
            "last_selected_cycle": None,
        }
        state["questions"].append(interrupt)
        state["experiments"] = [
            {
                "id": "X_HANDOFF_INTERRUPT",
                "question_id": interrupt["id"],
                "status": "proposed",
                "readiness": "evidence_ready",
            }
        ]
        state["cycles"] = 21

        drives = compute_drives(
            state,
            strict_question_attention=True,
        )
        self.assertGreater(
            drives["evidence_hunger"],
            drives["empirical_frontier"],
            "Evidence-ready work must be able to interrupt mature frontier exploration.",
        )
        intention = choose_intention(state, drives)
        self.assertEqual(intention["kind"], "resolve_pending_evidence")
        self.assertEqual(intention["target"], "X_HANDOFF_INTERRUPT")

        with tempfile.TemporaryDirectory() as temp:
            core = AgentCore(StateStore(Path(temp) / "organism.json"))
            interrupt_text = core._generate_question(
                state,
                surprise=None,
                intention=intention,
                thought=None,
                strict_question_attention=True,
            )
            interrupt_followup = core._upsert_question(state, interrupt_text)

            second = update_agenda(
                state,
                legacy_question=interrupt_followup,
                cycle=21,
            )
            self.assertIsNotNone(second)
            self.assertTrue(second["foreground_changed"])
            self.assertIn(frontier_thread_id, second["suspended_thread_ids"])

            state["experiments"][0]["status"] = "completed"
            state["experiments"][0]["readiness"] = "resolved"
            family["evidence_refs"].extend(
                ["P_HANDOFF_NEW", "R_HANDOFF_NEW"]
            )
            state["experiments"].append(
                {
                    "id": "X_HANDOFF_FRONTIER_PROGRESS",
                    "question_id": frontier["id"],
                    "status": "completed",
                    "outcome": "supported",
                    "evidence_refs": [
                        "E_HANDOFF_FRONTIER_PROGRESS",
                        "R_HANDOFF_FRONTIER_PROGRESS",
                    ],
                }
            )
            state["cycles"] = 22

            next_drives = compute_drives(
                state,
                strict_question_attention=True,
            )
            next_intention = choose_intention(state, next_drives)
            self.assertEqual(
                next_intention["kind"],
                "explore_empirical_frontier",
            )
            frontier_text = core._generate_question(
                state,
                surprise=None,
                intention=next_intention,
                thought=None,
                strict_question_attention=True,
            )
            resumed_frontier = core._upsert_question(state, frontier_text)
            resumed_frontier.setdefault(
                "source",
                "empirical_frontier_transfer",
            )
            resumed_frontier["source_learning_family"] = (
                next_intention["target"]
            )
            resumed_frontier["source_evidence_refs"] = list(
                next_intention["evidence_refs"]
            )

            third = update_agenda(
                state,
                legacy_question=resumed_frontier,
                cycle=22,
            )

        self.assertIsNotNone(third)
        self.assertEqual(third["resumed_thread_id"], frontier_thread_id)
        self.assertTrue(third["foreground_changed"])
        self.assertTrue(third["priority_change_supported_by_new_evidence"])
        self.assertEqual(state["agenda"]["genuine_resumption_count"], 1)

    def test_phase42_real_cycle_confirmation_does_not_fake_an_interrupt(self) -> None:
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 19
        state["metrics"].update(
            {
                "continuity": 1.0,
                "self_model": 1.0,
                "open_endedness": 0.1,
            }
        )
        replication = {
            "id": "Q_CYCLE_REPLICATION",
            "text": (
                "Will measured repository fields remain unchanged until the next "
                "self-observation unless an intervening code change alters the baseline?"
            ),
            "status": "open",
            "created_cycle": 1,
            "times_selected": 20,
            "last_selected_cycle": 19,
            "source": "repository_stability_prediction",
        }
        frontier = {
            "id": "Q_CYCLE_FRONTIER",
            "text": (
                "Which distinct measurable relationship should be tested next to "
                "challenge or extend the learned "
                "repository_stability_without_intervention pattern?"
            ),
            "status": "open",
            "created_cycle": 2,
            "times_selected": 5,
            "last_selected_cycle": 18,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": [
                "P_HIST_1",
                "R_HIST_1",
                "P_HIST_2",
                "R_HIST_2",
                "P_HIST_3",
                "R_HIST_3",
                "P_HIST_4",
                "R_HIST_4",
                "P_HIST_5",
                "R_HIST_5",
                "P_HIST_6",
                "R_HIST_6",
            ],
        }
        state["questions"] = [replication, frontier]
        state["experiments"] = [
            {
                "id": f"X{index:06d}",
                "cycle": index,
                "question_id": replication["id"],
                "status": "completed",
                "learning_family": REPOSITORY_STABILITY_FAMILY,
                "observed_prediction_status": "confirmed",
                "evidence_refs": [f"P_HIST_{index}", f"R_HIST_{index}"],
            }
            for index in range(1, 7)
        ]
        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = {
            "family": REPOSITORY_STABILITY_FAMILY,
            "completed_trials": 6,
            "evaluable_trials": 6,
            "stable_observations": 6,
            "change_observations": 0,
            "inconclusive_trials": 0,
            "stability_rate": 1.0,
            "next_expected_status": "confirmed",
            "experiment_refs": [f"X{index:06d}" for index in range(1, 7)],
            "evidence_refs": list(frontier["source_evidence_refs"]),
        }
        first = update_agenda(
            state,
            legacy_question=frontier,
            cycle=20,
        )
        self.assertIsNotNone(first)
        frontier_thread_id = first["selected_thread_id"]

        observation = {
            "branch": "autonomous/growth",
            "baseline_fingerprint": "same-baseline",
            "tracked_files": 100,
            "python_files": 20,
            "python_source_lines": 5000,
            "test_files": 12,
            "working_tree_clean": True,
        }
        state["environment_snapshots"] = [dict(observation, cycle=20)]

        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            core = AgentCore(store)
            prediction = core._make_prediction(
                state,
                observation,
                "2026-10-02T00:00:00+00:00",
            )
            state["predictions"].append(prediction)
            core._create_prediction_experiment(
                state,
                prediction,
                "2026-10-02T00:00:00+00:00",
            )
            store.save(state)

            event = core.cycle(
                observation=observation,
                strict_experiment_admission=True,
            )
            after = store.load()

        resolved_prediction = next(
            item
            for item in after["predictions"]
            if item["id"] == prediction["id"]
        )
        self.assertEqual(resolved_prediction["status"], "confirmed")
        self.assertEqual(event["drives"]["evidence_hunger"], 0.0)
        self.assertFalse(event["agenda_decision"]["foreground_changed"])
        self.assertIsNone(event["agenda_decision"]["resumed_thread_id"])
        self.assertEqual(
            event["agenda_decision"]["selected_thread_id"],
            frontier_thread_id,
        )
        replication_summary = next(
            item
            for item in event["agenda_decision"]["candidate_summaries"]
            if item["question_id"] == replication["id"]
        )
        self.assertTrue(
            replication_summary["active_experiment_path"],
            "Agenda must score the replacement evidence-ready prediction path "
            "that exists by the end of the same observed cycle.",
        )
        self.assertIn(
            replication["id"],
            [
                item["id"]
                for item in event["strict_actionable_questions"]
            ],
        )
        self.assertEqual(after["agenda"]["genuine_resumption_count"], 0)

    def test_phase42_real_cycle_prediction_error_returns_frontier_without_false_genuine_resumption(self) -> None:
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 19
        state["metrics"].update(
            {
                "continuity": 1.0,
                "self_model": 1.0,
                "open_endedness": 0.1,
            }
        )
        replication = {
            "id": "Q_CYCLE_REPLICATION",
            "text": (
                "Will measured repository fields remain unchanged until the next "
                "self-observation unless an intervening code change alters the baseline?"
            ),
            "status": "open",
            "created_cycle": 1,
            "times_selected": 20,
            "last_selected_cycle": 19,
            "source": "repository_stability_prediction",
        }
        frontier = {
            "id": "Q_CYCLE_FRONTIER",
            "text": (
                "Which distinct measurable relationship should be tested next to "
                "challenge or extend the learned "
                "repository_stability_without_intervention pattern?"
            ),
            "status": "open",
            "created_cycle": 2,
            "times_selected": 5,
            "last_selected_cycle": 18,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": [
                "P_HIST_1",
                "R_HIST_1",
                "P_HIST_2",
                "R_HIST_2",
                "P_HIST_3",
                "R_HIST_3",
                "P_HIST_4",
                "R_HIST_4",
                "P_HIST_5",
                "R_HIST_5",
                "P_HIST_6",
                "R_HIST_6",
            ],
        }
        state["questions"] = [replication, frontier]
        state["experiments"] = [
            {
                "id": f"X{index:06d}",
                "cycle": index,
                "question_id": replication["id"],
                "status": "completed",
                "learning_family": REPOSITORY_STABILITY_FAMILY,
                "observed_prediction_status": "confirmed",
                "evidence_refs": [f"P_HIST_{index}", f"R_HIST_{index}"],
            }
            for index in range(1, 7)
        ]
        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = {
            "family": REPOSITORY_STABILITY_FAMILY,
            "completed_trials": 6,
            "evaluable_trials": 6,
            "stable_observations": 6,
            "change_observations": 0,
            "inconclusive_trials": 0,
            "stability_rate": 1.0,
            "next_expected_status": "confirmed",
            "experiment_refs": [f"X{index:06d}" for index in range(1, 7)],
            "evidence_refs": list(frontier["source_evidence_refs"]),
        }
        first = update_agenda(
            state,
            legacy_question=frontier,
            cycle=20,
        )
        self.assertIsNotNone(first)
        frontier_thread_id = first["selected_thread_id"]

        baseline_observation = {
            "branch": "autonomous/growth",
            "baseline_fingerprint": "same-baseline",
            "tracked_files": 100,
            "python_files": 20,
            "python_source_lines": 5000,
            "test_files": 12,
            "working_tree_clean": True,
        }
        changed_observation = dict(
            baseline_observation,
            branch="diagnostic/alternate-context",
        )
        state["environment_snapshots"] = [
            dict(baseline_observation, cycle=20)
        ]

        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            core = AgentCore(store)
            prediction = core._make_prediction(
                state,
                baseline_observation,
                "2026-10-02T00:00:00+00:00",
            )
            state["predictions"].append(prediction)
            core._create_prediction_experiment(
                state,
                prediction,
                "2026-10-02T00:00:00+00:00",
            )
            store.save(state)

            interrupted = core.cycle(
                observation=changed_observation,
                strict_experiment_admission=True,
            )
            after_interrupt = store.load()
            returned = core.cycle(
                observation=changed_observation,
                strict_experiment_admission=True,
            )
            after_return = store.load()

        self.assertEqual(interrupted["drives"]["prediction_error"], 1.0)
        self.assertTrue(interrupted["agenda_decision"]["foreground_changed"])
        self.assertIn(
            frontier_thread_id,
            interrupted["agenda_decision"]["suspended_thread_ids"],
        )
        self.assertNotEqual(
            interrupted["agenda_decision"]["selected_thread_id"],
            frontier_thread_id,
        )
        self.assertEqual(
            after_interrupt["agenda"]["genuine_resumption_count"],
            0,
        )

        self.assertEqual(
            returned["agenda_decision"]["resumed_thread_id"],
            frontier_thread_id,
        )
        self.assertTrue(returned["agenda_decision"]["foreground_changed"])
        self.assertFalse(
            returned["agenda_decision"][
                "priority_change_supported_by_new_evidence"
            ]
        )
        self.assertEqual(
            returned["agenda_decision"]["selected"]["new_evidence_refs"],
            [],
        )
        self.assertEqual(
            after_return["agenda"]["genuine_resumption_count"],
            0,
        )

    def test_mature_empirical_frontier_feeds_phase42_persistent_agenda(self) -> None:
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 19
        state["empirical_learning"]["families"][
            REPOSITORY_STABILITY_FAMILY
        ] = {
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
                "P_HANDOFF_1",
                "R_HANDOFF_1",
                "P_HANDOFF_2",
                "R_HANDOFF_2",
                "P_HANDOFF_3",
                "R_HANDOFF_3",
            ],
        }
        replication = {
            "id": "Q_HANDOFF_REPLICATION",
            "text": "Will another comparable observation preserve the stable pattern?",
            "status": "open",
            "created_cycle": 1,
            "times_selected": 20,
            "last_selected_cycle": 19,
            "source": "repository_stability_prediction",
        }
        frontier = {
            "id": "Q_HANDOFF_FRONTIER",
            "text": (
                "Which distinct measurable relationship should be tested next "
                "to challenge or extend the mature empirical pattern?"
            ),
            "status": "open",
            "created_cycle": 2,
            "times_selected": 5,
            "last_selected_cycle": 18,
            "source": "empirical_frontier_transfer",
            "source_learning_family": REPOSITORY_STABILITY_FAMILY,
            "source_evidence_refs": [
                "P_HANDOFF_1",
                "R_HANDOFF_1",
                "P_HANDOFF_2",
                "R_HANDOFF_2",
            ],
        }
        state["questions"] = [replication, frontier]
        state["experiments"] = [
            {
                "id": "X_HANDOFF",
                "question_id": replication["id"],
                "status": "proposed",
                "readiness": "evidence_ready",
                "learning_family": REPOSITORY_STABILITY_FAMILY,
                "empirical_basis": state["empirical_learning"]["families"][
                    REPOSITORY_STABILITY_FAMILY
                ],
            }
        ]

        decision = update_agenda(
            state,
            legacy_question=replication,
            cycle=20,
        )

        self.assertIsNotNone(decision)
        self.assertEqual(
            decision["legacy_counterfactual"]["question_id"],
            replication["id"],
        )
        self.assertEqual(
            decision["selected"]["question_id"],
            frontier["id"],
        )
        self.assertTrue(decision["changed_choice"])
        self.assertTrue(decision["evidence_refs"])
        self.assertGreater(decision["decision_margin"], 0.0)
        self.assertEqual(len(state["agenda"]["threads"]), 2)


if __name__ == "__main__":
    unittest.main()
