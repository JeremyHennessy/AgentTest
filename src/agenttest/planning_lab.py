from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
from typing import Any

from .action_lab import (
    ACTION_ORDER,
    BASE_WORLD_VERSION,
    BOUNDS,
    STATEFUL_WORLD_VERSION,
    TRANSFER_WORLD_VERSION,
    apply_bounded_action,
    validate_action_lab_history,
)

PLANNING_LAB_VERSION = "persistent-planning-lab-v9"
CURIOSITY_POLICY_VERSION = "evidence-valued-curiosity-v1"
EPISODIC_MEMORY_VERSION = "episodic-route-memory-v1"
TRANSFER_POLICY_VERSION = "bounded-transfer-v1"
SELF_EXPERIMENT_POLICY_VERSION = "self-generated-falsifiable-experiment-v1"
OBJECTIVE_SELECTION_POLICY_VERSION = "bounded-objective-selection-v1"
OBJECTIVE_REALIZATION_POLICY_VERSION = "objective-information-realization-v1"
OUTCOME_AWARE_OBJECTIVE_POLICY_VERSION = "outcome-aware-objective-valuation-v1"
EPISODIC_MEMORY_MAX_ENTRIES = 64
EPISODIC_MEMORY_MAX_DECISIONS = 128
EPISODIC_MEMORY_MAX_ROUTE_CANDIDATES = 24
CURIOSITY_TARGET_STATE_SAMPLES = 2
CURIOSITY_MAX_PROBES_PER_REVISION = 1
TRANSFER_MAX_PROBES_PER_REVISION = 1
TRANSFER_MIN_SOURCE_STATE_SAMPLES = 2
SELF_EXPERIMENT_COOLDOWN_CYCLES = 12
SELF_EXPERIMENT_MAX_PER_GOAL = 1
SELF_EXPERIMENT_MIN_COMPLETED_PLAN_STEPS = 1
SELF_EXPERIMENT_MIN_REMAINING_PLAN_STEPS = 2
OBJECTIVE_SELECTION_MIN_RECOVERED_EXPERIMENTS = 2
OBJECTIVE_SELECTION_COOLDOWN_CYCLES = 12
OBJECTIVE_SELECTION_MAX_DECISIONS = 128
OBJECTIVE_REALIZATION_MAX_RECORDS = 128
OUTCOME_VALUATION_MIN_REALIZATIONS = 3
OUTCOME_VALUATION_MIN_ACTIONS = 2
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
        "state_effects": {},
        "model_revisions": [],
        "curiosity_decisions": [],
        "curiosity_probes": [],
        "episodic_memory_started_cycle": None,
        "episodic_route_memories": [],
        "memory_decisions": [],
        "transfer_decisions": [],
        "transfer_probes": [],
        "last_transfer_probe_cycle": None,
        "self_experiment_started_cycle": None,
        "self_experiment_decisions": [],
        "self_experiments": [],
        "last_self_experiment_cycle": None,
        "objective_selection_started_cycle": None,
        "objective_decisions": [],
        "last_objective_selection_cycle": None,
        "objective_realization_started_cycle": None,
        "objective_realization_decisions": [],
        "objective_realizations": [],
        "active_objective_realization_id": None,
        "outcome_valuation_started_cycle": None,
        "world_version": STATEFUL_WORLD_VERSION,
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
    lab["version"] = PLANNING_LAB_VERSION
    if lab.get("world_version") in {None, BASE_WORLD_VERSION}:
        lab["world_version"] = STATEFUL_WORLD_VERSION
    return lab


def _position_key(position: list[int] | tuple[int, int]) -> str:
    return f"{int(position[0])},{int(position[1])}"


def _state_action_key(
    position: list[int] | tuple[int, int],
    action: str,
) -> str:
    return f"{_position_key(position)}|{action}"


def _in_bounds(position: tuple[int, int], bounds: int) -> bool:
    return all(-bounds <= value <= bounds for value in position)


def _rebuild_model(lab: dict[str, Any]) -> dict[str, Any]:
    samples: dict[str, list[tuple[int, int]]] = defaultdict(list)
    blocked_counts: Counter[str] = Counter()
    state_samples: dict[str, list[tuple[int, int]]] = defaultdict(list)
    state_blocked_counts: Counter[str] = Counter()
    world_version = str(lab.get("world_version") or STATEFUL_WORLD_VERSION)

    for record in lab.get("transition_observations", []):
        action = str(record.get("action") or "")
        if action not in ACTION_ORDER:
            continue
        blocked = bool(record.get("blocked"))
        delta = record.get("delta")
        valid_delta = (
            isinstance(delta, list)
            and len(delta) == 2
            and all(isinstance(value, int) for value in delta)
        )
        if blocked:
            blocked_counts[action] += 1
        elif valid_delta:
            samples[action].append((int(delta[0]), int(delta[1])))

        before = record.get("before")
        same_world = record.get("world_version") == world_version
        valid_before = (
            isinstance(before, list)
            and len(before) == 2
            and all(isinstance(value, int) for value in before)
        )
        if same_world and valid_before:
            key = _state_action_key(before, action)
            if blocked:
                state_blocked_counts[key] += 1
            elif valid_delta:
                state_samples[key].append((int(delta[0]), int(delta[1])))

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

    state_effects: dict[str, Any] = {}
    state_keys = sorted(set(state_samples) | set(state_blocked_counts))
    for key in state_keys:
        action_samples = state_samples[key]
        blocked_samples = int(state_blocked_counts[key])
        if blocked_samples > len(action_samples):
            state_effects[key] = {
                "samples": blocked_samples + len(action_samples),
                "blocked_samples": blocked_samples,
                "unblocked_samples": len(action_samples),
                "blocked": True,
                "modal_delta": None,
                "confidence": round(
                    blocked_samples / (blocked_samples + len(action_samples)),
                    6,
                ),
            }
            continue

        effect_counts = Counter(action_samples)
        effect, count = sorted(
            effect_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
        state_effects[key] = {
            "samples": blocked_samples + len(action_samples),
            "blocked_samples": blocked_samples,
            "unblocked_samples": len(action_samples),
            "blocked": False,
            "modal_delta": [int(effect[0]), int(effect[1])],
            "confidence": round(
                count / (blocked_samples + len(action_samples)),
                6,
            ),
        }

    lab["learned_effects"] = learned
    lab["state_effects"] = state_effects
    return learned


def _bootstrap_from_action_lab(
    state: dict[str, Any],
    lab: dict[str, Any],
) -> bool:
    bootstrap_pending = (
        lab.get("status") in {"uninitialized", "waiting_for_model"}
        and lab.get("bootstrapped_cycle") is None
        and not lab.get("active_goal_id")
        and not lab.get("active_plan_id")
        and not any(lab.get(key) for key in ("goals", "plans", "executions"))
    )
    if not bootstrap_pending:
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
                "before": list(record.get("before", [0, 0])),
                "after": list(record.get("after", [0, 0])),
                "delta": list(record.get("delta", [0, 0])),
                "blocked": bool(record.get("blocked")),
                "world_version": BASE_WORLD_VERSION,
            }
        )

    # A waiting bootstrap may ingest a validated extension of the same source
    # ledger. Preserve copied rows/annotations and other transition provenance;
    # never count the same source observation twice or overwrite a reused ID.
    existing = lab.get("transition_observations", [])
    source_by_id = {item["source_id"]: item for item in observations}
    copied_ids: set[str] = set()
    for item in existing:
        if item.get("source") != "action_lab":
            continue
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in copied_ids:
            raise ValueError("cannot retry bootstrap with ambiguous copied action provenance")
        copied_ids.add(source_id)
        current = source_by_id.get(source_id)
        if current is None or any(item.get(key) != value for key, value in current.items()):
            raise ValueError(f"cannot retry bootstrap from changed or missing action provenance: {source_id}")
    existing.extend(item for item in observations if item["source_id"] not in copied_ids)
    lab["transition_observations"] = existing
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
    state_effects: dict[str, Any],
    bounds: int,
) -> tuple[list[str], list[list[int]]] | None:
    if start == goal:
        return [], []

    queue = deque([(start, [], [])])
    seen = {start}
    while queue:
        position, actions, predicted_states = queue.popleft()
        for action in ACTION_ORDER:
            state_effect = state_effects.get(
                _state_action_key(position, action),
                {},
            )
            if state_effect.get("blocked"):
                continue
            delta = state_effect.get("modal_delta")
            if not isinstance(delta, list) or len(delta) != 2:
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


def _state_effect_prediction(
    lab: dict[str, Any],
    position: list[int] | tuple[int, int],
    action: str,
) -> list[int] | None:
    effect = lab.get("state_effects", {}).get(
        _state_action_key(position, action),
        {},
    )
    if int(effect.get("samples", 0) or 0) <= 0:
        return None
    before = [int(position[0]), int(position[1])]
    if effect.get("blocked"):
        return before
    delta = effect.get("modal_delta")
    if not isinstance(delta, list) or len(delta) != 2:
        return None
    return [
        before[0] + int(delta[0]),
        before[1] + int(delta[1]),
    ]


def _select_curiosity_probe(
    lab: dict[str, Any],
    goal: dict[str, Any],
    plan: dict[str, Any],
    cycle: int,
) -> dict[str, Any] | None:
    position = [int(value) for value in lab.get("position", [0, 0])]
    actions = list(plan.get("actions", []))
    step_index = int(plan.get("next_step_index", 0) or 0)
    remaining_goal_steps = max(0, len(actions) - step_index)
    if remaining_goal_steps <= 0:
        return None
    next_goal_action = str(actions[step_index])

    probes = lab.get("curiosity_probes", [])
    for revision in reversed(lab.get("model_revisions", [])):
        revision_id = str(revision.get("id") or "")
        action = str(revision.get("action") or "")
        before = revision.get("before")
        if (
            not revision_id
            or action not in ACTION_ORDER
            or not isinstance(before, list)
            or before != position
            or revision.get("goal_id") == goal.get("id")
            or action == next_goal_action
        ):
            continue
        prior_probe_count = sum(
            1
            for probe in probes
            if probe.get("source_model_revision_id") == revision_id
        )
        if prior_probe_count >= CURIOSITY_MAX_PROBES_PER_REVISION:
            continue

        key = _state_action_key(position, action)
        effect = lab.get("state_effects", {}).get(key, {})
        state_samples = int(effect.get("samples", 0) or 0)
        if (
            state_samples <= 0
            or state_samples >= CURIOSITY_TARGET_STATE_SAMPLES
        ):
            continue
        expected_after = _state_effect_prediction(lab, position, action)
        if expected_after is None:
            continue

        information_value = round(1.0 / state_samples, 6)
        goal_delay_cost = round(1.0 / (remaining_goal_steps + 1), 6)
        decision_margin = round(information_value - goal_delay_cost, 6)
        decision = {
            "id": f"CD{len(lab.get('curiosity_decisions', [])) + 1:06d}",
            "cycle": cycle,
            "policy_version": CURIOSITY_POLICY_VERSION,
            "source_model_revision_id": revision_id,
            "goal_id": goal.get("id"),
            "plan_id": plan.get("id"),
            "state_action_key": key,
            "state": position,
            "action": action,
            "expected_after": expected_after,
            "state_samples": state_samples,
            "information_value": information_value,
            "goal_delay_cost": goal_delay_cost,
            "decision_margin": decision_margin,
            "remaining_goal_steps": remaining_goal_steps,
            "status": (
                "probe_selected"
                if decision_margin > 0.0
                else "continue_goal"
            ),
        }
        lab.setdefault("curiosity_decisions", []).append(decision)
        return decision if decision["status"] == "probe_selected" else None
    return None


def _execute_curiosity_probe(
    lab: dict[str, Any],
    goal: dict[str, Any],
    plan: dict[str, Any],
    decision: dict[str, Any],
    cycle: int,
) -> dict[str, Any]:
    before = [int(value) for value in decision["state"]]
    action = str(decision["action"])
    expected_after = [int(value) for value in decision["expected_after"]]
    world_version = str(
        lab.get("world_version") or STATEFUL_WORLD_VERSION
    )
    outcome = apply_bounded_action(
        before,
        action,
        bounds=int(lab.get("bounds", BOUNDS)),
        world_version=world_version,
    )
    after = list(outcome["after"])
    matched_prior_state_effect = after == expected_after

    probe = {
        "id": f"CP{len(lab.get('curiosity_probes', [])) + 1:06d}",
        "cycle": cycle,
        "policy_version": CURIOSITY_POLICY_VERSION,
        "decision_id": decision["id"],
        "source_model_revision_id": decision["source_model_revision_id"],
        "goal_id": goal.get("id"),
        "plan_id": plan.get("id"),
        "state_action_key": decision["state_action_key"],
        "action": action,
        "before": before,
        "predicted_after": expected_after,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_prior_state_effect": matched_prior_state_effect,
        "state_samples_before": int(decision["state_samples"]),
        "information_value": float(decision["information_value"]),
        "goal_delay_cost": float(decision["goal_delay_cost"]),
        "decision_margin": float(decision["decision_margin"]),
        "world_version": world_version,
    }
    lab.setdefault("curiosity_probes", []).append(probe)
    lab["position"] = after
    position_key = _position_key(after)
    lab.setdefault("visit_counts", {})[position_key] = (
        int(lab["visit_counts"].get(position_key, 0) or 0) + 1
    )
    lab["last_action_cycle"] = cycle
    lab.setdefault("transition_observations", []).append(
        {
            "source": "curiosity_probe",
            "source_id": probe["id"],
            "cycle": cycle,
            "action": action,
            "before": before,
            "after": after,
            "delta": list(outcome["delta"]),
            "blocked": bool(outcome["blocked"]),
            "world_version": world_version,
        }
    )
    learned = _rebuild_model(lab)
    effect_after = lab.get("state_effects", {}).get(
        decision["state_action_key"],
        {},
    )
    probe["state_samples_after"] = int(effect_after.get("samples", 0) or 0)

    source_revision = next(
        (
            revision
            for revision in lab.get("model_revisions", [])
            if revision.get("id") == decision["source_model_revision_id"]
        ),
        None,
    )
    if source_revision is not None:
        source_revision.setdefault("curiosity_probe_ids", []).append(probe["id"])
        source_revision["curiosity_status"] = (
            "probe_confirmed"
            if matched_prior_state_effect
            else "probe_refuted"
        )

    new_revision_id = None
    if not matched_prior_state_effect:
        revision = {
            "id": f"MR{len(lab.get('model_revisions', [])) + 1:06d}",
            "cycle": cycle,
            "trigger_curiosity_probe_id": probe["id"],
            "source_model_revision_id": decision["source_model_revision_id"],
            "goal_id": goal.get("id"),
            "plan_id": plan.get("id"),
            "state_action_key": decision["state_action_key"],
            "before": before,
            "action": action,
            "predicted_after": expected_after,
            "observed_after": after,
            "observed_delta": list(outcome["delta"]),
            "observed_blocked": bool(outcome["blocked"]),
            "world_version": world_version,
            "status": "state_evidence_recorded",
        }
        lab.setdefault("model_revisions", []).append(revision)
        new_revision_id = revision["id"]

    goal_reached = after == list(goal.get("target", []))
    if goal_reached:
        plan["status"] = "completed"
        plan["completed_cycle"] = cycle
        plan["completion_reason"] = "curiosity_probe_reached_goal"
        goal["status"] = "completed"
        goal["completed_cycle"] = cycle
        goal["completed_plan_id"] = plan["id"]
        lab["active_plan_id"] = None
        lab["active_goal_id"] = None
        lab["status"] = "goal_reached"
    elif after != before:
        plan["status"] = "invalidated"
        plan["invalidated_cycle"] = cycle
        plan["invalidation_reason"] = "curiosity_probe_changed_state"
        plan["curiosity_probe_id"] = probe["id"]
        lab["active_plan_id"] = None
        lab["status"] = "needs_replan"
    else:
        lab["status"] = "executing_plan"

    probe["resulting_status"] = lab["status"]
    probe["goal_reached"] = goal_reached
    probe["replan_required"] = bool(after != before and not goal_reached)
    return {
        "id": probe["id"],
        "execution_kind": "curiosity_probe",
        "cycle": cycle,
        "goal_id": goal.get("id"),
        "plan_id": plan.get("id"),
        "step_index": int(plan.get("next_step_index", 0) or 0),
        "plan_length": len(plan.get("actions", [])),
        "action": action,
        "before": before,
        "predicted_after": expected_after,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_prediction": matched_prior_state_effect,
        "world_version": world_version,
        "lab_version": PLANNING_LAB_VERSION,
        "status": lab["status"],
        "goal": list(goal.get("target", [])),
        "goal_reached": goal_reached,
        "replan_required": probe["replan_required"],
        "model_revision_id": new_revision_id,
        "source_model_revision_id": decision["source_model_revision_id"],
        "curiosity_decision_id": decision["id"],
        "curiosity_probe_id": probe["id"],
        "information_value": decision["information_value"],
        "goal_delay_cost": decision["goal_delay_cost"],
        "decision_margin": decision["decision_margin"],
        "state_samples_before": decision["state_samples"],
        "state_samples_after": probe["state_samples_after"],
        "remaining_plan_steps": (
            0
            if goal_reached or probe["replan_required"]
            else len(plan.get("actions", []))
            - int(plan.get("next_step_index", 0) or 0)
        ),
        "learned_effects": learned,
    }



def _select_transfer_probe(
    lab: dict[str, Any],
    goal: dict[str, Any],
    plan: dict[str, Any],
    cycle: int,
) -> dict[str, Any] | None:
    """Select one isolated target-world probe from source-world evidence only."""

    source_world = str(lab.get("world_version") or STATEFUL_WORLD_VERSION)
    if source_world != STATEFUL_WORLD_VERSION:
        return None
    if plan.get("status") != "active":
        return None

    latest_curiosity_probe = (
        lab.get("curiosity_probes", [])[-1]
        if lab.get("curiosity_probes")
        else None
    )
    if (
        isinstance(latest_curiosity_probe, dict)
        and latest_curiosity_probe.get("plan_id") == plan.get("id")
        and int(latest_curiosity_probe.get("cycle", -1) or -1) == cycle - 1
        and latest_curiosity_probe.get("resulting_status") == "executing_plan"
        and latest_curiosity_probe.get("after")
        == latest_curiosity_probe.get("before")
    ):
        return None

    step_index = int(plan.get("next_step_index", 0) or 0)
    actions = list(plan.get("actions", []))
    if step_index >= len(actions):
        return None

    learned = lab.get("learned_effects", {})
    source_effects = lab.get("state_effects", {})
    probes = lab.get("transfer_probes", [])

    for revision in reversed(lab.get("model_revisions", [])):
        revision_id = str(revision.get("id") or "")
        action = str(revision.get("action") or "")
        before = revision.get("before")
        if (
            not revision_id
            or action not in ACTION_ORDER
            or not isinstance(before, list)
            or len(before) != 2
            or revision.get("world_version") != source_world
            or revision.get("observed_blocked") is not True
            or revision.get("curiosity_status") != "probe_confirmed"
        ):
            continue

        prior_probe_count = sum(
            1
            for probe in probes
            if probe.get("source_model_revision_id") == revision_id
        )
        if prior_probe_count >= TRANSFER_MAX_PROBES_PER_REVISION:
            continue

        state_action_key = _state_action_key(before, action)
        source_effect = source_effects.get(state_action_key, {})
        source_samples = int(source_effect.get("samples", 0) or 0)
        if (
            source_samples < TRANSFER_MIN_SOURCE_STATE_SAMPLES
            or source_effect.get("blocked") is not True
        ):
            continue

        general_effect = learned.get(action, {})
        general_delta = general_effect.get("modal_delta")
        general_samples = int(general_effect.get("unblocked_samples", 0) or 0)
        if (
            general_samples < MIN_MODEL_SAMPLES
            or not isinstance(general_delta, list)
            or len(general_delta) != 2
            or float(general_effect.get("confidence", 0.0) or 0.0) <= 0.0
        ):
            continue

        probe_state = [int(before[0]), int(before[1])]
        source_prediction = _state_effect_prediction(lab, probe_state, action)
        if source_prediction is None:
            continue
        general_prediction = [
            probe_state[0] + int(general_delta[0]),
            probe_state[1] + int(general_delta[1]),
        ]
        if (
            not _in_bounds(
                (general_prediction[0], general_prediction[1]),
                int(lab.get("bounds", BOUNDS)),
            )
            or general_prediction == source_prediction
        ):
            continue

        target_evidence_samples = sum(
            1
            for probe in probes
            if (
                probe.get("target_world_version") == TRANSFER_WORLD_VERSION
                and probe.get("state_action_key") == state_action_key
            )
        )
        if target_evidence_samples != 0:
            continue

        decision = {
            "id": f"TD{len(lab.get('transfer_decisions', [])) + 1:06d}",
            "cycle": cycle,
            "policy_version": TRANSFER_POLICY_VERSION,
            "source_model_revision_id": revision_id,
            "source_world_version": source_world,
            "target_world_version": TRANSFER_WORLD_VERSION,
            "goal_id": goal.get("id"),
            "plan_id": plan.get("id"),
            "plan_next_step_index": step_index,
            "state_action_key": state_action_key,
            "probe_state": probe_state,
            "action": action,
            "source_state_samples": source_samples,
            "general_action_samples": general_samples,
            "target_evidence_samples_before": target_evidence_samples,
            "source_specific_prediction": source_prediction,
            "general_action_prediction": general_prediction,
            "counterfactual_prior": "source_state_exception_as_if_transferable",
            "counterfactual_prediction": source_prediction,
            "selected_prior": "general_action_effect",
            "selected_prediction": general_prediction,
            "status": "probe_selected",
            "rationale": (
                "Target-world evidence is absent. Keep the source-world state exception "
                "scoped to its observed world and test whether the broader learned action "
                "effect transfers with one isolated bounded probe."
            ),
        }
        lab.setdefault("transfer_decisions", []).append(decision)
        return decision
    return None


def _execute_transfer_probe(
    lab: dict[str, Any],
    goal: dict[str, Any],
    plan: dict[str, Any],
    decision: dict[str, Any],
    cycle: int,
) -> dict[str, Any]:
    """Execute one target-world action without mutating the active source-world plan."""

    source_position_before = [
        int(value) for value in lab.get("position", [0, 0])
    ]
    source_step_before = int(plan.get("next_step_index", 0) or 0)
    source_plan_id = str(plan.get("id") or "")
    probe_state = [int(value) for value in decision["probe_state"]]
    action = str(decision["action"])

    outcome = apply_bounded_action(
        probe_state,
        action,
        bounds=int(lab.get("bounds", BOUNDS)),
        world_version=TRANSFER_WORLD_VERSION,
    )
    after = list(outcome["after"])
    selected_prediction = [
        int(value) for value in decision["selected_prediction"]
    ]
    counterfactual_prediction = [
        int(value) for value in decision["counterfactual_prediction"]
    ]
    matched_selected_prior = after == selected_prediction
    matched_source_exception_counterfactual = after == counterfactual_prediction

    if matched_selected_prior and not matched_source_exception_counterfactual:
        interpretation = "general_effect_transferred_source_exception_did_not"
    elif matched_source_exception_counterfactual and not matched_selected_prior:
        interpretation = "source_exception_transferred"
    else:
        interpretation = "target_world_surprise"

    probe = {
        "id": f"TP{len(lab.get('transfer_probes', [])) + 1:06d}",
        "cycle": cycle,
        "policy_version": TRANSFER_POLICY_VERSION,
        "decision_id": decision["id"],
        "source_model_revision_id": decision["source_model_revision_id"],
        "source_world_version": decision["source_world_version"],
        "target_world_version": TRANSFER_WORLD_VERSION,
        "goal_id": goal.get("id"),
        "plan_id": source_plan_id,
        "plan_next_step_index": source_step_before,
        "state_action_key": decision["state_action_key"],
        "action": action,
        "before": probe_state,
        "selected_prediction": selected_prediction,
        "counterfactual_prediction": counterfactual_prediction,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_selected_prior": matched_selected_prior,
        "matched_source_exception_counterfactual": (
            matched_source_exception_counterfactual
        ),
        "target_evidence_samples_before": int(
            decision["target_evidence_samples_before"]
        ),
        "target_evidence_samples_after": int(
            decision["target_evidence_samples_before"]
        ) + 1,
        "interpretation": interpretation,
    }
    lab.setdefault("transfer_probes", []).append(probe)
    lab["last_transfer_probe_cycle"] = cycle

    source_plan_preserved = (
        list(lab.get("position", [0, 0])) == source_position_before
        and lab.get("active_plan_id") == source_plan_id
        and int(plan.get("next_step_index", 0) or 0) == source_step_before
        and plan.get("status") == "active"
    )
    probe["source_position_before"] = source_position_before
    probe["source_position_after"] = list(lab.get("position", [0, 0]))
    probe["source_plan_preserved"] = source_plan_preserved
    decision["probe_id"] = probe["id"]
    decision["outcome"] = interpretation

    return {
        "id": probe["id"],
        "execution_kind": "transfer_probe",
        "cycle": cycle,
        "goal_id": goal.get("id"),
        "plan_id": source_plan_id,
        "step_index": source_step_before,
        "plan_length": len(plan.get("actions", [])),
        "action": action,
        "before": probe_state,
        "predicted_after": selected_prediction,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_prediction": matched_selected_prior,
        "source_world_version": decision["source_world_version"],
        "world_version": TRANSFER_WORLD_VERSION,
        "lab_version": PLANNING_LAB_VERSION,
        "status": lab.get("status"),
        "goal": list(goal.get("target", [])),
        "goal_reached": False,
        "replan_required": False,
        "model_revision_id": None,
        "source_model_revision_id": decision["source_model_revision_id"],
        "transfer_decision_id": decision["id"],
        "transfer_probe_id": probe["id"],
        "target_evidence_samples_before": decision[
            "target_evidence_samples_before"
        ],
        "target_evidence_samples_after": probe[
            "target_evidence_samples_after"
        ],
        "source_specific_prediction": list(
            decision["source_specific_prediction"]
        ),
        "counterfactual_prior": decision["counterfactual_prior"],
        "counterfactual_prediction": counterfactual_prediction,
        "selected_prior": decision["selected_prior"],
        "interpretation": interpretation,
        "source_plan_preserved": source_plan_preserved,
        "remaining_plan_steps": len(plan.get("actions", [])) - source_step_before,
        "learned_effects": json.loads(
            json.dumps(lab.get("learned_effects", {}))
        ),
    }



def _select_self_generated_experiment(
    lab: dict[str, Any],
    goal: dict[str, Any],
    plan: dict[str, Any],
    cycle: int,
) -> dict[str, Any] | None:
    """Choose one falsifiable local experiment from accumulated evidence."""

    started = lab.get("self_experiment_started_cycle")
    if started is None or cycle <= int(started or 0):
        return None
    if str(lab.get("world_version") or STATEFUL_WORLD_VERSION) != STATEFUL_WORLD_VERSION:
        return None
    if plan.get("status") != "active":
        return None

    step_index = int(plan.get("next_step_index", 0) or 0)
    actions = list(plan.get("actions", []))
    remaining_goal_steps = max(0, len(actions) - step_index)
    if (
        step_index < SELF_EXPERIMENT_MIN_COMPLETED_PLAN_STEPS
        or remaining_goal_steps < SELF_EXPERIMENT_MIN_REMAINING_PLAN_STEPS
        or step_index >= len(actions)
    ):
        return None

    if any(
        item.get("goal_id") == goal.get("id")
        for item in lab.get("self_experiments", [])
    ):
        return None

    last_cycle = lab.get("last_self_experiment_cycle")
    if (
        last_cycle is not None
        and cycle - int(last_cycle or 0) < SELF_EXPERIMENT_COOLDOWN_CYCLES
    ):
        return None

    latest_curiosity_probe = (
        lab.get("curiosity_probes", [])[-1]
        if lab.get("curiosity_probes")
        else None
    )
    if (
        isinstance(latest_curiosity_probe, dict)
        and latest_curiosity_probe.get("plan_id") == plan.get("id")
        and int(latest_curiosity_probe.get("cycle", -1) or -1) == cycle - 1
        and latest_curiosity_probe.get("resulting_status") == "executing_plan"
        and latest_curiosity_probe.get("after")
        == latest_curiosity_probe.get("before")
    ):
        return None

    latest_transfer_probe = (
        lab.get("transfer_probes", [])[-1]
        if lab.get("transfer_probes")
        else None
    )
    if (
        isinstance(latest_transfer_probe, dict)
        and latest_transfer_probe.get("plan_id") == plan.get("id")
        and int(latest_transfer_probe.get("cycle", -1) or -1) == cycle - 1
        and latest_transfer_probe.get("source_plan_preserved") is True
    ):
        return None

    position = [int(value) for value in lab.get("position", [0, 0])]
    next_goal_action = str(actions[step_index])
    bounds = int(lab.get("bounds", BOUNDS))
    learned = lab.get("learned_effects", {})
    state_effects = lab.get("state_effects", {})
    observations = lab.get("transition_observations", [])
    prior_keys = {
        str(item.get("state_action_key") or "")
        for item in lab.get("self_experiments", [])
    }

    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for action in ACTION_ORDER:
        if action == next_goal_action:
            continue
        key = _state_action_key(position, action)
        if key in prior_keys:
            continue
        state_effect = state_effects.get(key, {})
        state_samples = int(state_effect.get("samples", 0) or 0)
        if state_samples != 0:
            continue

        general_effect = learned.get(action, {})
        delta = general_effect.get("modal_delta")
        general_samples = int(general_effect.get("unblocked_samples", 0) or 0)
        confidence = float(general_effect.get("confidence", 0.0) or 0.0)
        if (
            general_samples < MIN_MODEL_SAMPLES
            or confidence <= 0.0
            or not isinstance(delta, list)
            or len(delta) != 2
        ):
            continue

        predicted_after = [
            position[0] + int(delta[0]),
            position[1] + int(delta[1]),
        ]
        if not _in_bounds(
            (predicted_after[0], predicted_after[1]),
            bounds,
        ):
            continue

        source_refs = [
            str(item.get("source_id") or "")
            for item in observations
            if (
                item.get("action") == action
                and item.get("blocked") is False
                and item.get("delta") == delta
                and item.get("source_id")
            )
        ][-8:]
        if not source_refs:
            continue

        information_value = round(1.0 / (state_samples + 1), 6)
        goal_delay_cost = round(1.0 / (remaining_goal_steps + 1), 6)
        decision_margin = round(information_value - goal_delay_cost, 6)
        if decision_margin <= 0.0:
            continue

        payload = {
            "state_action_key": key,
            "state": position,
            "action": action,
            "predicted_after": predicted_after,
            "state_samples_before": state_samples,
            "general_action_samples": general_samples,
            "general_confidence": round(confidence, 6),
            "source_observation_refs": source_refs,
            "information_value": information_value,
            "goal_delay_cost": goal_delay_cost,
            "decision_margin": decision_margin,
        }
        candidates.append(
            (
                state_samples,
                general_samples,
                ACTION_ORDER.index(action),
                payload,
            )
        )

    if not candidates:
        return None

    _, _, _, selected = min(candidates)
    decision = {
        "id": f"SED{len(lab.get('self_experiment_decisions', [])) + 1:06d}",
        "cycle": cycle,
        "policy_version": SELF_EXPERIMENT_POLICY_VERSION,
        "goal_id": goal.get("id"),
        "plan_id": plan.get("id"),
        "plan_next_step_index": step_index,
        "next_goal_action": next_goal_action,
        **selected,
        "hypothesis": (
            f"At state {selected['state']}, action {selected['action']} will "
            f"follow the learned general effect and reach "
            f"{selected['predicted_after']}."
        ),
        "falsification": (
            f"Any observed result other than {selected['predicted_after']} "
            "falsifies this local prediction."
        ),
        "status": "experiment_selected",
        "rationale": (
            "This current-state action has no state-specific evidence, while "
            "the general action effect is evidence-backed; one bounded action "
            "can test the prediction at lower cost than its information value."
        ),
    }
    lab.setdefault("self_experiment_decisions", []).append(decision)
    return decision


def _execute_self_generated_experiment(
    lab: dict[str, Any],
    goal: dict[str, Any],
    plan: dict[str, Any],
    decision: dict[str, Any],
    cycle: int,
) -> dict[str, Any]:
    """Run exactly one internally selected falsifiable bounded-world action."""

    before = [int(value) for value in decision["state"]]
    action = str(decision["action"])
    predicted_after = [int(value) for value in decision["predicted_after"]]
    world_version = str(lab.get("world_version") or STATEFUL_WORLD_VERSION)

    outcome = apply_bounded_action(
        before,
        action,
        bounds=int(lab.get("bounds", BOUNDS)),
        world_version=world_version,
    )
    after = list(outcome["after"])
    matched_prediction = after == predicted_after
    interpretation = (
        "hypothesis_supported"
        if matched_prediction
        else "hypothesis_refuted"
    )
    experiment = {
        "id": f"SE{len(lab.get('self_experiments', [])) + 1:06d}",
        "cycle": cycle,
        "policy_version": SELF_EXPERIMENT_POLICY_VERSION,
        "decision_id": decision["id"],
        "goal_id": goal.get("id"),
        "plan_id": plan.get("id"),
        "plan_next_step_index": int(plan.get("next_step_index", 0) or 0),
        "state_action_key": decision["state_action_key"],
        "action": action,
        "before": before,
        "predicted_after": predicted_after,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_prediction": matched_prediction,
        "hypothesis": decision["hypothesis"],
        "falsification": decision["falsification"],
        "source_observation_refs": list(
            decision.get("source_observation_refs", [])
        ),
        "state_samples_before": int(decision["state_samples_before"]),
        "information_value": float(decision["information_value"]),
        "goal_delay_cost": float(decision["goal_delay_cost"]),
        "decision_margin": float(decision["decision_margin"]),
        "interpretation": interpretation,
        "world_version": world_version,
    }
    lab.setdefault("self_experiments", []).append(experiment)
    lab["last_self_experiment_cycle"] = cycle
    decision["experiment_id"] = experiment["id"]
    decision["outcome"] = interpretation

    lab["position"] = after
    position_key = _position_key(after)
    lab.setdefault("visit_counts", {})[position_key] = (
        int(lab["visit_counts"].get(position_key, 0) or 0) + 1
    )
    lab["last_action_cycle"] = cycle
    lab.setdefault("transition_observations", []).append(
        {
            "source": "self_generated_experiment",
            "source_id": experiment["id"],
            "cycle": cycle,
            "action": action,
            "before": before,
            "after": after,
            "delta": list(outcome["delta"]),
            "blocked": bool(outcome["blocked"]),
            "world_version": world_version,
        }
    )
    learned = _rebuild_model(lab)
    effect_after = lab.get("state_effects", {}).get(
        decision["state_action_key"],
        {},
    )
    experiment["state_samples_after"] = int(
        effect_after.get("samples", 0) or 0
    )

    revision_id = None
    if not matched_prediction:
        revision = {
            "id": f"MR{len(lab.get('model_revisions', [])) + 1:06d}",
            "cycle": cycle,
            "trigger_self_experiment_id": experiment["id"],
            "goal_id": goal.get("id"),
            "plan_id": plan.get("id"),
            "state_action_key": decision["state_action_key"],
            "before": before,
            "action": action,
            "predicted_after": predicted_after,
            "observed_after": after,
            "observed_delta": list(outcome["delta"]),
            "observed_blocked": bool(outcome["blocked"]),
            "world_version": world_version,
            "status": "state_evidence_recorded",
        }
        lab.setdefault("model_revisions", []).append(revision)
        revision_id = revision["id"]

    goal_reached = after == list(goal.get("target", []))
    if goal_reached:
        plan["status"] = "completed"
        plan["completed_cycle"] = cycle
        plan["completion_reason"] = "self_experiment_reached_goal"
        goal["status"] = "completed"
        goal["completed_cycle"] = cycle
        goal["completed_plan_id"] = plan["id"]
        lab["active_plan_id"] = None
        lab["active_goal_id"] = None
        lab["status"] = "goal_reached"
    elif after != before:
        plan["status"] = "invalidated"
        plan["invalidated_cycle"] = cycle
        plan["invalidation_reason"] = "self_experiment_changed_state"
        plan["self_experiment_id"] = experiment["id"]
        lab["active_plan_id"] = None
        lab["status"] = "needs_replan"
    else:
        lab["status"] = "executing_plan"

    experiment["resulting_status"] = lab["status"]
    experiment["goal_reached"] = goal_reached
    experiment["replan_required"] = bool(
        after != before and not goal_reached
    )
    return {
        "id": experiment["id"],
        "execution_kind": "self_generated_experiment",
        "cycle": cycle,
        "goal_id": goal.get("id"),
        "plan_id": plan.get("id"),
        "step_index": int(decision["plan_next_step_index"]),
        "plan_length": len(plan.get("actions", [])),
        "action": action,
        "before": before,
        "predicted_after": predicted_after,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_prediction": matched_prediction,
        "world_version": world_version,
        "lab_version": PLANNING_LAB_VERSION,
        "status": lab["status"],
        "goal": list(goal.get("target", [])),
        "goal_reached": goal_reached,
        "replan_required": experiment["replan_required"],
        "model_revision_id": revision_id,
        "self_experiment_decision_id": decision["id"],
        "self_experiment_id": experiment["id"],
        "hypothesis": decision["hypothesis"],
        "falsification": decision["falsification"],
        "source_observation_refs": list(
            decision.get("source_observation_refs", [])
        ),
        "information_value": decision["information_value"],
        "goal_delay_cost": decision["goal_delay_cost"],
        "decision_margin": decision["decision_margin"],
        "state_samples_before": decision["state_samples_before"],
        "state_samples_after": experiment["state_samples_after"],
        "interpretation": interpretation,
        "remaining_plan_steps": (
            0
            if goal_reached or experiment["replan_required"]
            else len(plan.get("actions", []))
            - int(plan.get("next_step_index", 0) or 0)
        ),
        "learned_effects": learned,
    }


def _planning_episode_payload(episode: dict[str, Any]) -> dict[str, Any] | None:
    if episode.get("kind") != "planning_lab":
        return None
    content = episode.get("content")
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _consolidate_episodic_route_memories(
    state: dict[str, Any],
    lab: dict[str, Any],
    cycle: int,
) -> None:
    started = lab.get("episodic_memory_started_cycle")
    if started is None:
        lab["episodic_memory_started_cycle"] = cycle
        return
    started_cycle = int(started or 0)
    world_version = str(lab.get("world_version") or STATEFUL_WORLD_VERSION)
    completed = [
        plan
        for plan in lab.get("plans", [])
        if plan.get("status") == "completed"
        and int(plan.get("completed_cycle", 0) or 0) >= started_cycle
        and str(plan.get("world_version") or world_version) == world_version
    ]
    completed.sort(key=lambda plan: int(plan.get("completed_cycle", 0) or 0))
    completed = completed[-EPISODIC_MEMORY_MAX_ENTRIES:]
    memories = list(lab.get("episodic_route_memories", []))
    existing = {str(item.get("source_plan_id") or "") for item in memories}
    episodes = state.get("episodes", [])

    for plan in completed:
        plan_id = str(plan.get("id") or "")
        if not plan_id or plan_id in existing:
            continue
        executions = sorted(
            [
                item
                for item in lab.get("executions", [])
                if item.get("plan_id") == plan_id
                and item.get("matched_prediction") is True
            ],
            key=lambda item: (
                int(item.get("step_index", 0) or 0),
                int(item.get("cycle", 0) or 0),
            ),
        )
        if not executions:
            continue
        if any(
            int(item.get("cycle", 0) or 0) < started_cycle
            for item in executions
        ):
            continue
        execution_cycles = {int(item.get("cycle", 0) or 0) for item in executions}
        source_episode_ids: list[str] = []
        for episode in episodes:
            if int(episode.get("cycle", 0) or 0) not in execution_cycles:
                continue
            payload = _planning_episode_payload(episode)
            if payload is None or payload.get("plan_id") != plan_id:
                continue
            episode_id = str(episode.get("id") or "")
            if episode_id:
                source_episode_ids.append(episode_id)
        if len(source_episode_ids) != len(execution_cycles):
            continue

        state_action_keys = [
            _state_action_key(item.get("before", [0, 0]), str(item.get("action") or ""))
            for item in executions
            if str(item.get("action") or "") in ACTION_ORDER
        ]
        actions = [str(item.get("action") or "") for item in executions]
        action_bigrams = [
            f"{actions[index]}>{actions[index + 1]}"
            for index in range(len(actions) - 1)
        ]
        suffix = plan_id[2:] if plan_id.startswith("PP") else plan_id
        memory = {
            "id": f"EM{suffix}",
            "policy_version": EPISODIC_MEMORY_VERSION,
            "created_cycle": cycle,
            "source_plan_id": plan_id,
            "source_goal_id": plan.get("goal_id"),
            "source_episode_ids": source_episode_ids,
            "source_execution_ids": [item.get("id") for item in executions],
            "start": list(plan.get("start", [])),
            "goal": list(plan.get("goal", [])),
            "actions": actions,
            "state_action_keys": state_action_keys,
            "action_bigrams": action_bigrams,
            "completed_cycle": int(plan.get("completed_cycle", 0) or 0),
            "outcome": "goal_completed",
            "world_version": world_version,
        }
        memories.append(memory)
        existing.add(plan_id)

    lab["episodic_route_memories"] = memories[-EPISODIC_MEMORY_MAX_ENTRIES:]


def _shortest_plan_candidates(
    start: tuple[int, int],
    goal: tuple[int, int],
    learned: dict[str, Any],
    state_effects: dict[str, Any],
    bounds: int,
) -> list[tuple[list[str], list[list[int]]]]:
    counterfactual = _shortest_plan(start, goal, learned, state_effects, bounds)
    if counterfactual is None:
        return []
    target_length = len(counterfactual[0])
    if target_length == 0:
        return [counterfactual]

    queue = deque([(start, [], [], {start})])
    found: list[tuple[list[str], list[list[int]]]] = []
    seen_actions: set[tuple[str, ...]] = set()
    while queue and len(found) < EPISODIC_MEMORY_MAX_ROUTE_CANDIDATES:
        position, actions, predicted_states, visited = queue.popleft()
        if len(actions) >= target_length:
            continue
        for action in ACTION_ORDER:
            state_effect = state_effects.get(
                _state_action_key(position, action),
                {},
            )
            if state_effect.get("blocked"):
                continue
            delta = state_effect.get("modal_delta")
            if not isinstance(delta, list) or len(delta) != 2:
                delta = learned.get(action, {}).get("modal_delta")
            if not isinstance(delta, list) or len(delta) != 2:
                continue
            target = (
                int(position[0]) + int(delta[0]),
                int(position[1]) + int(delta[1]),
            )
            if not _in_bounds(target, bounds) or target in visited:
                continue
            next_actions = [*actions, action]
            next_states = [*predicted_states, [target[0], target[1]]]
            if target == goal:
                if len(next_actions) == target_length:
                    signature = tuple(next_actions)
                    if signature not in seen_actions:
                        found.append((next_actions, next_states))
                        seen_actions.add(signature)
                continue
            if len(next_actions) < target_length:
                queue.append(
                    (
                        target,
                        next_actions,
                        next_states,
                        {*visited, target},
                    )
                )

    signature = tuple(counterfactual[0])
    if signature not in seen_actions:
        found.insert(0, counterfactual)
    else:
        found.sort(key=lambda item: 0 if tuple(item[0]) == signature else 1)
    return found[:EPISODIC_MEMORY_MAX_ROUTE_CANDIDATES]


def _route_memory_features(
    start: tuple[int, int],
    actions: list[str],
    predicted_states: list[list[int]],
) -> tuple[list[str], list[str]]:
    before = [int(start[0]), int(start[1])]
    keys: list[str] = []
    for index, action in enumerate(actions):
        keys.append(_state_action_key(before, action))
        if index < len(predicted_states):
            before = [int(value) for value in predicted_states[index]]
    bigrams = [
        f"{actions[index]}>{actions[index + 1]}"
        for index in range(len(actions) - 1)
    ]
    return keys, bigrams


def _select_plan_with_episodic_memory(
    lab: dict[str, Any],
    goal: dict[str, Any],
    cycle: int,
    learned: dict[str, Any],
) -> tuple[list[str], list[list[int]], dict[str, Any] | None] | None:
    start = tuple(int(value) for value in lab.get("position", [0, 0]))
    target = tuple(int(value) for value in goal.get("target", [0, 0]))
    bounds = int(lab.get("bounds", BOUNDS))
    state_effects = lab.get("state_effects", {})
    counterfactual = _shortest_plan(start, target, learned, state_effects, bounds)
    if counterfactual is None:
        return None

    memories = [
        item
        for item in lab.get("episodic_route_memories", [])
        if item.get("outcome") == "goal_completed"
        and item.get("world_version")
        == str(lab.get("world_version") or STATEFUL_WORLD_VERSION)
    ]
    candidates = _shortest_plan_candidates(
        start,
        target,
        learned,
        state_effects,
        bounds,
    )
    if len(candidates) < 2 or not memories:
        return counterfactual[0], counterfactual[1], None

    edge_counts: Counter[str] = Counter()
    bigram_counts: Counter[str] = Counter()
    for memory in memories:
        edge_counts.update(str(key) for key in memory.get("state_action_keys", []))
        bigram_counts.update(str(key) for key in memory.get("action_bigrams", []))

    scored: list[
        tuple[int, int, list[str], list[list[int]], list[str], list[str]]
    ] = []
    for index, (actions, predicted_states) in enumerate(candidates):
        keys, bigrams = _route_memory_features(start, actions, predicted_states)
        replay_score = (
            2 * sum(int(edge_counts[key]) for key in keys)
            + sum(int(bigram_counts[key]) for key in bigrams)
        )
        scored.append(
            (replay_score, index, actions, predicted_states, keys, bigrams)
        )
    counterfactual_actions = list(counterfactual[0])
    counterfactual_item = next(
        item for item in scored if item[2] == counterfactual_actions
    )
    selected = min(scored, key=lambda item: (item[0], item[1]))
    changed_choice = (
        selected[2] != counterfactual_actions
        and selected[0] < counterfactual_item[0]
    )

    counterfactual_keys = set(counterfactual_item[4])
    counterfactual_bigrams = set(counterfactual_item[5])
    relevant_memories = [
        memory
        for memory in memories
        if counterfactual_keys.intersection(memory.get("state_action_keys", []))
        or counterfactual_bigrams.intersection(memory.get("action_bigrams", []))
    ][-8:]
    memory_refs = [str(item.get("id")) for item in relevant_memories if item.get("id")]
    episode_refs: list[str] = []
    for memory in relevant_memories:
        for ref in memory.get("source_episode_ids", []):
            ref = str(ref)
            if ref and ref not in episode_refs:
                episode_refs.append(ref)

    decision_id = f"MD{len(lab.get('plans', [])) + 1:06d}"
    decision = {
        "id": decision_id,
        "cycle": cycle,
        "policy_version": EPISODIC_MEMORY_VERSION,
        "goal_id": goal.get("id"),
        "start": [start[0], start[1]],
        "goal": [target[0], target[1]],
        "candidate_count": len(candidates),
        "counterfactual_actions": counterfactual_actions,
        "counterfactual_predicted_states": counterfactual[1],
        "counterfactual_replay_score": int(counterfactual_item[0]),
        "selected_actions": list(selected[2]),
        "selected_predicted_states": selected[3],
        "selected_replay_score": int(selected[0]),
        "changed_choice": changed_choice,
        "memory_refs": memory_refs,
        "source_episode_refs": episode_refs,
        "status": (
            "memory_changed_choice"
            if changed_choice
            else "counterfactual_retained"
        ),
        "rationale": (
            "Prefer an equally short valid route with less replayed episodic route history."
        ),
    }
    lab.setdefault("memory_decisions", []).append(decision)
    lab["memory_decisions"] = lab["memory_decisions"][
        -EPISODIC_MEMORY_MAX_DECISIONS:
    ]
    chosen = selected if changed_choice else counterfactual_item
    return list(chosen[2]), chosen[3], decision


def _recovered_self_experiment_refs(lab: dict[str, Any]) -> list[str]:
    """Return Phase 38 experiments whose interrupted goals later completed."""

    completed_goal_ids = {
        str(goal.get("id") or "")
        for goal in lab.get("goals", [])
        if goal.get("status") == "completed" and goal.get("id")
    }
    refs = [
        str(experiment.get("id") or "")
        for experiment in lab.get("self_experiments", [])
        if (
            experiment.get("goal_id") in completed_goal_ids
            and experiment.get("interpretation")
            in {"hypothesis_supported", "hypothesis_refuted"}
            and experiment.get("id")
        )
    ]
    return refs


def _objective_candidate_metrics(
    lab: dict[str, Any],
    *,
    target: tuple[int, int],
    visit_count: int,
    distance: int,
) -> dict[str, Any]:
    state_effects = lab.get("state_effects", {})
    unseen_actions = 0
    state_samples = 0
    for action in ACTION_ORDER:
        effect = state_effects.get(_state_action_key(target, action), {})
        samples = int(effect.get("samples", 0) or 0)
        state_samples += samples
        if samples == 0:
            unseen_actions += 1

    target_list = [int(target[0]), int(target[1])]
    memory_refs = [
        str(memory.get("id") or "")
        for memory in lab.get("episodic_route_memories", [])
        if (
            memory.get("outcome") == "goal_completed"
            and memory.get("goal") == target_list
            and memory.get("id")
        )
    ][-8:]

    novelty_value = round(1.0 / (visit_count + 1), 6)
    uncertainty_value = round(unseen_actions / max(1, len(ACTION_ORDER)), 6)
    memory_novelty_value = round(1.0 / (len(memory_refs) + 1), 6)
    information_value = round(
        novelty_value + uncertainty_value + memory_novelty_value,
        6,
    )
    max_bounded_distance = max(1, 4 * int(lab.get("bounds", BOUNDS)))
    action_cost = round(distance / max_bounded_distance, 6)
    objective_score = round(information_value - action_cost, 6)
    return {
        "target": target_list,
        "prior_visits": int(visit_count),
        "planned_distance": int(distance),
        "target_state_samples": int(state_samples),
        "unseen_target_actions": int(unseen_actions),
        "novelty_value": novelty_value,
        "uncertainty_value": uncertainty_value,
        "memory_novelty_value": memory_novelty_value,
        "information_value": information_value,
        "action_cost": action_cost,
        "objective_score": objective_score,
        "memory_refs": memory_refs,
    }


def _objective_outcome_metrics(
    lab: dict[str, Any],
    *,
    target: tuple[int, int],
    base_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Estimate future objective value from persisted Phase 40 outcomes only."""

    target_list = [int(target[0]), int(target[1])]
    learned = lab.get("learned_effects", {})
    state_effects = lab.get("state_effects", {})
    observations = lab.get("transition_observations", [])

    realization_action = None
    for action in ACTION_ORDER:
        key = _state_action_key(target, action)
        if int(state_effects.get(key, {}).get("samples", 0) or 0) != 0:
            continue
        general = learned.get(action, {})
        delta = general.get("modal_delta")
        if (
            int(general.get("unblocked_samples", 0) or 0) < MIN_MODEL_SAMPLES
            or float(general.get("confidence", 0.0) or 0.0) <= 0.0
            or not isinstance(delta, list)
            or len(delta) != 2
        ):
            continue
        source_refs = [
            str(item.get("source_id") or "")
            for item in observations
            if (
                item.get("action") == action
                and item.get("blocked") is False
                and item.get("delta") == delta
                and item.get("source_id")
            )
        ]
        if source_refs:
            realization_action = action
            break

    outcome_records = [
        item
        for item in lab.get("objective_realizations", [])
        if (
            realization_action is not None
            and item.get("action") == realization_action
            and item.get("id")
            and isinstance(item.get("realized_information_gain"), (int, float))
        )
    ]
    outcome_refs = [
        str(item.get("id") or "")
        for item in outcome_records
        if item.get("id")
    ][-16:]
    evidence_count = len(outcome_records)
    mean_realized_gain = round(
        (
            sum(float(item.get("realized_information_gain", 0.0) or 0.0) for item in outcome_records)
            / evidence_count
        )
        if evidence_count
        else 0.0,
        6,
    )
    evidence_weight = round(
        evidence_count / (evidence_count + 1),
        6,
    ) if evidence_count else 0.0
    outcome_value = round(mean_realized_gain * evidence_weight, 6)
    refutation_count = sum(
        1
        for item in outcome_records
        if item.get("interpretation") == "hypothesis_refuted"
    )
    refutation_rate = round(
        refutation_count / evidence_count,
        6,
    ) if evidence_count else 0.0
    base_score = float(base_metrics.get("objective_score", 0.0) or 0.0)
    return {
        **base_metrics,
        "phase40_realization_action": realization_action,
        "phase40_outcome_evidence_count": evidence_count,
        "phase40_outcome_refs": outcome_refs,
        "mean_realized_information_gain": mean_realized_gain,
        "outcome_evidence_weight": evidence_weight,
        "outcome_value": outcome_value,
        "outcome_refutation_rate": refutation_rate,
        "outcome_adjusted_score": round(base_score + outcome_value, 6),
        "outcome_target": target_list,
    }


def _outcome_valuation_ready(lab: dict[str, Any], cycle: int) -> bool:
    started = lab.get("outcome_valuation_started_cycle")
    if started is None or cycle <= int(started or 0):
        return False
    outcomes = [
        item
        for item in lab.get("objective_realizations", [])
        if (
            item.get("id")
            and isinstance(item.get("realized_information_gain"), (int, float))
            and item.get("action") in ACTION_ORDER
        )
    ]
    actions = {str(item.get("action")) for item in outcomes}
    return (
        len(outcomes) >= OUTCOME_VALUATION_MIN_REALIZATIONS
        and len(actions) >= OUTCOME_VALUATION_MIN_ACTIONS
    )


def _latest_pending_objective_realization(lab: dict[str, Any]) -> dict[str, Any] | None:
    active_id = lab.get("active_objective_realization_id")
    if not active_id:
        return None
    return next(
        (
            item
            for item in lab.get("objective_realization_decisions", [])
            if item.get("id") == active_id and item.get("status") == "precommitted"
        ),
        None,
    )


def _select_objective_realization(
    lab: dict[str, Any],
    cycle: int,
) -> dict[str, Any] | None:
    """Precommit one local information-gathering action after a self-selected goal."""

    started = lab.get("objective_realization_started_cycle")
    if started is None or cycle <= int(started or 0):
        return None
    if lab.get("active_goal_id") is not None:
        return None
    if _latest_pending_objective_realization(lab) is not None:
        return None

    realized_goal_ids = {
        str(item.get("goal_id") or "")
        for item in lab.get("objective_realizations", [])
        if item.get("goal_id")
    }
    decisions_by_id = {
        str(item.get("id") or ""): item
        for item in lab.get("objective_decisions", [])
        if item.get("id")
    }
    candidates = [
        goal
        for goal in lab.get("goals", [])
        if (
            goal.get("status") == "completed"
            and int(goal.get("assigned_cycle", 0) or 0) > int(started or 0)
            and goal.get("selection", {}).get("kind")
            in {"self_selected_bounded_objective", "outcome_aware_bounded_objective"}
            and str(goal.get("id") or "") not in realized_goal_ids
        )
    ]
    if not candidates:
        return None

    goal = candidates[-1]
    selection = goal.get("selection", {})
    objective_decision = decisions_by_id.get(
        str(selection.get("objective_decision_id") or "")
    )
    if not objective_decision or not (
        objective_decision.get("changed_choice") is True
        or objective_decision.get("outcome_changed_choice") is True
    ):
        return None

    _rebuild_model(lab)
    position = [int(value) for value in lab.get("position", [0, 0])]
    if position != list(goal.get("target", [])):
        return None

    learned = lab.get("learned_effects", {})
    state_effects = lab.get("state_effects", {})
    bounds = int(lab.get("bounds", BOUNDS))
    observations = lab.get("transition_observations", [])
    action_candidates: list[tuple[int, str, list[int], list[str]]] = []
    for order, action in enumerate(ACTION_ORDER):
        key = _state_action_key(position, action)
        if int(state_effects.get(key, {}).get("samples", 0) or 0) != 0:
            continue
        general = learned.get(action, {})
        delta = general.get("modal_delta")
        if (
            int(general.get("unblocked_samples", 0) or 0) < MIN_MODEL_SAMPLES
            or float(general.get("confidence", 0.0) or 0.0) <= 0.0
            or not isinstance(delta, list)
            or len(delta) != 2
        ):
            continue
        predicted_after = [
            position[0] + int(delta[0]),
            position[1] + int(delta[1]),
        ]
        refs = [
            str(item.get("source_id") or "")
            for item in observations
            if (
                item.get("action") == action
                and item.get("blocked") is False
                and item.get("delta") == delta
                and item.get("source_id")
            )
        ][-8:]
        if not refs:
            continue
        action_candidates.append((order, action, predicted_after, refs))

    if not action_candidates:
        return None

    _, action, predicted_after, source_refs = min(action_candidates)
    key = _state_action_key(position, action)
    decision = {
        "id": f"OR{len(lab.get('objective_realization_decisions', [])) + 1:06d}",
        "cycle": cycle,
        "policy_version": OBJECTIVE_REALIZATION_POLICY_VERSION,
        "status": "precommitted",
        "goal_id": goal.get("id"),
        "objective_decision_id": objective_decision.get("id"),
        "state": position,
        "state_action_key": key,
        "action": action,
        "predicted_after": predicted_after,
        "hypothesis": (
            f"At {position}, {action} will follow the learned general effect "
            f"and produce {predicted_after}."
        ),
        "falsification": (
            f"Any observed result other than {predicted_after} falsifies this "
            "local transfer of the learned general effect."
        ),
        "source_observation_refs": source_refs,
        "state_samples_before": 0,
        "expected_information_gain": 1.0,
        "rationale": (
            "The completed self-selected objective was valuable partly because "
            "this local action had no state-specific evidence. Test exactly one "
            "such action before selecting another goal."
        ),
    }
    lab.setdefault("objective_realization_decisions", []).append(decision)
    lab["objective_realization_decisions"] = lab[
        "objective_realization_decisions"
    ][-OBJECTIVE_REALIZATION_MAX_RECORDS:]
    lab["active_objective_realization_id"] = decision["id"]
    lab["status"] = "objective_realization_precommitted"
    return decision


def _execute_objective_realization(
    lab: dict[str, Any],
    decision: dict[str, Any],
    cycle: int,
) -> dict[str, Any]:
    """Execute a previously persisted Phase 40 precommit and measure realized gain."""

    before = [int(value) for value in lab.get("position", [0, 0])]
    if before != list(decision.get("state", [])):
        decision["status"] = "cancelled_position_changed"
        decision["cancelled_cycle"] = cycle
        lab["active_objective_realization_id"] = None
        lab["status"] = "objective_realization_cancelled"
        return {
            "lab_version": PLANNING_LAB_VERSION,
            "execution_kind": "objective_information_realization",
            "status": lab["status"],
            "action": None,
            "objective_realization_decision_id": decision.get("id"),
            "reason": "Position changed after the Phase 40 precommit; no action executed.",
        }

    action = str(decision.get("action") or "")
    predicted_after = list(decision.get("predicted_after", []))
    key = _state_action_key(before, action)
    _rebuild_model(lab)
    samples_before = int(lab.get("state_effects", {}).get(key, {}).get("samples", 0) or 0)
    outcome = apply_bounded_action(
        before,
        action,
        bounds=int(lab.get("bounds", BOUNDS)),
        world_version=str(lab.get("world_version") or STATEFUL_WORLD_VERSION),
    )
    after = list(outcome["after"])
    matched_prediction = after == predicted_after
    realization_id = f"OI{len(lab.get('objective_realizations', [])) + 1:06d}"
    lab.setdefault("transition_observations", []).append(
        {
            "source": "objective_information_realization",
            "source_id": realization_id,
            "cycle": cycle,
            "action": action,
            "before": before,
            "after": after,
            "delta": list(outcome["delta"]),
            "blocked": bool(outcome["blocked"]),
            "world_version": str(lab.get("world_version") or STATEFUL_WORLD_VERSION),
        }
    )
    lab["position"] = after
    position_key = _position_key(after)
    lab.setdefault("visit_counts", {})[position_key] = (
        int(lab["visit_counts"].get(position_key, 0) or 0) + 1
    )
    lab["last_action_cycle"] = cycle
    _rebuild_model(lab)
    samples_after = int(lab.get("state_effects", {}).get(key, {}).get("samples", 0) or 0)
    realized_information_gain = round(
        min(1.0, max(0, samples_after - samples_before)),
        6,
    )
    realization = {
        "id": realization_id,
        "cycle": cycle,
        "policy_version": OBJECTIVE_REALIZATION_POLICY_VERSION,
        "decision_id": decision.get("id"),
        "goal_id": decision.get("goal_id"),
        "objective_decision_id": decision.get("objective_decision_id"),
        "state_action_key": key,
        "action": action,
        "before": before,
        "predicted_after": predicted_after,
        "after": after,
        "delta": list(outcome["delta"]),
        "blocked": bool(outcome["blocked"]),
        "matched_prediction": matched_prediction,
        "state_samples_before": samples_before,
        "state_samples_after": samples_after,
        "expected_information_gain": float(
            decision.get("expected_information_gain", 0.0) or 0.0
        ),
        "realized_information_gain": realized_information_gain,
        "interpretation": (
            "hypothesis_supported"
            if matched_prediction
            else "hypothesis_refuted"
        ),
    }
    lab.setdefault("objective_realizations", []).append(realization)
    lab["objective_realizations"] = lab["objective_realizations"][
        -OBJECTIVE_REALIZATION_MAX_RECORDS:
    ]
    decision["status"] = "completed"
    decision["completed_cycle"] = cycle
    decision["realization_id"] = realization_id
    decision["realized_information_gain"] = realized_information_gain
    decision["interpretation"] = realization["interpretation"]
    lab["active_objective_realization_id"] = None
    lab["status"] = "objective_information_realized"
    return {
        **realization,
        "execution_kind": "objective_information_realization",
        "lab_version": PLANNING_LAB_VERSION,
        "status": lab["status"],
        "goal": list(decision.get("state", [])),
        "goal_reached": False,
        "replan_required": False,
        "remaining_plan_steps": 0,
        "objective_realization_decision_id": decision.get("id"),
        "objective_realization_id": realization_id,
        "learned_effects": json.loads(json.dumps(lab.get("learned_effects", {}))),
    }


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
            planned = _shortest_plan(
                start,
                target,
                learned,
                lab.get("state_effects", {}),
                bounds,
            )
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
    counterfactual = min(
        pool,
        key=lambda item: (
            item[0],
            -item[1],
            item[2],
            item[3],
        ),
    )
    chosen = counterfactual
    objective_decision = None

    recovered_experiment_refs = _recovered_self_experiment_refs(lab)
    started = lab.get("objective_selection_started_cycle")
    last_selection_cycle = lab.get("last_objective_selection_cycle")
    objective_selection_ready = (
        started is not None
        and cycle > int(started or 0)
        and len(recovered_experiment_refs)
        >= OBJECTIVE_SELECTION_MIN_RECOVERED_EXPERIMENTS
        and (
            last_selection_cycle is None
            or cycle - int(last_selection_cycle or 0)
            >= OBJECTIVE_SELECTION_COOLDOWN_CYCLES
        )
    )

    if objective_selection_ready:
        scored: list[
            tuple[
                float,
                int,
                int,
                int,
                int,
                tuple[int, int, int, int, list[str], list[list[int]]],
                dict[str, Any],
            ]
        ] = []
        for item in pool:
            visit_count, distance, x, y, _, _ = item
            metrics = _objective_candidate_metrics(
                lab,
                target=(x, y),
                visit_count=visit_count,
                distance=distance,
            )
            scored.append(
                (
                    -float(metrics["objective_score"]),
                    visit_count,
                    -distance,
                    x,
                    y,
                    item,
                    metrics,
                )
            )
        scored.sort(key=lambda item: item[:5])
        phase39_item = scored[0][5]
        phase39_metrics = scored[0][6]
        selected_item = phase39_item
        selected_metrics = phase39_metrics
        outcome_changed_choice = False
        outcome_decision_margin = 0.0
        outcome_policy_ready = _outcome_valuation_ready(lab, cycle)

        outcome_scored: list[
            tuple[
                float,
                int,
                int,
                int,
                int,
                tuple[int, int, int, int, list[str], list[list[int]]],
                dict[str, Any],
            ]
        ] = []
        if outcome_policy_ready:
            for item in pool:
                visit_count, distance, x, y, _, _ = item
                base_metrics = _objective_candidate_metrics(
                    lab,
                    target=(x, y),
                    visit_count=visit_count,
                    distance=distance,
                )
                metrics = _objective_outcome_metrics(
                    lab,
                    target=(x, y),
                    base_metrics=base_metrics,
                )
                outcome_scored.append(
                    (
                        -float(metrics["outcome_adjusted_score"]),
                        visit_count,
                        -distance,
                        x,
                        y,
                        item,
                        metrics,
                    )
                )
            outcome_scored.sort(key=lambda item: item[:5])
            outcome_item = outcome_scored[0][5]
            outcome_metrics = outcome_scored[0][6]
            phase39_outcome_metrics = _objective_outcome_metrics(
                lab,
                target=(phase39_item[2], phase39_item[3]),
                base_metrics=phase39_metrics,
            )
            outcome_decision_margin = round(
                float(outcome_metrics["outcome_adjusted_score"])
                - float(phase39_outcome_metrics["outcome_adjusted_score"]),
                6,
            )
            outcome_changed_choice = (
                [outcome_item[2], outcome_item[3]]
                != [phase39_item[2], phase39_item[3]]
                and outcome_decision_margin > 0.0
            )
            if outcome_changed_choice:
                selected_item = outcome_item
                selected_metrics = outcome_metrics
            else:
                selected_metrics = phase39_outcome_metrics

        counterfactual_metrics = _objective_candidate_metrics(
            lab,
            target=(counterfactual[2], counterfactual[3]),
            visit_count=counterfactual[0],
            distance=counterfactual[1],
        )
        if outcome_policy_ready:
            counterfactual_for_margin = _objective_outcome_metrics(
                lab,
                target=(counterfactual[2], counterfactual[3]),
                base_metrics=counterfactual_metrics,
            )
            selected_score = float(selected_metrics["outcome_adjusted_score"])
            counterfactual_score = float(
                counterfactual_for_margin["outcome_adjusted_score"]
            )
        else:
            selected_score = float(selected_metrics["objective_score"])
            counterfactual_score = float(counterfactual_metrics["objective_score"])
        decision_margin = round(selected_score - counterfactual_score, 6)
        changed_choice = (
            [selected_item[2], selected_item[3]]
            != [counterfactual[2], counterfactual[3]]
            and decision_margin > 0.0
        )
        if changed_choice or outcome_changed_choice:
            chosen = selected_item

        top_candidates = [
            entry[6]
            for entry in (
                outcome_scored
                if outcome_policy_ready
                else scored
            )[: min(5, len(scored))]
        ]
        outcome_refs = sorted(
            {
                ref
                for metrics in top_candidates
                for ref in metrics.get("phase40_outcome_refs", [])
            }
        )
        objective_decision = {
            "id": f"OD{len(lab.get('objective_decisions', [])) + 1:06d}",
            "cycle": cycle,
            "policy_version": (
                OUTCOME_AWARE_OBJECTIVE_POLICY_VERSION
                if outcome_policy_ready
                else OBJECTIVE_SELECTION_POLICY_VERSION
            ),
            "status": (
                "outcome_evidence_changed_choice"
                if outcome_changed_choice
                else (
                    "objective_changed_choice"
                    if changed_choice
                    else "counterfactual_retained"
                )
            ),
            "changed_choice": changed_choice,
            "outcome_changed_choice": outcome_changed_choice,
            "candidate_count": len(pool),
            "counterfactual_policy": "least_visited_farthest_reachable",
            "counterfactual": counterfactual_metrics,
            "phase39_counterfactual": phase39_metrics,
            "selected": (
                selected_metrics
                if (changed_choice or outcome_changed_choice)
                else counterfactual_metrics
            ),
            "best_scored_candidate": selected_metrics,
            "decision_margin": decision_margin,
            "outcome_decision_margin": outcome_decision_margin,
            "outcome_evidence_refs": outcome_refs,
            "phase38_recovery_refs": recovered_experiment_refs[
                -OBJECTIVE_SELECTION_MIN_RECOVERED_EXPERIMENTS:
            ],
            "candidate_summaries": top_candidates,
            "rationale": (
                "Use measured Phase 40 information outcomes to adjust the "
                "existing bounded objective valuation while preserving the "
                "Phase 39 choice as an explicit counterfactual."
                if outcome_policy_ready
                else (
                    "Prefer a reachable bounded objective with greater evidence value "
                    "after accounting for travel cost and remembered familiarity."
                )
            ),
        }
        lab.setdefault("objective_decisions", []).append(objective_decision)
        lab["objective_decisions"] = lab["objective_decisions"][
            -OBJECTIVE_SELECTION_MAX_DECISIONS:
        ]
        lab["last_objective_selection_cycle"] = cycle

    visit_count, distance, x, y, _, _ = chosen
    selection_kind = (
        "outcome_aware_bounded_objective"
        if (
            objective_decision is not None
            and objective_decision.get("outcome_changed_choice") is True
        )
        else (
            "self_selected_bounded_objective"
            if (
                objective_decision is not None
                and objective_decision.get("changed_choice") is True
            )
            else "least_visited_farthest_reachable"
        )
    )
    goal = {
        "id": f"PG{len(lab.get('goals', [])) + 1:06d}",
        "assigned_cycle": cycle,
        "target": [x, y],
        "status": "active",
        "selection": {
            "kind": selection_kind,
            "prior_visits": visit_count,
            "planned_distance": distance,
            "preferred_step_range": [
                PREFERRED_MIN_PLAN_STEPS,
                PREFERRED_MAX_PLAN_STEPS,
            ],
            "objective_decision_id": (
                objective_decision.get("id")
                if objective_decision is not None
                else None
            ),
            "counterfactual_target": (
                list(objective_decision["counterfactual"]["target"])
                if objective_decision is not None
                else None
            ),
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
    planned = _select_plan_with_episodic_memory(
        lab,
        goal,
        cycle,
        learned,
    )
    if planned is None:
        lab["status"] = "blocked_no_plan"
        return None

    actions, predicted_states, memory_decision = planned
    memory_influenced = bool(
        memory_decision and memory_decision.get("changed_choice")
    )
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
        "memory_selection_reason": (
            "episodic_memory_tiebreak"
            if memory_influenced
            else None
        ),
        "world_version": str(
            lab.get("world_version") or STATEFUL_WORLD_VERSION
        ),
        "model_samples": {
            action: int(
                learned.get(action, {}).get("unblocked_samples", 0) or 0
            )
            for action in ACTION_ORDER
        },
        "memory_decision_id": (
            memory_decision.get("id") if memory_decision else None
        ),
        "memory_influenced": memory_influenced,
        "memory_refs": (
            list(memory_decision.get("memory_refs", []))
            if memory_decision
            else []
        ),
        "memory_episode_refs": (
            list(memory_decision.get("source_episode_refs", []))
            if memory_decision
            else []
        ),
        "counterfactual_actions": (
            list(memory_decision.get("counterfactual_actions", []))
            if memory_decision
            else actions
        ),
        "counterfactual_replay_score": (
            memory_decision.get("counterfactual_replay_score")
            if memory_decision
            else None
        ),
        "selected_replay_score": (
            memory_decision.get("selected_replay_score")
            if memory_decision
            else None
        ),
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

    _consolidate_episodic_route_memories(state, lab, cycle)

    pending_realization = _latest_pending_objective_realization(lab)
    if pending_realization is not None:
        return _execute_objective_realization(lab, pending_realization, cycle)

    if _active_goal(lab) is None:
        selected_realization = _select_objective_realization(lab, cycle)
        if selected_realization is not None:
            return {
                "lab_version": PLANNING_LAB_VERSION,
                "execution_kind": "objective_information_precommit",
                "status": lab.get("status"),
                "action": None,
                "goal_id": selected_realization.get("goal_id"),
                "objective_realization_decision_id": selected_realization.get("id"),
                "hypothesis": selected_realization.get("hypothesis"),
                "falsification": selected_realization.get("falsification"),
                "expected_information_gain": selected_realization.get(
                    "expected_information_gain"
                ),
                "reason": "Phase 40 precommitted a bounded evidence-realization action before acting.",
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
            reason=(
                "replan_after_invalidation"
                if lab.get("status") == "needs_replan"
                else "initial_goal_plan"
            ),
        )
    if plan is None:
        return {
            "lab_version": PLANNING_LAB_VERSION,
            "status": lab.get("status"),
            "action": None,
            "goal_id": goal.get("id"),
            "reason": "No learned multi-step plan reaches the active goal.",
        }

    curiosity_decision = _select_curiosity_probe(
        lab,
        goal,
        plan,
        cycle,
    )
    if curiosity_decision is not None:
        return _execute_curiosity_probe(
            lab,
            goal,
            plan,
            curiosity_decision,
            cycle,
        )

    transfer_decision = _select_transfer_probe(
        lab,
        goal,
        plan,
        cycle,
    )
    if transfer_decision is not None:
        return _execute_transfer_probe(
            lab,
            goal,
            plan,
            transfer_decision,
            cycle,
        )

    self_experiment_decision = _select_self_generated_experiment(
        lab,
        goal,
        plan,
        cycle,
    )
    if self_experiment_decision is not None:
        return _execute_self_generated_experiment(
            lab,
            goal,
            plan,
            self_experiment_decision,
            cycle,
        )

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
    world_version = str(
        lab.get("world_version") or STATEFUL_WORLD_VERSION
    )
    outcome = apply_bounded_action(
        before,
        action,
        bounds=int(lab.get("bounds", BOUNDS)),
        world_version=world_version,
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
        "world_version": world_version,
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
            "before": before,
            "after": after,
            "delta": list(outcome["delta"]),
            "blocked": bool(outcome["blocked"]),
            "world_version": world_version,
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
        revision = {
            "id": f"MR{len(lab.get('model_revisions', [])) + 1:06d}",
            "cycle": cycle,
            "trigger_execution_id": execution["id"],
            "goal_id": goal["id"],
            "plan_id": plan["id"],
            "state_action_key": _state_action_key(before, action),
            "before": before,
            "action": action,
            "predicted_after": predicted_after,
            "observed_after": after,
            "observed_delta": list(outcome["delta"]),
            "observed_blocked": bool(outcome["blocked"]),
            "world_version": world_version,
            "status": "state_evidence_recorded",
        }
        lab.setdefault("model_revisions", []).append(revision)
        lab["active_plan_id"] = None
        lab["status"] = "needs_replan"

    return {
        **execution,
        "lab_version": PLANNING_LAB_VERSION,
        "status": lab["status"],
        "goal": list(goal.get("target", [])),
        "goal_reached": goal_reached,
        "replan_required": not matched_prediction,
        "model_revision_id": (
            None
            if matched_prediction
            else lab.get("model_revisions", [{}])[-1].get("id")
        ),
        "remaining_plan_steps": (
            0
            if goal_reached or not matched_prediction
            else len(actions) - int(plan.get("next_step_index", 0) or 0)
        ),
        "memory_decision_id": plan.get("memory_decision_id"),
        "memory_influenced": bool(plan.get("memory_influenced")),
        "memory_refs": list(plan.get("memory_refs", [])),
        "memory_episode_refs": list(plan.get("memory_episode_refs", [])),
        "counterfactual_actions": list(plan.get("counterfactual_actions", [])),
        "counterfactual_replay_score": plan.get("counterfactual_replay_score"),
        "selected_replay_score": plan.get("selected_replay_score"),
        "learned_effects": learned,
    }
