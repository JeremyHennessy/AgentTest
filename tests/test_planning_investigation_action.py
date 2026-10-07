from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import agenttest.planning_lab as planning_lab
from agenttest.action_lab import (
    BASE_WORLD_VERSION,
    STATEFUL_WORLD_VERSION,
    TRANSFER_WORLD_VERSION,
    apply_bounded_action,
    step_action_lab,
)
from agenttest.planning_lab import execute_investigation_action, step_planning_lab
from agenttest.state import initial_state


class PlanningInvestigationActionTests(unittest.TestCase):
    def _ready_state(self) -> dict:
        state = initial_state()
        for cycle in range(1, 9):
            state["cycles"] = cycle
            step_action_lab(state)
        state["cycles"] = 9
        step_planning_lab(state)
        return state

    def _execute(self, state: dict, action: str = "north") -> dict:
        return execute_investigation_action(
            state, action=action, case_id="IC000001", attempt_id="IA000001",
        )

    def test_records_one_actual_action_without_bootstrapping(self) -> None:
        state = initial_state()
        for cycle in range(1, 9):
            state["cycles"] = cycle
            step_action_lab(state)
        lab = state["planning_lab"]
        lab["position"] = [-1, 1]
        state["cycles"] = 10
        action_lab_before = copy.deepcopy(state["action_lab"])

        with patch.object(planning_lab, "apply_bounded_action", wraps=apply_bounded_action) as apply:
            result = self._execute(state)

        apply.assert_called_once_with(
            [-1, 1], "north", bounds=2, world_version=STATEFUL_WORLD_VERSION,
        )
        self.assertEqual(result["before"], [-1, 1])
        self.assertEqual(result["after"], [0, 1])
        self.assertEqual(result["delta"], [1, 0])
        self.assertIsNone(result["predicted_after"])
        self.assertIsNone(result["matched_prediction"])
        self.assertFalse(result["goal_reached"])
        self.assertIsNone(result["plan_id"])
        self.assertEqual(lab["last_action_cycle"], 10)
        self.assertEqual(lab["visit_counts"]["0,1"], 1)
        self.assertEqual(len(lab["executions"]), 1)
        self.assertEqual(len(lab["transition_observations"]), 1)
        observation = lab["transition_observations"][0]
        self.assertEqual(observation["source_id"], result["id"])
        self.assertEqual(observation["source"], "investigation_action")
        self.assertEqual(observation["case_id"], "IC000001")
        self.assertEqual(observation["attempt_id"], "IA000001")
        self.assertEqual(observation["world_version"], STATEFUL_WORLD_VERSION)
        self.assertEqual(lab["state_effects"]["-1,1|north"]["samples"], 1)
        self.assertEqual(lab["bootstrapped_from_action_count"], 0)
        self.assertIsNone(lab["bootstrapped_cycle"])
        self.assertEqual(state["action_lab"], action_lab_before)
        self.assertEqual(lab["goals"], [])
        self.assertEqual(lab["plans"], [])
        self.assertEqual(lab["objective_realizations"], [])

    def test_blocked_action_records_evidence_and_cancels_precommit(self) -> None:
        state = initial_state()
        lab = state["planning_lab"]
        lab["position"] = [0, 2]
        lab["active_objective_realization_id"] = "OR000001"
        decision = {
            "id": "OR000001", "status": "precommitted", "state": [0, 2],
            "goal_id": "PG000001", "objective_decision_id": "OD000001",
            "action": "south", "expected_information_gain": 1.0,
            "source_observation_refs": ["PX000099"],
        }
        lab["objective_realization_decisions"] = [decision]
        state["cycles"] = 12

        first = self._execute(state, "south")
        state["cycles"] = 13
        second = self._execute(state, "south")

        self.assertTrue(first["blocked"])
        self.assertEqual(first["after"], [0, 2])
        self.assertEqual(first["delta"], [0, 0])
        self.assertIsNone(first["matched_prediction"])
        self.assertEqual(second["predicted_after"], [0, 2])
        self.assertTrue(second["matched_prediction"])
        self.assertEqual(lab["state_effects"]["0,2|south"]["blocked_samples"], 2)
        self.assertEqual(lab["visit_counts"]["0,2"], 2)
        self.assertEqual(decision["status"], "cancelled_investigation_action")
        self.assertEqual(decision["cancelled_cycle"], 12)
        self.assertEqual(decision["investigation_execution_id"], first["id"])
        self.assertEqual(decision["source_observation_refs"], ["PX000099"])
        self.assertEqual(decision["objective_decision_id"], "OD000001")
        self.assertNotIn("realization_id", decision)
        self.assertNotIn("realized_information_gain", decision)
        self.assertIsNone(lab["active_objective_realization_id"])
        self.assertEqual(lab["objective_realizations"], [])

    def test_displaced_plan_replans_from_actual_position_after_reload(self) -> None:
        state = self._ready_state()
        lab = state["planning_lab"]
        old_plan = next(p for p in lab["plans"] if p["id"] == lab["active_plan_id"])
        old_goal = copy.deepcopy(lab["goals"])
        old_plan_before = copy.deepcopy(old_plan)
        lab["episodic_route_memories"] = [{"id": "EM_OLD", "source_plan_id": "PP_OLD"}]
        action = next(
            action for action in ("north", "east", "south", "west")
            if (outcome := apply_bounded_action(lab["position"], action,
                                                world_version=STATEFUL_WORLD_VERSION))["after"]
            not in (lab["position"], lab["goals"][-1]["target"])
        )
        state["cycles"] = 10

        result = self._execute(state, action)

        self.assertEqual(old_plan["status"], "invalidated")
        self.assertEqual(old_plan["invalidation_reason"], "investigation_action_changed_state")
        self.assertEqual(old_plan["investigation_execution_id"], result["id"])
        for key in ("actions", "predicted_states", "next_step_index", "memory_refs"):
            self.assertEqual(old_plan[key], old_plan_before[key])
        self.assertEqual(lab["goals"], old_goal)
        self.assertEqual(lab["episodic_route_memories"], [{"id": "EM_OLD", "source_plan_id": "PP_OLD"}])
        self.assertTrue(result["replan_required"])
        self.assertIsNone(lab["active_plan_id"])
        reloaded = json.loads(json.dumps(state))
        reloaded["cycles"] = 11
        resumed = step_planning_lab(reloaded)
        replacement = next(p for p in reloaded["planning_lab"]["plans"]
                           if p["id"] == resumed["plan_id"])
        self.assertEqual(resumed["before"], result["after"])
        self.assertEqual(replacement["start"], result["after"])
        self.assertEqual(replacement["reason"], "replan_after_invalidation")
        self.assertNotEqual(resumed["id"], result["id"])
        self.assertEqual(resumed["goal_id"], old_goal[-1]["id"])

    def test_incidental_goal_arrival_does_not_complete_legacy_objective(self) -> None:
        state = self._ready_state()
        lab = state["planning_lab"]
        goal = lab["goals"][-1]
        plan = lab["plans"][-1]
        action = next(a for a in ("north", "east", "south", "west")
                      if not apply_bounded_action(lab["position"], a,
                                                  world_version=STATEFUL_WORLD_VERSION)["blocked"])
        goal["target"] = apply_bounded_action(lab["position"], action,
                                               world_version=STATEFUL_WORLD_VERSION)["after"]
        goal["selection"] = {"kind": "self_selected_bounded_objective", "objective_decision_id": "OD000001"}
        state["cycles"] = 10

        result = self._execute(state, action)

        self.assertEqual(goal["status"], "cancelled")
        self.assertEqual(goal["selection"]["objective_decision_id"], "OD000001")
        self.assertNotIn("completed_cycle", goal)
        self.assertEqual(plan["status"], "invalidated")
        self.assertIsNone(lab["active_goal_id"])
        self.assertFalse(result["goal_reached"])
        self.assertEqual(lab["objective_realizations"], [])
        state["cycles"] = 11
        resumed = step_planning_lab(state)
        self.assertEqual(resumed["before"], result["after"])
        self.assertNotEqual(resumed["goal_id"], goal["id"])

    def test_blocked_action_preserves_undisplaced_plan(self) -> None:
        state = self._ready_state()
        lab = state["planning_lab"]
        lab["position"] = [0, 2]
        plan_before = copy.deepcopy(lab["plans"])
        active_plan_id = lab["active_plan_id"]

        result = self._execute(state, "south")

        self.assertTrue(result["blocked"])
        self.assertFalse(result["replan_required"])
        self.assertEqual(lab["active_plan_id"], active_plan_id)
        self.assertEqual(lab["plans"], plan_before)

    def test_unique_px_identity_survives_sparse_history_and_legacy_resume(self) -> None:
        state = self._ready_state()
        lab = state["planning_lab"]
        lab["executions"][0]["id"] = "PX000099"
        lab["transition_observations"][-1]["source_id"] = "PX000099"
        lab["transition_observations"].append({
            "source": "planning_lab", "source_id": "PX000105",
        })
        state["cycles"] = 10

        result = self._execute(state)
        state["cycles"] = 11
        resumed = step_planning_lab(state)

        self.assertEqual(result["id"], "PX000106")
        self.assertEqual(resumed["id"], "PX000107")

    def test_rejects_invalid_inputs_and_other_worlds_without_action_or_mutation(self) -> None:
        for change, kwargs in [
            ({}, {"action": "teleport"}),
            ({}, {"case_id": ""}),
            ({}, {"attempt_id": None}),
            ({"world_version": BASE_WORLD_VERSION}, {}),
            ({"world_version": TRANSFER_WORLD_VERSION}, {}),
            ({"position": [3, 0]}, {}),
            ({"position": [True, 0]}, {}),
        ]:
            with self.subTest(change=change, kwargs=kwargs):
                state = initial_state()
                state["planning_lab"].update(change)
                before = copy.deepcopy(state)
                args = {"action": "north", "case_id": "IC000001", "attempt_id": "IA000001", **kwargs}
                with patch.object(planning_lab, "apply_bounded_action") as apply:
                    with self.assertRaises(ValueError):
                        execute_investigation_action(state, **args)
                apply.assert_not_called()
                self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
