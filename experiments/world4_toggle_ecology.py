from __future__ import annotations

from copy import deepcopy
from typing import Any

WORLD4_VERSION = "toggle-ecology-v0"
WORLD4_BOUNDS = 2
WORLD4_ACTIONS = ("north", "east", "south", "west", "interact", "observe")
_MOVE = {
    "north": (1, 0),
    "east": (0, -1),
    "south": (-1, 0),
    "west": (0, 1),
}
_LEVER_POSITIONS = (
    [1, 0],
    [0, -1],
    [-1, 0],
    [0, 1],
)


def initial_world4_state(seed: int = 1) -> dict[str, Any]:
    index = abs(int(seed)) % len(_LEVER_POSITIONS)
    return {
        "world_version": WORLD4_VERSION,
        "cycle": 0,
        "position": [0, 0],
        "lever_position": list(_LEVER_POSITIONS[index]),
        "signal_mode": abs(int(seed)) % 2,
        "interaction_count": 0,
    }


def observe_world4(state: dict[str, Any]) -> dict[str, Any]:
    position = list(state["position"])
    visible = ["lever"] if position == state["lever_position"] else []
    return {
        "world_version": WORLD4_VERSION,
        "cycle": int(state["cycle"]),
        "position": position,
        "visible_objects": visible,
        "slow_signal": int(state["signal_mode"]),
    }


def transition_world4(
    state: dict[str, Any], action: str, *, cycle: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    if action not in WORLD4_ACTIONS:
        raise ValueError("unsupported World 4 action")
    world = deepcopy(state)
    before = list(world["position"])
    blocked = False
    effect = None

    if action in _MOVE:
        dx, dy = _MOVE[action]
        target = [before[0] + dx, before[1] + dy]
        if any(abs(value) > WORLD4_BOUNDS for value in target):
            blocked = True
        else:
            world["position"] = target
    elif action == "interact":
        if before == world["lever_position"]:
            world["signal_mode"] = 1 - int(world["signal_mode"])
            world["interaction_count"] += 1
            effect = "signal_toggled"
        else:
            effect = "no_visible_target"

    world["cycle"] = int(cycle)
    return world, {
        "action": action,
        "before": before,
        "after": list(world["position"]),
        "blocked": blocked,
        "interaction_effect": effect,
    }
