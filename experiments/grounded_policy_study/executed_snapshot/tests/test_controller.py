import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from ora_study.choreography import Choreography
from ora_study.controller import run_scientific, run_stub
from ora_study.ledger import Ledger, IntegrityError, CapacityError
from ora_study.protocol import LIMITS, canonical, registry, transition_slots
from ora_study.resources import BudgetedFiles, Window, environment_evidence

RESULTS = Path(__file__).resolve().parents[2] / "policy-study-results"
RESULTS.mkdir(exist_ok=True)

class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=RESULTS, prefix="unit-")
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()

class LedgerTests(TemporaryCase):
    def make(self):
        item = Ledger(self.root/"ledger.jsonl", create=True)
        self.addCleanup(item.close)
        return item
    def test_registry_is_complete_before_work(self):
        ledger = self.make()
        self.assertEqual(len(registry()["arm_case_ids"]), 64)
        self.assertEqual(len(set(registry()["decision_ids"])), 128)
        self.assertEqual(ledger.records[0]["kind"], "registered")
        self.assertEqual(ledger.counters()["actual_invocations"], 0)
    def test_null_costs_decision_without_invocation(self):
        ledger = self.make()
        for decision in registry()["decision_ids"]:
            ledger.decision_start(decision)
            ledger.decision_commit(decision, receipt_hash="a"*64, is_null=True)
        self.assertEqual(ledger.counters()["decisions_durable_verified"], 128)
        self.assertEqual(ledger.counters()["null_decisions_verified"], 128)
        self.assertEqual(ledger.counters()["actual_invocations"], 0)
        with self.assertRaises(IntegrityError):
            ledger.decision_start(registry()["decision_ids"][0])
    def test_charge_precedes_start_and_bounds_unknown_crash(self):
        ledger = self.make()
        with self.assertRaises(IntegrityError):
            ledger.advance("unissued", "started")
        ticket = ledger.charge("owned", transition_slots()["owned"][0])
        self.assertIsNone(ledger.counters()["actual_invocations"])
        self.assertEqual(ledger.counters()["actual_invocations_upper_bound"], 1)
        ledger.advance(ticket, "started")
        self.assertIsNone(ledger.counters()["actual_invocations"])
        ledger.advance(ticket, "computed", result_hash="b"*64)
        self.assertEqual(ledger.counters()["actual_invocations"], 1)
    def test_lost_response_reconciles_without_replay(self):
        ledger = self.make()
        slot = transition_slots()["owned"][0]
        ticket = ledger.charge("owned", slot)
        ledger.advance(ticket, "started")
        ledger.reconcile_saved(ticket, result_hash="b"*64, authority_hash="c"*64)
        count = len(ledger.records)
        ledger.reconcile_saved(ticket, result_hash="b"*64, authority_hash="c"*64)
        self.assertEqual(len(ledger.records), count)
        self.assertEqual(ledger.counters()["durably_consumed_verified"], 1)
        with self.assertRaises(IntegrityError):
            ledger.charge("owned", slot)
        with self.assertRaises(IntegrityError):
            ledger.reconcile_saved(ticket, result_hash="d"*64, authority_hash="c"*64)
    def test_uncommitted_crash_does_not_reset_or_retry(self):
        ledger = self.make()
        slot = transition_slots()["neutral"][0]
        ledger.charge("neutral", slot)
        with self.assertRaises(IntegrityError):
            ledger.charge("neutral", slot)
        with self.assertRaises(FileExistsError):
            Ledger(self.root/"ledger.jsonl", create=True)
    def test_global_ceiling_charges_all_slots(self):
        ledger = self.make()
        for kind, slots in transition_slots().items():
            for slot in slots:
                ledger.charge(kind, slot)
        self.assertEqual(ledger.counters()["invocations_charged_verified"], 512)
        with self.assertRaises(CapacityError):
            ledger.charge("neutral", transition_slots()["neutral"][0])
    def test_corrupt_tail_preserves_verified_prefix_unknown_upper(self):
        ledger = self.make()
        ticket = ledger.charge("probe", transition_slots()["probe"][0])
        ledger.advance(ticket, "started")
        ledger.close()
        with open(self.root/"ledger.jsonl", "ab") as stream:
            stream.write(b'{"torn":')
        restored = Ledger(self.root/"ledger.jsonl")
        self.assertTrue(restored.broken)
        self.assertEqual(restored.counters()["invocations_charged_verified"], 1)
        self.assertIsNone(restored.counters()["actual_invocations_upper_bound"])
        with self.assertRaises(IntegrityError):
            restored.charge("probe", transition_slots()["probe"][1])
    def test_fsync_failure_marks_ledger_uncertain(self):
        ledger = self.make()
        with patch("ora_study.ledger.os.fsync", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                ledger.charge("owned", transition_slots()["owned"][0])
        self.assertTrue(ledger.broken)
        self.assertIsNone(ledger.counters()["actual_invocations_upper_bound"])

class ChoreographyTests(unittest.TestCase):
    def test_probe_gate_and_first_null_equality(self):
        flow = Choreography()
        anchor = registry()["anchors"][0]["anchor_id"]
        with self.assertRaises(IntegrityError):
            flow.note(anchor, "probe", action="north")
        flow.note(anchor,"pair_prepared",semantic_hash="e"*64)
        for arm in ("R", "W"):
            flow.note(anchor, "created", arm=arm)
            flow.note(anchor, "first_t1", arm=arm, semantic_hash="a"*64, is_null=True)
        for arm in ("R", "W"):
            flow.note(anchor, "first_t3", arm=arm, semantic_hash="b"*64)
        flow.note(anchor, "second_t1", arm="R", semantic_hash="c"*64)
        with self.assertRaises(IntegrityError):
            flow.note(anchor, "probe", action="north")
        with self.assertRaises(IntegrityError):
            flow.note(anchor, "second_t1", arm="W", semantic_hash="d"*64)
        flow.note(anchor, "second_t1", arm="W", semantic_hash="c"*64)
        flow.note(anchor, "probe", action="north")
        with self.assertRaises(IntegrityError):
            flow.note(anchor, "probe", action="north")
        with self.assertRaises(IntegrityError):
            flow.permit_report()

class BudgetTests(TemporaryCase):
    def test_reserve_and_atomic_replacement_peak(self):
        files = BudgetedFiles(self.root, total=1000, reserve=100)
        files.write("payload", b"x"*600)
        with self.assertRaises(CapacityError):
            files.write("payload", b"y"*400)  # old + temporary + reserve >1000
        files.write("terminal", b"done", final=True)
        self.assertFalse(files.reserve_path.exists())
        with self.assertRaises(IntegrityError):
            files.write("new_science", b"forbidden")
    def test_symlink_output_refused(self):
        files = BudgetedFiles(self.root, total=1000, reserve=100)
        (self.root/"alias").symlink_to(self.root/"finalization.reserve")
        with self.assertRaises(IntegrityError):
            files.used()
    def test_preflight_never_promises_hard_limits(self):
        evidence = environment_evidence()
        self.assertFalse(evidence["scientific_execution_allowed"])
        self.assertFalse(evidence["resource_mechanisms"]["rlimit_cpu_is_aggregate"])
        self.assertFalse(Window().sample()["hard_enforcement"])

class SupervisorTests(TemporaryCase):
    def test_success_is_fixture_only(self):
        result = run_stub(self.root/"run")
        self.assertEqual(result["classification"], "fixture_complete")
        self.assertEqual(result["science_transition_invocations"], 0)
        self.assertEqual(result["known_counters"]["actual_invocations"], 1)
        self.assertEqual(result["known_counters"]["durably_consumed_verified"], 1)
        self.assertTrue((self.root/"run"/"terminal.json").exists())
    def test_started_vs_computed_vs_durable_failures(self):
        for mode, started, computed, durable in (("fail_before_start", 0, 0, 0), ("fail_after_start", 1, 0, 0),
                ("fail_after_compute", 1, 1, 0), ("lost_response", 1, 1, 1)):
            with self.subTest(mode=mode):
                result = run_stub(self.root/mode, mode=mode)
                self.assertEqual(result["classification"], "invalid" if computed == 0 else "incomplete")
                counts = result["known_counters"]
                self.assertEqual(counts["invocations_started_verified"], started)
                self.assertEqual(counts["invocations_computed_verified"], computed)
                self.assertEqual(counts["durably_consumed_verified"], durable)
                self.assertEqual(counts["invocations_charged_verified"], 1)
    def test_all_startup_and_finalization_failures_structured(self):
        for phase in ("source_validation", "locking", "restart", "worker_startup", "report", "seal", "cleanup"):
            with self.subTest(phase=phase):
                result = run_stub(self.root/phase, inject_phase=phase)
                self.assertIn(result["classification"], ("invalid", "incomplete"))
                self.assertEqual(result["phase"], phase)
                self.assertEqual(result["science_transition_invocations"], 0)
                self.assertEqual(result["known_counters"]["scheduled_arm_cases"], 64)
                self.assertTrue((self.root/phase/"terminal.json").exists())
    def test_wall_interruption_kills_group_and_keeps_counts(self):
        result = run_stub(self.root/"hang", mode="hang", wall_ns=100_000_000)
        self.assertEqual(result["classification"], "invalid")
        self.assertLess(result["resources"]["wall_ns"], 2_000_000_000)
        self.assertEqual(result["known_counters"]["invocations_charged_verified"], 1)
        self.assertIsNone(result["known_counters"]["actual_invocations"])
    def test_untrusted_or_overlarge_child_output_is_bounded(self):
        for mode, expected in (("bad_json", "invalid"), ("stderr_flood", "invalid")):
            with self.subTest(mode=mode):
                result = run_stub(self.root/mode, mode=mode)
                self.assertEqual(result["classification"], expected)
    def test_existing_directory_never_reused(self):
        result = run_stub(self.root)
        self.assertEqual(result["classification"], "incomplete")
        self.assertFalse((self.root/"ledger.jsonl").exists())
    def test_scientific_path_refuses_before_output_or_import(self):
        target = self.root/"science"
        before = set(sys.modules)
        with self.assertRaises(IntegrityError):
            run_scientific(target)
        self.assertFalse(target.exists())
        self.assertFalse(any(name.startswith(("grounded_policy_v2", "agenttest", "open_object_world_challenge")) for name in set(sys.modules)-before))

if __name__ == "__main__":
    unittest.main()
