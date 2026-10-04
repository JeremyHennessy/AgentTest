from __future__ import annotations

from copy import deepcopy
from typing import Any

NATIVE_EVIDENCE_VERSION = "native-inquiry-evidence-v1"
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
