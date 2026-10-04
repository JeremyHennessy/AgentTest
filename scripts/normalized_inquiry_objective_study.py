from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from natural_relation_diversity_sweep import WORLD2_SCRIPTS, WORLD3_SCRIPTS
from normalized_inquiry_objectives import OBJECTIVES, rank_normalized_candidates
from normalized_relation_evidence import normalized_evidence, normalized_relation_candidates
from world2_ecology import initial_world2_state, observe_world2, transition_world2
from world2_native_observation import native_world2_observation
from world3_ecology import initial_world3_state, observe_world3, transition_world3
from world3_native_observation import native_world3_observation


def main():
    corpus = []
    for seed in range(1, 6):
        for name, actions in WORLD2_SCRIPTS:
            corpus.append(run_w2(seed, name, actions))
    for seed in range(1, 5):
        for name, actions in WORLD3_SCRIPTS:
            corpus.append(run_w3(seed, name, actions))
    outcomes = {}
    for objective in OBJECTIVES:
        counts = Counter()
        relation_counts = Counter()
        rows = []
        for item in corpus:
            ranked = rank_normalized_candidates(item["candidates"], objective)
            eligible = [entry for entry in ranked if entry["eligible"]]
            winner = eligible[0] if eligible else None
            label = (
                f"{winner['candidate']['relation']}|{winner['candidate']['feature']}|"
                f"{winner['candidate'].get('action')}"
                if winner else "none"
            )
            counts[label] += 1
            relation_counts[winner["candidate"]["relation"] if winner else "none"] += 1
            rows.append({
                "world": item["world"], "seed": item["seed"], "script": item["script"],
                "winner": label, "winner_score": winner["score"] if winner else None,
                "eligible_count": len(eligible),
            })
        outcomes[objective] = {
            "winner_counts": dict(sorted(counts.items())),
            "relation_counts": dict(sorted(relation_counts.items())),
            "distinct_winners": len(counts),
            "distinct_relation_families": len(relation_counts),
            "rows": rows,
        }
    print(json.dumps({
        "study": "normalized-inquiry-objective-comparison-v1",
        "trajectory_count": len(corpus),
        "objectives": outcomes,
    }, indent=2, sort_keys=True))


def run_w2(seed, name, actions):
    world = initial_world2_state(seed=seed)
    samples = [native_world2_observation(observe_world2(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world2(world, action, cycle=cycle)
        samples.append(native_world2_observation(observe_world2(world), action_receipt=record))
    return summarize("world2", seed, name, samples)


def run_w3(seed, name, actions):
    world = initial_world3_state(seed=seed)
    samples = [native_world3_observation(observe_world3(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world3(world, action, cycle=cycle)
        samples.append(native_world3_observation(observe_world3(world), action_receipt=record))
    return summarize("world3", seed, name, samples)


def summarize(world, seed, script, samples):
    return {
        "world": world, "seed": seed, "script": script,
        "candidates": normalized_relation_candidates(normalized_evidence(samples)),
    }


if __name__ == "__main__":
    main()
