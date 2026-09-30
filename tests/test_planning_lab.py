from __future__ import annotations

import ast
import inspect
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
from agenttest.state import StateStore, initial_state


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

    def test_planner_does_not_reference_hidden_environment_transition_map(self) -> None:
        source = inspect.getsource(planning_lab)
        self.assertNotIn("_HIDDEN_ACTION_DELTAS", source)
        self.assertNotIn("_HIDDEN_STATEFUL_BLOCKS", source)

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
                {"__future__", "collections", "typing", "action_lab"}
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
