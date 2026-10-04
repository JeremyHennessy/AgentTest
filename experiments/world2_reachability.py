from __future__ import annotations

import itertools
import random
from collections import Counter
from typing import Any

from world2_ecology import (
    WORLD2_ACTIONS,
    initial_world2_state,
    transition_world2,
)


def classify_trace(initial: dict[str, Any], final: dict[str, Any]) -> set[str]:
    """Classify phenomena demonstrated by observable/action history."""

    found: set[str] = set()
    history = final.get("history", [])

    # Resource dynamics: same location observed at different values.
    local_samples: dict[str, set[int]] = {}
    for record in history:
        observation = record.get("observation") or {}
        value = observation.get("local_resource")
        position = observation.get("position")
        if value is not None and isinstance(position, list):
            key = f"{position[0]},{position[1]}"
            local_samples.setdefault(key, set()).add(int(value))
    if any(len(values) >= 2 for values in local_samples.values()):
        found.add("periodic_resource")

    # Persistent object intervention is directly observable through the action
    # outcome and later observations can show the object at its displaced site.
    displacement_cycles = [
        int(record["cycle"])
        for record in history
        if record.get("interaction_effect") == "object_displaced"
    ]
    if displacement_cycles:
        displaced_position = final["objects"]["O1"]["position"]
        if any(
            int(record["cycle"]) > displacement_cycles[0]
            and (record.get("observation") or {}).get("visible_objects")
            and (record.get("observation") or {}).get("position") == displaced_position
            for record in history
        ):
            found.add("persistent_object")

    # Slow process is observable without exposing its cause.
    slow_values = [
        int((record.get("observation") or {}).get("slow_signal", 0) or 0)
        for record in history
    ]
    if slow_values and max(slow_values) > min(slow_values):
        found.add("delayed_process")

    # Latent-condition consequence is exposed only as an anomalous interaction.
    if any(
        record.get("interaction_effect") == "local_resource_changed"
        for record in history
    ):
        found.add("latent_condition")

    return found


def run_sequence(*, seed: int, actions: tuple[str, ...]) -> dict[str, Any]:
    world = initial_world2_state(seed=seed)
    initial = world
    for cycle, action in enumerate(actions, start=1):
        world, _ = transition_world2(world, action, cycle=cycle)
    return {
        "seed": seed,
        "actions": list(actions),
        "phenomena": sorted(classify_trace(initial, world)),
        "final": world,
    }


def enumerate_reachability(
    *,
    seeds: tuple[int, ...] = (1, 2, 3),
    horizon: int = 8,
    actions: tuple[str, ...] = WORLD2_ACTIONS,
    max_sequences: int | None = 50000,
) -> dict[str, Any]:
    """Enumerate deterministic paths for reachability evidence, not intelligence."""

    phenomenon_paths: dict[str, list[dict[str, Any]]] = {}
    combination_counts: Counter[tuple[str, ...]] = Counter()
    sequence_count = 0

    for seed in seeds:
        for sequence in itertools.product(actions, repeat=horizon):
            result = run_sequence(seed=seed, actions=sequence)
            sequence_count += 1
            phenomena = tuple(result["phenomena"])
            combination_counts[phenomena] += 1
            for phenomenon in phenomena:
                examples = phenomenon_paths.setdefault(phenomenon, [])
                if len(examples) < 5:
                    examples.append(
                        {
                            "seed": seed,
                            "actions": list(sequence),
                        }
                    )
            if max_sequences is not None and sequence_count >= max_sequences:
                break
        if max_sequences is not None and sequence_count >= max_sequences:
            break

    return {
        "sequence_count": sequence_count,
        "horizon": horizon,
        "seeds": list(seeds),
        "phenomenon_path_counts": {
            phenomenon: sum(
                count
                for combination, count in combination_counts.items()
                if phenomenon in combination
            )
            for phenomenon in sorted(phenomenon_paths)
        },
        "phenomenon_examples": phenomenon_paths,
        "combination_counts": {
            "+".join(combination) if combination else "none": count
            for combination, count in sorted(combination_counts.items())
        },
    }


def sample_reachability(
    *,
    seeds: tuple[int, ...] = (1, 2, 3, 4, 5),
    horizon: int = 12,
    sample_count: int = 20000,
    sampler_seed: int = 20261004,
    actions: tuple[str, ...] = WORLD2_ACTIONS,
) -> dict[str, Any]:
    """Deterministically sample diverse paths without Ora or adaptive search."""

    rng = random.Random(int(sampler_seed))
    phenomenon_counts: Counter[str] = Counter()
    combination_counts: Counter[tuple[str, ...]] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {}

    for _ in range(sample_count):
        seed = seeds[rng.randrange(len(seeds))]
        sequence = tuple(actions[rng.randrange(len(actions))] for _ in range(horizon))
        result = run_sequence(seed=seed, actions=sequence)
        phenomena = tuple(result["phenomena"])
        combination_counts[phenomena] += 1
        for phenomenon in phenomena:
            phenomenon_counts[phenomenon] += 1
            bucket = examples.setdefault(phenomenon, [])
            if len(bucket) < 5:
                bucket.append({"seed": seed, "actions": list(sequence)})

    return {
        "sample_count": sample_count,
        "horizon": horizon,
        "seeds": list(seeds),
        "sampler_seed": int(sampler_seed),
        "phenomenon_path_counts": dict(sorted(phenomenon_counts.items())),
        "phenomenon_examples": examples,
        "combination_counts": {
            "+".join(combination) if combination else "none": count
            for combination, count in sorted(combination_counts.items())
        },
    }
