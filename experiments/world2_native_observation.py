from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from world2_ecology import WORLD2_ACTIONS, WORLD2_BOUNDS, WORLD2_VERSION

SCHEMA_VERSION = "world2-observation-v1"
CONTRACT_ID = "world2-causal-ecology-v0-native-observation-v1"
_RESOURCE_STATUSES = {"measured", "not_present_here", "unavailable"}
_ALLOWED_TOP_LEVEL = {
    "schema_version",
    "world_version",
    "contract_id",
    "observation_id",
    "world_step",
    "position",
    "visible_object_ids",
    "local_resource",
    "slow_signal",
    "action_receipt",
}
_ALLOWED_READING = {"status", "value", "scope"}
_ALLOWED_RECEIPT = {"action", "before", "after", "blocked", "observed_effect"}
_ALLOWED_EFFECTS = {
    None,
    "object_displaced",
    "no_visible_target",
    "observation_only",
    "local_resource_changed",
}
_OBJECT_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_OBSERVATION_ID = re.compile(r"^sample-[0-9]{6}$")


def _position(value: Any, *, field: str) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int for item in value)
        or any(abs(item) > WORLD2_BOUNDS for item in value)
    ):
        raise ValueError(f"{field} must be an in-bounds integer coordinate")
    return list(value)


def _reading(*, status: str, scope: str, value: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status, "scope": scope}
    if status == "measured":
        result["value"] = value
    return result


def native_world2_observation(
    world_observation: dict[str, Any],
    *,
    action_receipt: dict[str, Any] | None = None,
    resource_available: bool = True,
) -> dict[str, Any]:
    """Translate bounded World 2 observables without importing hidden world state."""
    world_version = world_observation.get("world_version")
    if world_version != WORLD2_VERSION:
        raise ValueError("unsupported World 2 version")
    world_step = world_observation.get("cycle")
    if type(world_step) is not int or world_step < 0:
        raise ValueError("cycle must be a non-negative integer")
    position = _position(world_observation.get("position"), field="position")
    visible = world_observation.get("visible_objects")
    if (
        not isinstance(visible, list)
        or any(not isinstance(item, str) or not _OBJECT_ID.fullmatch(item) for item in visible)
        or len(visible) != len(set(visible))
    ):
        raise ValueError("visible object IDs must be unique bounded strings")

    resource = world_observation.get("local_resource")
    if not resource_available:
        local_resource = _reading(status="unavailable", scope="local")
    elif resource is None:
        local_resource = _reading(status="not_present_here", scope="local")
    elif type(resource) is int and 0 <= resource <= 4:
        local_resource = _reading(status="measured", scope="local", value=resource)
    else:
        raise ValueError("local resource must be absent or an integer from 0 to 4")

    slow_signal = world_observation.get("slow_signal")
    if type(slow_signal) is not int or not 0 <= slow_signal <= 9:
        raise ValueError("slow signal must be an integer from 0 to 9")

    envelope: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "world_version": WORLD2_VERSION,
        "contract_id": CONTRACT_ID,
        "observation_id": f"sample-{world_step:06d}",
        "world_step": world_step,
        "position": position,
        "visible_object_ids": sorted(visible),
        "local_resource": local_resource,
        "slow_signal": _reading(status="measured", scope="broadcast", value=slow_signal),
        "action_receipt": _native_action_receipt(action_receipt),
    }
    return validate_native_world2_observation(envelope)


def _native_action_receipt(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    action = receipt.get("action")
    if action not in WORLD2_ACTIONS:
        raise ValueError("unsupported action receipt")
    effect = receipt.get("interaction_effect")
    blocked = receipt.get("blocked")
    if type(blocked) is not bool:
        raise ValueError("blocked receipt status must be boolean")
    if effect not in _ALLOWED_EFFECTS:
        raise ValueError("unsupported observed action effect")
    before = _position(receipt.get("before"), field="action_receipt.before")
    after = _position(receipt.get("after"), field="action_receipt.after")
    if action not in ("north", "east", "south", "west") and after != before:
        raise ValueError("non-movement receipt cannot move the actor")
    if blocked and after != before:
        raise ValueError("blocked action cannot move the actor")
    return {
        "action": action,
        "before": before,
        "after": after,
        "blocked": blocked,
        "observed_effect": effect,
    }


def validate_native_world2_observation(envelope: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on schema drift or malformed measurements."""
    if not isinstance(envelope, dict) or set(envelope) != _ALLOWED_TOP_LEVEL:
        raise ValueError("native observation fields do not match the contract")
    if envelope["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported native observation schema")
    if envelope["world_version"] != WORLD2_VERSION:
        raise ValueError("unsupported World 2 version")
    if envelope["contract_id"] != CONTRACT_ID:
        raise ValueError("unexpected native observation contract")
    if not isinstance(envelope["observation_id"], str) or not _OBSERVATION_ID.fullmatch(envelope["observation_id"]):
        raise ValueError("invalid observation ID")
    step = envelope["world_step"]
    if type(step) is not int or step < 0 or envelope["observation_id"] != f"sample-{step:06d}":
        raise ValueError("observation ID and world step disagree")
    _position(envelope["position"], field="position")

    visible = envelope["visible_object_ids"]
    if (
        not isinstance(visible, list)
        or visible != sorted(visible)
        or len(visible) != len(set(visible))
        or any(not isinstance(item, str) or not _OBJECT_ID.fullmatch(item) for item in visible)
    ):
        raise ValueError("visible object IDs must be sorted unique bounded strings")

    _validate_reading(envelope["local_resource"], scope="local", maximum=4, allow_absence=True)
    _validate_reading(envelope["slow_signal"], scope="broadcast", maximum=9, allow_absence=False)

    receipt = envelope["action_receipt"]
    if receipt is not None:
        if not isinstance(receipt, dict) or set(receipt) != _ALLOWED_RECEIPT:
            raise ValueError("action receipt fields do not match the contract")
        if receipt["action"] not in WORLD2_ACTIONS or type(receipt["blocked"]) is not bool:
            raise ValueError("invalid action receipt")
        before = _position(receipt["before"], field="action_receipt.before")
        after = _position(receipt["after"], field="action_receipt.after")
        if receipt["observed_effect"] not in _ALLOWED_EFFECTS:
            raise ValueError("invalid observed action effect")
        if receipt["action"] not in ("north", "east", "south", "west") and after != before:
            raise ValueError("non-movement receipt cannot move the actor")
        if receipt["blocked"] and after != before:
            raise ValueError("blocked action cannot move the actor")
        if after != envelope["position"]:
            raise ValueError("action receipt does not end at observed position")

    return deepcopy(envelope)


def _validate_reading(
    reading: Any, *, scope: str, maximum: int, allow_absence: bool
) -> None:
    if not isinstance(reading, dict) or not set(reading).issubset(_ALLOWED_READING):
        raise ValueError("measurement fields do not match the contract")
    if reading.get("scope") != scope or reading.get("status") not in _RESOURCE_STATUSES:
        raise ValueError("invalid measurement status or scope")
    status = reading["status"]
    if not allow_absence and status != "measured":
        raise ValueError("this sensor must have a measured value")
    if status == "measured":
        if set(reading) != {"status", "scope", "value"}:
            raise ValueError("measured readings require exactly one value")
        value = reading["value"]
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError("measurement value is out of range")
    elif set(reading) != {"status", "scope"}:
        raise ValueError("non-measured readings cannot carry a value")
