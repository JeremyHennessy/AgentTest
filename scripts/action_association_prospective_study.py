from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from action_association_semantics import compare_prefix_to_suffix
from normalized_relation_evidence import normalized_evidence, normalized_relation_candidates
from world2_ecology import initial_world2_state, observe_world2, transition_world2
from world2_native_observation import native_world2_observation
from world3_ecology import initial_world3_state, observe_world3, transition_world3
from world3_native_observation import native_world3_observation
from world4_toggle_ecology import initial_world4_state, observe_world4, transition_world4
from world4_native_observation import native_world4_observation

WORLD2 = (
    ("north_interact", ("north", "interact", "observe", "south", "observe", "north", "observe", "observe")),
    ("mixed", ("south", "observe", "north", "north", "interact", "observe", "south", "observe", "observe")),
)
WORLD3 = (
    ("object_a", ("north", "west", "interact", "observe", "south", "east", "observe", "observe")),
    ("object_b", ("south", "east", "interact", "observe", "north", "west", "observe", "observe")),
)
WORLD4 = (
    ("north_probe", ("north", "interact", "observe", "south", "observe", "north", "interact", "observe")),
    ("east_probe", ("east", "interact", "observe", "west", "observe", "east", "interact", "observe")),
    ("south_probe", ("south", "interact", "observe", "north", "observe", "south", "interact", "observe")),
    ("west_probe", ("west", "interact", "observe", "east", "observe", "west", "interact", "observe")),
)


def main() -> None:
    trajectories = []
    for seed in range(1, 6):
        for script, actions in WORLD2:
            trajectories.append(("world2", seed, script, samples_w2(seed, actions)))
    for seed in range(1, 5):
        for script, actions in WORLD3:
            trajectories.append(("world3", seed, script, samples_w3(seed, actions)))
    for seed in range(1, 5):
        for script, actions in WORLD4:
            trajectories.append(("world4", seed, script, samples_w4(seed, actions)))

    rows = []
    statuses = Counter()
    selected = 0
    for world, seed, script, samples in trajectories:
        split = max(3, len(samples) // 2)
        prefix = samples[:split]
        suffix = samples[split - 1 :]
        prefix_candidates = association_candidates(prefix)
        suffix_candidates = association_candidates(suffix)
        if not prefix_candidates:
            rows.append({
                "world": world, "seed": seed, "script": script,
                "status": "no_prefix_association",
            })
            statuses["no_prefix_association"] += 1
            continue
        prefix_candidate = choose_prefix(prefix_candidates)
        suffix_match = next(
            (
                item for item in suffix_candidates
                if key(item) == key(prefix_candidate)
            ),
            None,
        )
        outcome = compare_prefix_to_suffix(prefix_candidate, suffix_match)
        statuses[outcome["status"]] += 1
        selected += 1
        rows.append({
            "world": world,
            "seed": seed,
            "script": script,
            "selected": key(prefix_candidate),
            "outcome": outcome,
        })

    report = {
        "study": "action-association-prospective-semantics-v1",
        "trajectory_count": len(trajectories),
        "selected_prefix_association_count": selected,
        "status_counts": dict(sorted(statuses.items())),
        "rows": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def association_candidates(samples):
    return [
        item for item in normalized_relation_candidates(normalized_evidence(samples))
        if item["relation"] == "action_associated_with_change"
        and item["status"] != "insufficient_comparison"
    ]


def choose_prefix(items):
    # Frozen, truth-blind rule: prefer larger observed absolute rate difference,
    # then more exposure, then stable candidate ID.
    return sorted(
        items,
        key=lambda item: (
            -abs(float(item.get("effect_difference") or 0.0)),
            -int(item.get("evaluable") or 0),
            item["id"],
        ),
    )[0]


def key(item):
    return (
        item["relation"],
        item["feature"],
        item.get("action"),
    )


def samples_w2(seed, actions):
    world = initial_world2_state(seed=seed)
    samples = [native_world2_observation(observe_world2(world))]
    for cycle, action in enumerate(actions, 1):
        world, receipt = transition_world2(world, action, cycle=cycle)
        samples.append(native_world2_observation(observe_world2(world), action_receipt=receipt))
    return samples


def samples_w3(seed, actions):
    world = initial_world3_state(seed=seed)
    samples = [native_world3_observation(observe_world3(world))]
    for cycle, action in enumerate(actions, 1):
        world, receipt = transition_world3(world, action, cycle=cycle)
        samples.append(native_world3_observation(observe_world3(world), action_receipt=receipt))
    return samples


def samples_w4(seed, actions):
    world = initial_world4_state(seed=seed)
    samples = [native_world4_observation(observe_world4(world))]
    for cycle, action in enumerate(actions, 1):
        world, receipt = transition_world4(world, action, cycle=cycle)
        samples.append(native_world4_observation(observe_world4(world), action_receipt=receipt))
    return samples


if __name__ == "__main__":
    main()
