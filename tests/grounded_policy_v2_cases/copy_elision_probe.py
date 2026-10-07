"""Differential tests on ordinary JSON and saved authored engineering inputs."""
import sys
from pathlib import Path
API = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(API / "experiments"))
import grounded_policy_v2
from grounded_policy_v2 import contracts as c, executive as e, primitives as p, store, views, policy
import base64
from copy import deepcopy
import json
import resource

resource.setrlimit(resource.RLIMIT_AS, (384*1048576,)*2)
resource.setrlimit(resource.RLIMIT_CPU, (60,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE, (2*1048576,)*2)
ROOT = Path(sys.argv[2]).resolve()
ROOT.mkdir()
RECIPE = json.loads(Path(sys.argv[3]).read_bytes())
RESULTS = {}
COUNTS = {}
WORLD_FILE = str(API / "experiments/open_object_world_challenge.py")
POLICY_FILE = str(API / "experiments/grounded_policy_v2/policy.py")
EXEC_FILE = str(API / "experiments/grounded_policy_v2/executive.py")


def guard(frame, event, arg):
    if event != "call":
        return
    filename, name = frame.f_code.co_filename, frame.f_code.co_name
    if filename == WORLD_FILE and name == "transition":
        COUNTS["forbidden"] = COUNTS.get("forbidden",0) + 1
        raise AssertionError("No transitions in copy proofs")
    if filename == POLICY_FILE and name in ("evaluate", "build_cohort"):
        COUNTS["forbidden"] = COUNTS.get("forbidden",0) + 1
        raise AssertionError("No fixture producer or selector in copy proofs")
    if filename == EXEC_FILE:
        if name in ("create", "select_next", "execute", "interpret", "cancel"):
            COUNTS["forbidden"] = COUNTS.get("forbidden",0) + 1
            raise AssertionError("No API action methods in copy proofs")
        if name == "validate_capsule":
            COUNTS[name] = COUNTS.get(name, 0) + 1
            assert COUNTS[name] <= 64


sys.setprofile(guard)


def reference_encoded(value):
    return p.canonical(p.seal(value)) + b"\n"


def outcome(fn, value):
    before = repr(value)
    try:
        result = fn(value)
        answer = {"bytes":base64.b64encode(result).decode()} if isinstance(result, bytes) else {"ok":True}
    except Exception as error:
        answer = {"error":type(error).__name__, "message":str(error)}
    assert repr(value) == before, "Checksum function mutated its input"
    return answer


primitive_rows = []
for value in ({}, {"seal":"stale"}, {"a":[None,True,3,2.5,{"z":"é"}],"seal":None},
              {"nested":{"items":[{"x":1},{"x":2}]}}, {"seal":[1],"payload":{"x":2}}):
    before = deepcopy(value)
    assert p.encoded(value) == reference_encoded(value)
    assert value == before
    sealed = p.seal(value)
    p.verify_seal(sealed)
    assert p.encoded(sealed) == p.encoded(value)
    sealed["added"] = ["tampered"]
    primitive_rows.append({"encoded":outcome(p.encoded,value),"tampered":outcome(p.verify_seal,sealed)})
for value in (None, True, 0, 1.5, "text", [], [["x",1]], ("x",),
              {"payload":float("nan")}, {"seal":None,"payload":float("nan")},
              {"seal":[],"payload":float("inf")}, {"seal":0}, {"payload":{1,2}}):
    primitive_rows.append({"encoded":outcome(p.encoded,value),"verify":outcome(p.verify_seal,value)})
shared = {"items":[{"x":1}]}
value = {"left":shared,"right":shared}
sealed = p.seal(value)
assert sealed["left"] is sealed["right"] and sealed["left"] is not shared
sealed["left"]["items"][0]["x"] = 99
assert value["left"]["items"][0]["x"] == 1
blob = p.encoded(value)
value["left"]["items"].append({"x":2})
assert json.loads(blob)["left"]["items"] == [{"x":1}]
RESULTS["primitives"] = primitive_rows


def empty_cohort():
    value = dict(schema_version="grounded-cohort-v2",code_version=policy.VERSION,discovery_events=[],actions=[
        dict(action=action,status="insufficient_explanatory_diversity",nonzero_delta=None,observed_deltas=[],
             conditional_count=0,retained_conditional_count=0,models=[]) for action in policy.ACTIONS])
    value["cohort_digest"] = p.digest(value)
    return value


def fixture(name, mode="retain_first", *, empty=False, limits=None):
    folder = ROOT / name
    folder.mkdir()
    research = folder / "research"
    research.mkdir()
    world = deepcopy(RECIPE["source_world"])
    frames = deepcopy(RECIPE["frames"])
    if empty:
        world.update(cycle=0,history=[],position=deepcopy(frames[0]["observation"]["position"]))
        frames = frames[:1]
    copies = dict(ora={"nested":{"values":[1,2]}},world=world,observations=frames)
    sources = {}
    for key,value in copies.items():
        path=folder/(key+".json")
        path.write_bytes(p.canonical(value))
        sources[key],_ = e._source(path)
    capsule = store.CapsuleStore(research/"authored.json",research,enabled=True)
    with capsule._locked(creating=True) as (_,filesystem):
        identity=dict(run_id="copy-proof-"+name,path=str(capsule.path),research_dir=str(research),filesystem=filesystem,
            source_inputs=sources,code_manifest=c.code_manifest(),runtime_manifest=c.runtime_manifest(),
            profile=limits or c.profile(),selection_backend=c.BACKEND,science_configuration=c.science_configuration(),
            evidence_mode=mode,discovery_count=0 if empty else 2,
            adapter=dict(source_id=e.SOURCE_ID,descriptor=e.SOURCE_DESCRIPTOR_HASH,actor="agent",world_id=p.digest(world),
                world_version=e.WORLD_VERSION,grammar="challenge-candidate-commands-v1"),
            initial_ora_hash=p.digest(copies["ora"]),initial_world_hash=p.digest(world),initial_frames_hash=p.digest(frames))
    state=dict(version=c.VERSION,identity=identity,identity_hash=p.digest(identity),revision=0,frames=frames,
        cohort=empty_cohort() if empty else deepcopy(RECIPE["cohort"]),ora=deepcopy(copies["ora"]),world=world,
        decisions=[],attempts=[],outcomes=[],beliefs=[],events=[],reserve=0,seal=None)
    return capsule,state


def stage(state, ordinal, body):
    _,view,mask,anchor=e._view(state,ordinal,state["world"],state["outcomes"],state["beliefs"],state["decisions"])
    before=p.canonical(state)
    staged,decision=e._stage_selection(state,ordinal,body,view,mask,anchor)
    assert p.canonical(state)==before
    return staged,decision


def check(capsule,state):
    before=p.canonical(state)
    assert p.encoded(state)==reference_encoded(state)
    capsule.path.write_bytes(p.encoded(state))
    checked=capsule.read()
    assert p.canonical(checked)+b"\n"==reference_encoded(state)
    assert p.canonical(state)==before
    return checked


def finish_owned(state,ordinal):
    decision=state["decisions"][-1];attempt=state["attempts"][-1]
    result=e._signed(dict(id=e._id(state,"outcome",ordinal),revision=state["revision"]+1,
        attempt_id=attempt["id"],decision_id=decision["id"],owner_id=decision["owner_id"],experiment_id=decision["experiment_id"],
        selection_hash=decision["hash"],case_hash=decision["case_hash"],command=deepcopy(decision["command"]),
        before_observation=RECIPE["observations"][ordinal+1],after_observation=RECIPE["observations"][ordinal+2],
        receipt=RECIPE["receipts"][ordinal+1],world_before_hash=p.digest(state["world"]),
        world_after_hash=p.digest(RECIPE["owned_worlds"][ordinal-1])))
    state["world"]=deepcopy(RECIPE["owned_worlds"][ordinal-1]);state["outcomes"].append(result)
    attempt.update(status="committed",outcome_id=result["id"]);state["reserve"]=c.INTERPRETATION_RESERVE
    e._event(state,"execute",result["id"],result["hash"])


def interpret_authored(state):
    decision=state["decisions"][-1];result=state["outcomes"][-1];attempt=state["attempts"][-1]
    belief=e._interpretation(state,decision,result,state["beliefs"][-1] if state["beliefs"] else None,state["revision"]+1)
    state["beliefs"].append(belief);attempt.update(status="interpreted",belief_id=belief["id"]);state["reserve"]=0
    e._event(state,"interpret",belief["id"],belief["hash"])


saved={}
for mode in ("retain_first","withhold_first"):
    capsule,state=fixture(mode,mode)
    rows=[check(capsule,state)]
    for ordinal in (1,2):
        body=RECIPE["retained_second_body"] if ordinal==2 and mode=="retain_first" else RECIPE["first_body"]
        state,_=stage(state,ordinal,body);rows.append(check(capsule,state))
        finish_owned(state,ordinal);rows.append(check(capsule,state))
        interpret_authored(state);rows.append(check(capsule,state))
    saved[mode]=rows
    RESULTS[mode]=[{"revision":s["revision"],"world":s["world"],"reserve":s["reserve"],
        "bodies":[d["body"] for d in s["decisions"]],"status":[a["status"] for a in s["attempts"]]} for s in rows]

# Returned staged data retains the original complete deep isolation contract.
_,original=fixture("isolation")
before=deepcopy(original)
staged,_=stage(original,1,RECIPE["first_body"])
staged["identity"]["profile"]["max_actions"]=0
staged["frames"][0]["observation"]["position"][0]=99
staged["cohort"]["actions"][0]["models"][0]["structure"]["kind"]="changed"
staged["ora"]["nested"]["values"].append(3)
staged["world"]["history"].clear()
assert original==before
RESULTS["stage_isolation"]=True

# Independently authored empty-D/null menu, accepted by the complete checker.
capsule,state=fixture("policy-null",empty=True)
_,view,_,_=e._view(state,1,state["world"],[],[],[])
context=deepcopy(view["context"])
for entity in context["visible_ids"]:
    context.setdefault("entity."+entity+".state",None)
reason="insufficient_explanatory_diversity"
menu=[dict(action=a,command={"action":a},cohort_status=reason,forecastable=False,forecast_reason=reason,
    inquiry_eligible=False,eligibility_reason=reason,selection_eligible=False,selection_reason=reason,
    concrete_predictions=[],unavailable_models=[],evidence_event_ids=[],posterior=[],forecast=None,
    unresolved_mass=None,predictive_entropy_bits=None,expected_model_entropy_bits=None,score_bits=None) for a in policy.ACTIONS]
body=dict(schema_version="grounded-policy-decision-v2",code_version=policy.VERSION,
    cohort_digest=state["cohort"]["cohort_digest"],context=context,context_digest=p.digest(context),menu=menu,selected_action=None)
for ordinal in (1,2):
    state,d=stage(state,ordinal,body);assert d["status"]=="policy_null";check(capsule,state)
assert not state["attempts"]
RESULTS["policy_null"]=True

capsule,state=fixture("action-capacity",limits=c.profile(max_actions=0))
state,d=stage(state,1,RECIPE["first_body"]);assert d["status"]=="capacity_null"
check(capsule,state);RESULTS["action_capacity_null"]=True

# Independent old-algorithm encoding computes the exact selected-byte boundary.
limits=[]
for label,offset in (("byte-exact",0),("byte-under",-1)):
    capsule,base=fixture(label)
    _,view,mask,anchor=e._view(base,1,base["world"],[],[],[])
    cap=2*1048576
    for _ in range(8):
        trial=deepcopy(base);trial["identity"]["profile"]["max_bytes"]=cap;trial["identity_hash"]=p.digest(trial["identity"])
        d=e._decision(trial,1,RECIPE["first_body"],view,mask,anchor,1,"selected")
        trial["decisions"].append(d);trial["attempts"].append(e._attempt(trial,d));trial["reserve"]=c.COMPLETION_RESERVE
        e._event(trial,"select",d["id"],d["hash"])
        needed=len(reference_encoded(trial))+trial["reserve"]
        if needed==cap:break
        cap=needed
    else:raise AssertionError("Byte boundary did not converge")
    base["identity"]["profile"]["max_bytes"]=cap+offset;base["identity_hash"]=p.digest(base["identity"])
    original=deepcopy(base);state,d=stage(base,1,RECIPE["first_body"])
    assert base==original and d["status"]==("selected" if offset==0 else "capacity_null")
    assert len(reference_encoded(state))+state["reserve"]<=cap+offset
    check(capsule,state);limits.append({"offset":offset,"status":d["status"]})
RESULTS["byte_capacity"]=limits

capsule,state=fixture("cancelled")
state,_=stage(state,1,RECIPE["first_body"])
attempt=state["attempts"][0];attempt["status"]="cancelled";state["reserve"]=0
e._event(state,"cancel",attempt["id"],p.digest(attempt));check(capsule,state)
RESULTS["cancelled"]=True

# Resealed tampering reaches semantic checks rather than merely the outer seal.
bad_rows=[]
for kind in ("body","owner","world","belief","reserve","tuple-position","bad-seal"):
    state=deepcopy(saved["retain_first"][6])
    if kind=="body":state["decisions"][0]["body"]["selected_action"]="east"
    elif kind=="owner":state["attempts"][0]["owner_id"]="foreign"
    elif kind=="world":state["world"]["position"]=[-2,0]
    elif kind=="belief":state["beliefs"][0]["evaluations"][0]["verdict"]="invented"
    elif kind=="reserve":state["reserve"]=1
    elif kind=="tuple-position":state["frames"][0]["observation"]["position"]=tuple(state["frames"][0]["observation"]["position"])
    state=p.seal(state)
    if kind=="bad-seal":state["seal"]="0"*64
    result=outcome(e.validate_capsule,state)
    assert "error" in result
    bad_rows.append({"kind":kind,**result})
assert e.validate_capsule.__kwdefaults__=={"verify_checksum":True}
RESULTS["tampering"]=bad_rows
sys.setprofile(None)
assert COUNTS == {"validate_capsule":27}, "Unexpected or forbidden calls cannot be hidden by negative cases"
print(json.dumps({"results":RESULTS,"counts":COUNTS,"transition_calls":0,"producer_calls":0,"selector_calls":0},sort_keys=True))
