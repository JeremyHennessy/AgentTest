"""Synthetic-only tests; registered seeds 0..3 and real 1803 state are not run."""
import unittest

from ora2.matched_continuity_study001 import (
    ARMS, CYCLES, SEEDS, PROTOCOL_BLOB, InvalidStudy, inspect, one,
)


class MatchedContinuityPreflight(unittest.TestCase):
    def test_finite_registered_bounds(self):
        self.assertEqual(SEEDS, (0, 1, 2, 3))
        self.assertEqual(ARMS, ("control", "candidate"))
        self.assertEqual(CYCLES, 4)
        self.assertEqual(len(PROTOCOL_BLOB), 40)

    def test_genuine_goal_identity_is_not_synthesized(self):
        goal = {"id": "PG000448", "target": [0, 2], "status": "active"}
        plan = {"id": "PP000451", "goal_id": "PG000448", "goal": [0, 2], "status": "active"}
        state = {"cycles": 1803, "planning_lab": {
            "goals": [goal], "plans": [plan],
            "active_goal_id": "PG000448", "active_plan_id": "PP000451",
            "active_objective_realization_id": None,
        }}
        result = inspect(state)
        self.assertEqual(result["active_goal"], "PG000448")
        self.assertEqual(result["active_plan"], "PP000451")
        self.assertEqual(result["goal_status"], "active")
        with self.assertRaises(InvalidStudy):
            inspect({**state, "planning_lab": {**state["planning_lab"], "goals": []}})
        with self.assertRaises(InvalidStudy):
            inspect({**state, "planning_lab": {**state["planning_lab"], "plans": [plan, plan]}})

    def test_duplicate_record_identity_fails_closed(self):
        with self.assertRaises(InvalidStudy):
            one([{"id": "PG000448"}, {"id": "PG000448"}], "PG000448")


if __name__ == "__main__":
    unittest.main()
