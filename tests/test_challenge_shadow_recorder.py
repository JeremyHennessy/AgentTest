from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.state import StateStore, initial_state
from challenge_shadow_recorder import (
    ChallengeShadowRecorder,
    SOURCE_ID,
    reviewed_source_descriptor,
    single_transition_outcome,
    source_manifest,
    validate_observation,
)
from native_observe_inquire_integration import (
    observe_and_inquire_policy,
    validate_publication,
)
from open_object_world_challenge import initial_world, observe_world, transition
from open_object_world_challenge_explorer import (
    choose_command,
    command_key,
    observation_signature,
)


class ChallengeShadowRecorderTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        store.save(initial_state())
        return store

    def stream(self, steps=80):
        store = self.make_store()
        recorder = ChallengeShadowRecorder(store, enabled=True)
        world = initial_world(1)
        attempts = Counter()
        observation = observe_world(world)
        recorder.ingest(observation)
        observations = [observation]
        receipts = []
        for cycle in range(1, steps + 1):
            command = choose_command(observation, attempts)
            attempts[(observation_signature(observation), command_key(command))] += 1
            world, receipt = transition(world, command, cycle=cycle)
            observation = observe_world(world)
            recorder.ingest(observation, receipt)
            observations.append(observation)
            receipts.append(receipt)
        return store, recorder, world, attempts, observations, receipts

    def test_disabled_by_default(self):
        store = self.make_store()
        before = store.path.read_bytes()
        with self.assertRaises(RuntimeError):
            ChallengeShadowRecorder(store)
        self.assertEqual(store.path.read_bytes(), before)

    def test_reviewed_source_descriptor_is_exact_and_non_authoritative(self):
        descriptor = reviewed_source_descriptor()
        self.assertEqual(
            descriptor["commit"],
            "80c0f63163d08aa2efc04ca60e1c41032ba2e839",
        )
        self.assertEqual(
            descriptor["world_blob"],
            "49683553596400e8c7b49b5ed5fdec5f937b7a22",
        )
        self.assertEqual(
            descriptor["explorer_blob"],
            "db5415b17077fdad65bf1671700f79979ff92be1",
        )
        manifest = source_manifest()
        self.assertEqual(manifest["source_id"], SOURCE_ID)
        self.assertFalse(manifest["signed_source"])
        self.assertFalse(manifest["allow_environment_actions"])

    def test_hidden_observation_field_is_rejected(self):
        observation = observe_world(initial_world(1))
        observation["_hidden"] = "no"
        with self.assertRaises(ValueError):
            validate_observation(observation)

    def test_identical_delivery_is_idempotent_and_conflict_fails(self):
        store = self.make_store()
        recorder = ChallengeShadowRecorder(store, enabled=True)
        observation = observe_world(initial_world(1))
        self.assertTrue(recorder.ingest(observation))
        before = store.path.read_bytes()
        self.assertFalse(recorder.ingest(observation))
        self.assertEqual(store.path.read_bytes(), before)
        conflicting = dict(observation)
        conflicting["position"] = [-1, 0]
        with self.assertRaises(ValueError):
            recorder.ingest(conflicting)
        self.assertEqual(store.path.read_bytes(), before)

    def test_stream_publishes_valid_native_inquiry_candidate(self):
        _, recorder, _, _, _, _ = self.stream(100)
        publication = recorder.publication()
        checked = validate_publication(
            publication,
            source_manifest(),
            observe_and_inquire_policy(),
        )
        candidate = checked["selected_temporal_candidate"]
        self.assertGreaterEqual(candidate["evaluable"], 3)
        self.assertIn(
            candidate["relation"],
            {"same_next_observation", "changes_next_observation"},
        )
        self.assertGreaterEqual(candidate["objective_score"], 0.0)
        self.assertLessEqual(candidate["objective_score"], 1.0)

    def test_recorder_retains_only_latest_public_observation_not_raw_trace(self):
        store, _, _, _, observations, receipts = self.stream(100)
        state = store.load()
        cursor = state["challenge_shadow_recorder_v1"]
        self.assertEqual(cursor["latest"], observations[-1])
        self.assertNotIn("observations", cursor)
        self.assertNotIn("receipts", cursor)
        self.assertNotIn("history", cursor)
        self.assertEqual(len(receipts), 100)

    def test_single_transition_outcome_matches_selected_relation(self):
        _, recorder, world, attempts, _, _ = self.stream(120)
        publication = recorder.publication()
        candidate = publication["selected_temporal_candidate"]
        for cycle in range(121, 181):
            before = observe_world(world)
            command = choose_command(before, attempts)
            attempts[(observation_signature(before), command_key(command))] += 1
            world, receipt = transition(world, command, cycle=cycle)
            after = observe_world(world)
            recorder.ingest(after, receipt)
            outcome = single_transition_outcome(
                before=before,
                after=after,
                candidate=candidate,
            )
            if outcome is not None:
                self.assertEqual(outcome["measurement"]["evaluable"], 1)
                self.assertEqual(
                    outcome["measurement"]["confirmations"]
                    + outcome["measurement"]["refutations"],
                    1,
                )
                return
        self.fail("selected temporal feature never became evaluable post-inquiry")


if __name__ == "__main__":
    unittest.main()
