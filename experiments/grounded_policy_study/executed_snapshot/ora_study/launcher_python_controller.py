"""Compiler-embedded, zero-world-call Python controller integration fixture.

No files are created by this script. It loads verified captured study source,
exercises the finite all-null schedule with an explicitly in-memory fixture
ledger, and starts only the compiler-bound native arithmetic child. No API,
policy, scientific observation, simulator or actual source corpus is imported.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys

package_root=Path(os.environ["ORA_LAUNCHER_PACKAGE_ROOT"])
manifest_path=Path(os.environ["ORA_LAUNCHER_MANIFEST_PATH"])
try:
    manifest_raw=manifest_path.read_bytes()
except OSError:
    raise SystemExit(91)
if len(manifest_raw)>65536 or hashlib.sha256(manifest_raw).hexdigest()!=os.environ["ORA_LAUNCHER_MANIFEST_SHA256"]:
    raise SystemExit(91)
manifest=json.loads(manifest_raw)
bootstrap_path=package_root/"source_bootstrap.py"
bootstrap_raw=bootstrap_path.read_bytes()
if hashlib.sha256(bootstrap_raw).hexdigest()!=manifest["source_bootstrap.py"]:
    raise SystemExit(91)
bootstrap={"__name__":"captured_launcher_bootstrap","__file__":str(bootstrap_path)}
exec(compile(bootstrap_raw,str(bootstrap_path),"exec"),bootstrap)
try:
    finder=bootstrap["PinnedSources"](package_root,manifest)
    finder.install()
except (RuntimeError,OSError):
    raise SystemExit(91)
from ora_study.driver import FiniteDriver
from ora_study.protocol import MOVEMENTS,digest
from ora_study.ledger import IntegrityError

if resource.getrlimit(resource.RLIMIT_AS)!=(96*1048576,384*1048576):
    raise RuntimeError("Unexpected inherited controller address space")
if len(os.sched_getaffinity(0))!=1 or len(list(Path("/proc/self/task").iterdir()))!=1:
    raise RuntimeError("Controller must remain one thread on one allowed CPU")
if any(name.startswith(("grounded_policy_v2","agenttest","open_object_world_challenge")) for name in sys.modules):
    raise RuntimeError("Authored integration must not import scientific modules")

class MemoryFixtureLedger:
    def __init__(self):
        self.records=[]
        self.workers=set()
        self.decisions=set()
        self.nulls=0
        self.append("authored_fixture_registered",{})
    def append(self,kind,payload):
        row={"sequence":len(self.records),"kind":kind,"payload":payload}
        row["hash"]=digest(row)
        self.records.append(row)
        return row["hash"]
    def claim_worker(self,name):
        if name in self.workers:
            raise IntegrityError("Repeated fixture worker")
        self.workers.add(name)
        self.append("fixture_worker",{"name":name})
    def decision_start(self,name):
        if name in self.decisions:
            raise IntegrityError("Repeated fixture decision")
        self.decisions.add(name)
    def decision_commit(self,name,*,receipt_hash,is_null):
        if not is_null:
            raise IntegrityError("Authored null fixture cannot own an action")
        self.nulls+=1
        self.append("fixture_null",{"name":name,"hash":receipt_hash})
class NullFixtureTransport:
    authored_fixture_only=True
    def __init__(self):
        self.states={}
        self.saved=0
    def neutral(self,layout):
        pass  # Schedule label only; no neutral data or transition is generated.
    def prepare_pair(self,anchor):
        return {"logical_inputs_sha256":digest({"authored":anchor["anchor_id"]})}
    def api_stage(self,anchor,arm,phase,stage):
        key=anchor["cases"][arm]
        if phase=="create_select":
            self.states[key]={"decisions":[],"outcomes":[],"world":{"authored_scalar":5}}
        if phase not in ("create_select","select"):
            raise IntegrityError("No API action in fixture")
        self.states[key]["decisions"].append({"ordinal":stage,"status":"policy_null","hash":digest({"key":key,"stage":stage})})
        return self.states[key]
    def first_decision_semantics(self,state):
        return {"authored_null":True}
    def first_lifecycle_semantics(self,state):
        return {"authored_null":True,"complete":1}
    def decision_semantics(self,state,ordinal):
        return {"forecasts":{a:{"status":"unavailable"} for a in MOVEMENTS},"authored_null":True}
    def freeze_forecast_set(self,*args,**kwargs):
        pass
    def probes(self,*args):
        return {a:{"authored_label":a} for a in MOVEMENTS}
    def save_anchor(self,*args):
        self.saved+=1
    def seal_saved_records(self,head):
        if self.saved!=32:
            raise IntegrityError("Authored schedule incomplete")
        return {"authored_seal":head}
    def report_saved(self,seal):
        return {"fixture_only":True,"science_result":None,"science_calls":0}

ledger=MemoryFixtureLedger()
report=FiniteDriver(NullFixtureTransport(),ledger).run_authored_fixture()
if ledger.nulls!=128 or report["candidate_report"]["science_calls"]!=0:
    raise RuntimeError("Authored schedule check failed")

def emit(phase,value=0,code=0):
    limits_as=resource.getrlimit(resource.RLIMIT_AS)
    limits_cpu=resource.getrlimit(resource.RLIMIT_CPU)
    nproc=resource.getrlimit(resource.RLIMIT_NPROC)[0]
    usage=resource.getrusage(resource.RUSAGE_SELF)
    row={"phase":phase,"pid":os.getpid(),"value":value,"code":code,
         "as_soft":limits_as[0],"as_hard":limits_as[1],"cpu_soft":limits_cpu[0],"cpu_hard":limits_cpu[1],
         "nproc_soft":18446744073709551615 if nproc==resource.RLIM_INFINITY else nproc,
         "affinity_cpu":next(iter(os.sched_getaffinity(0))),"user_ns":int(usage.ru_utime*1e9),"system_ns":int(usage.ru_stime*1e9)}
    data=(json.dumps(row,separators=(",",":"))+"\n").encode()
    if len(data)>1024 or os.write(3,data)!=len(data):
        raise RuntimeError("Bounded native event write failed")
emit(9,value=ledger.nulls)
child=subprocess.Popen([os.environ["ORA_LAUNCHER_CHILD_EXE"],"--authored-child",str(os.getpid())],
    stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    env={"LANG":"C","LC_ALL":"C"},pass_fds=(3,),close_fds=True)
emit(5,value=child.pid)
stdout,stderr=child.communicate(timeout=5)
if len(stdout)>1024 or len(stderr)>1024:
    raise RuntimeError("Fixed native child violated stream contract")
emit(3,code=child.returncode)
if child.returncode:
    raise SystemExit(child.returncode)
print(json.dumps({"authored_fixture":True,"null_decisions":128,"actual_api_calls":0,"actual_world_calls":0,"captured_source_modules":len(finder.modules)},separators=(",",":")),flush=True)
