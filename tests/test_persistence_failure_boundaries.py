"""Characterize existing persistence boundaries; these passing tests do NOT prove recovery.

Only synthetic temporary stores are used. No Core.cycle, provider, network, live
state, or archived scientific trajectory is executed. Update these expectations
with independently specified recovery tests when a recovery implementation exists.
"""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from agenttest.state import StateStore, initial_state

CLOCK = "2026-10-06T00:00:00+00:00"
ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ("experiment_design_eval", "blocked_attention_eval")


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        "persistence_boundary_" + name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def failing_append(path, partial=False):
    """Inject an actual temporary-file prefix write, or fail before opening it."""
    original = Path.open

    class PartialAppend:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def write(self, text):
            self.handle.write(text[:max(1, len(text) // 2)])
            self.handle.flush()
            raise OSError("injected partial journal append")

    def open_file(target, mode="r", *args, **kwargs):
        if target == path and mode == "a":
            if not partial:
                raise OSError("injected journal open failure")
            return PartialAppend(original(target, mode, *args, **kwargs))
        return original(target, mode, *args, **kwargs)

    with patch.object(Path, "open", open_file):
        yield


class PersistenceFailureBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.store = StateStore(self.folder / "organism.json")
        self.state = initial_state()
        self.state["cycles"] = 7
        self.state["boundary_fixture"] = {
            "text": "synthetic history: caf\u00e9\nline two",
            "values": [None, False, 0, 1.25, "unmodified"],
        }
        with patch("agenttest.state.utc_now", return_value=CLOCK):
            self.store.save(deepcopy(self.state))
        self.state = json.loads(self.store.path.read_bytes())
        self.store.append_journal({"event": "synthetic_prefix", "cycle": 6})
        self.snapshot = self.store.path.read_bytes()
        self.prefix = self.store.journal_path.read_bytes()

    def test_replace_failure_preserves_committed_state_and_journal(self):
        changed = deepcopy(self.state)
        changed["cycles"] = 8
        with patch.object(Path, "replace", side_effect=OSError("injected replace failure")):
            with self.assertRaises(OSError):
                self.store.save(changed)
        self.assertEqual(self.store.path.read_bytes(), self.snapshot)
        self.assertEqual(self.store.journal_path.read_bytes(), self.prefix)
        self.assertEqual(StateStore(self.store.path).load()["cycles"], 7)
        # An orphan temp file is not automatically promoted during load.
        self.assertTrue(self.store.path.with_suffix(".json.tmp").exists())

    def test_truncated_temporary_snapshot_is_not_promoted_on_restart(self):
        self.store.path.with_suffix(".json.tmp").write_bytes(b'{"cycles":8')
        self.assertEqual(StateStore(self.store.path).load(), self.state)
        self.assertEqual(self.store.path.read_bytes(), self.snapshot)
        self.assertEqual(self.store.journal_path.read_bytes(), self.prefix)

    def test_saved_state_survives_append_failure_but_restart_does_not_repair_gap(self):
        changed = deepcopy(self.state)
        changed["cycles"] = 8
        self.store.save(changed)
        committed = self.store.path.read_bytes()
        with failing_append(self.store.journal_path):
            with self.assertRaises(OSError):
                self.store.append_journal({"event": "synthetic_commit", "cycle": 8})
        for _ in range(2):
            self.assertEqual(StateStore(self.store.path).load()["cycles"], 8)
            self.assertEqual(self.store.path.read_bytes(), committed)
            self.assertEqual(self.store.journal_path.read_bytes(), self.prefix)
        # This explicitly demonstrates an unresolved consistency gap.

    def test_partial_append_preserves_prefix_but_next_append_does_not_repair_tail(self):
        with failing_append(self.store.journal_path, partial=True):
            with self.assertRaises(OSError):
                self.store.append_journal({"event": "synthetic_partial", "cycle": 8})
        partial = self.store.journal_path.read_bytes()
        self.assertTrue(partial.startswith(self.prefix))
        self.assertGreater(len(partial), len(self.prefix))
        self.assertFalse(partial.endswith(b"\n"))
        restarted = StateStore(self.store.path)
        restarted.append_journal({"event": "synthetic_later", "cycle": 9})
        damaged = self.store.journal_path.read_bytes()
        self.assertTrue(damaged.startswith(partial))
        with self.assertRaises(json.JSONDecodeError):
            json.loads(damaged[len(self.prefix):])
        self.assertEqual(self.store.path.read_bytes(), self.snapshot)

    def test_complete_record_without_newline_is_concatenated_not_recovered(self):
        self.store.journal_path.write_bytes(self.prefix[:-1])
        self.store.append_journal({"event": "synthetic_later", "cycle": 8})
        self.assertEqual(len(self.store.journal_path.read_bytes().splitlines()), 1)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(self.store.journal_path.read_bytes())
        self.assertEqual(self.store.path.read_bytes(), self.snapshot)

    def test_raw_append_is_not_idempotent(self):
        event = {"event": "synthetic_repeated", "cycle": 8, "id": "TEST-EVENT"}
        self.store.append_journal(event)
        StateStore(self.store.path).append_journal(event)
        events = [json.loads(line) for line in self.store.journal_path.read_bytes().splitlines()]
        self.assertEqual(events[-2:], [event, event])
        self.assertEqual(self.store.path.read_bytes(), self.snapshot)

    def test_invalid_committed_json_fails_without_repair_or_history_mutation(self):
        damaged = b'{"cycles":'
        self.store.path.write_bytes(damaged)
        with self.assertRaises(json.JSONDecodeError):
            StateStore(self.store.path).load()
        self.assertEqual(self.store.path.read_bytes(), damaged)
        self.assertEqual(self.store.journal_path.read_bytes(), self.prefix)

    def test_missing_snapshot_with_existing_journal_returns_initial_state(self):
        # Observe the current API behavior; never save this reset state.
        self.store.path.unlink()
        loaded = StateStore(self.store.path).load()
        self.assertEqual(loaded["cycles"], 0)
        self.assertFalse(self.store.path.exists())
        self.assertEqual(self.store.journal_path.read_bytes(), self.prefix)

    def run_diagnostic(self, module, store, output):
        argv = [module.__file__, "--state", str(store.path), "--output", str(output)]
        with patch.object(sys, "argv", argv), patch.object(module, "_now", return_value=CLOCK):
            with redirect_stdout(io.StringIO()):
                module.main()

    def diagnostic_store(self, name):
        folder = self.folder / name
        store = StateStore(folder / "organism.json")
        with patch("agenttest.state.utc_now", return_value=CLOCK):
            store.save(deepcopy(self.state))
        store.append_journal({"event": "synthetic_prefix", "cycle": 6})
        return store, folder / "diagnostic.json"

    def test_both_direct_writers_preserve_old_state_on_replace_failure(self):
        for name in DIAGNOSTICS:
            with self.subTest(writer=name):
                module = load_script(name)
                store, output = self.diagnostic_store(name)
                before = store.path.read_bytes(), store.journal_path.read_bytes()
                with patch.object(Path, "replace", side_effect=OSError("injected replace failure")):
                    with self.assertRaises(OSError):
                        self.run_diagnostic(module, store, output)
                self.assertEqual((store.path.read_bytes(), store.journal_path.read_bytes()), before)
                self.assertFalse(output.exists())
                self.run_diagnostic(module, store, output)
                self.assertTrue(json.loads(output.read_bytes())["created"])
                self.assertEqual(len(json.loads(store.path.read_bytes())["system_diagnostics"]), 1)

    def test_both_direct_writers_retry_cached_state_without_repairing_missing_event(self):
        for name in DIAGNOSTICS:
            with self.subTest(writer=name):
                module = load_script(name)
                store, output = self.diagnostic_store(name)
                prefix = store.journal_path.read_bytes()
                with failing_append(store.journal_path):
                    with self.assertRaises(OSError):
                        self.run_diagnostic(module, store, output)
                committed = store.path.read_bytes()
                self.assertEqual(len(json.loads(committed)["system_diagnostics"]), 1)
                self.assertFalse(output.exists())
                for _ in range(2):
                    self.run_diagnostic(module, store, output)
                    self.assertFalse(json.loads(output.read_bytes())["created"])
                    self.assertEqual(store.path.read_bytes(), committed)
                    self.assertEqual(store.journal_path.read_bytes(), prefix)

    def test_both_direct_writers_leave_partial_tail_on_cached_retry(self):
        for name in DIAGNOSTICS:
            with self.subTest(writer=name):
                module = load_script(name)
                store, output = self.diagnostic_store(name)
                prefix = store.journal_path.read_bytes()
                with failing_append(store.journal_path, partial=True):
                    with self.assertRaises(OSError):
                        self.run_diagnostic(module, store, output)
                damaged = store.journal_path.read_bytes()
                self.assertTrue(damaged.startswith(prefix))
                self.run_diagnostic(module, store, output)
                self.assertFalse(json.loads(output.read_bytes())["created"])
                self.assertEqual(store.journal_path.read_bytes(), damaged)
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(damaged[len(prefix):])

    def test_both_direct_writers_reexpand_compact_snapshot_without_semantic_loss(self):
        for name in DIAGNOSTICS:
            with self.subTest(writer=name):
                module = load_script(name)
                store, output = self.diagnostic_store(name)
                self.assertEqual(store.path.read_bytes().count(b"\n"), 1)
                self.run_diagnostic(module, store, output)
                saved = store.path.read_bytes()
                decoded = json.loads(saved)
                self.assertEqual(saved.decode(), json.dumps(decoded, indent=2, sort_keys=True) + "\n")
                compact = json.dumps(decoded, separators=(",", ":"), sort_keys=True) + "\n"
                self.assertGreater(len(saved), len(compact.encode()))
                for key, value in self.state.items():
                    if key not in {"system_diagnostics", "updated_at"}:
                        self.assertEqual(decoded[key], value)


if __name__ == "__main__":
    unittest.main()
