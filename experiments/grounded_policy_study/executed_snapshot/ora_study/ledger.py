"""Single-writer, hash-chained accounting; no simulator imports or callbacks.

A charged ticket is not proof that a transition function actually began. Crashes
leave explicit invocation bounds. Replay never starts work and preserves the
last independently verified prefix if a later record is torn or corrupt.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
from .protocol import LIMITS, CALL_CEILINGS, canonical, digest, registry, transition_slots, worker_slots, worker_allowances

class IntegrityError(RuntimeError):
    pass

class CapacityError(RuntimeError):
    pass

class Ledger:
    def __init__(self, path, *, create=False, data_kind="synthetic_fixture"):
        self.path = Path(path)
        self.records = []
        self.fd = None
        self.broken = False
        self.expected_bytes = 0
        if create:
            if data_kind != "synthetic_fixture":
                raise IntegrityError("Scientific ledger creation disabled pending review")
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.append("registered", {"registry": registry(), "worker_slots":worker_slots(), "limits": LIMITS, "call_ceilings":CALL_CEILINGS, "data_kind": data_kind})
        else:
            self.records, self.broken = self.read_verified(self.path)
            self.expected_bytes = sum(len(canonical(row))+1 for row in self.records)

    @staticmethod
    def read_verified(path):
        rows = []
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                for line in stream:
                    if not line.endswith(b"\n"):
                        return rows, True
                    value = json.loads(line)
                    if canonical(value) + b"\n" != line:
                        return rows, True
                    proof = value.pop("hash")
                    if value.get("sequence") != len(rows) or value.get("previous") != (rows[-1]["hash"] if rows else None) or digest(value) != proof:
                        return rows, True
                    value["hash"] = proof
                    rows.append(value)
        except (OSError, ValueError, TypeError, KeyError):
            return rows, True
        return rows, not rows or rows[0]["kind"] != "registered"

    def append(self, kind, payload):
        if self.fd is None or self.broken:
            raise IntegrityError("Read-only or uncertain ledger cannot resume")
        row = {"sequence": len(self.records), "previous": self.records[-1]["hash"] if self.records else None,
               "kind": kind, "payload": payload, "monotonic_ns": time.monotonic_ns()}
        row["hash"] = digest(row)
        raw = canonical(row) + b"\n"
        if len(raw) > 64 * 1024:
            raise CapacityError("Ledger event exceeds bounded record allowance")
        try:
            # Reject a modified/truncated file rather than silently appending.
            if os.fstat(self.fd).st_size != self.expected_bytes:
                raise IntegrityError("Ledger length changed")
            os.lseek(self.fd, 0, os.SEEK_END)
            view = memoryview(raw)
            while view:
                count = os.write(self.fd, view)
                if count <= 0:
                    raise OSError("short ledger append")
                view = view[count:]
            os.fsync(self.fd)
        except BaseException:
            self.broken = True
            raise
        self.records.append(row)
        self.expected_bytes += len(raw)
        return row["hash"]

    def _events(self, kind):
        return [r["payload"] for r in self.records if r["kind"] == kind]

    def claim_worker(self, worker_id):
        if worker_id not in worker_slots() or any(p["worker_id"]==worker_id for p in self._events("worker_admitted")):
            raise IntegrityError("Unknown/repeated cold worker dispatch")
        if self._events("terminal_reconciliation_started"):
            raise IntegrityError("Terminal reconciliation forbids every later worker")
        allowance=worker_allowances(worker_id)
        for category, ceiling in CALL_CEILINGS.items():
            reserved=sum(p["allowances"][category] for p in self._events("worker_admitted"))
            if reserved+allowance[category]>ceiling:
                raise CapacityError("Source-derived call reservation exhausted: "+category)
        self.append("worker_admitted",{"worker_id":worker_id,"allowances":allowance})
        if worker_id=="terminal_reconciliation":
            self.append("terminal_reconciliation_started",{"worker_id":worker_id})

    def record_actual_call(self, worker_id, call_id, category, *, exited=False):
        if category not in CALL_CEILINGS or type(call_id) is not int or call_id<1:
            raise IntegrityError("Unknown call accounting category/identity")
        if not any(p["worker_id"]==worker_id for p in self._events("worker_admitted")):
            raise IntegrityError("Call from unadmitted worker")
        event="actual_call_exited" if exited else "actual_call_entered"
        records=self._events(event)
        if any(p["worker_id"]==worker_id and p["call_id"]==call_id for p in records):
            raise IntegrityError("Duplicate actual call receipt")
        if exited:
            if not any(p["worker_id"]==worker_id and p["call_id"]==call_id and p["category"]==category for p in self._events("actual_call_entered")):
                raise IntegrityError("Call exit lacks matching entry")
        reservation=next(p for p in self._events("worker_admitted") if p["worker_id"]==worker_id)
        overrun=(not exited and (sum(p["category"]==category for p in records)>=CALL_CEILINGS[category]
            or sum(p["category"]==category and p["worker_id"]==worker_id for p in records)>=reservation["allowances"][category]))
        self.append(event,{"worker_id":worker_id,"call_id":call_id,"category":category,"overrun":overrun})
        if overrun:
            self.append("integrity_failure",{"reason":"Unexpected function frame entered beyond pre-dispatch source reservation","worker_id":worker_id,"category":category})
            raise IntegrityError("Actual overrun persisted; study invalid, body cannot continue")

    def decision_start(self, decision_id):
        if decision_id not in registry()["decision_ids"]:
            raise IntegrityError("Unregistered decision")
        if any(p["decision_id"] == decision_id for p in self._events("decision_started")):
            raise IntegrityError("Decision already started; reconcile instead of replaying")
        self.append("decision_started", {"decision_id": decision_id})

    def decision_commit(self, decision_id, *, receipt_hash, is_null):
        if type(is_null) is not bool or not _valid_hash(receipt_hash):
            raise IntegrityError("Invalid durable decision proof")
        if not any(p["decision_id"] == decision_id for p in self._events("decision_started")):
            raise IntegrityError("Decision has no started slot")
        if any(p["decision_id"] == decision_id for p in self._events("decision_durable")):
            raise IntegrityError("Duplicate durable decision")
        self.append("decision_durable", {"decision_id": decision_id, "receipt_hash": receipt_hash, "is_null": is_null})

    def charge(self, category, slot, *, recomputation_of=None):
        if category not in transition_slots() or slot not in transition_slots()[category]:
            raise IntegrityError("Unregistered transition slot")
        charges = self._events("charged")
        if len(charges) >= LIMITS["transition_invocations"]:
            raise CapacityError("Global invocation ceiling exhausted")
        prior = [p for p in charges if p["slot"] == slot]
        durable = self._events("durably_consumed")
        if any(p["slot"] == slot for p in durable):
            raise IntegrityError("Committed action cannot be replayed")
        if prior:
            # No retry can be authorized simply by changing a ticket or directory.
            raise IntegrityError("Uncommitted invocation needs audited continuation; automatic recomputation disabled")
        if recomputation_of is not None:
            raise IntegrityError("Continuation is not implemented")
        ticket = f"invocation{len(charges) + 1}"
        self.append("charged", {"ticket": ticket, "category": category, "slot": slot, "recomputation_of": None})
        return ticket

    def advance(self, ticket, stage, *, result_hash=None, authority_hash=None):
        charge = next((p for p in self._events("charged") if p["ticket"] == ticket), None)
        if charge is None:
            raise IntegrityError("Worker cannot run without a charged ticket")
        stages = ("started", "computed", "durably_consumed")
        if stage not in stages:
            raise IntegrityError("Unknown transition stage")
        if any(p["ticket"] == ticket for p in self._events(stage)):
            raise IntegrityError("Duplicate transition lifecycle event")
        previous = stages[stages.index(stage)-1] if stage != "started" else "charged"
        if not any(p["ticket"] == ticket for p in self._events(previous)):
            raise IntegrityError("Out-of-order transition lifecycle")
        if stage != "started" and not _valid_hash(result_hash):
            raise IntegrityError("Missing complete result hash")
        if stage == "durably_consumed" and not _valid_hash(authority_hash):
            raise IntegrityError("Missing authoritative persisted proof")
        self.append(stage, {"ticket": ticket, "category": charge["category"], "slot": charge["slot"],
                            "result_hash": result_hash, "authority_hash": authority_hash})

    def reconcile_saved(self, ticket, *, result_hash, authority_hash):
        """Caller supplies independently read/validated durable evidence, not retry.

        No API is called here; integration authority verifier is still required.
        """
        charge = next((p for p in self._events("charged") if p["ticket"] == ticket), None)
        if charge is None or not _valid_hash(result_hash) or not _valid_hash(authority_hash):
            raise IntegrityError("Invalid reconciliation proof")
        consumed = next((p for p in self._events("durably_consumed") if p["ticket"] == ticket), None)
        if consumed:
            if (consumed["result_hash"], consumed["authority_hash"]) != (result_hash, authority_hash):
                raise IntegrityError("Changed committed result")
            return
        if not any(p["ticket"] == ticket for p in self._events("started")):
            raise IntegrityError("Durable evidence has no observed start")
        computed = next((p for p in self._events("computed") if p["ticket"] == ticket), None)
        if computed and computed["result_hash"] != result_hash:
            raise IntegrityError("Computed/durable result mismatch")
        if not computed:
            self.advance(ticket, "computed", result_hash=result_hash)
        self.advance(ticket, "durably_consumed", result_hash=result_hash, authority_hash=authority_hash)

    def counters(self):
        charges = self._events("charged")
        computed = self._events("computed")
        consumed = self._events("durably_consumed")
        # Without a computed result, charge/start only bound actual invocation.
        lower = max(len(computed),sum(p["category"]=="transition" for p in self._events("actual_call_entered")))
        upper = None if self.broken else max(len(charges),lower)
        return {
            "data_kind": self.records[0]["payload"]["data_kind"] if self.records else "unknown",
            "scheduled_arm_cases": 64 if self.records else None,
            "scheduled_decisions": 128 if self.records else None,
            "decisions_started_verified": len(self._events("decision_started")),
            "decisions_durable_verified": len(self._events("decision_durable")),
            "null_decisions_verified": sum(p["is_null"] for p in self._events("decision_durable")),
            "invocations_charged_verified": len(charges),
            "invocations_started_verified": len(self._events("started")),
            "invocations_computed_verified": lower,
            "actual_invocations": lower if upper == lower else None,
            "actual_invocations_lower_bound": lower, "actual_invocations_upper_bound": upper,
            "durably_consumed_verified": len(consumed),
            "durable_by_category_verified": {kind: sum(p["category"] == kind for p in consumed) for kind in transition_slots()},
            "recomputation_charges_verified": sum(p["recomputation_of"] is not None for p in charges),
            "evidence_loss": self.broken,
            "workers_admitted_verified":len(self._events("worker_admitted")),
            "actual_call_entries_verified":{category:sum(p["category"]==category for p in self._events("actual_call_entered")) for category in CALL_CEILINGS},
            "science_transition_invocations": 0,
        }

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

def _valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
