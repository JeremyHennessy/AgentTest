"""Read-only original native-plan precommit and matched future comparison.

Reads original planner state only in the admission/score adapter. The new
two-clock learner never sees goals, plan IDs, future executions, or target.
No action is selected or executed here.
"""
from __future__ import annotations

from typing import Any

from agenttest.action_lab import ACTION_ORDER
from agenttest.two_clock_stream import DELTAS, digest

VERSION = "original-ora-native-plan-preaction-comparator-v1"


def _position(value: Any) -> list[int]:
    if (not isinstance(value, list) or len(value) != 2
            or any(type(x) is not int or not -2 <= x <= 2 for x in value)):
        raise ValueError("unverifiable original plan physical position")
    return list(value)


def _hash_id(kind: str, value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 160:
        raise ValueError("invalid source original goal/plan identity")
    return digest([VERSION, kind, value])


def _delta(before: list[int], after: list[int]) -> str:
    value = f"{after[0]-before[0]},{after[1]-before[1]}"
    if value not in DELTAS:
        raise ValueError("source planned outcome outside physical observation alphabet")
    return value


def freeze_plan(state: dict, source_commit: str, position: list[int]) -> dict:
    """Freeze ORIGINAL planner's *already precommitted next step*, if valid."""
    if not isinstance(state, dict) or not isinstance(state.get("planning_lab"), dict):
        raise ValueError("missing original planner")
    lab = state["planning_lab"]
    before = _position(position)
    plan_id = lab.get("active_plan_id")
    goal_id = lab.get("active_goal_id")
    if lab.get("active_objective_realization_id") is not None:
        return {"version": VERSION, "status": "pending_precommit", "source_commit": source_commit}
    if plan_id is None:
        return {"version": VERSION, "status": "no_active_plan", "source_commit": source_commit}
    if goal_id is None:
        return {"version": VERSION, "status": "plan_without_active_goal", "source_commit": source_commit}
    plans = lab.get("plans")
    goals = lab.get("goals")
    if not isinstance(plans, list) or not isinstance(goals, list):
        raise ValueError("original plan/goal registries are malformed")
    matches = [p for p in plans if isinstance(p, dict) and p.get("id") == plan_id]
    goal_matches = [g for g in goals if isinstance(g, dict) and g.get("id") == goal_id]
    if len(matches) != 1 or len(goal_matches) != 1:
        return {"version": VERSION, "status": "ambiguous_source_plan_or_goal", "source_commit": source_commit}
    plan, goal = matches[0], goal_matches[0]
    if (plan.get("status") != "active" or goal.get("status") != "active"
            or plan.get("goal_id") != goal_id):
        return {"version": VERSION, "status": "inactive_or_mismatched_plan", "source_commit": source_commit}
    steps, predicted = plan.get("actions"), plan.get("predicted_states")
    step = plan.get("next_step_index")
    if (not isinstance(steps, list) or not isinstance(predicted, list)
            or len(steps) != len(predicted) or not steps
            or type(step) is not int or step < 0 or step >= len(steps)):
        return {"version": VERSION, "status": "stale_or_invalid_plan_step", "source_commit": source_commit}
    action = steps[step]
    if action not in ACTION_ORDER:
        return {"version": VERSION, "status": "unknown_planned_command", "source_commit": source_commit}
    try:
        expected_after = _position(predicted[step])
        expected_delta = _delta(before, expected_after)
    except ValueError:
        return {"version": VERSION, "status": "invalid_planned_physical_effect", "source_commit": source_commit}
    # This plans NEXT remaining step, even when a previous step was consumed
    # in the frozen cycle. It never reuses a previously executed step index.
    return {
        "version": VERSION, "status": "frozen_valid_next_plan_step",
        "source_commit": source_commit,
        "plan_id_hash": _hash_id("plan", plan_id),
        "goal_id_hash": _hash_id("goal", goal_id),
        "step_index": step,
        "before": before,
        "action": action,
        "predicted_after": expected_after,
        "predicted_delta": expected_delta,
    }


def validate_preview(preview: Any, source_commit: str, source_position: list[int]) -> None:
    if not isinstance(preview, dict) or preview.get("version") != VERSION:
        raise ValueError("unknown planner comparator evidence version")
    if preview.get("source_commit") != source_commit:
        raise ValueError("planner precommit changed source after freezing")
    status = preview.get("status")
    allowed_abstain = {
        "pending_precommit", "no_active_plan", "plan_without_active_goal",
        "ambiguous_source_plan_or_goal", "inactive_or_mismatched_plan",
        "stale_or_invalid_plan_step", "unknown_planned_command",
        "invalid_planned_physical_effect",
    }
    if status in allowed_abstain:
        if set(preview) != {"version", "status", "source_commit"}:
            raise ValueError("forged noncommittal planner expectation")
        return
    required = {
        "version", "status", "source_commit", "plan_id_hash",
        "goal_id_hash", "step_index", "before", "action", "predicted_after",
        "predicted_delta",
    }
    if status != "frozen_valid_next_plan_step" or set(preview) != required:
        raise ValueError("invalid frozen native plan step schema")
    if (type(preview["step_index"]) is not int or preview["step_index"] < 0
            or preview["action"] not in ACTION_ORDER
            or not all(isinstance(preview[k], str) and len(preview[k]) == 64
                       and all(c in "0123456789abcdef" for c in preview[k])
                       for k in ("plan_id_hash", "goal_id_hash"))
            or _position(preview["before"]) != _position(source_position)
            or _delta(preview["before"], _position(preview["predicted_after"]))
            != preview["predicted_delta"]):
        raise ValueError("unsupported native plan expectation or original identity")


def compare_future(
    old_preview: dict | None, *, current_lab: dict, first: dict,
    old_source_commit: str, old_position: list[int],
    learned_scores: dict[str, dict],
) -> dict:
    if old_preview is None:
        return {"status": "not_frozen_by_old_shadow_version", "credit": False}
    validate_preview(old_preview, old_source_commit, old_position)
    if old_preview["status"] != "frozen_valid_next_plan_step":
        return {"status": old_preview["status"], "credit": False}
    if first.get("source") != "planning_lab":
        return {"status": "first_action_not_legacy_plan_execution", "credit": False}
    if first.get("action") != old_preview["action"]:
        return {"status": "original_plan_did_not_choose_frozen_action", "credit": False}
    if first.get("before") != old_position:
        raise ValueError("planner scorer input is not first frozen public context")
    record_id = first.get("source_id")
    executions = current_lab.get("executions")
    if not isinstance(executions, list):
        raise ValueError("source original executions are malformed")
    events = [x for x in executions if isinstance(x, dict) and x.get("id") == record_id]
    if len(events) != 1:
        return {"status": "missing_or_ambiguous_native_execution", "credit": False}
    executed = events[0]
    if (type(executed.get("step_index")) is not int
            or executed["step_index"] != old_preview["step_index"]
            or executed.get("action") != old_preview["action"]
            or executed.get("before") != old_preview["before"]
            or _hash_id("plan", executed.get("plan_id")) != old_preview["plan_id_hash"]
            or _hash_id("goal", executed.get("goal_id")) != old_preview["goal_id_hash"]):
        return {"status": "different_native_plan_step", "credit": False}
    if executed.get("predicted_after") != old_preview["predicted_after"]:
        raise ValueError("original execution retroactively changed frozen plan forecast")
    after = _position(first.get("after"))
    actual = _delta(old_position, after)
    planned = old_preview["predicted_delta"]
    # Proper five-class Brier of a one-hot point forecast on the same
    # natural physical action. Not an adaptive calibration comparator.
    planning_brier = 0.0 if planned == actual else 2.0
    if not isinstance(learned_scores, dict) or "two_clock" not in learned_scores:
        raise ValueError("no independently frozen learned model on natural action")
    return {
        "status": "matched_original_plan_preaction_comparison", "credit": True,
        "plan_id_hash": old_preview["plan_id_hash"],
        "step_index": old_preview["step_index"],
        "original_expected_delta": planned,
        "naturally_observed_delta": actual,
        "original_planner_brier": planning_brier,
        "two_clock_brier": learned_scores["two_clock"]["brier"],
        "old_plan_matches_actual": planned == actual,
        "matched_natural_source_id": record_id,
        "prediction_not_goal_utility": True,
    }
