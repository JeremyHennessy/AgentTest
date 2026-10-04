from __future__ import annotations

from copy import deepcopy
from typing import Any

NATIVE_EVIDENCE_VERSION = "native-inquiry-evidence-v1"
NATIVE_EVIDENCE_V2_VERSION = "native-inquiry-evidence-v2"
_ALLOWED_RELATIONS = {
    "same_next_observation",
    "changes_next_observation",
    "action_associated_with_change",
}
_REQUIRED = {
    "version",
    "relation",
    "observation_refs",
    "evaluable",
    "confirmations",
    "refutations",
    "action_present",
    "action_absent",
}


def validate_native_evidence_payload(evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("native evidence must be an object")
    version = evidence.get("version")
    if version == NATIVE_EVIDENCE_VERSION:
        return validate_native_evidence(evidence)
    if version == NATIVE_EVIDENCE_V2_VERSION:
        return validate_native_evidence_v2(evidence)
    raise ValueError("unsupported native evidence version")


def validate_native_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict) or set(evidence) != _REQUIRED:
        raise ValueError("native evidence fields do not match the contract")
    if evidence["version"] != NATIVE_EVIDENCE_VERSION:
        raise ValueError("unsupported native evidence version")

    relation = _validate_relation(evidence["relation"])
    refs = evidence["observation_refs"]
    if (
        not isinstance(refs, list)
        or not refs
        or any(not isinstance(ref, str) or not ref for ref in refs)
        or len(refs) != len(set(refs))
        or len(refs) > 64
    ):
        raise ValueError("native evidence requires unique observation references")

    evaluable = _count(evidence["evaluable"], "evaluable")
    confirmations = _count(evidence["confirmations"], "confirmations")
    refutations = _count(evidence["refutations"], "refutations")
    if confirmations + refutations != evaluable:
        raise ValueError("native evidence counts must partition evaluable observations")

    present = evidence["action_present"]
    absent = evidence["action_absent"]
    if relation["kind"] == "action_associated_with_change":
        present = _exposure(present, "action_present")
        absent = _exposure(absent, "action_absent")
        if not present["evaluable"] or not absent["evaluable"]:
            raise ValueError(
                "action association requires both action-present and action-absent exposure"
            )
        if present["evaluable"] + absent["evaluable"] != evaluable:
            raise ValueError("action exposure groups must partition evaluable observations")
    else:
        if present is not None or absent is not None:
            raise ValueError("temporal native evidence cannot carry action exposures")
        present = None
        absent = None

    return {
        "version": NATIVE_EVIDENCE_VERSION,
        "relation": relation,
        "observation_refs": list(refs),
        "evaluable": evaluable,
        "confirmations": confirmations,
        "refutations": refutations,
        "action_present": deepcopy(present),
        "action_absent": deepcopy(absent),
    }



def validate_native_evidence_v2(evidence: dict[str, Any]) -> dict[str, Any]:
    required = {
        "version",
        "relation",
        "observation_refs",
        "measurement_kind",
        "measurement",
    }
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise ValueError("native evidence v2 fields do not match the contract")
    if evidence["version"] != NATIVE_EVIDENCE_V2_VERSION:
        raise ValueError("unsupported native evidence v2 version")

    relation = _validate_relation(evidence["relation"])
    refs = _refs(evidence["observation_refs"])
    measurement_kind = evidence["measurement_kind"]
    measurement = evidence["measurement"]

    if measurement_kind == "binary_transition_outcomes":
        if relation["kind"] not in {"same_next_observation", "changes_next_observation"}:
            raise ValueError("binary transition evidence requires a temporal relation")
        if not isinstance(measurement, dict) or set(measurement) != {
            "evaluable", "confirmations", "refutations"
        }:
            raise ValueError("binary transition measurement fields do not match contract")
        evaluable = _count(measurement["evaluable"], "measurement.evaluable")
        confirmations = _count(
            measurement["confirmations"], "measurement.confirmations"
        )
        refutations = _count(
            measurement["refutations"], "measurement.refutations"
        )
        if confirmations + refutations != evaluable:
            raise ValueError(
                "binary transition outcomes must partition evaluable observations"
            )
        normalized_measurement = {
            "evaluable": evaluable,
            "confirmations": confirmations,
            "refutations": refutations,
        }
    elif measurement_kind == "comparative_action_exposure":
        if relation["kind"] != "action_associated_with_change":
            raise ValueError(
                "comparative action evidence requires action association relation"
            )
        if not isinstance(measurement, dict) or set(measurement) != {
            "action_present",
            "action_absent",
            "observed_change_rate_action_present",
            "observed_change_rate_action_absent",
            "observed_change_rate_difference",
        }:
            raise ValueError("comparative action measurement fields do not match contract")
        present = _exposure(measurement["action_present"], "measurement.action_present")
        absent = _exposure(measurement["action_absent"], "measurement.action_absent")
        if not present["evaluable"] or not absent["evaluable"]:
            raise ValueError("comparative action evidence requires both exposure groups")
        present_rate = present["changed"] / present["evaluable"]
        absent_rate = absent["changed"] / absent["evaluable"]
        expected = {
            "action_present": present,
            "action_absent": absent,
            "observed_change_rate_action_present": round(present_rate, 6),
            "observed_change_rate_action_absent": round(absent_rate, 6),
            "observed_change_rate_difference": round(present_rate - absent_rate, 6),
        }
        for key in (
            "observed_change_rate_action_present",
            "observed_change_rate_action_absent",
            "observed_change_rate_difference",
        ):
            value = measurement[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            if round(float(value), 6) != expected[key]:
                raise ValueError(f"{key} does not match exposure counts")
        normalized_measurement = expected
    else:
        raise ValueError("unsupported native evidence v2 measurement kind")

    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": relation,
        "observation_refs": refs,
        "measurement_kind": measurement_kind,
        "measurement": normalized_measurement,
    }

def _validate_relation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "kind", "feature", "action", "comparison_status"
    }:
        raise ValueError("native evidence relation fields do not match the contract")
    kind = value["kind"]
    if kind not in _ALLOWED_RELATIONS:
        raise ValueError("unsupported native evidence relation")
    feature = value["feature"]
    if not isinstance(feature, str) or not feature.strip():
        raise ValueError("native evidence feature is required")
    action = value["action"]
    comparison = value["comparison_status"]
    if kind == "action_associated_with_change":
        if not isinstance(action, str) or not action.strip():
            raise ValueError("action association requires action label")
        if comparison != "comparable":
            raise ValueError("action association evidence must be comparable")
    else:
        if action is not None or comparison != "not_applicable":
            raise ValueError("temporal evidence relation metadata is invalid")
    return {
        "kind": kind,
        "feature": feature.strip(),
        "action": action.strip() if isinstance(action, str) else None,
        "comparison_status": comparison,
    }



def _refs(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(ref, str) or not ref for ref in value)
        or len(value) != len(set(value))
        or len(value) > 64
    ):
        raise ValueError("native evidence requires unique observation references")
    return list(value)

def _count(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _exposure(value: Any, field: str) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"evaluable", "changed", "same"}:
        raise ValueError(f"{field} fields do not match the contract")
    evaluable = _count(value["evaluable"], f"{field}.evaluable")
    changed = _count(value["changed"], f"{field}.changed")
    same = _count(value["same"], f"{field}.same")
    if changed + same != evaluable:
        raise ValueError(f"{field} counts must partition evaluable observations")
    return {"evaluable": evaluable, "changed": changed, "same": same}
