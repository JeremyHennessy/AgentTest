from __future__ import annotations

import json
from typing import Any

from .native_evidence import validate_native_evidence_payload

NATIVE_OUTCOME_VERSION = "native-inquiry-outcome-v1"


def resolve_native_outcome(
    state: dict[str, Any],
    *,
    experiment_id: str,
    evidence_ref: str,
    cycle: int,
    completed_at: str,
) -> dict[str, Any]:
    experiment = next(
        (
            item
            for item in state.get("experiments", [])
            if str(item.get("id")) == str(experiment_id)
        ),
        None,
    )
    if experiment is None:
        raise KeyError(f"Unknown experiment: {experiment_id}")
    if experiment.get("status") == "completed":
        raise ValueError(f"Experiment already completed: {experiment_id}")
    if experiment.get("readiness") != "awaiting_native_evidence":
        raise ValueError("experiment is not awaiting native evidence")

    metadata = experiment.get("native_inquiry")
    if not isinstance(metadata, dict):
        raise ValueError("experiment is not a native inquiry experiment")
    expected_relation = metadata.get("relation")
    if not isinstance(expected_relation, dict):
        raise ValueError("native inquiry experiment lacks relation metadata")

    episode = next(
        (
            item
            for item in state.get("episodes", [])
            if str(item.get("id")) == str(evidence_ref)
        ),
        None,
    )
    if episode is None:
        raise KeyError(f"Unknown native evidence: {evidence_ref}")
    if episode.get("kind") != "native_inquiry_evidence":
        raise ValueError("evidence reference is not native inquiry evidence")
    if int(episode.get("cycle", -1)) < int(experiment.get("created_cycle", cycle)):
        raise ValueError("native evidence predates the experiment")

    try:
        payload = json.loads(str(episode.get("content") or ""))
    except json.JSONDecodeError as exc:
        raise ValueError("native evidence episode content is invalid") from exc
    evidence = validate_native_evidence_payload(payload)
    if evidence["relation"] != expected_relation:
        raise ValueError("native evidence relation does not match experiment")

    if evidence.get("measurement_kind") != "binary_transition_outcomes":
        raise ValueError(
            "native outcome resolver currently supports temporal binary evidence only"
        )
    measurement = evidence["measurement"]
    evaluable = int(measurement["evaluable"])
    confirmations = int(measurement["confirmations"])
    refutations = int(measurement["refutations"])
    if evaluable <= 0:
        raise ValueError("native outcome evidence must be evaluable")
    if confirmations and refutations:
        raise ValueError("native outcome evidence is mixed; more evidence is required")
    if confirmations == evaluable:
        outcome = "supported"
    elif refutations == evaluable:
        outcome = "falsified"
    else:
        raise ValueError("native outcome evidence does not resolve the inquiry")

    experiment["status"] = "completed"
    experiment["readiness"] = "resolved"
    experiment["outcome"] = outcome
    experiment["evidence_strength"] = 1.0
    experiment["evidence_refs"] = list(
        dict.fromkeys(
            list(experiment.get("evidence_refs") or []) + [str(evidence_ref)]
        )
    )
    experiment["completion_source"] = "native_inquiry_evidence_contract"
    experiment["completed_at"] = completed_at
    experiment.setdefault("status_history", []).append(
        {
            "cycle": int(cycle),
            "from": "proposed",
            "to": "completed",
            "reason": "native_inquiry_evidence_contract_resolved",
            "evidence_refs": [str(evidence_ref)],
            "outcome": outcome,
        }
    )
    return {
        "version": NATIVE_OUTCOME_VERSION,
        "experiment_id": str(experiment_id),
        "evidence_ref": str(evidence_ref),
        "outcome": outcome,
        "evaluable": evaluable,
        "confirmations": confirmations,
        "refutations": refutations,
    }
