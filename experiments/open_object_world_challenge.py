from __future__ import annotations

from copy import deepcopy
from typing import Any

WORLD_VERSION = "open-object-world-challenge-v1"
BOUNDS = 2
MOVE_ACTIONS = ("north", "east", "south", "west")
ACTIONS = MOVE_ACTIONS + ("inspect", "interact", "take", "drop", "push")
_MOVE = {
    "north": (1, 0),
    "east": (0, -1),
    "south": (-1, 0),
    "west": (0, 1),
}

_BASE = {
    "agent": [-2, 0],
    "entities": {
        "O001": {
            "_kind": "object",
            "position": [-2, -2],
            "_mass": 2,
            "_carryable": True,
            "_movable": True,
            "appearance": "large matte form",
        },
        "O002": {
            "_kind": "object",
            "position": [-2, -1],
            "_mass": 1,
            "_carryable": True,
            "_movable": True,
            "appearance": "small pale form",
        },
        "O003": {
            "_kind": "object",
            "position": [-2, 2],
            "_mass": 1,
            "_carryable": True,
            "_movable": True,
            "appearance": "small dark grooved form",
        },
        "O004": {
            "_kind": "object",
            "position": [2, 2],
            "_mass": 2,
            "_carryable": True,
            "_movable": True,
            "appearance": "hollow bright form",
        },
        "M001": {
            "_kind": "pressure",
            "position": [-1, -1],
            "appearance": "shallow marked floor plate",
        },
        "M002": {
            "_kind": "socket",
            "position": [-1, 2],
            "_latched": False,
            "_required_object": "O003",
            "appearance": "recessed slotted fixture",
        },
        "M003": {
            "_kind": "override",
            "position": [2, 0],
            "_latched": False,
            "appearance": "unmarked pivot fixture",
        },
        "B001": {
            "_kind": "barrier",
            "_gate": "pressure",
            "position": [0, -1],
            "appearance": "segmented gate",
        },
        "B002": {
            "_kind": "barrier",
            "_gate": "socket",
            "position": [0, 1],
            "appearance": "segmented gate",
        },
        "W001": {
            "_kind": "wall",
            "position": [0, -2],
            "appearance": "continuous dark partition",
        },
        "W002": {
            "_kind": "wall",
            "position": [0, 0],
            "appearance": "continuous dark partition",
        },
        "W003": {
            "_kind": "wall",
            "position": [0, 2],
            "appearance": "continuous dark partition",
        },
    },
}

_TRANSFORMS = {
    1: lambda p: [p[0], p[1]],
    2: lambda p: [p[0], -p[1]],
    3: lambda p: [-p[0], p[1]],
    4: lambda p: [-p[0], -p[1]],
}


def initial_world(seed: int = 1) -> dict[str, Any]:
    layout_id = ((int(seed) - 1) % 4) + 1
    transform = _TRANSFORMS[layout_id]
    base = deepcopy(_BASE)
    entities = {}
    for entity_id, entity in base["entities"].items():
        row = deepcopy(entity)
        row["position"] = transform(row["position"])
        entities[entity_id] = row
    return {
        "world_version": WORLD_VERSION,
        "layout_id": layout_id,
        "cycle": 0,
        "position": transform(base["agent"]),
        "inventory": [],
        "entities": entities,
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
        kind = entity.get("_kind")
        if kind in {"pressure", "socket", "override"}:
            view["observable_state"] = _mechanism_state(state, kind)
        elif kind == "barrier":
            view["observable_state"] = (
                "open" if _barrier_open(state, entity) else "closed"
            )
        visible.append(view)

    return {
        "world_version": WORLD_VERSION,
        "observation_id": f"owc-{int(state['cycle']):06d}",
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
    before_public = _public_state_map(observe_world(world))
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
    after_public = _public_state_map(observe_world(world))
    if any(
        before_public.get(key) != value
        for key, value in after_public.items()
        if key in before_public
    ):
        if "public_state_changed" not in receipt["observed_effects"]:
            receipt["observed_effects"].append("public_state_changed")
    receipt["visible_entity_states"] = after_public
    record = {
        "id": f"OWC-A{len(world['history']) + 1:06d}",
        "cycle": int(cycle),
        **deepcopy(receipt),
    }
    world["history"].append(record)
    _validate_state(world)
    return world, record


def _move_agent(world: dict[str, Any], action: str, receipt: dict[str, Any]) -> None:
    dx, dy = _MOVE[action]
    target = [world["position"][0] + dx, world["position"][1] + dy]
    if (
        not _in_bounds(target)
        or _closed_barrier_at(world, target)
        or _solid_entity_at(world, target)
    ):
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
    view = {
        "id": entity_id,
        "position": list(entity["position"]),
        "appearance": str(entity.get("appearance") or ""),
    }
    kind = entity.get("_kind")
    if kind in {"pressure", "socket", "override"}:
        view["observable_state"] = _mechanism_state(world, kind)
    elif kind == "barrier":
        view["observable_state"] = (
            "open" if _barrier_open(world, entity) else "closed"
        )
    receipt["inspection"] = view


def _interact(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target = _target_entity(world, command.get("target"), max_distance=1)
    if target is None:
        receipt["observed_effects"].append("target_not_observable")
        return
    _, entity = target
    kind = entity.get("_kind")
    before = _mechanism_state(world, kind) if kind in {"pressure", "socket", "override"} else None

    if kind == "socket":
        required = str(entity.get("_required_object") or "")
        if required in world["inventory"]:
            entity["_latched"] = not bool(entity.get("_latched"))
            receipt["success"] = True
        else:
            receipt["success"] = True
            receipt["observed_effects"].append("no_observed_change")
    elif kind == "override":
        entity["_latched"] = not bool(entity.get("_latched"))
        receipt["success"] = True
    elif kind == "pressure":
        receipt["success"] = True
        receipt["observed_effects"].append("no_observed_change")
    else:
        receipt["success"] = True
        receipt["observed_effects"].append("no_observed_change")

    after = _mechanism_state(world, kind) if kind in {"pressure", "socket", "override"} else None
    if before is not None and after != before:
        receipt["observed_effects"].append("target_state_changed")


def _take(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target_id = str(command.get("target") or "")
    entity = world["entities"].get(target_id)
    position = entity.get("position") if isinstance(entity, dict) else None
    if (
        not isinstance(entity, dict)
        or entity.get("_kind") != "object"
        or not isinstance(position, list)
        or _manhattan(world["position"], position) > 1
        or not bool(entity.get("_carryable"))
    ):
        receipt["observed_effects"].append("target_unavailable")
        return
    entity["position"] = None
    if target_id not in world["inventory"]:
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
    receipt["observed_effects"].extend(
        ["inventory_changed", "target_position_changed"]
    )


def _push(world: dict[str, Any], command: dict[str, Any], receipt: dict[str, Any]) -> None:
    target_id = str(command.get("target") or "")
    direction = str(command.get("direction") or "")
    entity = world["entities"].get(target_id)
    if (
        direction not in MOVE_ACTIONS
        or not isinstance(entity, dict)
        or entity.get("_kind") != "object"
        or not bool(entity.get("_movable"))
    ):
        receipt["observed_effects"].append("target_unavailable")
        return
    position = entity.get("position")
    if not isinstance(position, list):
        receipt["observed_effects"].append("target_unavailable")
        return
    dx, dy = _MOVE[direction]
    expected = [world["position"][0] + dx, world["position"][1] + dy]
    if position != expected:
        receipt["observed_effects"].append("target_unavailable")
        return
    destination = [position[0] + dx, position[1] + dy]
    if (
        not _in_bounds(destination)
        or _closed_barrier_at(world, destination)
        or _solid_entity_at(world, destination, exclude=target_id)
    ):
        receipt["blocked"] = True
        receipt["observed_effects"].append("target_movement_blocked")
        return
    entity["position"] = destination
    world["position"] = position
    receipt["success"] = True
    receipt["observed_effects"].extend(
        ["position_changed", "target_position_changed"]
    )


def _pressure_active(world: dict[str, Any]) -> bool:
    plate = next(
        item
        for item in world["entities"].values()
        if item.get("_kind") == "pressure"
    )
    position = plate["position"]
    total_mass = sum(
        int(item.get("_mass", 0) or 0)
        for item in world["entities"].values()
        if item.get("_kind") == "object"
        and item.get("position") == position
    )
    return total_mass >= 2


def _socket_active(world: dict[str, Any]) -> bool:
    socket = next(
        item
        for item in world["entities"].values()
        if item.get("_kind") == "socket"
    )
    required = str(socket.get("_required_object") or "")
    required_entity = world["entities"].get(required, {})
    return bool(socket.get("_latched")) or required_entity.get("position") == socket.get("position")


def _override_active(world: dict[str, Any]) -> bool:
    override = next(
        item
        for item in world["entities"].values()
        if item.get("_kind") == "override"
    )
    return bool(override.get("_latched"))


def _mechanism_state(world: dict[str, Any], kind: str) -> str:
    active = (
        _pressure_active(world)
        if kind == "pressure"
        else _socket_active(world)
        if kind == "socket"
        else _override_active(world)
    )
    return "active" if active else "inactive"


def _barrier_open(world: dict[str, Any], barrier: dict[str, Any]) -> bool:
    if _override_active(world):
        return True
    gate = barrier.get("_gate")
    if gate == "pressure":
        return _pressure_active(world)
    if gate == "socket":
        return _socket_active(world)
    return False


def _closed_barrier_at(world: dict[str, Any], position: list[int]) -> bool:
    return any(
        item.get("_kind") == "barrier"
        and item.get("position") == position
        and not _barrier_open(world, item)
        for item in world["entities"].values()
    )


def _solid_entity_at(
    world: dict[str, Any],
    position: list[int],
    *,
    exclude: str | None = None,
) -> bool:
    return any(
        entity_id != exclude
        and item.get("position") == position
        and item.get("_kind") in {"object", "wall"}
        for entity_id, item in world["entities"].items()
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


def _public_state_map(observation: dict[str, Any]) -> dict[str, str]:
    return {
        str(item["id"]): str(item["observable_state"])
        for item in observation.get("visible_entities", [])
        if item.get("observable_state") is not None
    }


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("world_version") != WORLD_VERSION:
        raise ValueError("unsupported open object challenge world version")
    position = state.get("position")
    if not isinstance(position, list) or len(position) != 2 or not _in_bounds(position):
        raise ValueError("invalid agent position")
    inventory = state.get("inventory")
    if not isinstance(inventory, list) or len(inventory) != len(set(inventory)):
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
    for target_id in inventory:
        if target_id not in entities or entities[target_id].get("position") is not None:
            raise ValueError("inventory/entity position mismatch")


def _in_bounds(position: list[int] | tuple[int, int]) -> bool:
    return all(-BOUNDS <= int(value) <= BOUNDS for value in position)


def _manhattan(left: list[int], right: list[int]) -> int:
    return abs(int(left[0]) - int(right[0])) + abs(int(left[1]) - int(right[1]))
