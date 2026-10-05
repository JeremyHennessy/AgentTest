from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from open_object_world_challenge import initial_world, observe_world, transition
from open_object_world_challenge_explorer import (
    choose_command,
    command_key,
    observation_signature,
)


def _record_public(
    observation,
    *,
    positions,
    inventory_states,
    state_history,
):
    positions.add(tuple(observation["position"]))
    inventory_states.add(tuple(sorted(observation["inventory_ids"])))
    for row in observation["visible_entities"]:
        state = row.get("observable_state")
        if state is not None:
            state_history.setdefault(str(row["id"]), []).append(str(state))


def run_layout(seed: int, steps: int, roundtrip_cycle: int) -> dict:
    world = initial_world(seed)
    attempts = Counter()
    initial_position = tuple(world["position"])
    positions = set()
    inventory_states = set()
    signatures = set()
    state_history = {}
    effects = Counter()
    first_effect_cycle = {}
    first_open_cycle = {}
    first_active_cycle = {}
    first_cross_cycle = None
    first_inventory_cycle = None
    roundtrip_preserved = False

    for cycle in range(1, steps + 1):
        observation = observe_world(world)
        signatures.add(observation_signature(observation))
        _record_public(
            observation,
            positions=positions,
            inventory_states=inventory_states,
            state_history=state_history,
        )

        if observation["inventory_ids"] and first_inventory_cycle is None:
            first_inventory_cycle = cycle

        initial_side = -1 if initial_position[0] < 0 else 1
        current_side = -1 if observation["position"][0] < 0 else 1 if observation["position"][0] > 0 else 0
        if current_side == -initial_side and first_cross_cycle is None:
            first_cross_cycle = cycle

        for entity_id in ("B001", "B002"):
            states = state_history.get(entity_id, [])
            if states and states[-1] == "open":
                first_open_cycle.setdefault(entity_id, cycle)
        for entity_id in ("M001", "M002", "M003"):
            states = state_history.get(entity_id, [])
            if states and states[-1] == "active":
                first_active_cycle.setdefault(entity_id, cycle)

        if cycle == roundtrip_cycle:
            before = observe_world(world)
            world = json.loads(json.dumps(world, sort_keys=True))
            after = observe_world(world)
            if before != after:
                raise AssertionError("world JSON roundtrip changed public observation")
            roundtrip_preserved = True

        command = choose_command(observation, attempts)
        attempts[(observation_signature(observation), command_key(command))] += 1
        world, receipt = transition(world, command, cycle=cycle)
        for effect in receipt.get("observed_effects", []):
            effect = str(effect)
            effects[effect] += 1
            first_effect_cycle.setdefault(effect, cycle)

    final_observation = observe_world(world)
    signatures.add(observation_signature(final_observation))
    _record_public(
        final_observation,
        positions=positions,
        inventory_states=inventory_states,
        state_history=state_history,
    )

    entity_state_sets = {
        entity_id: sorted(set(states))
        for entity_id, states in sorted(state_history.items())
        if len(set(states)) > 1
    }
    opened = [
        entity_id
        for entity_id in ("B001", "B002")
        if "open" in set(state_history.get(entity_id, []))
    ]
    activated = [
        entity_id
        for entity_id in ("M001", "M002", "M003")
        if "active" in set(state_history.get(entity_id, []))
    ]

    return {
        "seed": seed,
        "steps": steps,
        "layout_id": int(world["layout_id"]),
        "roundtrip_preserved": roundtrip_preserved,
        "unique_observations": len(signatures),
        "unique_positions": len(positions),
        "unique_inventory_states": len(inventory_states),
        "first_inventory_cycle": first_inventory_cycle,
        "first_cross_cycle": first_cross_cycle,
        "crossed_partition": first_cross_cycle is not None,
        "opened_barriers": opened,
        "activated_mechanisms": activated,
        "first_open_cycle": first_open_cycle,
        "first_active_cycle": first_active_cycle,
        "entities_with_public_state_change": entity_state_sets,
        "observed_effect_counts": dict(sorted(effects.items())),
        "first_effect_cycle": dict(sorted(first_effect_cycle.items())),
        "final_observation": final_observation,
    }


def run_study(steps: int) -> dict:
    layouts = [
        run_layout(seed, steps, max(1, steps // 2))
        for seed in range(1, 5)
    ]
    crossed = sum(row["crossed_partition"] for row in layouts)
    any_gate = sum(bool(row["opened_barriers"]) for row in layouts)
    both_gates = sum(len(row["opened_barriers"]) == 2 for row in layouts)
    two_mechanisms = sum(len(row["activated_mechanisms"]) >= 2 for row in layouts)
    override = sum("M003" in row["activated_mechanisms"] for row in layouts)
    inventory = sum(row["first_inventory_cycle"] is not None for row in layouts)
    roundtrip = sum(row["roundtrip_preserved"] for row in layouts)

    hypothesis_supported = (
        crossed == 4
        and any_gate == 4
        and both_gates >= 3
        and two_mechanisms >= 3
        and inventory == 4
        and roundtrip == 4
    )
    return {
        "study": "open-object-world-challenge-unguided-v1",
        "policy": "least-tried-public-actions-v1",
        "steps_per_layout": steps,
        "hypothesis": (
            "Without a goal, reward, solution script, or hidden-state access, "
            "the frozen least-tried public-action explorer discovers item-mediated "
            "state changes and crosses the partition in all four spatial layouts."
        ),
        "acceptance": {
            "crossed_partition_layouts": 4,
            "opened_any_gate_layouts": 4,
            "opened_both_gates_layouts_min": 3,
            "activated_two_mechanisms_layouts_min": 3,
            "used_inventory_layouts": 4,
            "json_roundtrip_layouts": 4,
        },
        "summary": {
            "layout_count": 4,
            "crossed_partition_layouts": crossed,
            "opened_any_gate_layouts": any_gate,
            "opened_both_gates_layouts": both_gates,
            "activated_two_mechanisms_layouts": two_mechanisms,
            "override_discovered_layouts": override,
            "used_inventory_layouts": inventory,
            "json_roundtrip_layouts": roundtrip,
            "hypothesis_supported": hypothesis_supported,
        },
        "layouts": layouts,
        "authority": {
            "production_modified": False,
            "live_world_activated": False,
            "phase42_credit": False,
            "environment_action_authority": False,
            "external_model_api": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=1600)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run_study(args.steps)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(json.dumps(report["summary"], sort_keys=True))
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
