from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from normalized_inquiry_objectives import rank_normalized_candidates
from open_object_world_native_bridge import (
    collect_trace,
    held_out_evaluation,
    temporal_candidates,
)


def main() -> None:
    rows = []
    for seed in range(1, 5):
        trace = collect_trace(seed=seed, steps=1000)
        observations = trace["observations"]
        split = len(observations) // 2
        prefix = observations[:split]
        held = observations[split - 1 :]
        candidates = temporal_candidates(prefix)
        ranked = [
            item
            for item in rank_normalized_candidates(
                candidates,
                "information_gain",
            )
            if item["eligible"]
        ]

        top = []
        for rank, item in enumerate(ranked[:10], start=1):
            top.append(
                {
                    "rank": rank,
                    "feature": item["candidate"]["feature"],
                    "relation": item["candidate"]["relation"],
                    "score": item["score"],
                    "prefix_evaluable": item["candidate"]["evaluable"],
                    "prefix_confirmations": item["candidate"][
                        "confirmations"
                    ],
                    "prefix_refutations": item["candidate"]["refutations"],
                    "held_out": held_out_evaluation(
                        item["candidate"],
                        held,
                    ),
                }
            )

        entity_state_rows = []
        for rank, item in enumerate(ranked, start=1):
            feature = str(item["candidate"]["feature"])
            if not feature.endswith(".state"):
                continue
            entity_state_rows.append(
                {
                    "rank": rank,
                    "feature": feature,
                    "relation": item["candidate"]["relation"],
                    "score": item["score"],
                    "prefix_evaluable": item["candidate"]["evaluable"],
                    "held_out": held_out_evaluation(
                        item["candidate"],
                        held,
                    ),
                }
            )

        rows.append(
            {
                "seed": seed,
                "candidate_count": len(ranked),
                "top_10": top,
                "entity_state_candidates": entity_state_rows,
            }
        )

    report = {
        "study": "open-object-world-candidate-spectrum-v1",
        "steps_per_layout": 1000,
        "objective": "information_gain",
        "feature_reweighting": False,
        "feature_suppression": False,
        "rows": rows,
        "summary": {
            "top_features": [
                row["top_10"][0]["feature"]
                if row["top_10"]
                else None
                for row in rows
            ],
            "best_entity_state_ranks": [
                (
                    row["entity_state_candidates"][0]["rank"]
                    if row["entity_state_candidates"]
                    else None
                )
                for row in rows
            ],
            "entity_state_candidate_counts": [
                len(row["entity_state_candidates"])
                for row in rows
            ],
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
