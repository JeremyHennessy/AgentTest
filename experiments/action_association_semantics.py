from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

VERSION = "action-association-semantics-v1"
MIN_EXPOSURE_PER_GROUP = 1
MIN_EFFECT_DIFFERENCE = 0.20


def interpret_action_association(candidate: dict[str, Any]) -> dict[str, Any]:
    """Interpret a normalized two-exposure association without causal language.

    The relation claim is directional and observational:
    action-present transitions have a different feature-change rate than
    action-absent transitions. Support means held evidence preserves a
    material non-zero rate difference; contradiction means comparable held
    evidence shrinks that difference below the predeclared material threshold.
    """
    if candidate.get("relation") != "action_associated_with_change":
        raise ValueError("candidate is not an action association")
    if candidate.get("status") == "insufficient_comparison":
        return _insufficient(candidate, "candidate lacks both exposure groups")

    present = _exposure(candidate.get("action_present"), "action_present")
    absent = _exposure(candidate.get("action_absent"), "action_absent")
    if (
        present["evaluable"] < MIN_EXPOSURE_PER_GROUP
        or absent["evaluable"] < MIN_EXPOSURE_PER_GROUP
    ):
        return _insufficient(candidate, "candidate lacks minimum exposure")

    p_present = present["changed"] / present["evaluable"]
    p_absent = absent["changed"] / absent["evaluable"]
    effect = p_present - p_absent
    magnitude = abs(effect)
    direction = (
        "higher_with_action"
        if effect > 0
        else "lower_with_action"
        if effect < 0
        else "no_difference"
    )
    status = (
        "supported_association"
        if magnitude >= MIN_EFFECT_DIFFERENCE
        else "contradicted_association"
    )
    return {
        "version": VERSION,
        "status": status,
        "feature": str(candidate["feature"]),
        "action": str(candidate["action"]),
        "direction": direction,
        "effect_difference": round(effect, 6),
        "effect_magnitude": round(magnitude, 6),
        "material_threshold": MIN_EFFECT_DIFFERENCE,
        "action_present": deepcopy(present),
        "action_absent": deepcopy(absent),
        "evaluable": present["evaluable"] + absent["evaluable"],
        "confirmations": (
            present["evaluable"] + absent["evaluable"]
            if status == "supported_association"
            else 0
        ),
        "refutations": (
            present["evaluable"] + absent["evaluable"]
            if status == "contradicted_association"
            else 0
        ),
        "claim": (
            f"Observed action {candidate['action']} is associated with a "
            f"{direction.replace('_', ' ')} change rate in {candidate['feature']}."
        ),
        "causal": False,
    }


def compare_prefix_to_suffix(
    prefix_candidate: dict[str, Any],
    suffix_candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    prefix = interpret_action_association(prefix_candidate)
    if prefix["status"] == "insufficient_comparison":
        return {
            "version": VERSION,
            "status": "prefix_insufficient",
            "prefix": prefix,
            "suffix": None,
            "same_direction": None,
            "held_out_supports_prefix": None,
        }
    if suffix_candidate is None:
        return {
            "version": VERSION,
            "status": "suffix_not_observed",
            "prefix": prefix,
            "suffix": None,
            "same_direction": None,
            "held_out_supports_prefix": None,
        }
    suffix = interpret_action_association(suffix_candidate)
    if suffix["status"] == "insufficient_comparison":
        return {
            "version": VERSION,
            "status": "suffix_insufficient",
            "prefix": prefix,
            "suffix": suffix,
            "same_direction": None,
            "held_out_supports_prefix": None,
        }

    same_direction = (
        prefix["direction"] == suffix["direction"]
        and prefix["direction"] != "no_difference"
    )
    held_support = (
        suffix["status"] == "supported_association"
        and same_direction
    )
    return {
        "version": VERSION,
        "status": (
            "held_out_supported"
            if held_support
            else "held_out_contradicted"
        ),
        "prefix": prefix,
        "suffix": suffix,
        "same_direction": same_direction,
        "held_out_supports_prefix": held_support,
    }


def public_evidence_payload(
    interpretation: dict[str, Any],
    *,
    observation_refs: list[str],
) -> dict[str, Any]:
    """Map a verified association interpretation to the public evidence schema."""
    if interpretation.get("status") not in {
        "supported_association",
        "contradicted_association",
    }:
        raise ValueError("association interpretation is not public-evidence ready")
    present = interpretation["action_present"]
    absent = interpretation["action_absent"]
    return {
        "version": "native-inquiry-evidence-v1",
        "relation": {
            "kind": "action_associated_with_change",
            "feature": interpretation["feature"],
            "action": interpretation["action"],
            "comparison_status": "comparable",
        },
        "observation_refs": list(observation_refs),
        "evaluable": int(interpretation["evaluable"]),
        "confirmations": int(interpretation["confirmations"]),
        "refutations": int(interpretation["refutations"]),
        "action_present": deepcopy(present),
        "action_absent": deepcopy(absent),
    }


def _insufficient(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": "insufficient_comparison",
        "feature": str(candidate.get("feature") or ""),
        "action": str(candidate.get("action") or ""),
        "reason": reason,
        "causal": False,
    }


def _exposure(value: Any, field: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an exposure table")
    required = {"same", "changed", "evaluable"}
    if set(value) != required:
        raise ValueError(f"{field} fields do not match normalized exposure schema")
    evaluable = int(value["evaluable"])
    changed = int(value["changed"])
    same = int(value["same"])
    if min(evaluable, changed, same) < 0 or changed + same != evaluable:
        raise ValueError(f"{field} counts are inconsistent")
    return {"same": same, "changed": changed, "evaluable": evaluable}
