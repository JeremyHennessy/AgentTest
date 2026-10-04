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


def main() -> None:
    trajectories = []
    for seed in range(1, 6):
        for name, actions in WORLD2_SCRIPTS:
            trajectories.append(("world2", seed, name, samples_world2(seed, actions)))
    for seed in range(1, 5):
        for name, actions in WORLD3_SCRIPTS:
            trajectories.append(("world3", seed, name, samples_world3(seed, actions)))

    rows = []
    for world, seed, script, samples in trajectories:
        result = benchmark_trajectory(samples)
        rows.append({
            "world": world,
            "seed": seed,
            "script": script,
            "benchmark": result,
        })

    objectives = {
        objective: aggregate_objective(rows, objective)
        for objective in OBJECTIVES
    }
    report = {
        "study": "prospective-inquiry-benchmark-v1",
        "corpus": "frozen-natural-relation-diversity-45-trajectories",
        "selection_protocol": "prefix_only_then_held_out_suffix",
        "trajectory_count": len(rows),
        "objectives": objectives,
        "rows": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def aggregate_objective(rows, objective):
    relation_counts = Counter()
    feature_counts = Counter()
    held_status = Counter()
    entropy_reductions = []
    evidence_counts = []
    transition_refutations = 0
    transition_confirmations = 0
    transition_both = 0
    action_both_exposures = 0
    selected = 0
    evaluable = 0

    for row in rows:
        item = row["benchmark"]["results"][objective]
        if item["status"] != "selected":
            continue
        selected += 1
        candidate = item["selected"]["candidate"]
        relation_counts[candidate["relation"]] += 1
        feature_counts[candidate["feature"]] += 1
        held = item["held_out"]
        held_status[held["status"]] += 1
        if held.get("evaluable"):
            evaluable += 1
            evidence_counts.append(int(held.get("evidence_count", 0) or 0))
            reduction = held.get("posterior_entropy_reduction")
            if reduction is not None:
                entropy_reductions.append(float(reduction))
        if candidate["relation"] == "action_associated_with_change":
            if held.get("both_exposures_observed"):
                action_both_exposures += 1
        else:
            transition_refutations += int(bool(held.get("realized_refutation")))
            transition_confirmations += int(bool(held.get("realized_confirmation")))
            transition_both += int(bool(held.get("both_outcomes_observed")))

    return {
        "selected_count": selected,
        "held_out_evaluable_count": evaluable,
        "held_out_evaluable_rate": round(evaluable / selected, 6) if selected else None,
        "relation_counts": dict(sorted(relation_counts.items())),
        "feature_counts": dict(sorted(feature_counts.items())),
        "held_out_status_counts": dict(sorted(held_status.items())),
        "total_held_out_evidence_count": sum(evidence_counts),
        "mean_held_out_evidence_count": round(statistics.mean(evidence_counts), 6) if evidence_counts else None,
        "mean_realized_posterior_entropy_reduction": (
            round(statistics.mean(entropy_reductions), 6)
            if entropy_reductions
            else None
        ),
        "positive_entropy_reduction_count": sum(1 for value in entropy_reductions if value > 0),
        "negative_entropy_reduction_count": sum(1 for value in entropy_reductions if value < 0),
        "transition_realized_refutation_count": transition_refutations,
        "transition_realized_confirmation_count": transition_confirmations,
        "transition_both_outcomes_count": transition_both,
        "action_both_exposures_held_out_count": action_both_exposures,
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
