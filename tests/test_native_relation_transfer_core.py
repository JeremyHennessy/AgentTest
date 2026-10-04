from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology", "world2_native_observation",
    "native_relation_discovery", "native_relation_family_memory",
    "native_relation_transfer_core",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

w2 = sys.modules["world2_ecology"]
w2n = sys.modules["world2_native_observation"]
relations = sys.modules["native_relation_discovery"]
families = sys.modules["native_relation_family_memory"]
transfer = sys.modules["native_relation_transfer_core"]


def trained_state():
    state = initial_state()
    world = w2.initial_world2_state(seed=1)
    samples = [w2n.native_world2_observation(w2.observe_world2(world))]
    for cycle, action in enumerate(
        ("north", "interact", "observe", "observe", "observe", "observe"), start=1
    ):
        world, record = w2.transition_world2(world, action, cycle=cycle)
        samples.append(
            w2n.native_world2_observation(
                w2.observe_world2(world), action_receipt=record
            )
        )
    ledger = relations.evaluate_relations(relations.propose_relations(samples), samples)
    families.update_family_memory(state, ledger)
    return state


HELD_OUT = [
    {"id": "H1", "version": relations.RELATION_VERSION, "relation": "action_precedes_change", "feature": "local_cue", "action": "interact"},
    {"id": "H2", "version": relations.RELATION_VERSION, "relation": "same_next_observation", "feature": "local_cue", "action": None},
    {"id": "H3", "version": relations.RELATION_VERSION, "relation": "changes_next_observation", "feature": "local_cue", "action": None},
]


class NativeRelationTransferCoreTests(unittest.TestCase):
    def test_training_changes_held_out_relation_scores_reaching_core(self):
        trained = transfer.run_held_out_relation_core_path(trained_state(), HELD_OUT)
        blank = transfer.run_held_out_relation_core_path(initial_state(), HELD_OUT)
        self.assertEqual(trained["status"], "proposed")
        self.assertEqual(blank["status"], "proposed")
        trained_scores = {
            item["proposal"]["id"]: item["score"] for item in trained["ranked"]
        }
        blank_scores = {
            item["proposal"]["id"]: item["score"] for item in blank["ranked"]
        }
        self.assertTrue(
            any(trained_scores[key] > blank_scores[key] for key in trained_scores)
        )
        self.assertGreater(trained["selected"]["score"], blank["selected"]["score"])
        self.assertEqual(trained["question"]["source"], "native_relation_family_transfer")
        self.assertEqual(
            trained["experiment"]["hypothesis"],
            trained["candidate"]["hypothesis"],
        )

    def test_transfer_core_path_does_not_execute_or_read_target_truth(self):
        source = (EXPERIMENTS / "native_relation_transfer_core.py").read_text(encoding="utf-8")
        for forbidden in (
            "world3",
            "cue_sites",
            "transition_world",
            ".cycle(",
            ".save(",
            "StateStore",
            "subprocess",
            "requests",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
