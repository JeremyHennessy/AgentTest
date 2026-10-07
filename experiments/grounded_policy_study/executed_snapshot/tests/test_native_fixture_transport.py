"""Only authored scalar functions and native-shaped JSON; no real API imports."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from ora_study.native_fixture_transport import (FixtureInventory,FixtureLedger,FixtureReferences,
    SequentialNativeTransport,CALL_CAPS,NORMAL_SLOTS,ALLOCATION,LOG_CAP,MIB,read_regular)
from ora_study.native_fixture_controller import FixtureController
from ora_study.ledger import IntegrityError,CapacityError
from ora_study.protocol import canonical,digest

# A captured Python program exercising real cold pipes, entry/exit acknowledgement
# and fsynced ledger. Its sole tracked operation is authored scalar arithmetic.
FAKE_WORKER = b'''
import json,sys,os,hashlib,resource
packet=json.loads(sys.stdin.buffer.readline())
request=packet["request"]
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def h(x): return hashlib.sha256(canon(x)).hexdigest()
def send(x):
    os.write(1,canon(x)+b"\\n")
    ack=json.loads(sys.stdin.buffer.readline())
    if ack!={"accepted":True,"request_sha256":h(x)}: raise RuntimeError("bad ack")
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
assert resource.getrlimit(resource.RLIMIT_AS)==(384*1048576,384*1048576)
assert resource.getrlimit(resource.RLIMIT_FSIZE)==(2*1048576,2*1048576)
assert resource.getrlimit(resource.RLIMIT_NPROC)==(1,1)
assert len(os.sched_getaffinity(0))==1
assert set(os.environ)<= {"LANG","LC_ALL"}
assert not any(n.startswith(("grounded_policy_v2","agenttest","open_object_world_challenge")) for n in sys.modules)
if request.get("die"):
    os._exit(7)
if request.get("flood"):
    while True: os.write(2,b"x"*65536)
sys.path.insert(0,packet["configuration"]["test_package_parent"])
from ora_study.call_accounting import CallAccounting
def scalar(): return ({"authored_scalar":7},{"authored_scalar":8})
def count(message):
    send(message)
    return True
with CallAccounting({(scalar.__code__.co_filename,"scalar"):"transition"},count):
    for i in range(request.get("calls",1)): scalar()
result={"authored":True,"actual_api_calls":0,"actual_world_calls":0,"pid":os.getpid()}
send({"event":"stage_complete","result":result,"result_sha256":h(result)})
'''


class FixtureTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/"one-fixture"
        self.files=FixtureInventory(self.root)
        self.ledger=FixtureLedger(self.root/"ledger.jsonl")
        self.original_affinity=os.sched_getaffinity(0)
        os.sched_setaffinity(0,{min(self.original_affinity)})
        self.transport=SequentialNativeTransport(self.files,self.ledger,FAKE_WORKER,
            "/authored/fake_worker.py",{"test_package_parent":str(Path(__file__).parents[1])},time.clock_gettime_ns(time.CLOCK_BOOTTIME)+20*10**9,authored_fixture=True)
    def tearDown(self):
        self.ledger.close(); self.files.close()
        os.sched_setaffinity(0,self.original_affinity)
        self.tmp.cleanup()
    def test_fresh_capped_child_actual_entry_durable_prefix(self):
        ticket=self.ledger.charge("setup","setup.north1")
        result=self.transport._dispatch("setup",{},tickets=(ticket,))
        self.assertEqual(result["actual_world_calls"],0)
        self.assertNotEqual(result["pid"],os.getpid())
        rows,broken=FixtureLedger.read_verified(self.ledger.path)
        self.assertFalse(broken)
        kinds=[r["kind"] for r in rows]
        self.assertLess(kinds.index("charged"),kinds.index("actual_call_entered"))
        self.assertEqual(self.ledger.counters()["actual_entries"]["transition"],1)
        self.assertFalse(self.ledger.counters()["evidence_loss"])
        with self.assertRaises(IntegrityError): self.transport._dispatch("setup",{})
    def test_lost_child_marks_verified_counts_only_lower_bounds(self):
        with self.assertRaises(IntegrityError): self.transport._dispatch("setup",{"die":True})
        counters=self.ledger.counters()
        self.assertTrue(counters["evidence_loss"])
        self.assertTrue(counters["actual_entries_are_lower_bounds"])
        self.assertEqual(counters["reservation_upper_bounds"]["transition"],2)
        with self.assertRaises(IntegrityError): self.transport._dispatch("reporter",{})
    def test_overrun_entry_is_preserved_before_failure(self):
        self.ledger.claim_worker("setup")
        for i in (1,2): self.ledger.record_actual_call("setup",i,"transition")
        with self.assertRaises(IntegrityError): self.ledger.record_actual_call("setup",3,"transition")
        self.assertEqual(self.ledger.counters()["actual_entries"]["transition"],3)
        self.assertTrue(self.ledger._events("actual_call_entered")[-1]["overrun"])
        self.assertEqual(self.ledger.records[-1]["kind"],"integrity_failure")
    def test_unprecharged_observed_entry_stops_and_preserves(self):
        with self.assertRaises(IntegrityError): self.transport._dispatch("setup",{},tickets=())
        self.assertEqual(self.ledger.counters()["actual_entries"]["transition"],1)
        self.assertTrue(self.ledger.counters()["evidence_loss"])
    def test_global_reservations_include_one_terminal_read(self):
        self.ledger.claim_worker("setup")
        for worker in NORMAL_SLOTS: self.ledger.claim_worker(worker)
        self.ledger.claim_worker("terminal_reconciliation")
        self.ledger.claim_worker("reporter")
        totals={c:sum(p["allowances"][c] for p in self.ledger._events("worker_admitted")) for c in CALL_CAPS}
        self.assertEqual(totals,CALL_CAPS)
        with self.assertRaises(IntegrityError): self.ledger.claim_worker("terminal_reconciliation")
    def test_no_recharge_and_exclusive_root(self):
        self.ledger.charge("setup","setup.north1")
        with self.assertRaises(IntegrityError): self.ledger.charge("setup","setup.north1")
        with self.assertRaises(IntegrityError): FixtureInventory(self.root)
        with self.assertRaises(IntegrityError): self.ledger.charge("probe","north")
    def test_fixed_filesystem_inventory_and_log_prefix(self):
        self.assertEqual(sum(ALLOCATION.values()),25*MIB)
        self.files.log(b"a"*LOG_CAP)
        with self.assertRaises(CapacityError): self.files.log(b"b")
        self.assertEqual((self.root/"worker-logs.bin").stat().st_size,LOG_CAP)
    def test_scientific_guard_and_explicit_fixture_binding(self):
        # The real fixture is never invoked by test discovery; it needs the
        # separate fixed-profile GO receipt and durable one-attempt marker.
        with self.assertRaises(IntegrityError): self.transport.scientific_stage({"enabled":True})
        for name in ("native_fixture_controller.py","native_fixture_worker.py"):
            tree=ast.parse((Path(__file__).parents[1]/"ora_study"/name).read_text())
            assignments={t.id:n.value.value for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) for t in n.targets if isinstance(t,ast.Name)}
            self.assertIs(assignments["REAL_FIXTURE_ADMISSION_REVIEWED"],True)
            self.assertIs(assignments["SCIENTIFIC_ADMISSION_REVIEWED"],False)
    def test_symlink_and_oversize_inputs_refused(self):
        self.files.put_new("tiny","setup",b"abc")
        with self.assertRaises(IntegrityError): read_regular(self.root/"tiny",2)
        (self.root/"alias").symlink_to(self.root/"tiny")
        with self.assertRaises(IntegrityError): read_regular(self.root/"alias",10)


class CohortFixtureTests(unittest.TestCase):
    def test_complete_three_frame_raw_rows_and_normalized_missing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=FixtureInventory(Path(tmp)/"fixture")
            ledger=FixtureLedger(files.root/"ledger.jsonl")
            try:
                frames=[{"authored_frame":i} for i in range(3)]
                rows=[{"event_id":"authored-e1","before_context":{"visible_ids":["object1"]}}]
                norm=deepcopy(rows); norm[0]["before_context"]["entity.object1.state"]=None
                cohort={"discovery_events":[{"event_id":"authored-e1","digest":digest(norm[0])}],"authored":True}
                refs=FixtureReferences(ledger,files,frames,rows)
                proof=refs.bind("native-invariant.R",frames,cohort,{"run_id":"R","discovery_count":2})
                self.assertEqual(proof["D_sha256"],digest(frames))
                with self.assertRaises(IntegrityError): refs.bind("native-invariant.W",frames+[{}],cohort,{"run_id":"W","discovery_count":2})
                bad=deepcopy(cohort); bad["authored"]=False
                with self.assertRaises(IntegrityError): refs.bind("native-invariant.W",frames,bad,{"run_id":"W","discovery_count":2})
                refs.bind("native-invariant.W",frames,cohort,{"run_id":"W","discovery_count":2})
                self.assertEqual(len(ledger._events("cohort_reference_bound")),2)
            finally: ledger.close(); files.close()


class CompleteAuthoredControllerTests(unittest.TestCase):
    def test_one_pair_null_schedule_saves_and_rechecks_parent_sequences(self):
        # Handwritten public frames and declaration-only native receipts. These
        # are not API-validated models or outcomes and contain no world calls.
        from test_native_projection import bare_state, add_decision, observation, signed
        from ora_study.native_projection import _rows
        from ora_study.native_fixture_controller import report_saved
        from ora_study.profiles import INVARIANT_PROFILE
        class FakePort:
            authored_fixture_only=True
            def __init__(self,files,ledger):
                self.files,self.ledger=files,ledger
                self.config={"api_manifest":{"authored.py":"b"*64},"api_runtime_manifest":{"authored":"runtime"}}
                self.references=None; self.bound_identities={}; self.calls=[]; self.states={}
                self.emit=lambda *args:None
            def _dispatch(self,worker,request,*,tickets=(),precondition=None):
                self.ledger.claim_worker(worker); self.calls.append(worker)
                phase=request["phase"]
                if phase=="setup":
                    frames=[{"observation":observation(0),"receipt":None}]; transitions=[]
                    for i,ticket in enumerate(tickets,1):
                        receipt={"id":f"OWC-A{i:06d}","cycle":i,"action":"north","target":None,
                            "direction":None,"before":[0,0],"after":[0,0],"success":False,"blocked":True,
                            "observed_effects":["Authored stationary frame"],"visible_entity_states":{}}
                        world={"authored_scalar":i}
                        record={"world":world,"receipt":receipt}; transitions.append(record)
                        frames.append({"observation":observation(i),"receipt":receipt})
                        self.ledger.record_actual_call(worker,i,"transition")
                        self.ledger.advance(ticket,"started")
                        self.ledger.record_actual_call(worker,i,"transition",exited=True)
                        self.ledger.advance(ticket,"computed",result_hash=digest(record))
                    self.values={"ora":{},"world":world,"observations":frames}
                    result={"phase":"setup","values":self.values,"transitions":transitions}
                    self.ledger.append("worker_complete",{"worker_id":worker,"result_sha256":digest(result)})
                    return result
                if phase=="report_saved":
                    result=report_saved(request)
                    self.ledger.append("worker_complete",{"worker_id":worker,"result_sha256":digest(result)})
                    return result
                case=request["case_id"]; path=Path(request["path"])
                if phase=="create_select":
                    state=bare_state(case,"retain_first" if request["arm"]=="R" else "withhold_first")
                    state.update(frames=deepcopy(self.values["observations"]),ora={},world=deepcopy(self.values["world"]))
                    identity=state["identity"]
                    identity.update(path=str(path),research_dir=str(path.parent),discovery_count=2,
                        initial_ora_hash=digest({}),initial_world_hash=digest(state["world"]),
                        initial_frames_hash=digest(state["frames"]),code_manifest=self.config["api_manifest"],runtime_manifest=self.config["api_runtime_manifest"])
                    identity["adapter"]["world_id"]=identity["initial_world_hash"]
                    for name,source in request["source_paths"].items():
                        raw=Path(source).read_bytes(); info=Path(source).stat()
                        identity["source_inputs"][name]={"path":source,"sha256":hashlib.sha256(raw).hexdigest(),
                            "device":info.st_dev,"inode":info.st_ino,"bytes":len(raw)}
                    state["identity_hash"]=digest(identity)
                    rows=_rows(state["frames"])
                    state["cohort"]["discovery_events"]=[{"event_id":r["event_id"],"digest":digest(r)} for r in rows]
                    state["cohort"]["cohort_digest"]=digest({k:v for k,v in state["cohort"].items() if k!="cohort_digest"})
                    self.references.bind(case,state["frames"],state["cohort"],identity)
                    self.bound_identities[case]=digest(identity)
                    path.with_name(path.name+".lock").write_bytes(b"")
                else:
                    raw=path.read_bytes(); state=json.loads(raw)
                    assert precondition=={"capsule_sha256":hashlib.sha256(raw).hexdigest(),"identity_sha256":digest(state["identity"])}
                add_decision(state,status="policy_null")
                path.write_bytes(canonical(state)+b"\n")
                result={"phase":phase,"state":state,"returned":state["decisions"][-1]}
                self.ledger.append("worker_complete",{"worker_id":worker,"result_sha256":digest(result)})
                return result
        with tempfile.TemporaryDirectory() as tmp:
            files=FixtureInventory(Path(tmp)/"fixture"); ledger=FixtureLedger(files.root/"ledger.jsonl")
            try:
                port=FakePort(files,ledger)
                report=FixtureController(port)._run_pair()
                self.assertEqual(port.calls,["setup","native-invariant.R.create_select.stage1",
                    "native-invariant.W.create_select.stage1","native-invariant.R.select.stage2",
                    "native-invariant.W.select.stage2","reporter"])
                self.assertIsNone(report["science_result"])
                self.assertEqual(report["counters"]["actual_entries"]["transition"],2)
                self.assertEqual(report["fixture_decisions"],4)
                self.assertEqual(report["scientific_denominators"],0)
                self.assertTrue(report["requires_outer_terminal_seal"])
                self.assertEqual(len(list((files.root/"exports").glob("*.json"))),4)
                self.assertTrue((files.root/"candidate-report.json").exists())
                seal=next(row for row in ledger.records if row["kind"]=="fixture_evidence_sealed")
                saved_request={"phase":"report_saved","exports":deepcopy(seal["payload"]["exports"]),
                    "ledger_path":str(ledger.path),"ledger_head":seal["hash"],
                    "counters":deepcopy(seal["payload"]["counters"]),"terminal_state":"complete"}
                saved_request["counters"]["actual_entries"]["transition"]+=1
                with self.assertRaises(IntegrityError): report_saved(saved_request)
                saved_request["counters"]=deepcopy(seal["payload"]["counters"])
                saved_request["ledger_head"]=ledger.records[0]["hash"]
                with self.assertRaises(IntegrityError): report_saved(saved_request)
            finally: ledger.close(); files.close()


class OneAttemptMarkerTests(unittest.TestCase):
    def test_changed_output_root_cannot_reset_one_fixture_marker(self):
        from ora_study.native_fixture_controller import claim_one_started_marker,FIXTURE_ID
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); package=base/"study"/"ora_study"
            package.mkdir(parents=True); (base/"policy-study-results").mkdir()
            receipt=base/"authored-approval.json"
            files=FixtureInventory(base/"first-output")
            second=FixtureInventory(base/"second-output")
            try:
                def make_config(destination):
                    expected={"decision":"GO","fixture_id":FIXTURE_ID,"output_root":str(destination),
                        "profile_sha256":"a"*64,"study_manifest_sha256":"b"*64,
                        "started_marker_path":str(base/"policy-study-results"/"ONE_NATIVE_INVARIANT_STARTED.json")}
                    receipt.write_bytes(canonical(expected)+b"\n")
                    return {"fixture_id":FIXTURE_ID,"output_root":str(destination),"admission_receipt_path":str(receipt),
                        "started_marker_path":expected["started_marker_path"]}
                claim_one_started_marker(files,package,make_config(files.root),"a"*64,"b"*64)
                with self.assertRaises(FileExistsError):
                    claim_one_started_marker(second,package,make_config(second.root),"a"*64,"b"*64)
            finally: files.close(); second.close()

    def test_native_root_adopts_only_usable_terminal_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"native"; root.mkdir()
            (root/"launcher.status").write_bytes(b"\0"*MIB)
            files=FixtureInventory(root,native_root_precreated=True)
            try:
                self.assertEqual(files.used("finalization"),MIB)
                self.assertEqual(files.used("ledger_and_logs"),2*MIB)
            finally: files.close()


if __name__=="__main__": unittest.main()
