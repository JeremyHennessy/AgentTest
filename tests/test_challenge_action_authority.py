from __future__ import annotations

import shutil
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from challenge_action_authority import (
    ChallengeActionExecutor,
    _unsafe_replace_world_for_adversarial_test,
)
from challenge_shadow_recorder import ChallengeShadowRecorder, source_manifest
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


class ChallengeActionAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def prepared(self, steps=120):
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

        ora_store = StateStore(self.root / "ora.json")
        ora_store.save(initial_state())
        staged = stage_publication_inquiry(
            AgentCore(ora_store),
            policy=observe_and_inquire_policy(),
            source_manifest=source_manifest(),
            publication=recorder.publication(),
        )
        experiment_id = staged["inquiry_result"]["experiment"]["id"]
        executor = ChallengeActionExecutor.create(
            self.root / "executor.json",
            world=world,
            max_actions=1,
        )
        return recorder, ora_store, executor, experiment_id, world, attempts

    def test_issue_and_execute_once_then_restart_replay_fails(self):
        recorder, ora, executor, experiment_id, _, _ = self.prepared()
        issued = executor.issue(
            ora_store=ora,
            recorder=recorder,
            experiment_id=experiment_id,
        )
        token = issued["token"]
        result = ChallengeActionExecutor(executor.path).execute(token)
        self.assertEqual(result["actions_consumed"], 1)
        self.assertEqual(result["remaining_budget"], 0)
        before = executor.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "already consumed"):
            ChallengeActionExecutor(executor.path).execute(token)
        self.assertEqual(executor.path.read_bytes(), before)

    def test_command_mutation_fails_without_state_change(self):
        recorder, ora, executor, experiment_id, _, _ = self.prepared()
        token = executor.issue(
            ora_store=ora,
            recorder=recorder,
            experiment_id=experiment_id,
        )["token"]
        bad = deepcopy(token)
        bad["command"] = {"action": "south"}
        before = executor.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "modified"):
            executor.execute(bad)
        self.assertEqual(executor.path.read_bytes(), before)

    def test_source_mutation_fails_without_state_change(self):
        recorder, ora, executor, experiment_id, _, _ = self.prepared()
        token = executor.issue(
            ora_store=ora,
            recorder=recorder,
            experiment_id=experiment_id,
        )["token"]
        bad = deepcopy(token)
        bad["source_id"] = "research.other"
        before = executor.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            executor.execute(bad)
        self.assertEqual(executor.path.read_bytes(), before)

    def test_stale_world_fails_without_consumption(self):
        recorder, ora, executor, experiment_id, world, attempts = self.prepared()
        token = executor.issue(
            ora_store=ora,
            recorder=recorder,
            experiment_id=experiment_id,
        )["token"]
        observation = observe_world(world)
        alternate = choose_command(observation, attempts)
        advanced, _ = transition(world, alternate, cycle=observation["cycle"] + 1)
        _unsafe_replace_world_for_adversarial_test(executor.path, advanced)
        before = executor.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "stale"):
            ChallengeActionExecutor(executor.path).execute(token)
        self.assertEqual(executor.path.read_bytes(), before)
        state = ChallengeActionExecutor(executor.path).load()
        record = state["capabilities"][0]
        self.assertEqual(record["status"], "issued")
        self.assertEqual(state["actions_consumed"], 0)

    def test_budget_exhaustion_blocks_second_issue(self):
        recorder, ora, executor, experiment_id, _, _ = self.prepared()
        token = executor.issue(
            ora_store=ora,
            recorder=recorder,
            experiment_id=experiment_id,
        )["token"]
        result = executor.execute(token)
        recorder.ingest(result["observation"], result["receipt"])
        with self.assertRaisesRegex(RuntimeError, "budget is exhausted"):
            executor.issue(
                ora_store=ora,
                recorder=recorder,
                experiment_id=experiment_id,
            )

    def test_issue_requires_native_readiness(self):
        recorder, ora, executor, experiment_id, _, _ = self.prepared()
        state = ora.load()
        experiment = next(row for row in state["experiments"] if row["id"] == experiment_id)
        experiment["readiness"] = "awaiting_specification_or_evidence"
        ora.save(state)
        before = executor.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "not awaiting native evidence"):
            executor.issue(
                ora_store=ora,
                recorder=recorder,
                experiment_id=experiment_id,
            )
        self.assertEqual(executor.path.read_bytes(), before)

    def test_issue_requires_recorder_world_alignment(self):
        recorder, ora, executor, experiment_id, world, attempts = self.prepared()
        observation = observe_world(world)
        command = choose_command(observation, attempts)
        advanced, _ = transition(world, command, cycle=observation["cycle"] + 1)
        _unsafe_replace_world_for_adversarial_test(executor.path, advanced)
        before = executor.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "not aligned"):
            executor.issue(
                ora_store=ora,
                recorder=recorder,
                experiment_id=experiment_id,
            )
        self.assertEqual(executor.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
