from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from open_object_world_challenge import initial_world, observe_world, transition


def step(world, cycle, action, target=None, direction=None):
    command = {"action": action}
    if target is not None:
        command["target"] = target
    if direction is not None:
        command["direction"] = direction
    return transition(world, command, cycle=cycle)


def public_state(observation, entity_id):
    row = next(
        item
        for item in observation["visible_entities"]
        if item["id"] == entity_id
    )
    return row.get("observable_state")


class OpenObjectWorldChallengeTests(unittest.TestCase):
    def test_observation_never_exposes_private_mechanics(self):
        world = initial_world(1)
        observation = observe_world(world)
        self.assertEqual(
            set(observation),
            {
                "world_version",
                "observation_id",
                "cycle",
                "position",
                "inventory_ids",
                "visible_entities",
            },
        )
        for entity in observation["visible_entities"]:
            self.assertFalse(any(key.startswith("_") for key in entity))

    def test_wall_partition_blocks_direct_crossing(self):
        world = initial_world(1)
        world, first = step(world, 1, "north")
        self.assertTrue(first["success"])
        world, receipt = step(world, 2, "north")
        self.assertFalse(receipt["success"])
        self.assertTrue(receipt["blocked"])
        self.assertEqual(world["position"], [-1, 0])

    def test_heavy_object_on_pressure_plate_opens_pressure_gate(self):
        world = initial_world(1)
        world, _ = step(world, 1, "east")
        world, _ = step(world, 2, "take", "O001")
        world, _ = step(world, 3, "north")
        world, _ = step(world, 4, "east")
        world, _ = step(world, 5, "drop", "O001")
        world, _ = step(world, 6, "west")
        observation = observe_world(world)
        self.assertEqual(public_state(observation, "B001"), "open")
        self.assertEqual(public_state(observation, "M001"), "active")

    def test_two_light_objects_can_also_activate_pressure_gate(self):
        world = initial_world(1)
        world, _ = step(world, 1, "take", "O002")
        world, _ = step(world, 2, "west")
        world, _ = step(world, 3, "take", "O003")
        world, _ = step(world, 4, "east")
        world, _ = step(world, 5, "east")
        world, _ = step(world, 6, "east")
        world, _ = step(world, 7, "north")
        world, _ = step(world, 8, "drop", "O002")
        world, _ = step(world, 9, "drop", "O003")
        world, _ = step(world, 10, "west")
        observation = observe_world(world)
        self.assertEqual(public_state(observation, "M001"), "active")
        self.assertEqual(public_state(observation, "B001"), "open")

    def test_required_portable_object_activates_socket_by_drop(self):
        world = initial_world(1)
        world, _ = step(world, 1, "west")
        world, _ = step(world, 2, "west")
        world, _ = step(world, 3, "take", "O003")
        world, _ = step(world, 4, "north")
        world, _ = step(world, 5, "drop", "O003")
        observation = observe_world(world)
        self.assertEqual(public_state(observation, "M002"), "active")
        world, _ = step(world, 6, "east")
        observation = observe_world(world)
        self.assertEqual(public_state(observation, "B002"), "open")

    def test_wrong_portable_object_does_not_activate_socket(self):
        world = initial_world(1)
        world, _ = step(world, 1, "take", "O002")
        world, _ = step(world, 2, "west")
        world, _ = step(world, 3, "west")
        world, _ = step(world, 4, "north")
        world, _ = step(world, 5, "drop", "O002")
        observation = observe_world(world)
        self.assertEqual(public_state(observation, "M002"), "inactive")

    def test_far_side_override_is_optional_loose_affordance(self):
        world = initial_world(1)
        world, _ = step(world, 1, "east")
        world, _ = step(world, 2, "take", "O001")
        world, _ = step(world, 3, "north")
        world, _ = step(world, 4, "east")
        world, _ = step(world, 5, "drop", "O001")
        world, _ = step(world, 6, "west")
        world, _ = step(world, 7, "north")
        world, _ = step(world, 8, "north")
        world, _ = step(world, 9, "west")
        world, _ = step(world, 10, "north")
        world, receipt = step(world, 11, "interact", "M003")
        self.assertTrue(receipt["success"])
        self.assertEqual(public_state(observe_world(world), "M003"), "active")

        world, _ = step(world, 12, "south")
        world, _ = step(world, 13, "east")
        observation = observe_world(world)
        self.assertEqual(public_state(observation, "B001"), "open")

    def test_all_four_layouts_are_spatial_transforms_with_same_entities(self):
        expected = set(initial_world(1)["entities"])
        positions = set()
        for seed in range(1, 5):
            world = initial_world(seed)
            self.assertEqual(set(world["entities"]), expected)
            positions.add(tuple(world["position"]))
        self.assertEqual(len(positions), 2)

    def test_research_source_contains_no_reward_or_solution_contract(self):
        world_source = (
            ROOT / "experiments" / "open_object_world_challenge.py"
        ).read_text()
        explorer_source = (
            ROOT / "experiments" / "open_object_world_challenge_explorer.py"
        ).read_text()
        for forbidden in ("reward", "solution", "target_goal", "goal_score"):
            self.assertNotIn(forbidden, world_source.lower())
            self.assertNotIn(forbidden, explorer_source.lower())


if __name__ == "__main__":
    unittest.main()
