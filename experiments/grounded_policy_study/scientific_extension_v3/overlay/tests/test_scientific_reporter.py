"""Authored JSON/ledger observations only; no world, API or policy execution."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ora_study import native_projection as projection, scorer
from ora_study import scientific_reporter as reporter
from ora_study.protocol import MIB, canonical, digest, registry, worker_allowances
from ora_study.scientific_profile import CALL_CAPS, SLOTS
from ora_study.scientific_transport import ScientificLedger
from ora_study.ledger import CapacityError, IntegrityError
from test_native_projection import bare_state, add_decision, observation, signed


def descriptor(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value) + b"\n"
    path.write_bytes(raw)
    return {"path": str(path), "raw_sha256": hashlib.sha256(raw).hexdigest(), "state_sha256": digest(value)}


def source_binding():
    return {"api_manifest_sha256": digest({"fixture.py": "b" * 64}),
            "study_manifest_sha256": "a" * 64, "runtime_manifest_sha256": digest({"fixture": "authored"}),
            "python_sha256": "d" * 64, "cold_flags": {"isolated": 1, "no_site": 1, "no_bytecode": True}}


def empty_index():
    return {"schema": reporter.INDEX_SCHEMA, "registry": registry(), "anchors": [
        {"anchor_id": row["anchor_id"], "layout": row["layout"], "neutral_t": row["t"],
         "capsules": {"R": None, "W": None}, "probes": {}, "forecast_commitment": None}
        for row in registry()["anchors"]]}


class AuthoredSavedReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = ScientificLedger(self.root / "ledger.jsonl", authored_fixture=True)
        self.ledger.append("scientific_source_frozen", {"source_binding": source_binding()})
        self.index = empty_index()

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def seal(self, terminal="resource_interrupted"):
        index = descriptor(self.root / "study-index.json", self.index)
        head = self.ledger.append("scientific_evidence_sealed", {"index_path": index["path"],
            "index_sha256": index["raw_sha256"], "terminal_state": terminal,
            "resources": {"authored_fixture": True}, "formation": {"scope": "one_run", "fixture": True}})
        return {"phase": "report_saved", "index_path": index["path"], "index_sha256": index["raw_sha256"],
                "ledger_path": str(self.ledger.path), "ledger_head": head}

    def admit(self, worker):
        self.ledger.claim_worker(worker)
        self.ledger.append("source_receipt", {"worker_id": worker, **source_binding()})

    def entry(self, worker, call, category):
        self.ledger.record_actual_call(worker, call, category)

    def exited(self, worker, call, category):
        self.ledger.record_actual_call(worker, call, category, exited=True)

    def complete(self, worker):
        self.ledger.append("worker_complete", {"worker_id": worker, "result_sha256": digest({"authored": True})})

    def authored_pair(self):
        """Hand author one null/null anchor and all required source receipts."""
        worker, layout = "neutral.layout1", 1
        self.admit(worker)
        frames = [{"observation": observation(0), "receipt": None}]
        initial = descriptor(self.root / "neutral/initial.json", {"world": {"authored": 0}, "frame": frames[0]})
        self.ledger.append("neutral_initial", {"layout": layout, "descriptor": initial})
        for t in range(1, 65):
            ticket = self.ledger.charge("neutral", f"neutral.layout1.t{t}")
            self.entry(worker, t, "transition")
            self.ledger.advance(ticket, "started")
            self.exited(worker, t, "transition")
            receipt = {"id": f"OWC-A{t:06d}", "cycle": t, "action": "north", "target": None, "direction": None,
                "before": [0, 0], "after": [0, 0], "success": False, "blocked": True,
                "observed_effects": ["Authored JSON"], "visible_entity_states": {}}
            after = observation(t)
            result_hash = digest({"world": {"authored": t}, "receipt": receipt})
            self.ledger.advance(ticket, "computed", result_hash=result_hash)
            saved = {"event": "neutral_transition_saved", "layout": 1, "t": t, "ticket": ticket,
                "command": {"action": "north"}, "before_observation": frames[-1]["observation"],
                "after_observation": after, "receipt": receipt}
            self.ledger.append("neutral_transition_saved", saved)
            self.ledger.advance(ticket, "durably_consumed", result_hash=result_hash, authority_hash=digest(saved))
            frames.append({"observation": after, "receipt": receipt})
            if t == 32:
                material = {"frames": deepcopy(frames), "projected_rows": projection._rows(frames)}
                d = descriptor(self.root / "references/D.json", material)
                self.ledger.append("D_frozen", {"layout": 1, "descriptor": d, "D_sha256": digest(frames),
                    "projected_D_sha256": digest(material["projected_rows"])})
            if t in scorer.ANCHOR_TIMES:
                d = descriptor(self.root / f"neutral/t{t}.json", {"world": {"authored": t}})
                self.ledger.append("neutral_anchor_saved", {"layout": 1, "t": t, "anchor_id": f"layout1.t{t}",
                    "descriptor": d, "frames_sha256": digest(frames), "ticket": ticket, "computed_result_sha256": result_hash})
        self.complete(worker)
        d = descriptor(self.root / "neutral/frames.json", {"frames": frames})
        self.ledger.append("neutral_complete", {"layout": 1, "descriptor": d, "actual_transitions": 64, "counter_attempt_total": 64})
        frames = frames[:33]
        values = {"ora": {}, "world": {"authored": 32}, "observations": frames}
        states, proofs = {}, {}
        for arm in ("R", "W"):
            case = "layout1.t32." + arm
            proofs[case] = {}
            for name, value in values.items():
                path = self.root / "sources" / case / (name + ".json")
                d = descriptor(path, value)
                info = path.stat()
                proofs[case][name] = {"path": str(path), "sha256": d["raw_sha256"], "device": info.st_dev,
                                      "inode": info.st_ino, "bytes": info.st_size}
            state = bare_state("authored-" + arm, {"R": "retain_first", "W": "withhold_first"}[arm])
            state.update(frames=deepcopy(frames), world={"authored": 32}, ora={})
            identity = state["identity"]
            identity.update(path=str(self.root / "capsules" / (case + ".json")), research_dir=str(self.root / "capsules"),
                source_inputs=proofs[case], discovery_count=32, initial_ora_hash=digest({}),
                initial_world_hash=digest(values["world"]), initial_frames_hash=digest(frames))
            identity["adapter"]["world_id"] = identity["initial_world_hash"]
            state["identity_hash"] = digest(identity)
            cohort = state["cohort"]
            cohort["discovery_events"] = [{"event_id": row["event_id"], "digest": digest(row)} for row in projection._rows(frames)]
            cohort["cohort_digest"] = digest({k: v for k, v in cohort.items() if k != "cohort_digest"})
            add_decision(state, status="policy_null")
            add_decision(state, status="policy_null")
            states[arm] = state
        self.ledger.append("paired_sources_frozen", {"anchor_id": "layout1.t32", "source_proofs": proofs,
            "logical_values_sha256": digest(values)})
        for stage in (1, 2):
            for arm in ("R", "W"):
                case, state = "layout1.t32." + arm, states[arm]
                decision_id = f"{case}.stage{stage}"
                self.ledger.decision_start(decision_id)
                phase = "create_select" if stage == 1 else "select"
                worker = f"{case}.{phase}.stage{stage}"
                self.admit(worker)
                if stage == 1:
                    self.entry(worker, 1, "producer")
                    self.exited(worker, 1, "producer")
                    self.ledger.append("cohort_reference_bound", {"case_id": case, "layout": 1,
                        "reference_case_id": "layout1.t32.R", "D_sha256": digest(frames),
                        "projected_D_sha256": digest(projection._rows(frames)), "cohort_sha256": digest(state["cohort"]),
                        "reference_bytes_sha256": digest({"frames": frames, "projected_rows": projection._rows(frames), "cohort": state["cohort"]}),
                        "native_identity": state["identity"]})
                self.entry(worker, 2, "selecting_backend")
                self.exited(worker, 2, "selecting_backend")
                self.complete(worker)
                self.ledger.decision_commit(decision_id, receipt_hash=state["decisions"][stage - 1]["hash"], is_null=True)
            if stage == 1:
                self.ledger.append("first_pair_gate", {"anchor_id": "layout1.t32", "semantics_sha256": digest(projection.first_decision_semantics(states["R"]))})
        commitment = {"anchor_id": "layout1.t32", "commands": ["north"], "source_world_sha256": digest(values["world"]),
            "both_second_T1_durable": True, "second_T1_sha256": {arm: states[arm]["decisions"][1]["hash"] for arm in ("R", "W")}}
        commitment["ledger_receipt_sha256"] = self.ledger.append("forecast_set_frozen", deepcopy(commitment))
        d = descriptor(self.root / "exports/F.json", {"commitment": commitment, "post_first_world": values["world"]})
        self.index["anchors"][0]["forecast_commitment"] = d
        self.ledger.append("forecast_artifact_saved", {"anchor_id": "layout1.t32", "descriptor": d})
        worker = "probes.layout1.t32"
        self.admit(worker)
        for call, action in enumerate(scorer.DIRECTIONS, 1):
            ticket = self.ledger.charge("probe", "probe.layout1.t32." + action)
            self.entry(worker, call, "transition")
            self.ledger.advance(ticket, "started")
            self.exited(worker, call, "transition")
            receipt = deepcopy(frames[-1]["receipt"])
            receipt.update(id="OWC-A000033", cycle=33, action=action)
            result_hash = digest({"authored_probe": action})
            self.ledger.advance(ticket, "computed", result_hash=result_hash)
            saved = {"anchor_id": "layout1.t32", "action": action, "source_world_sha256": digest(values["world"]),
                "forecast_commitment_sha256": digest(commitment), "command": {"action": action},
                "before_observation": observation(32), "after_observation": observation(33), "receipt": receipt}
            d = descriptor(self.root / "exports" / (action + ".json"), saved)
            self.index["anchors"][0]["probes"][action] = d
            self.ledger.append("probe_saved", {"anchor_id": "layout1.t32", "action": action, "ticket": ticket, "descriptor": d})
            self.ledger.advance(ticket, "durably_consumed", result_hash=result_hash, authority_hash=digest(saved))
        self.complete(worker)
        for arm, state in states.items():
            self.index["anchors"][0]["capsules"][arm] = descriptor(Path(state["identity"]["path"]), state)
        return states

    def test_empty_saved_interruption_is_incomplete_with_exact_zero_counts(self):
        result = reporter.build_saved_report(self.seal())
        self.assertEqual(result["classification"], "incomplete", result["errors"])
        self.assertIsNone(result["scientific_result"])
        self.assertEqual(result["counters"]["neutral_invocations"], {"known": 0, "unknown": False})
        self.assertTrue(result["requires_outer_terminal_seal"])

    def test_authored_pair_binds_native_bytes_and_all_raw_entries(self):
        self.authored_pair()
        result = reporter.build_saved_report(self.seal())
        self.assertEqual(result["classification"], "incomplete", result["errors"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["counters"]["neutral_invocations"]["known"], 64)
        self.assertEqual(result["counters"]["probe_invocations"]["known"], 4)
        self.assertEqual(result["counters"]["decisions_committed"]["known"], 4)
        self.assertEqual(len(result["anchors"]), 1)
        self.assertEqual(len(result["raw_public_outcomes"][0]["probes"]), 4)
        self.assertEqual(result["fixture_denominators"]["validated_decisions"], 4)
        self.assertLess(len(canonical(result)), MIB)
        self.assertNotIn("native_body", str(result["saved_input"]))

    def test_partial_index_cannot_omit_a_durable_probe(self):
        self.authored_pair()
        del self.index["anchors"][0]["probes"]["west"]
        result = reporter.build_saved_report(self.seal())
        self.assertEqual(result["classification"], "invalid")
        self.assertTrue(any("omitted or changed independently saved probe" in error for error in result["errors"]))
        self.assertEqual(result["counters"]["probe_durable"]["known"], 4)

    def test_partial_capsule_cannot_omit_committed_second_decision(self):
        states = self.authored_pair()
        state = states["W"]
        state["decisions"] = state["decisions"][:1]
        state["events"] = state["events"][:1]
        state["revision"] = 1
        self.index["anchors"][0]["capsules"]["W"] = descriptor(Path(state["identity"]["path"]), state)
        result = reporter.build_saved_report(self.seal())
        self.assertEqual(result["classification"], "invalid")
        self.assertTrue(any("omits independently committed decision" in error for error in result["errors"]))
        self.assertEqual(result["counters"]["decisions_committed"]["known"], 4)

    def test_first_null_full_second_semantics_checked_before_compacting(self):
        self.authored_pair()
        request = self.seal()
        original = projection.decision_semantics
        def differing_native_body(state, ordinal):
            semantic = original(state, ordinal)
            if ordinal == 2 and state["identity"]["evidence_mode"] == "withhold_first":
                semantic["native_body"]["menu"][0]["expected_model_entropy_bits"] = "0.610000000000000000"
            return semantic
        with patch.object(projection, "decision_semantics", side_effect=differing_native_body):
            result = reporter.build_saved_report(request)
        self.assertEqual(result["classification"], "invalid")
        self.assertTrue(any("First-null pair differs in complete second" in error for error in result["errors"]))

    def test_sealed_integrity_failure_dominates_incomplete(self):
        result = reporter.build_saved_report(self.seal("integrity_failure"))
        self.assertEqual(result["classification"], "invalid")
        self.assertIsNone(result["scientific_result"])

    def test_unclosed_worker_marks_affected_count_unknown(self):
        self.admit("neutral.layout1")
        result = reporter.build_saved_report(self.seal())
        self.assertEqual(result["classification"], "invalid")
        self.assertEqual(result["counters"]["neutral_invocations"], {"known": 0, "unknown": True})
        self.assertEqual(result["counters"]["owned_invocations"], {"known": 0, "unknown": False})

    def test_no_caller_counts_or_gate_booleans(self):
        request = self.seal()
        request["counters"] = {"probe_invocations": 0}
        self.assertEqual(reporter.build_saved_report(request)["classification"], "invalid")

    def test_verified_seal_survives_only_later_torn_reporter_tail(self):
        request = self.seal()
        self.ledger.close()
        with (self.root / "ledger.jsonl").open("ab") as stream:
            stream.write(b'{"torn":')
        result = reporter.build_saved_report(request)
        self.assertEqual(result["classification"], "incomplete", result["errors"])
        self.assertTrue(result["raw_invocation_evidence"]["later_ledger_tail_broken"])

    def test_pinned_index_cannot_be_replaced(self):
        request = self.seal()
        (self.root / "study-index.json").write_bytes(b"{}\n")
        self.assertEqual(reporter.build_saved_report(request)["classification"], "invalid")

    def test_fixed_worker_chunks_reconstruct_exact_bytes_and_reject_tamper(self):
        request = self.seal()
        (self.root / "reports").mkdir()
        value = {"classification": "incomplete", "scientific_result": None, "saved_records_seal_hash": request["ledger_head"],
                 "payload": "a" * (4 * MIB + 71)}
        with patch.object(reporter, "build_saved_report", return_value=value):
            manifest = reporter.report_saved(request)
        self.assertLess(len(canonical(manifest)), 4096)
        result = reporter.read_chunked_report(manifest, self.root)
        self.assertEqual(result, value)
        chunks = list((self.root / "reports").glob("*.bin"))
        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(path.stat().st_size <= 2 * MIB for path in chunks))
        chunks[0].chmod(0o600)
        chunks[0].write_bytes(b"bad")
        with self.assertRaises(IntegrityError):
            reporter.read_chunked_report(manifest, self.root)

    def test_chunk_writer_never_overwrites_existing_files(self):
        request = self.seal()
        (self.root / "reports").mkdir()
        reporter.report_saved(request)
        with self.assertRaises(FileExistsError):
            reporter.report_saved(request)

    def test_verified_invalid_manifest_dominates_later_allocation_failure(self):
        request = self.seal()
        (self.root / "reports").mkdir()
        value = {"classification": "invalid", "scientific_result": None,
                 "saved_records_seal_hash": request["ledger_head"]}
        with patch.object(reporter, "build_saved_report", return_value=value):
            manifest = reporter.report_saved(request)
        with patch.object(reporter, "_read_report_chunks", side_effect=MemoryError("authored allocation")):
            with self.assertRaisesRegex(IntegrityError, "Verified invalid report manifest"):
                reporter.read_chunked_report(manifest, self.root)

    def test_original_descriptor_rejects_aliased_file(self):
        d = descriptor(self.root / "original.json", {"value": 1})
        (self.root / "alias.json").symlink_to(self.root / "original.json")
        d["path"] = str(self.root / "alias.json")
        with self.assertRaises(IntegrityError):
            reporter.read_descriptor(d, self.root)


class LedgerAndCompactionTests(unittest.TestCase):
    def test_invalid_candidate_dominates_failure_before_descriptor(self):
        for classification, error_type in ((scorer.INVALID, IntegrityError), (scorer.INCONCLUSIVE, CapacityError)):
            with patch.object(reporter, "build_saved_report", return_value={"classification": classification}), \
                 patch.object(reporter, "_persist_report", side_effect=CapacityError("authored output allocation")):
                with self.assertRaises(error_type):
                    reporter.report_saved({"authored": True})

    def test_reserved_report_overflow_is_typed_resource_interruption(self):
        with self.assertRaises(CapacityError):
            reporter.chunk_exact_bytes({"authored": "too much"}, maximum=4)

    def test_raw_second_charge_requires_F_even_without_outcome(self):
        audit = reporter.LedgerAudit([], source_binding=source_binding())
        anchor = "layout1.t32"
        audit.first_gates[anchor] = {"sequence": 3, "payload": {"semantics_sha256": "a" * 64}}
        for arm in ("R", "W"):
            audit.decisions[f"{anchor}.{arm}.stage1"] = {"sequence": 2, "payload": {"is_null": True, "receipt_hash": "b" * 64}}
            audit.decisions[f"{anchor}.{arm}.stage2"] = {"sequence": 5, "payload": {"is_null": False, "receipt_hash": "c" * 64}}
        with self.assertRaisesRegex(IntegrityError, "shared F/world"):
            audit._owned_or_probe_gate("owned", "owned.layout1.t32.R.stage2", 10)
        audit.forecast_sets[anchor] = {"sequence": 9, "payload": {"both_second_T1_durable": True,
            "second_T1_sha256": {"R": "c" * 64, "W": "c" * 64}, "source_world_sha256": "d" * 64}}
        audit._owned_or_probe_gate("owned", "owned.layout1.t32.R.stage2", 10)
        with self.assertRaisesRegex(IntegrityError, "shared F/world"):
            audit._owned_or_probe_gate("owned", "owned.layout1.t32.R.stage2", 9)

    def test_illegal_observed_entry_is_counted_even_without_legal_charge(self):
        worker = "layout1.t32.R.execute.stage1"
        payloads = [("registered", {"registry": registry(), "worker_slots": list(SLOTS), "call_ceilings": dict(CALL_CAPS), "automatic_retries": 0}),
            ("worker_admitted", {"worker_id": worker, "allowances": worker_allowances(worker)}),
            ("source_receipt", {"worker_id": worker, **source_binding()}),
            ("charged", {"ticket": "invocation1", "category": "owned", "slot": "owned.layout1.t32.R.stage1", "recomputation_of": None}),
            ("actual_call_entered", {"worker_id": worker, "call_id": 1, "category": "transition", "overrun": False}),
            ("actual_call_exited", {"worker_id": worker, "call_id": 1, "category": "transition", "overrun": False}),
            ("worker_complete", {"worker_id": worker})]
        rows = [{"sequence": index, "kind": kind, "payload": value} for index, (kind, value) in enumerate(payloads)]
        audit = reporter.LedgerAudit(rows, source_binding=source_binding())
        self.assertTrue(audit.errors)
        self.assertEqual(audit.counters()["owned_invocations"], {"known": 1, "unknown": False})

    def test_compact_stage_preserves_forecast_and_reconstructable_native_reference(self):
        state = add_decision(bare_state(), status="policy_null")
        sequence = {"t1_committed": 4, "outcome_invoked": None, "outcome_durable": None, "t3_completed": None}
        stage = projection.project_native_stage(state, 1, case_id="case-R", sequence=sequence)
        description = {"path": "/immutable/capsule.json", "raw_sha256": "a" * 64, "state_sha256": digest(state)}
        compact = reporter.compact_stage(stage, description, 1)
        self.assertEqual(compact["t1"]["semantic"]["forecasts"], stage["t1"]["semantic"]["forecasts"])
        self.assertEqual(compact["t1"]["provenance"]["full_semantic_sha256"], stage["t1"]["sha256"])
        self.assertEqual(compact["t1"]["provenance"]["native_capsule"], description)
        self.assertNotIn("native_body", compact["t1"]["semantic"])
        scorer._stage(compact, "case-R", 1, stage["t1"]["semantic"]["context"], interrupted=True)

    def test_reporter_imports_no_executable_api_policy_or_world(self):
        tree = ast.parse(Path(reporter.__file__).read_text())
        banned = ("grounded_policy", "agenttest", "world_worker", "scientific_worker", "executive", "open_object_world")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertFalse(any(name in (node.module or "") for name in banned))
            if isinstance(node, ast.Import):
                self.assertFalse(any(part in alias.name for alias in node.names for part in banned))
        self.assertNotIn("initial_world(", Path(reporter.__file__).read_text())
        self.assertNotIn("transition(", Path(reporter.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
