from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from natural_relation_diversity_sweep import WORLD2_SCRIPTS, WORLD3_SCRIPTS
from normalized_inquiry_objectives import OBJECTIVES
from prospective_inquiry_benchmark import benchmark_trajectory
from world2_ecology import initial_world2_state, observe_world2, transition_world2
from world2_native_observation import native_world2_observation
from world3_ecology import initial_world3_state, observe_world3, transition_world3
from world3_native_observation import native_world3_observation

SPLITS = ("early", "midpoint", "late")


def main() -> None:
    corpus = []
    for seed in range(1, 6):
        for name, actions in WORLD2_SCRIPTS:
            corpus.append(("world2", seed, name, samples_world2(seed, actions)))
    for seed in range(1, 5):
        for name, actions in WORLD3_SCRIPTS:
            corpus.append(("world3", seed, name, samples_world3(seed, actions)))

    split_reports = {}
    agreement = {}
    for split_name in SPLITS:
        rows = []
        for world, seed, script, samples in corpus:
            split_index = choose_split(split_name, len(samples))
            bench = benchmark_trajectory(samples, split_index=split_index)
            rows.append({
                "world": world,
                "seed": seed,
                "script": script,
                "split_index": split_index,
                "sample_count": len(samples),
                "benchmark": bench,
            })
        split_reports[split_name] = {
            objective: aggregate(rows, objective)
            for objective in OBJECTIVES
        }
        agreement[split_name] = exact_selection_agreement(
            rows, "information_gain", "discrimination"
        )

    cross_split = {
        objective: {
            "mean_entropy_reduction_by_split": {
                split_name: split_reports[split_name][objective][
                    "mean_realized_posterior_entropy_reduction"
                ]
                for split_name in SPLITS
            },
            "held_out_evaluable_rate_by_split": {
                split_name: split_reports[split_name][objective][
                    "held_out_evaluable_rate"
                ]
                for split_name in SPLITS
            },
        }
        for objective in OBJECTIVES
    }

    print(json.dumps({
        "study": "prospective-objective-robustness-v1",
        "trajectory_count": len(corpus),
        "split_protocols": list(SPLITS),
        "split_reports": split_reports,
        "information_gain_discrimination_exact_selection_agreement": agreement,
        "cross_split": cross_split,
    }, indent=2, sort_keys=True))


def choose_split(name: str, sample_count: int) -> int:
    if name == "early":
        value = max(2, sample_count // 3)
    elif name == "midpoint":
        value = max(2, sample_count // 2)
    elif name == "late":
        value = max(2, sample_count - 2)
    else:
        raise ValueError(name)
    return min(value, sample_count - 1)


def aggregate(rows, objective):
    selected = 0
    evaluable = 0
    reductions = []
    relation_counts = Counter()
    feature_counts = Counter()
    evidence_counts = []
    for row in rows:
        item = row["benchmark"]["results"][objective]
        if item["status"] != "selected":
            continue
        selected += 1
        candidate = item["selected"]["candidate"]
        relation_counts[candidate["relation"]] += 1
        feature_counts[candidate["feature"]] += 1
        held = item["held_out"]
        if held.get("evaluable"):
            evaluable += 1
            evidence_counts.append(int(held.get("evidence_count", 0) or 0))
            reduction = held.get("posterior_entropy_reduction")
            if reduction is not None:
                reductions.append(float(reduction))
    return {
        "selected_count": selected,
        "held_out_evaluable_count": evaluable,
        "held_out_evaluable_rate": round(evaluable / selected, 6) if selected else None,
        "relation_counts": dict(sorted(relation_counts.items())),
        "feature_counts": dict(sorted(feature_counts.items())),
        "mean_held_out_evidence_count": (
            round(statistics.mean(evidence_counts), 6)
            if evidence_counts
            else None
        ),
        "mean_realized_posterior_entropy_reduction": (
            round(statistics.mean(reductions), 6)
            if reductions
            else None
        ),
        "positive_entropy_reduction_count": sum(1 for value in reductions if value > 0),
        "negative_entropy_reduction_count": sum(1 for value in reductions if value < 0),
        "zero_entropy_reduction_count": sum(1 for value in reductions if value == 0),
    }


def exact_selection_agreement(rows, left_objective, right_objective):
    equal = 0
    comparable = 0
    for row in rows:
        left = row["benchmark"]["results"][left_objective]
        right = row["benchmark"]["results"][right_objective]
        if left["status"] != "selected" or right["status"] != "selected":
            continue
        comparable += 1
        l = left["selected"]["candidate"]
        r = right["selected"]["candidate"]
        left_key = (l["relation"], l["feature"], l.get("action"))
        right_key = (r["relation"], r["feature"], r.get("action"))
        equal += int(left_key == right_key)
    return {
        "comparable_count": comparable,
        "exact_match_count": equal,
        "exact_match_rate": round(equal / comparable, 6) if comparable else None,
    }


def samples_world2(seed, actions):
    world = initial_world2_state(seed=seed)
    samples = [native_world2_observation(observe_world2(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world2(world, action, cycle=cycle)
        samples.append(native_world2_observation(observe_world2(world), action_receipt=record))
    return samples


def samples_world3(seed, actions):
    world = initial_world3_state(seed=seed)
    samples = [native_world3_observation(observe_world3(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world3(world, action, cycle=cycle)
        samples.append(native_world3_observation(observe_world3(world), action_receipt=record))
    return samples


if __name__ == "__main__":
    main()
