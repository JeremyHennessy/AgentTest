from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

DIAGNOSTIC_VERSION = "experiment-design-v1"
PREDICTION_CONTRACT_KIND = "prediction_status"


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


def evaluate_experiment_design(state: dict[str, Any]) -> dict[str, Any]:
    """Read-only diagnostic for active experiment specification quality."""

    before = json.dumps(state, sort_keys=True)
    active = [
        experiment
        for experiment in state.get("experiments", [])
        if experiment.get("status") == "proposed"
    ]
    questions = {
        str(question.get("id")): question
        for question in state.get("questions", [])
        if question.get("id")
    }

    question_groups: dict[str, list[str]] = defaultdict(list)
    method_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    readiness = Counter()
    contracted: list[str] = []
    uncontracted: list[str] = []

    for experiment in active:
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
    contracted_count = len(contracted)

    if active_count == 0:
        outcome = "no_active_experiments"
    elif any(
        cluster["size"] >= 2 and not cluster["contracted_ids"]
        for cluster in duplicate_clusters
    ):
        outcome = "specification_churn"
    elif uncontracted:
        outcome = "specification_backlog"
    else:
        outcome = "evidence_ready"

    result = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "outcome": outcome,
        "active_experiment_count": active_count,
        "active_question_count": len(question_groups),
        "contracted_count": contracted_count,
        "uncontracted_count": len(uncontracted),
        "contracted_ratio": (
            1.0 if active_count == 0 else contracted_count / active_count
        ),
        "readiness_counts": dict(sorted(readiness.items())),
        "largest_question_group": largest_question_group,
        "largest_duplicate_cluster": largest_duplicate,
        "duplicate_cluster_count": len(duplicate_clusters),
        "duplicate_clusters": duplicate_clusters,
        "active_question_groups": {
            question_id: experiment_ids
            for question_id, experiment_ids in sorted(question_groups.items())
        },
        "contracted_experiment_ids": contracted,
        "uncontracted_experiment_ids": uncontracted,
        "source_state_mutated": False,
    }

    result["source_state_mutated"] = before != json.dumps(state, sort_keys=True)
    return result
