from __future__ import annotations

from copy import deepcopy
from typing import Any

VERSION = "native-inquiry-evidence-v2"


def temporal_evidence_v2(
    *,
    relation: dict[str, Any],
    observation_refs: list[str],
    evaluable: int,
    confirmations: int,
    refutations: int,
) -> dict[str, Any]:
    if relation.get("kind") not in {
        "same_next_observation",
        "changes_next_observation",
    }:
        raise ValueError("temporal v2 evidence requires a temporal relation")
    if confirmations + refutations != evaluable:
        raise ValueError("temporal outcomes must partition evaluable transitions")
    return {
        "version": VERSION,
        "relation": deepcopy(relation),
        "observation_refs": _refs(observation_refs),
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": _count(evaluable),
            "confirmations": _count(confirmations),
            "refutations": _count(refutations),
        },
    }


def action_association_evidence_v2(
    *,
    relation: dict[str, Any],
    observation_refs: list[str],
    action_present: dict[str, int],
    action_absent: dict[str, int],
) -> dict[str, Any]:
    """Represent comparative exposure evidence without inventing trial-level truth labels."""
    if relation.get("kind") != "action_associated_with_change":
        raise ValueError("association v2 evidence requires action association relation")
    if relation.get("comparison_status") != "comparable":
        raise ValueError("action association must be comparable")
    present = _exposure(action_present, "action_present")
    absent = _exposure(action_absent, "action_absent")
    if not present["evaluable"] or not absent["evaluable"]:
        raise ValueError("both exposure groups are required")
    present_rate = present["changed"] / present["evaluable"]
    absent_rate = absent["changed"] / absent["evaluable"]
    return {
        "version": VERSION,
        "relation": deepcopy(relation),
        "observation_refs": _refs(observation_refs),
        "measurement_kind": "comparative_action_exposure",
        "measurement": {
            "action_present": present,
            "action_absent": absent,
            "observed_change_rate_action_present": round(present_rate, 6),
            "observed_change_rate_action_absent": round(absent_rate, 6),
            "observed_change_rate_difference": round(present_rate - absent_rate, 6),
        },
    }


def validate_evidence_v2(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version",
        "relation",
        "observation_refs",
        "measurement_kind",
        "measurement",
    }:
        raise ValueError("native evidence v2 fields do not match contract")
    if value["version"] != VERSION:
        raise ValueError("unsupported native evidence v2 version")
    kind = value["measurement_kind"]
    relation = value["relation"]
    refs = _refs(value["observation_refs"])
    measurement = value["measurement"]
    if kind == "binary_transition_outcomes":
        result = temporal_evidence_v2(
            relation=relation,
            observation_refs=refs,
            evaluable=measurement.get("evaluable"),
            confirmations=measurement.get("confirmations"),
            refutations=measurement.get("refutations"),
        )
    elif kind == "comparative_action_exposure":
        result = action_association_evidence_v2(
            relation=relation,
            observation_refs=refs,
            action_present=measurement.get("action_present"),
            action_absent=measurement.get("action_absent"),
        )
    else:
        raise ValueError("unsupported native evidence v2 measurement kind")
    if result != value:
        raise ValueError("native evidence v2 contains inconsistent derived fields")
    return result


def _refs(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(ref, str) or not ref for ref in value)
        or len(value) != len(set(value))
    ):
        raise ValueError("observation refs must be unique non-empty strings")
    return list(value)


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("evidence count must be a non-negative integer")
    return value


def _exposure(value: Any, field: str) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"evaluable", "changed", "same"}:
        raise ValueError(f"{field} fields do not match contract")
    evaluable = _count(value["evaluable"])
    changed = _count(value["changed"])
    same = _count(value["same"])
    if changed + same != evaluable:
        raise ValueError(f"{field} outcomes must partition evaluable exposure")
    return {"evaluable": evaluable, "changed": changed, "same": same}
