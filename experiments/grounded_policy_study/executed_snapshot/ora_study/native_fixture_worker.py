"""Fresh -I -S -B cold worker, held source-disabled for exact-byte review.

No environment, JSON, caller boolean or command-line option grants admission.
The test suite executes separate authored fake worker text, never this API path.
"""
REAL_FIXTURE_ADMISSION_REVIEWED = True
SCIENTIFIC_ADMISSION_REVIEWED = False


def _read_regular(path, maximum):
    import os
    import stat
    from pathlib import Path
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise RuntimeError("Noncanonical source ancestry")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>maximum:
            raise RuntimeError("Unbounded/aliased source")
        raw=bytearray()
        while True:
            part=os.read(fd,min(65536,maximum+1-len(raw)))
            if not part: break
            raw.extend(part)
            if len(raw)>maximum: raise RuntimeError("Bounded source exceeded")
        if os.fstat(fd).st_size!=len(raw): raise RuntimeError("Source changed while captured")
        return bytes(raw)
    finally:
        os.close(fd)


def _study(config):
    import hashlib
    from pathlib import Path
    root=Path(config["package_root"])
    payload=_read_regular(root/"source_bootstrap.py",1048576)
    if hashlib.sha256(payload).hexdigest()!=config["study_manifest"]["source_bootstrap.py"]:
        raise RuntimeError("Study bootstrap source differs")
    scope={"__name__":"captured_bootstrap","__file__":str(root/"source_bootstrap.py")}
    exec(compile(payload,scope["__file__"],"exec"),scope)
    finder=scope["PinnedSources"](root,config["study_manifest"])
    finder.install()
    return finder


def _api(config):
    """Verify expected closure, then verify API's actual captured byte mapping.

    The captured bootstrap imports only standard-library support and captures
    source; the first executive/world import occurs after the second comparison.
    """
    import hashlib
    import importlib.util
    import sys
    from pathlib import Path
    forbidden=("fractions","decimal","numbers","_decimal","_pydecimal","agenttest",
               "grounded_policy_v2","inquiry_executive","open_object_world_challenge")
    if any(any(n==p or n.startswith(p+".") for p in forbidden) for n in sys.modules):
        raise RuntimeError("API must be first before warm numerical/Ora/world dependencies")
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("Fresh isolated source-only interpreter required")
    root=Path(config["api_root"]).absolute()
    adapters=("challenge_action_authority","challenge_shadow_recorder","challenge_shadow_epistemic_selector",
        "native_observe_inquire_integration","normalized_inquiry_objectives","open_object_world_challenge",
        "open_object_world_challenge_explorer")
    paths=list((root/"src/agenttest").rglob("*.py"))+list((root/"experiments/grounded_policy_v2").rglob("*.py"))
    paths += [root/"experiments"/(n+".py") for n in adapters]
    expected=config["api_manifest"]
    if {str(p.relative_to(root)) for p in paths}!=set(expected):
        raise RuntimeError("API source closure membership differs")
    captured={}
    for relative,wanted in sorted(expected.items()):
        if Path(relative).is_absolute() or ".." in Path(relative).parts: raise RuntimeError("API source escape")
        raw=_read_regular(root/relative,2*1048576)
        if hashlib.sha256(raw).hexdigest()!=wanted: raise RuntimeError("Expected API source digest differs")
        captured[relative]=raw
    init=root/"experiments/grounded_policy_v2/__init__.py"
    spec=importlib.util.spec_from_file_location("grounded_policy_v2",init,submodule_search_locations=[str(init.parent)])
    module=importlib.util.module_from_spec(spec)
    sys.modules["grounded_policy_v2"]=module
    exec(compile(captured["experiments/grounded_policy_v2/__init__.py"],str(init),"exec"),module.__dict__)
    if module.IMPORT_MANIFEST!=expected or module._SOURCE_BYTES!=captured:
        raise RuntimeError("API's captured execution bytes differ from frozen expected bytes")
    if (module.NUMERICAL_IMPORT_MANIFEST!=config["api_runtime_manifest"]["modules"]
        or module._NUMERICAL_EXTENSION_HASH!=config["api_runtime_manifest"]["compiled_decimal"]["sha256"]
        or module._NUMERICAL_EXTENSION.origin!=config["api_runtime_manifest"]["compiled_decimal"]["origin"]):
        raise RuntimeError("Captured numerical source/extension differs from expected runtime")
    from grounded_policy_v2.executive import GroundedExecutive
    from grounded_policy_v2.contracts import _RUNTIME_AT_IMPORT
    if _RUNTIME_AT_IMPORT!=config["api_runtime_manifest"]:
        raise RuntimeError("Loaded complete API runtime differs from frozen runtime")
    return module,GroundedExecutive


def main():
    if REAL_FIXTURE_ADMISSION_REVIEWED is not True:
        raise RuntimeError("Real software fixture disabled pending exact-source/profile GO")
    import hashlib
    import json
    import os
    from pathlib import Path
    import resource
    import sys
    import time
    packet_raw=sys.stdin.buffer.readline(4*1048576+1)
    if len(packet_raw)>4*1048576 or not packet_raw.endswith(b"\n"):
        raise RuntimeError("Missing bounded native request")
    packet=json.loads(packet_raw)
    if set(packet)!={"request","configuration","precondition"}: raise RuntimeError("Unknown worker envelope")
    config,request=packet["configuration"],packet["request"]
    if config["profile"]!="one_native_invariant_pair_v1": raise RuntimeError("Fixture profile mismatch")
    if resource.getrlimit(resource.RLIMIT_AS)!=(384*1048576,384*1048576) or len(os.sched_getaffinity(0))!=1:
        raise RuntimeError("Worker resource inheritance differs")
    if (len(list(Path('/proc/self/task').iterdir()))!=1 or resource.getrlimit(resource.RLIMIT_NPROC)!=(1,1)
        or resource.getrlimit(resource.RLIMIT_CPU)!=(850,850)
        or resource.getrlimit(resource.RLIMIT_FSIZE)!=(2*1048576,2*1048576)):
        raise RuntimeError("Worker must remain single process/thread")
    if time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=config["deadline_ns"]:
        raise RuntimeError("Native absolute expiry passed")
    usage=resource.getrusage(resource.RUSAGE_SELF)
    as_limit=resource.getrlimit(resource.RLIMIT_AS); cpu_limit=resource.getrlimit(resource.RLIMIT_CPU)
    event={"phase":2,"pid":os.getpid(),"value":0,"code":0,"as_soft":as_limit[0],"as_hard":as_limit[1],
        "cpu_soft":cpu_limit[0],"cpu_hard":cpu_limit[1],"nproc_soft":1,"affinity_cpu":next(iter(os.sched_getaffinity(0))),
        "user_ns":int(usage.ru_utime*1e9),"system_ns":int(usage.ru_stime*1e9)}
    event_raw=(json.dumps(event,separators=(",",":"))+"\n").encode()
    if len(event_raw)>1024 or os.write(3,event_raw)!=len(event_raw): raise RuntimeError("Native child event failed")
    runtime=hashlib.sha256(_read_regular(Path(sys.executable).resolve(),64*1048576)).hexdigest()
    if runtime!=config["python_sha256"]: raise RuntimeError("Frozen Python runtime differs")
    if request.get("phase")=="report_saved":
        _study(config)
        from ora_study.native_transport import exchange_stdio
        from ora_study.protocol import digest
        from ora_study.native_fixture_controller import report_saved
        result=report_saved(request)
        exchange_stdio({"event":"stage_complete","result":result,"result_sha256":digest(result)})
        return
    module,api_type=_api(config)
    _study(config)
    from ora_study.call_accounting import CallAccounting
    from ora_study.native_transport import exchange_stdio
    from ora_study.protocol import digest
    from ora_study.stage_adapter import dispatch_invariant_stage
    from open_object_world_challenge import initial_world, observe_world, transition
    exchange_stdio({"event":"source_receipt","api_manifest_sha256":digest(module.IMPORT_MANIFEST),
        "study_manifest_sha256":digest(config["study_manifest"]),"python_sha256":runtime,
        "cold_flags":{"isolated":sys.flags.isolated,"no_site":sys.flags.no_site,"no_bytecode":sys.dont_write_bytecode},
        "runtime_manifest":sys.modules["grounded_policy_v2.contracts"]._RUNTIME_AT_IMPORT})
    root=Path(config["api_root"])
    identities={(str(root/"experiments/grounded_policy_v2/executive.py"),"validate_capsule"):"capsule_validation",
        (str(root/"experiments/grounded_policy_v2/policy.py"),"build_cohort"):"producer",
        (str(root/"experiments/grounded_policy_v2/policy.py"),"verify_cohort"):"cohort_proof",
        (str(root/"experiments/grounded_policy_v2/policy.py"),"verify_evaluation"):"decision_proof",
        (str(root/"experiments/grounded_policy_v2/policy.py"),"_reconstruct_cohort"):"checker_reconstruction",
        (str(root/"experiments/grounded_policy_v2/policy.py"),"evaluate"):"selecting_backend",
        (str(root/"experiments/open_object_world_challenge.py"),"transition"):"transition",
        (str(root/"src/agenttest/core.py"),"cycle"):"forbidden_core_cycle"}
    def count(message):
        exchange_stdio(message)
        return True
    def bind(case,frames,cohort,identity):
        response=exchange_stdio({"event":"cohort_bind","case_id":case,"D_frames":frames,
            "cohort":cohort,"native_identity":identity})
        return response["cohort_binding"]
    precondition=packet["precondition"]
    if request.get("phase") not in ("setup","create_select"):
        if not isinstance(precondition,dict) or set(precondition)!={"capsule_sha256","identity_sha256"}:
            raise RuntimeError("Every later API operation requires exact native identity/history")
        prior_raw=_read_regular(request["path"],2*1048576)
        prior=json.loads(prior_raw)
        if hashlib.sha256(prior_raw).hexdigest()!=precondition["capsule_sha256"] or digest(prior["identity"])!=precondition["identity_sha256"]:
            raise RuntimeError("Native authority changed before API mutation")
    elif precondition is not None:
        raise RuntimeError("Unexpected setup/create precondition")
    with CallAccounting(identities,count):
        if request=={"phase":"setup"}:
            world=initial_world(1)
            frames=[{"observation":observe_world(world),"receipt":None}]
            results=[]
            for _ in range(2):
                world,receipt=transition(world,{"action":"north"},cycle=world["cycle"]+1)
                results.append({"world":world,"receipt":receipt})
                frames.append({"observation":observe_world(world),"receipt":receipt})
            result={"phase":"setup","values":{"ora":{},"world":world,"observations":frames},"transitions":results}
        else:
            result=dispatch_invariant_stage(api_type,request,cohort_binder=bind)
    exchange_stdio({"event":"stage_complete","result":result,"result_sha256":digest(result)})


if __name__=="__main__":
    main()
