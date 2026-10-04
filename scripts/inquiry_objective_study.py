from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from inquiry_objectives import OBJECTIVES, rank_with_objective
from natural_relation_diversity_sweep import HELD_OUT, WORLD2_SCRIPTS, WORLD3_SCRIPTS, run_world2, run_world3


def main() -> None:
    corpus = []
    for seed in range(1, 6):
        for name, actions in WORLD2_SCRIPTS:
            corpus.append(run_world2(seed, name, actions))
    for seed in range(1, 5):
        for name, actions in WORLD3_SCRIPTS:
            corpus.append(run_world3(seed, name, actions))

    objectives = {}
    for objective in OBJECTIVES:
        rows = []
        winners = Counter()
        for item in corpus:
            ranked = rank_with_objective(
                {"families": item["family_memory"]},
                HELD_OUT,
                objective,
            )
            winner = ranked[0]["proposal"]["relation"]
            winners[winner] += 1
            rows.append({
                "world": item["world"],
                "seed": item["seed"],
                "script": item["script"],
                "winner": winner,
                "winner_score": ranked[0]["score"],
                "scores": {entry["proposal"]["id"]: entry["score"] for entry in ranked},
            })
        objectives[objective] = {
            "winner_counts": dict(sorted(winners.items())),
            "distinct_winners": sorted(winners),
            "selection_diversity": len(winners),
            "rows": rows,
        }

    report = {
        "study": "inquiry-objective-comparison-v1",
        "corpus": "frozen-natural-relation-diversity-45-trajectories",
        "trajectory_count": len(corpus),
        "objectives": objectives,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
