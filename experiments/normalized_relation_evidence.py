from __future__ import annotations

from copy import deepcopy
from typing import Any

NORMALIZED_VERSION = "normalized-relation-evidence-v1"
_MISSING = object()


def normalized_evidence(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build comparable feature transition and action exposure tables from observed pairs."""
    features = _feature_names(observations)
    actions = _observed_actions(observations)
    feature_tables: dict[str, Any] = {}
    for feature in features:
        transitions = {"same": 0, "changed": 0, "evaluable": 0}
        action_tables = {
            action: {
                "action_present": {"same": 0, "changed": 0, "evaluable": 0},
                "action_absent": {"same": 0, "changed": 0, "evaluable": 0},
            }
            for action in actions
        }
        for left, right in zip(observations, observations[1:]):
            before = _feature_value(left, feature)
            after = _feature_value(right, feature)
            if before is _MISSING or after is _MISSING:
                continue
            changed = before != after
            bucket = "changed" if changed else "same"
            transitions[bucket] += 1
            transitions["evaluable"] += 1
            observed_action = (right.get("action_receipt") or {}).get("action")
            for action in actions:
                exposure = "action_present" if observed_action == action else "action_absent"
                action_tables[action][exposure][bucket] += 1
                action_tables[action][exposure]["evaluable"] += 1
        feature_tables[feature] = {
            "transitions": transitions,
            "action_exposures": action_tables,
        }
    return {
        "version": NORMALIZED_VERSION,
        "pair_count": max(0, len(observations) - 1),
        "features": feature_tables,
    }


def normalized_relation_candidates(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Return comparable association candidates with explicit exposure/base-rate context."""
    candidates = []
    index = 1
    for feature, table in sorted(evidence["features"].items()):
        transitions = table["transitions"]
        candidates.append(_transition_candidate(index, feature, "same_next_observation", transitions)); index += 1
        candidates.append(_transition_candidate(index, feature, "changes_next_observation", transitions)); index += 1
        for action, exposure in sorted(table["action_exposures"].items()):
            present = exposure["action_present"]
            absent = exposure["action_absent"]
            if not present["evaluable"] or not absent["evaluable"]:
                status = "insufficient_comparison"
                effect = None
            else:
                p_present = present["changed"] / present["evaluable"]
                p_absent = absent["changed"] / absent["evaluable"]
                effect = round(p_present - p_absent, 6)
                status = "association_observed" if effect != 0 else "no_observed_association"
            candidates.append({
                "id": f"NE{index:04d}",
                "version": NORMALIZED_VERSION,
                "relation": "action_associated_with_change",
                "feature": feature,
                "action": action,
                "status": status,
                "effect_difference": effect,
                "action_present": deepcopy(present),
                "action_absent": deepcopy(absent),
                "evaluable": present["evaluable"] + absent["evaluable"],
            })
            index += 1
    return candidates


def _transition_candidate(index: int, feature: str, relation: str, transitions: dict[str, int]) -> dict[str, Any]:
    target = "same" if relation == "same_next_observation" else "changed"
    opposite = "changed" if target == "same" else "same"
    return {
        "id": f"NE{index:04d}",
        "version": NORMALIZED_VERSION,
        "relation": relation,
        "feature": feature,
        "action": None,
        "status": "evaluated" if transitions["evaluable"] else "unevaluated",
        "evaluable": transitions["evaluable"],
        "confirmations": transitions[target],
        "refutations": transitions[opposite],
    }


def _feature_names(observations: list[dict[str, Any]]) -> list[str]:
    names = set()
    for item in observations:
        if "visible_object_ids" in item:
            names.add("visible_object_ids")
        for key in ("local_resource", "slow_signal", "local_cue"):
            reading = item.get(key)
            if isinstance(reading, dict) and reading.get("status") == "measured":
                names.add(key)
    return sorted(names)


def _observed_actions(observations: list[dict[str, Any]]) -> list[str]:
    return sorted({
        str((item.get("action_receipt") or {}).get("action"))
        for item in observations
        if (item.get("action_receipt") or {}).get("action")
    })


def _feature_value(observation: dict[str, Any], feature: str) -> Any:
    if feature == "visible_object_ids":
        return tuple(observation.get(feature, []))
    reading = observation.get(feature)
    if isinstance(reading, dict) and reading.get("status") == "measured":
        return reading.get("value")
    return _MISSING
