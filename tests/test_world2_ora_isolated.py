from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state


EXPERIMENTS = Path(__file__).parents[1] / "experiments"
for name in ("world2_ecology",):
    path = EXPERIMENTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[name] = module

adapter_path = EXPERIMENTS / "world2_ora_isolated.py"
adapter_spec = importlib.util.spec_from_file_location("world2_ora_isolated", adapter_path)
adapter = importlib.util.module_from_spec(adapter_spec)
assert adapter_spec.loader is not None
adapter_spec.loader.exec_module(adapter)


class World2OraIsolatedTests(unittest.TestCase):
    def test_trial_does_not_mutate_source_state(self) -> None:
        source = initial_state()
        before = copy.deepcopy(source)
        result = adapter.run_isolated_ora_world2_trial(
            source,
            seed=1,
            actions=["north", "interact", "south", "observe", "observe", "observe"],
        )
        self.assertEqual(source, before)
        self.assertGreater(result["ora_final"]["cycles"], source["cycles"])

    def test_trial_is_reproducible_for_same_source_seed_and_actions(self) -> None:
        source = initial_state()
        actions = ["north", "interact", "south", "observe", "observe", "observe"]
        first = adapter.run_isolated_ora_world2_trial(source, seed=2, actions=actions)
        second = adapter.run_isolated_ora_world2_trial(source, seed=2, actions=actions)
        # Ignore wall-clock metadata while comparing scientific outputs.
        self.assertEqual(first["world_final"], second["world_final"])
        self.assertEqual(
            [item["world"] for item in first["cycles"]],
            [item["world"] for item in second["cycles"]],
        )
        self.assertEqual(
            [item["question"]["text"] if item["question"] else None for item in first["cycles"]],
            [item["question"]["text"] if item["question"] else None for item in second["cycles"]],
        )

    def test_adapter_has_no_production_state_path_or_growth_reference(self) -> None:
        source = adapter_path.read_text(encoding="utf-8")
        self.assertNotIn('"state/organism.json"', source)
        self.assertNotIn("autonomous/growth", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("requests", source)

    def test_adapter_does_not_grant_action_or_planning_lab_authority(self) -> None:
        source = initial_state()
        result = adapter.run_isolated_ora_world2_trial(
            source,
            seed=1,
            actions=["observe", "observe"],
        )
        self.assertEqual(result["ora_final"]["action_lab"]["history"], [])
        self.assertEqual(result["ora_final"]["planning_lab"]["executions"], [])


if __name__ == "__main__":
    unittest.main()
