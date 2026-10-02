from __future__ import annotations

import unittest

import agenttest.planning_lab as planning_lab
from agenttest.action_lab import ACTION_ORDER, BOUNDS, STATEFUL_WORLD_VERSION
from agenttest.planning_lab import initial_planning_lab_state


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


if __name__ == "__main__":
    unittest.main()
