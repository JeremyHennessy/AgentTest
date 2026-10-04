from __future__ import annotations

import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import StateStore

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in ("world2_ecology", "world2_ora_isolated"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module

adapter = sys.modules["world2_ora_isolated"]
world2 = sys.modules["world2_ecology"]


class World2ObservationContractTests(unittest.TestCase):
    def _observation(self):
        return world2.observe_world2(world2.initial_world2_state(seed=1))

    def test_clock_only_change_is_not_a_baseline_change(self):
        first = self._observation()
        second = copy.deepcopy(first)
        second["cycle"] += 1
        self.assertEqual(
            adapter.world2_repository_shaped_observation(first),
            adapter.world2_repository_shaped_observation(second),
            "Elapsed time alone must not manufacture a repository intervention.",
        )

    def test_resource_change_is_data_not_an_intervention(self):
        first = self._observation()
        first["local_resource"] = 1
        second = copy.deepcopy(first)
        second["cycle"] += 1
        second["local_resource"] = 2
        before = adapter.world2_repository_shaped_observation(first)
        after = adapter.world2_repository_shaped_observation(second)
        self.assertNotEqual(before["test_files"], after["test_files"])
        self.assertEqual(before["baseline_fingerprint"], after["baseline_fingerprint"])

    def test_real_cycle_accepts_unchanged_readings_as_confirmation(self):
        first = self._observation()
        second = copy.deepcopy(first)
        second["cycle"] += 1
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "organism.json"
            AgentCore(StateStore(path)).cycle(
                observation=adapter.world2_repository_shaped_observation(first),
                cognition=False, strict_experiment_admission=True,
            )
            result = AgentCore(StateStore(path)).cycle(
                observation=adapter.world2_repository_shaped_observation(second),
                cognition=False, strict_experiment_admission=True,
            )
        self.assertEqual(result["prediction_result"]["status"], "confirmed")

    def test_world_version_change_is_still_an_intervention(self):
        first = self._observation()
        second = copy.deepcopy(first)
        second["world_version"] = "test-only-different-world-version"
        self.assertNotEqual(
            adapter.world2_repository_shaped_observation(first)["baseline_fingerprint"],
            adapter.world2_repository_shaped_observation(second)["baseline_fingerprint"],
        )


if __name__ == "__main__":
    unittest.main()
