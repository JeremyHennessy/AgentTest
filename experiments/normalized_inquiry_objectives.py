from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

VERSION = "normalized-inquiry-objectives-v1"
OBJECTIVES = (
    "information_gain",
    "discrimination",
    "falsifiability",
    "uncertainty_reduction",
    "evidence_balance",
)


def rank_normalized_candidates(
    candidates: list[dict[str, Any]], objective: str
) -> list[dict[str, Any]]:
    if objective not in OBJECTIVES:
        raise ValueError("unknown normalized inquiry objective")
    ranked = []
    for candidate in candidates:
        score, eligible, detail = _score(candidate, objective)
        ranked.append({
            "candidate": deepcopy(candidate),
            "objective": objective,
            "eligible": eligible,
            "score": round(score, 6) if score is not None else None,
            "detail": detail,
        })
    return sorted(
        ranked,
        key=lambda item: (
            0 if item["eligible"] else 1,
            -(item["score"] if item["score"] is not None else -1.0),
            item["candidate"]["id"],
        ),
    )


def _score(candidate: dict[str, Any], objective: str):
    relation = candidate["relation"]
    if relation == "action_associated_with_change":
        if candidate["status"] == "insufficient_comparison":
            return None, False, {"reason": "requires_action_present_and_absent_exposure"}
        present = candidate["action_present"]
        absent = candidate["action_absent"]
        n1, y1 = present["evaluable"], present["changed"]
        n0, y0 = absent["evaluable"], absent["changed"]
        p1 = (y1 + 1.0) / (n1 + 2.0)
        p0 = (y0 + 1.0) / (n0 + 2.0)
        separation = abs(p1 - p0)
        uncertainty = (_binary_entropy(p1) + _binary_entropy(p0)) / 2.0
        exposure = min(n1, n0) / (min(n1, n0) + 2.0)
        balance = 1.0 - abs(n1 - n0) / (n1 + n0)
        if objective == "information_gain":
            score = separation * uncertainty * (0.35 + 0.65 * exposure)
        elif objective == "discrimination":
            score = separation * (0.25 + 0.75 * exposure)
        elif objective == "falsifiability":
            score = min(p1, 1 - p1) + min(p0, 1 - p0)
            score *= 0.5 * (0.4 + 0.6 * exposure)
        elif objective == "uncertainty_reduction":
            score = uncertainty * exposure
        else:
            score = balance * (0.3 + 0.7 * exposure)
        return score, True, {
            "p_change_action_present": round(p1, 6),
            "p_change_action_absent": round(p0, 6),
            "absolute_rate_difference": round(separation, 6),
            "exposure_balance": round(balance, 6),
        }

    n = int(candidate.get("evaluable", 0) or 0)
    c = int(candidate.get("confirmations", 0) or 0)
    r = int(candidate.get("refutations", 0) or 0)
    if not n:
        return None, False, {"reason": "no_evaluable_transition"}
    p = (c + 1.0) / (n + 2.0)
    entropy = _binary_entropy(p)
    reliability = n / (n + 4.0)
    if objective == "information_gain":
        score = entropy * (0.35 + 0.65 * reliability)
    elif objective == "discrimination":
        score = 4.0 * p * (1.0 - p) * (0.25 + 0.75 * reliability)
    elif objective == "falsifiability":
        score = (min(c, r) + 1.0) / (n + 2.0)
    elif objective == "uncertainty_reduction":
        alpha, beta = c + 1.0, r + 1.0
        total = alpha + beta
        h_confirm = _binary_entropy((alpha + 1.0) / (total + 1.0))
        h_refute = _binary_entropy(alpha / (total + 1.0))
        score = max(0.0, entropy - (p * h_confirm + (1.0 - p) * h_refute))
    else:
        score = 1.0 - abs(c - r) / n
    return score, True, {
        "posterior_relation_rate": round(p, 6),
        "evaluable": n,
    }


def _binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))
