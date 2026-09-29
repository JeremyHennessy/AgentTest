from __future__ import annotations

from typing import Any

DRIVE_ORDER = (
    "prediction_error",
    "evidence_hunger",
    "uncertainty",
    "continuity_repair",
    "calibration_gap",
    "novelty_hunger",
)


def compute_drives(
    state: dict[str, Any],
    surprise: dict[str, Any] | None = None,
    prediction_result: dict[str, Any] | None = None,
) -> dict[str, float]:
    metrics = state.get("metrics", {})
    pending = [
        item for item in state.get("experiments", [])
        if item.get("status") == "proposed"
        and item.get("readiness") != "needs_specification"
    ]
    open_questions = [
        item for item in state.get("questions", [])
        if item.get("status") == "open"
    ]

    status = prediction_result.get("status") if prediction_result else None
    violated = status == "violated"
    intervention = status == "invalidated_by_intervention"
    return {
        "prediction_error": (
            1.0
            if violated
            else (0.0 if intervention else (0.6 if surprise else 0.0))
        ),
        "evidence_hunger": min(0.8, len(pending) / 4.0),
        "uncertainty": min(0.8, len(open_questions) / 6.0),
        "continuity_repair": max(0.0, 1.0 - metrics.get("continuity", 0.0)),
        "calibration_gap": max(0.0, 1.0 - metrics.get("self_model", 0.0)),
        "novelty_hunger": max(0.0, 0.5 - metrics.get("open_endedness", 0.0)),
    }


def choose_intention(
    state: dict[str, Any],
    drives: dict[str, float],
) -> dict[str, Any]:
    dominant = max(DRIVE_ORDER, key=lambda name: drives.get(name, 0.0))
    strength = drives.get(dominant, 0.0)

    pending = [
        item for item in state.get("experiments", [])
        if item.get("status") == "proposed"
        and item.get("readiness") != "needs_specification"
    ]
    latest_surprise = state.get("surprises", [])[-1] if state.get("surprises") else None

    mapping = {
        "prediction_error": "explain_change",
        "evidence_hunger": "resolve_pending_evidence",
        "uncertainty": "reduce_uncertainty",
        "continuity_repair": "preserve_continuity",
        "calibration_gap": "calibrate_self_model",
        "novelty_hunger": "explore_novelty",
    }
    kind = mapping[dominant]
    target = None
    if dominant == "evidence_hunger" and pending:
        target = pending[0]["id"]
    elif dominant == "prediction_error" and latest_surprise:
        target = latest_surprise["id"]

    return {
        "id": f"I{len(state.get('intentions', [])) + 1:06d}",
        "cycle": state["cycles"],
        "kind": kind,
        "dominant_drive": dominant,
        "strength": strength,
        "target": target,
        "rationale": (
            f"{dominant} had the highest current pressure ({strength:.3f}); "
            "ties use a fixed order so the choice is reproducible."
        ),
    }
