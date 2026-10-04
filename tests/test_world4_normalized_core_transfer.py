from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(EXPERIMENTS))
sys.path.insert(0, str(SCRIPTS_DIR))

for name in (
    "world4_toggle_ecology",
    "world4_native_observation",
    "normalized_relation_evidence",
    "normalized_inquiry_objectives",
    "normalized_inquiry_core",
    "prospective_inquiry_benchmark",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world4 = sys.modules["world4_toggle_ecology"]
native = sys.modules["world4_native_observation"]
normalized = sys.modules["normalized_relation_evidence"]
objectives = sys.modules["normalized_inquiry_objectives"]
core_path = sys.modules["normalized_inquiry_core"]

from prospective_objective_robustness import choose_split
from world4_objective_holdout import SCRIPTS


def samples(seed, actions):
    world = world4.initial_world4_state(seed=seed)
    result = [native.native_world4_observation(world4.observe_world4(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = world4.transition_world4(world, action, cycle=cycle)
        result.append(
            native.native_world4_observation(
                world4.observe_world4(world), action_receipt=record
            )
        )
    return result


class World4NormalizedCoreTransferTests(unittest.TestCase):
    def test_information_gain_and_discrimination_are_behaviorally_equivalent_on_holdout(self):
        comparisons = 0
        for seed in range(1, 5):
            for _, actions in SCRIPTS:
                trajectory = samples(seed, actions)
                for split_name in ("early", "midpoint", "late"):
                    split = choose_split(split_name, len(trajectory))
                    candidates = normalized.normalized_relation_candidates(
                        normalized.normalized_evidence(trajectory[:split])
                    )
                    ig = next(
                        x
                        for x in objectives.rank_normalized_candidates(
                            candidates, "information_gain"
                        )
                        if x["eligible"]
                    )
                    disc = next(
                        x
                        for x in objectives.rank_normalized_candidates(
                            candidates, "discrimination"
                        )
                        if x["eligible"]
                    )
                    ig_key = (
                        ig["candidate"]["relation"],
                        ig["candidate"]["feature"],
                        ig["candidate"].get("action"),
                    )
                    disc_key = (
                        disc["candidate"]["relation"],
                        disc["candidate"]["feature"],
                        disc["candidate"].get("action"),
                    )
                    self.assertEqual(ig_key, disc_key)
                    comparisons += 1
        self.assertEqual(comparisons, 72)

    def test_information_gain_holdout_candidates_traverse_real_copied_core(self):
        proposed = 0
        for seed in range(1, 5):
            for _, actions in SCRIPTS:
                trajectory = samples(seed, actions)
                for split_name in ("early", "midpoint", "late"):
                    split = choose_split(split_name, len(trajectory))
                    candidates = normalized.normalized_relation_candidates(
                        normalized.normalized_evidence(trajectory[:split])
                    )
                    result = core_path.run_normalized_core_path(
                        initial_state(), candidates, "information_gain"
                    )
                    self.assertEqual(result["status"], "proposed")
                    self.assertEqual(
                        result["question"]["source"],
                        "normalized_inquiry_objective",
                    )
                    self.assertNotIn(
                        " causes ",
                        result["candidate"]["hypothesis"].lower(),
                    )
                    proposed += 1
        self.assertEqual(proposed, 72)


if __name__ == "__main__":
    unittest.main()
