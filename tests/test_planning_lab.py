from __future__ import annotations

import ast
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import agenttest.planning_lab as planning_lab
from agenttest.action_lab import step_action_lab
from agenttest.core import AgentCore
from agenttest.planning_lab import (
    ensure_planning_lab_state,
    step_planning_lab,
)
from agenttest.state import StateStore, initial_state, migrate_state


class PlanningLabTests(unittest.TestCase):
    def _phase32_ready_state(self) -> dict:
        state = initial_state()
        for cycle in range(1, 9):
            state["cycles"] = cycle
            state["generation"] = cycle
            step_action_lab(state)
        return state

    def test_insufficient_phase32_model_stays_fail_closed(self) -> None:
        state = initial_state()
        for cycle in range(1, 4):
            state["cycles"] = cycle
            state["generation"] = cycle
            step_action_lab(state)

        state["cycles"] = 4
        first = step_planning_lab(state)
        state["cycles"] = 5
        second = step_planning_lab(state)

        self.assertEqual(first["status"], "waiting_for_model")
        self.assertEqual(second["status"], "waiting_for_model")
        self.assertIsNone(first["action"])
        self.assertIsNone(second["action"])
        self.assertEqual(state["planning_lab"]["executions"], [])

    def test_first_planning_turn_bootstraps_from_phase32_and_creates_multistep_plan(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9

        result = step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        self.assertEqual(lab["bootstrapped_from_action_count"], 8)
        self.assertEqual(result["status"], "executing_plan")
        self.assertEqual(result["step_index"], 0)
        self.assertGreaterEqual(result["plan_length"], 3)
        self.assertLessEqual(result["plan_length"], 4)
        self.assertTrue(result["matched_prediction"])
        self.assertFalse(result["goal_reached"])
        self.assertEqual(len(lab["executions"]), 1)
        self.assertEqual(len(lab["plans"]), 1)
        self.assertEqual(
            lab["plans"][0]["model_samples"],
            {"north": 2, "east": 2, "south": 2, "west": 2},
        )

    def test_plan_persists_across_reload_and_executes_one_step_per_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = self._phase32_ready_state()
            state["cycles"] = 9
            state["generation"] = 9
            first = step_planning_lab(state)
            store.save(state)

            reloaded = store.load()
            first_plan_id = first["plan_id"]
            first_execution_count = len(reloaded["planning_lab"]["executions"])
            reloaded["cycles"] = 10
            reloaded["generation"] = 10
            second = step_planning_lab(reloaded)

            self.assertEqual(second["plan_id"], first_plan_id)
            self.assertEqual(second["step_index"], 1)
            self.assertEqual(
                len(reloaded["planning_lab"]["executions"]),
                first_execution_count + 1,
            )
            self.assertTrue(second["matched_prediction"])

    def test_goal_completes_from_persisted_multistep_plan(self) -> None:
        state = self._phase32_ready_state()
        reached = None
        plan_id = None

        for cycle in range(9, 20):
            state["cycles"] = cycle
            state["generation"] = cycle
            result = step_planning_lab(state)
            if plan_id is None:
                plan_id = result.get("plan_id")
            if result.get("goal_reached"):
                reached = result
                break

        self.assertIsNotNone(reached)
        self.assertEqual(reached["plan_id"], plan_id)
        self.assertTrue(reached["matched_prediction"])
        lab = state["planning_lab"]
        self.assertEqual(lab["status"], "goal_reached")
        completed = [goal for goal in lab["goals"] if goal.get("status") == "completed"]
        self.assertEqual(len(completed), 1)

    def test_prediction_mismatch_invalidates_plan_for_replanning(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        first = step_planning_lab(state)
        lab = state["planning_lab"]
        plan = next(item for item in lab["plans"] if item["id"] == first["plan_id"])

        next_index = int(plan["next_step_index"])
        self.assertLess(next_index, len(plan["predicted_states"]))
        plan["predicted_states"][next_index] = [99, 99]

        state["cycles"] = 10
        state["generation"] = 10
        second = step_planning_lab(state)

        self.assertFalse(second["matched_prediction"])
        self.assertTrue(second["replan_required"])
        self.assertEqual(lab["status"], "needs_replan")
        self.assertIsNone(lab["active_plan_id"])
        self.assertEqual(plan["status"], "invalidated")
        self.assertEqual(plan["invalidation_reason"], "prediction_mismatch")

        state["cycles"] = 11
        state["generation"] = 11
        third = step_planning_lab(state)
        replacement = next(
            item
            for item in lab["plans"]
            if item["id"] == third["plan_id"]
        )
        self.assertEqual(replacement["reason"], "replan_after_invalidation")

    def test_state_dependent_surprise_updates_model_and_replans_around_it(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        lab["position"] = [0, 2]
        lab["visit_counts"]["0,2"] = int(
            lab["visit_counts"].get("0,2", 0) or 0
        ) + 1
        lab["goals"] = [
            {
                "id": "PG000001",
                "assigned_cycle": 9,
                "target": [-2, 2],
                "status": "active",
                "selection": {
                    "kind": "test_fixture",
                    "prior_visits": 0,
                    "planned_distance": 2,
                    "preferred_step_range": [3, 4],
                },
            }
        ]
        lab["plans"] = [
            {
                "id": "PP000001",
                "goal_id": "PG000001",
                "created_cycle": 9,
                "start": [0, 2],
                "goal": [-2, 2],
                "actions": ["south", "south"],
                "predicted_states": [[-1, 2], [-2, 2]],
                "next_step_index": 0,
                "status": "active",
                "reason": "test_fixture",
                "model_samples": {
                    action: int(
                        lab["learned_effects"][action]["unblocked_samples"]
                    )
                    for action in lab["learned_effects"]
                },
            }
        ]
        lab["executions"] = []
        lab["model_revisions"] = []
        lab["active_goal_id"] = "PG000001"
        lab["active_plan_id"] = "PP000001"
        lab["status"] = "executing_plan"

        state["cycles"] = 10
        state["generation"] = 10
        mismatch = step_planning_lab(state)

        self.assertFalse(mismatch["matched_prediction"])
        self.assertTrue(mismatch["replan_required"])
        self.assertTrue(mismatch["blocked"])
        self.assertEqual(mismatch["after"], [0, 2])
        self.assertEqual(mismatch["model_revision_id"], "MR000001")
        self.assertEqual(lab["status"], "needs_replan")
        self.assertIsNone(lab["active_plan_id"])
        self.assertTrue(lab["state_effects"]["0,2|south"]["blocked"])
        self.assertEqual(
            lab["model_revisions"][0]["trigger_execution_id"],
            mismatch["id"],
        )

        state["cycles"] = 11
        state["generation"] = 11
        recovered = step_planning_lab(state)
        replacement = next(
            item
            for item in lab["plans"]
            if item["id"] == recovered["plan_id"]
        )

        self.assertEqual(replacement["reason"], "replan_after_invalidation")
        self.assertNotEqual(replacement["id"], "PP000001")
        self.assertEqual(recovered["action"], "east")
        self.assertTrue(recovered["matched_prediction"])
        self.assertEqual(lab["status"], "executing_plan")

    def test_evidence_valued_curiosity_retests_single_sample_exception_once(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        lab["position"] = [0, 2]
        lab["visit_counts"]["0,2"] = int(
            lab["visit_counts"].get("0,2", 0) or 0
        ) + 1
        lab["transition_observations"].append(
            {
                "source": "planning_lab",
                "source_id": "PX_TEST_BLOCK",
                "cycle": 9,
                "action": "south",
                "before": [0, 2],
                "after": [0, 2],
                "delta": [0, 0],
                "blocked": True,
                "world_version": lab["world_version"],
            }
        )
        lab["model_revisions"] = [
            {
                "id": "MR000001",
                "cycle": 9,
                "trigger_execution_id": "PX_TEST_BLOCK",
                "goal_id": "PG_PREVIOUS",
                "plan_id": "PP_PREVIOUS",
                "state_action_key": "0,2|south",
                "before": [0, 2],
                "action": "south",
                "predicted_after": [-1, 2],
                "observed_after": [0, 2],
                "observed_delta": [0, 0],
                "observed_blocked": True,
                "world_version": lab["world_version"],
                "status": "state_evidence_recorded",
            }
        ]
        lab["goals"] = [
            {
                "id": "PG000001",
                "assigned_cycle": 9,
                "target": [-2, 2],
                "status": "active",
                "selection": {
                    "kind": "test_fixture",
                    "prior_visits": 0,
                    "planned_distance": 4,
                    "preferred_step_range": [3, 4],
                },
            }
        ]
        lab["plans"] = [
            {
                "id": "PP000001",
                "goal_id": "PG000001",
                "created_cycle": 9,
                "start": [0, 2],
                "goal": [-2, 2],
                "actions": ["east", "south", "south", "west"],
                "predicted_states": [[0, 1], [-1, 1], [-2, 1], [-2, 2]],
                "next_step_index": 0,
                "status": "active",
                "reason": "replan_after_invalidation",
                "world_version": lab["world_version"],
                "model_samples": {
                    action: int(
                        lab["learned_effects"].get(action, {}).get(
                            "unblocked_samples",
                            0,
                        )
                    )
                    for action in ("north", "east", "south", "west")
                },
            }
        ]
        lab["active_goal_id"] = "PG000001"
        lab["active_plan_id"] = "PP000001"
        lab["status"] = "executing_plan"

        state["cycles"] = 10
        state["generation"] = 10
        probe = step_planning_lab(state)

        self.assertEqual(probe["execution_kind"], "curiosity_probe")
        self.assertEqual(probe["curiosity_probe_id"], "CP000001")
        self.assertEqual(probe["source_model_revision_id"], "MR000001")
        self.assertEqual(probe["action"], "south")
        self.assertTrue(probe["blocked"])
        self.assertEqual(probe["before"], [0, 2])
        self.assertEqual(probe["after"], [0, 2])
        self.assertTrue(probe["matched_prediction"])
        self.assertGreater(probe["information_value"], probe["goal_delay_cost"])
        self.assertEqual(probe["state_samples_before"], 1)
        self.assertEqual(probe["state_samples_after"], 2)
        self.assertEqual(lab["plans"][0]["next_step_index"], 0)
        self.assertEqual(lab["active_plan_id"], "PP000001")
        self.assertEqual(lab["model_revisions"][0]["curiosity_status"], "probe_confirmed")

        state["cycles"] = 11
        state["generation"] = 11
        resumed = step_planning_lab(state)

        self.assertNotEqual(resumed.get("execution_kind"), "curiosity_probe")
        self.assertEqual(resumed["plan_id"], "PP000001")
        self.assertEqual(resumed["action"], "east")
        self.assertEqual(resumed["step_index"], 0)
        self.assertEqual(len(lab["curiosity_probes"]), 1)

    def test_curiosity_probe_refutation_invalidates_plan_and_preserves_prior_evidence(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        lab["position"] = [0, 1]
        lab["transition_observations"].append(
            {
                "source": "planning_lab",
                "source_id": "PX_TEST_FALSE_BLOCK",
                "cycle": 9,
                "action": "south",
                "before": [0, 1],
                "after": [0, 1],
                "delta": [0, 0],
                "blocked": True,
                "world_version": lab["world_version"],
            }
        )
        lab["model_revisions"] = [
            {
                "id": "MR000001",
                "cycle": 9,
                "trigger_execution_id": "PX_TEST_FALSE_BLOCK",
                "goal_id": "PG_PREVIOUS",
                "plan_id": "PP_PREVIOUS",
                "state_action_key": "0,1|south",
                "before": [0, 1],
                "action": "south",
                "predicted_after": [-1, 1],
                "observed_after": [0, 1],
                "observed_delta": [0, 0],
                "observed_blocked": True,
                "world_version": lab["world_version"],
                "status": "state_evidence_recorded",
            }
        ]
        lab["goals"] = [
            {
                "id": "PG000001",
                "assigned_cycle": 9,
                "target": [0, -2],
                "status": "active",
                "selection": {
                    "kind": "test_fixture",
                    "prior_visits": 0,
                    "planned_distance": 3,
                    "preferred_step_range": [3, 4],
                },
            }
        ]
        lab["plans"] = [
            {
                "id": "PP000001",
                "goal_id": "PG000001",
                "created_cycle": 9,
                "start": [0, 1],
                "goal": [0, -2],
                "actions": ["east", "east", "east"],
                "predicted_states": [[0, 0], [0, -1], [0, -2]],
                "next_step_index": 0,
                "status": "active",
                "reason": "test_fixture",
                "world_version": lab["world_version"],
                "model_samples": {},
            }
        ]
        lab["active_goal_id"] = "PG000001"
        lab["active_plan_id"] = "PP000001"
        lab["status"] = "executing_plan"

        state["cycles"] = 10
        state["generation"] = 10
        probe = step_planning_lab(state)

        self.assertEqual(probe["execution_kind"], "curiosity_probe")
        self.assertFalse(probe["matched_prediction"])
        self.assertEqual(probe["after"], [-1, 1])
        self.assertTrue(probe["replan_required"])
        self.assertEqual(probe["model_revision_id"], "MR000002")
        self.assertEqual(lab["status"], "needs_replan")
        self.assertIsNone(lab["active_plan_id"])
        self.assertEqual(lab["plans"][0]["invalidation_reason"], "curiosity_probe_changed_state")
        self.assertEqual(len(lab["model_revisions"]), 2)
        self.assertEqual(
            lab["model_revisions"][0]["curiosity_status"],
            "probe_refuted",
        )
        self.assertEqual(
            lab["model_revisions"][1]["trigger_curiosity_probe_id"],
            "CP000001",
        )
        self.assertEqual(
            lab["model_revisions"][1]["source_model_revision_id"],
            "MR000001",
        )

    def test_transfer_probe_uses_zero_target_evidence_and_preserves_source_plan(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        lab["position"] = [0, 0]
        lab["transition_observations"].extend(
            [
                {
                    "source": "planning_lab",
                    "source_id": "PX_SOURCE_BLOCK",
                    "cycle": 9,
                    "action": "south",
                    "before": [0, 2],
                    "after": [0, 2],
                    "delta": [0, 0],
                    "blocked": True,
                    "world_version": lab["world_version"],
                },
                {
                    "source": "curiosity_probe",
                    "source_id": "CP_SOURCE_CONFIRM",
                    "cycle": 9,
                    "action": "south",
                    "before": [0, 2],
                    "after": [0, 2],
                    "delta": [0, 0],
                    "blocked": True,
                    "world_version": lab["world_version"],
                },
            ]
        )
        lab["model_revisions"] = [
            {
                "id": "MR000001",
                "cycle": 9,
                "trigger_execution_id": "PX_SOURCE_BLOCK",
                "goal_id": "PG_SOURCE",
                "plan_id": "PP_SOURCE",
                "state_action_key": "0,2|south",
                "before": [0, 2],
                "action": "south",
                "predicted_after": [-1, 2],
                "observed_after": [0, 2],
                "observed_delta": [0, 0],
                "observed_blocked": True,
                "world_version": lab["world_version"],
                "status": "state_evidence_recorded",
                "curiosity_status": "probe_confirmed",
                "curiosity_probe_ids": ["CP_SOURCE_CONFIRM"],
            }
        ]
        lab["goals"] = [
            {
                "id": "PG_TRANSFER",
                "assigned_cycle": 9,
                "target": [1, 1],
                "status": "active",
                "selection": {
                    "kind": "test_fixture",
                    "prior_visits": 0,
                    "planned_distance": 2,
                    "preferred_step_range": [3, 4],
                },
            }
        ]
        lab["plans"] = [
            {
                "id": "PP_TRANSFER",
                "goal_id": "PG_TRANSFER",
                "created_cycle": 9,
                "start": [0, 0],
                "goal": [1, 1],
                "actions": ["north", "west"],
                "predicted_states": [[1, 0], [1, 1]],
                "next_step_index": 0,
                "status": "active",
                "reason": "test_fixture",
                "world_version": lab["world_version"],
                "model_samples": {},
            }
        ]
        lab["active_goal_id"] = "PG_TRANSFER"
        lab["active_plan_id"] = "PP_TRANSFER"
        lab["status"] = "executing_plan"
        source_observation_count = len(lab["transition_observations"])

        state["cycles"] = 10
        state["generation"] = 10
        probe = step_planning_lab(state)

        self.assertEqual(probe["execution_kind"], "transfer_probe")
        self.assertEqual(probe["transfer_decision_id"], "TD000001")
        self.assertEqual(probe["transfer_probe_id"], "TP000001")
        self.assertEqual(probe["source_model_revision_id"], "MR000001")
        self.assertEqual(probe["before"], [0, 2])
        self.assertEqual(probe["action"], "south")
        self.assertEqual(probe["target_evidence_samples_before"], 0)
        self.assertEqual(probe["target_evidence_samples_after"], 1)
        self.assertEqual(probe["source_specific_prediction"], [0, 2])
        self.assertEqual(probe["counterfactual_prediction"], [0, 2])
        self.assertEqual(probe["predicted_after"], [-1, 2])
        self.assertEqual(probe["after"], [-1, 2])
        self.assertTrue(probe["matched_prediction"])
        self.assertEqual(
            probe["interpretation"],
            "general_effect_transferred_source_exception_did_not",
        )
        self.assertTrue(probe["source_plan_preserved"])
        self.assertEqual(lab["position"], [0, 0])
        self.assertEqual(lab["active_plan_id"], "PP_TRANSFER")
        self.assertEqual(lab["plans"][0]["next_step_index"], 0)
        self.assertEqual(
            len(lab["transition_observations"]),
            source_observation_count,
        )

        state["cycles"] = 11
        state["generation"] = 11
        resumed = step_planning_lab(state)

        self.assertNotEqual(resumed.get("execution_kind"), "transfer_probe")
        self.assertEqual(resumed["plan_id"], "PP_TRANSFER")
        self.assertEqual(resumed["step_index"], 0)
        self.assertEqual(resumed["action"], "north")
        self.assertEqual(len(lab["transfer_probes"]), 1)

    def test_transfer_evidence_persists_across_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = self._phase32_ready_state()
            lab = ensure_planning_lab_state(state)
            lab["transfer_decisions"] = [
                {
                    "id": "TD_PERSIST",
                    "source_model_revision_id": "MR_PERSIST",
                    "target_evidence_samples_before": 0,
                    "selected_prior": "general_action_effect",
                }
            ]
            lab["transfer_probes"] = [
                {
                    "id": "TP_PERSIST",
                    "decision_id": "TD_PERSIST",
                    "source_model_revision_id": "MR_PERSIST",
                    "target_evidence_samples_after": 1,
                    "source_plan_preserved": True,
                }
            ]
            lab["last_transfer_probe_cycle"] = 42
            store.save(state)
            reloaded = store.load()

            self.assertEqual(
                reloaded["planning_lab"]["transfer_decisions"][0]["id"],
                "TD_PERSIST",
            )
            self.assertEqual(
                reloaded["planning_lab"]["transfer_probes"][0]["id"],
                "TP_PERSIST",
            )
            self.assertEqual(
                reloaded["planning_lab"]["last_transfer_probe_cycle"],
                42,
            )

    def test_phase38_migration_activates_only_existing_persisted_state(self) -> None:
        fresh = initial_state()
        self.assertIsNone(
            fresh["planning_lab"]["self_experiment_started_cycle"]
        )

        old = initial_state()
        old["schema_version"] = 20
        old["cycles"] = 50
        old["generation"] = 50
        old["planning_lab"]["self_experiment_started_cycle"] = None
        migrated = migrate_state(old)

        self.assertEqual(migrated["schema_version"], 24)
        self.assertEqual(
            migrated["planning_lab"]["self_experiment_started_cycle"],
            50,
        )

    def test_self_generated_experiment_forms_falsifiable_hypothesis_and_replans(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        lab["transition_observations"] = [
            item
            for item in lab["transition_observations"]
            if item.get("world_version") != lab["world_version"]
        ]
        lab["position"] = [1, 0]
        lab["visit_counts"]["1,0"] = int(
            lab["visit_counts"].get("1,0", 0) or 0
        ) + 1
        lab["goals"] = [
            {
                "id": "PG_SELF",
                "assigned_cycle": 9,
                "target": [1, 2],
                "status": "active",
                "selection": {
                    "kind": "test_fixture",
                    "prior_visits": 0,
                    "planned_distance": 3,
                    "preferred_step_range": [3, 4],
                },
            }
        ]
        lab["plans"] = [
            {
                "id": "PP_SELF",
                "goal_id": "PG_SELF",
                "created_cycle": 9,
                "start": [0, 0],
                "goal": [1, 2],
                "actions": ["north", "west", "west"],
                "predicted_states": [[1, 0], [1, 1], [1, 2]],
                "next_step_index": 1,
                "status": "active",
                "reason": "test_fixture",
                "world_version": lab["world_version"],
                "model_samples": {},
            }
        ]
        lab["active_goal_id"] = "PG_SELF"
        lab["active_plan_id"] = "PP_SELF"
        lab["status"] = "executing_plan"
        lab["self_experiment_started_cycle"] = 8

        state["cycles"] = 10
        state["generation"] = 10
        experiment = step_planning_lab(state)

        self.assertEqual(
            experiment["execution_kind"],
            "self_generated_experiment",
        )
        self.assertEqual(
            experiment["self_experiment_decision_id"],
            "SED000001",
        )
        self.assertEqual(experiment["self_experiment_id"], "SE000001")
        self.assertEqual(experiment["action"], "north")
        self.assertEqual(experiment["before"], [1, 0])
        self.assertEqual(experiment["predicted_after"], [2, 0])
        self.assertEqual(experiment["after"], [2, 0])
        self.assertTrue(experiment["matched_prediction"])
        self.assertEqual(
            experiment["interpretation"],
            "hypothesis_supported",
        )
        self.assertEqual(experiment["state_samples_before"], 0)
        self.assertEqual(experiment["state_samples_after"], 1)
        self.assertTrue(experiment["source_observation_refs"])
        self.assertIn("At state [1, 0], action north", experiment["hypothesis"])
        self.assertIn(
            "Any observed result other than [2, 0]",
            experiment["falsification"],
        )
        self.assertGreater(
            experiment["information_value"],
            experiment["goal_delay_cost"],
        )
        self.assertTrue(experiment["replan_required"])
        self.assertEqual(lab["status"], "needs_replan")
        self.assertIsNone(lab["active_plan_id"])
        self.assertEqual(
            lab["plans"][0]["invalidation_reason"],
            "self_experiment_changed_state",
        )

        state["cycles"] = 11
        state["generation"] = 11
        resumed = step_planning_lab(state)
        replacement = next(
            item
            for item in lab["plans"]
            if item.get("id") == resumed.get("plan_id")
        )

        self.assertNotEqual(
            resumed.get("execution_kind"),
            "self_generated_experiment",
        )
        self.assertEqual(resumed["goal_id"], "PG_SELF")
        self.assertEqual(replacement["reason"], "replan_after_invalidation")
        self.assertEqual(len(lab["self_experiments"]), 1)

    def test_self_generated_experiment_accepts_refutation_and_preserves_valid_plan(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        lab["transition_observations"] = [
            item
            for item in lab["transition_observations"]
            if item.get("world_version") != lab["world_version"]
        ]
        lab["transition_observations"].extend(
            [
                {
                    "source": "test_fixture",
                    "source_id": "N_EXTRA",
                    "cycle": 9,
                    "action": "north",
                    "before": [0, 0],
                    "after": [1, 0],
                    "delta": [1, 0],
                    "blocked": False,
                    "world_version": "bounded-world-v1",
                },
                {
                    "source": "test_fixture",
                    "source_id": "W_EXTRA",
                    "cycle": 9,
                    "action": "west",
                    "before": [0, 0],
                    "after": [0, 1],
                    "delta": [0, 1],
                    "blocked": False,
                    "world_version": "bounded-world-v1",
                },
            ]
        )
        lab["position"] = [0, 2]
        lab["visit_counts"]["0,2"] = int(
            lab["visit_counts"].get("0,2", 0) or 0
        ) + 1
        lab["goals"] = [
            {
                "id": "PG_REFUTE",
                "assigned_cycle": 9,
                "target": [0, 0],
                "status": "active",
                "selection": {
                    "kind": "test_fixture",
                    "prior_visits": 0,
                    "planned_distance": 3,
                    "preferred_step_range": [3, 4],
                },
            }
        ]
        lab["plans"] = [
            {
                "id": "PP_REFUTE",
                "goal_id": "PG_REFUTE",
                "created_cycle": 9,
                "start": [-1, 2],
                "goal": [0, 0],
                "actions": ["north", "east", "east"],
                "predicted_states": [[0, 2], [0, 1], [0, 0]],
                "next_step_index": 1,
                "status": "active",
                "reason": "test_fixture",
                "world_version": lab["world_version"],
                "model_samples": {},
            }
        ]
        lab["active_goal_id"] = "PG_REFUTE"
        lab["active_plan_id"] = "PP_REFUTE"
        lab["status"] = "executing_plan"
        lab["self_experiment_started_cycle"] = 8

        state["cycles"] = 10
        state["generation"] = 10
        experiment = step_planning_lab(state)

        self.assertEqual(
            experiment["execution_kind"],
            "self_generated_experiment",
        )
        self.assertEqual(experiment["action"], "south")
        self.assertEqual(experiment["before"], [0, 2])
        self.assertEqual(experiment["predicted_after"], [-1, 2])
        self.assertEqual(experiment["after"], [0, 2])
        self.assertFalse(experiment["matched_prediction"])
        self.assertEqual(
            experiment["interpretation"],
            "hypothesis_refuted",
        )
        self.assertFalse(experiment["replan_required"])
        self.assertEqual(experiment["model_revision_id"], "MR000001")
        self.assertEqual(lab["active_plan_id"], "PP_REFUTE")
        self.assertEqual(lab["plans"][0]["next_step_index"], 1)
        self.assertTrue(lab["state_effects"]["0,2|south"]["blocked"])
        self.assertEqual(
            lab["model_revisions"][0]["trigger_self_experiment_id"],
            "SE000001",
        )

        state["cycles"] = 11
        state["generation"] = 11
        resumed = step_planning_lab(state)

        self.assertNotEqual(
            resumed.get("execution_kind"),
            "self_generated_experiment",
        )
        self.assertEqual(resumed["plan_id"], "PP_REFUTE")
        self.assertEqual(resumed["step_index"], 1)
        self.assertEqual(resumed["action"], "east")
        self.assertEqual(len(lab["self_experiments"]), 1)

    def test_self_generated_experiment_state_persists_across_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = self._phase32_ready_state()
            lab = ensure_planning_lab_state(state)
            lab["self_experiment_started_cycle"] = 8
            lab["self_experiment_decisions"] = [
                {
                    "id": "SED_PERSIST",
                    "hypothesis": "persist me",
                    "falsification": "persist falsifier",
                }
            ]
            lab["self_experiments"] = [
                {
                    "id": "SE_PERSIST",
                    "decision_id": "SED_PERSIST",
                    "interpretation": "hypothesis_supported",
                }
            ]
            lab["last_self_experiment_cycle"] = 9
            store.save(state)
            reloaded = store.load()

            self.assertEqual(
                reloaded["planning_lab"]["self_experiment_decisions"][0]["id"],
                "SED_PERSIST",
            )
            self.assertEqual(
                reloaded["planning_lab"]["self_experiments"][0]["id"],
                "SE_PERSIST",
            )
            self.assertEqual(
                reloaded["planning_lab"]["last_self_experiment_cycle"],
                9,
            )

    def test_phase39_migration_activates_objective_selection_prospectively(self) -> None:
        state = self._phase32_ready_state()
        state["schema_version"] = 21
        state["cycles"] = 50
        state["generation"] = 50
        lab = ensure_planning_lab_state(state)
        lab["objective_selection_started_cycle"] = None

        migrated = migrate_state(state)

        self.assertEqual(migrated["schema_version"], 24)
        self.assertEqual(
            migrated["planning_lab"]["objective_selection_started_cycle"],
            50,
        )
        self.assertEqual(migrated["planning_lab"]["objective_decisions"], [])
        self.assertIsNone(
            migrated["planning_lab"]["last_objective_selection_cycle"]
        )
        self.assertEqual(
            migrated["planning_lab"]["objective_realization_started_cycle"],
            50,
        )
        self.assertEqual(
            migrated["planning_lab"]["objective_realization_decisions"],
            [],
        )
        self.assertEqual(migrated["planning_lab"]["objective_realizations"], [])

    def test_phase40_precommits_then_realizes_objective_information(self) -> None:
        state = self._phase32_ready_state()
        lab = ensure_planning_lab_state(state)
        self.assertTrue(planning_lab._bootstrap_from_action_lab(state, lab))

        lab["position"] = [0, 0]
        lab["visit_counts"] = {"0,0": 1}
        lab["goals"] = [
            {
                "id": "PG_PHASE40",
                "assigned_cycle": 11,
                "completed_cycle": 14,
                "status": "completed",
                "target": [0, 0],
                "selection": {
                    "kind": "self_selected_bounded_objective",
                    "objective_decision_id": "OD_PHASE40",
                },
            }
        ]
        lab["objective_decisions"] = [
            {
                "id": "OD_PHASE40",
                "cycle": 11,
                "changed_choice": True,
                "selected": {
                    "target": [0, 0],
                    "unseen_target_actions": 4,
                    "information_value": 2.0,
                },
            }
        ]
        lab["active_goal_id"] = None
        lab["active_plan_id"] = None
        lab["objective_realization_started_cycle"] = 10
        lab["objective_realization_decisions"] = []
        lab["objective_realizations"] = []
        lab["active_objective_realization_id"] = None
        lab["status"] = "goal_reached"

        state["cycles"] = 15
        state["generation"] = 15
        precommit = step_planning_lab(state)

        self.assertEqual(
            precommit["execution_kind"],
            "objective_information_precommit",
        )
        self.assertIsNone(precommit["action"])
        self.assertEqual(lab["position"], [0, 0])
        self.assertEqual(len(lab["objective_realization_decisions"]), 1)
        decision = lab["objective_realization_decisions"][0]
        self.assertEqual(decision["status"], "precommitted")
        self.assertTrue(decision["hypothesis"])
        self.assertTrue(decision["falsification"])
        self.assertEqual(decision["state_samples_before"], 0)
        self.assertEqual(decision["expected_information_gain"], 1.0)

        state["cycles"] = 16
        state["generation"] = 16
        realized = step_planning_lab(state)

        self.assertEqual(
            realized["execution_kind"],
            "objective_information_realization",
        )
        self.assertIsNotNone(realized["action"])
        self.assertEqual(len(lab["objective_realizations"]), 1)
        observation = lab["objective_realizations"][0]
        self.assertEqual(observation["decision_id"], decision["id"])
        self.assertEqual(observation["state_samples_before"], 0)
        self.assertEqual(observation["state_samples_after"], 1)
        self.assertEqual(observation["realized_information_gain"], 1.0)
        self.assertIn(
            observation["interpretation"],
            {"hypothesis_supported", "hypothesis_refuted"},
        )
        self.assertEqual(decision["status"], "completed")
        self.assertIsNone(lab["active_objective_realization_id"])

    def test_phase40_can_realize_boundary_exception_information(self) -> None:
        state = self._phase32_ready_state()
        lab = ensure_planning_lab_state(state)
        self.assertTrue(planning_lab._bootstrap_from_action_lab(state, lab))

        world_version = lab["world_version"]
        lab["transition_observations"] = [
            {
                "source": "test_fixture",
                "source_id": "P40_N1",
                "cycle": 8,
                "action": "north",
                "before": [-1, 0],
                "after": [0, 0],
                "delta": [1, 0],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_N2",
                "cycle": 8,
                "action": "north",
                "before": [0, 0],
                "after": [1, 0],
                "delta": [1, 0],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_S1",
                "cycle": 8,
                "action": "south",
                "before": [1, 0],
                "after": [0, 0],
                "delta": [-1, 0],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_S2",
                "cycle": 8,
                "action": "south",
                "before": [0, 0],
                "after": [-1, 0],
                "delta": [-1, 0],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_E1",
                "cycle": 8,
                "action": "east",
                "before": [0, 1],
                "after": [0, 0],
                "delta": [0, -1],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_E2",
                "cycle": 8,
                "action": "east",
                "before": [0, 0],
                "after": [0, -1],
                "delta": [0, -1],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_W1",
                "cycle": 8,
                "action": "west",
                "before": [0, -1],
                "after": [0, 0],
                "delta": [0, 1],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_W2",
                "cycle": 8,
                "action": "west",
                "before": [0, 0],
                "after": [0, 1],
                "delta": [0, 1],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_LOCAL_N",
                "cycle": 9,
                "action": "north",
                "before": [-2, 1],
                "after": [-1, 1],
                "delta": [1, 0],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_LOCAL_E",
                "cycle": 9,
                "action": "east",
                "before": [-2, 1],
                "after": [-2, 0],
                "delta": [0, -1],
                "blocked": False,
                "world_version": world_version,
            },
            {
                "source": "test_fixture",
                "source_id": "P40_LOCAL_W",
                "cycle": 9,
                "action": "west",
                "before": [-2, 1],
                "after": [-2, 2],
                "delta": [0, 1],
                "blocked": False,
                "world_version": world_version,
            },
        ]
        lab["position"] = [-2, 1]
        lab["visit_counts"] = {"-2,1": 1}
        lab["goals"] = [
            {
                "id": "PG_PHASE40_BOUNDARY",
                "assigned_cycle": 11,
                "completed_cycle": 14,
                "status": "completed",
                "target": [-2, 1],
                "selection": {
                    "kind": "self_selected_bounded_objective",
                    "objective_decision_id": "OD_PHASE40_BOUNDARY",
                },
            }
        ]
        lab["objective_decisions"] = [
            {
                "id": "OD_PHASE40_BOUNDARY",
                "cycle": 11,
                "changed_choice": True,
            }
        ]
        lab["active_goal_id"] = None
        lab["active_plan_id"] = None
        lab["objective_realization_started_cycle"] = 10
        lab["objective_realization_decisions"] = []
        lab["objective_realizations"] = []
        lab["active_objective_realization_id"] = None
        lab["status"] = "goal_reached"

        state["cycles"] = 15
        state["generation"] = 15
        precommit = step_planning_lab(state)

        self.assertEqual(
            precommit["execution_kind"],
            "objective_information_precommit",
        )
        decision = lab["objective_realization_decisions"][0]
        self.assertEqual(decision["action"], "south")
        self.assertEqual(decision["predicted_after"], [-3, 1])
        self.assertEqual(decision["state_samples_before"], 0)

        state["cycles"] = 16
        state["generation"] = 16
        realized = step_planning_lab(state)

        self.assertEqual(realized["action"], "south")
        self.assertTrue(realized["blocked"])
        self.assertEqual(realized["after"], [-2, 1])
        self.assertFalse(realized["matched_prediction"])
        self.assertEqual(realized["interpretation"], "hypothesis_refuted")
        self.assertEqual(realized["state_samples_before"], 0)
        self.assertEqual(realized["state_samples_after"], 1)
        self.assertEqual(realized["realized_information_gain"], 1.0)

    def test_phase39_selects_bounded_objective_with_explicit_counterfactual(self) -> None:
        state = self._phase32_ready_state()
        lab = ensure_planning_lab_state(state)
        self.assertTrue(planning_lab._bootstrap_from_action_lab(state, lab))

        lab["position"] = [0, 0]
        lab["visit_counts"] = {"0,0": 1}
        lab["goals"] = [
            {
                "id": "PG_REC_A",
                "status": "completed",
                "target": [1, 0],
            },
            {
                "id": "PG_REC_B",
                "status": "completed",
                "target": [0, 1],
            },
        ]
        lab["plans"] = []
        lab["active_goal_id"] = None
        lab["active_plan_id"] = None
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
        lab["objective_selection_started_cycle"] = 8
        lab["objective_decisions"] = []
        lab["last_objective_selection_cycle"] = None

        world_version = lab["world_version"]
        lab["transition_observations"].extend(
            [
                {
                    "source": "test_fixture",
                    "source_id": "OBJ_N",
                    "cycle": 8,
                    "action": "north",
                    "before": [-2, -2],
                    "after": [-1, -2],
                    "delta": [1, 0],
                    "blocked": False,
                    "world_version": world_version,
                },
                {
                    "source": "test_fixture",
                    "source_id": "OBJ_E",
                    "cycle": 8,
                    "action": "east",
                    "before": [-2, -2],
                    "after": [-2, -2],
                    "delta": [0, 0],
                    "blocked": True,
                    "world_version": world_version,
                },
                {
                    "source": "test_fixture",
                    "source_id": "OBJ_S",
                    "cycle": 8,
                    "action": "south",
                    "before": [-2, -2],
                    "after": [-2, -2],
                    "delta": [0, 0],
                    "blocked": True,
                    "world_version": world_version,
                },
                {
                    "source": "test_fixture",
                    "source_id": "OBJ_W",
                    "cycle": 8,
                    "action": "west",
                    "before": [-2, -2],
                    "after": [-2, -1],
                    "delta": [0, 1],
                    "blocked": False,
                    "world_version": world_version,
                },
            ]
        )

        goal = planning_lab._choose_goal(lab, 9)
        decision = lab["objective_decisions"][0]

        self.assertIsNotNone(goal)
        self.assertEqual(decision["status"], "objective_changed_choice")
        self.assertTrue(decision["changed_choice"])
        self.assertEqual(
            decision["counterfactual"]["target"],
            [-2, -2],
        )
        self.assertNotEqual(
            decision["selected"]["target"],
            decision["counterfactual"]["target"],
        )
        self.assertGreater(decision["decision_margin"], 0.0)
        self.assertEqual(
            decision["phase38_recovery_refs"],
            ["SE_REC_A", "SE_REC_B"],
        )
        self.assertGreaterEqual(decision["candidate_count"], 2)
        self.assertTrue(decision["candidate_summaries"])
        self.assertEqual(
            goal["selection"]["kind"],
            "self_selected_bounded_objective",
        )
        self.assertEqual(
            goal["selection"]["objective_decision_id"],
            decision["id"],
        )
        self.assertEqual(
            goal["selection"]["counterfactual_target"],
            [-2, -2],
        )

        goal["status"] = "completed"
        lab["active_goal_id"] = None
        second_goal = planning_lab._choose_goal(lab, 10)

        self.assertEqual(len(lab["objective_decisions"]), 1)
        self.assertEqual(
            second_goal["selection"]["kind"],
            "least_visited_farthest_reachable",
        )

    def test_phase41_activation_is_prospective_on_schema24_migration(self) -> None:
        state = self._phase32_ready_state()
        lab = ensure_planning_lab_state(state)
        state["schema_version"] = 23
        state["cycles"] = 50
        state["generation"] = 50
        lab["outcome_valuation_started_cycle"] = None

        migrated = migrate_state(state)

        self.assertEqual(migrated["schema_version"], 24)
        self.assertEqual(
            migrated["planning_lab"]["outcome_valuation_started_cycle"],
            50,
        )

        migrated["cycles"] = 51
        migrated["generation"] = 51
        migrate_state(migrated)
        self.assertEqual(
            migrated["planning_lab"]["outcome_valuation_started_cycle"],
            50,
        )

    def test_phase41_outcomes_change_objective_choice_with_phase39_counterfactual(self) -> None:
        state = self._phase32_ready_state()
        lab = ensure_planning_lab_state(state)
        self.assertTrue(planning_lab._bootstrap_from_action_lab(state, lab))

        lab["position"] = [0, 0]
        lab["visit_counts"] = {
            f"{x},{y}": 100
            for x in range(-2, 3)
            for y in range(-2, 3)
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
        lab["objective_selection_started_cycle"] = 8
        lab["last_objective_selection_cycle"] = None
        lab["objective_decisions"] = []
        lab["outcome_valuation_started_cycle"] = 8

        world_version = lab["world_version"]
        lab["transition_observations"].extend(
            [
                {
                    "source": "phase41_fixture",
                    "source_id": "P41_A_NORTH",
                    "cycle": 8,
                    "action": "north",
                    "before": [-2, -1],
                    "after": [-1, -1],
                    "delta": [1, 0],
                    "blocked": False,
                    "world_version": world_version,
                },
                {
                    "source": "phase41_fixture",
                    "source_id": "P41_B_EAST",
                    "cycle": 8,
                    "action": "east",
                    "before": [-2, 2],
                    "after": [-2, 1],
                    "delta": [0, -1],
                    "blocked": False,
                    "world_version": world_version,
                },
            ]
        )
        lab["objective_realizations"] = [
            {
                "id": "OI_N1",
                "action": "north",
                "realized_information_gain": 1.0,
                "interpretation": "hypothesis_refuted",
            },
            {
                "id": "OI_N2",
                "action": "north",
                "realized_information_gain": 1.0,
                "interpretation": "hypothesis_supported",
            },
            {
                "id": "OI_E1",
                "action": "east",
                "realized_information_gain": 1.0,
                "interpretation": "hypothesis_refuted",
            },
        ]

        goal = planning_lab._choose_goal(lab, 9)
        decision = lab["objective_decisions"][0]

        self.assertIsNotNone(goal)
        self.assertEqual(
            decision["policy_version"],
            "outcome-aware-objective-valuation-v1",
        )
        self.assertTrue(decision["outcome_changed_choice"])
        self.assertEqual(
            decision["phase39_counterfactual"]["target"],
            [-2, -1],
        )
        self.assertEqual(decision["selected"]["target"], [-2, 2])
        self.assertEqual(
            decision["selected"]["phase40_realization_action"],
            "north",
        )
        self.assertEqual(
            decision["selected"]["phase40_outcome_refs"],
            ["OI_N1", "OI_N2"],
        )
        self.assertGreater(decision["outcome_decision_margin"], 0.0)
        self.assertEqual(
            goal["selection"]["kind"],
            "outcome_aware_bounded_objective",
        )
        self.assertEqual(
            goal["selection"]["objective_decision_id"],
            decision["id"],
        )

    def test_completed_route_consolidates_citable_episodic_memory(self) -> None:
        state = self._phase32_ready_state()
        reached = None
        for cycle in range(9, 20):
            state["cycles"] = cycle
            state["generation"] = cycle
            result = step_planning_lab(state)
            if result.get("goal_reached"):
                reached = result
                break

        self.assertIsNotNone(reached)
        lab = ensure_planning_lab_state(state)
        completed_plan = next(
            plan
            for plan in lab["plans"]
            if plan.get("id") == reached["plan_id"]
        )
        executions = [
            item
            for item in lab["executions"]
            if item.get("plan_id") == completed_plan["id"]
        ]
        state["episodes"] = [
            {
                "id": f"E_TEST_{index}",
                "cycle": item["cycle"],
                "time": "2026-01-01T00:00:00+00:00",
                "kind": "planning_lab",
                "content": json.dumps(
                    {
                        "action": item["action"],
                        "before": item["before"],
                        "after": item["after"],
                        "plan_id": item["plan_id"],
                    }
                ),
                "concepts": ["planning_lab"],
            }
            for index, item in enumerate(executions, start=1)
        ]
        lab["episodic_memory_started_cycle"] = min(
            int(item["cycle"]) for item in executions
        )

        next_cycle = int(completed_plan["completed_cycle"]) + 1
        state["cycles"] = next_cycle
        state["generation"] = next_cycle
        step_planning_lab(state)

        memories = lab["episodic_route_memories"]
        memory = next(
            item
            for item in memories
            if item["source_plan_id"] == completed_plan["id"]
        )
        self.assertEqual(memory["outcome"], "goal_completed")
        self.assertEqual(
            memory["source_execution_ids"],
            [item["id"] for item in executions],
        )
        self.assertEqual(
            memory["source_episode_ids"],
            [f"E_TEST_{index}" for index in range(1, len(executions) + 1)],
        )
        self.assertTrue(memory["state_action_keys"])

    def test_episodic_memory_changes_equal_cost_route_choice_with_counterfactual(self) -> None:
        state = self._phase32_ready_state()
        state["cycles"] = 9
        state["generation"] = 9
        step_planning_lab(state)
        lab = ensure_planning_lab_state(state)

        lab["position"] = [0, 0]
        lab["goals"] = [
            {
                "id": "PG_MEMORY",
                "assigned_cycle": 10,
                "target": [1, 1],
                "status": "active",
                "selection": {
                    "kind": "test_fixture",
                    "prior_visits": 0,
                    "planned_distance": 2,
                    "preferred_step_range": [3, 4],
                },
            }
        ]
        lab["plans"] = []
        lab["active_goal_id"] = "PG_MEMORY"
        lab["active_plan_id"] = None
        lab["status"] = "goal_assigned"
        lab["episodic_memory_started_cycle"] = 9
        lab["episodic_route_memories"] = [
            {
                "id": "EM_TEST",
                "policy_version": "episodic-route-memory-v1",
                "created_cycle": 9,
                "source_plan_id": "PP_OLD",
                "source_goal_id": "PG_OLD",
                "source_episode_ids": ["E_MEMORY"],
                "source_execution_ids": ["PX_MEMORY"],
                "start": [0, 0],
                "goal": [1, 1],
                "actions": ["north", "west"],
                "state_action_keys": ["0,0|north", "1,0|west"],
                "action_bigrams": ["north>west"],
                "completed_cycle": 9,
                "outcome": "goal_completed",
                "world_version": lab["world_version"],
            }
        ]

        state["cycles"] = 10
        state["generation"] = 10
        result = step_planning_lab(state)
        plan = lab["plans"][0]
        decision = lab["memory_decisions"][0]

        self.assertTrue(result["memory_influenced"])
        self.assertEqual(plan["reason"], "initial_goal_plan")
        self.assertEqual(
            plan["memory_selection_reason"],
            "episodic_memory_tiebreak",
        )
        self.assertEqual(decision["status"], "memory_changed_choice")
        self.assertEqual(decision["counterfactual_actions"], ["north", "west"])
        self.assertEqual(decision["selected_actions"], ["west", "north"])
        self.assertGreater(
            decision["counterfactual_replay_score"],
            decision["selected_replay_score"],
        )
        self.assertEqual(decision["memory_refs"], ["EM_TEST"])
        self.assertEqual(decision["source_episode_refs"], ["E_MEMORY"])
        self.assertEqual(result["action"], "west")

    def test_episodic_memory_and_decision_persist_across_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = self._phase32_ready_state()
            state["planning_lab"]["episodic_memory_started_cycle"] = 8
            state["planning_lab"]["episodic_route_memories"] = [
                {
                    "id": "EM_PERSIST",
                    "policy_version": "episodic-route-memory-v1",
                    "source_plan_id": "PP_PERSIST",
                    "source_episode_ids": ["E_PERSIST"],
                    "state_action_keys": ["0,0|north"],
                    "action_bigrams": [],
                    "outcome": "goal_completed",
                    "world_version": state["planning_lab"]["world_version"],
                }
            ]
            state["planning_lab"]["memory_decisions"] = [
                {
                    "id": "MD_PERSIST",
                    "changed_choice": True,
                    "memory_refs": ["EM_PERSIST"],
                    "source_episode_refs": ["E_PERSIST"],
                }
            ]
            store.save(state)
            reloaded = store.load()

            self.assertEqual(
                reloaded["planning_lab"]["episodic_route_memories"][0]["id"],
                "EM_PERSIST",
            )
            self.assertEqual(
                reloaded["planning_lab"]["memory_decisions"][0]["id"],
                "MD_PERSIST",
            )

    def test_planner_does_not_reference_hidden_environment_transition_map(self) -> None:
        source = inspect.getsource(planning_lab)
        self.assertNotIn("_HIDDEN_ACTION_DELTAS", source)
        self.assertNotIn("_HIDDEN_STATEFUL_BLOCKS", source)
        self.assertNotIn("_HIDDEN_TRANSFER_BLOCKS", source)

    def test_planning_lab_module_has_no_external_effect_imports(self) -> None:
        tree = ast.parse(inspect.getsource(planning_lab))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])

        self.assertTrue(
            imports.issubset(
                {"__future__", "json", "collections", "typing", "action_lab"}
            )
        )

    def test_core_planning_turn_becomes_citable_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = self._phase32_ready_state()
            store.save(state)
            core = AgentCore(store)

            result = core.cycle("persistent planning", planning_lab=True)
            persisted = store.load()

            self.assertIsNotNone(result["planning_lab_result"])
            self.assertIsNotNone(result["planning_lab_result"]["action"])
            episode = next(
                item
                for item in persisted["episodes"]
                if item.get("kind") == "planning_lab"
            )
            self.assertIn("goal_directed_action", episode["concepts"])
            self.assertEqual(
                len(persisted["planning_lab"]["executions"]),
                1,
            )

    def test_default_cycle_grants_no_planning_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            core = AgentCore(store)

            result = core.cycle("ordinary cycle")
            persisted = store.load()

            self.assertIsNone(result["planning_lab_result"])
            self.assertEqual(persisted["planning_lab"]["executions"], [])
            self.assertEqual(persisted["planning_lab"]["status"], "uninitialized")

    def test_action_and_planning_authority_are_mutually_exclusive(self) -> None:
        core = AgentCore()
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            core.cycle(
                "invalid authority combination",
                action_lab=True,
                planning_lab=True,
            )


if __name__ == "__main__":
    unittest.main()
