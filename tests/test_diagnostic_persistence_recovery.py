"""Integration gate for copied diagnostic writers using exact-event recovery.

No live state, workflow, Core.cycle, external observation, provider, or archived
scientific trajectory is used. The default CLI path remains independently tested
against exact legacy-format bytes. Recovery mode requires an explicit copied root.
"""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agenttest.persistence_recovery import RecoveryError, RecoveryStore
from agenttest.state import initial_state

CLOCK = "2026-10-06T00:00:00+00:00"
ROOT = Path(__file__).resolve().parents[1]
WRITERS = ("experiment_design_eval", "blocked_attention_eval")


class InjectedStop(RuntimeError):
    pass


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        "diagnostic_recovery_" + name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encode_compact(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def prefix_bytes():
    return (json.dumps({"event": "synthetic_prefix", "cycle": 40},
                       sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class DiagnosticRecoveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = initial_state()
        self.state["cycles"] = 41
        self.state["integration_fixture"] = {
            "text": "copied diagnostic recovery",
            "values": [None, False, 0, 1.25],
        }
        self.state_raw = encode_compact(self.state)
        self.journal_raw = prefix_bytes()

    def run_module(self, module, args, checkpoint=None):
        output = io.StringIO()
        with patch.object(module, "_now", return_value=CLOCK), redirect_stdout(output):
            module.run(args, recovery_checkpoint=checkpoint)
        return output.getvalue()

    def create_recovery(self, name):
        root = self.root / name
        return RecoveryStore.create(
            root, self.state_raw, self.journal_raw, copied_only=True
        )

    def default_paths(self, name):
        folder = self.root / name
        folder.mkdir()
        state = folder / "organism.json"
        journal = folder / "journal.jsonl"
        state.write_bytes(self.state_raw)
        journal.write_bytes(self.journal_raw)
        return folder, state, journal

    def recovery_args(self, store, output):
        return [
            "--state", str(store.state),
            "--output", str(output),
            "--copy-recovery-root", str(store.root),
        ]

    def test_opt_in_success_matches_default_state_journal_output_and_stdout(self):
        for name in WRITERS:
            with self.subTest(writer=name):
                module = load_script(name)
                _, state, journal = self.default_paths("default-" + name)
                default_output = state.parent / "diagnostic.json"
                default_stdout = self.run_module(
                    module,
                    ["--state", str(state), "--output", str(default_output)],
                )

                store = self.create_recovery("recovery-" + name)
                recovery_output = store.root / "diagnostic.json"
                recovery_stdout = self.run_module(
                    module, self.recovery_args(store, recovery_output)
                )

                self.assertEqual(store.state.read_bytes(), state.read_bytes())
                self.assertEqual(store.journal.read_bytes(), journal.read_bytes())
                self.assertEqual(recovery_output.read_bytes(), default_output.read_bytes())
                self.assertEqual(recovery_stdout, default_stdout)
                self.assertTrue(json.loads(recovery_output.read_bytes())["created"])
                self.assertFalse(store.pending.exists())
                self.assertFalse(store.payload.exists())

    def test_recovery_runs_before_cache_and_repairs_missing_event_exactly_once(self):
        for name in WRITERS:
            with self.subTest(writer=name):
                module = load_script(name)

                reference = self.create_recovery("reference-" + name)
                reference_output = reference.root / "diagnostic.json"
                self.run_module(module, self.recovery_args(reference, reference_output))
                expected_state = reference.state.read_bytes()
                expected_journal = reference.journal.read_bytes()

                store = self.create_recovery("interrupted-" + name)
                output = store.root / "diagnostic.json"
                stopped = {"done": False}

                def checkpoint(label):
                    if label == "snapshot:replaced" and not stopped["done"]:
                        stopped["done"] = True
                        raise InjectedStop(label)

                with self.assertRaises(InjectedStop):
                    self.run_module(
                        module, self.recovery_args(store, output), checkpoint=checkpoint
                    )
                self.assertTrue(store.pending.exists())
                self.assertFalse(output.exists())
                self.assertEqual(store.journal.read_bytes(), self.journal_raw)

                self.run_module(module, self.recovery_args(store, output))
                self.assertEqual(store.state.read_bytes(), expected_state)
                self.assertEqual(store.journal.read_bytes(), expected_journal)
                self.assertFalse(json.loads(output.read_bytes())["created"])
                settled = store.journal.read_bytes()

                self.run_module(module, self.recovery_args(store, output))
                self.assertEqual(store.journal.read_bytes(), settled)
                events = [json.loads(line) for line in settled.splitlines()]
                self.assertEqual(
                    sum(item.get("event") == "system_diagnostic" for item in events), 1
                )

    def test_other_diagnostic_recovers_pending_before_starting_new_work(self):
        experiment = load_script("experiment_design_eval")
        attention = load_script("blocked_attention_eval")

        reference = self.create_recovery("cross-reference")
        self.run_module(
            experiment,
            self.recovery_args(reference, reference.root / "experiment.json"),
        )
        self.run_module(
            attention,
            self.recovery_args(reference, reference.root / "attention.json"),
        )
        expected_state = reference.state.read_bytes()
        expected_journal = reference.journal.read_bytes()

        store = self.create_recovery("cross-interrupted")
        stopped = {"done": False}

        def checkpoint(label):
            if label == "snapshot:replaced" and not stopped["done"]:
                stopped["done"] = True
                raise InjectedStop(label)

        with self.assertRaises(InjectedStop):
            self.run_module(
                experiment,
                self.recovery_args(store, store.root / "experiment.json"),
                checkpoint=checkpoint,
            )
        self.assertTrue(store.pending.exists())

        self.run_module(
            attention,
            self.recovery_args(store, store.root / "attention.json"),
        )
        self.assertEqual(store.state.read_bytes(), expected_state)
        self.assertEqual(store.journal.read_bytes(), expected_journal)
        self.assertFalse(store.pending.exists())
        state = json.loads(store.state.read_bytes())
        self.assertEqual(len(state["system_diagnostics"]), 2)
        kinds = [item["kind"] for item in state["system_diagnostics"]]
        self.assertEqual(kinds, ["experiment_design", "attention_control"])

    def test_foreign_tail_rejects_before_cache_or_output(self):
        module = load_script("experiment_design_eval")
        store = self.create_recovery("foreign-tail")
        output = store.root / "diagnostic.json"
        stopped = {"done": False}

        def checkpoint(label):
            if label == "snapshot:replaced" and not stopped["done"]:
                stopped["done"] = True
                raise InjectedStop(label)

        with self.assertRaises(InjectedStop):
            self.run_module(
                module, self.recovery_args(store, output), checkpoint=checkpoint
            )
        with store.journal.open("ab") as handle:
            handle.write(b"foreign")
        before_state = store.state.read_bytes()
        before_journal = store.journal.read_bytes()
        with self.assertRaises(RecoveryError):
            self.run_module(module, self.recovery_args(store, output))
        self.assertEqual(store.state.read_bytes(), before_state)
        self.assertEqual(store.journal.read_bytes(), before_journal)
        self.assertFalse(output.exists())

    def test_copy_flag_rejects_state_outside_owned_root(self):
        module = load_script("experiment_design_eval")
        store = self.create_recovery("owned-root")
        _, foreign_state, _ = self.default_paths("foreign-state")
        before = store.state.read_bytes(), store.journal.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_module(
                module,
                [
                    "--state", str(foreign_state),
                    "--output", str(self.root / "outside.json"),
                    "--copy-recovery-root", str(store.root),
                ],
            )
        self.assertEqual((store.state.read_bytes(), store.journal.read_bytes()), before)
        self.assertFalse((self.root / "outside.json").exists())

    def test_default_path_creates_no_recovery_metadata(self):
        for name in WRITERS:
            with self.subTest(writer=name):
                module = load_script(name)
                folder, state, _ = self.default_paths("plain-" + name)
                self.run_module(
                    module,
                    ["--state", str(state), "--output", str(folder / "diagnostic.json")],
                )
                self.assertFalse((folder / "COPY-ONLY.json").exists())
                self.assertFalse((folder / "pending.json").exists())
                self.assertFalse((folder / "prepared-snapshot.json").exists())
                self.assertFalse(any(folder.glob("receipt-*.json")))


if __name__ == "__main__":
    unittest.main()
