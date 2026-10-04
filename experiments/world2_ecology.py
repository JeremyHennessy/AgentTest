from __future__ import annotations

from copy import deepcopy
from typing import Any

WORLD2_VERSION = "causal-ecology-v0"
WORLD2_BOUNDS = 2
WORLD2_ACTIONS = ("north", "east", "south", "west", "interact", "observe")

_DELTAS = {
    "north": (1, 0),
    "east": (0, -1),
    "south": (-1, 0),
    "west": (0, 1),
}


def initial_world2_state(*, seed: int = 1) -> dict[str, Any]:
    """Create deterministic isolated ecology state. Not connected to AgentCore."""

    phase = abs(int(seed)) % 5
    return {
        "version": WORLD2_VERSION,
        "seed": int(seed),
        "cycle": 0,
        "position": [0, 0],
        "objects": {
            "O1": {"position": [1, 0], "moved": False},
        },
        "resources": {
            "-1,0": 2,
            "0,1": 1,
            "1,1": 3,
        },
        "resource_phase": phase,
        "latent_mode": 0,
        "slow_process": 0,
        "pending_slow_effects": [],
        "history": [],
    }


def _in_bounds(position: tuple[int, int]) -> bool:
    return all(-WORLD2_BOUNDS <= value <= WORLD2_BOUNDS for value in position)


def _key(position: list[int] | tuple[int, int]) -> str:
    return f"{int(position[0])},{int(position[1])}"


def _advance_background(world: dict[str, Any], cycle: int) -> None:
    # Periodic local resource field. Values are bounded and phase-shifted by seed.
    phase = int(world.get("resource_phase", 0) or 0)
    for index, key in enumerate(sorted(world["resources"])):
        period = 3 + index
        if (cycle + phase + index) % period == 0:
            world["resources"][key] = (int(world["resources"][key]) + 1) % 5

    # Deterministic latent mode transition. The label is never exposed by observe().
    object_position = world["objects"]["O1"]["position"]
    if cycle > 0 and cycle % 11 == 0 and object_position[0] != 1:
        world["latent_mode"] = 1 - int(world["latent_mode"])

    # Delayed effects mature independently of attention.
    remaining = []
    for effect in world.get("pending_slow_effects", []):
        if int(effect["matures_cycle"]) <= cycle:
            world["slow_process"] = max(
                0, min(9, int(world["slow_process"]) + int(effect["delta"]))
            )
        else:
            remaining.append(effect)
    world["pending_slow_effects"] = remaining


def observe_world2(world: dict[str, Any]) -> dict[str, Any]:
    """Return bounded local observables only; hidden configuration is omitted."""

    position = list(world["position"])
    key = _key(position)
    visible_objects = sorted(
        object_id
        for object_id, record in world["objects"].items()
        if record.get("position") == position
    )
    observation = {
        "world_version": WORLD2_VERSION,
        "cycle": int(world["cycle"]),
        "position": position,
        "visible_objects": visible_objects,
        "local_resource": (
            int(world["resources"][key])
            if key in world["resources"]
            else None
        ),
        "slow_signal": int(world["slow_process"]),
    }
    return observation


def transition_world2(
    world: dict[str, Any],
    action: str,
    *,
    cycle: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pure deterministic transition for isolated simulation."""

    if action not in WORLD2_ACTIONS:
        raise ValueError(f"unsupported World 2 action: {action}")
    if int(cycle) <= int(world.get("cycle", 0) or 0):
        raise ValueError("World 2 cycle must increase")

    next_world = deepcopy(world)
    next_world["cycle"] = int(cycle)
    _advance_background(next_world, int(cycle))

    before = list(next_world["position"])
    outcome: dict[str, Any] = {
        "action": action,
        "before": before,
        "after": before,
        "blocked": False,
        "interaction_effect": None,
    }

    if action in _DELTAS:
        delta = _DELTAS[action]
        proposed = (before[0] + delta[0], before[1] + delta[1])
        if _in_bounds(proposed):
            next_world["position"] = [proposed[0], proposed[1]]
            outcome["after"] = list(next_world["position"])
        else:
            outcome["blocked"] = True
    elif action == "interact":
        obj = next_world["objects"]["O1"]
        if obj["position"] == before:
            # Move the object one cell west when possible. This is persistent.
            proposed = (before[0], before[1] + 1)
            if _in_bounds(proposed):
                obj["position"] = [proposed[0], proposed[1]]
                obj["moved"] = True
                outcome["interaction_effect"] = "object_displaced"
                # Delayed consequence: the slow signal changes later, not now.
                next_world["pending_slow_effects"].append(
                    {"matures_cycle": int(cycle) + 4, "delta": 2}
                )
        else:
            outcome["interaction_effect"] = "no_visible_target"
    else:
        # observe has no direct intervention; background processes already advanced.
        outcome["interaction_effect"] = "observation_only"

    # Latent condition changes a familiar interaction consequence without exposing
    # the hidden mode itself.
    if (
        action == "interact"
        and int(next_world["latent_mode"]) == 1
        and outcome["interaction_effect"] == "no_visible_target"
    ):
        key = _key(before)
        if key in next_world["resources"]:
            next_world["resources"][key] = max(
                0, int(next_world["resources"][key]) - 1
            )
            outcome["interaction_effect"] = "local_resource_changed"

    observation = observe_world2(next_world)
    record = {
        "cycle": int(cycle),
        **outcome,
        "observation": deepcopy(observation),
    }
    next_world["history"].append(record)
    return next_world, record


def replay_world2(*, seed: int, actions: list[str]) -> dict[str, Any]:
    world = initial_world2_state(seed=seed)
    for cycle, action in enumerate(actions, start=1):
        world, _ = transition_world2(world, action, cycle=cycle)
    return world
