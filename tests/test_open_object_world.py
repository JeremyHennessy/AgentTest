from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments" / "open_object_world.py"
spec = importlib.util.spec_from_file_location("open_object_world", MODULE_PATH)
assert spec is not None and spec.loader is not None
world = importlib.util.module_from_spec(spec)
sys.modules["open_object_world"] = world
spec.loader.exec_module(world)


def run(state, commands):
    current = state
    receipts = []
    for cycle, command in enumerate(commands, start=1):
        current, receipt = world.transition(current, command, cycle=cycle)
        receipts.append(receipt)
    return current, receipts


class OpenObjectWorldTests(unittest.TestCase):
    def test_agent_observation_hides_private_mechanics(self):
        state = world.initial_world(seed=1)
        observed = world.observe_world(state)
        rendered = repr(observed)
        for forbidden in (
            "_kind",
            "_mass",
            "_carryable",
            "_movable",
            "_latched",
            "solution",
            "reward",
            "goal",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_closed_structure_blocks_route_until_world_state_changes(self):
        state = world.initial_world(seed=1)
        state, receipts = run(
            state,
            [
                {"action": "north"},
                {"action": "west"},
                {"action": "north"},
            ],
        )
        self.assertTrue(receipts[-1]["blocked"])
        self.assertEqual(state["position"], [1, 1])
        self.assertEqual(receipts[-1]["barrier_observed_state"], "closed")

    def test_direct_generic_interaction_can_change_remote_route_state(self):
        state = world.initial_world(seed=1)
        state, receipts = run(
            state,
            [
                {"action": "north"},
                {"action": "interact", "target": "M001"},
                {"action": "west"},
                {"action": "north"},
            ],
        )
        self.assertTrue(receipts[1]["success"])
        self.assertIn("target_state_changed", receipts[1]["observed_effects"])
        self.assertEqual(receipts[1]["barrier_observed_state"], "open")
        self.assertEqual(state["position"], [2, 1])

    def test_heavier_anonymous_object_can_change_same_route_without_interact(self):
        state = world.initial_world(seed=1)
        state, receipts = run(
            state,
            [
                {"action": "take", "target": "O001"},
                {"action": "north"},
                {"action": "west"},
                {"action": "drop", "target": "O001"},
                {"action": "north"},
            ],
        )
        self.assertNotIn("O001", state["inventory"])
        self.assertEqual(state["entities"]["O001"]["position"], [1, 1])
        self.assertEqual(receipts[3]["barrier_observed_state"], "open")
        self.assertEqual(state["position"], [2, 1])

    def test_two_lighter_objects_can_change_same_route_without_interact(self):
        state = world.initial_world(seed=1)
        state, receipts = run(
            state,
            [
                {"action": "take", "target": "O002"},
                {"action": "east"},
                {"action": "take", "target": "O003"},
                {"action": "west"},
                {"action": "west"},
                {"action": "north"},
                {"action": "drop", "target": "O002"},
                {"action": "drop", "target": "O003"},
                {"action": "north"},
            ],
        )
        self.assertEqual(state["inventory"], [])
        self.assertEqual(state["entities"]["O002"]["position"], [1, 1])
        self.assertEqual(state["entities"]["O003"]["position"], [1, 1])
        self.assertEqual(receipts[7]["barrier_observed_state"], "open")
        self.assertEqual(state["position"], [2, 1])

    def test_generic_push_persists_object_position_without_goal_signal(self):
        state = world.initial_world(seed=1)
        state, receipts = run(
            state,
            [
                {"action": "push", "target": "O001", "direction": "south"},
                {"action": "inspect", "target": "O001"},
            ],
        )
        self.assertTrue(receipts[0]["success"])
        self.assertEqual(state["position"], [-1, 0])
        self.assertEqual(state["entities"]["O001"]["position"], [-2, 0])
        self.assertEqual(receipts[1]["inspection"]["position"], [-2, 0])

    def test_object_and_mechanism_state_persist_across_unrelated_actions(self):
        state = world.initial_world(seed=1)
        state, _ = run(
            state,
            [
                {"action": "take", "target": "O001"},
                {"action": "north"},
                {"action": "west"},
                {"action": "drop", "target": "O001"},
            ],
        )
        snapshot = world.observe_world(state)
        self.assertEqual(
            next(x for x in snapshot["visible_entities"] if x["id"] == "M001")[
                "observable_state"
            ],
            "lit",
        )
        state, _ = world.transition(
            state,
            {"action": "inspect", "target": "M001"},
            cycle=20,
        )
        self.assertEqual(state["entities"]["O001"]["position"], [1, 1])
        self.assertEqual(
            next(
                x for x in world.observe_world(state)["visible_entities"]
                if x["id"] == "M001"
            )["observable_state"],
            "lit",
        )

    def test_spatial_variants_preserve_mechanics_without_preserving_layout(self):
        states = [world.initial_world(seed=seed) for seed in range(1, 5)]
        positions = {
            seed: {
                entity_id: tuple(entity["position"])
                for entity_id, entity in state["entities"].items()
            }
            for seed, state in enumerate(states, start=1)
        }
        self.assertEqual(len({positions[s]["M001"] for s in positions}), 4)
        for state in states:
            self.assertEqual(len(state["entities"]), 5)
            self.assertEqual(
                sorted(
                    entity["_mass"]
                    for entity in state["entities"].values()
                    if entity["_kind"] == "object"
                ),
                [1, 1, 2],
            )

    def test_world_source_contains_no_reward_or_scripted_goal_contract(self):
        source = MODULE_PATH.read_text().lower()
        for forbidden in (
            "reward +=",
            "reward=",
            "solution =",
            "goal =",
            "correct_sequence",
            "win_condition",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
