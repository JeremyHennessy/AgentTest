"""Copied recovery integration for lower-risk paired state/event writers.

Domain proposal/review/diagnostic/intervention functions are stubbed so these tests
measure persistence plumbing only. Existing suites remain authoritative for domain
semantics. No live state, Core.cycle, interaction, provider or world path is used.
"""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import agenttest.cli as cli
from agenttest.persistence_recovery import RecoveryStore, digest
from agenttest.state import initial_state

CLOCK = "2026-10-06T00:00:00+00:00"
ROOT = Path(__file__).resolve().parents[1]
PREFIX_EVENT = {"event": "synthetic_prefix", "cycle": 40}


class StopAfterSnapshot(RuntimeError):
    pass


def load_reconcile():
    spec = importlib.util.spec_from_file_location(
        "recovery_reconcile_verified_change",
        ROOT / "scripts" / "reconcile_verified_change.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compact(value):
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode()


def prefix_bytes():
    return compact(PREFIX_EVENT)


def cached_append(state, key, item, identity):
    rows = state.setdefault(key, [])
    found = next((row for row in rows if row.get("id") == identity), None)
    if found is not None:
        return found, False
    rows.append(deepcopy(item))
    return rows[-1], True


class PairedWriterRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = initial_state()
        self.state["cycles"] = 41
        self.state_raw = compact(self.state)
        self.journal_raw = prefix_bytes()

    def create_recovery(self, name):
        return RecoveryStore.create(
            self.root / name,
            self.state_raw,
            self.journal_raw,
            copied_only=True,
        )

    def default_paths(self, name):
        folder = self.root / name
        folder.mkdir()
        state = folder / "organism.json"
        journal = folder / "journal.jsonl"
        state.write_bytes(self.state_raw)
        journal.write_bytes(self.journal_raw)
        return folder, state, journal

    def run_cli(self, command, state, output, *, recovery=None):
        argv = ["agenttest", "--state", str(state)]
        if recovery is not None:
            argv += ["--copy-recovery-root", str(recovery.root)]
        argv += [command, "--output", str(output)]

        proposal = {"id": "M_COPY", "target_dimension": "agency"}
        review = {
            "id": "V_COPY",
            "proposal_id": "M_COPY",
            "verdict": "supported_problem",
            "patch_authority": "candidate_allowed",
        }
        diagnostic = {
            "id": "D_COPY",
            "proposal_id": "M_COPY",
            "kind": "self_model_grounding",
            "outcome": "grounded",
        }
        patches = {
            "propose-change": patch.object(
                cli,
                "propose_self_change",
                side_effect=lambda state: cached_append(
                    state, "change_proposals", proposal, proposal["id"]
                ),
            ),
            "review-change": patch.object(
                cli,
                "review_change_proposal",
                side_effect=lambda state: cached_append(
                    state, "proposal_reviews", review, review["id"]
                ),
            ),
            "diagnose-change": patch.object(
                cli,
                "run_proposal_diagnostic",
                side_effect=lambda state: cached_append(
                    state, "proposal_diagnostics", diagnostic, diagnostic["id"]
                ),
            ),
        }
        stdout = io.StringIO()
        with (
            patch.object(sys, "argv", argv),
            patch("agenttest.state.utc_now", return_value=CLOCK),
            patch.object(cli, "utc_now", return_value=CLOCK),
            patches[command],
            redirect_stdout(stdout),
        ):
            cli.main()
        return stdout.getvalue()

    def cli_operation_id(self, command):
        return {
            "propose-change": "change-proposal-M_COPY",
            "review-change": "change-review-V_COPY",
            "diagnose-change": "change-diagnostic-D_COPY",
        }[command]

    def interrupt_to_reference(self, store, target_state, target_journal, operation_id):
        event = target_journal[len(self.journal_raw):]
        stopped = {"done": False}

        def checkpoint(label):
            if label == "snapshot:replaced" and not stopped["done"]:
                stopped["done"] = True
                raise StopAfterSnapshot(label)

        interrupter = RecoveryStore(
            store.root, copied_only=True, checkpoint=checkpoint
        )
        with self.assertRaises(StopAfterSnapshot):
            interrupter.commit(
                operation_id,
                digest(self.state_raw),
                digest(self.journal_raw),
                target_state,
                event,
            )
        self.assertTrue(store.pending.exists())
        self.assertEqual(store.journal.read_bytes(), self.journal_raw)

    def test_cli_opt_in_matches_default_bytes_for_each_paired_command(self):
        for command in ("propose-change", "review-change", "diagnose-change"):
            with self.subTest(command=command):
                _, state, journal = self.default_paths("default-" + command)
                default_output = state.parent / "result.json"
                default_stdout = self.run_cli(
                    command, state, default_output
                )

                store = self.create_recovery("recovery-" + command)
                recovery_output = store.root / "result.json"
                recovery_stdout = self.run_cli(
                    command, store.state, recovery_output, recovery=store
                )

                self.assertEqual(store.state.read_bytes(), state.read_bytes())
                self.assertEqual(store.journal.read_bytes(), journal.read_bytes())
                self.assertEqual(recovery_output.read_bytes(), default_output.read_bytes())
                self.assertEqual(recovery_stdout, default_stdout)
                self.assertTrue(json.loads(recovery_output.read_bytes())["created"])

    def test_cli_retry_recovers_before_cached_domain_result(self):
        for command in ("propose-change", "review-change", "diagnose-change"):
            with self.subTest(command=command):
                reference = self.create_recovery("ref-" + command)
                self.run_cli(
                    command,
                    reference.state,
                    reference.root / "result.json",
                    recovery=reference,
                )
                target_state = reference.state.read_bytes()
                target_journal = reference.journal.read_bytes()

                store = self.create_recovery("interrupted-" + command)
                self.interrupt_to_reference(
                    store,
                    target_state,
                    target_journal,
                    self.cli_operation_id(command),
                )
                output = store.root / "result.json"
                self.run_cli(command, store.state, output, recovery=store)
                self.assertEqual(store.state.read_bytes(), target_state)
                self.assertEqual(store.journal.read_bytes(), target_journal)
                self.assertFalse(json.loads(output.read_bytes())["created"])
                settled = store.journal.read_bytes()
                self.run_cli(command, store.state, output, recovery=store)
                self.assertEqual(store.journal.read_bytes(), settled)

    def test_cli_next_paired_command_settles_previous_pending_transaction(self):
        reference = self.create_recovery("cli-cross-reference")
        self.run_cli(
            "propose-change",
            reference.state,
            reference.root / "proposal.json",
            recovery=reference,
        )
        self.run_cli(
            "review-change",
            reference.state,
            reference.root / "review.json",
            recovery=reference,
        )
        expected_state = reference.state.read_bytes()
        expected_journal = reference.journal.read_bytes()

        proposal_reference = self.create_recovery("proposal-reference")
        self.run_cli(
            "propose-change",
            proposal_reference.state,
            proposal_reference.root / "proposal.json",
            recovery=proposal_reference,
        )
        store = self.create_recovery("cli-cross-interrupted")
        self.interrupt_to_reference(
            store,
            proposal_reference.state.read_bytes(),
            proposal_reference.journal.read_bytes(),
            "change-proposal-M_COPY",
        )

        self.run_cli(
            "review-change",
            store.state,
            store.root / "review.json",
            recovery=store,
        )
        self.assertEqual(store.state.read_bytes(), expected_state)
        self.assertEqual(store.journal.read_bytes(), expected_journal)

    def reconcile_args(self, state, output, recovery=None):
        argv = [
            "reconcile_verified_change.py",
            "--state", str(state),
            "--commit-sha", "a" * 40,
            "--changed-file", "src/agenttest/core.py",
            "--verify-run-id", "123",
            "--pr-number", "999",
            "--attribution-text", "synthetic copied recovery fixture",
            "--output", str(output),
        ]
        if recovery is not None:
            argv += ["--copy-recovery-root", str(recovery.root)]
        return argv

    def reconcile_stub(self, state, **kwargs):
        receipt = {
            "id": "A_COPY",
            "proposal_id": "M_COPY",
            "commit_sha": "a" * 40,
            "verification": {"run_id": 123},
            "verification_scope": "applied_and_preserved",
            "improvement_claim": "not_implied",
        }
        return cached_append(state, "accepted_changes", receipt, receipt["id"])

    def run_reconcile(self, module, state, output, recovery=None):
        stdout = io.StringIO()
        with (
            patch.object(
                sys, "argv", self.reconcile_args(state, output, recovery)
            ),
            patch("agenttest.state.utc_now", return_value=CLOCK),
            patch.object(module, "utc_now", return_value=CLOCK),
            patch.object(
                module,
                "record_verified_intervention",
                side_effect=self.reconcile_stub,
            ),
            redirect_stdout(stdout),
        ):
            module.main()
        return stdout.getvalue()

    def test_reconciliation_opt_in_matches_default_and_recovers_missing_event(self):
        module = load_reconcile()
        _, state, journal = self.default_paths("reconcile-default")
        default_output = state.parent / "result.json"
        default_stdout = self.run_reconcile(
            module, state, default_output
        )

        reference = self.create_recovery("reconcile-reference")
        recovery_output = reference.root / "result.json"
        recovery_stdout = self.run_reconcile(
            module, reference.state, recovery_output, recovery=reference
        )
        self.assertEqual(reference.state.read_bytes(), state.read_bytes())
        self.assertEqual(reference.journal.read_bytes(), journal.read_bytes())
        self.assertEqual(recovery_output.read_bytes(), default_output.read_bytes())
        self.assertEqual(recovery_stdout, default_stdout)

        target_state = reference.state.read_bytes()
        target_journal = reference.journal.read_bytes()
        store = self.create_recovery("reconcile-interrupted")
        self.interrupt_to_reference(
            store,
            target_state,
            target_journal,
            "verified-intervention-A_COPY",
        )
        output = store.root / "result.json"
        self.run_reconcile(module, store.state, output, recovery=store)
        self.assertEqual(store.state.read_bytes(), target_state)
        self.assertEqual(store.journal.read_bytes(), target_journal)
        self.assertFalse(json.loads(output.read_bytes())["created"])

    def test_copy_recovery_flag_rejects_unreviewed_cli_commands(self):
        store = self.create_recovery("unsupported")
        before = store.state.read_bytes(), store.journal.read_bytes()
        with (
            patch.object(
                sys,
                "argv",
                [
                    "agenttest",
                    "--state", str(store.state),
                    "--copy-recovery-root", str(store.root),
                    "status",
                ],
            ),
            self.assertRaises(SystemExit),
        ):
            cli.main()
        self.assertEqual(
            (store.state.read_bytes(), store.journal.read_bytes()), before
        )


if __name__ == "__main__":
    unittest.main()
