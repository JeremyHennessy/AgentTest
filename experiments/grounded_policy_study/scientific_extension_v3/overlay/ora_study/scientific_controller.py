"""Disabled, fixed v4 controller over the reviewed native process transport.

No module import starts a world, API, selector or worker. The parent controller
owns immutable inputs, case identities and all durable acknowledgements. Saved
capsules remain the original exports; reports cannot reopen the API.
"""
SCIENTIFIC_ADMISSION_REVIEWED = False
RUN_ID = "ora-two-decision-v4-first-comparison"


def report_saved(request):
    from .scientific_reporter import report_saved as saved_reporter
    return saved_reporter(request)


def reserve_controller_inventory(files):
    """Declare every controller/reporter slot before scientific startup."""
    from .protocol import registry, MIB, MOVEMENTS
    for layout in (1, 2, 3, 4):
        files.reserve(f"neutral/layout{layout}-initial.json", "source_inputs", 8*1024)
        files.reserve(f"neutral/layout{layout}-frames.json", "source_inputs", 208*1024)
        files.reserve(f"references/layout{layout}-D.json", "D_references", 208*1024)
        files.reserve(f"references/layout{layout}-cohort.json", "D_references", 256*1024+1)
    for anchor in registry()["anchors"]:
        name = anchor["anchor_id"]
        files.reserve(f"neutral/{name}-world.json", "source_inputs", 96*1024)
        files.reserve(f"exports/{name}-forecast.json", "saved_exports", 100*1024)
        for action in MOVEMENTS:
            files.reserve(f"exports/{name}-probe-{action}.json", "saved_exports", 16*1024)
    files.reserve("study-index.json", "saved_exports", 512*1024)
    files.reserve("frozen-profile.json", "manifests", 512*1024)
    files.reserve("artifact-inventory.json", "manifests", 256*1024)
    files.reserve("controller-terminal.json", "manifests", 64*1024)
    files.reserve("failure-report.json", "manifests", 64*1024)
    for number, cap in enumerate((2*MIB, 2*MIB, 2*MIB-16384)):
        files.reserve(f"reports/scientific-report.part{number}.bin", "reports", cap)
    files.reserve("reports/scientific-report.json", "reports", 16384)
    # The reporter owns no mkdir capability beyond these declared output slots.
    (files.root/"reports").mkdir()


class ScientificReferences:
    """Full-byte equality to the first declared real cohort, without rebuilding."""
    def __init__(self, controller):
        from .protocol import registry
        self.owner = controller
        self.references = {}
        self.bound_cases = set()
        self.native_ids = set()
        self.cases = {case: anchor for anchor in registry()["anchors"] for case in anchor["cases"].values()}
        self.first = {layout: next(a["cases"]["R"] for a in registry()["anchors"] if a["layout"] == layout)
                      for layout in (1, 2, 3, 4)}

    def bind(self, case_id, frames, cohort, identity):
        from copy import deepcopy
        from .ledger import IntegrityError
        from .protocol import canonical, digest
        if case_id not in self.cases or case_id in self.bound_cases:
            raise IntegrityError("Unknown or repeated cohort identity")
        layout = self.cases[case_id]["layout"]
        frozen = self.owner.discovery[layout]
        if frames != frozen["frames"] or len(frames) != 33:
            raise IntegrityError("Native D differs from complete frozen discovery frames")
        if not isinstance(identity, dict) or not identity.get("run_id") or identity["run_id"] in self.native_ids:
            raise IntegrityError("Native capsule identity missing/reused")
        normalized = deepcopy(frozen["projected_rows"])
        for row in normalized:
            for entity_id in row["before_context"]["visible_ids"]:
                row["before_context"].setdefault("entity."+entity_id+".state", None)
        if cohort.get("discovery_events") != [{"event_id": row["event_id"], "digest": digest(row)} for row in normalized]:
            raise IntegrityError("Cohort derivation differs from frozen movement projection")
        raw = canonical(cohort)
        if layout not in self.references:
            if case_id != self.first[layout]:
                raise IntegrityError("Only the first declared real capsule may establish reference")
            descriptor = self.owner._put(f"references/layout{layout}-cohort.json", "D_references", cohort)
            self.references[layout] = (raw, descriptor)
        elif self.references[layout][0] != raw:
            raise IntegrityError("Complete canonical cohort differs from immutable first reference")
        reference_hash = digest({"frames": frames, "projected_rows": frozen["projected_rows"], "cohort": cohort})
        proof = self.owner.ledger.append("cohort_reference_bound", {
            "case_id": case_id, "layout": layout, "reference_case_id": self.first[layout],
            "reference_bytes_sha256": reference_hash, "D_sha256": digest(frames),
            "projected_D_sha256": digest(frozen["projected_rows"]), "cohort_sha256": digest(cohort),
            "native_identity": identity})
        self.bound_cases.add(case_id)
        self.native_ids.add(identity["run_id"])
        return {"case_id": case_id, "D_sha256": digest(frames), "cohort_sha256": digest(cohort),
                "reference_bytes_sha256": reference_hash, "durable_ack_sha256": proof}


class ScientificController:
    """FiniteDriver port: all mutable authority stays in this trusted parent."""
    def __init__(self, transport):
        from .protocol import registry
        self.transport = transport
        self.files, self.ledger = transport.files, transport.ledger
        self.authored_fixture_only = getattr(transport, "authored_fixture_only", False)
        self.states, self.sources, self.source_proofs, self.identities = {}, {}, {}, {}
        self.frames, self.discovery, self.worlds, self.probe_records = {}, {}, {}, {}
        self.forecasts, self.saved = {}, {}
        self.candidate_classification = None
        self.index = {"schema": "ora.scientific.study-index.v1", "registry": registry(),
            "anchors": [{"anchor_id": a["anchor_id"], "layout": a["layout"], "neutral_t": a["t"],
                "capsules": {"R": None, "W": None}, "probes": {}, "forecast_commitment": None}
                for a in registry()["anchors"]]}
        self.by_anchor = {a["anchor_id"]: a for a in self.index["anchors"]}
        transport.event_handler = self.world_event
        transport.references = ScientificReferences(self)

    def _put(self, name, category, value):
        import hashlib
        from .protocol import canonical, digest
        raw = canonical(value)+b"\n"
        self.files.put_new(name, category, raw)
        return {"path": str(self.files.root/name), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "state_sha256": digest(value)}

    def _read(self, name, cap):
        import json
        from .native_fixture_transport import read_regular
        return json.loads(read_regular(self.files.root/name, cap))

    def _computed(self, ticket):
        from .ledger import IntegrityError
        rows = [p for p in self.ledger._events("computed") if p["ticket"] == ticket]
        if len(rows) != 1:
            raise IntegrityError("Saved outcome lacks one observed computed return")
        return rows[0]["result_hash"]

    def world_event(self, worker_id, request, message):
        from copy import deepcopy
        from .ledger import IntegrityError
        from .native_projection import _frames, _rows, public_probe_semantics
        from .protocol import digest, ANCHORS
        event = message["event"]
        if event == "probe_saved":
            anchor_id = request["anchor_id"]
            if message["anchor_id"] != anchor_id:
                raise IntegrityError("Probe switched anchor")
            body = public_probe_semantics(message["outcome"])
            action = body["command"]["action"]
            value = {"anchor_id": anchor_id, "action": action,
                "source_world_sha256": request["forecast_commitment"]["source_world_sha256"],
                "forecast_commitment_sha256": digest(request["forecast_commitment"]), **body}
            descriptor = self._put(f"exports/{anchor_id}-probe-{action}.json", "saved_exports", value)
            self.ledger.append("probe_saved", {"anchor_id": anchor_id, "action": action,
                "ticket": message["ticket"], "descriptor": descriptor})
            self.ledger.reconcile_saved(message["ticket"], result_hash=self._computed(message["ticket"]),
                                        authority_hash=digest(value))
            self.probe_records.setdefault(anchor_id, {})[action] = body
            self.by_anchor[anchor_id]["probes"][action] = descriptor
            return {}
        layout = message["layout"]
        if layout != request["layout"]:
            raise IntegrityError("Neutral callback switched layout")
        if event == "neutral_initial":
            if layout in self.frames:
                raise IntegrityError("Repeated neutral source")
            _frames([message["frame"]])
            self.frames[layout] = [deepcopy(message["frame"])]
            descriptor = self._put(f"neutral/layout{layout}-initial.json", "source_inputs",
                                   {"world": message["world"], "frame": message["frame"]})
            self.ledger.append(event, {"layout": layout, "descriptor": descriptor})
        elif event == "neutral_transition_saved":
            frames = self.frames[layout]
            if message["t"] != len(frames) or message["before_observation"] != frames[-1]["observation"]:
                raise IntegrityError("Neutral saved transition breaks its immutable prefix")
            receipt, command = message["receipt"], message["command"]
            if any(receipt.get(key) != command.get(key) for key in ("action", "target", "direction")):
                raise IntegrityError("Neutral receipt differs from actually dispatched command")
            frame = {"observation": deepcopy(message["after_observation"]), "receipt": deepcopy(receipt)}
            _frames(frames+[frame])
            self.ledger.append(event, deepcopy(message))
            self.ledger.reconcile_saved(message["ticket"], result_hash=self._computed(message["ticket"]),
                                        authority_hash=digest(message))
            frames.append(frame)
        elif event == "D_frozen":
            frames = self.frames[layout]
            if len(frames) != 33 or frames != message["frames"] or message["projected_rows"] != _rows(frames):
                raise IntegrityError("Discovery frames/movement projection differ from saved neutral prefix")
            value = {"frames": deepcopy(frames), "projected_rows": deepcopy(message["projected_rows"])}
            descriptor = self._put(f"references/layout{layout}-D.json", "D_references", value)
            self.discovery[layout] = value
            self.ledger.append(event, {"layout": layout, "descriptor": descriptor,
                "D_sha256": digest(frames), "projected_D_sha256": digest(value["projected_rows"])})
        elif event == "neutral_anchor_saved":
            t = message["t"]
            if t not in ANCHORS or message["frames"] != self.frames[layout] or len(message["frames"]) != t+1:
                raise IntegrityError("Anchor does not match declared immutable neutral prefix")
            anchor_id = f"layout{layout}.t{t}"
            tickets = [row["ticket"] for row in self.ledger._events("charged")
                       if row["slot"] == f"neutral.layout{layout}.t{t}"]
            if len(tickets) != 1 or digest({"world": message["world"], "receipt": message["frames"][-1]["receipt"]}) != self._computed(tickets[0]):
                raise IntegrityError("Copied anchor world differs from independently observed transition return")
            descriptor = self._put(f"neutral/{anchor_id}-world.json", "source_inputs", {"world": message["world"]})
            self.worlds[anchor_id] = descriptor
            self.ledger.append(event, {"layout": layout, "t": t, "anchor_id": anchor_id,
                "descriptor": descriptor, "frames_sha256": digest(message["frames"]), "ticket": tickets[0],
                "computed_result_sha256": self._computed(tickets[0])})
        else:
            raise IntegrityError("Unknown durable world callback")
        return {}

    def neutral(self, layout):
        from .ledger import IntegrityError
        from .protocol import digest
        result = self.transport._dispatch(f"neutral.layout{layout}", {"phase": "neutral", "layout": layout})
        expected = {"event": "neutral_complete", "layout": layout, "actual_transitions": 64, "counter_attempt_total": 64}
        if result != expected or len(self.frames[layout]) != 65:
            raise IntegrityError("Neutral worker omitted its full fixed horizon/counter")
        descriptor = self._put(f"neutral/layout{layout}-frames.json", "source_inputs", {"frames": self.frames[layout]})
        self.ledger.append("neutral_complete", {"layout": layout, "actual_transitions": 64,
            "counter_attempt_total": 64, "descriptor": descriptor})
        del self.frames[layout]

    def prepare_pair(self, anchor):
        import hashlib
        from .native_fixture_transport import read_regular
        from .artifact_inventory import SOURCE_BOUNDS
        from .protocol import canonical, digest
        from .ledger import IntegrityError
        frames = self._read(f"neutral/layout{anchor['layout']}-frames.json", 208*1024)["frames"][:anchor["t"]+1]
        world = self._read(f"neutral/{anchor['anchor_id']}-world.json", 96*1024)["world"]
        values = {"ora": {}, "world": world, "observations": frames}
        proofs = {}
        for arm in ("R", "W"):
            case = anchor["cases"][arm]
            if case in self.sources:
                raise IntegrityError("A registered source set cannot be recreated")
            self.sources[case], self.source_proofs[case] = {}, {}
            for key, value in values.items():
                name = f"sources/{case}/{key}.json"
                self._put(name, "source_inputs", value)
                path = self.files.root/name
                path.chmod(0o400)
                raw = read_regular(path, SOURCE_BOUNDS[key])
                info = path.stat()
                self.sources[case][key] = str(path)
                self.source_proofs[case][key] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                    "device": info.st_dev, "inode": info.st_ino, "bytes": len(raw)}
            proofs[case] = self.source_proofs[case]
        for key in values:
            r, w = (proofs[anchor["cases"][a]][key] for a in ("R", "W"))
            if r["inode"] == w["inode"] or (r["sha256"], r["bytes"]) != (w["sha256"], w["bytes"]):
                raise IntegrityError("Paired immutable source copies differ or share an inode")
        logical_hash = digest(values)
        self.ledger.append("paired_sources_frozen", {"anchor_id": anchor["anchor_id"],
            "source_proofs": proofs, "logical_values_sha256": logical_hash})
        return {"logical_inputs_sha256": logical_hash}

    def _sequence(self, kind, **matching):
        from .ledger import IntegrityError
        rows = [r for r in self.ledger.records if r["kind"] == kind and
                all(r["payload"].get(key) == value for key, value in matching.items())]
        if len(rows) != 1:
            raise IntegrityError("Native receipt needs one independent parent ledger position")
        return rows[0]["sequence"]

    def api_stage(self, anchor, arm, phase, stage):
        import hashlib, json, os
        from .protocol import digest, MIB
        from .native_fixture_transport import read_regular
        from .artifact_inventory import SOURCE_BOUNDS
        from .native_projection import decision_semantics
        from .ledger import IntegrityError
        case = anchor["cases"][arm]
        capsule = self.files.root/"capsules"/(case+".json")
        request = {"phase": phase, "case_id": case, "path": str(capsule), "research_dir": str(capsule.parent),
                   "source_paths": self.sources[case], "arm": arm, "stage": stage}
        for key, path in self.sources[case].items():
            raw = read_regular(path, SOURCE_BOUNDS[key]); info = os.stat(path)
            actual = {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "device": info.st_dev,
                      "inode": info.st_ino, "bytes": len(raw)}
            if actual != self.source_proofs[case][key]:
                raise IntegrityError("Frozen case source identity changed")
        precondition = None
        if phase != "create_select":
            raw = read_regular(capsule, 2*MIB); previous = json.loads(raw)
            if previous != self.states[case] or digest(previous["identity"]) != self.identities[case]:
                raise IntegrityError("Case identity/history changed before mutation")
            precondition = {"capsule_sha256": hashlib.sha256(raw).hexdigest(), "identity_sha256": self.identities[case]}
        ticket = self.transport.charge_owned(case, stage) if phase == "execute" else None
        self.files.begin_api_write(case)
        result = self.transport._dispatch(f"{case}.{phase}.stage{stage}", request,
            tickets=(ticket,) if ticket else (), precondition=precondition)
        self.files.finish_api_write(case)
        state = result["state"]
        if json.loads(read_regular(capsule, 2*MIB)) != state:
            raise IntegrityError("Returned state differs from original saved capsule")
        identity = state["identity"]
        if (identity["path"] != str(capsule) or identity["research_dir"] != str(capsule.parent)
            or identity["source_inputs"] != self.source_proofs[case] or identity["discovery_count"] != 32
            or identity["evidence_mode"] != {"R": "retain_first", "W": "withhold_first"}[arm]
            or identity["code_manifest"] != self.transport.config["api_manifest"]
            or identity["runtime_manifest"] != self.transport.config["api_runtime_manifest"]):
            raise IntegrityError("Returned capsule differs from frozen case/source/mode")
        identity_hash = digest(identity)
        if self.transport.bound_identities.get(case) != identity_hash or (case in self.identities and self.identities[case] != identity_hash):
            raise IntegrityError("Native case identity replaced after its pre-T1 binding")
        self.identities[case] = identity_hash
        decision_semantics(state, stage)
        if phase == "execute":
            outcome = state["outcomes"][-1]
            self.ledger.reconcile_saved(ticket, result_hash=digest({"world": state["world"], "receipt": outcome["receipt"]}),
                                        authority_hash=outcome["hash"])
        elif phase == "interpret":
            self.ledger.append("interpretation_durable", {"decision_id": f"{case}.stage{stage}",
                "belief_hash": state["beliefs"][-1]["hash"]})
        self.states[case] = state
        return state

    @staticmethod
    def first_decision_semantics(state):
        from .native_projection import first_decision_semantics
        return first_decision_semantics(state)

    @staticmethod
    def decision_semantics(state, ordinal):
        from .native_projection import decision_semantics
        return decision_semantics(state, ordinal)

    @staticmethod
    def public_outcome_semantics(outcome):
        from .native_projection import public_outcome_semantics
        return public_outcome_semantics(outcome)

    @staticmethod
    def public_probe_semantics(probe):
        from .native_projection import public_probe_semantics
        return public_probe_semantics(probe)

    def first_lifecycle_semantics(self, state):
        from .native_projection import project_native_stage
        from .protocol import digest
        case = next(case for case, identity in self.identities.items() if identity == digest(state["identity"]))
        mapping = {"t1_committed": self._sequence("decision_durable", decision_id=case+".stage1"),
                   "outcome_invoked": None, "outcome_durable": None, "t3_completed": None}
        if state["outcomes"]:
            mapping.update(outcome_invoked=self._sequence("started", slot="owned."+case+".stage1"),
                outcome_durable=self._sequence("durably_consumed", slot="owned."+case+".stage1"),
                t3_completed=self._sequence("interpretation_durable", decision_id=case+".stage1"))
        saved = project_native_stage(state, 1, case_id=case, sequence=mapping)
        return {"null": saved["outcome"] is None, "interpretation": saved["t3"]["semantic"] if saved["t3"] else None}

    def freeze_forecast_set(self, anchor, commands, second, *, commitment):
        from .protocol import digest
        from .ledger import IntegrityError
        world = self.states[anchor["cases"]["R"]]["world"]
        if world != self.states[anchor["cases"]["W"]]["world"] or digest(world) != commitment["source_world_sha256"]:
            raise IntegrityError("Probe source is not the paired complete post-first world")
        descriptor = self._put(f"exports/{anchor['anchor_id']}-forecast.json", "saved_exports",
                               {"commitment": commitment, "post_first_world": world})
        self.forecasts[anchor["anchor_id"]] = commitment
        self.by_anchor[anchor["anchor_id"]]["forecast_commitment"] = descriptor
        self.ledger.append("forecast_artifact_saved", {"anchor_id": anchor["anchor_id"], "descriptor": descriptor})

    def probes(self, anchor, commitment, state):
        from .ledger import IntegrityError
        result = self.transport._dispatch("probes."+anchor["anchor_id"], {"phase": "probes",
            "anchor_id": anchor["anchor_id"], "post_first_world": state["world"], "forecast_commitment": commitment})
        expected = self.probe_records[anchor["anchor_id"]]
        from .protocol import MOVEMENTS
        if result != {"event": "probes_complete", "anchor_id": anchor["anchor_id"], "outcomes": [expected[a] for a in MOVEMENTS]}:
            raise IntegrityError("Probe terminal result differs from acknowledged original outcomes")
        return expected

    def save_anchor(self, anchor, retained, withheld, probes, commitment):
        import hashlib
        from .native_fixture_transport import read_regular
        from .protocol import digest, MIB
        from .ledger import IntegrityError
        row = self.by_anchor[anchor["anchor_id"]]
        if anchor["anchor_id"] in self.saved:
            raise IntegrityError("Anchor cannot be resaved/replaced")
        for arm, state in (("R", retained), ("W", withheld)):
            case = anchor["cases"][arm]
            path = self.files.root/"capsules"/(case+".json")
            raw = read_regular(path, 2*MIB)
            if state != self.states[case] or digest(state["identity"]) != self.identities[case]:
                raise IntegrityError("Final original export changed native identity")
            row["capsules"][arm] = {"path": str(path), "raw_sha256": hashlib.sha256(raw).hexdigest(), "state_sha256": digest(state)}
        self.ledger.append("anchor_saved", {"anchor_id": anchor["anchor_id"], "descriptor": row})
        self.saved[anchor["anchor_id"]] = True
        for case in anchor["cases"].values():
            del self.states[case]
        self.probe_records.pop(anchor["anchor_id"], None)

    def seal_saved_records(self, previous_head):
        from .protocol import digest
        from .ledger import IntegrityError
        if len(self.saved) != 32 or self.ledger.records[-1]["hash"] != previous_head:
            raise IntegrityError("Complete raw seal requires every fixed anchor and current ledger head")
        counts = self.ledger.counters()
        if counts["evidence_loss"] or counts["actual_entries"]["transition"] != counts["durably_consumed"]:
            raise IntegrityError("Unverifiable invocation accounting makes run invalid")
        descriptor = self._put("study-index.json", "saved_exports", self.index)
        resources = self.files.verify_inventory()
        # Resource enforcement is the outer native process, which is still
        # alive. This raw evidence seal never claims its own finalization passed.
        sealed = self.ledger.append("scientific_evidence_sealed", {"index_path": descriptor["path"],
            "index_sha256": descriptor["raw_sha256"], "terminal_state": "complete", "resources": resources,
            "formation": {"scope": "one_run", "source": "frozen_v4", "fixture": False}})
        return {"phase": "report_saved", "index_path": descriptor["path"], "index_sha256": descriptor["raw_sha256"],
                "ledger_path": str(self.ledger.path), "ledger_head": sealed}

    def report_saved(self, seal):
        from .ledger import IntegrityError
        result = self.transport._dispatch("reporter", seal)
        from .scientific_reporter import read_chunked_report
        report = read_chunked_report(result, self.files.root)
        if report.get("saved_records_seal_hash") != seal["ledger_head"]:
            raise IntegrityError("Saved reporter result is not bound to the authenticated raw seal")
        self.candidate_classification = report["classification"]
        # The trusted saved reporter owns only its four pre-reserved fixed
        # report slots. Every actual byte is reconciled after its cold exit.
        inventory = self.files.verify_inventory()
        self.ledger.append("scientific_report_saved", {"report": result, "inventory": inventory})
        self._put("artifact-inventory.json", "manifests", inventory)
        return result

    def run(self):
        from .ledger import IntegrityError
        from .driver import FiniteDriver
        if SCIENTIFIC_ADMISSION_REVIEWED is not True:
            raise IntegrityError("Scientific controller disabled pending exact-source review")
        result = FiniteDriver(self, self.ledger).run()
        result["candidate_classification"] = self.candidate_classification
        return result


def claim_started_marker(files, config, profile_sha256, study_manifest_sha256):
    """A permanent one-attempt marker; failure never chooses another directory."""
    import hashlib, json, os
    from pathlib import Path
    from .native_fixture_transport import read_regular
    from .protocol import canonical
    from .ledger import IntegrityError
    receipt_raw = read_regular(config["admission_receipt_path"], 4096)
    receipt = json.loads(receipt_raw)
    expected = {"decision": "GO", "run_id": RUN_ID, "output_root": config["output_root"],
        "profile_sha256": profile_sha256, "study_manifest_sha256": study_manifest_sha256,
        "started_marker_path": config["started_marker_path"]}
    if config["run_id"] != RUN_ID or receipt != expected:
        raise IntegrityError("Exact scientific source/profile GO receipt absent or different")
    marker = Path(config["started_marker_path"])
    fixed_marker = Path(config["package_root"]).parents[1]/"policy-study-results"/"ONE_SCIENTIFIC_COMPARISON_STARTED.json"
    if marker != fixed_marker:
        raise IntegrityError("Fixed scientific one-attempt marker location differs")
    if any(path.is_symlink() for path in (marker, *marker.parents)):
        raise IntegrityError("Aliased scientific started marker")
    files.reserve_started_marker(marker)
    value = dict(expected, admission_receipt_sha256=hashlib.sha256(receipt_raw).hexdigest())
    raw = canonical(value)+b"\n"
    if len(raw) > 4096:
        raise IntegrityError("Started marker exceeds fixed slot")
    fd = os.open(marker, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o400)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            if count <= 0: raise OSError("Short started marker write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(marker.parent, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(directory)
    finally: os.close(directory)
    return {"marker_path": str(marker), "marker_sha256": hashlib.sha256(raw).hexdigest(), **value}


def failure_status(error, counts, integrity_events, candidate_classification=None):
    """Only a specifically identified resource interruption may be incomplete."""
    import errno
    from .ledger import CapacityError
    resource_error = isinstance(error, (CapacityError, MemoryError, TimeoutError)) or (
        isinstance(error, OSError) and error.errno in (errno.ENOMEM, errno.ENOSPC, errno.EFBIG))
    return "incomplete" if (resource_error and not counts["evidence_loss"] and not integrity_events
                            and candidate_classification != "invalid") else "invalid"


def emit_native_terminal(transport, ledger, status, candidate_classification=None):
    from . import scorer
    counts = ledger.counters()
    exact = counts["actual_entries_exact"]
    def known(category):
        return -1 if exact[category] is None else exact[category]
    transport.emit(10, known("transition"), sum(".stage" in e["worker_id"] for e in ledger._events("worker_admitted")))
    transport.emit(11, known("selecting_backend"), known("producer"))
    classes = (scorer.INVALID, scorer.INCOMPLETE, scorer.ADVERSE, scorer.INCONCLUSIVE,
               scorer.NO_BENEFIT, scorer.PREDICTIVE_ONLY, scorer.FULL_PASS)
    candidate = candidate_classification or (scorer.INVALID if status == "invalid" else scorer.INCOMPLETE)
    if candidate not in classes:
        raise ValueError("Unknown frozen scientific classification")
    transport.emit(12, classes.index(candidate), 0)
    transport.emit(9, counts["decisions_durable_verified"], {"complete": 0, "incomplete": 1, "invalid": 2}[status])


def main():
    # Compiled controller source guards before imports, inputs or output writes.
    if SCIENTIFIC_ADMISSION_REVIEWED is not True:
        raise RuntimeError("Scientific execution is disabled pending exact-source admission")
    import hashlib, json, os, resource, time
    from pathlib import Path
    root = Path(os.environ["ORA_LAUNCHER_PACKAGE_ROOT"])
    manifest_raw = Path(os.environ["ORA_LAUNCHER_MANIFEST_PATH"]).read_bytes()
    if len(manifest_raw) > 65536 or hashlib.sha256(manifest_raw).hexdigest() != os.environ["ORA_LAUNCHER_MANIFEST_SHA256"]:
        raise RuntimeError("Compiler-bound study manifest differs")
    manifest = json.loads(manifest_raw)
    bootstrap = root/"source_bootstrap.py"
    raw = bootstrap.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["source_bootstrap.py"]:
        raise RuntimeError("Captured source bootstrap differs")
    scope = {"__name__": "captured_bootstrap", "__file__": str(bootstrap)}
    exec(compile(raw, str(bootstrap), "exec"), scope)
    finder = scope["PinnedSources"](root, manifest); finder.install()
    from ora_study.scientific_transport import ScientificInventory, ScientificLedger, ScientificTransport
    from ora_study.native_fixture_transport import read_regular
    from ora_study.scientific_controller import (ScientificController as BoundController,
        reserve_controller_inventory as reserve_all, claim_started_marker, failure_status,
        emit_native_terminal)
    from ora_study.native_fixture_controller import _emit
    from ora_study.protocol import MIB, digest
    from ora_study.ledger import IntegrityError, CapacityError
    config_raw = read_regular(os.environ["ORA_LAUNCHER_PROFILE_PATH"], 65536)
    if hashlib.sha256(config_raw).hexdigest() != os.environ["ORA_LAUNCHER_PROFILE_SHA256"]:
        raise IntegrityError("Compiler-bound scientific profile differs")
    config = json.loads(config_raw)
    required = {"schema", "profile", "run_id", "output_root", "api_root", "api_manifest", "python_sha256",
                "api_runtime_manifest", "admission_receipt_path", "started_marker_path", "protocol_sha256"}
    if (set(config) != required or config["schema"] != "ora.scientific.launch.v1"
        or config["profile"] != "prospective_study_v4" or config["run_id"] != RUN_ID
        or config["protocol_sha256"] != "0764aab03b99d59cc9eeb9c3aaeac481beda5c955c860e6c3db5f94fd08bda50"):
        raise IntegrityError("Unknown compiler-bound scientific profile")
    deadline = int(os.environ["ORA_LAUNCHER_DEADLINE_NS"])
    if not 0 < deadline-time.clock_gettime_ns(time.CLOCK_BOOTTIME) <= 850*1000000000:
        raise IntegrityError("Whole-life native expiry missing/out of range")
    if resource.getrlimit(resource.RLIMIT_AS) != (96*MIB, 384*MIB) or len(os.sched_getaffinity(0)) != 1:
        raise IntegrityError("Native controller resource inheritance differs")
    config.update(package_root=str(root), study_manifest=manifest, deadline_ns=deadline)
    worker_path, worker_bytes, _ = finder.modules["ora_study.scientific_worker"]
    files = ScientificInventory(config["output_root"], native_root_precreated=True)
    reserve_all(files)
    ledger = ScientificLedger(files.root/"ledger.jsonl")
    transport = ScientificTransport(files, ledger, worker_bytes, str(worker_path), config, deadline, emit=_emit)
    controller = None
    try:
        files.put_new("frozen-profile.json", "manifests", config)
        marker = claim_started_marker(files, config, os.environ["ORA_LAUNCHER_PROFILE_SHA256"], os.environ["ORA_LAUNCHER_MANIFEST_SHA256"])
        ledger.append("one_attempt_started", marker)
        ledger.append("scientific_source_frozen", {"source_binding": {
            "api_manifest_sha256": digest(config["api_manifest"]), "study_manifest_sha256": digest(manifest),
            "runtime_manifest_sha256": digest(config["api_runtime_manifest"]), "python_sha256": config["python_sha256"],
            "cold_flags": {"isolated": 1, "no_site": 1, "no_bytecode": True}}})
        controller = BoundController(transport)
        result = controller.run()
        counts = ledger.counters()
        status = "invalid" if result["candidate_classification"] == "invalid" else "complete"
        ledger.append("controller_complete", {"candidate_report": result["candidate_report"], "counters": counts})
        files.put_new("controller-terminal.json", "manifests", {"status": status, "counters": counts,
            "ledger": ledger.seal_descriptor(), "report": result["candidate_report"], "requires_outer_terminal_seal": True})
        files.verify_inventory()
        emit_native_terminal(transport, ledger, status, result["candidate_classification"])
        print(json.dumps({"candidate_report": result["candidate_report"], "requires_outer_terminal_seal": True}, separators=(",", ":")), flush=True)
    except BaseException as error:
        try:
            counts = ledger.counters()
            candidate_classification = controller.candidate_classification if controller is not None else None
            status = failure_status(error, counts, ledger._events("integrity_failure"), candidate_classification)
            ledger.append("integrity_failure" if status == "invalid" else "resource_interrupted", {"reason": type(error).__name__, "detail": str(error)[:1024]})
            files.put_new("failure-report.json", "manifests", {"status": status,
                "counters": counts, "reason": type(error).__name__, "scientific_result": None, "requires_outer_terminal_seal": True})
            emit_native_terminal(transport, ledger, status, candidate_classification)
        finally:
            raise
    finally:
        ledger.close(); files.close()


if __name__ == "__main__":
    main()
