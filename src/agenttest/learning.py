from __future__ import annotations

from typing import Any

EMPIRICAL_LEARNING_VERSION = "empirical-learning-v1"
REPOSITORY_STABILITY_FAMILY = "repository_stability_without_intervention"
MIN_ADAPTIVE_EVALUABLE_TRIALS = 3


def _family_for_experiment(experiment: dict[str, Any]) -> str | None:
    explicit = experiment.get("learning_family")
    if isinstance(explicit, str) and explicit:
        return explicit
    if experiment.get("source") == "repository_stability_prediction":
        return REPOSITORY_STABILITY_FAMILY
    return None


def _empty_family(family: str) -> dict[str, Any]:
    return {
        "family": family,
        "completed_trials": 0,
        "evaluable_trials": 0,
        "stable_observations": 0,
        "change_observations": 0,
        "inconclusive_trials": 0,
        "stability_rate": None,
        "next_expected_status": "confirmed",
        "experiment_refs": [],
        "evidence_refs": [],
        "last_completed_cycle": None,
    }


def _dedupe_append(values: list[str], value: str | None, *, limit: int = 64) -> None:
    if value and value not in values:
        values.append(value)
        if len(values) > limit:
            del values[:-limit]


def _stance_for_family(record: dict[str, Any]) -> str:
    evaluable = int(record.get("evaluable_trials", 0) or 0)
    stable = int(record.get("stable_observations", 0) or 0)
    changed = int(record.get("change_observations", 0) or 0)
    if (
        evaluable >= MIN_ADAPTIVE_EVALUABLE_TRIALS
        and changed > stable
    ):
        return "violated"
    return "confirmed"


def consolidate_empirical_learning(state: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a provenance-backed empirical summary from completed experiments."""

    families: dict[str, dict[str, Any]] = {}

    for experiment in state.get("experiments", []):
        if experiment.get("status") != "completed":
            continue
        family = _family_for_experiment(experiment)
        if family is None:
            continue

        record = families.setdefault(family, _empty_family(family))
        record["completed_trials"] += 1

        experiment_id = str(experiment.get("id") or "")
        _dedupe_append(record["experiment_refs"], experiment_id or None)
        for ref in experiment.get("evidence_refs", []):
            _dedupe_append(record["evidence_refs"], str(ref))

        cycle = int(experiment.get("cycle", 0) or 0)
        current_last = record.get("last_completed_cycle")
        record["last_completed_cycle"] = (
            cycle
            if current_last is None
            else max(int(current_last), cycle)
        )

        observed_status = experiment.get("observed_prediction_status")
        if observed_status == "confirmed":
            record["stable_observations"] += 1
            record["evaluable_trials"] += 1
        elif observed_status == "violated":
            record["change_observations"] += 1
            record["evaluable_trials"] += 1
        elif observed_status == "invalidated_by_intervention":
            record["inconclusive_trials"] += 1

    for record in families.values():
        evaluable = int(record["evaluable_trials"])
        record["stability_rate"] = (
            record["stable_observations"] / evaluable
            if evaluable > 0
            else None
        )
        record["next_expected_status"] = _stance_for_family(record)
        if evaluable == 0:
            record["evidence_state"] = "insufficient_evidence"
        elif evaluable < MIN_ADAPTIVE_EVALUABLE_TRIALS:
            record["evidence_state"] = "provisional"
        elif record["stable_observations"] > record["change_observations"]:
            record["evidence_state"] = "provisional_stability"
        elif record["change_observations"] > record["stable_observations"]:
            record["evidence_state"] = "provisional_change"
        else:
            record["evidence_state"] = "mixed"

    previous = state.get("empirical_learning")
    current = {
        "version": EMPIRICAL_LEARNING_VERSION,
        "updated_cycle": int(state.get("cycles", 0) or 0),
        "families": families,
    }
    state["empirical_learning"] = current
    return {
        "version": EMPIRICAL_LEARNING_VERSION,
        "updated_cycle": current["updated_cycle"],
        "family_count": len(families),
        "changed": previous != current,
        "families": families,
    }


def empirical_family(
    state: dict[str, Any],
    family: str,
) -> dict[str, Any] | None:
    learning = state.get("empirical_learning", {})
    families = learning.get("families", {}) if isinstance(learning, dict) else {}
    record = families.get(family)
    return record if isinstance(record, dict) else None


def expected_prediction_status(
    state: dict[str, Any],
    family: str = REPOSITORY_STABILITY_FAMILY,
) -> str:
    record = empirical_family(state, family)
    if record is None:
        return "confirmed"
    stance = record.get("next_expected_status")
    return stance if stance in {"confirmed", "violated"} else "confirmed"


EMPIRICAL_FRONTIER_MAX_PRESSURE = 0.7
EMPIRICAL_FRONTIER_FULL_MATURITY_TRIALS = 6


def empirical_family_saturation(record: dict[str, Any]) -> float:
    """Estimate how little marginal information another identical trial is likely to add."""

    evaluable = int(record.get("evaluable_trials", 0) or 0)
    if evaluable < MIN_ADAPTIVE_EVALUABLE_TRIALS:
        return 0.0

    rate = record.get("stability_rate")
    if not isinstance(rate, (int, float)):
        return 0.0

    decisiveness = min(1.0, abs(float(rate) - 0.5) * 2.0)
    maturity = min(
        1.0,
        evaluable / float(EMPIRICAL_FRONTIER_FULL_MATURITY_TRIALS),
    )
    return round(decisiveness * (0.5 + 0.5 * maturity), 6)


def empirical_frontier_signal(state: dict[str, Any]) -> dict[str, Any] | None:
    """Transfer mature empirical evidence into a bounded foreground-attention signal."""

    learning_state = state.get("empirical_learning", {})
    families = (
        learning_state.get("families", {})
        if isinstance(learning_state, dict)
        else {}
    )
    candidates: list[dict[str, Any]] = []

    for family, record in families.items():
        if not isinstance(record, dict):
            continue
        saturation = empirical_family_saturation(record)
        if saturation <= 0.0:
            continue
        candidates.append(
            {
                "family": str(family),
                "saturation": saturation,
                "pressure": round(
                    EMPIRICAL_FRONTIER_MAX_PRESSURE * saturation,
                    6,
                ),
                "evaluable_trials": int(
                    record.get("evaluable_trials", 0) or 0
                ),
                "stable_observations": int(
                    record.get("stable_observations", 0) or 0
                ),
                "change_observations": int(
                    record.get("change_observations", 0) or 0
                ),
                "stability_rate": record.get("stability_rate"),
                "evidence_state": record.get("evidence_state"),
                "evidence_refs": list(record.get("evidence_refs", []))[-16:],
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            -float(item["pressure"]),
            -int(item["evaluable_trials"]),
            str(item["family"]),
        )
    )
    return candidates[0]
