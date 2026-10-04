from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from normalized_inquiry_objectives import OBJECTIVES, rank_normalized_candidates
from normalized_relation_evidence import normalized_evidence, normalized_relation_candidates

BENCHMARK_VERSION = "prospective-inquiry-benchmark-v1"


def benchmark_trajectory(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Select from prefix evidence only, then evaluate the frozen inquiry on held-out suffix."""
    if len(samples) < 4:
        raise ValueError("prospective benchmark requires at least four observations")
    split = max(2, len(samples) // 2)
    if split >= len(samples):
        split = len(samples) - 1

    prefix = samples[:split]
    # Keep the final prefix observation only as the boundary condition. All scored
    # transitions after it include at least one observation unseen at selection time.
    suffix_window = samples[split - 1 :]

    prefix_candidates = normalized_relation_candidates(normalized_evidence(prefix))
    suffix_candidates = normalized_relation_candidates(normalized_evidence(suffix_window))

    results: dict[str, Any] = {}
    for objective in OBJECTIVES:
        ranked = rank_normalized_candidates(prefix_candidates, objective)
        eligible = [item for item in ranked if item["eligible"]]
        if not eligible:
            results[objective] = {
                "status": "no_prefix_candidate",
                "selected": None,
                "held_out": None,
            }
            continue
        selected = eligible[0]
        held_out = _evaluate_selected(
            selected["candidate"], suffix_candidates, suffix_window
        )
        results[objective] = {
            "status": "selected",
            "selected": {
                "candidate": deepcopy(selected["candidate"]),
                "prefix_score": selected["score"],
                "prefix_detail": deepcopy(selected["detail"]),
            },
            "held_out": held_out,
        }

    return {
        "version": BENCHMARK_VERSION,
        "sample_count": len(samples),
        "prefix_sample_count": len(prefix),
        "held_out_new_sample_count": len(samples) - split,
        "prefix_last_observation_id": prefix[-1].get("observation_id"),
        "first_unseen_observation_id": samples[split].get("observation_id"),
        "results": results,
    }


def _evaluate_selected(
    selected: dict[str, Any],
    suffix_candidates: list[dict[str, Any]],
    suffix_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    match = next(
        (
            item
            for item in suffix_candidates
            if item["relation"] == selected["relation"]
            and item["feature"] == selected["feature"]
            and item.get("action") == selected.get("action")
        ),
        None,
    )
    if selected["relation"] == "action_associated_with_change":
        return _evaluate_action_association(
            selected,
            suffix_observations,
        )

    if match is None:
        return {
            "status": "feature_not_observed",
            "evaluable": False,
            "evidence_count": 0,
            "posterior_entropy_reduction": None,
        }
    return _evaluate_transition(selected, match)


def _evaluate_transition(prefix: dict[str, Any], suffix: dict[str, Any]) -> dict[str, Any]:
    n0 = int(prefix.get("evaluable", 0) or 0)
    c0 = int(prefix.get("confirmations", 0) or 0)
    r0 = int(prefix.get("refutations", 0) or 0)
    n1 = int(suffix.get("evaluable", 0) or 0)
    c1 = int(suffix.get("confirmations", 0) or 0)
    r1 = int(suffix.get("refutations", 0) or 0)
    before = _beta_binary_entropy(c0 + 1.0, r0 + 1.0)
    after = _beta_binary_entropy(c0 + c1 + 1.0, r0 + r1 + 1.0)
    return {
        "status": "evaluable" if n1 else "no_held_out_transition",
        "evaluable": bool(n1),
        "evidence_count": n1,
        "confirmations": c1,
        "refutations": r1,
        "realized_refutation": r1 > 0,
        "realized_confirmation": c1 > 0,
        "both_outcomes_observed": c1 > 0 and r1 > 0,
        "posterior_entropy_before": round(before, 6),
        "posterior_entropy_after": round(after, 6),
        "posterior_entropy_reduction": round(before - after, 6),
    }


def _evaluate_action_association(
    prefix: dict[str, Any],
    suffix_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    p1 = prefix["action_present"]
    p0 = prefix["action_absent"]
    s1 = {"same": 0, "changed": 0, "evaluable": 0}
    s0 = {"same": 0, "changed": 0, "evaluable": 0}
    feature = prefix["feature"]
    selected_action = prefix["action"]

    for left, right in zip(suffix_observations, suffix_observations[1:]):
        before_value = _feature_value(left, feature)
        after_value = _feature_value(right, feature)
        if before_value is _MISSING or after_value is _MISSING:
            continue
        receipt = right.get("action_receipt") or {}
        bucket = s1 if receipt.get("action") == selected_action else s0
        changed = before_value != after_value
        bucket["changed" if changed else "same"] += 1
        bucket["evaluable"] += 1

    held_count = int(s1["evaluable"]) + int(s0["evaluable"])
    before = 0.5 * (
        _beta_binary_entropy(p1["changed"] + 1.0, p1["same"] + 1.0)
        + _beta_binary_entropy(p0["changed"] + 1.0, p0["same"] + 1.0)
    )
    after = 0.5 * (
        _beta_binary_entropy(
            p1["changed"] + s1["changed"] + 1.0,
            p1["same"] + s1["same"] + 1.0,
        )
        + _beta_binary_entropy(
            p0["changed"] + s0["changed"] + 1.0,
            p0["same"] + s0["same"] + 1.0,
        )
    )
    both_exposures = bool(s1["evaluable"] and s0["evaluable"])
    effect = None
    if both_exposures:
        effect = round(
            s1["changed"] / s1["evaluable"] - s0["changed"] / s0["evaluable"],
            6,
        )
    return {
        "status": (
            "comparable_held_out"
            if both_exposures
            else "partial_exposure"
            if held_count
            else "no_held_out_transition"
        ),
        "evaluable": bool(held_count),
        "evidence_count": held_count,
        "action_present_evidence": int(s1["evaluable"]),
        "action_absent_evidence": int(s0["evaluable"]),
        "both_exposures_observed": both_exposures,
        "held_out_effect_difference": effect,
        "posterior_entropy_before": round(before, 6),
        "posterior_entropy_after": round(after, 6),
        "posterior_entropy_reduction": round(before - after, 6),
    }


_MISSING = object()


def _feature_value(observation: dict[str, Any], feature: str) -> Any:
    if feature == "visible_object_ids":
        return tuple(observation.get(feature, []))
    reading = observation.get(feature)
    if isinstance(reading, dict) and reading.get("status") == "measured":
        return reading.get("value")
    return _MISSING


def _beta_binary_entropy(alpha: float, beta: float) -> float:
    p = alpha / (alpha + beta)
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))
