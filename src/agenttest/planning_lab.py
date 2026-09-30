from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any

from .action_lab import (
    ACTION_ORDER,
    BOUNDS,
    apply_bounded_action,
    validate_action_lab_history,
)

PLANNING_LAB_VERSION = "persistent-planning-lab-v1"
MIN_MODEL_SAMPLES = 2
PREFERRED_MIN_PLAN_STEPS = 3
PREFERRED_MAX_PLAN_STEPS = 4


def initial_planning_lab_state() -> dict[str, Any]:
    return {
        "version": PLANNING_LAB_VERSION,
        "status": "uninitialized",
        "bounds": BOUNDS,
        "position": [0, 0],
        "visit_counts": {"0,0": 1},
        "transition_observations": [],
        "learned_effects": {},
        "goals": [],
        "plans": [],
        "executions": [],
        "active_goal_id": None,
        "active_plan_id": None,
        "bootstrapped_from_action_count": 0,
        "bootstrapped_cycle": None,
        "last_action_cycle": None,
    }


def ensure_planning_lab_state(state: dict[str, Any]) -> dict[str, Any]:
    lab = state.setdefault("planning_lab", initial_planning_lab_state())
    defaults = initial_planning_lab_state()
    for key, value in defaults.items():
        lab.setdefault(key, value)
    return lab


def _position_key(position: list[int] | tuple[int, int]) -> str:
    return f"{int(position[0])},{int(position[1])}"


def _in_bounds(position: tuple[int, int], bounds: int) -> bool:
    return all(-bounds <= value <= bounds for value in position)


def _rebuild_model(lab: dict[str, Any]) -> dict[str, Any]:
    samples: dict[str, list[tuple[int, int]]] = defaultdict(list)
    blocked_counts: Counter[str] = Counter()

    for record in lab.get("transition_observations", []):
        action = str(record.get("action") or "")
        if action not in ACTION_ORDER:
            continue
        if record.get("blocked"):
            blocked_counts[action] += 1
            continue
        delta = record.get("delta")
        if (
            isinstance(delta, list)
            and len(delta) == 2
            and all(isinstance(value, int) for value in delta)
        ):
            samples[action].append((int(delta[0]), int(delta[1])))

    learned: dict[str, Any] = {}
    for action in ACTION_ORDER:
        action_samples = samples[action]
        effect_counts = Counter(action_samples)
        if effect_counts:
            effect, count = sorted(
                effect_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0]
            modal_delta = [int(effect[0]), int(effect[1])]
            confidence = count / len(action_samples)
        else:
            modal_delta = None
            confidence = 0.0
        learned[action] = {
            "unblocked_samples": len(action_samples),
            "blocked_samples": int(blocked_counts[action]),
            "modal_delta": modal_delta,
            "confidence": round(confidence, 6),
        }

    lab["learned_effects"] = learned
    return learned


def _bootstrap_from_action_lab(
    state: dict[str, Any],
    lab: dict[str, Any],
) -> bool:
    if lab.get("status") != "uninitialized":
        learned = _rebuild_model(lab)
        ready = all(
            int(learned[action].get("unblocked_samples", 0) or 0)
            >= MIN_MODEL_SAMPLES
            and isinstance(learned[action].get("modal_delta"), list)
            and float(learned[action].get("confidence", 0.0) or 0.0) > 0.0
            for action in ACTION_ORDER
        )
        if not ready:
            lab["status"] = "waiting_for_model"
        return ready

    action_lab = state.get("action_lab", {})
    valid, error = validate_action_lab_history(action_lab)
    if not valid:
        raise ValueError(f"cannot bootstrap planning lab from invalid action history: {error}")

    observations: list[dict[str, Any]] = []
    for record in action_lab.get("history", []):
        action = str(record.get("action") or "")
        if action not in ACTION_ORDER:
            continue
        observations.append(
            {
                "source": "action_lab",
                "source_id": record.get("id"),
                "cycle": int(record.get("cycle", 0) or 0),
                "action": action,
                "delta": list(record.get("delta", [0, 0])),
                "blocked": bool(record.get("blocked")),
            }
        )

    lab["transition_observations"] = observations
    learned = _rebuild_model(lab)
    ready = all(
        int(learned[action].get("unblocked_samples", 0) or 0) >= MIN_MODEL_SAMPLES
        and isinstance(learned[action].get("modal_delta"), list)
        and float(learned[action].get("confidence", 0.0) or 0.0) > 0.0
        for action in ACTION_ORDER
    )
    if not ready:
        lab["status"] = "waiting_for_model"
        lab["bootstrapped_from_action_count"] = len(action_lab.get("history", []))
        return False

    lab["bounds"] = int(action_lab.get("bounds", BOUNDS))
    lab["position"] = [
        int(value) for value in action_lab.get("position", [0, 0])
    ]
    lab["visit_counts"] = {
        str(key): int(value)
        for key, value in action_lab.get("visit_counts", {"0,0": 1}).items()
        if int(value) > 0
    }
    lab["status"] = "ready"
    lab["bootstrapped_from_action_count"] = len(action_lab.get("history", []))
    lab["bootstrapped_cycle"] = int(state.get("cycles", 0) or 0)
    return True


def _shortest_plan(
    start: tuple[int, int],
    goal: tuple[int, int],
    learned: dict[str, Any],
    bounds: int,
) -> tuple[list[str], list[list[int]]] | None:
    if start == goal:
        return [], []

    queue = deque([(start, [], [])])
    seen = {start}
    while queue:
        position, actions, predicted_states = queue.popleft()
        for action in ACTION_ORDER:
            delta = learned.get(action, {}).get("modal_delta")
            if not isinstance(delta, list) or len(delta) != 2:
                continue
            target = (
                int(position[0]) + int(delta[0]),
                int(position[1]) + int(delta[1]),
            )
            if not _in_bounds(target, bounds) or target in seen:
                continue
            next_actions = [*actions, action]
            next_states = [*predicted_states, [target[0], target[1]]]
            if target == goal:
                return next_actions, next_states
            seen.add(target)
            queue.append((target, next_actions, next_states))
    return None


def _active_goal(lab: dict[str, Any]) -> dict[str, Any] | None:
    goal_id = lab.get("active_goal_id")
    if not goal_id:
        return None
    return next(
        (item for item in lab.get("goals", []) if item.get("id") == goal_id),
        None,
    )


def _active_plan(lab: dict[str, Any]) -> dict[str, Any] | None:
    plan_id = lab.get("active_plan_id")
    if not plan_id:
        return None
    return next(
        (item for item in lab.get("plans", []) if item.get("id") == plan_id),
        None,
    )


def _choose_goal(lab: dict[str, Any], cycle: int) -> dict[str, Any] | None:
    learned = _rebuild_model(lab)
    bounds = int(lab.get("bounds", BOUNDS))
    start = tuple(int(value) for value in lab.get("position", [0, 0]))
    visits = lab.get("visit_counts", {})

    candidates: list[
        tuple[int, int, int, int, list[str], list[list[int]]]
    ] = []
    for x in range(-bounds, bounds + 1):
        for y in range(-bounds, bounds + 1):
            target = (x, y)
            if target == start:
                continue
            planned = _shortest_plan(start, target, learned, bounds)
            if planned is None:
                continue
            actions, predicted_states = planned
            if not actions:
                continue
            candidates.append(
                (
                    int(visits.get(_position_key(target), 0) or 0),
                    len(actions),
                    x,
                    y,
                    actions,
                    predicted_states,
                )
            )

    if not candidates:
        lab["status"] = "blocked_no_goal"
        return None

    preferred = [
        item
        for item in candidates
        if PREFERRED_MIN_PLAN_STEPS <= item[1] <= PREFERRED_MAX_PLAN_STEPS
    ]
    pool = preferred or candidates
    visit_count, distance, x, y, _, _ = min(
        pool,
        key=lambda item: (
            item[0],
            -item[1],
            item[2],
            item[3],
        ),
    )
    goal = {
        "id": f"PG{len(lab.get('goals', [])) + 1:06d}",
        "assigned_cycle": cycle,
        "target": [x, y],
        "status": "active",
        "selection": {
            "kind": "least_visited_farthest_reachable",
            "prior_visits": visit_count,
            "planned_distance": distance,
            "preferred_step_range": [
                PREFERRED_MIN_PLAN_STEPS,
                PREFERRED_MAX_PLAN_STEPS,
            ],
        },
    }
    lab.setdefault("goals", []).append(goal)
    lab["active_goal_id"] = goal["id"]
    lab["status"] = "goal_assigned"
    return goal


def _create_plan(
    lab: dict[str, Any],
    goal: dict[str, Any],
    cycle: int,
    *,
    reason: str,
) -> dict[str, Any] | None:
    learned = _rebuild_model(lab)
    start = tuple(int(value) for value in lab.get("position", [0, 0]))
    target = tuple(int(value) for value in goal.get("target", [0, 0]))
    planned = _shortest_plan(
        start,
        target,
        learned,
        int(lab.get("bounds", BOUNDS)),
    )
    if planned is None:
        lab["status"] = "blocked_no_plan"
        return None

    actions, predicted_states = planned
    plan = {
        "id": f"PP{len(lab.get('plans', [])) + 1:06d}",
        "goal_id": goal["id"],
        "created_cycle": cycle,
        "start": [start[0], start[1]],
        "goal": [target[0], target[1]],
        "actions": actions,
        "predicted_states": predicted_states,
        "next_step_index": 0,
        "status": "active",
        "reason": reason,
        "model_samples": {
            action: int(
                learned.get(action, {}).get("unblocked_samples", 0) or 0
            )
            for action in ACTION_ORDER
        },
    }
    lab.setdefault("plans", []).append(plan)
    lab["active_plan_id"] = plan["id"]
    lab["status"] = "plan_active"
    return plan


def step_planning_lab(state: dict[str, Any]) -> dict[str, Any]:
    """Execute exactly one persisted model-planned internal action."""

    lab = ensure_planning_lab_state(state)
    cycle = int(state.get("cycles", 0) or 0)
    if not _bootstrap_from_action_lab(state, lab):
        return {
            "lab_version": PLANNING_LAB_VERSION,
            "status": lab.get("status"),
            "action": None,
            "reason": "Phase 32 transition model does not yet meet the planning evidence threshold.",
        }

    goal = _active_goal(lab)
    if goal is None:
        goal = _choose_goal(lab, cycle)
    if goal is None:
        return {
            "lab_version": PLANNING_LAB_VERSION,
            "status": lab.get("status"),
            "action": None,
            "reason": "No reachable planning goal is available.",
        }

    plan = _active_plan(lab)
    if plan is None or plan.get("status") != "active":
        plan = _create_plan(
            lab,
            goal,
            cycle,
            reason="initial_goal_plan" if plan is None else "replan_after_invalidation",
        )
    if plan is None:
        return {
            "lab_version": PLANNING_LAB_VERSION,
            "status": lab.get("status"),
            "action": None,
            "goal_id": goal.get("id"),
            "reason": "No learned multi-step plan reaches the active goal.",
        }

    step_index = int(plan.get("next_step_index", 0) or 0)
    actions = list(plan.get("actions", []))
    predicted_states = list(plan.get("predicted_states", []))
    if step_index >= len(actions) or step_index >= len(predicted_states):
        plan["status"] = "invalidated"
        plan["invalidated_cycle"] = cycle
        plan["invalidation_reason"] = "plan_exhausted_before_goal"
        lab["active_plan_id"] = None
        lab["status"] = "needs_replan"
        return {
            "lab_version": PLANNING_LAB_VERSION,
            "status": "needs_replan",
            "action": None,
            "goal_id": goal.get("id"),
            "plan_id": plan.get("id"),
            "reason": "Persisted plan exhausted before reaching its goal.",
        }

    action = str(actions[step_index])
    before = [int(value) for value in lab.get("position", [0, 0])]
    predicted_after = [
        int(value) for value in predicted_states[step_index]
    ]
    outcome = apply_bounded_action(
        before,
        action,
        bounds=int(lab.get("bounds", BOUNDS)),
    )
    after = list(outcome["after"])
    matched_prediction = after == predicted_after

    execution = {
        "id": f"PX{len(lab.get('executions', [])) + 1:06d}",
        "cycle": cycle,
        "goal_id": goal["id"],
        "plan_id": plan["id"],
        "step_index": step_index,
        "plan_length": len(actions),
        "action": action,
        "before": before,
        "predicted_after": predicted_after,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_prediction": matched_prediction,
    }
    lab.setdefault("executions", []).append(execution)
    lab["position"] = after
    position_key = _position_key(after)
    lab.setdefault("visit_counts", {})[position_key] = (
        int(lab["visit_counts"].get(position_key, 0) or 0) + 1
    )
    lab["last_action_cycle"] = cycle
    lab.setdefault("transition_observations", []).append(
        {
            "source": "planning_lab",
            "source_id": execution["id"],
            "cycle": cycle,
            "action": action,
            "delta": list(outcome["delta"]),
            "blocked": bool(outcome["blocked"]),
        }
    )
    learned = _rebuild_model(lab)

    goal_reached = after == list(goal.get("target", []))
    if matched_prediction:
        plan["next_step_index"] = step_index + 1
        if goal_reached:
            plan["status"] = "completed"
            plan["completed_cycle"] = cycle
            goal["status"] = "completed"
            goal["completed_cycle"] = cycle
            goal["completed_plan_id"] = plan["id"]
            lab["active_plan_id"] = None
            lab["active_goal_id"] = None
            lab["status"] = "goal_reached"
        else:
            lab["status"] = "executing_plan"
    else:
        plan["status"] = "invalidated"
        plan["invalidated_cycle"] = cycle
        plan["invalidation_reason"] = "prediction_mismatch"
        plan["mismatch_execution_id"] = execution["id"]
        lab["active_plan_id"] = None
        lab["status"] = "needs_replan"

    return {
        **execution,
        "lab_version": PLANNING_LAB_VERSION,
        "status": lab["status"],
        "goal": list(goal.get("target", [])),
        "goal_reached": goal_reached,
        "replan_required": not matched_prediction,
        "remaining_plan_steps": (
            0
            if goal_reached or not matched_prediction
            else len(actions) - int(plan.get("next_step_index", 0) or 0)
        ),
        "learned_effects": learned,
    }
