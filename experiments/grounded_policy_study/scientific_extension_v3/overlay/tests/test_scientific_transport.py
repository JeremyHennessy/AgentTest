"""Authored metadata/scalar workers only: zero API setup or real world calls."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from ora_study.ledger import CapacityError, IntegrityError
from ora_study.protocol import canonical, digest, registry, worker_allowances, transition_slots, MOVEMENTS
from ora_study.scientific_profile import (ALLOCATION, PROFILE, SLOTS, CALL_CAPS, MIB,
    LEDGER_CAP, LEDGER_NAMES, LEDGER_SEGMENT_CAPS, SOURCE_BOUNDS)
from ora_study.scientific_transport import ScientificInventory, ScientificLedger, ScientificTransport
from ora_study import scientific_worker


def authored_mixed_discovery():
    """Stationary, hand-authored public JSON; no simulator or chooser is called."""
    def observation(cycle):
        return {"world_version": "open-object-world-challenge-v1", "observation_id": f"owc-{cycle:06d}",
            "cycle": cycle, "position": [0, 0], "inventory_ids": [], "visible_entities": []}
    frames = [{"observation": observation(0), "receipt": None}]
    rows = []
    actions = ("north", "inspect", "east", "interact", "south", "take", "west", "drop") * 4
    for cycle, action in enumerate(actions, 1):
        receipt = {"id": f"OWC-A{cycle:06d}", "cycle": cycle, "action": action,
            "target": None, "direction": None, "before": [0, 0], "after": [0, 0],
            "success": True, "blocked": action in MOVEMENTS, "observed_effects": [], "visible_entity_states": {}}
        before, after = frames[-1]["observation"], observation(cycle)
        frames.append({"observation": after, "receipt": receipt})
        if action in MOVEMENTS:
            rows.append({"event_id": receipt["id"], "before_context": {"position": [0, 0], "inventory_ids": [], "visible_ids": []},
                "action": action, "after_position": [0, 0],
                "refs": {"before": digest(before), "receipt": digest(receipt), "after": digest(after)}})
    return frames, rows


# This is a separate, explicitly authored protocol peer. Scalar dictionaries
# below are not observations, world trajectories, policy data, or API inputs.
STUB_WORKER = br'''
import json,sys,os,hashlib
def canon(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def digest(value): return hashlib.sha256(canon(value)).hexdigest()
def send(message):
    os.write(1,canon(message)+b"\n")
    answer=json.loads(sys.stdin.buffer.readline())
    assert answer.get("accepted") is True and answer["request_sha256"]==digest(message)
    return answer
packet=json.loads(sys.stdin.buffer.readline()); request=packet["request"]
assert not any(name.startswith(("grounded_policy_v2","agenttest","open_object_world_challenge")) for name in sys.modules)
if packet["configuration"].get("die"): os._exit(7)
phase=request["phase"]
if phase=="neutral":
    layout=request["layout"]
    send({"event":"neutral_initial","layout":layout,"world":{"authored_scalar":0},"frame":{"authored_scalar":0}})
    for index in range(1,65):
        reply=send({"event":"transition_permit","category":"neutral","slot":f"neutral.layout{layout}.t{index}","command":{"authored_scalar":index}})
        send({"event":"actual_call_entered","call_id":index,"category":"transition"})
        result={"world":{"authored_scalar":index},"receipt":{"authored_scalar":index}}
        send({"event":"actual_call_exited","call_id":index,"category":"transition","computed_result_sha256":digest(result)})
        send({"event":"neutral_transition_saved","layout":layout,"t":index,"ticket":reply["ticket"],"authored_scalar_result":result})
        if index==32:
            send({"event":"D_frozen","layout":layout,"frames":packet["configuration"]["authored_D_frames"],"projected_rows":packet["configuration"]["authored_D_rows"]})
        if index in (32,36,40,44,48,52,56,60):
            send({"event":"neutral_anchor_saved","layout":layout,"t":index,"world":{"authored_scalar":index},"frames":[{"authored_scalar":0}]*(index+1)})
elif phase=="probes":
    for index,action in enumerate(("north","east","south","west"),1):
        reply=send({"event":"transition_permit","category":"probe","slot":f"probe.{request['anchor_id']}.{action}","command":{"action":action},"source_world_sha256":digest(request["post_first_world"]),"forecast_commitment_sha256":digest(request["forecast_commitment"])})
        send({"event":"actual_call_entered","call_id":index,"category":"transition"})
        result={"world":{"authored_scalar":index},"receipt":{"authored_scalar":index}}
        send({"event":"actual_call_exited","call_id":index,"category":"transition","computed_result_sha256":digest(result)})
        send({"event":"probe_saved","anchor_id":request["anchor_id"],"ticket":reply["ticket"],"outcome":{"command":{"action":action}},"authored_scalar_result":result})
result={"authored_stub":True,"actual_world_calls":0,"actual_api_calls":0}
send({"event":"stage_complete","result":result,"result_sha256":digest(result)})
'''


class ScientificTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.files = ScientificInventory(Path(self.tmp.name) / "authored")
        self.ledger = ScientificLedger(self.files.root / "ledger.jsonl", authored_fixture=True)

    def tearDown(self):
        self.ledger.close()
        self.files.close()
        self.tmp.cleanup()

    def transport(self, *, handler=None, config=None, authored=True, worker=STUB_WORKER):
        frames, rows = authored_mixed_discovery()
        config = {"authored_D_frames": frames, "authored_D_rows": rows, **(config or {})}
        return ScientificTransport(self.files, self.ledger, worker, "/authored/zero_world_stub.py",
            config, time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 60 * 10**9,
            event_handler=handler, authored_fixture=authored)

    def test_profile_complete_inventory_and_disabled_entrypoints(self):
        self.assertEqual((len(PROFILE["case_ids"]), len(registry()["decision_ids"])), (64, 128))
        self.assertEqual(sum(ALLOCATION.values()), 192 * MIB)
        self.assertEqual(ALLOCATION["ledger_and_logs"], 18 * MIB)
        self.assertEqual(ALLOCATION["saved_exports"], 8 * MIB)
        self.assertEqual(sum(LEDGER_SEGMENT_CAPS), LEDGER_CAP)
        self.assertTrue(all(value <= 2 * MIB for value in LEDGER_SEGMENT_CAPS))
        self.assertEqual(len(self.files.capsules), 64)
        for case in PROFILE["case_ids"]:
            for key, bound in SOURCE_BOUNDS.items():
                self.assertEqual(self.files.records[f"sources/{case}/{key}.json"]["reserved_bytes"], bound)
        with patch("builtins.open", side_effect=AssertionError("No access before admission")), \
             patch.object(scientific_worker, "SCIENTIFIC_ADMISSION_REVIEWED", False):
            with self.assertRaises(RuntimeError):
                scientific_worker.main()
        with patch("ora_study.scientific_transport.SCIENTIFIC_ADMISSION_REVIEWED", False):
            with self.assertRaises(IntegrityError):
                self.transport(authored=False)._dispatch("neutral.layout1", {"phase": "neutral", "layout": 1})
            with self.assertRaises(IntegrityError):
                self.transport().scientific_stage("neutral.layout1", {"phase": "neutral", "layout": 1})
        self.assertEqual(self.ledger.counters()["scientific_transition_invocations"], 0)
        self.assertEqual(self.ledger.counters()["science_transition_invocations"], 0)
        self.assertNotIn("scientific_denominators", self.ledger.counters())
        self.assertNotIn("science_result", self.ledger.counters())
        self.assertNotIn("scientific_admission_reviewed", self.ledger.counters())
        self.assertIs(self.ledger.counters()["source_scientific_admission_reviewed"], False)

    def test_captured_bootstrap_and_numeric_guard_reuse_verified_source(self):
        root = Path(__file__).parents[1] / "ora_study"
        original = ast.parse((root / "native_fixture_worker.py").read_text())
        scientific = ast.parse((root / "scientific_worker.py").read_text())
        for name in ("_read_regular", "_study", "_api"):
            original_function = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == name)
            scientific_function = next(node for node in scientific.body if isinstance(node, ast.FunctionDef) and node.name == name)
            self.assertEqual(ast.dump(original_function), ast.dump(scientific_function))
        for filename in ("scientific_worker.py", "scientific_transport.py", "scientific_profile.py"):
            tree = ast.parse((root / filename).read_text())
            flags = [node.value for node in tree.body if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "SCIENTIFIC_ADMISSION_REVIEWED" for target in node.targets)]
            self.assertEqual(len(flags), 1)
            self.assertIsInstance(flags[0], ast.Constant)
            self.assertIs(flags[0].value, False)
        calls = {ast.unparse(node.func) for node in ast.walk(scientific) if isinstance(node, ast.Call)}
        self.assertIn("_run_neutral_loaded", calls)
        self.assertIn("_run_probes_loaded", calls)
        self.assertNotIn("_load", calls)

    def test_full_registry_maximum_metadata_schedule_fits_reallocated_budget(self):
        """All 420 normal/reporter reservations, 512 authored scalar slots.

        This is a counter/serialization test, with no policy/world generation and
        no real API import. It includes upper-bound function receipts and large
        authored identity manifests for all64 capsules.
        """
        totals = {category: 0 for category in CALL_CAPS}
        fake_manifest = {f"authored_module_{index:04d}.py": hashlib.sha256(str(index).encode()).hexdigest()
                         for index in range(256)}
        for worker_id in SLOTS:
            if worker_id == "terminal_reconciliation":
                continue
            self.ledger.claim_worker(worker_id)
            self.ledger.append("source_receipt", {"worker_id": worker_id,
                "api_manifest_sha256": digest(fake_manifest), "study_manifest_sha256": "2" * 64,
                "runtime_manifest_sha256": "3" * 64, "python_sha256": "4" * 64,
                "cold_flags": {"isolated": 1, "no_site": 1, "no_bytecode": True}})
            serial = 0
            for category, count in worker_allowances(worker_id).items():
                for _ in range(count):
                    serial += 1
                    self.ledger.record_actual_call(worker_id, serial, category)
                    self.ledger.record_actual_call(worker_id, serial, category, exited=True)
                totals[category] += count
            if ".create_select." in worker_id:
                self.ledger.append("cohort_reference_bound", {"case_id": worker_id.split(".create_select")[0],
                    "native_identity": {"code_manifest": fake_manifest, "runtime_manifest": fake_manifest},
                    "D_sha256": "5" * 64, "cohort_sha256": "6" * 64})
            self.ledger.append("worker_complete", {"worker_id": worker_id, "result_sha256": "7" * 64})
        for category, slots in transition_slots().items():
            for slot in slots:
                ticket = self.ledger.charge(category, slot)
                self.ledger.advance(ticket, "started")
                self.ledger.advance(ticket, "computed", result_hash="8" * 64)
                self.ledger.reconcile_saved(ticket, result_hash="8" * 64, authority_hash="9" * 64)
        for decision in registry()["decision_ids"]:
            self.ledger.decision_start(decision)
            self.ledger.decision_commit(decision, receipt_hash="a" * 64, is_null=False)
            self.ledger.append("interpretation_durable", {"decision_id": decision, "belief_hash": "b" * 64})
        for anchor in registry()["anchors"]:
            self.ledger.append("first_pair_gate", {"anchor_id": anchor["anchor_id"], "semantics_sha256": "c" * 64})
            self.ledger.append("forecast_set_frozen", {"anchor_id": anchor["anchor_id"], "commands": list(MOVEMENTS),
                "source_world_sha256": "d" * 64, "both_second_T1_durable": True,
                "second_T1_sha256": {"R": "a" * 64, "W": "a" * 64}})
        # Also reserve/record the single globally terminal read-only allowance.
        self.ledger.uncertain_workers.add(SLOTS[-3])
        self.ledger.claim_worker("terminal_reconciliation")
        serial = 0
        for category, count in worker_allowances("terminal_reconciliation").items():
            for _ in range(count):
                serial += 1
                self.ledger.record_actual_call("terminal_reconciliation", serial, category)
                self.ledger.record_actual_call("terminal_reconciliation", serial, category, exited=True)
            totals[category] += count
        self.ledger.append("worker_complete", {"worker_id": "terminal_reconciliation", "result_sha256": "e" * 64})
        self.assertEqual(totals, dict(CALL_CAPS))
        self.assertEqual(self.ledger.counters()["actual_entries"], dict(CALL_CAPS))
        self.assertEqual(self.ledger.counters()["charged_transitions"], 512)
        self.assertEqual(self.ledger.counters()["durably_consumed"], 512)
        self.assertEqual(self.ledger.counters()["scientific_transition_invocations"], 0)
        self.assertLess(self.ledger.expected_bytes, LEDGER_CAP)
        self.assertGreater(self.ledger.segment_index, 0)
        decoded, broken = ScientificLedger.read_verified(self.ledger.path)
        self.assertFalse(broken)
        self.assertEqual(decoded, self.ledger.records)
        self.assertEqual(self.files.verify_inventory()["actual_bytes"], self.ledger.expected_bytes)
        self.assertEqual(self.ledger.seal_descriptor()["total_prefix_bytes"], self.ledger.expected_bytes)
        for name, cap in zip(LEDGER_NAMES, LEDGER_SEGMENT_CAPS):
            path = self.files.root / name
            if path.exists():
                self.assertLessEqual(path.stat().st_size, cap)

    def _durable_stub_event(self, worker, request, message):
        if message["event"] in ("neutral_transition_saved", "probe_saved"):
            self.ledger.reconcile_saved(message["ticket"], result_hash=digest(message["authored_scalar_result"]),
                authority_hash=self.ledger.append("authored_scalar_saved", {"worker_id": worker, "ticket": message["ticket"]}))
        else:
            self.ledger.append("authored_metadata_saved", {"worker_id": worker, "event": message["event"]})
        return {}

    def test_cold_stub_neutral_precharge_full_horizon_and_freezes(self):
        original = os.sched_getaffinity(0)
        try:
            os.sched_setaffinity(0, {min(original)})
            transport = self.transport(handler=self._durable_stub_event)
            result = transport._dispatch("neutral.layout1", {"phase": "neutral", "layout": 1})
        finally:
            os.sched_setaffinity(0, original)
        self.assertEqual((result["actual_world_calls"], result["actual_api_calls"]), (0, 0))
        self.assertEqual(self.ledger.counters()["actual_entries_exact"]["transition"], 64)
        self.assertEqual(self.ledger.counters()["durably_consumed"], 64)
        for ticket in self.ledger._events("charged"):
            charged = next(row["sequence"] for row in self.ledger.records if row["kind"] == "charged" and row["payload"]["ticket"] == ticket["ticket"])
            started = next(row["sequence"] for row in self.ledger.records if row["kind"] == "started" and row["payload"]["ticket"] == ticket["ticket"])
            self.assertLess(charged, started)

    def _commitment(self, anchor="layout1.t32"):
        for arm in ("R", "W"):
            self.ledger.decision_start(f"{anchor}.{arm}.stage2")
            self.ledger.decision_commit(f"{anchor}.{arm}.stage2", receipt_hash=digest(arm), is_null=False)
        world = {"authored_scalar": 42}
        body = {"anchor_id": anchor, "commands": ["north", "west"], "source_world_sha256": digest(world),
            "both_second_T1_durable": True, "second_T1_sha256": {arm: digest(arm) for arm in ("R", "W")}}
        commitment = {**body, "ledger_receipt_sha256": self.ledger.append("forecast_set_frozen", body)}
        return {"phase": "probes", "anchor_id": anchor, "post_first_world": world, "forecast_commitment": commitment}

    def test_cold_stub_probes_bind_both_T1_F_world_and_all_four_commands(self):
        request = self._commitment()
        original = os.sched_getaffinity(0)
        try:
            os.sched_setaffinity(0, {min(original)})
            result = self.transport(handler=self._durable_stub_event)._dispatch("probes.layout1.t32", request)
        finally:
            os.sched_setaffinity(0, original)
        self.assertEqual(result["actual_world_calls"], 0)
        self.assertEqual(self.ledger.counters()["actual_entries_exact"]["transition"], 4)
        self.assertEqual([row["slot"].rsplit(".", 1)[-1] for row in self.ledger._events("charged")], list(MOVEMENTS))

    def test_invalid_probe_binding_and_owned_before_gate_charge_nothing(self):
        transport = self.transport()
        with self.assertRaises(IntegrityError):
            transport.charge_owned("layout1.t32.R", 1)
        request = self._commitment()
        request["post_first_world"]["authored_scalar"] += 1
        with self.assertRaises(IntegrityError):
            transport._dispatch("probes.layout1.t32", request)
        self.assertEqual(self.ledger._events("charged"), [])
        self.assertEqual(self.ledger._events("worker_admitted"), [])

    def test_owned_precharge_requires_equal_pair_and_both_second_commitments(self):
        transport = self.transport()
        anchor = "layout1.t32"
        for arm in ("R", "W"):
            self.ledger.decision_start(f"{anchor}.{arm}.stage1")
            self.ledger.decision_commit(f"{anchor}.{arm}.stage1", receipt_hash=digest(arm), is_null=False)
        with self.assertRaises(IntegrityError):
            transport.charge_owned(anchor + ".R", 1)
        self.assertFalse(self.ledger._events("charged"))
        self.ledger.append("first_pair_gate", {"anchor_id": anchor, "semantics_sha256": "a" * 64})
        ticket = transport.charge_owned(anchor + ".R", 1)
        self.assertEqual(ticket, "invocation1")
        with self.assertRaises(IntegrityError):
            transport.charge_owned(anchor + ".R", 1)
        with self.assertRaises(IntegrityError):
            transport.charge_owned(anchor + ".R", 2)
        self._commitment(anchor)
        self.assertEqual(transport.charge_owned(anchor + ".R", 2), "invocation2")

    def test_neutral_cannot_skip_discovery_freeze_or_send_branch_feedback(self):
        transport = self.transport(handler=self._durable_stub_event)
        with self.assertRaises(IntegrityError):
            transport._validate_request("neutral.layout1", {"phase": "neutral", "layout": 1, "outcome": {}})
        request = {"phase": "neutral", "layout": 1}
        with self.assertRaises(IntegrityError):
            transport._world_event("neutral.layout1", request,
                {"event": "transition_permit", "category": "neutral", "slot": "neutral.layout1.t1", "command": {}})
        transport._world_event("neutral.layout1", request, {"event": "neutral_initial", "layout": 1})
        with self.assertRaises(IntegrityError):
            transport._world_event("neutral.layout1", request,
                {"event": "D_frozen", "layout": 1, "frames": [None] * 33, "projected_rows": [None] * 32})
        self.assertEqual(self.ledger._events("charged"), [])

    def test_mixed_command_discovery_preserves_all_frames_and_exact_movement_rows(self):
        frames, rows = authored_mixed_discovery()
        self.assertEqual((len(frames), len(rows)), (33, 16))
        transport = self.transport(handler=self._durable_stub_event)
        worker, request = "neutral.layout1", {"phase": "neutral", "layout": 1}
        transport._world_event(worker, request, {"event": "neutral_initial", "layout": 1})
        # Authored prior acknowledgement metadata, not actual transition calls.
        transport._saved_permits.update((worker, f"authored-ticket-{index}") for index in range(32))
        message = {"event": "D_frozen", "layout": 1, "frames": frames, "projected_rows": rows}
        for bad_rows in (rows[:-1], rows + [rows[0]], list(reversed(rows))):
            with self.assertRaises(IntegrityError):
                transport._world_event(worker, request, {**message, "projected_rows": bad_rows})
        wrong_rows = deepcopy(rows)
        wrong_rows[0]["refs"]["receipt"] = "0" * 64
        with self.assertRaises(IntegrityError):
            transport._world_event(worker, request, {**message, "projected_rows": wrong_rows})
        transport._world_event(worker, request, message)
        self.assertTrue(transport._neutral_progress[worker]["D_frozen"])
        self.assertEqual(len(message["frames"]), 33)
        self.assertEqual(self.ledger.counters()["scientific_transition_invocations"], 0)

    def test_external_started_marker_counts_actual_run_owned_bytes(self):
        marker = Path(self.tmp.name) / "PERMANENT_AUTHORED_MARKER.json"
        self.files.reserve_started_marker(marker)
        raw = canonical({"authored_marker": True}) + b"\n"
        marker.write_bytes(raw)
        report = self.files.verify_inventory()
        self.assertEqual(report["actual_bytes"], self.ledger.expected_bytes + len(raw))
        self.assertEqual(report["external_artifacts"]["external-one-attempt-marker"]["actual_bytes"], len(raw))
        self.assertEqual(report["external_artifacts"]["external-one-attempt-marker"]["sha256"], hashlib.sha256(raw).hexdigest())
        with self.assertRaises(IntegrityError):
            self.files.reserve_started_marker(marker)

    def test_lost_child_marks_only_affected_counts_unknown_and_stops(self):
        original = os.sched_getaffinity(0)
        transport = self.transport(config={"die": True})
        try:
            os.sched_setaffinity(0, {min(original)})
            with self.assertRaises(IntegrityError):
                transport._dispatch("neutral.layout1", {"phase": "neutral", "layout": 1})
        finally:
            os.sched_setaffinity(0, original)
        counters = self.ledger.counters()
        self.assertIsNone(counters["actual_entries_exact"]["transition"])
        self.assertEqual(counters["actual_entries_exact"]["producer"], 0)
        self.assertEqual(counters["reservation_upper_bounds"]["transition"], 64)
        with self.assertRaises(IntegrityError):
            transport._dispatch("neutral.layout2", {"phase": "neutral", "layout": 2})

    def test_typed_report_resource_failure_preserves_exact_science_counts(self):
        worker = b'import sys,json\njson.loads(sys.stdin.buffer.readline())\nsys.stdout.write(\'{"event":"stage_resource_failure","reason":"CapacityError"}\\n\')\nsys.stdout.flush()\nsys.stdin.buffer.readline()\n'
        original = os.sched_getaffinity(0)
        transport = self.transport(worker=worker)
        native_events = []
        transport.emit = lambda *row: native_events.append(row)
        try:
            os.sched_setaffinity(0, {min(original)})
            with self.assertRaises(CapacityError):
                transport._dispatch("reporter", {"phase": "report_saved"})
        finally:
            os.sched_setaffinity(0, original)
        counts = self.ledger.counters()
        self.assertFalse(counts["evidence_loss"])
        self.assertTrue(counts["reporting_uncertainty"])
        self.assertFalse(counts["actual_entries_are_lower_bounds"])
        self.assertEqual(counts["actual_entries_exact"], {name: 0 for name in CALL_CAPS})
        self.assertEqual(self.ledger._events("report_resource_failure")[0]["reason"], "CapacityError")
        from ora_study.scientific_controller import emit_native_terminal
        emit_native_terminal(transport, self.ledger, "incomplete")
        self.assertEqual([row[0] for row in native_events], [5, 3, 10, 11, 12, 9])
        self.assertNotEqual(native_events[1][2], 0)
        self.assertEqual(native_events[-1], (9, 0, 1))
        with self.assertRaises(IntegrityError):
            transport._dispatch("reporter", {"phase": "report_saved"})

    def test_normal_reap_followed_by_failure_emits_completion_once(self):
        worker = b'import sys\nsys.stdin.buffer.readline()\nraise SystemExit(7)\n'
        transport = self.transport(worker=worker)
        events = []
        transport.emit = lambda *row: events.append(row)
        original = os.sched_getaffinity(0)
        try:
            os.sched_setaffinity(0, {min(original)})
            with self.assertRaises(IntegrityError):
                transport._dispatch("reporter", {"phase": "report_saved"})
        finally:
            os.sched_setaffinity(0, original)
        self.assertEqual([row[0] for row in events], [5, 3])
        self.assertEqual(events[-1], (3, 0, 7))

    def test_torn_later_segment_preserves_verified_prefix(self):
        payload = {"authored_metadata": "x" * 60000}
        for _ in range(36):
            self.ledger.append("authored_metadata", payload)
        self.assertEqual(self.ledger.segment_index, 1)
        good = len(self.ledger.records)
        with (self.files.root / LEDGER_NAMES[1]).open("ab") as stream:
            stream.write(b'{"torn":')
        rows, broken = ScientificLedger.read_verified(self.ledger.path)
        self.assertTrue(broken)
        self.assertEqual(len(rows), good)
        with self.assertRaises(IntegrityError):
            self.ledger.append("must_stop", {})

    def test_retries_overruns_and_terminal_followups_rejected(self):
        self.ledger.claim_worker("neutral.layout1")
        with self.assertRaises(IntegrityError):
            self.ledger.claim_worker("neutral.layout1")
        self.ledger.charge("neutral", "neutral.layout1.t1")
        with self.assertRaises(IntegrityError):
            self.ledger.charge("neutral", "neutral.layout1.t1")
        with self.assertRaises(IntegrityError):
            self.ledger.record_actual_call("neutral.layout1", 1, "producer")
        self.assertEqual(self.ledger.counters()["actual_entries"]["producer"], 1)
        self.assertTrue(self.ledger._events("actual_call_entered")[0]["overrun"])
        self.ledger.uncertain_workers.add("neutral.layout1")
        self.ledger.claim_worker("terminal_reconciliation")
        with self.assertRaises(IntegrityError):
            self.ledger.claim_worker("reporter")

    def test_source_slot_overflow_and_unreserved_file_stop(self):
        name = "sources/layout1.t32.R/ora.json"
        with self.assertRaises(CapacityError):
            self.files.put_new(name, "source_inputs", b"x" * (SOURCE_BOUNDS["ora"] + 1))
        self.assertFalse((self.files.root / name).exists())
        (self.files.root / "unreserved.json").write_bytes(b"{}")
        with self.assertRaises(IntegrityError):
            self.files.verify_inventory()


if __name__ == "__main__":
    unittest.main()
