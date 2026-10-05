from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from action_association_semantics import compare_prefix_to_suffix
from open_object_world_action_association import (
    match_candidate,
    rank_information_gain,
)
from open_object_world_native_bridge import collect_trace


def main() -> None:
    rows = []
    for seed in range(1, 5):
        trace = collect_trace(seed=seed, steps=1000)
        observations = trace["observations"]
        receipts = trace["receipts"]
        split = len(receipts) // 2
        prefix_observations = observations[: split + 1]
        prefix_receipts = receipts[:split]
        held_observations = observations[split:]
        held_receipts = receipts[split:]

        ranked = rank_information_gain(
            prefix_observations,
            prefix_receipts,
        )
        top_rows = []
        for rank, item in enumerate(ranked[:12], start=1):
            candidate = item["candidate"]
            held_candidate = match_candidate(
                candidate,
                held_observations,
                held_receipts,
            )
            comparison = compare_prefix_to_suffix(
                candidate,
                held_candidate,
            )
            top_rows.append(
                {
                    "rank": rank,
                    "feature": candidate["feature"],
                    "action": candidate["action"],
                    "score": item["score"],
                    "prefix_effect_difference": candidate[
                        "effect_difference"
                    ],
                    "prefix_action_present_evaluable": candidate[
                        "action_present"
                    ]["evaluable"],
                    "prefix_action_absent_evaluable": candidate[
                        "action_absent"
                    ]["evaluable"],
                    "held_out_status": comparison["status"],
                    "held_out_same_direction": comparison[
                        "same_direction"
                    ],
                    "held_out_supports_prefix": comparison[
                        "held_out_supports_prefix"
                    ],
                    "held_out_effect_difference": (
                        comparison["suffix"].get("effect_difference")
                        if isinstance(comparison.get("suffix"), dict)
                        else None
                    ),
                }
            )

        state_rows = []
        for rank, item in enumerate(ranked, start=1):
            candidate = item["candidate"]
            if not str(candidate["feature"]).endswith(".state"):
                continue
            held_candidate = match_candidate(
                candidate,
                held_observations,
                held_receipts,
            )
            comparison = compare_prefix_to_suffix(
                candidate,
                held_candidate,
            )
            state_rows.append(
                {
                    "rank": rank,
                    "feature": candidate["feature"],
                    "action": candidate["action"],
                    "score": item["score"],
                    "prefix_effect_difference": candidate[
                        "effect_difference"
                    ],
                    "prefix_action_present_evaluable": candidate[
                        "action_present"
                    ]["evaluable"],
                    "held_out_status": comparison["status"],
                    "held_out_supports_prefix": comparison[
                        "held_out_supports_prefix"
                    ],
                    "held_out_effect_difference": (
                        comparison["suffix"].get("effect_difference")
                        if isinstance(comparison.get("suffix"), dict)
                        else None
                    ),
                }
            )

        rows.append(
            {
                "seed": seed,
                "candidate_count": len(ranked),
                "top_12": top_rows,
                "entity_state_associations": state_rows,
            }
        )

    report = {
        "study": "open-object-world-action-association-v1",
        "steps_per_layout": 1000,
        "selection_evidence": "first_500_transitions",
        "held_out_evidence": "last_500_transitions",
        "objective": "information_gain",
        "causal_claims": False,
        "feature_reweighting": False,
        "rows": rows,
        "summary": {
            "top_features_actions": [
                (
                    [row["top_12"][0]["feature"], row["top_12"][0]["action"]]
                    if row["top_12"]
                    else None
                )
                for row in rows
            ],
            "top_held_out_supported_count": sum(
                1
                for row in rows
                if row["top_12"]
                and row["top_12"][0]["held_out_status"]
                == "held_out_supported"
            ),
            "best_entity_state_ranks": [
                (
                    row["entity_state_associations"][0]["rank"]
                    if row["entity_state_associations"]
                    else None
                )
                for row in rows
            ],
            "held_out_supported_entity_state_counts": [
                sum(
                    1
                    for item in row["entity_state_associations"]
                    if item["held_out_status"] == "held_out_supported"
                )
                for row in rows
            ],
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
