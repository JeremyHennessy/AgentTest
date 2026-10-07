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

LEGACY_VERSION = "current-world-investigation-v1"
VERSION = "current-world-investigation-v3"
CONTEXT_REVISION_VERSION = "observed-transition-revision-v1"
REVISION_VERSION = "observed-effect-revision-v1"
MAX_DISCOVERY_ADDITIONS = 32
MAX_REVISED_DISCOVERY = 64
MAX_DISCOVERY_REVISIONS = 1
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


def _base_discovery(lane: dict, view: dict) -> tuple[list[dict], dict]:
    discovery = lane["discovery"]
    if canonical(view["rows"][:len(discovery)]) != canonical(discovery):
        raise Conflict("frozen_discovery_prefix_changed")
    policy.verify_cohort(discovery, lane["cohort"])
    return discovery, lane["cohort"]


def _signature(row: dict, recipe: str) -> str:
    if recipe == CONTEXT_REVISION_VERSION:
        # Historical reader only: never relabel or reinterpret a saved revision.
        return digest({key: row[key] for key in ("before_context", "action", "after_position")})
    if recipe != REVISION_VERSION:
        raise Conflict("unsupported_discovery_revision_recipe")
    before, after = row["before_context"]["position"], row["after_position"]
    return digest({"action": row["action"],
                   "displacement": [after[index] - before[index] for index in (0, 1)]})


def _promotions(discovery: list[dict], rows: list[dict], *, recipe: str = REVISION_VERSION) -> list[dict]:
    seen = {_signature(row, recipe) for row in discovery}
    additions = []
    for row in rows[len(discovery):]:
        signature = _signature(row, recipe)
        if signature in seen:
            continue
        seen.add(signature)
        additions.append(deepcopy(row))
        if len(additions) == MAX_DISCOVERY_ADDITIONS:
            break
    return additions


def model_structure_changes(before: dict, after: dict) -> list[dict]:
    """Compare representation, never posterior weights, support counts or scores."""
    changes = []
    for old, new in zip(before["actions"], after["actions"]):
        old_models = {canonical(model["structure"]): model["structure"] for model in old["models"]}
        new_models = {canonical(model["structure"]): model["structure"] for model in new["models"]}
        added, removed = new_models.keys() - old_models.keys(), old_models.keys() - new_models.keys()
        if added or removed or old["status"] != new["status"]:
            changes.append({"action": new["action"], "before_status": old["status"],
                            "after_status": new["status"],
                            "added_structures": [deepcopy(new_models[key]) for key in sorted(added)],
                            "removed_structures": [deepcopy(old_models[key]) for key in sorted(removed)]})
    return changes


def _revision(lane: dict, revision_id: str) -> dict:
    revisions = lane.get("discovery_revisions", [])
    matches = [row for row in revisions if row.get("revision_id") == revision_id]
    if len(revisions) > MAX_DISCOVERY_REVISIONS or len(matches) != 1:
        raise Conflict("missing_or_ambiguous_discovery_revision")
    revision = matches[0]
    if (revision.get("version") not in {CONTEXT_REVISION_VERSION, REVISION_VERSION}
            or revision.get("revision_hash") != digest({key: value for key, value in revision.items() if key != "revision_hash"})
            or revision.get("parent_discovery_hash") != digest(lane["discovery"])
            or revision.get("parent_cohort_hash") != lane["cohort"]["cohort_digest"]
            or len(revision["discovery"]) > MAX_REVISED_DISCOVERY
            or len(revision["promoted_refs"]) > MAX_DISCOVERY_ADDITIONS):
        raise Conflict("discovery_revision_content_changed")
    policy.verify_cohort(lane["discovery"], lane["cohort"])
    policy.verify_cohort(revision["discovery"], revision["cohort"])
    if model_structure_changes(lane["cohort"], revision["cohort"]) != revision["structural_changes"]:
        raise Conflict("discovery_revision_structure_mismatch")
    return revision


def verify_case_revision(lane: dict, case: dict) -> None:
    """Historical cases resolve their own immutable cohort without execution pins."""
    revision_id = case.get("discovery_revision_id")
    if revision_id is None:
        discovery, cohort = lane["discovery"], lane["cohort"]
        policy.verify_cohort(discovery, cohort)
    else:
        revision = _revision(lane, revision_id)
        if case.get("discovery_revision_hash") != revision["revision_hash"]:
            raise Conflict("case_discovery_revision_mismatch")
        discovery, cohort = revision["discovery"], revision["cohort"]
    if (case.get("discovery_hash") != digest(discovery)
            or case["decision"]["cohort_digest"] != cohort["cohort_digest"]):
        raise Conflict("case_discovery_cohort_mismatch")


def discovery_partition(lane: dict, view: dict, case: dict | None = None) -> tuple[list[dict], dict, list[dict]]:
    """Each revision has disjoint D/U; every actual row retains exactly one role."""
    discovery, cohort = _base_discovery(lane, view)
    revision_id = case.get("discovery_revision_id") if case is not None else lane.get("active_discovery_revision_id")
    if revision_id is not None:
        revision = _revision(lane, revision_id)
        count = revision["source_row_count"]
        if type(count) is not int or not len(discovery) <= count <= len(view["rows"]):
            raise Conflict("revision_source_cutoff_unavailable")
        source = view["rows"][:count]
        if digest(_refs(source)) != revision["source_rows_hash"]:
            raise Conflict("revision_source_history_changed")
        additions = _promotions(discovery, source, recipe=revision["version"])
        if (revision["promoted_refs"] != _refs(additions)
                or canonical(revision["discovery"]) != canonical(discovery + additions)):
            raise Conflict("revision_promotion_recipe_mismatch")
        discovery, cohort = revision["discovery"], revision["cohort"]
    if case is not None:
        verify_case_revision(lane, case)
    discovery_ids = {row["event_id"] for row in discovery}
    evidence = [row for row in view["rows"] if row["event_id"] not in discovery_ids]
    return discovery, cohort, evidence


def _can_revise_null(lane: dict) -> bool:
    """One deliberate v1-null migration also accepts its preserved gate-off state."""
    if (lane.get("revision_attempt") or lane.get("discovery_revisions")
            or lane.get("pending_authority") or len(lane.get("cases", [])) != 1
            or lane["cases"][0]["decision"]["selected_action"] is not None
            or lane.get("attempts") or lane.get("outcomes") or lane.get("beliefs")
            or lane.get("actions_remaining") != ACTION_ALLOWANCE):
        return False
    return (lane.get("version") in {LEGACY_VERSION, VERSION} and lane.get("status") == "null"
            or lane.get("version") == LEGACY_VERSION and lane.get("status") == "disabled")


def _prepare_revision(lane: dict, view: dict, state: dict, request_id: str) -> dict | None:
    discovery, cohort = _base_discovery(lane, view)
    verify_case_revision(lane, lane["cases"][0])
    if lane["cases"][0].get("case_hash") != _case_hash(lane["cases"][0]):
        raise Conflict("original_null_case_content_changed")
    additions = _promotions(discovery, view["rows"])
    if not additions:
        return None
    if len(discovery) + len(additions) > MAX_REVISED_DISCOVERY:
        raise Conflict("revised_discovery_capacity_exhausted")
    lane["revision_attempt"] = {"version": REVISION_VERSION, "cycle": state["cycles"],
        "request_id": request_id, "source_rows_hash": digest(_refs(view["rows"])), "status": "preparing"}
    revised_discovery = deepcopy(discovery) + additions
    revised_cohort = policy.build_cohort(revised_discovery)
    policy.verify_cohort(revised_discovery, revised_cohort)
    revision = {"revision_id": "CWR000001", "version": REVISION_VERSION,
                "created_cycle": state["cycles"], "request_id": request_id,
                "parent_discovery_hash": digest(discovery), "parent_cohort_hash": cohort["cohort_digest"],
                "source_row_count": len(view["rows"]), "source_rows_hash": digest(_refs(view["rows"])),
                "promoted_refs": _refs(additions), "discovery": revised_discovery, "cohort": revised_cohort,
                "structural_changes": model_structure_changes(cohort, revised_cohort)}
    revision["revision_hash"] = digest(revision)
    lane["discovery_revisions"] = [revision]
    lane["revision_attempt"].update(status="recorded", revision_id=revision["revision_id"],
                                    revision_hash=revision["revision_hash"])
    lane["version"] = VERSION
    lane["active_discovery_revision_id"] = revision["revision_id"]
    if revision["structural_changes"]:
        lane["status"] = "active"
    else:
        lane["status"] = "null"
    return revision


def _verify_decision(discovery: list[dict], context: dict, evidence: list[dict], decision: dict) -> None:
    contract = decision.get("numeric_contract")
    if contract is None:
        policy.verify_evaluation(discovery, context, evidence, decision)
    elif contract == policy.EXACT_NUMERIC_CONTRACT:
        policy.verify_bounded_exact_evaluation(discovery, context, evidence, decision)
    else:
        raise Conflict("unsupported_case_numeric_contract")


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
        discovery, cohort, evidence = discovery_partition(lane, view, case)
        if (authority.get("discovery_revision_id") != case.get("discovery_revision_id")
                or authority.get("discovery_revision_hash") != case.get("discovery_revision_hash")):
            raise Conflict("authority_discovery_revision_mismatch")
        _verify_decision(discovery, view["context"], evidence, case["decision"])
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
    _, _, after_evidence = discovery_partition(lane, after_view, case)
    evaluate = (policy.evaluate_bounded_exact if case["decision"].get("numeric_contract") == policy.EXACT_NUMERIC_CONTRACT
                else policy.evaluate)
    updated = evaluate(cohort, case["decision"]["context"], after_evidence)
    _verify_decision(discovery, case["decision"]["context"], after_evidence, updated)
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
    """Prepare immutably; one representation revision may follow the old null."""
    original = state.get("current_world_investigation")
    if original and original.get("pending_authority") is not None:
        return {"status": "pending", "case_id": None, "reason": "unconsumed_authority"}
    revise = bool(original and _can_revise_null(original))
    if original and original.get("status") in {"blocked", "null", "exhausted", "disabled"} and not revise:
        return {"status": original["status"], "case_id": None}
    lane = deepcopy(original)
    try:
        view = current_view(state)
        if lane is None:
            discovery = deepcopy(view["rows"][:DISCOVERY_LIMIT])
            cohort = policy.build_cohort(discovery)
            lane = {"version": VERSION, "owner": OWNER, "world_version": STATEFUL_WORLD_VERSION,
                    "discovery_limit": DISCOVERY_LIMIT, "discovery": discovery,
                    "cohort": cohort, "actions_remaining": ACTION_ALLOWANCE,
                    "cases": [], "attempts": [], "outcomes": [], "beliefs": [],
                    "rejections": [], "pending_authority": None, "status": "active"}
        if len(lane["cases"]) >= MAX_CASES or not lane["actions_remaining"]:
            lane["status"] = "exhausted"
            state["current_world_investigation"] = lane
            return {"status": "exhausted", "case_id": None}
        if len(view["rows"]) + lane["actions_remaining"] > MAX_OBSERVATIONS:
            raise Conflict("insufficient_observation_completion_reserve")
        if revise:
            revision = _prepare_revision(lane, view, state, request_id)
            if revision is None:
                return {"status": "null", "case_id": None, "reason": "no_novel_transition_signatures"}
            if not revision["structural_changes"]:
                bounded(lane, CHECKPOINT_BYTES, "current-world checkpoint")
                state["current_world_investigation"] = lane
                return {"status": "null", "case_id": None, "reason": "no_structural_change",
                        "discovery_revision_id": revision["revision_id"]}
        discovery, cohort, evidence = discovery_partition(lane, view)
        decision = policy.evaluate_bounded_exact(cohort, view["context"], evidence)
        _verify_decision(discovery, view["context"], evidence, decision)
        case = {"case_id": f"CWC{len(lane['cases']) + 1:06d}", "owner": OWNER,
                "question": "Which permitted movement best distinguishes the observation-derived models here?",
                "prepared_cycle": state["cycles"], "prepared_request_id": request_id,
                "execution_hash": execution_hash(), "observation_hash": view["observation_hash"],
                "world_version": view["world_version"], "discovery_hash": digest(discovery),
                "evidence_refs": _refs(evidence), "decision": decision}
        revision_id = lane.get("active_discovery_revision_id")
        if revision_id:
            revision = _revision(lane, revision_id)
            case.update(discovery_revision_id=revision_id, discovery_revision_hash=revision["revision_hash"])
        case["case_hash"] = _case_hash(case)
        lane["cases"].append(case)
        action = decision["selected_action"]
        if action is None:
            lane["status"] = "null"
        else:
            lane["pending_authority"] = {"owner": OWNER, "case_id": case["case_id"],
                "case_hash": case["case_hash"], "action": action, "allowance": 1}
            if revision_id:
                lane["pending_authority"].update(discovery_revision_id=revision_id,
                                                 discovery_revision_hash=revision["revision_hash"])
        bounded(lane, CHECKPOINT_BYTES, "current-world checkpoint")
        state["current_world_investigation"] = lane
        return {"status": "prepared" if action else "null", "case_id": case["case_id"],
                "case_hash": case["case_hash"], "selected_action": action,
                **({"discovery_revision_id": revision_id} if revision_id else {})}
    except (Conflict, KeyError, TypeError) as error:
        # A rejected staged revision/case cannot overwrite committed records or
        # leave an oversized appended envelope for Core to save.
        retained = deepcopy(original) if original is not None else {
            "version": VERSION, "owner": OWNER, "cases": [], "attempts": [],
            "outcomes": [], "beliefs": [], "actions_remaining": 0, "rejections": []}
        if lane and lane.get("revision_attempt") and not retained.get("revision_attempt"):
            retained["revision_attempt"] = deepcopy(lane["revision_attempt"])
            retained["revision_attempt"].update(status="blocked", reason=str(error))
            # A valid bounded model revision remains useful provenance even if
            # the subsequent evaluation abstains on arithmetic/record limits.
            # Never retain its rejected appended case or an oversized revision.
            if lane.get("discovery_revisions"):
                with_revision = deepcopy(retained)
                for key in ("version", "discovery_revisions", "active_discovery_revision_id"):
                    if key in lane:
                        with_revision[key] = deepcopy(lane[key])
                try:
                    bounded(with_revision, CHECKPOINT_BYTES - 4096, "revision with rejection reserve")
                except Conflict:
                    pass
                else:
                    retained = with_revision
        retained["status"], retained["pending_authority"] = "blocked", None
        retained["rejections"].append({"cycle": state["cycles"], "request_id": request_id, "reason": str(error)})
        bounded(retained, CHECKPOINT_BYTES, "current-world checkpoint")
        state["current_world_investigation"] = retained
        return {"status": "blocked", "case_id": None, "reason": str(error)}


def disable_prepared_case(state: dict) -> None:
    """One-way rollback preserves all records and retires pending authority."""
    lane = state.get("current_world_investigation")
    if lane and lane.get("status") != "disabled":
        key = "revision_rollback" if lane.get("revision_attempt") else "rollback"
        lane.setdefault(key, {"cycle": state["cycles"], "reason": "current_world_mode_disabled",
                              "retired_authority": deepcopy(lane.get("pending_authority"))})
        lane["pending_authority"] = None
        lane["status"] = "disabled"
