from __future__ import annotations

import json
from typing import Any

DIAGNOSTIC_VERSION = "blocked-attention-v1"


def evaluate_blocked_attention(state: dict[str, Any]) -> dict[str, Any]:
    """Read-only diagnostic for attention repeatedly returning to blocked experiments."""

    before = json.dumps(state, sort_keys=True)
    questions = {
        str(item.get("id")): item
        for item in state.get("questions", [])
        if item.get("id")
    }
    blocked = []
    reselected = []
    loops = []

    for experiment in state.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue
        specification = experiment.get("specification", {})
        if specification.get("actionability") != "blocked":
            continue

        experiment_id = str(experiment.get("id", ""))
        question_id = str(experiment.get("question_id") or "")
        question = questions.get(question_id, {})
        evaluated_cycle = int(specification.get("evaluated_cycle", 0) or 0)
        last_selected_cycle = int(experiment.get("last_selected_cycle", 0) or 0)
        experiment_times_selected = int(experiment.get("times_selected", 0) or 0)
        question_times_selected = int(question.get("times_selected", 0) or 0)
        selected_after_block = (
            evaluated_cycle > 0 and last_selected_cycle >= evaluated_cycle
        )

        record = {
            "experiment_id": experiment_id,
            "question_id": question_id or None,
            "question_text": question.get("text"),
            "evaluated_cycle": evaluated_cycle,
            "last_selected_cycle": last_selected_cycle,
            "experiment_times_selected": experiment_times_selected,
            "question_times_selected": question_times_selected,
            "selected_after_block": selected_after_block,
            "blocking_reason": specification.get("blocking_reason"),
            "missing_fields": list(specification.get("missing_fields", [])),
        }
        blocked.append(record)

        if selected_after_block:
            reselected.append(experiment_id)
            if experiment_times_selected >= 2 or question_times_selected >= 3:
                loops.append(record)

    if not blocked:
        outcome = "no_blocked_work"
    elif loops:
        outcome = "blocked_attention_loop"
    elif reselected:
        outcome = "blocked_attention_contact"
    else:
        outcome = "attention_redirected"

    result = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "outcome": outcome,
        "blocked_experiment_count": len(blocked),
        "blocked_experiment_ids": [item["experiment_id"] for item in blocked],
        "reselected_after_block_count": len(reselected),
        "reselected_after_block_ids": reselected,
        "loop_count": len(loops),
        "loop_experiment_ids": [item["experiment_id"] for item in loops],
        "loop_records": loops,
        "max_blocked_question_times_selected": max(
            (item["question_times_selected"] for item in blocked),
            default=0,
        ),
        "max_blocked_experiment_times_selected": max(
            (item["experiment_times_selected"] for item in blocked),
            default=0,
        ),
        "source_state_mutated": False,
    }
    result["source_state_mutated"] = before != json.dumps(state, sort_keys=True)
    return result
