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
):
    spec = importlib.util.spec_from_file_location(
        name, EXPERIMENTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

assoc = sys.modules["open_object_world_action_association"]


class OpenObjectWorldActionAssociationTests(unittest.TestCase):
    def test_action_label_uses_only_issued_public_command_fields(self):
        self.assertEqual(
            assoc.action_label(
                {
                    "action": "push",
                    "target": "O001",
                    "direction": "south",
                }
            ),
            "push:O001:south",
        )
        self.assertEqual(
            assoc.action_label({"action": "north"}),
            "north",
        )

    def test_simple_public_trace_yields_comparable_association(self):
        observations = [
            {
                "position": [0, 0],
                "inventory_ids": [],
                "visible_entities": [],
            },
            {
                "position": [1, 0],
                "inventory_ids": [],
                "visible_entities": [],
            },
            {
                "position": [1, 0],
                "inventory_ids": [],
                "visible_entities": [],
            },
            {
                "position": [2, 0],
                "inventory_ids": [],
                "visible_entities": [],
            },
            {
                "position": [2, 0],
                "inventory_ids": [],
                "visible_entities": [],
            },
        ]
        receipts = [
            {"action": "north"},
            {"action": "inspect", "target": "O001"},
            {"action": "north"},
            {"action": "inspect", "target": "O001"},
        ]
        candidates = assoc.association_candidates(observations, receipts)
        north = next(
            item
            for item in candidates
            if item["feature"] == "position"
            and item["action"] == "north"
        )
        self.assertEqual(
            north["action_present"],
            {"same": 0, "changed": 2, "evaluable": 2},
        )
        self.assertEqual(
            north["action_absent"],
            {"same": 2, "changed": 0, "evaluable": 2},
        )

    def test_module_has_no_hidden_world_mechanic_access(self):
        source = (
            EXPERIMENTS / "open_object_world_action_association.py"
        ).read_text()
        for forbidden in (
            "_mass",
            'get("_kind")',
            "mechanism_active",
            "barrier_open",
            "_latched",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
