from __future__ import annotations

from typing import Any

from open_object_world_action_association import (
    action_label,
    association_candidates,
)
from open_object_world_explorer import (
    GENERIC_ACTION_ORDER,
    candidate_commands,
    command_key,
)


MIN_EFFECT_SAMPLES = 2


def select_epistemic_command(
    observation: dict[str, Any],
    *,
    feature: str,
    relation: str,
    prefix_observations: list[dict[str, Any]],
    prefix_receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    if relation not in {
        "same_next_observation",
        "changes_next_observation",
    }:
        raise ValueError("epistemic action policy requires temporal inquiry")

    learned = {
        (item["feature"], item["action"]): item
        for item in association_candidates(
            prefix_observations,
            prefix_receipts,
            min_present=1,
        )
    }
    commands = candidate_commands(observation)
    if not commands:
        raise ValueError("no public commands available")

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
                "command": command,
                "action_label": label,
                "present_evaluable": present,
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
        "policy": "public-falsification-oriented-v1",
        "feature": feature,
        "relation": relation,
        "mode": mode,
        "command": chosen["command"],
        "action_label": chosen["action_label"],
        "present_evaluable": chosen["present_evaluable"],
        "posterior_change_probability": chosen[
            "posterior_change_probability"
        ],
        "falsification_probability": chosen[
            "falsification_probability"
        ],
        "epistemic_score": score,
        "candidate_count": len(rows),
    }
