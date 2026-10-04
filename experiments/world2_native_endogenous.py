from __future__ import annotations

from copy import deepcopy
from typing import Any

from world2_native_consumer import ensure_native_state
from world2_native_opportunity import native_inquiry_opportunities

ENDOGENOUS_VERSION = "world2-native-endogenous-focus-v0"
DRIVE_ORDER = (
    "prediction_error",
    "evidence_hunger",
    "uncertainty",
    "novelty_hunger",
)


def native_drives(state: dict[str, Any]) -> dict[str, float]:
    """Project persisted native evidence into Ora-style bounded drive concepts."""
    native = ensure_native_state(state)
    pending = [item for item in native["predictions"] if item.get("status") == "pending"]
    evidence = native["evidence"]
    recent_refutations = sum(1 for item in evidence[-8:] if item.get("status") == "refuted")
    challenged = sum(
        1
        for item in native["hypotheses"].values()
        if item.get("stance") in {"challenged", "mixed"}
    )
    observed_kinds = {
        item["prediction"]["kind"]
        for item in native["predictions"]
    }
    return {
        "prediction_error": min(1.0, recent_refutations / 2.0),
        "evidence_hunger": min(0.8, len(pending) / 4.0),
        "uncertainty": min(0.8, challenged / 3.0),
        "novelty_hunger": max(0.0, (3 - len(observed_kinds)) / 6.0),
    }


def choose_native_intention(state: dict[str, Any]) -> dict[str, Any]:
    drives = native_drives(state)
    dominant = max(DRIVE_ORDER, key=lambda name: drives[name])
    mapping = {
        "prediction_error": "explain_native_change",
        "evidence_hunger": "resolve_native_prediction",
        "uncertainty": "reduce_native_uncertainty",
        "novelty_hunger": "explore_native_novelty",
    }
    opportunities = native_inquiry_opportunities(state)
    compatible = [
        item for item in opportunities
        if _compatible(dominant, item)
    ]
    selected = compatible[0] if compatible else (opportunities[0] if opportunities else None)
    return {
        "version": ENDOGENOUS_VERSION,
        "kind": mapping[dominant],
        "dominant_drive": dominant,
        "strength": drives[dominant],
        "drives": drives,
        "target": deepcopy(selected),
        "evidence_refs": list((selected or {}).get("evidence_refs", [])),
        "selection_basis": "native_evidence_projected_through_ora_style_drive_order",
    }


def _compatible(drive: str, opportunity: dict[str, Any]) -> bool:
    if drive in {"prediction_error", "uncertainty"}:
        return opportunity["kind"] == "retest_challenged_hypothesis"
    if drive == "evidence_hunger":
        return opportunity["kind"] == "test_pending_prediction"
    return True
