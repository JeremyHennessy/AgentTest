from __future__ import annotations

from typing import Any

from .semantic import actionable_open_questions

DRIVE_ORDER = (
    "prediction_error",
    "specification_pressure",
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
    *,
    strict_question_attention: bool = False,
) -> dict[str, float]:
    metrics = state.get("metrics", {})
    pending = [
        item for item in state.get("experiments", [])
        if item.get("status") == "proposed"
        and item.get("readiness") != "needs_specification"
    ]
    specification_backlog = [
        item for item in state.get("experiments", [])
        if (
            item.get("specification", {}).get("actionability") != "blocked"
            and (
                item.get("status") == "needs_specification"
                or (
                    item.get("status") == "proposed"
                    and item.get("readiness") == "needs_specification"
                )
            )
        )
    ]
    open_questions = (
        actionable_open_questions(state)
        if strict_question_attention
        else [
            item for item in state.get("questions", [])
            if item.get("status") == "open"
        ]
    )

    status = prediction_result.get("status") if prediction_result else None
    violated = status == "violated"
    intervention = status == "invalidated_by_intervention"
    return {
        "prediction_error": (
            1.0
            if violated
            else (0.0 if intervention else (0.6 if surprise else 0.0))
        ),
        "specification_pressure": min(0.9, len(specification_backlog) / 4.0),
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
    specification_backlog = sorted(
        [
            item for item in state.get("experiments", [])
            if (
                item.get("specification", {}).get("actionability") != "blocked"
                and (
                    item.get("status") == "needs_specification"
                    or (
                        item.get("status") == "proposed"
                        and item.get("readiness") == "needs_specification"
                    )
                )
            )
        ],
        key=lambda item: (
            int(item.get("cycle", 0)),
            str(item.get("id", "")),
        ),
    )
    latest_surprise = state.get("surprises", [])[-1] if state.get("surprises") else None

    mapping = {
        "prediction_error": "explain_change",
        "specification_pressure": "specify_experiment",
        "evidence_hunger": "resolve_pending_evidence",
        "uncertainty": "reduce_uncertainty",
        "continuity_repair": "preserve_continuity",
        "calibration_gap": "calibrate_self_model",
        "novelty_hunger": "explore_novelty",
    }
    kind = mapping[dominant]
    target = None
    if dominant == "specification_pressure" and specification_backlog:
        target = specification_backlog[0]["id"]
    elif dominant == "evidence_hunger" and pending:
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
