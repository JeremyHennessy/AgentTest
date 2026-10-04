from __future__ import annotations

from copy import deepcopy
from typing import Any

from world4_toggle_ecology import WORLD4_ACTIONS, WORLD4_BOUNDS, WORLD4_VERSION

SCHEMA_VERSION = "world4-observation-v1"
CONTRACT_ID = "world4-toggle-ecology-v0-native-observation-v1"
_ALLOWED_EFFECTS = {None, "signal_toggled", "no_visible_target"}


def native_world4_observation(
    observation: dict[str, Any], *, action_receipt: dict[str, Any] | None = None
) -> dict[str, Any]:
    if observation.get("world_version") != WORLD4_VERSION:
        raise ValueError("unsupported World 4 version")
    cycle = observation.get("cycle")
    if type(cycle) is not int or cycle < 0:
        raise ValueError("invalid World 4 cycle")
    position = _position(observation.get("position"))
    visible = observation.get("visible_objects")
    if not isinstance(visible, list) or any(not isinstance(item, str) or not item for item in visible):
        raise ValueError("invalid visible object IDs")
    signal = observation.get("slow_signal")
    if type(signal) is not int or signal not in (0, 1):
        raise ValueError("World 4 slow signal must be binary")
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "world_version": WORLD4_VERSION,
        "contract_id": CONTRACT_ID,
        "observation_id": f"w4-sample-{cycle:06d}",
        "world_step": cycle,
        "position": position,
        "visible_object_ids": sorted(set(visible)),
        "slow_signal": {"status": "measured", "scope": "broadcast", "value": signal},
        "action_receipt": _receipt(action_receipt),
    }
    return validate_native_world4_observation(envelope)


def validate_native_world4_observation(envelope: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "world_version", "contract_id", "observation_id",
        "world_step", "position", "visible_object_ids", "slow_signal", "action_receipt",
    }
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise ValueError("World 4 observation fields do not match contract")
    if envelope["schema_version"] != SCHEMA_VERSION or envelope["world_version"] != WORLD4_VERSION:
        raise ValueError("unsupported World 4 observation contract")
    if envelope["contract_id"] != CONTRACT_ID:
        raise ValueError("unexpected World 4 contract")
    _position(envelope["position"])
    signal = envelope["slow_signal"]
    if (
        not isinstance(signal, dict)
        or set(signal) != {"status", "scope", "value"}
        or signal.get("status") != "measured"
        or signal.get("scope") != "broadcast"
        or type(signal.get("value")) is not int
        or signal.get("value") not in (0, 1)
    ):
        raise ValueError("invalid World 4 slow signal")
    return deepcopy(envelope)


def _position(value: Any) -> list[int]:
    if not isinstance(value, list) or len(value) != 2 or any(type(x) is not int or abs(x) > WORLD4_BOUNDS for x in value):
        raise ValueError("invalid position")
    return list(value)


def _receipt(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt.get("action") not in WORLD4_ACTIONS or type(receipt.get("blocked")) is not bool:
        raise ValueError("invalid action receipt")
    effect = receipt.get("interaction_effect")
    if effect not in _ALLOWED_EFFECTS:
        raise ValueError("invalid observed effect")
    before, after = _position(receipt.get("before")), _position(receipt.get("after"))
    if receipt["action"] not in ("north", "east", "south", "west") and before != after:
        raise ValueError("non-movement action moved actor")
    if receipt["blocked"] and before != after:
        raise ValueError("blocked action moved actor")
    return {"action": receipt["action"], "before": before, "after": after, "blocked": receipt["blocked"], "observed_effect": effect}
