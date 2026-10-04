from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

OBJECTIVE_VERSION = "inquiry-objectives-v0"
OBJECTIVES = (
    "baseline",
    "information_gain",
    "discrimination",
    "falsifiability",
    "uncertainty_reduction",
    "evidence_balance",
)


def rank_with_objective(
    family_memory: dict[str, Any],
    proposals: list[dict[str, Any]],
    objective: str,
) -> list[dict[str, Any]]:
    if objective not in OBJECTIVES:
        raise ValueError("unknown inquiry objective")
    ranked = []
    families = family_memory.get("families", {})
    for proposal in proposals:
        record = families.get(proposal["relation"], {})
        n = int(record.get("evaluable", 0) or 0)
        c = int(record.get("confirmations", 0) or 0)
        r = int(record.get("refutations", 0) or 0)
        score = _score(objective, n, c, r)
        ranked.append({
            "proposal": deepcopy(proposal),
            "objective": objective,
            "score": round(score, 6),
            "family_evidence": {"evaluable": n, "confirmations": c, "refutations": r},
        })
    return sorted(ranked, key=lambda item: (-item["score"], item["proposal"]["id"]))


def _score(objective: str, n: int, confirmations: int, refutations: int) -> float:
    if objective == "baseline":
        conflict = min(confirmations, refutations)
        conflict_ratio = conflict / n if n else 0.0
        evidence_weight = min(0.4, n / 20.0)
        return 0.3 + evidence_weight + min(0.3, conflict_ratio)

    # Beta(1,1) posterior over whether the relation holds on an evaluable trial.
    alpha = confirmations + 1.0
    beta = refutations + 1.0
    p = alpha / (alpha + beta)
    entropy = _binary_entropy(p)
    evidence_reliability = n / (n + 4.0) if n else 0.0

    if objective == "information_gain":
        # Prefer uncertain but increasingly grounded families; no target truth is used.
        return entropy * (0.35 + 0.65 * evidence_reliability)
    if objective == "discrimination":
        # Prefer a test whose possible outcomes are both plausible and therefore discriminating.
        return 4.0 * p * (1.0 - p) * (0.25 + 0.75 * evidence_reliability)
    if objective == "falsifiability":
        # Prefer relations with meaningful observed opportunity to fail, without rewarding raw volume alone.
        minority = min(confirmations, refutations)
        return (minority + 1.0) / (n + 2.0) if n else 0.5
    if objective == "uncertainty_reduction":
        # Approximate expected one-sample entropy reduction under the current posterior.
        current = entropy
        total = alpha + beta
        h_confirm = _binary_entropy((alpha + 1.0) / (total + 1.0))
        h_refute = _binary_entropy(alpha / (total + 1.0))
        expected_after = p * h_confirm + (1.0 - p) * h_refute
        return max(0.0, current - expected_after)
    if objective == "evidence_balance":
        if not n:
            return 1.0
        return 1.0 - abs(confirmations - refutations) / n
    raise AssertionError(objective)


def _binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))
