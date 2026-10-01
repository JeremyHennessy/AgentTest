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


if __name__ == "__main__":
    unittest.main()
