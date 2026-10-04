from __future__ import annotations

import importlib.util
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in ("world3_ecology", "world3_native_observation", "world3_transfer_adapter"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

world3 = sys.modules["world3_ecology"]
native = sys.modules["world3_native_observation"]
transfer = sys.modules["world3_transfer_adapter"]


def sample(world, record=None):
    return native.native_world3_observation(
        world3.observe_world3(world), action_receipt=record
    )


def through_core(state):
    candidate = transfer.world3_candidate(state)
    if candidate is None:
        return None
    working = deepcopy(state)
    core = AgentCore.__new__(AgentCore)
    intention = {
        "id": "W3I000001",
        "cycle": working["cycles"],
        "kind": "reduce_uncertainty",
        "dominant_drive": candidate["dominant_drive"],
        "strength": 1.0 if candidate["dominant_drive"] == "prediction_error" else 0.5,
        "target": None,
        "rationale": "World 3 transfer candidate from local observable evidence.",
        "evidence_refs": list(candidate["evidence_refs"]),
    }
    working["intentions"].append(intention)
    question_text = core._generate_question(working, None, intention, candidate)
    question = core._upsert_question(working, question_text)
    question["source"] = "world3_transfer"
    question["source_evidence_refs"] = list(candidate["evidence_refs"])
    experiment = core._select_or_propose_experiment(
        working, question, intention, candidate, require_grounded=True
    )
    return candidate, intention, question, experiment


class World3TransferTests(unittest.TestCase):
    def test_world3_has_no_world2_hidden_mechanisms(self):
        world = world3.initial_world3_state(seed=1)
        rendered = repr(world)
        self.assertNotIn("slow_signal", rendered)
        self.assertNotIn("pending_slow_effects", rendered)
        self.assertNotIn("resources", rendered)

    def test_local_cue_change_reaches_real_core_across_four_independent_phases(self):
        for seed in range(1, 5):
            with self.subTest(seed=seed):
                state = initial_state()
                world = world3.initial_world3_state(seed=seed)
                world["position"] = [0, 1]
                transfer.consume_world3(state, sample(world))
                initial = world["cue_sites"]["0,1"]
                for cycle in range(1, 6):
                    world, record = world3.transition_world3(world, "observe", cycle=cycle)
                    transfer.consume_world3(state, sample(world, record))
                    if world["cue_sites"]["0,1"] != initial:
                        break
                result = through_core(state)
                self.assertIsNotNone(result)
                candidate, intention, question, experiment = result
                self.assertEqual(intention["dominant_drive"], "prediction_error")
                self.assertTrue(question["source_evidence_refs"])
                self.assertEqual(experiment["hypothesis"], candidate["hypothesis"])
                self.assertEqual(experiment["method"], candidate["experiment"])

    def test_consumed_object_refutes_persistence_only_when_same_site_is_observed(self):
        state = initial_state()
        world = world3.initial_world3_state(seed=1)
        world["position"] = [1, 1]
        transfer.consume_world3(state, sample(world))
        world, record = world3.transition_world3(world, "interact", cycle=1)
        transfer.consume_world3(state, sample(world, record))
        result = through_core(state)
        self.assertIsNotNone(result)
        candidate, intention, question, experiment = result
        self.assertEqual(intention["dominant_drive"], "prediction_error")
        self.assertIn("object A", candidate["question"])

    def test_hidden_phase_does_not_enter_observation_memory_or_core_candidate(self):
        for seed in range(1, 5):
            state = initial_state()
            world = world3.initial_world3_state(seed=seed)
            transfer.consume_world3(state, sample(world))
            rendered = repr(state[transfer.WORLD3_MEMORY_KEY])
            self.assertNotIn("'phase'", rendered)
            candidate = transfer.world3_candidate(state)
            self.assertNotIn("phase", repr(candidate).lower())

    def test_empty_memory_does_not_manufacture_candidate(self):
        self.assertIsNone(transfer.world3_candidate(initial_state()))


if __name__ == "__main__":
    unittest.main()
