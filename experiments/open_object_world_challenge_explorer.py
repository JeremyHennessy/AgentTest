from __future__ import annotations

from collections import Counter
from typing import Any

from open_object_world_challenge import MOVE_ACTIONS

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
            str(item.get("appearance") or ""),
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
    if not candidates:
        raise ValueError("no public commands available")
    return min(
        candidates,
        key=lambda command: (
            attempt_counts[(signature, command_key(command))],
            GENERIC_ACTION_ORDER.index(str(command["action"])),
            command_key(command),
        ),
    )
