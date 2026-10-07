"""Finite API stage adapter, exercised only against authored fake executives.

This module imports no API and constructs no world or policy input. The disabled
cold worker owns the future actual API binding; the function here only preserves
native create/read/CAS/mutation/read ordering and rejects replay or substitution.
"""
from __future__ import annotations
from .ledger import IntegrityError
from .protocol import registry, digest
from .profiles import SCIENTIFIC_PROFILE,INVARIANT_PROFILE

PHASES = {"create_select", "select", "execute", "interpret", "terminal_reconcile"}

def dispatch_stage(api_type, request, *, cohort_binder=None):
    return _dispatch_stage(api_type,request,cohort_binder=cohort_binder,profile=SCIENTIFIC_PROFILE)

def dispatch_invariant_stage(api_type,request,*,cohort_binder=None):
    """Separate two-observation software profile; never selected by request data."""
    return _dispatch_stage(api_type,request,cohort_binder=cohort_binder,profile=INVARIANT_PROFILE)

def _dispatch_stage(api_type, request, *, cohort_binder, profile):
    """Run one supplied API binding; tests bind an explicit zero-world-call fake.

    The future source-checked cold worker is the only permitted scientific caller.
    This is not an authorization or resource boundary by itself.
    """
    if set(request) != {"phase", "case_id", "path", "research_dir", "source_paths", "arm", "stage"}:
        raise IntegrityError("Unknown stage request fields")
    phase = request["phase"]
    if phase not in PHASES or request["case_id"] not in profile["case_ids"]:
        raise IntegrityError("Unregistered stage")
    if request["arm"] not in ("R", "W") or not request["case_id"].endswith("."+request["arm"]):
        raise IntegrityError("Case/arm mismatch")
    if request["stage"] not in (1, 2) or type(request["stage"]) is not int:
        raise IntegrityError("Unsupported stage ordinal")
    if phase == "create_select":
        if request["stage"] != 1:
            raise IntegrityError("Creation cannot reset a second decision")
        api = api_type.create(request["path"], research_dir=request["research_dir"],
            source_paths=request["source_paths"], discovery_count=profile["discovery_count"], enabled=True,
            selection_backend="grounded_policy_v2",
            evidence_mode="retain_first" if request["arm"] == "R" else "withhold_first")
        state = api.read()
        if state["revision"] != 0 or state["decisions"] or state["outcomes"] or state["attempts"]:
            raise IntegrityError("Create returned a nonfresh capsule")
        if cohort_binder is None:
            raise IntegrityError("First T1 requires a durable D/cohort reference acknowledgement")
        d_hash = digest(state["frames"][:profile["discovery_count"]+1])
        cohort_hash = digest(state["cohort"])
        proof = cohort_binder(request["case_id"], state["frames"][:profile["discovery_count"]+1], state["cohort"], state["identity"])
        if (not isinstance(proof, dict) or proof.get("case_id") != request["case_id"]
                or proof.get("D_sha256") != d_hash or proof.get("cohort_sha256") != cohort_hash
                or not isinstance(proof.get("durable_ack_sha256"), str) or len(proof["durable_ack_sha256"]) != 64):
            raise IntegrityError("Cohort reference acknowledgement differs")
        returned = api.select_next(0)
        after = api.read()
        if after["revision"] != 1 or len(after["decisions"]) != 1 or returned != after["decisions"][0]:
            raise IntegrityError("Initial T1 result differs from durable capsule")
        return {"phase": phase, "state": after, "returned": returned, "cohort_binding":proof}
    api = api_type(request["path"], research_dir=request["research_dir"], enabled=True)
    state = api.read()
    if phase == "terminal_reconcile":
        return {"phase": phase, "state": state, "returned": None,
                "scientific_continuation_permitted": False}
    revision = state["revision"]
    stage = request["stage"]
    if phase == "select":
        if len(state["decisions"]) != stage-1:
            raise IntegrityError("Selection already committed or predecessor absent; never replay")
        returned = api.select_next(revision)
    else:
        if len(state["decisions"]) != stage:
            raise IntegrityError("Wrong latest decision ordinal")
        decision = state["decisions"][-1]
        if decision["ordinal"] != stage or decision["status"] != "selected":
            raise IntegrityError("Null/wrong-stage decision cannot be substituted")
        matches = [a for a in state["attempts"] if a["decision_id"] == decision["id"]]
        if len(matches) != 1:
            raise IntegrityError("Latest decision lacks unique prepared authority")
        attempt = matches[0]
        if phase == "execute":
            if attempt["status"] != "prepared":
                raise IntegrityError("Committed action is reconciliation-only, never replay")
            returned = api.execute(attempt["id"], revision)
        else:
            if attempt["status"] != "committed" or not attempt["outcome_id"]:
                raise IntegrityError("T3 requires a new durable uninterpreted outcome")
            returned = api.interpret(attempt["outcome_id"], revision)
    after = api.read()
    if after["revision"] != revision+1:
        raise IntegrityError("Mutation did not commit exactly one revision")
    collection = {"select":"decisions", "execute":"outcomes", "interpret":"beliefs"}[phase]
    if not after[collection] or returned != after[collection][-1]:
        raise IntegrityError("Returned result differs from saved authoritative record")
    return {"phase": phase, "state": after, "returned": returned}
