from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


EXPERIMENTS = Path(__file__).parents[1] / "experiments"
world_path = EXPERIMENTS / "world2_ecology.py"
reach_path = EXPERIMENTS / "world2_reachability.py"

world_spec = importlib.util.spec_from_file_location("world2_ecology", world_path)
world = importlib.util.module_from_spec(world_spec)
assert world_spec.loader is not None
world_spec.loader.exec_module(world)
sys.modules["world2_ecology"] = world

reach_spec = importlib.util.spec_from_file_location("world2_reachability", reach_path)
reach = importlib.util.module_from_spec(reach_spec)
assert reach_spec.loader is not None
reach_spec.loader.exec_module(reach)


class World2ReachabilityTests(unittest.TestCase):
    def test_periodic_resource_has_multiple_paths(self) -> None:
        result = reach.enumerate_reachability(
            seeds=(1, 2), horizon=6,
            actions=("north", "south", "west", "observe"),
            max_sequences=8192,
        )
        self.assertGreater(result["phenomenon_path_counts"].get("periodic_resource", 0), 1)

    def test_object_and_delayed_process_are_reachable_without_ora(self) -> None:
        sequences = [
            ("north", "interact", "west", "east", "observe", "observe", "observe", "observe"),
            ("north", "interact", "south", "observe", "observe", "observe", "north", "west"),
        ]
        found = []
        for sequence in sequences:
            result = reach.run_sequence(seed=1, actions=sequence)
            found.append(set(result["phenomena"]))
        self.assertTrue(any("delayed_process" in item for item in found))
        self.assertTrue(any("persistent_object" in item for item in found))

    def test_latent_condition_is_reachable_without_privileged_state_access(self) -> None:
        result = reach.enumerate_reachability(
            seeds=(1, 2, 3, 4, 5),
            horizon=8,
            max_sequences=50000,
        )
        count = result["phenomenon_path_counts"].get("latent_condition", 0)
        self.assertGreater(count, 1)
        self.assertLess(count, result["sequence_count"] // 4)

    def test_reachability_is_deterministic(self) -> None:
        kwargs = {
            "seeds": (1, 2),
            "horizon": 5,
            "actions": ("north", "south", "west", "interact", "observe"),
            "max_sequences": 3000,
        }
        self.assertEqual(
            reach.enumerate_reachability(**kwargs),
            reach.enumerate_reachability(**kwargs),
        )

    def test_harness_has_no_agenttest_dependency(self) -> None:
        source = reach_path.read_text(encoding="utf-8")
        self.assertNotIn("from agenttest", source)
        self.assertNotIn("import agenttest", source)


if __name__ == "__main__":
    unittest.main()
