from __future__ import annotations

from math import log2
from typing import Any

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION

FEATURE = "halifax_stanfield_wind_speed_kmh"
THRESHOLD_KMH = 5.0


def transition(left: float, right: float) -> str:
    return (
        "same_next_observation"
        if abs(right - left) <= THRESHOLD_KMH
        else "changes_next_observation"
    )


def evidence_from_observations(
    observations: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, float]:
    values = [
        (str(item["observation_id"]), float(item["wind_speed_kmh"]))
        for item in observations
        if isinstance(item.get("wind_speed_kmh"), (int, float))
    ]
    if len(values) < 4:
        raise ValueError("at least four wind observations are required")

    relations = [
        transition(left[1], right[1])
        for left, right in zip(values, values[1:])
    ]
    same = relations.count("same_next_observation")
    changed = relations.count("changes_next_observation")
    selected = (
        "same_next_observation"
        if same > changed
        else "changes_next_observation"
    )
    confirmations = relations.count(selected)
    refutations = len(relations) - confirmations
    p = confirmations / len(relations)
    entropy = 0.0 if p in (0.0, 1.0) else -(p * log2(p) + (1 - p) * log2(1 - p))

    payload = {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": selected,
            "feature": FEATURE,
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": [item[0] for item in values],
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": len(relations),
            "confirmations": confirmations,
            "refutations": refutations,
        },
    }
    return payload, selected, round(entropy, 6)


def stage_isolated_inquiry(
    core: AgentCore,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence, selected, uncertainty = evidence_from_observations(observations)
    recorded = core.record_native_evidence(evidence, enabled=True, persist=True)
    stable = selected == "same_next_observation"
    inquiry = {
        "version": NATIVE_INQUIRY_VERSION,
        "id": "NIC:halifax-weather:wind-speed",
        "objective": "information_gain",
        "objective_score": uncertainty,
        "relation": evidence["relation"],
        "question": (
            "Will Halifax Stanfield observed wind speed remain within 5 km/h "
            "of the prior hourly observation?"
            if stable
            else
            "Will Halifax Stanfield observed wind speed change by more than "
            "5 km/h on the next hourly observation?"
        ),
        "hypothesis": (
            "Hourly Halifax Stanfield wind speed usually remains within 5 km/h "
            "of the preceding observed value."
            if stable
            else
            "Hourly Halifax Stanfield wind speed usually changes by more than "
            "5 km/h from the preceding observed value."
        ),
        "method": (
            "Wait for the next legitimate Environment Canada hourly observation "
            "from the same pinned station and compare observed wind speed."
        ),
        "falsification": (
            "A next hourly wind observation on the opposite side of the fixed "
            "5 km/h transition threshold counts against this hypothesis."
        ),
        "predicted_observation": (
            "The next pinned-station hourly wind observation "
            + ("remains within" if stable else "moves beyond")
            + " 5 km/h of the preceding value."
        ),
        "evidence_refs": [recorded["evidence_ref"]],
    }
    proposed = core.propose_native_inquiry(inquiry, enabled=True, persist=True)
    return {
        "selected_relation": selected,
        "uncertainty": uncertainty,
        "evidence_result": recorded,
        "inquiry_result": proposed,
    }
