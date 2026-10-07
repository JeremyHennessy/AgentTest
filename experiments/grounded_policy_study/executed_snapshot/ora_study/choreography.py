"""Pure lifecycle ordering checks; never calls an API or materializes study data."""
from __future__ import annotations
from .ledger import IntegrityError, _valid_hash
from .protocol import ARMS, MOVEMENTS, registry

class Choreography:
    def __init__(self):
        self.anchors = {a["anchor_id"]: {"prepared": None, "created": set(), "first_t1": {}, "first_t3": {},
            "second_t1": {}, "second_t3": set(), "probes": set(), "first_world": {}}
            for a in registry()["anchors"]}
        self.sealed = False

    def note(self, anchor_id, event, *, arm=None, semantic_hash=None, is_null=None, action=None):
        if self.sealed or anchor_id not in self.anchors:
            raise IntegrityError("Unknown/closed anchor")
        state = self.anchors[anchor_id]
        if event in ("first_t1", "first_t3", "second_t1") and not _valid_hash(semantic_hash):
            raise IntegrityError("Missing semantic equality proof")
        if event not in ("probe", "pair_prepared") and arm not in ARMS:
            raise IntegrityError("Unknown arm")
        if event == "pair_prepared":
            if state["prepared"] is not None or not _valid_hash(semantic_hash):
                raise IntegrityError("Both immutable logical input sets must be bound exactly once")
            state["prepared"] = semantic_hash
        elif event == "created":
            if state["prepared"] is None:
                raise IntegrityError("Both separate logical source sets must be frozen before create")
            if arm == "W" and "R" not in state["first_t1"]:
                raise IntegrityError("Serial initial workers must use fixed R then W order")
            if arm in state["created"]:
                raise IntegrityError("Capsule recreation prohibited")
            state["created"].add(arm)
        elif event == "first_t1":
            if arm not in state["created"] or arm in state[event] or type(is_null) is not bool:
                raise IntegrityError("Fresh arm capsule must precede its own first selection")
            if state[event] and next(iter(state[event].values())) != (semantic_hash, is_null):
                raise IntegrityError("First selections differ")
            state[event][arm] = (semantic_hash, is_null)
        elif event == "first_t3":
            if set(state["first_t1"]) != set(ARMS) or arm in state[event]:
                raise IntegrityError("Both first T1 receipts precede first effects")
            # Full outcome/current-context/lifecycle proof supplied by adapter.
            if state[event] and next(iter(state[event].values())) != semantic_hash:
                raise IntegrityError("Actual first outcome/lifecycle differs")
            state[event][arm] = semantic_hash
        elif event == "second_t1":
            if set(state["first_t3"]) != set(ARMS) or arm in state[event]:
                raise IntegrityError("Both first T3 completions precede second selection")
            if state["first_t1"][arm][1] and state[event] and next(iter(state[event].values())) != semantic_hash:
                raise IntegrityError("First-null pair differs at stage two")
            state[event][arm] = semantic_hash
        elif event == "probe":
            if set(state["second_t1"]) != set(ARMS) or action not in MOVEMENTS or action in state["probes"]:
                raise IntegrityError("Common probes require both second T1 receipts; each action once")
            state["probes"].add(action)
        elif event == "second_t3":
            if set(state["second_t1"]) != set(ARMS) or arm in state[event]:
                raise IntegrityError("Both second T1 receipts precede second effects")
            state[event].add(arm)
        else:
            raise IntegrityError("Unsupported study event")

    def seal(self):
        if self.sealed or any(a["second_t3"] != set(ARMS) or a["probes"] != set(MOVEMENTS) for a in self.anchors.values()):
            raise IntegrityError("All fixed slots must finish before records seal")
        self.sealed = True

    def permit_report(self):
        if not self.sealed:
            raise IntegrityError("Efficacy reporter cannot unblind before records seal")
