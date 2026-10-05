from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "scripts"))

from open_object_world_epistemic_action_study import (
    inquiry_action_case,
    ranked_temporal,
    run_to_checkpoint,
)
from open_object_world_native_bridge import public_features


CHECKPOINTS = tuple(range(200, 951, 50))


def rate(cases, side):
    evaluable = [row for row in cases if row[side]["evaluable"]]
    if not evaluable:
        return None, 0
    return (
        round(
            sum(bool(row[side]["falsified"]) for row in evaluable)
            / len(evaluable),
            6,
        ),
        len(evaluable),
    )


def main() -> None:
    rows = []
    for seed in range(1, 5):
        for checkpoint in CHECKPOINTS:
            world, attempts, observations, receipts = run_to_checkpoint(
                seed,
                checkpoint,
            )
            ranked = ranked_temporal(observations)
            top = inquiry_action_case(
                world,
                attempts,
                observations,
                receipts,
                ranked[0],
                checkpoint,
            )

            visible_features = public_features(observations[-1])
            state_selected = next(
                (
                    item
                    for item in ranked
                    if str(item["candidate"]["feature"]).endswith(".state")
                    and item["candidate"]["feature"] in visible_features
                ),
                None,
            )
            state = (
                inquiry_action_case(
                    world,
                    attempts,
                    observations,
                    receipts,
                    state_selected,
                    checkpoint,
                )
                if state_selected is not None
                else None
            )
            rows.append(
                {
                    "seed": seed,
                    "checkpoint": checkpoint,
                    "top_inquiry": top,
                    "best_currently_visible_entity_state_inquiry": state,
                }
            )

    top_mature = [
        row["top_inquiry"]
        for row in rows
        if row["top_inquiry"]["epistemic_selection"]["mode"]
        == "seek_disconfirming_observation"
    ]
    state_cases = [
        row["best_currently_visible_entity_state_inquiry"]
        for row in rows
        if row["best_currently_visible_entity_state_inquiry"] is not None
    ]
    state_mature = [
        row
        for row in state_cases
        if row["epistemic_selection"]["mode"]
        == "seek_disconfirming_observation"
    ]

    top_epi_rate, top_epi_n = rate(
        top_mature,
        "epistemic_outcome",
    )
    top_base_rate, top_base_n = rate(
        top_mature,
        "unguided_outcome",
    )
    state_epi_rate, state_epi_n = rate(
        state_mature,
        "epistemic_outcome",
    )
    state_base_rate, state_base_n = rate(
        state_mature,
        "unguided_outcome",
    )

    report = {
        "study": "open-object-world-epistemic-replication-v1",
        "policy": "public-falsification-oriented-v1",
        "policy_parameters_changed": False,
        "checkpoint_protocol": {
            "start": 200,
            "stop": 950,
            "step": 50,
            "checkpoint_count_per_layout": len(CHECKPOINTS),
            "layout_count": 4,
        },
        "world_reward": False,
        "authored_goal": False,
        "hidden_mechanic_access": False,
        "rows": rows,
        "summary": {
            "case_count": len(rows),
            "mature_top_case_count": len(top_mature),
            "mature_top_epistemic_evaluable_count": top_epi_n,
            "mature_top_unguided_evaluable_count": top_base_n,
            "mature_top_epistemic_falsification_rate": top_epi_rate,
            "mature_top_unguided_falsification_rate": top_base_rate,
            "mature_top_different_from_unguided_count": sum(
                row["different_from_unguided"] for row in top_mature
            ),
            "visible_entity_state_case_count": len(state_cases),
            "mature_entity_state_case_count": len(state_mature),
            "mature_entity_state_epistemic_evaluable_count": state_epi_n,
            "mature_entity_state_unguided_evaluable_count": state_base_n,
            "mature_entity_state_epistemic_falsification_rate": state_epi_rate,
            "mature_entity_state_unguided_falsification_rate": state_base_rate,
            "mature_entity_state_different_from_unguided_count": sum(
                row["different_from_unguided"] for row in state_mature
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
