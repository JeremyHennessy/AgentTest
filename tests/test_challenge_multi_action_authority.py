from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from challenge_action_authority import ChallengeActionExecutor
from challenge_shadow_recorder import (
    ChallengeShadowRecorder,
    single_transition_outcome,
    source_manifest,
)
from native_observe_inquire_integration import (
    observe_and_inquire_policy,
    stage_publication_inquiry,
)
from open_object_world_challenge import initial_world, observe_world, transition
from open_object_world_challenge_explorer import (
    choose_command,
    command_key,
    observation_signature,
)


class ChallengeMultiActionAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _prefix(self, steps=600):
        recorder_store = StateStore(self.root / "recorder.json")
        recorder_store.save(initial_state())
        recorder = ChallengeShadowRecorder(recorder_store, enabled=True)
        world = initial_world(1)
        attempts = Counter()
        observation = observe_world(world)
        recorder.ingest(observation)
        for cycle in range(1, steps + 1):
            command = choose_command(observation, attempts)
            attempts[(observation_signature(observation), command_key(command))] += 1
            world, receipt = transition(world, command, cycle=cycle)
            observation = observe_world(world)
            recorder.ingest(observation, receipt)
        return recorder, world

    def _stage(self, ora: StateStore, recorder: ChallengeShadowRecorder):
        result = stage_publication_inquiry(
            AgentCore(ora),
            policy=observe_and_inquire_policy(),
            source_manifest=source_manifest(),
            publication=recorder.publication(),
        )
        return result["inquiry_result"]["experiment"]["id"]

    def test_each_action_requires_fresh_native_experiment(self):
        recorder, world = self._prefix()
        ora = StateStore(self.root / "ora.json")
        ora.save(initial_state())
        executor = ChallengeActionExecutor.create(
            self.root / "executor.json",
            world=world,
            max_actions=2,
        )

        first_experiment = self._stage(ora, recorder)
        first = executor.issue(
            ora_store=ora,
            recorder=recorder,
            experiment_id=first_experiment,
        )
        first_token = first["token"]
        self.assertEqual(first_token["id"], "CAC000001")
        self.assertEqual(first_token["budget_ordinal"], 1)
        first_before = recorder.latest_observation()
        first_result = ChallengeActionExecutor(executor.path).execute(first_token)
        recorder.ingest(first_result["observation"], first_result["receipt"])

        with self.assertRaisesRegex(RuntimeError, "already received"):
            ChallengeActionExecutor(executor.path).issue(
                ora_store=ora,
                recorder=recorder,
                experiment_id=first_experiment,
            )

        first_outcome = single_transition_outcome(
            before=first_before,
            after=first_result["observation"],
            candidate=recorder.publication()["selected_temporal_candidate"],
        )
        # The inquiry candidate was selected before the action; reconstruct it
        # from the persisted experiment instead of relying on the new publication.
        state = ora.load()
        exp = next(row for row in state["experiments"] if row["id"] == first_experiment)
        relation = exp["native_inquiry"]["relation"]
        first_candidate = {
            "feature": relation["feature"],
            "relation": relation["kind"],
        }
        first_outcome = single_transition_outcome(
            before=first_before,
            after=first_result["observation"],
            candidate=first_candidate,
        )
        self.assertIsNotNone(first_outcome)
        evidence = AgentCore(ora).record_native_evidence(
            first_outcome,
            enabled=True,
            persist=True,
        )
        AgentCore(ora).resolve_native_inquiry(
            first_experiment,
            evidence["evidence_ref"],
            enabled=True,
            persist=True,
        )

        second_experiment = self._stage(ora, recorder)
        self.assertNotEqual(second_experiment, first_experiment)
        second = ChallengeActionExecutor(executor.path).issue(
            ora_store=ora,
            recorder=recorder,
            experiment_id=second_experiment,
        )
        second_token = second["token"]
        self.assertEqual(second_token["id"], "CAC000002")
        self.assertEqual(second_token["budget_ordinal"], 2)
        self.assertNotEqual(
            second_token["recorder_chain_hash"],
            first_token["recorder_chain_hash"],
        )
        second_result = ChallengeActionExecutor(executor.path).execute(second_token)
        self.assertEqual(second_result["remaining_budget"], 0)
        with self.assertRaisesRegex(RuntimeError, "already consumed"):
            ChallengeActionExecutor(executor.path).execute(second_token)


if __name__ == "__main__":
    unittest.main()
