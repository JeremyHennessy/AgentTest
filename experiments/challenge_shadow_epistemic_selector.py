from __future__ import annotations

from copy import deepcopy
from typing import Any

from challenge_shadow_recorder import action_label
from open_object_world_challenge_explorer import (
    GENERIC_ACTION_ORDER,
    candidate_commands,
    command_key,
)

POLICY = "public-falsification-oriented-v1"
MIN_EFFECT_SAMPLES = 2


def select_epistemic_command(
    observation: dict[str, Any],
    *,
    feature: str,
    relation: str,
    associations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Choose one public command from persisted association summaries.

    Formula, minimum exposure and tie-breaking intentionally match the frozen
    public-falsification-oriented-v1 selector used in prior object-world work.
    This adapter accepts already-persisted association summaries instead of a
    raw observation/receipt prefix.
    """
    if relation not in {
        "same_next_observation",
        "changes_next_observation",
    }:
        raise ValueError("epistemic action policy requires temporal inquiry")

    learned = {
        (str(item["feature"]), str(item["action"])): deepcopy(item)
        for item in associations
        if isinstance(item, dict)
        and item.get("relation") == "action_associated_with_change"
        and item.get("feature")
        and item.get("action")
    }
    commands = candidate_commands(observation)
    if not commands:
        raise ValueError("no public challenge commands available")

    rows = []
    for command in commands:
        label = action_label(command)
        candidate = learned.get((feature, label))
        if candidate is None:
            present = 0
            changed = 0
            p_change = 0.5
        else:
            exposure = candidate["action_present"]
            present = int(exposure["evaluable"])
            changed = int(exposure["changed"])
            p_change = (changed + 1.0) / (present + 2.0)

        falsification_probability = (
            p_change
            if relation == "same_next_observation"
            else 1.0 - p_change
        )
        evidence_weight = present / (present + 2.0)
        rows.append(
            {
                "command": deepcopy(command),
                "action_label": label,
                "present_evaluable": present,
                "present_changed": changed,
                "posterior_change_probability": round(p_change, 6),
                "falsification_probability": round(
                    falsification_probability,
                    6,
                ),
                "evidence_weight": round(evidence_weight, 6),
            }
        )

    undersampled = [
        row
        for row in rows
        if row["present_evaluable"] < MIN_EFFECT_SAMPLES
    ]
    if undersampled:
        chosen = min(
            undersampled,
            key=lambda row: (
                row["present_evaluable"],
                GENERIC_ACTION_ORDER.index(
                    str(row["command"]["action"])
                ),
                command_key(row["command"]),
            ),
        )
        mode = "reduce_action_uncertainty"
        score = None
    else:
        for row in rows:
            row["epistemic_score"] = round(
                row["falsification_probability"]
                * (0.25 + 0.75 * row["evidence_weight"]),
                6,
            )
        chosen = max(
            rows,
            key=lambda row: (
                row["epistemic_score"],
                -GENERIC_ACTION_ORDER.index(
                    str(row["command"]["action"])
                ),
                tuple(reversed(command_key(row["command"]))),
            ),
        )
        mode = "seek_disconfirming_observation"
        score = chosen["epistemic_score"]

    return {
        "policy": POLICY,
        "feature": feature,
        "relation": relation,
        "mode": mode,
        "command": deepcopy(chosen["command"]),
        "action_label": chosen["action_label"],
        "present_evaluable": chosen["present_evaluable"],
        "present_changed": chosen["present_changed"],
        "posterior_change_probability": chosen[
            "posterior_change_probability"
        ],
        "falsification_probability": chosen[
            "falsification_probability"
        ],
        "epistemic_score": score,
        "candidate_count": len(rows),
        "association_count": len(associations),
    }
