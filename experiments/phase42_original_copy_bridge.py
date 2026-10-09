"""Copy-only bridge from evidence-owned investigations to original Ora's 5x5 world.

The original planning lab already has a bounded investigator-action executor.
This bridge never loads, saves, schedules, or edits the original state; it
accepts an in-memory COPY, makes one evidence-owned choice, and returns a copy.
It explicitly records plan interruption rather than hiding that consequence.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from agenttest.action_lab import (
    ACTION_ORDER, STATEFUL_WORLD_VERSION, apply_bounded_action,
)
from agenttest.causal_investigator import (
    MAX_HISTORY, classify_outcome, forecast, project_public,
    select_investigation, brier,
)
from agenttest.planning_lab import execute_investigation_action

VERSION = "phase42-original-world-copy-bridge-v1"
_REQUEST = re.compile(r"[A-Za-z0-9._:-]{1,96}\Z")


def _public(position: list[int]) -> dict[str, Any]:
    return project_public({
        "position": list(position), "inventory_ids": [], "visible_entities": [],
    })


def _evidence(lab: dict) -> tuple[list[dict], int, int]:
    """Inherit only physically comparable, source-cited stateful-world effects."""
    if lab.get("world_version") != STATEFUL_WORLD_VERSION:
        raise ValueError("a copied stateful original world is required")
    bounds = lab.get("bounds")
    if type(bounds) is not int or not 1 <= bounds <= 128:
        raise ValueError("invalid original world bounds")
    observations = lab.get("transition_observations", [])
    if not isinstance(observations, list):
        raise ValueError("invalid persisted original observations")
    seen = set()
    admitted = []
    incompatible = 0
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("malformed original observation")
        if row.get("world_version") != STATEFUL_WORLD_VERSION:
            incompatible += 1
            continue
        ref = row.get("source_id")
        action = row.get("action")
        before, after = row.get("before"), row.get("after")
        if (not isinstance(ref, str) or not ref or ref in seen
                or action not in ACTION_ORDER
                or not isinstance(before, list) or len(before) != 2
                or not isinstance(after, list) or len(after) != 2
                or any(type(v) is not int or not -bounds <= v <= bounds
                       for v in before + after)
                or type(row.get("blocked")) is not bool):
            raise ValueError("ambiguous or invalid original action evidence")
        seen.add(ref)
        actual = apply_bounded_action(
            before, action, bounds=bounds, world_version=STATEFUL_WORLD_VERSION,
        )
        if (actual["after"] != after
                or bool(actual["blocked"]) != row["blocked"]):
            raise ValueError("original action evidence fails protected replay")
        prior, later = _public(before), _public(after)
        kind = classify_outcome(prior, later, {"blocked": row["blocked"]})
        admitted.append({
            # These are explicitly inherited, unowned source observations.
            # They are evidence, NOT prior selected new-Phase42 investigations.
            "id": "original:" + ref,
            "public_before": prior,
            "command": {"action": action},
            "outcome_kind": kind,
        })
    total = len(admitted)
    # Deterministic recency cap. Do not select convenient outcomes or edit
    # original history; report all excluded-but-preserved observations.
    return admitted[-MAX_HISTORY:], max(0, total - MAX_HISTORY), incompatible


def probe_original_copy(
    original_state: dict,
    *,
    request_id: str,
    permit_commitment_interruption: bool = False,
) -> dict[str, Any]:
    """Execute at most one action on a COPY of the original Ora current world.

    This is a research API. Its returned state is NEVER written by this module.
    Caller is responsible for a separate, reviewed transactional persistence
    contract before any future use outside ephemeral copied tests.
    """
    if not isinstance(original_state, dict):
        raise ValueError("a copied original Ora state mapping is required")
    if not isinstance(request_id, str) or not _REQUEST.fullmatch(request_id):
        raise ValueError("a bounded unique copy-only request ID is required")
    if type(permit_commitment_interruption) is not bool:
        raise ValueError("commitment interruption control must be explicit")
    state = deepcopy(original_state)
    lab = state.get("planning_lab")
    if not isinstance(lab, dict):
        raise ValueError("missing original planning lab")
    if lab.get("world_version") != STATEFUL_WORLD_VERSION:
        raise ValueError("unsupported original world version")
    bounds = lab.get("bounds")
    position = lab.get("position")
    if (type(bounds) is not int or not 1 <= bounds <= 128
            or not isinstance(position, list) or len(position) != 2
            or any(type(v) is not int or not -bounds <= v <= bounds
                   for v in position)):
        raise ValueError("invalid original position or bounds")
    cycle = state.get("cycles")
    if type(cycle) is not int or cycle < 0:
        raise ValueError("invalid original cycle")
    if lab.get("last_action_cycle") == cycle:
        raise ValueError("an original world action was already consumed this cycle")
    for item in lab.get("executions", []):
        if isinstance(item, dict) and item.get("attempt_id") == request_id:
            raise ValueError("duplicate original-world attempt identity")
    previous, omitted, incompatible = _evidence(lab)
    view = _public(position)
    menu = [{"action": action} for action in ACTION_ORDER]
    selected = select_investigation(view, previous, menu)
    interrupted = any(lab.get(key) is not None for key in (
        "active_goal_id", "active_plan_id", "active_objective_realization_id",
    ))
    provenance = {
        "original_world": STATEFUL_WORLD_VERSION,
        "inherited_source_rows_used": len(previous),
        "earlier_compatible_rows_preserved_but_outside_window": omitted,
        "incompatible_world_rows_preserved_not_imported": incompatible,
        "candidate_selection": deepcopy(selected),
        "native_cycle": cycle,
        "active_commitment_present": interrupted,
    }
    if interrupted and not permit_commitment_interruption:
        return {
            "version": VERSION,
            "status": "abstained_active_commitment",
            "provenance": provenance,
            "state": state,
            "execution": None,
        }
    if interrupted and not permit_commitment_interruption:
        raise AssertionError("unreachable commitment authorization")
    case_id = "P42C-" + hashlib.sha256(
        json.dumps([cycle, position, selected, request_id],
                   sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    result = execute_investigation_action(
        state, action=selected["command"]["action"],
        case_id=case_id, attempt_id=request_id,
    )
    after_public = _public(result["after"])
    kind = classify_outcome(view, after_public, {"blocked": result["blocked"]})
    feedback = {
        "version": VERSION,
        "status": "executed_on_copy",
        "provenance": provenance,
        "case_id": case_id,
        "request_id": request_id,
        "execution": deepcopy(result),
        "observed_outcome_kind": kind,
        "preaction_prediction_brier": brier(
            selected["forecast"]["probabilities"], kind,
        ),
        "postaction_forecast_for_same_original_context": forecast(
            view, selected["command"], [
                *previous,
                {
                    "id": "copied:" + result["id"],
                    "public_before": view,
                    "command": selected["command"],
                    "outcome_kind": kind,
                },
            ],
        ),
        "state": state,
    }
    if state["planning_lab"]["executions"][-1]["attempt_id"] != request_id:
        raise AssertionError("owned action lost native provenance")
    if feedback["execution"]["action"] != selected["command"]["action"]:
        raise AssertionError("executed action is not inquiry-owned")
    return feedback
