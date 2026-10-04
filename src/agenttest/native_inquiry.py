from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from .evidence import known_evidence_ids

NATIVE_INQUIRY_VERSION = "native-inquiry-candidate-v1"
NATIVE_INQUIRY_SOURCE = "native_inquiry"
_ALLOWED_RELATIONS = {
    "same_next_observation",
    "changes_next_observation",
    "action_associated_with_change",
}
_ALLOWED_OBJECTIVES = {
    "information_gain",
    "discrimination",
    "falsifiability",
    "uncertainty_reduction",
    "evidence_balance",
}
_REQUIRED_FIELDS = {
    "version",
    "id",
    "objective",
    "objective_score",
    "relation",
    "question",
    "hypothesis",
    "method",
    "falsification",
    "predicted_observation",
    "evidence_refs",
}
_CAUSAL_WORDS = re.compile(r"\b(cause|causes|caused|causal|causation)\b", re.IGNORECASE)


def validate_native_inquiry_candidate(
    candidate: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Validate a bounded native inquiry against already persisted evidence."""
    if not isinstance(candidate, dict) or set(candidate) != _REQUIRED_FIELDS:
        raise ValueError("native inquiry fields do not match the contract")
    if candidate["version"] != NATIVE_INQUIRY_VERSION:
        raise ValueError("unsupported native inquiry version")

    identifier = candidate["id"]
    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or len(identifier) > 96
        or not re.fullmatch(r"[A-Za-z0-9._:-]+", identifier)
    ):
        raise ValueError("invalid native inquiry candidate ID")

    objective = candidate["objective"]
    if objective not in _ALLOWED_OBJECTIVES:
        raise ValueError("unsupported native inquiry objective")
    objective_score = candidate["objective_score"]
    if not isinstance(objective_score, (int, float)) or isinstance(objective_score, bool):
        raise ValueError("native inquiry objective score must be numeric")
    if not 0.0 <= float(objective_score) <= 1.0:
        raise ValueError("native inquiry objective score must be between 0 and 1")

    relation = _validate_relation(candidate["relation"])
    strings = {}
    for field in (
        "question",
        "hypothesis",
        "method",
        "falsification",
        "predicted_observation",
    ):
        value = candidate[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"native inquiry {field} must be non-empty text")
        if len(value) > 1200:
            raise ValueError(f"native inquiry {field} is too long")
        strings[field] = value.strip()

    if relation["kind"] == "action_associated_with_change":
        combined = " ".join(strings.values())
        if _CAUSAL_WORDS.search(combined):
            raise ValueError(
                "action-association inquiries must not overclaim causation"
            )
        if relation["comparison_status"] != "comparable":
            raise ValueError(
                "action-association inquiry requires comparable action-present "
                "and action-absent evidence"
            )

    evidence_refs = candidate["evidence_refs"]
    if (
        not isinstance(evidence_refs, list)
        or not evidence_refs
        or any(not isinstance(ref, str) or not ref for ref in evidence_refs)
        or len(evidence_refs) != len(set(evidence_refs))
        or len(evidence_refs) > 32
    ):
        raise ValueError("native inquiry requires unique persisted evidence refs")

    known = known_evidence_ids(state)
    unknown = [ref for ref in evidence_refs if ref not in known]
    if unknown:
        raise ValueError(
            "native inquiry references unknown evidence: " + ", ".join(unknown)
        )

    matching_native_refs = []
    episodes_by_id = {
        str(item.get("id")): item
        for item in state.get("episodes", [])
        if item.get("id")
    }
    for ref in evidence_refs:
        episode = episodes_by_id.get(ref)
        if not isinstance(episode, dict) or episode.get("kind") != "native_inquiry_evidence":
            continue
        try:
            payload = json.loads(str(episode.get("content") or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("native inquiry evidence episode is not valid JSON") from exc
        evidence_relation = payload.get("relation") if isinstance(payload, dict) else None
        if evidence_relation != relation:
            raise ValueError(
                "native inquiry relation does not match cited normalized evidence"
            )
        matching_native_refs.append(ref)
    if not matching_native_refs:
        raise ValueError(
            "native inquiry requires at least one matching normalized native evidence ref"
        )

    normalized = deepcopy(candidate)
    normalized["id"] = identifier.strip()
    normalized["objective_score"] = round(float(objective_score), 6)
    normalized["relation"] = relation
    for field, value in strings.items():
        normalized[field] = value
    normalized["evidence_refs"] = list(evidence_refs)
    return normalized


def native_inquiry_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": NATIVE_INQUIRY_VERSION,
        "candidate_id": candidate["id"],
        "objective": candidate["objective"],
        "objective_score": candidate["objective_score"],
        "relation": deepcopy(candidate["relation"]),
        "evidence_refs": list(candidate["evidence_refs"]),
    }


def _validate_relation(value: Any) -> dict[str, Any]:
    required = {
        "kind",
        "feature",
        "action",
        "comparison_status",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("native inquiry relation fields do not match the contract")

    kind = value["kind"]
    if kind not in _ALLOWED_RELATIONS:
        raise ValueError("unsupported native inquiry relation")

    feature = value["feature"]
    if (
        not isinstance(feature, str)
        or not feature.strip()
        or len(feature) > 128
        or not re.fullmatch(r"[A-Za-z0-9._:-]+", feature)
    ):
        raise ValueError("invalid native inquiry feature")

    action = value["action"]
    comparison_status = value["comparison_status"]
    if kind == "action_associated_with_change":
        if (
            not isinstance(action, str)
            or not action.strip()
            or len(action) > 128
            or not re.fullmatch(r"[A-Za-z0-9._:-]+", action)
        ):
            raise ValueError("action association requires a bounded action label")
        if comparison_status not in {"comparable", "insufficient_comparison"}:
            raise ValueError("invalid action comparison status")
    else:
        if action is not None:
            raise ValueError("temporal relation cannot carry an action")
        if comparison_status != "not_applicable":
            raise ValueError("temporal relation comparison status must be not_applicable")

    return {
        "kind": kind,
        "feature": feature.strip(),
        "action": action.strip() if isinstance(action, str) else None,
        "comparison_status": comparison_status,
    }
