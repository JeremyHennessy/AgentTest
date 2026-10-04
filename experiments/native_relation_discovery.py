from __future__ import annotations

from copy import deepcopy
from typing import Any

RELATION_VERSION = "native-relation-discovery-v0"
RELATIONS = (
    "same_next_observation",
    "changes_next_observation",
    "action_precedes_change",
)
MAX_PROPOSALS = 24


def propose_relations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compose candidate relations from observable feature names only, not world truth."""
    features = _feature_names(observations)
    actions = _observed_actions(observations)
    proposals: list[dict[str, Any]] = []
    for feature in features:
        for relation in ("same_next_observation", "changes_next_observation"):
            proposals.append(_proposal(relation, feature, None, len(proposals) + 1))
    for action in actions:
        for feature in features:
            proposals.append(_proposal("action_precedes_change", feature, action, len(proposals) + 1))
    return proposals[:MAX_PROPOSALS]


def evaluate_relations(
    proposals: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ledger = []
    for proposal in proposals:
        confirmations = 0
        refutations = 0
        evaluable = 0
        for left, right in zip(observations, observations[1:]):
            before = _feature_value(left, proposal["feature"])
            after = _feature_value(right, proposal["feature"])
            if before is _MISSING or after is _MISSING:
                continue
            relation = proposal["relation"]
            if relation == "same_next_observation":
                matched = before == after
            elif relation == "changes_next_observation":
                matched = before != after
            else:
                receipt = right.get("action_receipt") or {}
                if receipt.get("action") != proposal["action"]:
                    continue
                matched = before != after
            evaluable += 1
            if matched:
                confirmations += 1
            else:
                refutations += 1
        ledger.append({
            "proposal": deepcopy(proposal),
            "evaluable": evaluable,
            "confirmations": confirmations,
            "refutations": refutations,
            "support": round(confirmations / evaluable, 6) if evaluable else None,
            "status": (
                "unevaluated"
                if not evaluable
                else "supported"
                if confirmations > refutations
                else "challenged"
                if refutations > confirmations
                else "mixed"
            ),
        })
    return ledger


def select_relation_inquiry(ledger: list[dict[str, Any]]) -> dict[str, Any] | None:
    evaluable = [item for item in ledger if item["evaluable"]]
    if not evaluable:
        return None
    # Prefer contradiction first, then more evidence. This is uncertainty-driven,
    # not a hidden-truth score.
    return deepcopy(sorted(
        evaluable,
        key=lambda item: (
            0 if item["status"] in {"challenged", "mixed"} else 1,
            -item["evaluable"],
            item["proposal"]["id"],
        ),
    )[0])


def grounded_relation_candidate(selected: dict[str, Any] | None) -> dict[str, Any] | None:
    if selected is None:
        return None
    proposal = selected["proposal"]
    feature = proposal["feature"]
    relation = proposal["relation"]
    action = proposal.get("action")
    if relation == "same_next_observation":
        hypothesis = f"Observable feature {feature} tends to remain the same across consecutive legitimate observations."
        falsification = f"A consecutive evaluable observation where {feature} differs counts against this relation."
    elif relation == "changes_next_observation":
        hypothesis = f"Observable feature {feature} tends to change across consecutive legitimate observations."
        falsification = f"A consecutive evaluable observation where {feature} remains the same counts against this relation."
    else:
        hypothesis = f"Observed action {action} tends to precede a change in observable feature {feature}."
        falsification = f"An evaluable {action} transition where {feature} does not change counts against this relation."
    return {
        "id": "NRC-" + proposal["id"],
        "question": f"What next legitimate observation would most directly challenge the relation: {hypothesis}",
        "hypothesis": hypothesis,
        "experiment": "Collect the next legitimately observable sample required by this relation and compare it with the prior sample.",
        "falsification": falsification,
        "predicted_observation": None,
        "relation_status": selected["status"],
        "evaluable_trials": selected["evaluable"],
        "confirmations": selected["confirmations"],
        "refutations": selected["refutations"],
    }


_MISSING = object()


def _proposal(relation: str, feature: str, action: str | None, index: int) -> dict[str, Any]:
    return {
        "id": f"NR{index:04d}",
        "version": RELATION_VERSION,
        "relation": relation,
        "feature": feature,
        "action": action,
    }


def _feature_names(observations: list[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
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
