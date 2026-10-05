from __future__ import annotations

from collections import Counter
from typing import Any

from open_object_world import MOVE_ACTIONS, initial_world, observe_world, transition

GENERIC_ACTION_ORDER = (
    "north",
    "east",
    "south",
    "west",
    "inspect",
    "interact",
    "take",
    "push",
    "drop",
)


def observation_signature(observation: dict[str, Any]) -> tuple[Any, ...]:
    visible = tuple(
        (
            str(item.get("id") or ""),
            tuple(item.get("position") or []),
            item.get("observable_state"),
        )
        for item in observation.get("visible_entities", [])
    )
    return (
        tuple(observation.get("position") or []),
        tuple(sorted(observation.get("inventory_ids") or [])),
        visible,
    )


def candidate_commands(observation: dict[str, Any]) -> list[dict[str, Any]]:
    commands = [{"action": action} for action in MOVE_ACTIONS]
    visible_ids = [
        str(item.get("id") or "")
        for item in observation.get("visible_entities", [])
        if item.get("id")
    ]
    for entity_id in visible_ids:
        commands.extend(
            [
                {"action": "inspect", "target": entity_id},
                {"action": "interact", "target": entity_id},
                {"action": "take", "target": entity_id},
            ]
        )
        for direction in MOVE_ACTIONS:
            commands.append(
                {
                    "action": "push",
                    "target": entity_id,
                    "direction": direction,
                }
            )
    for entity_id in sorted(observation.get("inventory_ids") or []):
        commands.append({"action": "drop", "target": entity_id})
    return commands


def command_key(command: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(command.get("action") or ""),
        str(command.get("target") or ""),
        str(command.get("direction") or ""),
    )


def choose_command(
    observation: dict[str, Any],
    attempt_counts: Counter[tuple[Any, ...]],
) -> dict[str, Any]:
    signature = observation_signature(observation)
    candidates = candidate_commands(observation)
    return min(
        candidates,
        key=lambda command: (
            attempt_counts[(signature, command_key(command))],
            GENERIC_ACTION_ORDER.index(str(command["action"])),
            command_key(command),
        ),
    )


def run_unguided(seed: int, steps: int = 200) -> dict[str, Any]:
    world = initial_world(seed=seed)
    attempts: Counter[tuple[Any, ...]] = Counter()
    observation_signatures = set()
    positions = set()
    inventory_states = set()
    effect_counts: Counter[str] = Counter()
    visible_state_history: dict[str, list[str]] = {}

    for cycle in range(1, steps + 1):
        observation = observe_world(world)
        signature = observation_signature(observation)
        observation_signatures.add(signature)
        positions.add(tuple(observation["position"]))
        inventory_states.add(tuple(sorted(observation["inventory_ids"])))
        for item in observation["visible_entities"]:
            state = item.get("observable_state")
            if state is not None:
                visible_state_history.setdefault(str(item["id"]), []).append(
                    str(state)
                )

        command = choose_command(observation, attempts)
        attempts[(signature, command_key(command))] += 1
        world, receipt = transition(world, command, cycle=cycle)
        for effect in receipt.get("observed_effects", []):
            effect_counts[str(effect)] += 1

    final_observation = observe_world(world)
    observation_signatures.add(observation_signature(final_observation))
    positions.add(tuple(final_observation["position"]))
    inventory_states.add(tuple(sorted(final_observation["inventory_ids"])))
    for item in final_observation["visible_entities"]:
        state = item.get("observable_state")
        if state is not None:
            visible_state_history.setdefault(str(item["id"]), []).append(
                str(state)
            )

    state_changes = {
        entity_id: sorted(set(states))
        for entity_id, states in visible_state_history.items()
        if len(set(states)) > 1
    }
    return {
        "seed": int(seed),
        "steps": int(steps),
        "unique_observation_count": len(observation_signatures),
        "unique_position_count": len(positions),
        "unique_inventory_state_count": len(inventory_states),
        "observed_effect_counts": dict(sorted(effect_counts.items())),
        "entities_with_multiple_observed_states": state_changes,
        "final_observation": final_observation,
    }
