from __future__ import annotations

from copy import deepcopy
from typing import Any

from world3_ecology import WORLD3_ACTIONS, WORLD3_BOUNDS, WORLD3_VERSION

SCHEMA_VERSION = "world3-observation-v1"
CONTRACT_ID = "world3-transfer-ecology-v0-native-observation-v1"
_ALLOWED_EFFECTS = {None, "object_consumed", "no_visible_target"}


def native_world3_observation(
    observation: dict[str, Any], *, action_receipt: dict[str, Any] | None = None
) -> dict[str, Any]:
    if observation.get("world_version") != WORLD3_VERSION:
        raise ValueError("unsupported World 3 version")
    cycle = observation.get("cycle")
    if type(cycle) is not int or cycle < 0:
        raise ValueError("invalid World 3 cycle")
    position = _position(observation.get("position"))
    visible = observation.get("visible_objects")
    if not isinstance(visible, list) or any(not isinstance(item, str) or not item for item in visible):
        raise ValueError("invalid visible object IDs")
    cue = observation.get("local_cue")
    if cue is not None and (type(cue) is not int or not 0 <= cue <= 4):
        raise ValueError("local cue must be absent or 0..4")
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "world_version": WORLD3_VERSION,
        "contract_id": CONTRACT_ID,
        "observation_id": f"w3-sample-{cycle:06d}",
        "world_step": cycle,
        "position": position,
        "visible_object_ids": sorted(set(visible)),
        "local_cue": (
            {"status": "not_present_here", "scope": "local"}
            if cue is None
            else {"status": "measured", "scope": "local", "value": cue}
        ),
        "action_receipt": _receipt(action_receipt),
    }
    return validate_native_world3_observation(envelope)


def validate_native_world3_observation(envelope: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "world_version", "contract_id", "observation_id",
        "world_step", "position", "visible_object_ids", "local_cue", "action_receipt",
    }
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise ValueError("World 3 observation fields do not match contract")
    if envelope["schema_version"] != SCHEMA_VERSION or envelope["world_version"] != WORLD3_VERSION:
        raise ValueError("unsupported World 3 observation contract")
    if envelope["contract_id"] != CONTRACT_ID:
        raise ValueError("unexpected World 3 contract")
    _position(envelope["position"])
    cue = envelope["local_cue"]
    if not isinstance(cue, dict) or cue.get("scope") != "local":
        raise ValueError("invalid local cue")
    if cue.get("status") == "measured":
        if set(cue) != {"status", "scope", "value"} or type(cue["value"]) is not int or not 0 <= cue["value"] <= 4:
            raise ValueError("invalid measured local cue")
    elif cue.get("status") == "not_present_here":
        if set(cue) != {"status", "scope"}:
            raise ValueError("absent cue cannot carry value")
    else:
        raise ValueError("invalid local cue status")
    return deepcopy(envelope)


def _position(value: Any) -> list[int]:
    if not isinstance(value, list) or len(value) != 2 or any(type(x) is not int or abs(x) > WORLD3_BOUNDS for x in value):
        raise ValueError("invalid position")
    return list(value)


def _receipt(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt.get("action") not in WORLD3_ACTIONS or type(receipt.get("blocked")) is not bool:
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
