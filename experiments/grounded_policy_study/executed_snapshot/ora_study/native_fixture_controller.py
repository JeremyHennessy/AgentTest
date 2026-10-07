"""Compiler-embedded controller for ONE prospective native invariant pair.

Source-disabled until the parent and independent reviewer approve exact bytes.
No runtime option enables the fixture or scientific study. Setup is generated
once, both first decisions commit before either action, and the reporter reads
saved JSON only. C outer status remains final authority over this candidate.
"""
REAL_FIXTURE_ADMISSION_REVIEWED = True
SCIENTIFIC_ADMISSION_REVIEWED = False

FIXTURE_ID = "ora-bounded-native-invariant-2026-10-07-v1"


def claim_one_started_marker(files,package_root,config,profile_sha256,study_manifest_sha256):
    """Permanent one-attempt marker shared by all output-root choices.

    Only the parent/reviewer may supply the exact GO receipt. Neither test
    discovery nor a new output directory can create another admitted attempt.
    """
    import hashlib,json,os
    from pathlib import Path
    from ora_study.native_fixture_transport import read_regular
    from ora_study.protocol import canonical
    from ora_study.ledger import IntegrityError
    if config["fixture_id"]!=FIXTURE_ID:
        raise IntegrityError("This source is bound to one fixed fixture identity")
    receipt_raw=read_regular(config["admission_receipt_path"],4096)
    receipt=json.loads(receipt_raw)
    expected={"decision":"GO","fixture_id":FIXTURE_ID,"output_root":config["output_root"],
        "profile_sha256":profile_sha256,"study_manifest_sha256":study_manifest_sha256,
        "started_marker_path":config["started_marker_path"]}
    if receipt!=expected:
        raise IntegrityError("Exact-source/profile GO receipt is absent or differs")
    marker=Path(package_root).parents[1]/"policy-study-results"/"ONE_NATIVE_INVARIANT_STARTED.json"
    if str(marker)!=config["started_marker_path"]:
        raise IntegrityError("Global one-attempt marker location differs from frozen task root")
    if any(p.is_symlink() for p in (marker,*marker.parents)):
        raise IntegrityError("Aliased one-attempt marker ancestry")
    value=dict(expected,admission_receipt_sha256=hashlib.sha256(receipt_raw).hexdigest())
    raw=canonical(value)+b"\n"
    if len(raw)>4096: raise IntegrityError("Admission marker exceeds reserved slot")
    files.reserve("external-one-attempt-marker","manifests",4096)
    fd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400)
    try:
        view=memoryview(raw)
        while view:
            n=os.write(fd,view)
            if n<=0: raise OSError("Short one-attempt marker write")
            view=view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    directory=os.open(marker.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(directory)
    finally: os.close(directory)
    return {"marker_path":str(marker),"marker_sha256":hashlib.sha256(raw).hexdigest(),**value}



def report_saved(request):
    """No API reopen, policy evaluation, simulator import, or new sequence."""
    import json
    from .ledger import IntegrityError, Ledger
    from .protocol import digest
    from .native_fixture_transport import read_regular, MIB, INVARIANT_PROFILE
    from .native_projection import project_native_stage, _stage_records
    if set(request)!={"phase","exports","ledger_path","ledger_head","counters","terminal_state"}:
        raise IntegrityError("Unknown saved report request")
    rows,broken=Ledger.read_verified(request["ledger_path"])
    if broken or not any(row["hash"]==request["ledger_head"] for row in rows):
        raise IntegrityError("Saved reporter lacks verified sealed ledger prefix")
    # Additional reporter-admission/source rows may follow; the export positions
    # must be before the independently declared exact parent prefix.
    limit=next(row["sequence"] for row in rows if row["hash"]==request["ledger_head"])
    sealed=rows[limit]
    if (sealed["kind"]!="fixture_evidence_sealed" or sealed["payload"].get("exports")!=request["exports"]
        or sealed["payload"].get("counters")!=request["counters"]):
        raise IntegrityError("Report inputs do not match independently saved seal")
    if any(row["kind"] in ("integrity_failure","worker_uncertain") for row in rows[:limit+1]):
        raise IntegrityError("Invalid/uncertain parent status dominates complete reporter input")
    entries=[row["payload"] for row in rows[:limit+1] if row["kind"]=="actual_call_entered"]
    if any(request["counters"]["actual_entries"][key]!=sum(e["category"]==key for e in entries)
           for key in request["counters"]["actual_entries"]):
        raise IntegrityError("Report call counts differ from ledger observations")
    projected={}
    if set(request["exports"])!=set(INVARIANT_PROFILE["case_ids"]):
        raise IntegrityError("Reporter needs exactly the two fixture arms")
    for case,description in request["exports"].items():
        raw=read_regular(description["path"],2*MIB)
        state=json.loads(raw)
        if digest(state)!=description["state_sha256"]:
            raise IntegrityError("Saved authoritative export changed")
        stages={}
        for ordinal in (1,2):
            native_decision,native_outcome,native_belief=_stage_records(state,ordinal)
            mapping=description["sequences"][str(ordinal)]
            for field,seq in mapping.items():
                if seq is None: continue
                if type(seq) is not int or not 0<seq<=limit:
                    raise IntegrityError("Reporter sequence outside parent sealed prefix")
                row=rows[seq]
                expected={"t1_committed":"decision_durable","outcome_invoked":"started",
                          "outcome_durable":"durably_consumed","t3_completed":"interpretation_durable"}[field]
                if row["kind"]!=expected:
                    raise IntegrityError("Supplied sequence does not name corresponding ledger event")
                payload=row["payload"]
                if field in ("outcome_invoked","outcome_durable"):
                    if payload["slot"]!=f"owned.{case}.stage{ordinal}":
                        raise IntegrityError("Supplied sequence references another owned transition")
                elif payload.get("decision_id")!=f"{case}.stage{ordinal}":
                    raise IntegrityError("Supplied sequence references another decision")
                expected_hash={"t1_committed":("receipt_hash",native_decision["hash"]),
                    "outcome_durable":("authority_hash",native_outcome["hash"] if native_outcome else None),
                    "t3_completed":("belief_hash",native_belief["hash"] if native_belief else None)}.get(field)
                if expected_hash and payload.get(expected_hash[0])!=expected_hash[1]:
                    raise IntegrityError("Ledger receipt hash differs from saved native record")
            stages[str(ordinal)]=project_native_stage(state,ordinal,case_id=case,sequence=mapping)
        saved_projection=json.loads(read_regular(description["projection_path"],2*MIB))
        if stages!=saved_projection or digest(stages)!=description["projection_sha256"]:
            raise IntegrityError("Independent saved projection differs from immutable export")
        projected[case]=stages
    return {"schema":"ora.native-invariant.report.v1","data_kind":"synthetic_fixture",
        "profile":INVARIANT_PROFILE["name"],"candidate_status":request["terminal_state"],
        "requires_outer_terminal_seal":True,"scientific_result":None,"science_result":None,
        "scientific_denominators":0,"scientific_transition_invocations":0,
        "fixture_arms":2,"fixture_decisions":4,"counters":request["counters"],
        "projected_stages_sha256":digest(projected),"parent_ledger_head":request["ledger_head"]}


class FixtureController:
    def __init__(self,transport):
        self.transport=transport; self.files=transport.files; self.ledger=transport.ledger
        self.states={}; self.sources={}; self.identities={}; self.sequences={}; self.source_proofs={}
    def _sequence(self,kind,**matching):
        rows=[r for r in self.ledger.records if r["kind"]==kind and all(r["payload"].get(k)==v for k,v in matching.items())]
        if len(rows)!=1: raise RuntimeError("Sequence must identify one independent parent receipt")
        return rows[0]["sequence"]
    def setup(self):
        from .protocol import canonical,digest
        from .native_fixture_transport import FixtureReferences, SOURCE_BOUNDS
        from .native_projection import _frames,_rows
        tickets=tuple(self.ledger.charge("setup",f"setup.north{i}") for i in (1,2))
        result=self.transport._dispatch("setup",{"phase":"setup"},tickets=tickets)
        values=result["values"]
        if set(values)!={"ora","world","observations"} or values["ora"]!={} or len(values["observations"])!=3:
            raise RuntimeError("Setup differs from frozen single two-north source")
        _frames(values["observations"])
        if [f["receipt"]["action"] for f in values["observations"][1:]]!=["north","north"] or len(result["transitions"])!=2:
            raise RuntimeError("Setup trajectory differs")
        self.files.put_new("setup.json","setup",result)
        for ticket,record,frame in zip(tickets,result["transitions"],values["observations"][1:]):
            if record["receipt"]!=frame["receipt"]: raise RuntimeError("Setup durable receipt differs")
            self.ledger.reconcile_saved(ticket,result_hash=digest(record),authority_hash=digest(result))
        for arm in ("R","W"):
            case="native-invariant."+arm; self.sources[case]={}; self.source_proofs[case]={}
            for key,value in values.items():
                raw=canonical(value)+b"\n"
                if len(raw)>SOURCE_BOUNDS[key]: raise RuntimeError("Setup source exceeds frozen slot")
                name=f"sources/{case}/{key}.json"
                self.files.put_new(name,"source_inputs",raw)
                path=self.files.root/name
                path.chmod(0o400)
                self.sources[case][key]=str(path)
                import hashlib
                info=path.stat()
                self.source_proofs[case][key]={"path":str(path),"sha256":hashlib.sha256(raw).hexdigest(),
                    "device":info.st_dev,"inode":info.st_ino,"bytes":len(raw)}
        if any(self.source_proofs['native-invariant.R'][k]['inode']==self.source_proofs['native-invariant.W'][k]['inode'] for k in values):
            raise RuntimeError("Paired source files must be independently copied")
        self.transport.references=FixtureReferences(self.ledger,self.files,values["observations"],_rows(values["observations"]))
        self.ledger.append("paired_sources_frozen",{"source_proofs":self.source_proofs,"logical_values_sha256":digest(values)})
    def _api(self,arm,phase,stage):
        import hashlib
        import json
        from .protocol import digest
        from .native_fixture_transport import read_regular,MIB
        from .native_projection import decision_semantics
        case="native-invariant."+arm; decision_id=f"{case}.stage{stage}"
        capsule=self.files.root/"capsules"/(case+".json")
        request={"phase":phase,"case_id":case,"path":str(capsule),
            "research_dir":str(capsule.parent),"source_paths":self.sources[case],"arm":arm,"stage":stage}
        for key,path in self.sources[case].items():
            raw=read_regular(path,MIB); info=__import__('os').stat(path)
            observed={"path":path,"sha256":hashlib.sha256(raw).hexdigest(),"device":info.st_dev,"inode":info.st_ino,"bytes":len(raw)}
            if observed!=self.source_proofs[case][key]: raise RuntimeError("Immutable source identity changed")
        precondition=None
        if phase!="create_select":
            raw=read_regular(capsule,2*MIB); previous=json.loads(raw)
            if previous!=self.states[case] or digest(previous["identity"])!=self.identities[case]:
                raise RuntimeError("Native case identity/history changed before mutation")
            precondition={"capsule_sha256":hashlib.sha256(raw).hexdigest(),"identity_sha256":self.identities[case]}
        if phase in ("create_select","select"):
            self.ledger.append("decision_started",{"decision_id":decision_id})
        ticket=self.ledger.charge("owned","owned."+decision_id) if phase=="execute" else None
        self.files.begin_api_write(case)
        result=self.transport._dispatch(f"{case}.{phase}.stage{stage}",request,
            tickets=(ticket,) if ticket else (),precondition=precondition)
        self.files.finish_api_write(case)
        state=result["state"]
        if json.loads(read_regular(capsule,2*MIB))!=state:
            raise RuntimeError("API return differs from authoritative saved capsule")
        identity=state["identity"]
        if (identity["path"]!=str(capsule) or identity["research_dir"]!=str(capsule.parent)
            or identity["source_inputs"]!=self.source_proofs[case] or identity["discovery_count"]!=2
            or identity["evidence_mode"]!={"R":"retain_first","W":"withhold_first"}[arm]
            or identity["code_manifest"]!=self.transport.config["api_manifest"]
            or identity["runtime_manifest"]!=self.transport.config["api_runtime_manifest"]):
            raise RuntimeError("Native capsule bound wrong arm/source identity")
        identity_hash=digest(identity)
        if self.transport.bound_identities.get(case)!=identity_hash: raise RuntimeError("Returned native identity differs from pre-T1 bound identity")
        if case in self.identities and identity_hash!=self.identities[case]: raise RuntimeError("Native identity replaced")
        self.identities[case]=identity_hash
        decision_semantics(state,stage)
        mapping=self.sequences.setdefault(case,{}).setdefault(str(stage),{
            "t1_committed":None,"outcome_invoked":None,"outcome_durable":None,"t3_completed":None})
        if phase in ("create_select","select"):
            decision=state["decisions"][-1]
            self.ledger.append("decision_durable",{"decision_id":decision_id,"receipt_hash":decision["hash"],"is_null":decision["status"]!="selected"})
            mapping["t1_committed"]=self._sequence("decision_durable",decision_id=decision_id)
        elif phase=="execute":
            outcome=state["outcomes"][-1]
            result_hash=digest({"world":state["world"],"receipt":outcome["receipt"]})
            self.ledger.reconcile_saved(ticket,result_hash=result_hash,authority_hash=outcome["hash"])
            mapping["outcome_invoked"]=self._sequence("started",ticket=ticket)
            mapping["outcome_durable"]=self._sequence("durably_consumed",ticket=ticket)
        else:
            self.ledger.append("interpretation_durable",{"decision_id":decision_id,"belief_hash":state["beliefs"][-1]["hash"]})
            mapping["t3_completed"]=self._sequence("interpretation_durable",decision_id=decision_id)
        self.states[case]=state
        return state
    def run(self):
        if REAL_FIXTURE_ADMISSION_REVIEWED is not True:
            raise RuntimeError("Native invariant pair disabled pending exact-source/profile GO")
        return self._run_pair()
    def _run_pair(self):
        from .protocol import digest
        from .native_projection import first_decision_semantics, public_outcome_semantics, decision_semantics, project_native_stage
        self.setup()
        first={arm:self._api(arm,"create_select",1) for arm in ("R","W")}
        if first_decision_semantics(first["R"])!=first_decision_semantics(first["W"]):
            raise RuntimeError("Both complete first inputs/selections must match before E1")
        self.ledger.append("first_pair_gate",{"semantics_sha256":digest(first_decision_semantics(first["R"]))})
        first_null=first["R"]["decisions"][0]["status"]!="selected"
        del first
        if not first_null:
            owned={arm:self._api(arm,"execute",1) for arm in ("R","W")}
            if public_outcome_semantics(owned["R"]["outcomes"][-1])!=public_outcome_semantics(owned["W"]["outcomes"][-1]):
                raise RuntimeError("Actual first public outcomes differ")
            del owned
            for arm in ("R","W"): self._api(arm,"interpret",1)
        first_lifecycle={}
        for arm in ("R","W"):
            case="native-invariant."+arm
            saved=project_native_stage(self.states[case],1,case_id=case,sequence=self.sequences[case]["1"])
            first_lifecycle[arm]={"null":saved["outcome"] is None,
                "interpretation":saved["t3"]["semantic"] if saved["t3"] else None}
        if first_lifecycle["R"]!=first_lifecycle["W"]:
            raise RuntimeError("First canonical interpretation/lifecycle differs")
        self.ledger.append("first_lifecycle_gate",{"semantic_sha256":digest(first_lifecycle["R"])})
        worlds=[self.states["native-invariant."+arm]["world"] for arm in ("R","W")]
        if worlds[0]!=worlds[1]: raise RuntimeError("Full post-first worlds differ")
        self.ledger.append("post_first_world_gate",{"world_sha256":digest(worlds[0])})
        second={arm:self._api(arm,"select",2) for arm in ("R","W")}
        if first_null and decision_semantics(second["R"],2)!=decision_semantics(second["W"],2):
            raise RuntimeError("Null first stage must leave second semantics equal")
        selected={arm:second[arm]["decisions"][-1]["status"]=="selected" for arm in ("R","W")}
        del second
        for arm in ("R","W"):
            if selected[arm]:
                self._api(arm,"execute",2); self._api(arm,"interpret",2)
        exports={}
        for case,state in self.states.items():
            name=f"exports/{case}.json"
            self.files.put_new(name,"exports",state)
            projections={str(ordinal):project_native_stage(state,ordinal,case_id=case,sequence=self.sequences[case][str(ordinal)]) for ordinal in (1,2)}
            projection_name=f"exports/{case}.projected.json"
            self.files.put_new(projection_name,"exports",projections)
            exports[case]={"path":str(self.files.root/name),"state_sha256":digest(state),"sequences":self.sequences[case],
                "projection_path":str(self.files.root/projection_name),"projection_sha256":digest(projections)}
        counters=self.ledger.counters()
        if counters["evidence_loss"] or counters["actual_entries"]["transition"]!=counters["durably_consumed"]:
            raise RuntimeError("Transition entry/durable evidence is incomplete")
        seal=self.ledger.append("fixture_evidence_sealed",{"exports":exports,"counters":counters})
        report=self.transport._dispatch("reporter",{"phase":"report_saved","exports":exports,
            "ledger_path":str(self.ledger.path),"ledger_head":seal,"counters":counters,"terminal_state":"complete"})
        self.files.put_new("candidate-report.json","reports",report)
        self.transport.emit(10,counters["actual_entries"]["transition"],
            sum(p["worker_id"].startswith("native-invariant.") for p in self.ledger._events("worker_admitted")))
        self.transport.emit(11,counters["actual_entries"]["selecting_backend"],counters["actual_entries"]["producer"])
        self.transport.emit(9,4,0)
        return report


def _emit(phase,value=0,code=0):
    import json,os,resource
    limits_as=resource.getrlimit(resource.RLIMIT_AS)
    limits_cpu=resource.getrlimit(resource.RLIMIT_CPU)
    nproc=resource.getrlimit(resource.RLIMIT_NPROC)[0]
    usage=resource.getrusage(resource.RUSAGE_SELF)
    row={"phase":phase,"pid":os.getpid(),"value":value,"code":code,
        "as_soft":limits_as[0],"as_hard":limits_as[1],"cpu_soft":limits_cpu[0],"cpu_hard":limits_cpu[1],
        "nproc_soft":18446744073709551615 if nproc==resource.RLIM_INFINITY else nproc,
        "affinity_cpu":next(iter(os.sched_getaffinity(0))),"user_ns":int(usage.ru_utime*1e9),"system_ns":int(usage.ru_stime*1e9)}
    raw=(json.dumps(row,separators=(",",":"))+"\n").encode()
    if len(raw)>1024 or os.write(3,raw)!=len(raw): raise RuntimeError("Native event write failed")


def main():
    # These bytes are embedded by the native compiler. Check admission before
    # even reading fixture config, creating an output root or spawning a child.
    if REAL_FIXTURE_ADMISSION_REVIEWED is not True:
        raise RuntimeError("Native fixture controller disabled pending exact-source/profile GO")
    import hashlib,json,os,resource,time
    from pathlib import Path
    root=Path(os.environ["ORA_LAUNCHER_PACKAGE_ROOT"])
    manifest_raw=Path(os.environ["ORA_LAUNCHER_MANIFEST_PATH"]).read_bytes()
    if len(manifest_raw)>65536 or hashlib.sha256(manifest_raw).hexdigest()!=os.environ["ORA_LAUNCHER_MANIFEST_SHA256"]:
        raise RuntimeError("Compiler-bound study manifest differs")
    manifest=json.loads(manifest_raw)
    raw=(root/"source_bootstrap.py").read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest["source_bootstrap.py"]: raise RuntimeError("Bootstrap differs")
    scope={"__name__":"captured_bootstrap","__file__":str(root/"source_bootstrap.py")}
    exec(compile(raw,scope["__file__"],"exec"),scope)
    finder=scope["PinnedSources"](root,manifest); finder.install()
    from ora_study.native_fixture_transport import FixtureInventory,FixtureLedger,SequentialNativeTransport,read_regular,MIB
    from ora_study.native_fixture_controller import FixtureController as BoundController
    config_raw=read_regular(os.environ["ORA_LAUNCHER_PROFILE_PATH"],2*MIB)
    if hashlib.sha256(config_raw).hexdigest()!=os.environ["ORA_LAUNCHER_PROFILE_SHA256"]:
        raise RuntimeError("Compiler-bound fixture profile differs")
    config=json.loads(config_raw)
    if set(config)!={"schema","profile","output_root","api_root","api_manifest","python_sha256","api_runtime_manifest","fixture_id","admission_receipt_path","started_marker_path"} or config["schema"]!="ora.native-fixture.launch.v1" or config["profile"]!="one_native_invariant_pair_v1":
        raise RuntimeError("Unknown compiler-bound fixture profile")
    deadline=int(os.environ["ORA_LAUNCHER_DEADLINE_NS"])
    if not 0<deadline-time.clock_gettime_ns(time.CLOCK_BOOTTIME)<=850*1000000000:
        raise RuntimeError("Absolute outer expiry is missing/out of range")
    if resource.getrlimit(resource.RLIMIT_AS)!=(96*MIB,384*MIB) or len(os.sched_getaffinity(0))!=1:
        raise RuntimeError("Capped native controller inheritance differs")
    config.update(package_root=str(root),study_manifest=manifest,deadline_ns=deadline)
    worker_path,worker_bytes,_=finder.modules["ora_study.native_fixture_worker"]
    files=FixtureInventory(config["output_root"],native_root_precreated=True)
    ledger=FixtureLedger(files.root/"ledger.jsonl")
    transport=SequentialNativeTransport(files,ledger,worker_bytes,str(worker_path),config,deadline,emit=_emit)
    try:
        files.put_new("frozen-profile.json","manifests",config)
        marker=claim_one_started_marker(files,root,config,os.environ["ORA_LAUNCHER_PROFILE_SHA256"],os.environ["ORA_LAUNCHER_MANIFEST_SHA256"])
        ledger.append("one_attempt_started",marker)
        result=BoundController(transport).run()
        print(json.dumps(result,separators=(",",":")),flush=True)
    except BaseException as error:
        try:
            ledger.append("integrity_failure",{"reason":type(error).__name__,"detail":str(error)[:1024]})
            files.put_new("failure-report.json","reports",{"status":"invalid","scientific_result":None,
                "counters":ledger.counters(),"reason":type(error).__name__,"requires_outer_terminal_seal":True})
        finally:
            raise
    finally:
        ledger.close(); files.close()


if __name__=="__main__":
    main()
