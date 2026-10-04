from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state


EXPERIMENTS = Path(__file__).parents[1] / "experiments"
for name in ("world2_ecology", "world2_ora_isolated"):
    path = EXPERIMENTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[name] = module

path = EXPERIMENTS / "world2_ora_compare.py"
spec = importlib.util.spec_from_file_location("world2_ora_compare", path)
compare = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compare)


class World2OraComparisonTests(unittest.TestCase):
    def test_comparison_preserves_source_and_equal_cycle_count(self) -> None:
        source = initial_state()
        before = copy.deepcopy(source)
        actions = ["north", "interact", "south", "observe", "observe", "observe", "west", "observe"]
        result = compare.compare_world2_to_control(source, seed=1, actions=actions)
        self.assertEqual(source, before)
        self.assertEqual(result["control"]["cycle_count"], len(actions))
        self.assertEqual(result["world2"]["cycle_count"], len(actions))

    def test_comparison_is_reproducible(self) -> None:
        source = initial_state()
        actions = ["north", "interact", "south", "observe", "observe", "observe", "west", "observe"]
        first = compare.compare_world2_to_control(source, seed=2, actions=actions)
        second = compare.compare_world2_to_control(source, seed=2, actions=actions)
        self.assertEqual(first, second)

    def test_comparison_does_not_assert_world2_must_win(self) -> None:
        source = (EXPERIMENTS / "world2_ora_compare.py").read_text(encoding="utf-8")
        self.assertNotIn("assert world2", source.lower())
        self.assertNotIn("phase 43", source.lower())


if __name__ == "__main__":
    unittest.main()
