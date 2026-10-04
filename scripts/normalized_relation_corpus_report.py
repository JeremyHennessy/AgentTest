from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from natural_relation_diversity_sweep import WORLD2_SCRIPTS, WORLD3_SCRIPTS
from normalized_relation_evidence import normalized_evidence, normalized_relation_candidates
from world2_ecology import initial_world2_state, observe_world2, transition_world2
from world2_native_observation import native_world2_observation
from world3_ecology import initial_world3_state, observe_world3, transition_world3
from world3_native_observation import native_world3_observation


def main() -> None:
    rows = []
    for seed in range(1, 6):
        for name, actions in WORLD2_SCRIPTS:
            rows.append(run_world2(seed, name, actions))
    for seed in range(1, 5):
        for name, actions in WORLD3_SCRIPTS:
            rows.append(run_world3(seed, name, actions))
    statuses = Counter(
        candidate["status"]
        for row in rows
        for candidate in row["candidates"]
        if candidate["relation"] == "action_associated_with_change"
    )
    comparable = [
        candidate
        for row in rows
        for candidate in row["candidates"]
        if candidate["relation"] == "action_associated_with_change"
        and candidate["status"] != "insufficient_comparison"
    ]
    report = {
        "study": "normalized-relation-corpus-v1",
        "trajectory_count": len(rows),
        "action_association_status_counts": dict(sorted(statuses.items())),
        "comparable_action_association_count": len(comparable),
        "rows": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def run_world2(seed, name, actions):
    world = initial_world2_state(seed=seed)
    samples = [native_world2_observation(observe_world2(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world2(world, action, cycle=cycle)
        samples.append(native_world2_observation(observe_world2(world), action_receipt=record))
    return summarize("world2", seed, name, samples)


def run_world3(seed, name, actions):
    world = initial_world3_state(seed=seed)
    samples = [native_world3_observation(observe_world3(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world3(world, action, cycle=cycle)
        samples.append(native_world3_observation(observe_world3(world), action_receipt=record))
    return summarize("world3", seed, name, samples)


def summarize(world, seed, script, samples):
    evidence = normalized_evidence(samples)
    return {
        "world": world,
        "seed": seed,
        "script": script,
        "pair_count": evidence["pair_count"],
        "candidates": normalized_relation_candidates(evidence),
    }


if __name__ == "__main__":
    main()
