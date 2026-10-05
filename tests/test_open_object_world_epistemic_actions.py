from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
sys.path.insert(0, str(EXPERIMENTS))

for name in (
    "open_object_world",
    "open_object_world_explorer",
    "normalized_inquiry_objectives",
    "open_object_world_native_bridge",
    "open_object_world_action_association",
    "open_object_world_epistemic_actions",
):
    spec = importlib.util.spec_from_file_location(
        name, EXPERIMENTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

policy = sys.modules["open_object_world_epistemic_actions"]


class OpenObjectWorldEpistemicActionTests(unittest.TestCase):
    def test_under_sampled_public_command_is_explored_first(self):
        observation = {
            "position": [0, 0],
            "inventory_ids": [],
            "visible_entities": [],
        }
        prefix = [
            dict(observation),
            {**observation, "position": [1, 0]},
            {**observation, "position": [1, 0]},
        ]
        receipts = [
            {"action": "north"},
            {"action": "inspect", "target": "O001"},
        ]
        result = policy.select_epistemic_command(
            observation,
            feature="position",
            relation="same_next_observation",
            prefix_observations=prefix,
            prefix_receipts=receipts,
        )
        self.assertEqual(result["mode"], "reduce_action_uncertainty")
        self.assertIn(result["command"]["action"], {"east", "south", "west"})

    def test_falsification_mode_prefers_command_with_change_evidence(self):
        observation = {
            "position": [0, 0],
            "inventory_ids": [],
            "visible_entities": [],
        }
        observations = [dict(observation)]
        receipts = []
        position = [0, 0]
        for action, after in (
            ("north", [1, 0]),
            ("inspect", [1, 0]),
            ("north", [2, 0]),
            ("inspect", [2, 0]),
            ("east", [2, -1]),
            ("east", [2, -2]),
            ("south", [1, -2]),
            ("south", [0, -2]),
            ("west", [0, -1]),
            ("west", [0, 0]),
        ):
            receipts.append(
                {
                    "action": action,
                    "target": "O001" if action == "inspect" else None,
                }
            )
            position = list(after)
            observations.append(
                {
                    "position": list(position),
                    "inventory_ids": [],
                    "visible_entities": [],
                }
            )

        result = policy.select_epistemic_command(
            observation,
            feature="position",
            relation="same_next_observation",
            prefix_observations=observations,
            prefix_receipts=receipts,
        )
        # All currently available movement commands have evidence; the selected
        # experiment should seek a position change rather than a confirming hold.
        self.assertEqual(result["mode"], "seek_disconfirming_observation")
        self.assertIn(
            result["command"]["action"],
            {"north", "east", "south", "west"},
        )
        self.assertGreater(result["falsification_probability"], 0.5)

    def test_policy_source_contains_no_goal_reward_or_hidden_mechanics(self):
        source = (
            EXPERIMENTS / "open_object_world_epistemic_actions.py"
        ).read_text()
        for forbidden in (
            "_mass",
            'get("_kind")',
            "_latched",
            "reward",
            "solution",
            "goal",
            "barrier_open",
            "mechanism_active",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
