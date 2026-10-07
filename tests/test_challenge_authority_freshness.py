"""Copied-state authority negatives; no natural Ora run or milestone credit."""
from copy import deepcopy
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch

import test_challenge_multi_action_authority as fixtures
import challenge_action_authority as authority
import challenge_shadow_recorder as recorder_module
from agenttest.state import StateStore, initial_state


class ChallengeAuthorityFreshnessTests(unittest.TestCase):
    setUp = fixtures.ChallengeMultiActionAuthorityTests.setUp
    _stage = fixtures.ChallengeMultiActionAuthorityTests._stage

    @classmethod
    def setUpClass(cls):
        # The deterministic public prefix is shared as immutable fixture bytes;
        # each test gets independent copied stores and a new capability ledger.
        with tempfile.TemporaryDirectory() as directory:
            builder = fixtures.ChallengeMultiActionAuthorityTests()
            builder.root = Path(directory)
            recorder, world = builder._prefix()
            cls.prefix_bytes = recorder.store.path.read_bytes()
            cls.prefix_world = deepcopy(world)

    def _prefix(self):
        store = StateStore(self.root / "recorder.json")
        store.path.write_bytes(self.prefix_bytes)
        return recorder_module.ChallengeShadowRecorder(store, enabled=True), deepcopy(self.prefix_world)

    def _issued(self):
        recorder, world = self._prefix()
        ora = StateStore(self.root / "ora.json")
        ora.save(initial_state())
        experiment_id = self._stage(ora, recorder)
        executor = authority.ChallengeActionExecutor.create(
            self.root / "executor.json", world=world, max_actions=2,
        )
        token = executor.issue(
            ora_store=ora, recorder=recorder, experiment_id=experiment_id,
        )["token"]
        return ora, recorder, executor, token

    def _reject(self, ora, recorder, executor, token):
        before = executor.path.read_bytes()
        # Rejection must remain fail-closed on both fresh executor instances.
        for _ in range(2):
            with self.assertRaises((ValueError, RuntimeError)):
                authority.ChallengeActionExecutor(executor.path).execute(
                    token, ora_store=ora, recorder=recorder,
                )
            self.assertEqual(before, executor.path.read_bytes())

    def test_ora_and_inquiry_changes_reject_without_transition(self):
        ora, recorder, executor, token = self._issued()
        baseline = ora.path.read_bytes()
        mutations = [
            lambda s: s.update(cycles=s["cycles"] + 1),
            lambda s: s.update(research_marker="changed copied state"),
            lambda s: s["experiments"][0].update(status="completed"),
            lambda s: s["experiments"][0].update(readiness="resolved"),
            lambda s: s["experiments"][0].update(question_id="changed"),
            lambda s: s["experiments"][0]["native_inquiry"].update(candidate_id="changed"),
            lambda s: s["experiments"][0]["native_inquiry"]["relation"].update(feature="changed"),
            lambda s: s.update(experiments=[]),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                ora.path.write_bytes(baseline)
                state = ora.load()
                mutate(state)
                ora.save(state)
                self._reject(ora, recorder, executor, token)

    def test_recorder_changes_reject_even_with_valid_checkpoint_checksum(self):
        ora, recorder, executor, token = self._issued()
        baseline = recorder.store.path.read_bytes()
        for field, value in [
            ("chain", "changed"), ("source_id", "changed"),
            ("source_descriptor_hash", "changed"), ("by_action", {}),
        ]:
            with self.subTest(field=field):
                recorder.store.path.write_bytes(baseline)
                state = recorder.store.load()
                cursor = state[recorder_module.STATE_KEY]
                cursor[field] = value
                state[recorder_module.STATE_KEY] = recorder_module._seal(cursor)
                recorder.store.save(state)
                self._reject(ora, recorder, executor, token)

    def test_changed_selector_and_command_reject(self):
        ora, recorder, executor, token = self._issued()
        select = authority.select_epistemic_command

        def changed_selection(*args, **kwargs):
            selection = deepcopy(select(*args, **kwargs))
            selection["review_test_marker"] = "changed selector output"
            return selection

        with patch.object(authority, "select_epistemic_command", changed_selection):
            self._reject(ora, recorder, executor, token)
        changed_token = deepcopy(token)
        changed_token["command"] = {"action": "inspect", "target": "changed"}
        self._reject(ora, recorder, executor, changed_token)

    def test_world_and_budget_changes_reject(self):
        ora, recorder, executor, token = self._issued()
        baseline = executor.path.read_bytes()
        for mutate in [
            lambda s: s.update(max_actions=3),
            lambda s: s["world"].update(research_marker="changed world"),
        ]:
            executor.path.write_bytes(baseline)
            state = executor.load()
            mutate(state)
            authority._save_atomic(executor.path, state)
            self._reject(ora, recorder, executor, token)

    def test_source_content_change_rejects(self):
        source_root = self.root / "research-source"
        source_root.mkdir()
        for source in Path(authority.__file__).parent.glob("*.py"):
            shutil.copy2(source, source_root / source.name)
        with patch.object(authority, "__file__", str(source_root / "challenge_action_authority.py")):
            ora, recorder, executor, token = self._issued()
            selector = source_root / "challenge_shadow_epistemic_selector.py"
            selector.write_bytes(selector.read_bytes() + b"\n# changed after issuance\n")
            self._reject(ora, recorder, executor, token)

    def test_recorder_advance_rejects(self):
        ora, recorder, executor, token = self._issued()
        from open_object_world_challenge import observe_world, transition
        world = executor.load()["world"]
        next_world, receipt = transition(
            world, token["command"], cycle=observe_world(world)["cycle"] + 1,
        )
        recorder.ingest(observe_world(next_world), receipt)
        self._reject(ora, recorder, executor, token)

    def test_missing_copied_state_rejects_after_restart(self):
        ora, recorder, executor, token = self._issued()
        for path in [ora.path, recorder.store.path]:
            baseline = path.read_bytes()
            path.unlink()
            self._reject(ora, recorder, executor, token)
            path.write_bytes(baseline)

    def test_unchanged_action_succeeds_once_after_restart(self):
        ora, recorder, executor, token = self._issued()
        ora_before = ora.path.read_bytes()
        recorder_before = recorder.store.path.read_bytes()
        result = authority.ChallengeActionExecutor(executor.path).execute(
            token, ora_store=StateStore(ora.path),
            recorder=recorder_module.ChallengeShadowRecorder(
                StateStore(recorder.store.path), enabled=True,
            ),
        )
        self.assertEqual(result["actions_consumed"], 1)
        self.assertEqual(result["remaining_budget"], 1)
        self.assertEqual(ora_before, ora.path.read_bytes())
        self.assertEqual(recorder_before, recorder.store.path.read_bytes())
        self._reject(ora, recorder, executor, token)

    def test_legacy_executor_fails_closed(self):
        ora, recorder, executor, token = self._issued()
        state = executor.load()
        state["version"] = "challenge-action-authority-v1"
        authority._save_atomic(executor.path, state)
        self._reject(ora, recorder, executor, token)
