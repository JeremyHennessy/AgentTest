from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.state import initial_state
from native_relation_discovery import RELATION_VERSION, evaluate_relations, propose_relations
from native_relation_family_memory import FAMILY_MEMORY_KEY, rank_held_out_proposals, update_family_memory
from world2_ecology import initial_world2_state, observe_world2, transition_world2
from world2_native_observation import native_world2_observation
from world3_ecology import initial_world3_state, observe_world3, transition_world3
from world3_native_observation import native_world3_observation

HELD_OUT = [
    {"id": "H1", "version": RELATION_VERSION, "relation": "action_precedes_change", "feature": "novel_signal", "action": "interact"},
    {"id": "H2", "version": RELATION_VERSION, "relation": "same_next_observation", "feature": "novel_signal", "action": None},
    {"id": "H3", "version": RELATION_VERSION, "relation": "changes_next_observation", "feature": "novel_signal", "action": None},
]

WORLD2_SCRIPTS = (
    ("observe_short", ("observe",) * 4),
    ("observe_long", ("observe",) * 12),
    ("object_probe", ("north", "interact", "observe", "south", "north", "observe")),
    ("resource_probe", ("south", "observe", "observe", "observe", "observe", "observe")),
    ("mixed", ("north", "interact", "south", "south", "observe", "north", "observe", "observe")),
)
WORLD3_SCRIPTS = (
    ("observe_short", ("observe",) * 4),
    ("observe_long", ("observe",) * 12),
    ("object_a", ("north", "west", "interact", "observe", "observe")),
    ("object_b", ("south", "east", "interact", "observe", "observe")),
    ("mixed", ("west", "observe", "north", "observe", "south", "east", "observe", "observe")),
)


def main() -> None:
    results = []
    for seed in range(1, 6):
        for name, actions in WORLD2_SCRIPTS:
            results.append(run_world2(seed, name, actions))
    for seed in range(1, 5):
        for name, actions in WORLD3_SCRIPTS:
            results.append(run_world3(seed, name, actions))
    counts = Counter(item["selected_relation"] for item in results)
    report = {
        "study": "natural-relation-diversity-sweep-v1",
        "scoring_rule": "frozen-native-relation-family-memory-v0",
        "held_out_feature": "novel_signal",
        "trajectory_count": len(results),
        "winner_counts": dict(sorted(counts.items())),
        "distinct_winners": sorted(counts),
        "crossed_selection_boundary": len(counts) > 1,
        "results": results,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def run_world2(seed: int, name: str, actions: tuple[str, ...]) -> dict:
    world = initial_world2_state(seed=seed)
    samples = [native_world2_observation(observe_world2(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world2(world, action, cycle=cycle)
        samples.append(native_world2_observation(observe_world2(world), action_receipt=record))
    return summarize("world2", seed, name, samples)


def run_world3(seed: int, name: str, actions: tuple[str, ...]) -> dict:
    world = initial_world3_state(seed=seed)
    samples = [native_world3_observation(observe_world3(world))]
    for cycle, action in enumerate(actions, start=1):
        world, record = transition_world3(world, action, cycle=cycle)
        samples.append(native_world3_observation(observe_world3(world), action_receipt=record))
    return summarize("world3", seed, name, samples)


def summarize(world_name: str, seed: int, name: str, samples: list[dict]) -> dict:
    state = initial_state()
    ledger = evaluate_relations(propose_relations(samples), samples)
    update_family_memory(state, ledger)
    ranked = rank_held_out_proposals(state, HELD_OUT)
    return {
        "world": world_name,
        "seed": seed,
        "script": name,
        "sample_count": len(samples),
        "selected_id": ranked[0]["proposal"]["id"],
        "selected_relation": ranked[0]["proposal"]["relation"],
        "selected_score": ranked[0]["score"],
        "scores": {item["proposal"]["id"]: item["score"] for item in ranked},
        "family_memory": state[FAMILY_MEMORY_KEY]["families"],
    }


if __name__ == "__main__":
    main()
