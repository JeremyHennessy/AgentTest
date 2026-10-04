from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology", "world2_native_observation",
    "world3_ecology", "world3_native_observation",
    "native_relation_discovery", "native_relation_family_memory",
):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

w2 = sys.modules["world2_ecology"]
w2n = sys.modules["world2_native_observation"]
w3 = sys.modules["world3_ecology"]
w3n = sys.modules["world3_native_observation"]
relations = sys.modules["native_relation_discovery"]
families = sys.modules["native_relation_family_memory"]


def train_world2():
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
    return relations.evaluate_relations(relations.propose_relations(samples), samples)


class NativeRelationFamilyTransferTests(unittest.TestCase):
    def test_family_memory_survives_json_reload(self):
        state = initial_state()
        families.update_family_memory(state, train_world2())
        before = state[families.FAMILY_MEMORY_KEY]
        restored = json.loads(json.dumps(state, sort_keys=True))
        self.assertEqual(restored[families.FAMILY_MEMORY_KEY], before)

    def test_prior_family_evidence_changes_held_out_combination_priority(self):
        state = initial_state()
        ledger = train_world2()
        families.update_family_memory(state, ledger)

        # Held-out combinations: World 3's local_cue feature never appeared in World 2.
        held_out = [
            {
                "id": "H1",
                "version": relations.RELATION_VERSION,
                "relation": "action_precedes_change",
                "feature": "local_cue",
                "action": "interact",
            },
            {
                "id": "H2",
                "version": relations.RELATION_VERSION,
                "relation": "same_next_observation",
                "feature": "local_cue",
                "action": None,
            },
            {
                "id": "H3",
                "version": relations.RELATION_VERSION,
                "relation": "changes_next_observation",
                "feature": "local_cue",
                "action": None,
            },
        ]
        ranked = families.rank_held_out_proposals(state, held_out)
        baseline = families.rank_held_out_proposals(initial_state(), held_out)
        trained_scores = {
            item["proposal"]["id"]: item["score"] for item in ranked
        }
        baseline_scores = {
            item["proposal"]["id"]: item["score"] for item in baseline
        }
        self.assertTrue(
            any(
                trained_scores[proposal_id] > baseline_scores[proposal_id]
                for proposal_id in trained_scores
            )
        )
        self.assertTrue(
            any(item["family_evidence"]["evaluable"] > 0 for item in ranked)
        )

    def test_held_out_feature_is_not_present_in_training_memory(self):
        state = initial_state()
        families.update_family_memory(state, train_world2())
        rendered = repr(state[families.FAMILY_MEMORY_KEY])
        self.assertNotIn("local_cue", rendered)

    def test_ranking_does_not_inspect_world3_truth(self):
        source = (EXPERIMENTS / "native_relation_family_memory.py").read_text(encoding="utf-8")
        for forbidden in (
            "world3",
            "cue_sites",
            "phase",
            "latent_mode",
            "seed",
            "transition_world",
        ):
            self.assertNotIn(forbidden, source)

    def test_world3_can_supply_held_out_feature_only_after_transfer_ranking(self):
        world = w3.initial_world3_state(seed=2)
        world["position"] = [0, 1]
        observation = w3n.native_world3_observation(w3.observe_world3(world))
        self.assertEqual(observation["local_cue"]["status"], "measured")
        self.assertEqual(observation["local_cue"]["scope"], "local")


if __name__ == "__main__":
    unittest.main()
