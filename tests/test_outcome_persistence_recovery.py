"""Copied recovery contract for AgentCore.record_outcome only.

The central cycle, interaction flow, native state-only APIs and live workflows are
not enabled here. Tests use temporary stores and a fixed clock.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agenttest.core import AgentCore
from agenttest.persistence_recovery import RecoveryStore, digest
from agenttest.state import StateStore, initial_state

CLOCK = "2026-10-06T00:00:00+00:00"


def compact(value):
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode()


class StopAfterSnapshot(RuntimeError):
    pass


class OutcomeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        state = initial_state()
        state["cycles"] = 7
        state["experiments"].append(
            {
                "id": "X_COPY",
                "status": "proposed",
                "question_id": None,
                "method": "synthetic copied outcome fixture",
                "evidence_refs": [],
            }
        )
        self.state_raw = compact(state)
        self.journal_raw = compact({"event": "synthetic_prefix", "cycle": 6})

    def default_store(self, name):
        folder = self.root / name
        folder.mkdir()
        path = folder / "organism.json"
        path.write_bytes(self.state_raw)
        (folder / "journal.jsonl").write_bytes(self.journal_raw)
        return StateStore(path)

    def recovery_store(self, name):
        recovery = RecoveryStore.create(
            self.root / name,
            self.state_raw,
            self.journal_raw,
            copied_only=True,
        )
        return recovery, StateStore(recovery.state)

    def call(self, core, outcome="falsified", strength=0.75, recovery=None):
        kwargs = {}
        if recovery is not None:
            kwargs["copy_recovery_root"] = recovery.root
        with (
            patch("agenttest.core.utc_now", return_value=CLOCK),
            patch("agenttest.state.utc_now", return_value=CLOCK),
        ):
            return core.record_outcome(
                "X_COPY", outcome, strength, **kwargs
            )

    def test_opt_in_success_matches_default_state_journal_and_reflection(self):
        default = self.default_store("default")
        expected_reflection = self.call(AgentCore(default))
        expected_state = default.path.read_bytes()
        expected_journal = default.journal_path.read_bytes()

        recovery, store = self.recovery_store("recovery")
        actual_reflection = self.call(AgentCore(store), recovery=recovery)

        self.assertEqual(actual_reflection, expected_reflection)
        self.assertEqual(store.path.read_bytes(), expected_state)
        self.assertEqual(store.journal_path.read_bytes(), expected_journal)
        self.assertFalse(recovery.pending.exists())

    def test_retry_after_interrupted_state_commit_recovers_and_returns_same_reflection(self):
        reference_recovery, reference_store = self.recovery_store("reference")
        expected_reflection = self.call(
            AgentCore(reference_store), recovery=reference_recovery
        )
        target_state = reference_store.path.read_bytes()
        target_journal = reference_store.journal_path.read_bytes()
        exact_event = target_journal[len(self.journal_raw):]

        recovery, store = self.recovery_store("interrupted")
        stopped = {"done": False}

        def checkpoint(label):
            if label == "snapshot:replaced" and not stopped["done"]:
                stopped["done"] = True
                raise StopAfterSnapshot(label)

        interrupter = RecoveryStore(
            recovery.root, copied_only=True, checkpoint=checkpoint
        )
        with self.assertRaises(StopAfterSnapshot):
            interrupter.commit(
                "experiment-outcome-X_COPY",
                digest(self.state_raw),
                digest(self.journal_raw),
                target_state,
                exact_event,
            )
        self.assertTrue(recovery.pending.exists())
        self.assertEqual(store.journal_path.read_bytes(), self.journal_raw)

        actual = self.call(AgentCore(store), recovery=recovery)
        self.assertEqual(actual, expected_reflection)
        self.assertEqual(store.path.read_bytes(), target_state)
        self.assertEqual(store.journal_path.read_bytes(), target_journal)

        again = self.call(AgentCore(store), recovery=recovery)
        self.assertEqual(again, expected_reflection)
        self.assertEqual(store.journal_path.read_bytes(), target_journal)

    def test_conflicting_retry_after_recovery_fails_without_mutation(self):
        recovery, store = self.recovery_store("conflict")
        self.call(AgentCore(store), recovery=recovery)
        before = store.path.read_bytes(), store.journal_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "conflicts with retry"):
            self.call(
                AgentCore(store),
                outcome="supported",
                strength=0.75,
                recovery=recovery,
            )
        self.assertEqual((store.path.read_bytes(), store.journal_path.read_bytes()), before)

        with self.assertRaisesRegex(ValueError, "conflicts with retry"):
            self.call(
                AgentCore(store),
                outcome="falsified",
                strength=0.5,
                recovery=recovery,
            )
        self.assertEqual((store.path.read_bytes(), store.journal_path.read_bytes()), before)

    def test_default_completed_outcome_still_raises(self):
        store = self.default_store("default-completed")
        self.call(AgentCore(store))
        before = store.path.read_bytes(), store.journal_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "already completed"):
            self.call(AgentCore(store))
        self.assertEqual((store.path.read_bytes(), store.journal_path.read_bytes()), before)

    def test_copy_root_must_own_core_store(self):
        recovery, _ = self.recovery_store("owned")
        foreign = self.default_store("foreign")
        before = recovery.state.read_bytes(), recovery.journal.read_bytes()
        with self.assertRaisesRegex(ValueError, "does not own"):
            self.call(AgentCore(foreign), recovery=recovery)
        self.assertEqual((recovery.state.read_bytes(), recovery.journal.read_bytes()), before)


if __name__ == "__main__":
    unittest.main()
