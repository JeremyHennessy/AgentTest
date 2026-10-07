"""Independent final-v4 saved-artifact/ledger binding, with no experiment execution.

Native capsules remain the authoritative original files. This module reads one
sealed scientific ledger prefix, verifies its raw chronology, reconstructs the
scorer's global sequences, and keeps lossless references instead of duplicating
capsules or complete cohorts. It never imports an API, policy or world module.
A candidate is provisional until the outer controller seals final resource and
artifact accounting; invalid always dominates incomplete and efficacy.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from . import native_projection as projection
from . import scorer
from .ledger import CapacityError, IntegrityError, _valid_hash
from .native_fixture_transport import read_regular
from .protocol import MIB, canonical, digest, registry, transition_slots, worker_allowances
from .scientific_profile import CALL_CAPS, SLOTS
from .scientific_transport import ScientificLedger

INDEX_SCHEMA = "ora.scientific.study-index.v1"
REPORT_SCHEMA = "ora.scientific.saved-report.v1"
DESCRIPTOR_KEYS = {"path", "raw_sha256", "state_sha256"}
REQUEST_KEYS = {"phase", "index_path", "index_sha256", "ledger_path", "ledger_head"}
SOURCE_KEYS = {"api_manifest_sha256", "study_manifest_sha256", "runtime_manifest_sha256", "python_sha256", "cold_flags"}
ERRORS = (IntegrityError, scorer.SavedDataError, OSError, ValueError, TypeError, KeyError, IndexError, AttributeError)


def require(condition, message):
    if not condition:
        raise IntegrityError(message)


def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "Duplicate saved JSON member")
            out[key] = value
        return out
    def bad_number(value):
        raise IntegrityError("Nonexact saved JSON number")
    return json.loads(raw, object_pairs_hook=unique, parse_float=bad_number, parse_constant=bad_number)


def read_descriptor(description, root, maximum=2 * MIB):
    """Verify both original-byte and parsed-state hashes without copying bytes."""
    require(type(description) is dict and set(description) == DESCRIPTOR_KEYS,
            "Saved descriptor requires path/raw_sha256/state_sha256 only")
    require(all(_valid_hash(description[key]) for key in ("raw_sha256", "state_sha256")),
            "Invalid saved descriptor hash")
    path = Path(description["path"])
    require(path.is_absolute() and ".." not in path.parts and path.is_relative_to(root),
            "Artifact descriptor escapes immutable run root")
    raw = read_regular(path, maximum)
    require(hashlib.sha256(raw).hexdigest() == description["raw_sha256"], "Original artifact bytes changed")
    value = strict_json(raw)
    require(digest(value) == description["state_sha256"], "Artifact state hash changed")
    return value


def compact_stage(stage, descriptor, ordinal):
    """Retain scorer evidence; refer to complete immutable native proof material.

    The full native projection is validated and first-pair equality checked
    before this is called. The common cohort reference is identical across arms;
    the per-run capsule pointer remains provenance, outside logical semantics.
    """
    out = deepcopy(stage)
    t1, original = out["t1"], stage["t1"]
    semantic = t1["semantic"]
    full_semantic_sha256 = digest(semantic)
    for name in ("native_body", "admitted_cases", "native_envelope", "native_status"):
        semantic.pop(name, None)
    view = semantic["view_evidence"]["view"]
    cohort = view.pop("cohort")
    view["cohort_reference"] = {"schema": "ora.immutable-native-cohort.v1", "sha256": digest(cohort),
                                "json_pointer": "/cohort"}
    t1["provenance"] = {key: original["provenance"][key] for key in ("case_id", "decision_id", "run_id")}
    t1["provenance"].update(native_capsule=deepcopy(descriptor), native_ordinal=ordinal,
        full_semantic_sha256=full_semantic_sha256,
        materialized_view_sha256=digest(original["semantic"]["view_evidence"]["view"]),
        projection="ora_study.native_projection.project_native_stage")
    t1["sha256"] = digest(semantic)
    return out


class LedgerAudit:
    """Validate every raw call/charge, including unfinished and unused tickets."""
    def __init__(self, rows, *, broken=False, source_binding=None):
        self.rows, self.broken = rows, broken
        self.source_binding = source_binding
        self.errors = []
        self.by_kind = defaultdict(list)
        for row in rows:
            self.by_kind[row["kind"]].append(row)
        self.admitted, self.completed, self.sources = {}, {}, {}
        self.entries, self.exits = {}, {}
        self.charges, self.slots, self.starts, self.computed, self.durable = {}, {}, {}, {}, {}
        self.decisions_started, self.decisions, self.interpretations = {}, {}, {}
        self.bindings, self.first_gates, self.forecast_sets = {}, {}, {}
        self.actual_transition_slots = {}
        self.uncertain = set()
        self._audit()

    def check(self, label, operation):
        try:
            return operation()
        except ERRORS as exc:
            self.errors.append(label + ": " + str(exc))
            return None

    def _put(self, mapping, key, row, label):
        require(key not in mapping, "Repeated " + label)
        mapping[key] = row

    def _worker_for_slot(self, category, slot):
        if category == "neutral":
            return slot.rsplit(".t", 1)[0]
        if category == "probe":
            return "probes." + slot[len("probe."):].rsplit(".", 1)[0]
        decision = slot[len("owned."):]
        case, stage = decision.rsplit(".", 1)
        return case + ".execute." + stage

    def _first_complete(self, anchor_id, before):
        for arm in ("R", "W"):
            key = f"{anchor_id}.{arm}.stage1"
            decision = self.decisions.get(key)
            require(decision is not None and decision["sequence"] < before, "Second work lacks paired first T1")
            if not decision["payload"]["is_null"]:
                completion = self.interpretations.get(key)
                require(completion is not None and completion["sequence"] < before,
                        "Second work precedes paired first interpretation")

    def _owned_or_probe_gate(self, category, slot, before):
        if category == "neutral":
            layout = int(slot.split(".")[1][len("layout"):])
            t = int(slot.rsplit(".t", 1)[1])
            initial = _one(self.rows, "neutral_initial", layout=layout)
            require(initial["sequence"] < before, "Neutral invocation preceded initial source seal")
            if t > 1:
                previous = self.slots.get(f"neutral.layout{layout}.t{t - 1}")
                require(previous is not None and previous["payload"]["ticket"] in self.durable and
                        self.durable[previous["payload"]["ticket"]]["sequence"] < before,
                        "Neutral invocation preceded previous durable receipt")
            if t > 32:
                require(_one(self.rows, "D_frozen", layout=layout)["sequence"] < before,
                        "Neutral continuation preceded D freeze")
            if t - 1 in scorer.ANCHOR_TIMES:
                require(_one(self.rows, "neutral_anchor_saved", layout=layout, t=t - 1)["sequence"] < before,
                        "Neutral continuation preceded immutable anchor seal")
            return
        if category == "owned":
            decision_id = slot[len("owned."):]
            case, stage = decision_id.rsplit(".stage", 1)
            anchor_id = case.rsplit(".", 1)[0]
            own = self.decisions.get(decision_id)
            require(own is not None and own["payload"]["is_null"] is False,
                    "Owned invocation lacks non-null own T1")
            stage = int(stage)
        else:
            anchor_id = slot[len("probe."):].rsplit(".", 1)[0]
            stage = 2
            action = slot.rsplit(".", 1)[1]
            index = scorer.DIRECTIONS.index(action)
            if index:
                previous = self.slots.get(f"probe.{anchor_id}.{scorer.DIRECTIONS[index - 1]}")
                require(previous is not None and previous["payload"]["ticket"] in self.durable,
                        "Probe invocation preceded prior fixed-order durable probe")
        paired = {}
        for arm in ("R", "W"):
            key = f"{anchor_id}.{arm}.stage{stage}"
            decision = self.decisions.get(key)
            require(decision is not None and decision["sequence"] < before,
                    "Invocation precedes both paired T1 commitments")
            paired[arm] = decision["payload"]["receipt_hash"]
        first_gate = self.first_gates.get(anchor_id)
        require(first_gate is not None and first_gate["sequence"] < before,
                "Invocation precedes complete first-pair equality gate")
        if stage == 2:
            self._first_complete(anchor_id, before)
            frozen = self.forecast_sets.get(anchor_id)
            require(frozen is not None and frozen["sequence"] < before,
                    "Second/probe invocation precedes shared F/world commitment")
            payload = frozen["payload"]
            require(payload["second_T1_sha256"] == paired and payload["both_second_T1_durable"] is True,
                    "F commitment does not bind exact paired second T1s")
            require(_valid_hash(payload["source_world_sha256"]), "F commitment lacks full source-world hash")

    def _audit(self):
        expected = registry()
        allowed_slots = {category: set(values) for category, values in transition_slots().items()}
        total_entries, worker_entries, reserved = Counter(), Counter(), Counter()
        pending_entry = None
        for row in self.rows:
            def visit():
                nonlocal pending_entry
                kind, payload, seq = row["kind"], row["payload"], row["sequence"]
                require(type(payload) is dict, "Ledger event payload is not an object")
                if pending_entry is not None and kind != "started":
                    # A rejected/unfinished entry remains a known attempted call;
                    # it cannot disappear merely because no durable row exists.
                    raise IntegrityError("Observed transition entry lacks adjacent started slot")
                if kind == "registered":
                    require(seq == 0 and payload.get("registry") == expected, "Frozen registry differs")
                    require(payload.get("worker_slots") == list(SLOTS) and payload.get("call_ceilings") == dict(CALL_CAPS),
                            "Frozen worker/call ceilings differ")
                    require(payload.get("automatic_retries") == 0, "Automatic retries are not admitted")
                elif kind == "worker_admitted":
                    worker = payload["worker_id"]
                    require(worker in SLOTS, "Unknown worker")
                    require(payload["allowances"] == worker_allowances(worker), "Altered worker allowance")
                    require(not (set(self.admitted) - set(self.completed)), "Overlapping or post-uncertain workers")
                    self._put(self.admitted, worker, row, "worker admission")
                    reserved.update(payload["allowances"])
                    require(all(reserved[c] <= CALL_CAPS[c] for c in CALL_CAPS), "Global reservations exceeded")
                    if ".create_select." in worker:
                        case = worker.rsplit(".", 2)[0]
                        anchor_id = case.rsplit(".", 1)[0]
                        pair = _one(self.rows, "paired_sources_frozen", anchor_id=anchor_id)
                        require(pair["sequence"] < seq, "Initial worker preceded both immutable source sets")
                        if case.endswith(".W"):
                            require(anchor_id + ".R.stage1" in self.decisions,
                                    "Withhold-first initial worker preceded retain-first T1")
                    if ".stage2" in worker:
                        self._first_complete(worker.split(".")[0] + "." + worker.split(".")[1], seq)
                elif kind == "source_receipt":
                    worker = payload["worker_id"]
                    require(worker in self.admitted and worker not in self.completed, "Source receipt from unadmitted/closed worker")
                    require(set(payload) == SOURCE_KEYS | {"worker_id"}, "Unknown source receipt fields")
                    require(self.source_binding is not None and {k: payload[k] for k in SOURCE_KEYS} == self.source_binding,
                            "Cold source receipt differs from sealed source binding")
                    self._put(self.sources, worker, row, "source receipt")
                elif kind in ("actual_call_entered", "actual_call_exited"):
                    worker, call, category = payload["worker_id"], payload["call_id"], payload["category"]
                    require(worker in self.admitted and worker not in self.completed, "Call from unadmitted/closed worker")
                    require(worker in self.sources, "Call precedes cold source receipt")
                    require(type(call) is int and 1 <= call <= 65535 and category in CALL_CAPS, "Invalid actual-call identity")
                    key = worker, call
                    require(payload.get("overrun") is False, "Observed call overrun")
                    if kind == "actual_call_entered":
                        self._put(self.entries, key, row, "actual function entry")
                        total_entries[category] += 1
                        worker_entries[worker, category] += 1
                        require(total_entries[category] <= CALL_CAPS[category] and
                                worker_entries[worker, category] <= self.admitted[worker]["payload"]["allowances"][category],
                                "Actual function entry exceeds frozen allowance")
                        if category == "transition":
                            available = [charge for ticket, charge in self.charges.items() if ticket not in self.starts and
                                         self._worker_for_slot(charge["payload"]["category"], charge["payload"]["slot"]) == worker]
                            require(len(available) == 1, "Transition entry has no unique charged slot")
                            charge = available[0]["payload"]
                            self._owned_or_probe_gate(charge["category"], charge["slot"], seq)
                            self.actual_transition_slots[key] = charge["slot"]
                            pending_entry = key
                        elif category == "selecting_backend":
                            case, phase, stage = worker.rsplit(".", 2)
                            require(phase in ("create_select", "select"), "Selection entered from wrong phase")
                            key_decision = case + "." + stage
                            require(key_decision in self.decisions_started and key_decision not in self.decisions,
                                    "Selection lacks unique started decision")
                            require(case in self.bindings, "Selection precedes native identity/D/cohort binding")
                        elif category == "producer":
                            require(worker.endswith(".create_select.stage1"), "Producer entered outside initial create worker")
                    else:
                        require(key in self.entries and self.entries[key]["payload"]["category"] == category,
                                "Function exit lacks matching entry")
                        self._put(self.exits, key, row, "actual function exit")
                elif kind == "worker_complete":
                    worker = payload["worker_id"]
                    require(worker in self.admitted and worker in self.sources, "Completed worker lacks admission/source")
                    require({key for key in self.entries if key[0] == worker} == {key for key in self.exits if key[0] == worker},
                            "Completed worker lacks exact function exits")
                    self._put(self.completed, worker, row, "worker completion")
                elif kind == "worker_uncertain":
                    self.uncertain.add(payload["worker_id"])
                elif kind == "charged":
                    ticket, category, slot = payload["ticket"], payload["category"], payload["slot"]
                    require(category in allowed_slots and slot in allowed_slots[category], "Unregistered transition slot")
                    require(payload.get("recomputation_of") is None, "Recomputation is forbidden")
                    self._owned_or_probe_gate(category, slot, seq)
                    self._put(self.charges, ticket, row, "charged ticket")
                    self._put(self.slots, slot, row, "charged slot")
                    require(len(self.charges) <= 512, "Global transition ceiling exceeded")
                elif kind in ("started", "computed", "durably_consumed"):
                    ticket = payload["ticket"]
                    require(ticket in self.charges, "Transition event lacks charged ticket")
                    charge = self.charges[ticket]["payload"]
                    require(all(payload[key] == charge[key] for key in ("category", "slot")), "Transition slot/category changed")
                    target, predecessor = {"started": (self.starts, self.charges), "computed": (self.computed, self.starts),
                                           "durably_consumed": (self.durable, self.computed)}[kind]
                    require(ticket in predecessor and predecessor[ticket]["sequence"] < seq, "Transition lifecycle out of order")
                    self._put(target, ticket, row, kind)
                    if kind == "started":
                        require(pending_entry is not None and self.actual_transition_slots[pending_entry] == payload["slot"],
                                "Started transition lacks exact preceding actual entry")
                        self._owned_or_probe_gate(payload["category"], payload["slot"], seq)
                        pending_entry = None
                    else:
                        require(_valid_hash(payload["result_hash"]), "Missing transition result hash")
                        if kind == "durably_consumed":
                            require(_valid_hash(payload["authority_hash"]) and
                                    payload["result_hash"] == self.computed[ticket]["payload"]["result_hash"],
                                    "Durable transition differs from computed result")
                elif kind == "decision_started":
                    key = payload["decision_id"]
                    require(key in expected["decision_ids"], "Unregistered decision start")
                    if key.endswith("stage2"):
                        self._first_complete(key.rsplit(".", 2)[0], seq)
                    self._put(self.decisions_started, key, row, "decision start")
                elif kind == "decision_durable":
                    key = payload["decision_id"]
                    require(key in self.decisions_started and _valid_hash(payload["receipt_hash"]) and type(payload["is_null"]) is bool,
                            "Durable T1 lacks registered start/hash/null status")
                    case, stage = key.rsplit(".", 1)
                    worker = case + (".create_select." if stage == "stage1" else ".select.") + stage
                    require(worker in self.completed, "Durable T1 precedes cold selection-worker completion")
                    require(sum(entry["payload"]["worker_id"] == worker and entry["payload"]["category"] == "selecting_backend"
                                for entry in self.entries.values()) == 1, "T1 lacks exactly one backend entry")
                    self._put(self.decisions, key, row, "durable T1")
                elif kind == "interpretation_durable":
                    key = payload["decision_id"]
                    require(key in self.decisions and _valid_hash(payload["belief_hash"]), "Interpretation lacks native decision/hash")
                    charge = self.slots.get("owned." + key)
                    require(charge is not None and charge["payload"]["ticket"] in self.durable, "Interpretation precedes durable outcome")
                    case, stage = key.rsplit(".", 1)
                    require(case + ".interpret." + stage in self.completed,
                            "Interpretation receipt precedes cold interpreter completion")
                    self._put(self.interpretations, key, row, "interpretation")
                elif kind == "cohort_reference_bound":
                    case = payload["case_id"]
                    require(case in expected["arm_case_ids"], "Foreign cohort/native binding")
                    worker = case + ".create_select.stage1"
                    require(worker in self.admitted and worker in self.sources and worker not in self.completed,
                            "Native identity binding outside admitted initial worker")
                    producers = [key for key, entry in self.entries.items() if key[0] == worker and
                                 entry["payload"]["category"] == "producer"]
                    require(len(producers) == 1 and producers[0] in self.exits,
                            "Native identity binding lacks exactly one completed producer construction")
                    self._put(self.bindings, case, row, "native identity binding")
                    identities = [binding["payload"]["native_identity"]["run_id"] for binding in self.bindings.values()]
                    require(len(identities) == len(set(identities)), "Native run identity reused")
                elif kind == "first_pair_gate":
                    anchor = payload["anchor_id"]
                    require(_valid_hash(payload["semantics_sha256"]), "First-pair gate lacks semantic hash")
                    require(all(f"{anchor}.{arm}.stage1" in self.decisions for arm in ("R", "W")), "First gate precedes paired first T1")
                    self._put(self.first_gates, anchor, row, "first-pair equality gate")
                elif kind == "forecast_set_frozen":
                    anchor = payload["anchor_id"]
                    require(payload["commands"] == [move for move in scorer.DIRECTIONS if move in payload["commands"]], "Invalid frozen movement set")
                    require(payload["both_second_T1_durable"] is True and payload["second_T1_sha256"] ==
                            {arm: self.decisions[f"{anchor}.{arm}.stage2"]["payload"]["receipt_hash"] for arm in ("R", "W")},
                            "F does not bind both prior second T1s")
                    require(_valid_hash(payload["source_world_sha256"]), "F lacks source-world hash")
                    self._put(self.forecast_sets, anchor, row, "F commitment")
                elif kind in ("integrity_failure", "authority_failure", "source_failure", "leakage_failure"):
                    raise IntegrityError("Controller recorded " + kind)
            self.check(f"ledger[{row['sequence']}] {row['kind']}", visit)
        if pending_entry is not None:
            self.errors.append("Observed transition entry lacks a durable started-slot acknowledgement")
        self.uncertain |= set(self.admitted) - set(self.completed)
        if self.broken or self.uncertain:
            self.errors.append("Independent function counts contain an unknown remainder")

    def counters(self):
        """Exact known entry counts; uncertainty is explicit, never imputed."""
        result = {}
        raw_entries = [row["payload"] for row in self.by_kind["actual_call_entered"]]
        def worker_category(worker):
            if worker not in SLOTS:
                return None
            return ("neutral" if worker.startswith("neutral.") else "probe" if worker.startswith("probes.")
                    else "owned" if ".execute." in worker else None)
        unattributed = any(row.get("category") == "transition" and worker_category(row.get("worker_id")) is None for row in raw_entries)
        for category in ("neutral", "owned", "probe"):
            known = sum(row.get("category") == "transition" and worker_category(row.get("worker_id")) == category for row in raw_entries)
            unknown = self.broken or unattributed or any(worker_allowances(worker)["transition"] > 0 and
                ((category == "neutral" and worker.startswith("neutral.")) or
                 (category == "probe" and worker.startswith("probes.")) or
                 (category == "owned" and ".execute." in worker)) for worker in self.uncertain if worker in SLOTS)
            result[category + "_invocations"] = {"known": known, "unknown": unknown}
            result[category + "_durable"] = {"known": sum(row["payload"].get("category") == category for row in self.by_kind["durably_consumed"]), "unknown": self.broken}
        result["decisions_started"] = {"known": len(self.by_kind["decision_started"]), "unknown": self.broken}
        result["decisions_committed"] = {"known": len(self.by_kind["decision_durable"]), "unknown": self.broken}
        result["core_cycles"] = {"known": sum(row.get("category") == "forbidden_core_cycle" for row in raw_entries), "unknown": self.broken}
        # Historical/provider entry points are absent from the frozen source
        # closure. Zero is justified only after every source receipt is checked.
        source_unknown = self.broken or self.source_binding is None or any(worker not in self.sources for worker in self.admitted)
        for name in ("historical_runs", "provider_calls"):
            result[name] = {"known": 0, "unknown": source_unknown}
        return result


def _one(rows, kind, **matching):
    found = [row for row in rows if row["kind"] == kind and
             all(row["payload"].get(key) == value for key, value in matching.items())]
    require(len(found) == 1, "Expected exactly one " + kind + " binding")
    return found[0]


def _source_values(state, case_id, anchor_id, root, audit):
    identity = state["identity"]
    binding = audit.bindings[case_id]
    require(binding["payload"]["native_identity"] == identity, "Native identity differs from pre-T1 independent binding")
    require(identity["evidence_mode"] == {"R": "retain_first", "W": "withhold_first"}[case_id[-1]] and
            identity["discovery_count"] == 32, "Native arm/discovery identity differs")
    require(digest(identity["code_manifest"]) == audit.source_binding["api_manifest_sha256"] and
            digest(identity["runtime_manifest"]) == audit.source_binding["runtime_manifest_sha256"],
            "Native source/runtime differs from independent source receipt")
    pair = _one(audit.rows, "paired_sources_frozen", anchor_id=anchor_id)
    require(pair["sequence"] < binding["sequence"], "Native binding precedes frozen paired sources")
    require(set(pair["payload"]["source_proofs"]) == {anchor_id + ".R", anchor_id + ".W"}, "Paired source set differs")
    require(pair["payload"]["source_proofs"][case_id] == identity["source_inputs"], "Native source file identity differs")
    values = {}
    for name, proof in identity["source_inputs"].items():
        path = Path(proof["path"])
        require(path.is_absolute() and ".." not in path.parts and path.is_relative_to(root), "Native source escaped run root")
        raw = read_regular(path, 2 * MIB)
        info = path.stat()
        require(proof == {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                          "device": info.st_dev, "inode": info.st_ino, "bytes": len(raw)},
                "Original immutable source file changed")
        peer = pair["payload"]["source_proofs"][anchor_id + (".W" if case_id.endswith(".R") else ".R")][name]
        require((peer["device"], peer["inode"]) != (proof["device"], proof["inode"]) and
                peer["sha256"] == proof["sha256"] and peer["bytes"] == proof["bytes"],
                "Paired sources were not distinct byte-identical frozen files")
        values[name] = strict_json(raw)
    require(digest(values) == pair["payload"]["logical_values_sha256"], "Logical initial source state differs")
    require(values["observations"] == state["frames"] and digest(values["world"]) == identity["initial_world_hash"] and
            digest(values["ora"]) == identity["initial_ora_hash"], "Native initial world/Ora/frame source differs")
    require(identity["initial_frames_hash"] == digest(state["frames"]), "Native initial frame hash differs")
    layout = int(anchor_id.split(".")[0][len("layout"):])
    require(state["frames"] == audit.neutral_frames[layout][:len(state["frames"])] and
            values["world"] == audit.anchor_worlds[anchor_id], "Native paired sources differ from saved neutral anchor")
    frozen = _one(audit.rows, "D_frozen", layout=layout)
    require(frozen["sequence"] < pair["sequence"], "Paired source preceded immutable D")
    frames, projected = state["frames"][:33], projection._rows(state["frames"][:33])
    require(binding["payload"]["D_sha256"] == digest(frames) == frozen["payload"]["D_sha256"] and
            binding["payload"]["projected_D_sha256"] == digest(projected) == frozen["payload"]["projected_D_sha256"] and
            binding["payload"]["cohort_sha256"] == digest(state["cohort"]), "Frozen D/cohort reference differs")
    require(binding["payload"]["reference_case_id"] == f"layout{layout}.t32.R" and
            binding["payload"]["reference_bytes_sha256"] == digest({"frames": frames, "projected_rows": projected, "cohort": state["cohort"]}),
            "Complete D/cohort reference material differs")
    return values


def _stage(state, ordinal, case_id, audit):
    decision, outcome, belief = projection._stage_records(state, ordinal)
    key = f"{case_id}.stage{ordinal}"
    committed = audit.decisions[key]
    require(committed["payload"]["receipt_hash"] == decision["hash"] and
            committed["payload"]["is_null"] == (decision["status"] != "selected"), "Ledger T1 differs from native receipt")
    binding = audit.bindings[case_id]
    require(binding["sequence"] < committed["sequence"], "Native identity was bound after first T1")
    charge = audit.slots.get("owned." + key)
    ticket = charge["payload"]["ticket"] if charge else None
    started = audit.starts.get(ticket)
    durable = audit.durable.get(ticket)
    interpreted = audit.interpretations.get(key)
    require((durable is not None) == (outcome is not None), "Native/ledger durable owned outcome differs")
    require((interpreted is not None) == (belief is not None), "Native/ledger canonical interpretation differs")
    if outcome:
        require(started is not None and durable["payload"]["authority_hash"] == outcome["hash"],
                "Durable ledger outcome authority hash differs")
        if state["outcomes"][-1] == outcome:
            require(durable["payload"]["result_hash"] == digest({"world": state["world"], "receipt": outcome["receipt"]}),
                    "Native final world/receipt differs from independently observed return")
    if belief:
        require(interpreted["payload"]["belief_hash"] == belief["hash"], "Canonical belief differs from ledger")
    # An unfinished actual invocation deliberately has no fictitious durable
    # outcome projection. Its full raw charge/entry/start remains in the audit.
    sequence = {"t1_committed": committed["sequence"],
                "outcome_invoked": started["sequence"] if outcome else None,
                "outcome_durable": durable["sequence"] if outcome else None,
                "t3_completed": interpreted["sequence"] if belief else None}
    return projection.project_native_stage(state, ordinal, case_id=case_id, sequence=sequence)


def _anchor(description, root, audit):
    expected_fields = {"anchor_id", "layout", "neutral_t", "capsules", "probes", "forecast_commitment"}
    require(type(description) is dict and set(description) == expected_fields, "Unknown anchor index fields")
    anchor_id = description["anchor_id"]
    require(anchor_id == f"layout{description['layout']}.t{description['neutral_t']}", "Anchor ID differs from coordinates")
    require((description["layout"], description["neutral_t"]) in scorer.EXPECTED_ANCHORS, "Unknown anchor coordinates")
    require(set(description["capsules"]) == {"R", "W"}, "Anchor must declare both original capsule slots")
    require(type(description["probes"]) is dict and not set(description["probes"]) - set(scorer.DIRECTIONS), "Unknown probe direction")
    states, stages, values = {}, {"R": {}, "W": {}}, {}
    for arm in ("R", "W"):
        descriptor = description["capsules"][arm]
        case_id = anchor_id + "." + arm
        if descriptor is None:
            require(not any(key.startswith(case_id + ".") for key in audit.decisions), "Durable T1 lacks original capsule artifact")
            continue
        state = read_descriptor(descriptor, root)
        require(state["identity"]["path"] == descriptor["path"] and
                state["identity"]["research_dir"] == str(Path(descriptor["path"]).parent), "Descriptor/native capsule path differs")
        require(len(state["frames"]) == description["neutral_t"] + 1, "Capsule prefix differs from fixed anchor time")
        values[arm] = _source_values(state, case_id, anchor_id, root, audit)
        states[arm] = state
        for ordinal in range(1, len(state["decisions"]) + 1):
            stages[arm][str(ordinal)] = _stage(state, ordinal, case_id, audit)
        require(set(stages[arm]) <= {"1", "2"}, "Capsule has extra decisions")
        require(set(stages[arm]) == {key.rsplit("stage", 1)[1] for key in audit.decisions if key.startswith(case_id + ".")},
                "Original capsule omits independently committed decision stage")
        last_outcome = state["outcomes"][-1] if state["outcomes"] else None
        require(digest(state["world"]) == (last_outcome["world_after_hash"] if last_outcome else state["identity"]["initial_world_hash"]),
                "Full final native world hash differs from native lifecycle")
    if not states:
        require(not description["probes"] and description["forecast_commitment"] is None and anchor_id not in audit.first_gates,
                "Index omits capsules for saved paired work")
        return None, None
    first_state = next(iter(states.values()))
    initial = deepcopy(first_state["frames"][-1]["observation"])
    current = initial
    for state in states.values():
        if state["outcomes"]:
            current = state["outcomes"][0]["after_observation"]
            break
    if len(states) == 2:
        require(values["R"] == values["W"], "Paired complete logical source values differ")
        require(projection.first_decision_semantics(states["R"]) == projection.first_decision_semantics(states["W"]),
                "Complete first paired native inputs/menu/cases/selection differ")
        gate = audit.first_gates.get(anchor_id)
        if gate:
            require(gate["payload"]["semantics_sha256"] == digest(projection.first_decision_semantics(states["R"])),
                    "Independent first-pair gate hash differs from full native semantics")
        elif any(stages[arm].get("1", {}).get("outcome") for arm in ("R", "W")):
            raise IntegrityError("First outcomes lack independent complete-semantic pair gate")
        if (all("2" in stages[arm] for arm in ("R", "W")) and
                states["R"]["decisions"][0]["status"] != "selected"):
            require(projection.decision_semantics(states["R"], 2) == projection.decision_semantics(states["W"], 2),
                    "First-null pair differs in complete second native semantics")
    forecast_set, probes = None, {}
    probe_rows = [row for row in audit.by_kind["probe_saved"] if row["payload"].get("anchor_id") == anchor_id]
    require(len(probe_rows) == len(description["probes"]) and
            {row["payload"]["action"]: row["payload"]["descriptor"] for row in probe_rows} == description["probes"],
            "Index omitted or changed independently saved probe artifact")
    require({row["payload"]["ticket"] for row in probe_rows} ==
            {ticket for ticket, row in audit.durable.items() if row["payload"]["category"] == "probe" and
             row["payload"]["slot"].startswith("probe." + anchor_id + ".")},
            "Durable probe lacks corresponding original saved artifact")
    if description["forecast_commitment"] is not None:
        material = read_descriptor(description["forecast_commitment"], root)
        require(set(material) == {"commitment", "post_first_world"}, "F artifact must retain complete post-first world")
        commitment = material["commitment"]
        frozen = audit.forecast_sets[anchor_id]
        artifact = _one(audit.rows, "forecast_artifact_saved", anchor_id=anchor_id)
        require(artifact["payload"]["descriptor"] == description["forecast_commitment"] and artifact["sequence"] > frozen["sequence"],
                "Original forecast artifact differs from ledger file binding")
        require(set(commitment) == {"anchor_id", "commands", "source_world_sha256", "both_second_T1_durable", "second_T1_sha256", "ledger_receipt_sha256"} and
                commitment["ledger_receipt_sha256"] == frozen["hash"] and
                {key: value for key, value in commitment.items() if key != "ledger_receipt_sha256"} == frozen["payload"],
                "Saved F artifact differs from independent ledger commitment")
        source_hash = digest(material["post_first_world"])
        require(source_hash == commitment["source_world_sha256"], "Full post-first world differs from frozen F hash")
        for arm in ("R", "W"):
            state = states[arm]
            _, first_outcome, _ = projection._stage_records(state, 1)
            expected = first_outcome["world_after_hash"] if first_outcome else state["identity"]["initial_world_hash"]
            require(expected == source_hash and state["decisions"][1]["anchor"]["world_hash"] == source_hash,
                    "Paired native first/second world provenance differs from full probe source")
            if first_outcome:
                ticket = audit.slots[f"owned.{anchor_id}.{arm}.stage1"]["payload"]["ticket"]
                require(audit.durable[ticket]["payload"]["result_hash"] ==
                        digest({"world": material["post_first_world"], "receipt": first_outcome["receipt"]}),
                        "First owned observed return differs from full post-first world/receipt")
        forecast_set = {"commands": commitment["commands"], "basis": "D/current_C1",
                        "context_sha256": digest(projection._public_context(current)),
                        "cohort_sha256": digest(states["R"]["cohort"]), "committed_seq": frozen["sequence"]}
        forecast_set["sha256"] = digest(forecast_set)
        for action, descriptor in description["probes"].items():
            saved = read_descriptor(descriptor, root)
            require(set(saved) == {"anchor_id", "action", "source_world_sha256", "forecast_commitment_sha256",
                                   "command", "before_observation", "after_observation", "receipt"}, "Unknown saved probe fields")
            require(saved["anchor_id"] == anchor_id and saved["action"] == action and saved["command"] == {"action": action} and
                    saved["source_world_sha256"] == source_hash and saved["forecast_commitment_sha256"] == digest(commitment),
                    "Probe changed frozen anchor/action/F/world source")
            proof = _one(audit.rows, "probe_saved", anchor_id=anchor_id, action=action)
            require(proof["payload"]["descriptor"] == descriptor, "Probe file descriptor differs from saved ledger receipt")
            ticket = proof["payload"]["ticket"]
            require(audit.charges[ticket]["payload"]["slot"] == f"probe.{anchor_id}.{action}" and
                    audit.durable[ticket]["payload"]["authority_hash"] == digest(saved), "Probe native authority/ticket differs")
            require(artifact["sequence"] < audit.charges[ticket]["sequence"] and
                    audit.computed[ticket]["sequence"] < proof["sequence"] < audit.durable[ticket]["sequence"],
                    "Probe artifact/return/receipt chronology differs")
            body = projection.public_probe_semantics({key: saved[key] for key in ("command", "before_observation", "receipt", "after_observation")})
            body["hashes"] = {key: digest(value) for key, value in body.items()}
            body.update(invoked_seq=audit.starts[ticket]["sequence"], durable_seq=audit.durable[ticket]["sequence"])
            probes[action] = body
    else:
        require(anchor_id not in audit.forecast_sets and not description["probes"], "Saved index omitted frozen F/probe artifacts")
    row = {"layout": description["layout"], "neutral_t": description["neutral_t"],
           "initial_observation": initial, "c0": projection._public_context(initial), "c1": projection._public_context(current),
           "cases": {arm: {"case_id": anchor_id + "." + arm,
                           "stages": {number: compact_stage(stage, description["capsules"][arm], int(number))
                                      for number, stage in stages[arm].items()}} for arm in ("R", "W")},
           "forecast_set": forecast_set, "probes": probes}
    public = {"anchor_id": anchor_id, "first_owned": {arm: deepcopy(stages[arm].get("1", {}).get("outcome")) for arm in ("R", "W")},
              "second_owned": {arm: deepcopy(stages[arm].get("2", {}).get("outcome")) for arm in ("R", "W")}, "probes": deepcopy(probes)}
    return row, public


def _validate_neutral_evidence(audit, root, complete):
    """Reconstruct public prefixes only from saved original neutral messages."""
    audit.neutral_frames, audit.anchor_worlds = {}, {}
    seen_tickets = set()
    for layout in (1, 2, 3, 4):
        initial_rows = [row for row in audit.by_kind["neutral_initial"] if row["payload"].get("layout") == layout]
        if not initial_rows:
            require(not complete, "Completed run lacks neutral initial artifact")
            continue
        require(len(initial_rows) == 1, "Repeated neutral initial artifact")
        initial_row = initial_rows[0]
        initial = read_descriptor(initial_row["payload"]["descriptor"], root)
        require(set(initial) == {"world", "frame"}, "Unknown neutral initial artifact fields")
        frames = [initial["frame"]]
        projection._frames(frames)
        neutral_rows = [row for row in audit.by_kind["neutral_transition_saved"] if row["payload"].get("layout") == layout]
        for number, row in enumerate(neutral_rows, 1):
            payload = row["payload"]
            require(set(payload) == {"event", "layout", "t", "ticket", "command", "before_observation", "after_observation", "receipt"} and
                    payload["event"] == "neutral_transition_saved" and payload["t"] == number and number <= 64,
                    "Neutral saved rows differ from fixed 64-step chronology")
            require(payload["before_observation"] == frames[-1]["observation"], "Neutral public frame continuity differs")
            require(all(payload["receipt"].get(key) == payload["command"].get(key) for key in ("action", "target", "direction")),
                    "Neutral actual command/receipt differs")
            ticket = payload["ticket"]
            require(ticket not in seen_tickets and audit.charges[ticket]["payload"]["slot"] == f"neutral.layout{layout}.t{number}" and
                    audit.durable[ticket]["payload"]["authority_hash"] == digest(payload), "Neutral saved receipt differs from independent durable ticket")
            require(audit.computed[ticket]["sequence"] < row["sequence"] < audit.durable[ticket]["sequence"],
                    "Neutral saved receipt is outside observed-return/durable acknowledgement order")
            seen_tickets.add(ticket)
            frames.append({"observation": payload["after_observation"], "receipt": payload["receipt"]})
        projection._frames(frames)
        audit.neutral_frames[layout] = frames
        complete_rows = [row for row in audit.by_kind["neutral_complete"] if row["payload"].get("layout") == layout]
        if complete_rows:
            require(len(complete_rows) == 1 and len(frames) == 65, "Neutral completion lacks exactly 64 durable outcomes")
            payload = complete_rows[0]["payload"]
            require(payload["actual_transitions"] == 64 and payload["counter_attempt_total"] == 64 and
                    read_descriptor(payload["descriptor"], root) == {"frames": frames}, "Neutral completion/source prefix differs")
        else:
            require(not complete, "Completed run lacks neutral full-prefix seal")
        discovery_rows = [row for row in audit.by_kind["D_frozen"] if row["payload"].get("layout") == layout]
        if discovery_rows:
            require(len(discovery_rows) == 1 and len(frames) >= 33, "D froze outside complete 32-transition prefix")
            d = discovery_rows[0]
            material = {"frames": frames[:33], "projected_rows": projection._rows(frames[:33])}
            require(read_descriptor(d["payload"]["descriptor"], root) == material and
                    d["payload"]["D_sha256"] == digest(material["frames"]) and
                    d["payload"]["projected_D_sha256"] == digest(material["projected_rows"]), "Original frozen D bytes differ")
            require(d["sequence"] > neutral_rows[31]["sequence"] and
                    (len(neutral_rows) == 32 or d["sequence"] < neutral_rows[32]["sequence"]), "D freeze was not before neutral transition 33")
        elif len(frames) > 33:
            raise IntegrityError("Neutral continuation preceded frozen D")
        for row in audit.by_kind["neutral_anchor_saved"]:
            payload = row["payload"]
            if payload.get("layout") != layout:
                continue
            anchor_id, t = payload["anchor_id"], payload["t"]
            require((layout, t) in scorer.EXPECTED_ANCHORS and anchor_id == f"layout{layout}.t{t}" and
                    anchor_id not in audit.anchor_worlds and t < len(frames), "Invalid or repeated neutral anchor")
            value = read_descriptor(payload["descriptor"], root)
            require(set(value) == {"world"} and payload["frames_sha256"] == digest(frames[:t + 1]), "Neutral anchor/full-prefix binding differs")
            ticket = neutral_rows[t - 1]["payload"]["ticket"]
            require(audit.computed[ticket]["payload"]["result_hash"] == digest({"world": value["world"], "receipt": frames[t]["receipt"]}),
                    "Neutral full anchor world differs from observed transition return")
            require(row["sequence"] > audit.durable[ticket]["sequence"], "Neutral anchor precedes durable transition")
            audit.anchor_worlds[anchor_id] = value["world"]
    require(seen_tickets == {ticket for ticket, row in audit.durable.items() if row["payload"]["category"] == "neutral"},
            "Neutral durable receipts missing from saved original evidence")


def _untrusted_failure(request, error):
    return {"schema": REPORT_SCHEMA, "classification": scorer.INVALID,
            "provisional_computed_classification": scorer.INVALID, "scientific_result": None,
            "requires_outer_terminal_seal": True, "errors": [str(error)],
            "saved_request": deepcopy(request), "scientific_denominators": None,
            "raw_artifacts_preserved": True}


def build_saved_report(request):
    """Read a pinned original index and independently verified logical prefix.

    No request counter, sequence, terminal claim or pass boolean is accepted.
    Corrupt artifacts produce an invalid candidate retaining all index references
    and trustworthy sibling anchor summaries; they never select replacement data.
    """
    try:
        require(type(request) is dict and set(request) == REQUEST_KEYS and request["phase"] == "report_saved", "Unknown saved report request")
        require(_valid_hash(request["index_sha256"]) and _valid_hash(request["ledger_head"]), "Missing pinned report/index hash")
        root = Path(request["ledger_path"]).parent
        require(root.is_absolute() and ".." not in root.parts and not any(p.is_symlink() for p in (root, *root.parents)), "Invalid ledger root")
        index_path = Path(request["index_path"])
        require(index_path.is_absolute() and index_path.is_relative_to(root) and ".." not in index_path.parts, "Index escapes run root")
        index_raw = read_regular(index_path, 2 * MIB)
        require(hashlib.sha256(index_raw).hexdigest() == request["index_sha256"], "Pinned index original bytes changed")
        index = strict_json(index_raw)
        require(type(index) is dict and set(index) == {"schema", "registry", "anchors"} and index["schema"] == INDEX_SCHEMA,
                "Unknown scientific study index schema")
        require(index["registry"] == registry(), "Index frozen registry differs")
        require(type(index["anchors"]) is list and len(index["anchors"]) == 32 and
                [row["anchor_id"] for row in index["anchors"]] == [row["anchor_id"] for row in registry()["anchors"]],
                "Index must preserve every fixed anchor slot in order")
        all_rows, broken = ScientificLedger.read_verified(request["ledger_path"])
        match = [row for row in all_rows if row["hash"] == request["ledger_head"]]
        require(len(match) == 1 and match[0]["kind"] == "scientific_evidence_sealed", "Missing independently sealed scientific prefix")
        seal = match[0]
        rows = all_rows[:seal["sequence"] + 1]
        payload = seal["payload"]
        require(set(payload) == {"index_path", "index_sha256", "terminal_state", "resources", "formation"} and
                payload["index_path"] == request["index_path"] and payload["index_sha256"] == request["index_sha256"],
                "Index request differs from independent evidence seal")
        require(payload["terminal_state"] in ("complete", "resource_interrupted", "integrity_failure"), "Unknown sealed terminal state")
        source = _one(rows, "scientific_source_frozen")
        require(set(source["payload"]) == {"source_binding"} and set(source["payload"]["source_binding"]) == SOURCE_KEYS,
                "Invalid independent source binding")
        source_binding = source["payload"]["source_binding"]
        require(all(_valid_hash(source_binding[key]) for key in SOURCE_KEYS - {"cold_flags"}) and
                source_binding["cold_flags"] == {"isolated": 1, "no_site": 1, "no_bytecode": True}, "Invalid frozen source/runtime hashes")
        # A damaged tail strictly after the authenticated scientific seal cannot
        # retroactively invent scientific uncertainty. The outer terminal remains
        # responsible for reporter/finalization failures in that later tail.
        audit = LedgerAudit(rows, broken=False, source_binding=source_binding)
        require(source["sequence"] < min([row["sequence"] for row in audit.admitted.values()] or [seal["sequence"]]),
                "Source manifest froze after worker admission")
    except ERRORS as exc:
        return _untrusted_failure(request, exc)
    errors = list(audit.errors)
    try:
        _validate_neutral_evidence(audit, root, payload["terminal_state"] == "complete")
    except ERRORS as exc:
        errors.append("neutral evidence: " + str(exc))
    anchors, public = [], []
    for description in index["anchors"]:
        try:
            row, evidence = _anchor(description, root, audit)
            if row is not None:
                anchors.append(row)
                public.append(evidence)
        except ERRORS as exc:
            errors.append(description.get("anchor_id", "unknown anchor") + ": " + str(exc))
    data_kind = "synthetic_fixture" if rows[0]["payload"].get("data_kind") == "authored_stub" else "scientific_saved"
    require_kind = rows[0]["payload"].get("data_kind") in ("authored_stub", "scientific")
    if not require_kind:
        errors.append("Unknown independent ledger data kind")
    evidence_hash = digest({"ledger_head": request["ledger_head"], "index_sha256": request["index_sha256"],
                            "audit_errors": errors, "binding_version": REPORT_SCHEMA})
    gates = {name: {"status": "fail" if errors else "pass", "evidence_sha256": evidence_hash} for name in scorer.GATE_NAMES}
    saved = {"schema_version": scorer.SCHEMA_VERSION, "data_kind": data_kind,
             "terminal_state": "integrity_failure" if errors else payload["terminal_state"],
             "freeze": dict(scorer.DOCUMENT_HASHES),
             "registry": [{"layout": row["layout"], "neutral_t": row["t"], "cases": row["cases"]} for row in registry()["anchors"]],
             "anchors": anchors, "gates": gates, "counters": audit.counters(),
             "resources": deepcopy(payload["resources"]), "formation": deepcopy(payload["formation"]),
             "terminal_detail": {"sealed_terminal_state": payload["terminal_state"], "outer_finalization_pending": True}}
    result = scorer.score_saved_study(saved)
    result["errors"] = errors + result["errors"]
    if errors:
        result["classification"] = scorer.INVALID
    result["schema"] = REPORT_SCHEMA
    result["provisional_computed_classification"] = result["classification"]
    result["scientific_result"] = None
    result["requires_outer_terminal_seal"] = True
    result["finalization_status"] = "pending_outer_terminal"
    result["saved_records_seal_hash"] = seal["hash"]
    result["parent_ledger_head"] = seal["hash"]
    result["source_binding"] = deepcopy(source_binding)
    result["raw_public_outcomes"] = public
    result["saved_input"] = {"schema": "ora.scientific.saved-input-reference.v1",
        "index": {"path": str(index_path), "raw_sha256": request["index_sha256"], "state_sha256": digest(index)},
        "ledger_path": request["ledger_path"], "ledger_head": seal["hash"], "index_slots": deepcopy(index["anchors"]),
        "reconstruction": "Verify original capsules and the sealed ledger prefix, then rerun this saved-only reporter."}
    result["raw_invocation_evidence"] = {"charged": [deepcopy(row) for row in audit.by_kind["charged"]],
        "unfinished_started": [deepcopy(row) for ticket, row in audit.starts.items() if ticket not in audit.durable],
        "actual_transition_entries": [deepcopy(row) for row in audit.by_kind["actual_call_entered"] if row["payload"].get("category") == "transition"],
        "uncertain_workers": sorted(audit.uncertain), "verified_scientific_prefix_sequence": seal["sequence"],
        "later_ledger_tail_broken": broken}
    if result.get("scientific_denominators") is not None:
        result["scientific_denominators"]["observed_saved_rows_are_unverified_claims"] = False
        result["scientific_denominators"]["binding"] = "original artifacts and independently verified ledger prefix"
    for anchor in result.get("anchors", []):
        anchor.pop("_actions", None)
    result["reporter_source_sha256"] = hashlib.sha256(read_regular(Path(__file__), 2 * MIB)).hexdigest()
    return result


def chunk_exact_bytes(value, *, maximum=6 * MIB):
    """Lossless bounded file chunks; concatenation is the exact canonical JSON."""
    raw = canonical(value) + b"\n"
    if len(raw) > maximum:
        raise CapacityError("Saved report exceeds aggregate reserved allowance")
    return raw, [raw[offset:offset + 2 * MIB] for offset in range(0, len(raw), 2 * MIB)]


def write_chunked_report(files, value, *, prefix="reports/scientific-report"):
    """Parent-owned inventory writer; never overwrite or retry partial artifacts."""
    require(type(prefix) is str and not Path(prefix).is_absolute() and ".." not in Path(prefix).parts,
            "Invalid report chunk prefix")
    raw, chunks = chunk_exact_bytes(value)
    descriptions = []
    for number, part in enumerate(chunks):
        name = f"{prefix}.part{number:04d}.json-fragment"
        files.put_new(name, "reports", part)
        descriptions.append({"path": str(files.root / name), "bytes": len(part), "raw_sha256": hashlib.sha256(part).hexdigest()})
    return {"schema": "ora.exact-json-chunks.v1", "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "state_sha256": digest(value), "chunks": descriptions}


def _write_exact_new(path, raw, maximum):
    """Exclusive immutable write; retain partial file on failure for inventory."""
    if len(raw) > maximum:
        raise CapacityError("Reporter artifact exceeds its pre-reserved file slot")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Reporter output alias")
    require(path.parent.is_dir(), "Parent must reserve and create report directory before admission")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o400)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            require(written > 0, "Short scientific report write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def report_saved(request):
    """Worker entry: fixed bounded report files and a small descriptor response."""
    result = build_saved_report(request)
    try:
        return _persist_report(request, result)
    except BaseException as error:
        # A validated invalid candidate remains invalid even if no descriptor
        # can be persisted. The typed resource channel must not downgrade it.
        if result.get("classification") == scorer.INVALID:
            raise IntegrityError("Established invalid saved evidence; report persistence failed") from error
        raise


def _persist_report(request, result):
    require(type(request) is dict and set(request) == REQUEST_KEYS, "Cannot persist report for malformed request")
    root = Path(request["ledger_path"]).parent
    require(root.is_absolute() and Path(request["index_path"]).is_relative_to(root), "Invalid report root")
    raw, _ = chunk_exact_bytes(result, maximum=6 * MIB - 16384)
    caps = (2 * MIB, 2 * MIB, 2 * MIB - 16384)
    chunks, offset = [], 0
    for number, cap in enumerate(caps):
        if offset == len(raw):
            break
        part = raw[offset:offset + cap]
        path = root / "reports" / f"scientific-report.part{number}.bin"
        _write_exact_new(path, part, cap)
        chunks.append({"path": str(path), "bytes": len(part), "raw_sha256": hashlib.sha256(part).hexdigest()})
        offset += len(part)
    if offset != len(raw):
        raise CapacityError("Report exhausted fixed chunk reservations")
    manifest = {"schema": "ora.scientific.report-chunks.v1", "classification": result["classification"],
        "provisional_computed_classification": result["classification"], "scientific_result": None,
        "requires_outer_terminal_seal": True, "saved_records_seal_hash": result.get("saved_records_seal_hash"),
        "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(), "state_sha256": digest(result), "chunks": chunks}
    manifest_raw = canonical(manifest) + b"\n"
    path = root / "reports" / "scientific-report.json"
    _write_exact_new(path, manifest_raw, 16384)
    return {"path": str(path), "raw_sha256": hashlib.sha256(manifest_raw).hexdigest(), "state_sha256": digest(manifest)}


def read_chunked_report(descriptor, root):
    """Parent verification of every original report byte and candidate binding."""
    root = Path(root)
    require(descriptor["path"] == str(root / "reports" / "scientific-report.json"), "Unexpected report manifest path")
    manifest = read_descriptor(descriptor, root, 16384)
    require(set(manifest) == {"schema", "classification", "provisional_computed_classification", "scientific_result",
                             "requires_outer_terminal_seal", "saved_records_seal_hash", "bytes", "raw_sha256", "state_sha256", "chunks"} and
            manifest["schema"] == "ora.scientific.report-chunks.v1", "Unknown report chunk manifest")
    try:
        return _read_report_chunks(manifest, root)
    except BaseException as error:
        if manifest["classification"] == scorer.INVALID:
            raise IntegrityError("Verified invalid report manifest; chunk reconstruction failed") from error
        raise


def _read_report_chunks(manifest, root):
    require(1 <= len(manifest["chunks"]) <= 3, "Invalid report chunk count")
    pieces = []
    for number, chunk in enumerate(manifest["chunks"]):
        path = root / "reports" / f"scientific-report.part{number}.bin"
        require(set(chunk) == {"path", "bytes", "raw_sha256"} and chunk["path"] == str(path), "Unexpected report chunk path/fields")
        raw = read_regular(path, 2 * MIB if number < 2 else 2 * MIB - 16384)
        require(len(raw) == chunk["bytes"] and hashlib.sha256(raw).hexdigest() == chunk["raw_sha256"], "Report chunk original bytes differ")
        pieces.append(raw)
    raw = b"".join(pieces)
    require(len(raw) == manifest["bytes"] <= 6 * MIB - 16384 and hashlib.sha256(raw).hexdigest() == manifest["raw_sha256"],
            "Full report original bytes differ")
    report = strict_json(raw)
    require(canonical(report) + b"\n" == raw and digest(report) == manifest["state_sha256"], "Full report state digest differs")
    require(report["classification"] == manifest["classification"] == manifest["provisional_computed_classification"] and
            manifest["scientific_result"] is None and manifest["requires_outer_terminal_seal"] is True and
            report.get("saved_records_seal_hash") == manifest["saved_records_seal_hash"], "Manifest changes provisional result binding")
    return report
