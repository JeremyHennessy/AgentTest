from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "experiments" / "world2_ecology.py"
SPEC = importlib.util.spec_from_file_location("world2_ecology", MODULE_PATH)
world2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(world2)


class World2IsolatedSimulationTests(unittest.TestCase):
    def test_replay_is_exactly_deterministic(self) -> None:
        actions = [
            "north", "interact", "west", "observe", "observe",
            "south", "east", "observe", "interact", "observe",
            "observe", "observe",
        ]
        first = world2.replay_world2(seed=7, actions=actions)
        second = world2.replay_world2(seed=7, actions=actions)
        self.assertEqual(first, second)

    def test_transition_does_not_mutate_input(self) -> None:
        state = world2.initial_world2_state(seed=3)
        before = copy.deepcopy(state)
        after, record = world2.transition_world2(state, "north", cycle=1)
        self.assertEqual(state, before)
        self.assertNotEqual(after, before)
        self.assertEqual(record["before"], [0, 0])

    def test_observation_hides_latent_and_future_state(self) -> None:
        state = world2.initial_world2_state(seed=4)
        state["latent_mode"] = 1
        state["pending_slow_effects"] = [{"matures_cycle": 9, "delta": 2}]
        observation = world2.observe_world2(state)
        serialized = repr(observation)
        self.assertNotIn("latent_mode", serialized)
        self.assertNotIn("pending_slow_effects", serialized)
        self.assertNotIn("resource_phase", serialized)
        self.assertNotIn("matures_cycle", serialized)

    def test_periodic_resource_changes_without_local_attention(self) -> None:
        state = world2.initial_world2_state(seed=1)
        initial = copy.deepcopy(state["resources"])
        for cycle in range(1, 8):
            state, _ = world2.transition_world2(state, "observe", cycle=cycle)
        self.assertNotEqual(state["resources"], initial)

    def test_object_displacement_persists_after_leaving(self) -> None:
        state = world2.initial_world2_state(seed=1)
        state, _ = world2.transition_world2(state, "north", cycle=1)
        self.assertEqual(state["position"], [1, 0])
        state, record = world2.transition_world2(state, "interact", cycle=2)
        self.assertEqual(record["interaction_effect"], "object_displaced")
        moved = list(state["objects"]["O1"]["position"])
        state, _ = world2.transition_world2(state, "south", cycle=3)
        state, _ = world2.transition_world2(state, "observe", cycle=4)
        self.assertEqual(state["objects"]["O1"]["position"], moved)
        self.assertNotEqual(state["position"], moved)

    def test_delayed_effect_matures_while_attention_is_elsewhere(self) -> None:
        state = world2.initial_world2_state(seed=1)
        state, _ = world2.transition_world2(state, "north", cycle=1)
        state, _ = world2.transition_world2(state, "interact", cycle=2)
        self.assertEqual(state["slow_process"], 0)
        self.assertTrue(state["pending_slow_effects"])
        state, _ = world2.transition_world2(state, "south", cycle=3)
        state, _ = world2.transition_world2(state, "observe", cycle=4)
        state, _ = world2.transition_world2(state, "observe", cycle=5)
        self.assertEqual(state["slow_process"], 0)
        state, _ = world2.transition_world2(state, "observe", cycle=6)
        self.assertEqual(state["slow_process"], 2)
        self.assertEqual(state["pending_slow_effects"], [])

    def test_world2_has_no_agent_or_external_effect_imports(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.issubset({"__future__", "copy", "typing"}), imports)

    def test_existing_world_module_is_not_imported(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("agenttest", source)
        self.assertNotIn("StateStore", source)
        self.assertNotIn("AgentCore", source)

    def test_invalid_action_and_non_increasing_cycle_fail_closed(self) -> None:
        state = world2.initial_world2_state(seed=1)
        with self.assertRaises(ValueError):
            world2.transition_world2(state, "teleport", cycle=1)
        state, _ = world2.transition_world2(state, "observe", cycle=1)
        with self.assertRaises(ValueError):
            world2.transition_world2(state, "observe", cycle=1)


if __name__ == "__main__":
    unittest.main()
