from __future__ import annotations

from copy import deepcopy
from typing import Any

from world2_native_consumer import NATIVE_STATE_KEY, ensure_native_state

OPPORTUNITY_VERSION = "world2-native-opportunity-v0"


def native_inquiry_opportunities(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Rank inquiry opportunities from persisted native uncertainty/evidence only."""
    native = ensure_native_state(state)
    opportunities: list[dict[str, Any]] = []

    for item in native["predictions"]:
        if item.get("status") != "pending":
            continue
        pred = item["prediction"]
        kind = pred["kind"]
        hypothesis = native["hypotheses"].get(_key(pred))
        tension = _tension(hypothesis)
        specificity = 0.15 if pred.get("target_position") is not None else 0.05
        opportunities.append(
            {
                "version": OPPORTUNITY_VERSION,
                "kind": "test_pending_prediction",
                "prediction_id": pred["prediction_id"],
                "prediction_kind": kind,
                "target_position": deepcopy(pred.get("target_position")),
                "object_id": pred.get("object_id"),
                "evidence_refs": list((hypothesis or {}).get("evidence_refs", []))[-8:],
                "score": round(0.45 + tension + specificity, 6),
                "reason": (
                    "A persisted native prediction remains directly testable; "
                    "prior conflicting evidence increases its inquiry value."
                ),
            }
        )

    for key, record in native["hypotheses"].items():
        if record.get("stance") not in {"challenged", "mixed"}:
            continue
        opportunities.append(
            {
                "version": OPPORTUNITY_VERSION,
                "kind": "retest_challenged_hypothesis",
                "prediction_id": None,
                "prediction_kind": record["kind"],
                "target_position": deepcopy(record.get("target_position")),
                "object_id": record.get("object_id"),
                "evidence_refs": list(record.get("evidence_refs", []))[-8:],
                "score": round(0.8 + _tension(record), 6),
                "reason": "Observed evidence challenged or split a persisted native hypothesis.",
                "hypothesis_key": key,
            }
        )

    opportunities.sort(
        key=lambda item: (
            -float(item["score"]),
            item["kind"],
            str(item.get("prediction_id") or ""),
            str(item.get("hypothesis_key") or ""),
        )
    )
    return opportunities


def select_native_inquiry(state: dict[str, Any]) -> dict[str, Any] | None:
    """Select one inquiry target without selecting or executing a world action."""
    opportunities = native_inquiry_opportunities(state)
    if not opportunities:
        return None
    selected = deepcopy(opportunities[0])
    selected["selection_basis"] = "persisted_native_uncertainty_and_evidence"
    return selected


def _tension(record: dict[str, Any] | None) -> float:
    if not record:
        return 0.0
    confirmed = int(record.get("confirmed", 0) or 0)
    refuted = int(record.get("refuted", 0) or 0)
    total = confirmed + refuted
    if total == 0:
        return 0.0
    minority = min(confirmed, refuted)
    contradiction = minority / total
    challenged = 0.25 if refuted > confirmed else 0.0
    return min(0.45, round(contradiction * 0.4 + challenged, 6))


def _key(prediction: dict[str, Any]) -> str:
    return "|".join(
        [
            prediction["kind"],
            repr(prediction.get("target_position")),
            str(prediction.get("object_id")),
        ]
    )
