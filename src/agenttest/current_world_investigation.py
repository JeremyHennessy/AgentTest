"""Default-off, bounded investigation ownership for the existing planning world.

Only materialized same-world observations enter the unchanged pure policy. This
module never consults the actuator's map or invents inventory/visibility. Its
checkpoint is part of organism.json; Git commit/push, not a local return value,
marks durability in the serialized heartbeat workflow.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import sys

from .action_lab import STATEFUL_WORLD_VERSION
from .grounded_policy import policy
from .grounded_policy.primitives import Conflict, bounded, canonical, digest, label
from .planning_lab import execute_investigation_action

VERSION = "current-world-investigation-v1"
DISCOVERY_LIMIT = 32
MAX_OBSERVATIONS = 8192
MAX_CASES = 2
ACTION_ALLOWANCE = 2
CHECKPOINT_BYTES = 4 * 1024 * 1024
OWNER = "current-world-bounded-investigation"


def execution_manifest() -> dict:
    """Content identity is portable across runner paths and inodes."""
    root = Path(__file__).resolve().parent
    return {"version": VERSION, "policy": policy.VERSION,
            "python": list(sys.version_info[:3]),
            "sources": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted(root.rglob("*.py"))}}


_IMPORT_MANIFEST = execution_manifest()


def execution_hash() -> str:
    current = execution_manifest()
    if current != _IMPORT_MANIFEST:
        raise Conflict("execution_source_changed_after_import")
    return digest(current)


def current_view(state: dict) -> dict:
    """Project actual observations, keeping first delivery and exact source bodies."""
    lab = state.get("planning_lab")
    if not isinstance(lab, dict):
        raise Conflict("planning_world_unavailable")
    if lab.get("world_version") != STATEFUL_WORLD_VERSION or lab.get("bounds") != 2:
        raise Conflict("unsupported_current_world")
    context = policy.normalize_context({"position": lab.get("position"),
                                        "inventory_ids": None, "visible_ids": None})
    if context["position"] is None:
        raise Conflict("current_position_unavailable")
    observations = lab.get("transition_observations")
    if not isinstance(observations, list):
        raise Conflict("transition_observations_unavailable")
    seen, rows, last_cycle = {}, [], -1
    for raw in observations:
        if not isinstance(raw, dict):
            raise Conflict("invalid_transition_observation")
        # Base-world bootstrap and transfer-world outcomes are never current
        # stateful-world evidence, even if their labels or coordinates match.
        if raw.get("world_version") != STATEFUL_WORLD_VERSION:
            continue
        source = label(raw.get("source"), "transition source")
        source_id = label(raw.get("source_id"), "transition source ID")
        identity = source + ":" + source_id
        body = canonical(raw)
        if identity in seen:
            if seen[identity] != body:
                raise Conflict("conflicting_transition_source_body")
            continue
        seen[identity] = body
        before = policy.normalize_context({"position": raw.get("before"),
                                            "inventory_ids": None, "visible_ids": None})
        after = raw.get("after")
        if before["position"] is None or after is None:
            raise Conflict("transition_position_unavailable")
        policy.normalize_context({"position": after})
        cycle = raw.get("cycle")
        if type(cycle) is not int or not last_cycle <= cycle <= state.get("cycles", 0):
            raise Conflict("transition_chronology_invalid")
        last_cycle = cycle
        if raw.get("delta") != [after[i] - before["position"][i] for i in (0, 1)] or type(raw.get("blocked")) is not bool:
            raise Conflict("transition_outcome_inconsistent")
        row = {"event_id": identity, "before_context": before,
               "action": raw.get("action"), "after_position": deepcopy(after),
               "refs": {"before": digest({"world": STATEFUL_WORLD_VERSION, "context": before}),
                        "receipt": digest(raw),
                        "after": digest({"world": STATEFUL_WORLD_VERSION, "position": after})}}
        rows.extend(policy.normalize_rows([row]))
        if len(rows) > MAX_OBSERVATIONS:
            raise Conflict("current_observation_capacity_exhausted")
    observation = {"world_version": STATEFUL_WORLD_VERSION, "bounds": 2,
                   "context": context, "rows": rows}
    return {**observation, "observation_hash": digest(observation)}


def _refs(rows: list[dict]) -> list[dict]:
    return [{"event_id": row["event_id"], "sha256": digest(row)} for row in rows]


def _case_hash(case: dict) -> str:
    return digest({key: value for key, value in case.items() if key != "case_hash"})


def _validate_discovery(lane: dict, view: dict) -> tuple[dict, list[dict]]:
    discovery = lane["discovery"]
    count = len(discovery)
    if canonical(view["rows"][:count]) != canonical(discovery):
        raise Conflict("frozen_discovery_prefix_changed")
    policy.verify_cohort(discovery, lane["cohort"])
    return lane["cohort"], view["rows"][count:]


def consume_prepared_case(state: dict, *, request_id: str) -> dict:
    """Consume only authority prepared in a prior persisted heartbeat."""
    lane = state.get("current_world_investigation")
    result = {"action": None, "execution_kind": "current_world_investigation",
              "owner": OWNER, "status": "no_prepared_case"}
    if not lane or not lane.get("pending_authority"):
        return result
    authority = lane["pending_authority"]
    cases = [case for case in lane.get("cases", []) if case.get("case_id") == authority.get("case_id")]
    try:
        if len(cases) != 1:
            raise Conflict("case_owner_unavailable_or_ambiguous")
        case = cases[0]
        if case.get("owner") != OWNER or authority.get("owner") != OWNER:
            raise Conflict("case_owner_mismatch")
        if case.get("case_hash") != _case_hash(case) or authority.get("case_hash") != case["case_hash"]:
            raise Conflict("prepared_case_content_changed")
        if case.get("prepared_cycle", 0) >= state["cycles"] or case.get("prepared_request_id") == request_id:
            raise Conflict("case_not_prepared_by_previous_heartbeat")
        attempts = lane.get("attempts", [])
        if (lane.get("version") != VERSION or lane.get("owner") != OWNER
                or len(lane.get("cases", [])) > MAX_CASES
                or len(attempts) >= ACTION_ALLOWANCE
                or lane.get("actions_remaining") != ACTION_ALLOWANCE - len(attempts)
                or authority.get("allowance") != 1):
            raise Conflict("action_allowance_or_checkpoint_invalid")
        if case.get("execution_hash") != execution_hash():
            raise Conflict("prepared_execution_version_changed")
        view = current_view(state)
        if case.get("observation_hash") != view["observation_hash"]:
            raise Conflict("prepared_world_observation_or_evidence_changed")
        cohort, evidence = _validate_discovery(lane, view)
        policy.verify_evaluation(lane["discovery"], view["context"], evidence, case["decision"])
        action = case["decision"]["selected_action"]
        if action is None or action != authority.get("action"):
            raise Conflict("null_or_unowned_selection")
        if any(attempt.get("case_id") == case["case_id"] for attempt in lane.get("attempts", [])):
            raise Conflict("case_already_attempted")
    except (Conflict, KeyError, TypeError) as error:
        lane["pending_authority"] = None
        lane["status"] = "blocked"
        lane.setdefault("rejections", []).append({"case_id": authority.get("case_id"),
            "cycle": state["cycles"], "request_id": request_id, "reason": str(error)})
        result.update(status="rejected", reason=str(error))
        return result

    index = len(lane["attempts"]) + 1
    attempt_id = f"CWA{index:06d}"
    # Retire authority before the internal calculation. A failed cycle is never
    # reused from a partially saved local state. Only an exact clean remote
    # pending snapshot can recompute this uncommitted calculation.
    lane["pending_authority"] = None
    execution = execute_investigation_action(state, action=action,
        case_id=case["case_id"], attempt_id=attempt_id)
    lane["actions_remaining"] -= 1
    outcome_id, belief_id = f"CWO{index:06d}", f"CWB{index:06d}"
    attempt = {"attempt_id": attempt_id, "case_id": case["case_id"], "case_hash": case["case_hash"],
               "request_id": request_id, "cycle": state["cycles"], "action": action,
               "outcome_id": outcome_id, "belief_id": belief_id}
    outcome = {"outcome_id": outcome_id, "attempt_id": attempt_id,
               "case_id": case["case_id"], "execution": deepcopy(execution)}
    after_view = current_view(state)
    _, after_evidence = _validate_discovery(lane, after_view)
    updated = policy.evaluate(cohort, case["decision"]["context"], after_evidence)
    policy.verify_evaluation(lane["discovery"], case["decision"]["context"], after_evidence, updated)
    belief = {"belief_id": belief_id, "case_id": case["case_id"], "outcome_id": outcome_id,
              "context": deepcopy(case["decision"]["context"]), "decision": updated,
              "evidence_hash": digest(_refs(after_evidence)), "learning_success": "not_established"}
    for record in (attempt, outcome, belief):
        record["content_hash"] = digest(record)
    lane["attempts"].append(attempt)
    lane["outcomes"].append(outcome)
    lane["beliefs"].append(belief)
    lane["status"] = "active" if lane["actions_remaining"] else "exhausted"
    bounded(lane, CHECKPOINT_BYTES, "current-world checkpoint")
    return {**execution, "owner": OWNER, "case_id": case["case_id"], "case_hash": case["case_hash"],
            "attempt_id": attempt_id, "outcome_id": outcome_id, "belief_id": belief_id}


def prepare_next_case(state: dict, *, request_id: str) -> dict:
    """Freeze genuine D once; prepare the next owned case without any action."""
    lane = state.get("current_world_investigation")
    if lane and lane.get("status") in {"blocked", "null", "exhausted", "disabled"}:
        return {"status": lane["status"], "case_id": None}
    try:
        view = current_view(state)
        if lane is None:
            discovery = deepcopy(view["rows"][:DISCOVERY_LIMIT])
            # A missing genuine prefix is a truthful null, not synthetic seeding.
            cohort = policy.build_cohort(discovery)
            lane = {"version": VERSION, "owner": OWNER, "world_version": STATEFUL_WORLD_VERSION,
                    "discovery_limit": DISCOVERY_LIMIT, "discovery": discovery,
                    "cohort": cohort, "actions_remaining": ACTION_ALLOWANCE,
                    "cases": [], "attempts": [], "outcomes": [], "beliefs": [],
                    "rejections": [], "pending_authority": None, "status": "active"}
            state["current_world_investigation"] = lane
        if lane.get("pending_authority") is not None:
            raise Conflict("unconsumed_authority")
        if len(lane["cases"]) >= MAX_CASES or not lane["actions_remaining"]:
            lane["status"] = "exhausted"
            return {"status": "exhausted", "case_id": None}
        # Leave room for every remaining owned outcome without truncating D/U.
        if len(view["rows"]) + lane["actions_remaining"] > MAX_OBSERVATIONS:
            raise Conflict("insufficient_observation_completion_reserve")
        cohort, evidence = _validate_discovery(lane, view)
        decision = policy.evaluate(cohort, view["context"], evidence)
        policy.verify_evaluation(lane["discovery"], view["context"], evidence, decision)
        case = {"case_id": f"CWC{len(lane['cases']) + 1:06d}", "owner": OWNER,
                "question": "Which permitted movement best distinguishes the observation-derived models here?",
                "prepared_cycle": state["cycles"], "prepared_request_id": request_id,
                "execution_hash": execution_hash(), "observation_hash": view["observation_hash"],
                "world_version": view["world_version"], "discovery_hash": digest(lane["discovery"]),
                "evidence_refs": _refs(evidence), "decision": decision}
        case["case_hash"] = _case_hash(case)
        lane["cases"].append(case)
        action = decision["selected_action"]
        if action is None:
            lane["status"] = "null"
        else:
            lane["pending_authority"] = {"owner": OWNER, "case_id": case["case_id"],
                "case_hash": case["case_hash"], "action": action, "allowance": 1}
        bounded(lane, CHECKPOINT_BYTES, "current-world checkpoint")
        return {"status": "prepared" if action else "null", "case_id": case["case_id"],
                "case_hash": case["case_hash"], "selected_action": action}
    except (Conflict, KeyError, TypeError) as error:
        if lane is None:
            lane = {"version": VERSION, "owner": OWNER, "cases": [], "attempts": [],
                    "outcomes": [], "beliefs": [], "actions_remaining": 0, "rejections": []}
            state["current_world_investigation"] = lane
        lane["status"], lane["pending_authority"] = "blocked", None
        lane["rejections"].append({"cycle": state["cycles"], "request_id": request_id, "reason": str(error)})
        return {"status": "blocked", "case_id": None, "reason": str(error)}


def disable_prepared_case(state: dict) -> None:
    """One-way rollback preserves all records and retires pending authority."""
    lane = state.get("current_world_investigation")
    if lane and lane.get("status") != "disabled":
        lane["rollback"] = {"cycle": state["cycles"], "reason": "current_world_mode_disabled",
                            "retired_authority": deepcopy(lane.get("pending_authority"))}
        lane["pending_authority"] = None
        lane["status"] = "disabled"
