from __future__ import annotations

from typing import Any

from normalized_inquiry_objectives import rank_normalized_candidates
from open_object_world_native_bridge import public_features


def action_label(receipt: dict[str, Any]) -> str:
    action = str(receipt.get("action") or "")
    target = str(receipt.get("target") or "")
    direction = str(receipt.get("direction") or "")
    parts = [action]
    if target:
        parts.append(target)
    if direction:
        parts.append(direction)
    return ":".join(parts)


def association_candidates(
    observations: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    *,
    min_present: int = 2,
) -> list[dict[str, Any]]:
    if len(observations) != len(receipts) + 1:
        raise ValueError("trace observations/receipts are misaligned")

    feature_names = sorted(
        {
            feature
            for observation in observations
            for feature in public_features(observation)
        }
    )
    action_names = sorted({action_label(receipt) for receipt in receipts})
    rows = []
    index = 1

    for feature in feature_names:
        for action in action_names:
            present = {"same": 0, "changed": 0, "evaluable": 0}
            absent = {"same": 0, "changed": 0, "evaluable": 0}
            for left, right, receipt in zip(
                observations,
                observations[1:],
                receipts,
            ):
                before = public_features(left)
                after = public_features(right)
                if feature not in before or feature not in after:
                    continue
                bucket = (
                    present
                    if action_label(receipt) == action
                    else absent
                )
                changed = before[feature] != after[feature]
                bucket["changed" if changed else "same"] += 1
                bucket["evaluable"] += 1

            if (
                present["evaluable"] < min_present
                or absent["evaluable"] == 0
            ):
                continue
            p_present = present["changed"] / present["evaluable"]
            p_absent = absent["changed"] / absent["evaluable"]
            difference = round(p_present - p_absent, 6)
            rows.append(
                {
                    "id": f"OWA{index:05d}",
                    "relation": "action_associated_with_change",
                    "feature": feature,
                    "action": action,
                    "status": (
                        "association_observed"
                        if difference != 0
                        else "no_observed_association"
                    ),
                    "effect_difference": difference,
                    "action_present": present,
                    "action_absent": absent,
                    "evaluable": (
                        present["evaluable"] + absent["evaluable"]
                    ),
                }
            )
            index += 1
    return rows


def rank_information_gain(
    observations: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = association_candidates(observations, receipts)
    return [
        item
        for item in rank_normalized_candidates(
            candidates,
            "information_gain",
        )
        if item["eligible"]
    ]


def match_candidate(
    candidate: dict[str, Any],
    observations: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for item in association_candidates(
        observations,
        receipts,
        min_present=1,
    ):
        if (
            item["feature"] == candidate["feature"]
            and item["action"] == candidate["action"]
        ):
            return item
    return None
