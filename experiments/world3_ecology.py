from __future__ import annotations

from copy import deepcopy
from typing import Any

WORLD3_VERSION = "transfer-ecology-v0"
WORLD3_BOUNDS = 2
WORLD3_ACTIONS = ("north", "east", "south", "west", "interact", "observe")
_MOVE = {
    "north": (1, 0),
    "east": (0, -1),
    "south": (-1, 0),
    "west": (0, 1),
}


def initial_world3_state(seed: int = 1) -> dict[str, Any]:
    """Independent transfer world: local cue fields and consumable objects, no delayed broadcast."""
    phase = abs(int(seed)) % 4
    return {
        "world_version": WORLD3_VERSION,
        "cycle": 0,
        "position": [0, 0],
        "objects": {
            "A": {"position": [1, 1], "present": True},
            "B": {"position": [-1, -1], "present": True},
        },
        "cue_sites": {"0,1": 1, "1,-1": 2, "-1,0": 3},
        "phase": phase,
        "interactions": 0,
    }


def observe_world3(state: dict[str, Any]) -> dict[str, Any]:
    position = list(state["position"])
    visible = sorted(
        object_id
        for object_id, record in state["objects"].items()
        if record["present"] and record["position"] == position
    )
    key = f"{position[0]},{position[1]}"
    cue = state["cue_sites"].get(key)
    return {
        "world_version": WORLD3_VERSION,
        "cycle": int(state["cycle"]),
        "position": position,
        "visible_objects": visible,
        "local_cue": cue,
    }


def transition_world3(
    state: dict[str, Any], action: str, *, cycle: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    if action not in WORLD3_ACTIONS:
        raise ValueError("unsupported World 3 action")
    world = deepcopy(state)
    before = list(world["position"])
    blocked = False
    effect = None

    if action in _MOVE:
        dx, dy = _MOVE[action]
        target = [before[0] + dx, before[1] + dy]
        if any(abs(value) > WORLD3_BOUNDS for value in target):
            blocked = True
        else:
            world["position"] = target
    elif action == "interact":
        visible = [
            item
            for item in world["objects"].values()
            if item["present"] and item["position"] == before
        ]
        if visible:
            visible[0]["present"] = False
            world["interactions"] += 1
            effect = "object_consumed"
        else:
            effect = "no_visible_target"

    # Local cues drift on a seed-dependent cadence independent of object interaction.
    phase = int(world["phase"])
    for index, key in enumerate(sorted(world["cue_sites"])):
        if (cycle + phase + index) % 4 == 0:
            world["cue_sites"][key] = (int(world["cue_sites"][key]) + 1) % 5

    world["cycle"] = int(cycle)
    return world, {
        "action": action,
        "before": before,
        "after": list(world["position"]),
        "blocked": blocked,
        "interaction_effect": effect,
    }
