from __future__ import annotations

import importlib.util
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
sys.path.insert(0, str(EXPERIMENTS))

for name in ("open_object_world", "open_object_world_explorer"):
    spec = importlib.util.spec_from_file_location(
        name, EXPERIMENTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world = sys.modules["open_object_world"]
explorer = sys.modules["open_object_world_explorer"]


class OpenObjectWorldExplorerTests(unittest.TestCase):
    def test_candidate_generation_uses_public_observation_only(self):
        observation = world.observe_world(world.initial_world(seed=1))
        commands = explorer.candidate_commands(observation)
        self.assertTrue(commands)
        self.assertTrue(all("action" in command for command in commands))
        self.assertIn({"action": "north"}, commands)
        self.assertIn(
            {"action": "inspect", "target": "O001"},
            commands,
        )

    def test_choice_is_deterministic_for_same_observation_history(self):
        observation = world.observe_world(world.initial_world(seed=1))
        left = explorer.choose_command(observation, Counter())
        right = explorer.choose_command(observation, Counter())
        self.assertEqual(left, right)

    def test_explorer_policy_has_no_hidden_mechanics_or_goal_terms(self):
        source = (
            EXPERIMENTS / "open_object_world_explorer.py"
        ).read_text()
        for forbidden in (
            "_kind",
            "_mass",
            "_latched",
            "_carryable",
            "_movable",
            "barrier_open",
            "mechanism_active",
            "solution",
            "reward",
            "goal",
        ):
            self.assertNotIn(forbidden, source)

    def test_same_seed_replays_same_unguided_discovery(self):
        first = explorer.run_unguided(seed=2, steps=80)
        second = explorer.run_unguided(seed=2, steps=80)
        self.assertEqual(first, second)
        self.assertGreater(first["unique_observation_count"], 1)
        self.assertGreater(first["unique_position_count"], 1)


if __name__ == "__main__":
    unittest.main()
