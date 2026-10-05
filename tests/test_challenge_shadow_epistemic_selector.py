from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.state import StateStore, initial_state
from challenge_shadow_epistemic_selector import select_epistemic_command
from challenge_shadow_recorder import ChallengeShadowRecorder, action_label
from open_object_world_challenge import initial_world, observe_world, transition
from open_object_world_challenge_explorer import (
    candidate_commands,
    choose_command,
    command_key,
    observation_signature,
)


def association(feature, command, *, present=2, changed=1):
    label = action_label(command)
    return {
        "id": "A:" + label,
        "relation": "action_associated_with_change",
        "feature": feature,
        "action": label,
        "status": "association_observed",
        "effect_difference": 0.1,
        "action_present": {
            "evaluable": present,
            "changed": changed,
            "same": present - changed,
        },
        "action_absent": {
            "evaluable": 4,
            "changed": 1,
            "same": 3,
        },
        "evaluable": present + 4,
    }


class ChallengeShadowEpistemicSelectorTests(unittest.TestCase):
    def test_empty_evidence_reduces_uncertainty_with_frozen_tie_break(self):
        observation = observe_world(initial_world(1))
        result = select_epistemic_command(
            observation,
            feature="visible_ids",
            relation="same_next_observation",
            associations=[],
        )
        self.assertEqual(result["policy"], "public-falsification-oriented-v1")
        self.assertEqual(result["mode"], "reduce_action_uncertainty")
        self.assertEqual(result["command"], {"action": "north"})
        self.assertEqual(result["present_evaluable"], 0)

    def test_persisted_exposure_changes_least_sampled_choice(self):
        observation = observe_world(initial_world(1))
        north = {"action": "north"}
        result = select_epistemic_command(
            observation,
            feature="visible_ids",
            relation="same_next_observation",
            associations=[
                association("visible_ids", north, present=2, changed=1),
            ],
        )
        self.assertEqual(result["mode"], "reduce_action_uncertainty")
        self.assertEqual(result["command"], {"action": "east"})
        self.assertNotEqual(result["command"], {"action": "north"})

    def test_fully_sampled_policy_seeks_disconfirming_observation(self):
        observation = observe_world(initial_world(1))
        commands = candidate_commands(observation)
        rows = []
        for command in commands:
            rows.append(
                association(
                    "visible_ids",
                    command,
                    present=3,
                    changed=(3 if command == {"action": "north"} else 0),
                )
            )
        result = select_epistemic_command(
            observation,
            feature="visible_ids",
            relation="same_next_observation",
            associations=rows,
        )
        self.assertEqual(result["mode"], "seek_disconfirming_observation")
        self.assertEqual(result["command"], {"action": "north"})
        self.assertGreater(result["falsification_probability"], 0.5)
        self.assertIsNotNone(result["epistemic_score"])

    def test_selection_is_deterministic_under_association_order(self):
        observation = observe_world(initial_world(1))
        commands = candidate_commands(observation)[:4]
        rows = [
            association("visible_ids", command, present=3, changed=index % 3)
            for index, command in enumerate(commands)
        ]
        left = select_epistemic_command(
            observation,
            feature="visible_ids",
            relation="same_next_observation",
            associations=rows,
        )
        right = select_epistemic_command(
            observation,
            feature="visible_ids",
            relation="same_next_observation",
            associations=list(reversed(rows)),
        )
        self.assertEqual(left, right)

    def test_real_recorder_associations_survive_reload_and_drive_same_choice(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "recorder.json")
        store.save(initial_state())
        recorder = ChallengeShadowRecorder(store, enabled=True)
        world = initial_world(1)
        attempts = Counter()
        observation = observe_world(world)
        recorder.ingest(observation)

        for cycle in range(1, 120):
            command = choose_command(observation, attempts)
            attempts[(observation_signature(observation), command_key(command))] += 1
            world, receipt = transition(world, command, cycle=cycle)
            observation = observe_world(world)
            recorder.ingest(observation, receipt)

        publication = recorder.publication()
        candidate = publication["selected_temporal_candidate"]
        associations = recorder.action_associations()
        before = select_epistemic_command(
            observation,
            feature=candidate["feature"],
            relation=candidate["relation"],
            associations=associations,
        )

        reloaded = ChallengeShadowRecorder(
            StateStore(store.path),
            enabled=True,
        )
        after = select_epistemic_command(
            reloaded.latest_observation(),
            feature=candidate["feature"],
            relation=candidate["relation"],
            associations=reloaded.action_associations(),
        )
        self.assertEqual(before, after)
        self.assertGreater(len(associations), 0)


if __name__ == "__main__":
    unittest.main()
