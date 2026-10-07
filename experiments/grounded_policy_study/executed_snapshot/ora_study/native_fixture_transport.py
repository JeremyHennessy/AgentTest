"""Review-only finite cold-process transport; no API is imported here.

The actual fixture and scientific entrypoints stay source-disabled. Authored tests
use an explicitly supplied captured fake worker. This is a trusted-source resource
composition, not an adversarial Python/filesystem sandbox.
"""
from __future__ import annotations
from copy import deepcopy
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time
from .artifact_inventory import ArtifactInventory, SOURCE_BOUNDS
from .ledger import Ledger, IntegrityError, CapacityError
from .profiles import INVARIANT_PROFILE, SCIENTIFIC_PROFILE
from .protocol import canonical, digest, worker_allowances

MIB = 1048576
PIPE_CAP = 4*MIB
LOG_CAP = MIB-32768
CALL_CAPS = {"producer":2,"capsule_validation":64,"cohort_proof":64,
             "decision_proof":82,"checker_reconstruction":146,
             "selecting_backend":4,"transition":6,"forbidden_core_cycle":0}
ALLOCATION = {"capsules":4*MIB,"temporary_peak":2*MIB,"source_inputs":MIB,
              "setup":MIB,"references":2*MIB,"exports":8*MIB,
              "ledger_and_logs":2*MIB,"reports":2*MIB,"manifests":2*MIB,
              "finalization":MIB}
NORMAL_SLOTS = tuple(f"{case}.{phase}.stage{stage}" for case in INVARIANT_PROFILE["case_ids"]
    for phase,stage in (("create_select",1),("execute",1),("interpret",1),
                        ("select",2),("execute",2),("interpret",2)))
SLOTS = ("setup",)+NORMAL_SLOTS+("terminal_reconciliation","reporter")


def read_regular(path, maximum):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise IntegrityError("Symlinked artifact/source ancestry")
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > maximum:
            raise IntegrityError("Unbounded or aliased file")
        raw = bytearray()
        while True:
            part = os.read(fd,min(65536,maximum+1-len(raw)))
            if not part: break
            raw.extend(part)
            if len(raw)>maximum: raise CapacityError("File exceeds frozen allocation")
        if os.fstat(fd).st_size != len(raw):
            raise IntegrityError("File changed while read")
        return bytes(raw)
    finally:
        os.close(fd)


class FixtureInventory(ArtifactInventory):
    """All writable fixture slots, reserved before setup or child dispatch."""
    def __init__(self,root,*,native_root_precreated=False):
        root=Path(root).absolute()
        if any(p.is_symlink() for p in (root,*root.parents)):
            raise IntegrityError("Aliased output root")
        if native_root_precreated:
            if not root.is_dir() or {p.name for p in root.iterdir()}!={"launcher.status"}:
                raise IntegrityError("Native-precreated root must contain only its exclusive terminal reserve")
            reserve=root/"launcher.status"
            read_regular(reserve,MIB)
            if reserve.stat().st_size!=MIB:
                raise IntegrityError("Native terminal reserve must already exist at one MiB")
        else:
            if root.exists(): raise IntegrityError("One exclusive output root; never rerun/reuse")
            root.mkdir(mode=0o700)
        super().__init__(root,allocations=ALLOCATION)
        self.log_bytes=0
        self.reserve("launcher.status","finalization",MIB)
        self.reserve("launcher.stdout","ledger_and_logs",16384)
        self.reserve("launcher.stderr","ledger_and_logs",16384)
        self.reserve("capsules/.one-replacement.tmp","temporary_peak",2*MIB)
        self.reserve("ledger.jsonl","ledger_and_logs",MIB)
        self.reserve("worker-logs.bin","ledger_and_logs",LOG_CAP)
        (root/"capsules").mkdir()
        for case in INVARIANT_PROFILE["case_ids"]:
            self.reserve(f"capsules/{case}.json","capsules",2*MIB)
            self.reserve(f"capsules/{case}.json.lock","capsules",0)
            self.capsules.add(case)
        self.log_fd=os.open(root/"worker-logs.bin",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    def log(self,raw):
        if self.log_bytes+len(raw)>LOG_CAP:
            self.halted=True
            raise CapacityError("Aggregate worker log prefix allocation exhausted")
        view=memoryview(raw)
        while view:
            n=os.write(self.log_fd,view)
            if n<=0: raise OSError("Short log write")
            view=view[n:]
        self.log_bytes+=len(raw)
    def finish_api_write(self,case_id):
        # Native CapsuleStore uses its own mkstemp basename; allow only the two
        # capsule/lock pairs after each completed stage, never stranded temps.
        allowed={f"{c}.json" for c in self.capsules}|{f"{c}.json.lock" for c in self.capsules}
        if any(p.name not in allowed for p in (self.root/"capsules").iterdir()):
            self.halted=True
            raise IntegrityError("Unexpected/stranded native capsule artifact")
        super().finish_api_write(case_id)
    def close(self):
        if self.log_fd is not None:
            os.fsync(self.log_fd)
            os.close(self.log_fd)
            self.log_fd=None


class FixtureLedger(Ledger):
    """Independent sequence authority with six permanent transition slots."""
    def __init__(self,path):
        self.path=Path(path); self.records=[]; self.broken=False; self.expected_bytes=0
        self.uncertain_workers=set()
        self.fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.append("registered",{"profile":dict(INVARIANT_PROFILE),"call_ceilings":CALL_CAPS,
            "worker_slots":SLOTS,"data_kind":"synthetic_fixture","science_result":None})
    def append(self,kind,payload):
        # Reserve sufficient framing before Ledger appends/fsyncs. Prefix is
        # retained if later writes fail; it can never resume or refund counts.
        if self.expected_bytes+len(canonical(payload))+1024>MIB:
            self.broken=True
            raise CapacityError("Ledger prefix allocation exhausted")
        return super().append(kind,payload)
    def claim_worker(self,worker_id):
        if worker_id not in SLOTS or any(p["worker_id"]==worker_id for p in self._events("worker_admitted")):
            raise IntegrityError("Unknown/repeated fixture cold worker")
        if self._events("terminal_reconciliation_started") and worker_id!="reporter":
            raise IntegrityError("Terminal reconciliation forbids later API/setup workers")
        allowance=({c:int(c=="transition")*2 for c in CALL_CAPS} if worker_id=="setup"
                   else {c:0 for c in CALL_CAPS} if worker_id=="reporter"
                   else worker_allowances(worker_id))
        for category,ceiling in CALL_CAPS.items():
            reserved=sum(p["allowances"][category] for p in self._events("worker_admitted"))
            if reserved+allowance[category]>ceiling:
                raise CapacityError("Frozen fixture call reservation exhausted: "+category)
        self.append("worker_admitted",{"worker_id":worker_id,"allowances":allowance})
        if worker_id=="terminal_reconciliation":
            self.append("terminal_reconciliation_started",{"worker_id":worker_id})
    def charge(self,category,slot,*,recomputation_of=None):
        valid=(category=="setup" and slot in ("setup.north1","setup.north2") or
               category=="owned" and slot in tuple(f"owned.{c}.stage{s}" for c in INVARIANT_PROFILE["case_ids"] for s in (1,2)))
        if not valid or recomputation_of is not None or any(p["slot"]==slot for p in self._events("charged")):
            raise IntegrityError("Unknown/repeated transition slot; retries disabled")
        if len(self._events("charged"))>=6: raise CapacityError("Six-entry transition budget exhausted")
        ticket="invocation"+str(len(self._events("charged"))+1)
        self.append("charged",{"ticket":ticket,"category":category,"slot":slot,"recomputation_of":None})
        return ticket
    def record_actual_call(self,worker_id,call_id,category,*,exited=False):
        if category not in CALL_CAPS or type(call_id) is not int or call_id<1:
            raise IntegrityError("Unknown actual function entry")
        workers=[p for p in self._events("worker_admitted") if p["worker_id"]==worker_id]
        if len(workers)!=1: raise IntegrityError("Unadmitted function entry")
        name="actual_call_exited" if exited else "actual_call_entered"
        entries=self._events("actual_call_entered")
        if any(p["worker_id"]==worker_id and p["call_id"]==call_id for p in self._events(name)):
            raise IntegrityError("Repeated call observation")
        if exited and not any(p["worker_id"]==worker_id and p["call_id"]==call_id and p["category"]==category for p in entries):
            raise IntegrityError("Unmatched call return")
        overrun=not exited and (sum(p["category"]==category for p in entries)>=CALL_CAPS[category] or
            sum(p["worker_id"]==worker_id and p["category"]==category for p in entries)>=workers[0]["allowances"][category])
        self.append(name,{"worker_id":worker_id,"call_id":call_id,"category":category,"overrun":overrun})
        if overrun:
            self.append("integrity_failure",{"reason":"Actual frame entry exceeded frozen reservation","worker_id":worker_id,"category":category})
            raise IntegrityError("Actual overrun preserved; continuation refused")
    def counters(self):
        entries=self._events("actual_call_entered")
        count={c:sum(p["category"]==c for p in entries) for c in CALL_CAPS}
        admitted={p["worker_id"]:p for p in self._events("worker_admitted")}
        completed={p["worker_id"] for p in self._events("worker_complete")}
        uncertain=self.uncertain_workers | (set(admitted)-completed)
        unknown={c:self.broken or any(admitted[w]["allowances"][c]>0 for w in uncertain) for c in CALL_CAPS}
        maxima={c:sum(p["allowances"][c] for p in admitted.values()) for c in CALL_CAPS}
        return {"actual_entries":count,"charged_transitions":len(self._events("charged")),
            "durably_consumed":len(self._events("durably_consumed")),"evidence_loss":self.broken or bool(uncertain),
            "actual_entries_are_lower_bounds":self.broken or bool(uncertain),
            "actual_entries_exact":{c:None if unknown[c] else count[c] for c in CALL_CAPS},
            "uncertain_workers":sorted(uncertain),"reservation_upper_bounds":maxima,
            "scientific_transition_invocations":0,"scientific_denominators":0,"science_result":None}



class FixtureReferences:
    def __init__(self,ledger,files,frames,rows):
        self.ledger,self.files=ledger,files
        self.frames,self.rows=deepcopy(frames),deepcopy(rows)
        self.reference=None; self.cases=set(); self.native_ids=set()
    def bind(self,case_id,frames,cohort,identity):
        if case_id not in INVARIANT_PROFILE["case_ids"] or case_id in self.cases:
            raise IntegrityError("Unknown/repeated fixture reference")
        if len(frames)!=3 or canonical(frames)!=canonical(self.frames):
            raise IntegrityError("Fixture must bind complete exact three-frame D")
        normalized=deepcopy(self.rows)
        for row in normalized:
            for entity in row["before_context"]["visible_ids"]:
                row["before_context"].setdefault("entity."+entity+".state",None)
        if cohort.get("discovery_events")!=[{"event_id":r["event_id"],"digest":digest(r)} for r in normalized]:
            raise IntegrityError("Normalized discovery references differ")
        if identity.get("discovery_count")!=2 or not identity.get("run_id") or identity["run_id"] in self.native_ids:
            raise IntegrityError("Native identity discovery/run binding differs")
        material={"frames":frames,"projected_rows":self.rows,"cohort":cohort}
        raw=canonical(material)
        if len(raw)>2*MIB: raise CapacityError("Fixture D/cohort reference allocation exceeded")
        if self.reference is None:
            if case_id!=INVARIANT_PROFILE["case_ids"][0]: raise IntegrityError("R must establish reference first")
            self.files.put_new("D-cohort-reference.json","references",raw)
            self.reference=raw
        elif raw!=self.reference: raise IntegrityError("Full raw D/cohort bytes differ between arms")
        proof={"case_id":case_id,"D_sha256":digest(frames),"cohort_sha256":digest(cohort),
               "reference_bytes_sha256":digest(material)}
        proof["durable_ack_sha256"]=self.ledger.append("cohort_reference_bound",dict(proof,native_identity=identity))
        self.cases.add(case_id); self.native_ids.add(identity["run_id"])
        return proof


def _boottime_ns():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


def _child_setup(creator_pid,deadline_ns,affinity,libc):
    # creator_pid is captured BEFORE fork. Checking a freshly-read parent here
    # would bless reparenting if the creator died before this function began.
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0 or os.getppid()!=creator_pid:
        os._exit(92)
    resource.setrlimit(resource.RLIMIT_AS,(384*MIB,384*MIB))
    resource.setrlimit(resource.RLIMIT_CPU,(850,850))
    resource.setrlimit(resource.RLIMIT_FSIZE,(2*MIB,2*MIB))
    resource.setrlimit(resource.RLIMIT_NPROC,(1,1))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    if os.sched_getaffinity(0)!=affinity or len(affinity)!=1 or _boottime_ns()>=deadline_ns:
        os._exit(92)


class SequentialNativeTransport:
    """Same finite pipe/process core is available to the disabled science driver.

    Source-captured worker bytes, configuration and deadline must originate from
    the native launcher's compiler-bound manifest. Runtime JSON cannot choose a
    profile, source digest, executable, world, command or cap.
    """
    def __init__(self,files,ledger,worker_bytes,worker_filename,frozen_config,deadline_ns,*,emit=None,authored_fixture=False):
        self.files,self.ledger=files,ledger
        self.worker_bytes,self.worker_filename=worker_bytes,worker_filename
        self.config=deepcopy(frozen_config); self.deadline_ns=deadline_ns
        self.native_events=emit is not None
        self.emit=emit or (lambda *args:None)
        self.stdout_bytes=0
        self.active=None; self.halted=False; self.references=None; self.bound_identities={}
        self.authored_fixture_only=authored_fixture
        self.libc=ctypes.CDLL(None,use_errno=True)
        self.libc.prctl.argtypes=[ctypes.c_int,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong]
        self.libc.prctl.restype=ctypes.c_int
    def scientific_stage(self,*args,**kwargs):
        raise IntegrityError("Scientific transport remains disabled pending separate exact-source admission")
    def _dispatch(self,worker_id,request,*,tickets=(),precondition=None):
        if self.active is not None or self.halted or self.files.halted:
            raise IntegrityError("Only one cold child; no continuation after failure")
        if len(os.sched_getaffinity(0))!=1 or len(list(Path('/proc/self/task').iterdir()))!=1:
            raise IntegrityError("Singleton inherited CPU/thread required")
        if _boottime_ns()>=self.deadline_ns: raise CapacityError("Native absolute lifetime expired")
        if resource.getrlimit(resource.RLIMIT_FSIZE)[1] not in (resource.RLIM_INFINITY,) and resource.getrlimit(resource.RLIMIT_FSIZE)[1]<2*MIB:
            raise IntegrityError("Native outer FSIZE profile does not admit two-MiB capsule")
        self.ledger.claim_worker(worker_id)
        packet={"request":request,"configuration":self.config,"precondition":precondition}
        raw=canonical(packet)+b"\n"
        if len(raw)>PIPE_CAP: raise CapacityError("Cold-worker request exceeds envelope")
        # The source string is captured/verified, never imported from its path.
        source="exec(compile("+repr(self.worker_bytes)+","+repr(self.worker_filename)+",'exec'))"
        creator_pid=os.getpid(); affinity=os.sched_getaffinity(0)
        proc=None; selector=selectors.DefaultSelector(); result=None; ticket_map={}; entered=0; source_receipts=0
        try:
            proc=subprocess.Popen([sys.executable,"-I","-S","-B","-c",source],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={"LANG":"C","LC_ALL":"C"},
                close_fds=True,pass_fds=(3,) if self.native_events else (),start_new_session=False,
                preexec_fn=lambda:_child_setup(creator_pid,self.deadline_ns,affinity,self.libc))
            self.active=proc; self.emit(5,proc.pid,0)
            proc.stdin.write(raw); proc.stdin.flush()
            for stream,label in ((proc.stdout,"stdout"),(proc.stderr,"stderr")):
                os.set_blocking(stream.fileno(),False); selector.register(stream,selectors.EVENT_READ,label)
            pending=bytearray(); observed_bytes=0
            while selector.get_map():
                remaining=(self.deadline_ns-_boottime_ns())/1e9
                if remaining<=0: raise CapacityError("Absolute native lifetime expired")
                events=selector.select(min(remaining,1))
                for key,_ in events:
                    block=os.read(key.fileobj.fileno(),65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data=="stderr":
                        self.files.log(block); continue
                    observed_bytes+=len(block)
                    self.stdout_bytes+=len(block)
                    if self.stdout_bytes>64*MIB: raise CapacityError("Whole-run protocol prefix cap exceeded")
                    # Every worker has a finite protocol prefix, including all
                    # entry/return events, one cohort and one capsule/result.
                    if observed_bytes>12*MIB: raise CapacityError("Worker stdout aggregate prefix cap exceeded")
                    pending.extend(block)
                    while b"\n" in pending:
                        line,_,tail=pending.partition(b"\n"); pending=bytearray(tail)
                        if len(line)>PIPE_CAP: raise CapacityError("Worker frame cap exceeded")
                        message=json.loads(line)
                        if canonical(message)!=line or not isinstance(message,dict): raise IntegrityError("Noncanonical worker record")
                        if result is not None: raise IntegrityError("Worker continued after final result")
                        event=message.get("event"); reply={"accepted":True,"request_sha256":digest(message)}
                        if event in ("actual_call_entered","actual_call_exited"):
                            category=message["category"]; exited=event=="actual_call_exited"
                            if not self.authored_fixture_only and source_receipts!=1:
                                raise IntegrityError("Actual call preceded frozen source/runtime receipt")
                            self.ledger.record_actual_call(worker_id,message["call_id"],category,exited=exited)
                            if category=="transition":
                                if not exited:
                                    if entered>=len(tickets): raise IntegrityError("Uncharged transition entry persisted")
                                    ticket_map[message["call_id"]]=tickets[entered]; entered+=1
                                    self.ledger.advance(ticket_map[message["call_id"]],"started")
                                elif message.get("computed_result_sha256") is not None:
                                    self.ledger.advance(ticket_map[message["call_id"]],"computed",result_hash=message["computed_result_sha256"])
                        elif event=="cohort_bind":
                            if self.references is None: raise IntegrityError("Reference handshake before frozen setup")
                            if message["case_id"]!=request.get("case_id"): raise IntegrityError("Worker bound another case")
                            identity=message["native_identity"]
                            if (identity.get("path")!=request["path"] or identity.get("research_dir")!=request["research_dir"]
                                or identity.get("evidence_mode")!={"R":"retain_first","W":"withhold_first"}[request["arm"]]
                                or identity.get("code_manifest")!=self.config["api_manifest"]
                                or identity.get("runtime_manifest")!=self.config["api_runtime_manifest"]):
                                raise IntegrityError("Initial native case/mode/source/runtime identity differs")
                            for source_key,source_path in request["source_paths"].items():
                                raw_source=read_regular(source_path,MIB); info=os.stat(source_path)
                                observed={"path":source_path,"sha256":hashlib.sha256(raw_source).hexdigest(),
                                    "device":info.st_dev,"inode":info.st_ino,"bytes":len(raw_source)}
                                if identity["source_inputs"].get(source_key)!=observed:
                                    raise IntegrityError("Initial native source-file identity differs")
                            self.bound_identities[request["case_id"]]=digest(identity)
                            reply["cohort_binding"]=self.references.bind(message["case_id"],message["D_frames"],message["cohort"],message["native_identity"])
                        elif event=="source_receipt":
                            if (message.get("api_manifest_sha256")!=digest(self.config.get("api_manifest",{}))
                                or message.get("study_manifest_sha256")!=digest(self.config.get("study_manifest",{}))
                                or message.get("runtime_manifest")!=self.config.get("api_runtime_manifest")
                                or message.get("python_sha256")!=self.config.get("python_sha256")
                                or message.get("cold_flags")!={"isolated":1,"no_site":1,"no_bytecode":True}):
                                raise IntegrityError("Cold source/runtime receipt differs from compiler-bound manifest")
                            source_receipts+=1
                            if source_receipts!=1: raise IntegrityError("Repeated cold source receipt")
                            self.ledger.append("source_receipt",dict(message,worker_id=worker_id))
                        elif event=="stage_complete":
                            if not self.authored_fixture_only and request.get("phase")!="report_saved" and source_receipts!=1:
                                raise IntegrityError("Result lacks exact cold source/runtime receipt")
                            result=message["result"]
                            if message.get("result_sha256")!=digest(result): raise IntegrityError("Child final result digest differs")
                        else: raise IntegrityError("Unknown worker event")
                        answer=canonical(reply)+b"\n"
                        proc.stdin.write(answer); proc.stdin.flush()
                    if len(pending)>PIPE_CAP: raise CapacityError("Worker unterminated frame exceeds cap")
            if pending: raise IntegrityError("Torn final worker frame")
            code=proc.wait(timeout=max(.001,(self.deadline_ns-_boottime_ns())/1e9))
            self.emit(3,0,code)
            if code or result is None: raise IntegrityError("Cold worker failed or omitted complete result")
            entries=[p for p in self.ledger._events("actual_call_entered") if p["worker_id"]==worker_id]
            exits=[p for p in self.ledger._events("actual_call_exited") if p["worker_id"]==worker_id]
            if len(entries)!=len(exits): raise IntegrityError("Cold worker lost function-return evidence")
            self.ledger.append("worker_complete",{"worker_id":worker_id,"result_sha256":digest(result)})
            return result
        except BaseException:
            self.halted=True
            self.ledger.uncertain_workers.add(worker_id)
            try:
                self.ledger.append("worker_uncertain",{"worker_id":worker_id,"actual_counts":"lower_bounds_only"})
            except BaseException:
                self.ledger.broken=True
            if proc is not None and proc.poll() is None: proc.kill()
            if proc is not None: proc.wait()
            raise
        finally:
            selector.close()
            if proc is not None:
                for stream in (proc.stdin,proc.stdout,proc.stderr): stream.close()
            self.active=None
