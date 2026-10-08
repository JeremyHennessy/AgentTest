"""Opt-in pure belief revision from real action outcomes, not hidden world rules.

The general translation hypothesis is learned from observations and combined
with local counterevidence. No action selection, simulator, external AI model,
state writer, scheduler, or persistent pilot is invoked.
"""
from __future__ import annotations

from collections import Counter
import math

from .action_effect_transfer import (
    SMOOTHING, StudyInvalid, domain, point, predict, validate_rows,
)

VERSION = "ora2-structured-local-exception-belief-v1"
LOCAL_PRIOR_STRENGTH = 2


def _distance(a: dict, b: dict) -> float:
    """Finite Jensen-Shannon disagreement, in bits."""
    mixed = {p: (a[p] + b[p]) / 2 for p in domain()}
    return sum((a[p] * math.log2(a[p] / mixed[p]) +
                b[p] * math.log2(b[p] / mixed[p])) / 2 for p in domain())


def _top_one(distribution: dict):
    return max(sorted(distribution), key=lambda target: distribution[target])


def propose_from_history(rows: list[dict], before, action: str) -> dict:
    """Predict without a test outcome or any direct access to world mechanics.

    Historical source rows are the persistence layer: cold reconstruction
    derives exactly this belief again without adding or dropping a record.
    """
    records = validate_rows(rows)
    before = point(before)
    if type(action) is not str or not action or len(action) > 128:
        raise StudyInvalid("invalid opaque action")
    general = predict(records, before, action, model="shared_effect")
    local = Counter()
    refs = []
    for r in records:
        if r["before"] == before and r["action"] == action:
            local[r["after"]] += 1
            refs.append((r["source"], r["source_id"]))
    support = sum(local.values())
    if support:
        weight = support / (support + LOCAL_PRIOR_STRENGTH)
        learned = {p: SMOOTHING / len(domain()) +
                   (1 - SMOOTHING) * local[p] / support for p in domain()}
        combined = {p: (1 - weight) * general[p] + weight * learned[p]
                    for p in domain()}
        divergence = _distance(general, learned)
    else:
        weight, combined, divergence = 0.0, general, 0.0
    if not math.isclose(math.fsum(combined.values()), 1, abs_tol=1e-12, rel_tol=0):
        raise StudyInvalid("reconstructed forecast has incorrect total mass")
    if any(not math.isfinite(prob) or prob <= 0 or prob >= 1 for prob in combined.values()):
        raise StudyInvalid("improper categorical probability")
    return {
        "version": VERSION,
        "before": list(before),
        "action": action,
        "source_world": "bounded-stateful-world-v1",
        "local_observations": support,
        "local_source_refs": [{"source": s, "source_id": i} for s, i in refs],
        "local_weight": weight,
        "general_local_disagreement_bits": divergence,
        "general_top_one": list(_top_one(general)),
        "posterior_top_one": list(_top_one(combined)),
        "probabilities": [{"after": list(p), "probability": combined[p]}
                          for p in domain()],
        "autonomous_action_authorized": False,
        "pilot_enabled": False,
        "inference_limits": "Authored local/global mixture and public coordinate representation; no learned causal explanation of an unobserved local obstruction.",
    }
