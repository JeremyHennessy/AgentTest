from __future__ import annotations

from copy import deepcopy
from typing import Any

WORLD_VERSION = "open-object-world-v0"
BOUNDS = 2
MOVE_ACTIONS = ("north", "east", "south", "west")
ACTIONS = MOVE_ACTIONS + ("inspect", "interact", "take", "drop", "push")
_MOVE = {
    "north": (1, 0),
    "east": (0, -1),
    "south": (-1, 0),
    "west": (0, 1),
}

# The layouts vary spatially while preserving the same hidden mechanics.
# None of these private fields are emitted by observe_world().
_LAYOUTS = {
    1: {
        "agent": [0, 0],
        "entities": {
            "O001": {"_kind": "object", "position": [-1, 0], "_mass": 2, "_carryable": True, "_movable": True, "appearance": "large matte form"},
            "O002": {"_kind": "object", "position": [0, 1], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small pale form"},
            "O003": {"_kind": "object", "position": [1, -1], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small dark form"},
            "M001": {"_kind": "mechanism", "position": [1, 1], "_latched": False, "appearance": "marked floor fixture"},
            "B001": {"_kind": "barrier", "position": [2, 1], "appearance": "vertical segmented structure"},
        },
    },
    2: {
        "agent": [0, 0],
        "entities": {
            "O001": {"_kind": "object", "position": [0, -1], "_mass": 2, "_carryable": True, "_movable": True, "appearance": "large matte form"},
            "O002": {"_kind": "object", "position": [-1, 0], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small pale form"},
            "O003": {"_kind": "object", "position": [1, 1], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small dark form"},
            "M001": {"_kind": "mechanism", "position": [-1, -1], "_latched": False, "appearance": "marked floor fixture"},
            "B001": {"_kind": "barrier", "position": [-2, -1], "appearance": "vertical segmented structure"},
        },
    },
    3: {
        "agent": [0, 0],
        "entities": {
            "O001": {"_kind": "object", "position": [1, 0], "_mass": 2, "_carryable": True, "_movable": True, "appearance": "large matte form"},
            "O002": {"_kind": "object", "position": [0, -1], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small pale form"},
            "O003": {"_kind": "object", "position": [-1, 1], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small dark form"},
            "M001": {"_kind": "mechanism", "position": [-1, 1], "_latched": False, "appearance": "marked floor fixture"},
            "B001": {"_kind": "barrier", "position": [-1, 2], "appearance": "vertical segmented structure"},
        },
    },
    4: {
        "agent": [0, 0],
        "entities": {
            "O001": {"_kind": "object", "position": [0, 1], "_mass": 2, "_carryable": True, "_movable": True, "appearance": "large matte form"},
            "O002": {"_kind": "object", "position": [1, 0], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small pale form"},
            "O003": {"_kind": "object", "position": [-1, -1], "_mass": 1, "_carryable": True, "_movable": True, "appearance": "small dark form"},
            "M001": {"_kind": "mechanism", "position": [1, -1], "_latched": False, "appearance": "marked floor fixture"},
            "B001": {"_kind": "barrier", "position": [2, -1], "appearance": "vertical segmented structure"},
        },
    },
}


def initial_world(seed: int = 1) -> dict[str, Any]:
    layout_id = ((int(seed) - 1) % len(_LAYOUTS)) + 1
    layout = deepcopy(_LAYOUTS[layout_id])
    return {
        "world_version": WORLD_VERSION,
        "layout_id": layout_id,
        "cycle": 0,
        "position": list(layout["agent"]),
        "inventory": [],
        "entities": layout["entities"],
        "history": [],
    }


def observe_world(state: dict[str, Any]) -> dict[str, Any]:
    _validate_state(state)
    position = list(state["position"])
    visible = []
    for entity_id, entity in sorted(state["entities"].items()):
        entity_position = entity.get("position")
        if not isinstance(entity_position, list):
            continue
        if _manhattan(position, entity_position) > 1:
            continue
        view = {
            "id": entity_id,
            "position": list(entity_position),
            "appearance": str(entity.get("appearance") or ""),
        }
        if entity.get("_kind") == "mechanism":
            view["observable_state"] = "lit" if _mechanism_active(state) else "dark"
        elif entity.get("_kind") == "barrier":
            view["observable_state"] = "open" if _barrier_open(state) else "closed"
        visible.append(view)

    return {
        "world_version": WORLD_VERSION,
        "observation_id": f"ow-{int(state['cycle']):06d}",
        "cycle": int(state["cycle"]),
        "position": position,
        "inventory_ids": list(state["inventory"]),
        "visible_entities": visible,
    }


def transition(
    state: dict[str, Any],
    command: dict[str, Any],
    *,
    cycle: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_state(state)
    if not isinstance(command, dict):
        raise ValueError("command must be a mapping")
    action = str(command.get("action") or "")
    if action not in ACTIONS:
        raise ValueError("unsupported action")

    world = deepcopy(state)
    before = list(world["position"])
    receipt = {
        "action": action,
        "target": command.get("target"),
        "direction": command.get("direction"),
        "before": before,
        "after": before,
        "success": False,
        "blocked": False,
        "observed_effects": [],
    }

    if action in MOVE_ACTIONS:
        _move_agent(world, action, receipt)
    elif action == "inspect":
        _inspect(world, command, receipt)
    elif action == "interact":
        _interact(world, command, receipt)
    elif action == "take":
        _take(world, command, receipt)
    elif action == "drop":
        _drop(world, command, receipt)
    elif action == "push":
        _push(world, command, receipt)

    world["cycle"] = int(cycle)
    receipt["after"] = list(world["position"])
    receipt["mechanism_observed_state"] = "lit" if _mechanism_active(world) else "dark"
    receipt["barrier_observed_state"] = "open" if _barrier_open(world) else "closed"
    record = {
        "id": f"OWA{len(world['history']) + 1:06d}",
        "cycle": int(cycle),
        **deepcopy(receipt),
    }
    world["history"].append(record)
    _validate_state(world)
    return world, record


def _move_agent(world: dict[str, Any], action: str, receipt: dict[str, Any]) -> None:
    dx, dy = _MOVE[action]
    target = [world["position"][0] + dx, world["position"][1] + dy]
    if not _in_bounds(target):
        receipt["blocked"] = True
        receipt["observed_effects"].append("path_blocked")
        return
    if _closed_barrier_at(world, target):
        receipt["blocked"] = True
        receipt["observed_effects"].append("path_blocked")
        return
    if _solid_object_at(world, target):
        receipt["blocked"] = True
        receipt["observed_effects"].append("path_blocked")
        return
    world["position"] = target
    receipt["success"] = True
    receipt["observed_effects"].append("position_changed")


def _inspect(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target = _target_entity(world, command.get("target"), max_distance=1)
    if target is None:
        receipt["observed_effects"].append("target_not_observable")
        return
    entity_id, entity = target
    receipt["success"] = True
    receipt["observed_effects"].append("target_observed")
    receipt["inspection"] = {
        "id": entity_id,
        "position": list(entity["position"]),
        "appearance": str(entity.get("appearance") or ""),
        "observable_state": (
            "lit" if entity.get("_kind") == "mechanism" and _mechanism_active(world)
            else "dark" if entity.get("_kind") == "mechanism"
            else "open" if entity.get("_kind") == "barrier" and _barrier_open(world)
            else "closed" if entity.get("_kind") == "barrier"
            else None
        ),
    }


def _interact(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target = _target_entity(world, command.get("target"), max_distance=1)
    if target is None:
        receipt["observed_effects"].append("target_not_observable")
        return
    _, entity = target
    if entity.get("_kind") != "mechanism":
        receipt["success"] = True
        receipt["observed_effects"].append("no_observed_change")
        return
    before = _mechanism_active(world)
    entity["_latched"] = not bool(entity.get("_latched"))
    after = _mechanism_active(world)
    receipt["success"] = True
    receipt["observed_effects"].append(
        "target_state_changed" if before != after else "no_observed_change"
    )


def _take(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target_id = str(command.get("target") or "")
    entity = world["entities"].get(target_id)
    if (
        not isinstance(entity, dict)
        or entity.get("position") != world["position"]
        or not bool(entity.get("_carryable"))
    ):
        receipt["observed_effects"].append("target_unavailable")
        return
    entity["position"] = None
    world["inventory"].append(target_id)
    receipt["success"] = True
    receipt["observed_effects"].append("inventory_changed")


def _drop(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target_id = str(command.get("target") or "")
    if target_id not in world["inventory"]:
        receipt["observed_effects"].append("target_unavailable")
        return
    world["inventory"].remove(target_id)
    world["entities"][target_id]["position"] = list(world["position"])
    receipt["success"] = True
    receipt["observed_effects"].append("inventory_changed")
    receipt["observed_effects"].append("target_position_changed")


def _push(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target_id = str(command.get("target") or "")
    direction = str(command.get("direction") or "")
    entity = world["entities"].get(target_id)
    if direction not in MOVE_ACTIONS or not isinstance(entity, dict) or not bool(entity.get("_movable")):
        receipt["observed_effects"].append("target_unavailable")
        return
    entity_position = entity.get("position")
    if not isinstance(entity_position, list):
        receipt["observed_effects"].append("target_unavailable")
        return
    dx, dy = _MOVE[direction]
    expected = [world["position"][0] + dx, world["position"][1] + dy]
    if entity_position != expected:
        receipt["observed_effects"].append("target_unavailable")
        return
    destination = [entity_position[0] + dx, entity_position[1] + dy]
    if (
        not _in_bounds(destination)
        or _closed_barrier_at(world, destination)
        or _solid_object_at(world, destination, exclude=target_id)
    ):
        receipt["blocked"] = True
        receipt["observed_effects"].append("target_movement_blocked")
        return
    entity["position"] = destination
    world["position"] = entity_position
    receipt["success"] = True
    receipt["observed_effects"].append("position_changed")
    receipt["observed_effects"].append("target_position_changed")


def _mechanism_active(world: dict[str, Any]) -> bool:
    mechanism = next(
        entity for entity in world["entities"].values()
        if entity.get("_kind") == "mechanism"
    )
    if bool(mechanism.get("_latched")):
        return True
    position = mechanism.get("position")
    total_mass = 0
    for entity in world["entities"].values():
        if (
            entity.get("_kind") == "object"
            and entity.get("position") == position
        ):
            total_mass += int(entity.get("_mass", 0) or 0)
    return total_mass >= 2


def _barrier_open(world: dict[str, Any]) -> bool:
    return _mechanism_active(world)


def _closed_barrier_at(world: dict[str, Any], position: list[int]) -> bool:
    return any(
        entity.get("_kind") == "barrier"
        and entity.get("position") == position
        and not _barrier_open(world)
        for entity in world["entities"].values()
    )


def _solid_object_at(
    world: dict[str, Any],
    position: list[int],
    *,
    exclude: str | None = None,
) -> bool:
    return any(
        entity_id != exclude
        and entity.get("_kind") == "object"
        and entity.get("position") == position
        for entity_id, entity in world["entities"].items()
    )


def _target_entity(
    world: dict[str, Any],
    target_id: Any,
    *,
    max_distance: int,
) -> tuple[str, dict[str, Any]] | None:
    target = str(target_id or "")
    entity = world["entities"].get(target)
    if not isinstance(entity, dict):
        return None
    position = entity.get("position")
    if not isinstance(position, list):
        return None
    if _manhattan(world["position"], position) > max_distance:
        return None
    return target, entity


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("world_version") != WORLD_VERSION:
        raise ValueError("unsupported open object world version")
    position = state.get("position")
    if not isinstance(position, list) or len(position) != 2 or not _in_bounds(position):
        raise ValueError("invalid agent position")
    if not isinstance(state.get("inventory"), list):
        raise ValueError("invalid inventory")
    entities = state.get("entities")
    if not isinstance(entities, dict):
        raise ValueError("invalid entities")
    for entity_id, entity in entities.items():
        if not isinstance(entity_id, str) or not isinstance(entity, dict):
            raise ValueError("invalid entity")
        entity_position = entity.get("position")
        if entity_position is not None and (
            not isinstance(entity_position, list)
            or len(entity_position) != 2
            or not _in_bounds(entity_position)
        ):
            raise ValueError("invalid entity position")


def _in_bounds(position: list[int] | tuple[int, int]) -> bool:
    return all(-BOUNDS <= int(value) <= BOUNDS for value in position)


def _manhattan(left: list[int], right: list[int]) -> int:
    return abs(int(left[0]) - int(right[0])) + abs(int(left[1]) - int(right[1]))
