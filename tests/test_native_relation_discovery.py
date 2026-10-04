from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in (
    "world2_ecology",
    "world2_native_observation",
    "world3_ecology",
    "world3_native_observation",
    "native_relation_discovery",
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


class NativeRelationDiscoveryTests(unittest.TestCase):
    def test_proposals_are_composed_from_observed_features_not_world_truth(self):
        world = w3.initial_world3_state(seed=3)
        samples = [w3n.native_world3_observation(w3.observe_world3(world))]
        proposals = relations.propose_relations(samples)
        rendered = repr(proposals)
        self.assertNotIn("phase", rendered)
        self.assertNotIn("cue_sites", rendered)
        self.assertTrue(proposals)

    def test_world2_delayed_signal_sequence_yields_competing_relations(self):
        world = w2.initial_world2_state(seed=1)
        samples = [w2n.native_world2_observation(w2.observe_world2(world))]
        for cycle, action in enumerate(("north", "interact", "observe", "observe", "observe", "observe"), start=1):
            world, record = w2.transition_world2(world, action, cycle=cycle)
            samples.append(w2n.native_world2_observation(w2.observe_world2(world), action_receipt=record))
        proposals = relations.propose_relations(samples)
        ledger = relations.evaluate_relations(proposals, samples)
        slow = [x for x in ledger if x["proposal"]["feature"] == "slow_signal"]
        self.assertTrue(any(x["status"] == "supported" for x in slow))
        self.assertTrue(any(x["status"] == "challenged" for x in slow))
        candidate = relations.grounded_relation_candidate(relations.select_relation_inquiry(ledger))
        self.assertIsNotNone(candidate)

    def test_world3_local_cue_sequence_uses_same_relation_engine(self):
        world = w3.initial_world3_state(seed=2)
        world["position"] = [0, 1]
        samples = [w3n.native_world3_observation(w3.observe_world3(world))]
        for cycle in range(1, 6):
            world, record = w3.transition_world3(world, "observe", cycle=cycle)
            samples.append(w3n.native_world3_observation(w3.observe_world3(world), action_receipt=record))
        ledger = relations.evaluate_relations(relations.propose_relations(samples), samples)
        cue = [x for x in ledger if x["proposal"]["feature"] == "local_cue"]
        self.assertTrue(cue)
        self.assertTrue(any(x["refutations"] or x["confirmations"] for x in cue))

    def test_relation_engine_contains_no_world_specific_imports_or_truth_names(self):
        source = (EXPERIMENTS / "native_relation_discovery.py").read_text(encoding="utf-8")
        for forbidden in (
            "world2_",
            "world3_",
            "latent_mode",
            "resource_phase",
            "cue_sites",
            "pending_slow_effects",
            "seed",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
