from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

DIAGNOSTIC_VERSION = "experiment-design-v3"
PREDICTION_CONTRACT_KIND = "prediction_status"
SPECIFICATION_READINESS = {
    "awaiting_specification_or_evidence",
    "needs_specification",
}


def _normalized(text: object) -> str:
    return " ".join(str(text or "").lower().split())


def _valid_prediction_contract(experiment: dict[str, Any]) -> bool:
    contract = experiment.get("evidence_contract")
    if not isinstance(contract, dict):
        return False
    return (
        contract.get("kind") == PREDICTION_CONTRACT_KIND
        and isinstance(contract.get("prediction_id"), str)
        and bool(contract.get("prediction_id"))
        and contract.get("expected_status") in {"confirmed", "violated"}
    )


def _is_specification_backlog(experiment: dict[str, Any]) -> bool:
    if experiment.get("status") == "needs_specification":
        return True
    return (
        experiment.get("status") == "proposed"
        and not _valid_prediction_contract(experiment)
        and str(experiment.get("readiness") or "unspecified")
        in {*SPECIFICATION_READINESS, "unspecified"}
    )


def evaluate_experiment_design(state: dict[str, Any]) -> dict[str, Any]:
    """Read-only diagnostic separating executable work from specification backlog."""

    before = json.dumps(state, sort_keys=True)
    experiments = state.get("experiments", [])
    active = [
        experiment
        for experiment in experiments
        if experiment.get("status") == "proposed"
    ]
    backlog = [
        experiment
        for experiment in experiments
        if _is_specification_backlog(experiment)
    ]
    unresolved = [
        experiment
        for experiment in experiments
        if experiment.get("status") in {"proposed", "needs_specification"}
    ]
    questions = {
        str(question.get("id")): question
        for question in state.get("questions", [])
        if question.get("id")
    }

    question_groups: dict[str, list[str]] = defaultdict(list)
    active_question_groups: dict[str, list[str]] = defaultdict(list)
    method_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    readiness = Counter()
    contracted: list[str] = []
    uncontracted: list[str] = []

    for experiment in unresolved:
        experiment_id = str(experiment.get("id", ""))
        question_id = str(experiment.get("question_id") or "unlinked")
        question_groups[question_id].append(experiment_id)
        method_groups[(question_id, _normalized(experiment.get("method")))].append(
            experiment_id
        )

        readiness_value = str(experiment.get("readiness") or "unspecified")
        readiness[readiness_value] += 1
        if _valid_prediction_contract(experiment):
            contracted.append(experiment_id)
        else:
            uncontracted.append(experiment_id)

    for experiment in active:
        question_id = str(experiment.get("question_id") or "unlinked")
        active_question_groups[question_id].append(str(experiment.get("id", "")))

    duplicate_clusters = []
    for (question_id, method), experiment_ids in sorted(method_groups.items()):
        if len(experiment_ids) < 2:
            continue
        contracted_ids = [
            experiment_id
            for experiment_id in experiment_ids
            if experiment_id in contracted
        ]
        question = questions.get(question_id, {})
        duplicate_clusters.append(
            {
                "question_id": question_id,
                "question_text": question.get("text"),
                "question_times_selected": question.get("times_selected", 0),
                "normalized_method": method,
                "experiment_ids": experiment_ids,
                "size": len(experiment_ids),
                "contracted_ids": contracted_ids,
            }
        )

    largest_duplicate = max(
        (cluster["size"] for cluster in duplicate_clusters),
        default=0,
    )
    largest_question_group = max(
        (len(experiment_ids) for experiment_ids in question_groups.values()),
        default=0,
    )
    active_count = len(active)
    unresolved_count = len(unresolved)
    contracted_count = len(contracted)
    backlog_ids = [str(item.get("id", "")) for item in backlog]
    blocked_backlog_ids = [
        str(item.get("id", ""))
        for item in backlog
        if item.get("specification", {}).get("actionability") == "blocked"
    ]
    actionable_backlog_ids = [
        str(item.get("id", ""))
        for item in backlog
        if item.get("specification", {}).get("actionability") == "actionable"
    ]
    triaged_ids = set(blocked_backlog_ids) | set(actionable_backlog_ids)
    untriaged_backlog_ids = [
        identifier
        for identifier in backlog_ids
        if identifier not in triaged_ids
    ]

    if any(
        cluster["size"] >= 2 and not cluster["contracted_ids"]
        for cluster in duplicate_clusters
    ):
        outcome = "specification_churn"
    elif untriaged_backlog_ids or actionable_backlog_ids:
        outcome = "specification_backlog"
    elif blocked_backlog_ids:
        outcome = "blocked_specification_backlog"
    elif active_count == 0:
        outcome = "no_active_experiments"
    else:
        outcome = "evidence_ready"

    result = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "outcome": outcome,
        "active_experiment_count": active_count,
        "executable_experiment_count": sum(
            1 for item in active if _valid_prediction_contract(item)
        ),
        "specification_backlog_count": len(backlog_ids),
        "blocked_specification_count": len(blocked_backlog_ids),
        "actionable_specification_count": len(actionable_backlog_ids),
        "untriaged_specification_count": len(untriaged_backlog_ids),
        "unresolved_experiment_count": unresolved_count,
        "active_question_count": len(active_question_groups),
        "unresolved_question_count": len(question_groups),
        "contracted_count": contracted_count,
        "uncontracted_count": len(uncontracted),
        "contracted_ratio": (
            1.0 if unresolved_count == 0 else contracted_count / unresolved_count
        ),
        "readiness_counts": dict(sorted(readiness.items())),
        "largest_question_group": largest_question_group,
        "largest_duplicate_cluster": largest_duplicate,
        "duplicate_cluster_count": len(duplicate_clusters),
        "duplicate_clusters": duplicate_clusters,
        "active_question_groups": {
            question_id: experiment_ids
            for question_id, experiment_ids in sorted(active_question_groups.items())
        },
        "unresolved_question_groups": {
            question_id: experiment_ids
            for question_id, experiment_ids in sorted(question_groups.items())
        },
        "contracted_experiment_ids": contracted,
        "uncontracted_experiment_ids": uncontracted,
        "specification_backlog_ids": backlog_ids,
        "blocked_specification_ids": blocked_backlog_ids,
        "actionable_specification_ids": actionable_backlog_ids,
        "untriaged_specification_ids": untriaged_backlog_ids,
        "source_state_mutated": False,
    }

    result["source_state_mutated"] = before != json.dumps(state, sort_keys=True)
    return result
