"""Source-only scientific extension of the verified sequential process engine.

No real API is imported here. The authored test port executes only explicitly
supplied stub bytes. The scientific admission remains false at every entrypoint.
The segmented ledger preserves the independently acknowledged ordering:
each observed function entry is fsynced before the child may enter its body.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import subprocess
import sys
import time
from .artifact_inventory import ArtifactInventory, SOURCE_BOUNDS
from .ledger import Ledger, IntegrityError, CapacityError, _valid_hash
from .native_fixture_transport import SequentialNativeTransport, read_regular, _child_setup, _boottime_ns
from .protocol import canonical, digest, registry, worker_allowances, transition_slots, MOVEMENTS, ANCHORS, MIB
from .scientific_profile import (PROFILE, CALL_CAPS, ALLOCATION, SLOTS, LEDGER_CAP,
    LOG_CAP, PIPE_CAP, WORKER_PROTOCOL_CAP, RUN_PROTOCOL_CAP, LEDGER_NAMES, LEDGER_SEGMENT_CAPS)

SCIENTIFIC_ADMISSION_REVIEWED = False
_WORKER_INDEX = {name: index for index, name in enumerate(SLOTS)}


class ScientificInventory(ArtifactInventory):
    """One exclusive root with fixed capsule/source/temp/log/failure reserves."""
    def __init__(self, root, *, native_root_precreated=False):
        root = Path(root).absolute()
        if any(path.is_symlink() for path in (root, *root.parents)):
            raise IntegrityError("Aliased output root")
        if native_root_precreated:
            if not root.is_dir() or {p.name for p in root.iterdir()} != {"launcher.status"}:
                raise IntegrityError("Native root must contain only its terminal reserve")
            if len(read_regular(root / "launcher.status", MIB)) != MIB:
                raise IntegrityError("Native terminal reserve must occupy one MiB")
        else:
            if root.exists():
                raise IntegrityError("One exclusive output root; no reuse or retry")
            root.mkdir(mode=0o700)
        super().__init__(root, allocations=ALLOCATION)
        self.external_artifacts = {}
        self.reserve("launcher.status", "finalization", MIB)
        self.reserve("launcher.stdout", "ledger_and_logs", 16384)
        self.reserve("launcher.stderr", "ledger_and_logs", 16384)
        for name, cap in zip(LEDGER_NAMES, LEDGER_SEGMENT_CAPS):
            self.reserve(name, "ledger_and_logs", cap)
        self.reserve("worker-logs.bin", "ledger_and_logs", LOG_CAP)
        self.reserve("capsules/.one-replacement.tmp", "temporary_peak", 2 * MIB)
        self.reserve(".other-atomic-replacement.tmp", "temporary_peak", MIB)
        (root / "capsules").mkdir()
        for case in PROFILE["case_ids"]:
            self.register_capsule(case)
            for key, cap in SOURCE_BOUNDS.items():
                self.reserve(f"sources/{case}/{key}.json", "source_inputs", cap)
        self.log_bytes = 0
        self.log_fd = os.open(root / "worker-logs.bin", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)

    def reserve_started_marker(self, path):
        """Reserve the permanent attempt marker before the controller creates it.

        Its fixed external location prevents a new output directory from granting
        another attempt. These newly written bytes still belong to this run.
        """
        path = Path(path).absolute()
        if path.is_relative_to(self.root) or any(part.is_symlink() for part in (path, *path.parents)):
            raise IntegrityError("Permanent marker needs its unaliased external location")
        if path.exists():
            raise IntegrityError("Permanent attempt marker already exists; no new attempt")
        name = "external-one-attempt-marker"
        self.reserve(name, "manifests", 4096)
        self.external_artifacts[name] = path

    def put_new(self, name, category, value):
        raw = value if isinstance(value, bytes) else canonical(value) + b"\n"
        if name not in self.records:
            self.reserve(name, category, len(raw))
        item = self.records[name]
        if self.halted or item["category"] != category or item["actual_bytes"] is not None:
            raise IntegrityError("Artifact reservation is unavailable or already written")
        if len(raw) > item["reserved_bytes"]:
            self.halted = True
            raise CapacityError("Artifact exceeds its frozen slot")
        path = self._safe(name)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                view = memoryview(raw)
                while view:
                    count = os.write(fd, view)
                    if count <= 0:
                        raise OSError("Short artifact write")
                    view = view[count:]
                os.fsync(fd)
            finally:
                os.close(fd)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            item["actual_bytes"] = len(raw)
        except BaseException:
            self.halted = True
            raise

    def log(self, raw):
        if self.halted or self.log_bytes + len(raw) > LOG_CAP:
            self.halted = True
            raise CapacityError("Aggregate worker log prefix allocation exhausted")
        view = memoryview(raw)
        while view:
            count = os.write(self.log_fd, view)
            if count <= 0:
                self.halted = True
                raise OSError("Short log write")
            view = view[count:]
        self.log_bytes += len(raw)
        self.records["worker-logs.bin"]["actual_bytes"] = self.log_bytes

    def finish_api_write(self, case_id):
        allowed = {f"{case}.json" for case in self.capsules} | {f"{case}.json.lock" for case in self.capsules}
        if any(path.name not in allowed for path in (self.root / "capsules").iterdir()):
            self.halted = True
            raise IntegrityError("Unexpected or stranded native capsule artifact")
        super().finish_api_write(case_id)

    def verify_inventory(self):
        """Reconcile every extant file, including a partial prefix after failure."""
        total = 0
        for path in self.root.rglob("*"):
            if path.is_symlink():
                raise IntegrityError("Aliased run artifact")
            if path.is_dir():
                continue
            name = str(path.relative_to(self.root))
            if name not in self.records or name in self.external_artifacts:
                raise IntegrityError("Unreserved run artifact: " + name)
            raw = read_regular(path, self.records[name]["reserved_bytes"])
            self.records[name]["actual_bytes"] = len(raw)
            total += len(raw)
        external = {}
        for name, path in self.external_artifacts.items():
            if any(part.is_symlink() for part in (path, *path.parents)):
                raise IntegrityError("Aliased permanent marker")
            if not path.exists():
                external[name] = {"path": str(path), "actual_bytes": 0, "sha256": None}
                continue
            raw = read_regular(path, self.records[name]["reserved_bytes"])
            self.records[name]["actual_bytes"] = len(raw)
            external[name] = {"path": str(path), "actual_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            total += len(raw)
        if total > sum(ALLOCATION.values()):
            raise CapacityError("Whole-run output ceiling exceeded")
        return {**self.summary(), "actual_bytes": total, "external_artifacts": external,
            "integration_status": "Every extant file reconciled to its frozen reservation"}

    def close(self):
        if self.log_fd is not None:
            os.fsync(self.log_fd)
            os.close(self.log_fd)
            self.log_fd = None


class ScientificLedger(Ledger):
    """One canonical hash chain in nine prospectively reserved JSONL segments.

    Records have the established Ledger schema. Segments rotate only before a
    complete record, remain <=2 MiB, and together cannot exceed 17 MiB. This is
    a storage partition, not a counter reset, recovery path, or new run.
    """
    def __init__(self, path, *, authored_fixture=False):
        self.path = Path(path)
        if self.path.name != LEDGER_NAMES[0]:
            raise IntegrityError("Scientific ledger must use its reserved first segment")
        self.records = []
        self.broken = False
        self.expected_bytes = 0
        self.segment_index = 0
        self.segment_bytes = 0
        self.uncertain_workers = set()
        self._index = defaultdict(list)
        self._admitted = {}
        self._entries = {}
        self._exits = set()
        self._totals = defaultdict(int)
        self._worker_totals = defaultdict(int)
        self._reserved = defaultdict(int)
        self.authored_fixture_only = authored_fixture
        self.fd = self._open_segment(0)
        self.append("registered", {"registry": registry(), "profile": dict(PROFILE),
            "worker_slots": SLOTS, "call_ceilings": dict(CALL_CAPS),
            "data_kind": "authored_stub" if authored_fixture else "scientific",
            "source_scientific_admission_reviewed": SCIENTIFIC_ADMISSION_REVIEWED, "automatic_retries": 0})

    def _open_segment(self, index):
        fd = os.open(self.path.parent / LEDGER_NAMES[index], os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            os.close(fd)
            raise
        return fd

    @classmethod
    def read_verified(cls, path):
        path = Path(path)
        rows = []
        if path.name != LEDGER_NAMES[0]:
            return rows, True
        absent = False
        try:
            if any(segment.name not in LEDGER_NAMES for segment in path.parent.glob("ledger.part*.jsonl")):
                return rows, True
            for name, cap in zip(LEDGER_NAMES, LEDGER_SEGMENT_CAPS):
                segment = path.parent / name
                if not segment.exists():
                    absent = True
                    continue
                if absent:
                    return rows, True
                raw = read_regular(segment, cap)
                for line in raw.splitlines(keepends=True):
                    if len(line) > 65536 or not line.endswith(b"\n"):
                        return rows, True
                    value = json.loads(line)
                    if canonical(value) + b"\n" != line:
                        return rows, True
                    proof = value.pop("hash")
                    if (value.get("sequence") != len(rows)
                            or value.get("previous") != (rows[-1]["hash"] if rows else None)
                            or digest(value) != proof):
                        return rows, True
                    value["hash"] = proof
                    rows.append(value)
                if not raw:
                    return rows, True
        except (OSError, ValueError, TypeError, KeyError, IntegrityError):
            return rows, True
        return rows, not rows or rows[0]["kind"] != "registered"

    def seal_descriptor(self):
        """Bind the existing prefix without an API read or another ledger event."""
        segments = []
        for name, cap in zip(LEDGER_NAMES[:self.segment_index + 1], LEDGER_SEGMENT_CAPS):
            raw = read_regular(self.path.parent / name, cap)
            segments.append({"name": name, "prefix_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        return {"head": self.records[-1]["hash"], "sequence": self.records[-1]["sequence"],
                "segments": segments, "total_prefix_bytes": self.expected_bytes}

    def append(self, kind, payload):
        if self.fd is None or self.broken:
            raise IntegrityError("Read-only or uncertain ledger cannot resume")
        # Normalize tuples and other JSON containers once, so replay exposes
        # exactly the same semantic event objects as the live controller.
        payload = json.loads(canonical(payload))
        row = {"sequence": len(self.records), "previous": self.records[-1]["hash"] if self.records else None,
            "kind": kind, "payload": payload, "monotonic_ns": time.monotonic_ns()}
        row["hash"] = digest(row)
        raw = canonical(row) + b"\n"
        if len(raw) > 65536:
            raise CapacityError("Ledger event exceeds bounded record allowance")
        try:
            if os.fstat(self.fd).st_size != self.segment_bytes:
                raise IntegrityError("Ledger length changed")
            if self.segment_bytes + len(raw) > LEDGER_SEGMENT_CAPS[self.segment_index]:
                if self.segment_index + 1 >= len(LEDGER_SEGMENT_CAPS):
                    raise CapacityError("Whole-run ledger prefix allocation exhausted")
                os.fsync(self.fd)
                os.close(self.fd)
                self.fd = None
                self.segment_index += 1
                self.fd = self._open_segment(self.segment_index)
                self.segment_bytes = 0
            if self.expected_bytes + len(raw) > LEDGER_CAP:
                raise CapacityError("Whole-run ledger prefix allocation exhausted")
            os.lseek(self.fd, 0, os.SEEK_END)
            view = memoryview(raw)
            while view:
                count = os.write(self.fd, view)
                if count <= 0:
                    raise OSError("Short ledger append")
                view = view[count:]
            os.fsync(self.fd)
        except BaseException:
            self.broken = True
            raise
        self.expected_bytes += len(raw)
        self.segment_bytes += len(raw)
        self.records.append(row)
        self._index[kind].append(payload)
        return row["hash"]

    def _events(self, kind):
        return self._index[kind]

    def claim_worker(self, worker_id):
        if worker_id not in _WORKER_INDEX or worker_id in self._admitted:
            raise IntegrityError("Unknown or repeated scientific cold worker")
        if self._events("terminal_reconciliation_started"):
            raise IntegrityError("Terminal reconciliation forbids every later worker")
        if self.uncertain_workers and worker_id != "terminal_reconciliation":
            raise IntegrityError("Uncertain response forbids continuation")
        allowance = worker_allowances(worker_id)
        if any(self._reserved[category] + allowance[category] > ceiling for category, ceiling in CALL_CAPS.items()):
            raise CapacityError("Frozen whole-run function reservation exhausted")
        self.append("worker_admitted", {"worker_id": worker_id, "allowances": allowance})
        self._admitted[worker_id] = allowance
        for category, value in allowance.items():
            self._reserved[category] += value
        if worker_id == "terminal_reconciliation":
            self.append("terminal_reconciliation_started", {"worker_id": worker_id})

    def record_actual_call(self, worker_id, call_id, category, *, exited=False):
        if category not in CALL_CAPS or type(call_id) is not int or not 1 <= call_id <= 65535:
            raise IntegrityError("Unknown actual function entry")
        if worker_id not in self._admitted:
            raise IntegrityError("Unadmitted function entry")
        key = worker_id, call_id
        if (exited and (key in self._exits or self._entries.get(key) != category)
                or not exited and key in self._entries):
            raise IntegrityError("Repeated or unmatched function observation")
        overrun = not exited and (self._totals[category] >= CALL_CAPS[category]
            or self._worker_totals[worker_id, category] >= self._admitted[worker_id][category])
        self.append("actual_call_exited" if exited else "actual_call_entered",
            {"worker_id": worker_id, "call_id": call_id, "category": category, "overrun": overrun})
        if exited:
            self._exits.add(key)
        else:
            self._entries[key] = category
            self._totals[category] += 1
            self._worker_totals[worker_id, category] += 1
        if overrun:
            self.append("integrity_failure", {"reason": "Actual frame entry exceeded frozen reservation",
                "worker_id": worker_id, "category": category})
            raise IntegrityError("Actual overrun preserved; continuation refused")

    def counters(self):
        result = super().counters()
        completed = {entry["worker_id"] for entry in self._events("worker_complete")}
        uncertain = self.uncertain_workers | (set(self._admitted) - completed)
        entries = {category: self._totals[category] for category in CALL_CAPS}
        unknown = {category: self.broken or any(self._admitted[worker][category] for worker in uncertain)
                   for category in CALL_CAPS}
        result.update(actual_entries=entries,
            actual_entries_exact={category: None if unknown[category] else entries[category] for category in CALL_CAPS},
            actual_entries_are_lower_bounds=any(unknown.values()),
            reservation_upper_bounds={category: self._reserved[category] for category in CALL_CAPS},
            uncertain_workers=sorted(uncertain), evidence_loss=any(unknown.values()),
            reporting_uncertainty="reporter" in uncertain,
            charged_transitions=len(self._events("charged")), durably_consumed=len(self._events("durably_consumed")),
            scientific_transition_invocations=0 if self.authored_fixture_only else (None if unknown["transition"] else entries["transition"]),
            source_scientific_admission_reviewed=self.records[0]["payload"]["source_scientific_admission_reviewed"])
        result["actual_invocations"] = result["actual_entries_exact"]["transition"]
        result["actual_invocations_lower_bound"] = entries["transition"]
        result["actual_invocations_upper_bound"] = None if self.broken else entries["transition"] + sum(
            max(0, self._admitted[worker]["transition"] - self._worker_totals[worker, "transition"])
            for worker in uncertain)
        result["science_transition_invocations"] = result["scientific_transition_invocations"]
        return result


class ScientificTransport(SequentialNativeTransport):
    """The established cold process core with v4 event/slot validation."""
    def __init__(self, *args, event_handler=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_handler = event_handler
        self._permits = {}
        self._saved_permits = set()
        self._neutral_progress = {}

    def scientific_stage(self, *args, **kwargs):
        if SCIENTIFIC_ADMISSION_REVIEWED is not True:
            raise IntegrityError("Scientific transport disabled pending exact-source admission")
        return self._dispatch(*args, **kwargs)

    def _owned_gate(self, case_id, stage):
        if case_id not in PROFILE["case_ids"] or type(stage) is not int or stage not in (1, 2):
            raise IntegrityError("Unregistered owned decision")
        anchor_id = case_id.rsplit(".", 1)[0]
        decisions = {arm: [row for row in self.ledger._events("decision_durable")
                          if row["decision_id"] == f"{anchor_id}.{arm}.stage{stage}"] for arm in ("R", "W")}
        if any(len(rows) != 1 for rows in decisions.values()) or decisions[case_id[-1]][0]["is_null"]:
            raise IntegrityError("Owned invocation requires both paired T1s and a non-null own decision")
        first = [row for row in self.ledger._events("first_pair_gate") if row.get("anchor_id") == anchor_id]
        if len(first) != 1 or not _valid_hash(first[0].get("semantics_sha256")):
            raise IntegrityError("Owned invocation preceded paired first-input/selection equality")
        if stage == 2:
            frozen = [row for row in self.ledger._events("forecast_set_frozen") if row.get("anchor_id") == anchor_id]
            if (len(frozen) != 1 or frozen[0].get("both_second_T1_durable") is not True
                    or frozen[0].get("second_T1_sha256") != {arm: rows[0]["receipt_hash"] for arm, rows in decisions.items()}
                    or not _valid_hash(frozen[0].get("source_world_sha256"))):
                raise IntegrityError("Second owned invocation preceded paired T1/F/world commitment")

    def charge_owned(self, case_id, stage):
        self._owned_gate(case_id, stage)
        return self.ledger.charge("owned", f"owned.{case_id}.stage{stage}")

    def _validate_request(self, worker_id, request):
        if worker_id not in SLOTS or not isinstance(request, dict):
            raise IntegrityError("Unknown scientific cold-worker request")
        phase = request.get("phase")
        if worker_id.startswith("neutral.layout"):
            if request != {"phase": "neutral", "layout": int(worker_id.rsplit("layout", 1)[1])}:
                raise IntegrityError("Neutral worker accepts only its frozen layout")
        elif worker_id.startswith("probes."):
            if set(request) != {"phase", "anchor_id", "post_first_world", "forecast_commitment"} or phase != "probes" or worker_id != "probes." + request["anchor_id"]:
                raise IntegrityError("Probe worker request differs from fixed anchor")
            self._validate_probe_commitment(request)
        elif worker_id == "reporter":
            if phase != "report_saved":
                raise IntegrityError("Reporter can only read saved artifacts")
        else:
            if set(request) != {"phase", "case_id", "path", "research_dir", "source_paths", "arm", "stage"}:
                raise IntegrityError("Unknown API request fields")
            case = request["case_id"]
            if case not in PROFILE["case_ids"] or request["arm"] != case[-1] or type(request["stage"]) is not int or request["stage"] not in (1, 2):
                raise IntegrityError("Unregistered API case/stage")
            expected = "terminal_reconciliation" if phase == "terminal_reconcile" else f"{case}.{phase}.stage{request['stage']}"
            if worker_id != expected or (phase == "create_select" and request["stage"] != 1):
                raise IntegrityError("API phase or stage differs from admitted slot")
            if set(request["source_paths"]) != set(SOURCE_BOUNDS):
                raise IntegrityError("API source inputs differ from the three frozen slots")

    def _validate_probe_commitment(self, request):
        commitment = request["forecast_commitment"]
        keys = {"anchor_id", "commands", "source_world_sha256", "both_second_T1_durable", "second_T1_sha256", "ledger_receipt_sha256"}
        if not isinstance(commitment, dict) or set(commitment) != keys or commitment["anchor_id"] != request["anchor_id"] or commitment["both_second_T1_durable"] is not True:
            raise IntegrityError("Probe requires the paired durable second T1 commitment")
        if commitment["commands"] != [action for action in MOVEMENTS if action in commitment["commands"]]:
            raise IntegrityError("Forecast set must use unique frozen movement order")
        if digest(request["post_first_world"]) != commitment["source_world_sha256"]:
            raise IntegrityError("Probe source differs from frozen post-first world")
        if set(commitment["second_T1_sha256"]) != {"R", "W"}:
            raise IntegrityError("Both arm decision proofs are required")
        for arm, wanted in commitment["second_T1_sha256"].items():
            records = [event for event in self.ledger._events("decision_durable")
                       if event["decision_id"] == f"{request['anchor_id']}.{arm}.stage2"]
            if len(records) != 1 or records[0]["receipt_hash"] != wanted:
                raise IntegrityError("Probe T1 receipt is not independently durable")
        bound = [row for row in self.ledger.records if row["hash"] == commitment["ledger_receipt_sha256"]]
        if len(bound) != 1 or bound[0]["kind"] != "forecast_set_frozen" or bound[0]["payload"] != {key: value for key, value in commitment.items() if key != "ledger_receipt_sha256"}:
            raise IntegrityError("Forecast set lacks an exact independent ledger seal")

    def _world_event(self, worker_id, request, message):
        event = message["event"]
        if event == "transition_permit":
            category = "neutral" if request["phase"] == "neutral" else "probe" if request["phase"] == "probes" else None
            if category is None or message.get("category") != category:
                raise IntegrityError("Unexpected transition permit category")
            previous = sum(worker == worker_id for worker, _ in self._permits)
            if sum(worker == worker_id for worker, _ in self._saved_permits) != previous:
                raise IntegrityError("Next transition preceded durable previous receipt")
            if category == "neutral":
                progress = self._neutral_progress.get(worker_id)
                if progress is None or (previous >= 32 and not progress["D_frozen"]):
                    raise IntegrityError("Neutral transition preceded initial/D freeze acknowledgement")
                if previous in ANCHORS and previous not in progress["anchors"]:
                    raise IntegrityError("Neutral transition preceded immutable anchor acknowledgement")
            expected = (f"neutral.layout{request['layout']}.t{previous + 1}" if category == "neutral"
                        else f"probe.{request['anchor_id']}.{MOVEMENTS[previous]}" if previous < 4 else None)
            if message.get("slot") != expected or (category == "neutral" and previous >= 64):
                raise IntegrityError("Repeated, out-of-order or excess transition permit")
            if category == "probe" and (message.get("command") != {"action": MOVEMENTS[previous]}
                    or message.get("source_world_sha256") != request["forecast_commitment"]["source_world_sha256"]
                    or message.get("forecast_commitment_sha256") != digest(request["forecast_commitment"])):
                raise IntegrityError("Probe command/source/forecast commitment changed")
            ticket = self.ledger.charge(category, expected)
            self._permits[worker_id, ticket] = expected
            return {"ticket": ticket}
        allowed = ({"neutral_initial", "neutral_transition_saved", "D_frozen", "neutral_anchor_saved"}
                   if request["phase"] == "neutral" else {"probe_saved"} if request["phase"] == "probes" else set())
        if event not in allowed or self.event_handler is None:
            raise IntegrityError("Unexpected world event or missing durable parent handler")
        if request["phase"] == "neutral":
            if message.get("layout") != request["layout"]:
                raise IntegrityError("Neutral event changed layout")
            saved = sum(worker == worker_id for worker, _ in self._saved_permits)
            if event == "neutral_initial":
                if worker_id in self._neutral_progress:
                    raise IntegrityError("Repeated neutral initial event")
            else:
                progress = self._neutral_progress.get(worker_id)
                if progress is None:
                    raise IntegrityError("Neutral event preceded initial acknowledgement")
                if event == "D_frozen" and (saved != 32 or progress["D_frozen"] or len(message.get("frames", ())) != 33):
                    raise IntegrityError("Discovery must freeze once at exactly 32 transitions")
                if event == "D_frozen":
                    # D contains all32 attempted transitions. The policy
                    # projection contains movement rows only; inspect/interact/
                    # take/drop/push receipts remain in the full frozen frames.
                    from .native_projection import _frames, _rows
                    _frames(message["frames"])
                    if canonical(message.get("projected_rows")) != canonical(_rows(message["frames"])):
                        raise IntegrityError("Projected movement rows differ from complete frozen discovery frames")
                if event == "neutral_anchor_saved" and (message.get("t") != saved or saved not in ANCHORS or saved in progress["anchors"] or len(message.get("frames", ())) != saved + 1):
                    raise IntegrityError("Anchor differs from fixed neutral horizon")
        if event in ("neutral_transition_saved", "probe_saved"):
            key = worker_id, message.get("ticket")
            if key not in self._permits or key in self._saved_permits:
                raise IntegrityError("World save lacks one unused precharged permit")
            if not any(row["ticket"] == message["ticket"] for row in self.ledger._events("computed")):
                raise IntegrityError("World save preceded independently observed transition return")
            slot = self._permits[key]
            if event == "neutral_transition_saved" and slot != f"neutral.layout{message.get('layout')}.t{message.get('t')}":
                raise IntegrityError("Neutral saved receipt changed its charged slot")
            if event == "probe_saved" and slot != f"probe.{message.get('anchor_id')}.{message.get('outcome', {}).get('command', {}).get('action')}":
                raise IntegrityError("Probe saved receipt changed its charged slot")
        extra = self.event_handler(worker_id, deepcopy(request), deepcopy(message))
        if extra is None:
            extra = {}
        if not isinstance(extra, dict) or {"accepted", "request_sha256", "ticket"} & set(extra):
            raise IntegrityError("Parent handler attempted to replace protocol authority")
        if event in ("neutral_transition_saved", "probe_saved"):
            self._saved_permits.add((worker_id, message["ticket"]))
        if event == "neutral_initial":
            self._neutral_progress[worker_id] = {"D_frozen": False, "anchors": set()}
        elif event == "D_frozen":
            self._neutral_progress[worker_id]["D_frozen"] = True
        elif event == "neutral_anchor_saved":
            self._neutral_progress[worker_id]["anchors"].add(message["t"])
        return extra

    def _dispatch(self,worker_id,request,*,tickets=(),precondition=None):
        if not self.authored_fixture_only and SCIENTIFIC_ADMISSION_REVIEWED is not True:
            raise IntegrityError("Scientific process dispatch disabled pending exact-source admission")
        self._validate_request(worker_id, request)
        tickets = list(tickets)
        expected_ticket_slot = "owned." + request["case_id"] + ".stage" + str(request["stage"]) if request.get("phase") == "execute" else None
        if len(tickets) != int(expected_ticket_slot is not None):
            raise IntegrityError("Only an execute worker may receive one precharged owned ticket")
        if tickets:
            self._owned_gate(request["case_id"], request["stage"])
            charged = [p for p in self.ledger._events("charged") if p["ticket"] == tickets[0]]
            if len(charged) != 1 or charged[0]["category"] != "owned" or charged[0]["slot"] != expected_ticket_slot:
                raise IntegrityError("Owned worker ticket belongs to another invocation")
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
        completion_emitted=False
        def child_reaped(code):
            nonlocal completion_emitted
            if not completion_emitted:
                # Mark before writing: a failed native event is never retried.
                completion_emitted=True
                self.emit(3,0,code)
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
                    if self.stdout_bytes>RUN_PROTOCOL_CAP: raise CapacityError("Whole-run protocol prefix cap exceeded")
                    # Every worker has a finite protocol prefix, including all
                    # entry/return events, one cohort and one capsule/result.
                    if observed_bytes>WORKER_PROTOCOL_CAP: raise CapacityError("Worker stdout aggregate prefix cap exceeded")
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
                                or identity.get("runtime_manifest")!=self.config["api_runtime_manifest"]
                                or identity.get("discovery_count")!=32
                                or identity.get("selection_backend")!="grounded_policy_v2"):
                                raise IntegrityError("Initial native case/mode/source/runtime identity differs")
                            for source_key,source_path in request["source_paths"].items():
                                raw_source=read_regular(source_path,SOURCE_BOUNDS[source_key]); info=os.stat(source_path)
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
                            self.ledger.append("source_receipt", {"worker_id":worker_id,
                                "api_manifest_sha256":message["api_manifest_sha256"],
                                "study_manifest_sha256":message["study_manifest_sha256"],
                                "runtime_manifest_sha256":digest(message["runtime_manifest"]),
                                "python_sha256":message["python_sha256"],"cold_flags":message["cold_flags"]})
                        elif event in ("transition_permit", "neutral_initial", "neutral_transition_saved", "D_frozen", "neutral_anchor_saved", "probe_saved"):
                            if not self.authored_fixture_only and source_receipts != 1:
                                raise IntegrityError("World operation preceded exact cold source receipt")
                            extra = self._world_event(worker_id, request, message)
                            reply.update(extra)
                            if event == "transition_permit":
                                tickets.append(extra["ticket"])
                        elif event=="stage_complete":
                            if not self.authored_fixture_only and request.get("phase")!="report_saved" and source_receipts!=1:
                                raise IntegrityError("Result lacks exact cold source/runtime receipt")
                            result=message["result"]
                            if message.get("result_sha256")!=digest(result): raise IntegrityError("Child final result digest differs")
                        elif event=="stage_resource_failure":
                            if (worker_id!="reporter" or request.get("phase")!="report_saved"
                                or set(message)!={"event","reason"}
                                or message["reason"] not in ("CapacityError","MemoryError","TimeoutError","OutputResourceError")):
                                raise IntegrityError("Invalid typed reporter resource failure")
                            self.ledger.append("report_resource_failure",{"worker_id":worker_id,"reason":message["reason"]})
                            raise CapacityError("Saved reporter exhausted its fixed resource allocation: "+message["reason"])
                        else: raise IntegrityError("Unknown worker event")
                        answer=canonical(reply)+b"\n"
                        proc.stdin.write(answer); proc.stdin.flush()
                    if len(pending)>PIPE_CAP: raise CapacityError("Worker unterminated frame exceeds cap")
            if pending: raise IntegrityError("Torn final worker frame")
            code=proc.wait(timeout=max(.001,(self.deadline_ns-_boottime_ns())/1e9))
            child_reaped(code)
            if code or result is None: raise IntegrityError("Cold worker failed or omitted complete result")
            entries=[p for p in self.ledger._events("actual_call_entered") if p["worker_id"]==worker_id]
            exits=[p for p in self.ledger._events("actual_call_exited") if p["worker_id"]==worker_id]
            if len(entries)!=len(exits): raise IntegrityError("Cold worker lost function-return evidence")
            if entered != len(tickets):
                raise IntegrityError("Worker did not use exactly its precharged transition permits")
            if request.get("phase") in ("neutral", "probes"):
                required = 64 if request["phase"] == "neutral" else 4
                if entered != required or sum(w == worker_id for w, _ in self._saved_permits) != required:
                    raise IntegrityError("Worker omitted fixed neutral/probe invocation or saved receipt")
                if request["phase"] == "neutral" and self._neutral_progress[worker_id] != {"D_frozen": True, "anchors": set(ANCHORS)}:
                    raise IntegrityError("Neutral worker omitted complete D or fixed anchors")
            self.ledger.append("worker_complete",{"worker_id":worker_id,"result_sha256":digest(result)})
            return result
        except BaseException:
            self.halted=True
            self.ledger.uncertain_workers.add(worker_id)
            try:
                self.ledger.append("worker_uncertain",{"worker_id":worker_id,
                    "actual_counts":"lower_bounds_only" if any(worker_allowances(worker_id).values()) else "science_counts_unchanged"})
            except BaseException:
                self.ledger.broken=True
            if proc is not None and proc.poll() is None: proc.kill()
            if proc is not None:
                code=proc.wait()
                child_reaped(code)
            raise
        finally:
            selector.close()
            if proc is not None:
                for stream in (proc.stdin,proc.stdout,proc.stderr): stream.close()
            self.active=None
