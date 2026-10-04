from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from normalized_inquiry_objectives import OBJECTIVES
from prospective_inquiry_benchmark import benchmark_trajectory
from prospective_objective_robustness import choose_split
from world4_toggle_ecology import initial_world4_state, observe_world4, transition_world4
from world4_native_observation import native_world4_observation

SPLITS = ("early", "midpoint", "late")
SCRIPTS = (
    ("observe_short", ("observe",) * 4),
    ("observe_long", ("observe",) * 10),
    ("north_probe", ("north", "interact", "observe", "south", "observe")),
    ("east_probe", ("east", "interact", "observe", "west", "observe")),
    ("south_probe", ("south", "interact", "observe", "north", "observe")),
    ("west_probe", ("west", "interact", "observe", "east", "observe")),
)


def main() -> None:
    corpus = []
    for seed in range(1, 5):
        for script, actions in SCRIPTS:
            corpus.append((seed, script, samples_world4(seed, actions)))

    splits = {}
    for split_name in SPLITS:
        rows = []
        for seed, script, samples in corpus:
            split_index = choose_split(split_name, len(samples))
            rows.append({
                "seed": seed,
                "script": script,
                "sample_count": len(samples),
                "split_index": split_index,
                "benchmark": benchmark_trajectory(samples, split_index=split_index),
            })
        splits[split_name] = {
            objective: aggregate(rows, objective)
            for objective in OBJECTIVES
        }

    report = {
        "study": "world4-fresh-objective-holdout-v1",
        "world": "world4-toggle-ecology-v0",
        "trajectory_count": len(corpus),
        "split_protocols": list(SPLITS),
        "objectives_frozen_from": "normalized-inquiry-objectives-v1",
        "splits": splits,
        "rows": rows_by_split(corpus),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def rows_by_split(corpus):
    output = {}
    for split_name in SPLITS:
        rows = []
        for seed, script, samples in corpus:
            split_index = choose_split(split_name, len(samples))
            rows.append({
                "seed": seed,
                "script": script,
                "split_index": split_index,
                "benchmark": benchmark_trajectory(samples, split_index=split_index),
            })
        output[split_name] = rows
    return output


def aggregate(rows, objective):
    relation_counts = Counter()
    feature_counts = Counter()
    selected = 0
    evaluable = 0
    reductions = []
    evidence_counts = []
    action_both_exposures = 0
    for row in rows:
        result = row["benchmark"]["results"][objective]
        if result["status"] != "selected":
            continue
        selected += 1
        candidate = result["selected"]["candidate"]
        relation_counts[candidate["relation"]] += 1
        feature_counts[candidate["feature"]] += 1
        held = result["held_out"]
        if held.get("evaluable"):
            evaluable += 1
            evidence_counts.append(int(held.get("evidence_count", 0) or 0))
            if held.get("posterior_entropy_reduction") is not None:
                reductions.append(float(held["posterior_entropy_reduction"]))
        if held.get("both_exposures_observed"):
            action_both_exposures += 1
    return {
        "selected_count": selected,
        "held_out_evaluable_count": evaluable,
        "held_out_evaluable_rate": round(evaluable / selected, 6) if selected else None,
        "relation_counts": dict(sorted(relation_counts.items())),
        "feature_counts": dict(sorted(feature_counts.items())),
        "mean_held_out_evidence_count": round(statistics.mean(evidence_counts), 6) if evidence_counts else None,
        "mean_realized_posterior_entropy_reduction": round(statistics.mean(reductions), 6) if reductions else None,
        "positive_entropy_reduction_count": sum(1 for value in reductions if value > 0),
        "negative_entropy_reduction_count": sum(1 for value in reductions if value < 0),
        "zero_entropy_reduction_count": sum(1 for value in reductions if value == 0),
        "action_both_exposures_held_out_count": action_both_exposures,
    }


def samples_world4(seed, actions):
    world = initial_world4_state(seed=seed)
    samples = [native_world4_observation(observe_world4(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world4(world, action, cycle=cycle)
        samples.append(native_world4_observation(observe_world4(world), action_receipt=record))
    return samples


if __name__ == "__main__":
    main()
