from __future__ import annotations

from copy import deepcopy
from typing import Any

from world2_native_observation import CONTRACT_ID, validate_native_world2_observation

PREDICTION_VERSION = "world2-native-prediction-v1"
_SUPPORTED_KINDS = {
    "object_visible_at_position",
    "resource_value_at_position",
    "slow_signal_value",
}


def make_prediction(
    *,
    prediction_id: str,
    kind: str,
    created_observation: dict[str, Any],
    expected: Any,
    target_position: list[int] | None = None,
    object_id: str | None = None,
) -> dict[str, Any]:
    """Create a typed prediction from already observed native data only."""
    observation = validate_native_world2_observation(created_observation)
    if kind not in _SUPPORTED_KINDS:
        raise ValueError("unsupported native prediction kind")
    if not isinstance(prediction_id, str) or not prediction_id:
        raise ValueError("prediction ID is required")

    prediction: dict[str, Any] = {
        "version": PREDICTION_VERSION,
        "prediction_id": prediction_id,
        "contract_id": CONTRACT_ID,
        "kind": kind,
        "created_observation_id": observation["observation_id"],
        "created_world_step": observation["world_step"],
        "target_position": None,
        "object_id": None,
        "expected": None,
    }

    if kind == "object_visible_at_position":
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("object prediction requires an object ID")
        position = _position(target_position)
        if type(expected) is not bool:
            raise ValueError("object visibility expectation must be boolean")
        prediction.update(
            target_position=position,
            object_id=object_id,
            expected=expected,
        )
    elif kind == "resource_value_at_position":
        position = _position(target_position)
        if type(expected) is not int or not 0 <= expected <= 4:
            raise ValueError("resource expectation must be an integer from 0 to 4")
        prediction.update(target_position=position, expected=expected)
    else:
        if type(expected) is not int or not 0 <= expected <= 9:
            raise ValueError("slow signal expectation must be an integer from 0 to 9")
        prediction["expected"] = expected

    return prediction


def evaluate_prediction(
    prediction: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate only when the target is legitimately observed."""
    sample = validate_native_world2_observation(observation)
    pred = validate_prediction(prediction)
    if sample["contract_id"] != pred["contract_id"]:
        return _result(pred, sample, "invalidated_by_contract", None)

    kind = pred["kind"]
    if kind == "object_visible_at_position":
        if sample["position"] != pred["target_position"]:
            return _result(pred, sample, "unevaluable", "target_position_not_observed")
        actual = pred["object_id"] in sample["visible_object_ids"]
    elif kind == "resource_value_at_position":
        if sample["position"] != pred["target_position"]:
            return _result(pred, sample, "unevaluable", "target_position_not_observed")
        reading = sample["local_resource"]
        if reading["status"] != "measured":
            return _result(pred, sample, "unevaluable", f"resource_{reading['status']}")
        actual = reading["value"]
    else:
        reading = sample["slow_signal"]
        if reading["status"] != "measured":
            return _result(pred, sample, "unevaluable", f"slow_signal_{reading['status']}")
        actual = reading["value"]

    status = "confirmed" if actual == pred["expected"] else "refuted"
    return _result(pred, sample, status, None, actual=actual)


def validate_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    required = {
        "version",
        "prediction_id",
        "contract_id",
        "kind",
        "created_observation_id",
        "created_world_step",
        "target_position",
        "object_id",
        "expected",
    }
    if not isinstance(prediction, dict) or set(prediction) != required:
        raise ValueError("native prediction fields do not match the contract")
    if prediction["version"] != PREDICTION_VERSION:
        raise ValueError("unsupported prediction version")
    if prediction["contract_id"] != CONTRACT_ID:
        raise ValueError("unexpected prediction contract")
    if prediction["kind"] not in _SUPPORTED_KINDS:
        raise ValueError("unsupported native prediction kind")
    if not isinstance(prediction["prediction_id"], str) or not prediction["prediction_id"]:
        raise ValueError("invalid prediction ID")
    if not isinstance(prediction["created_observation_id"], str):
        raise ValueError("invalid source observation ID")
    if type(prediction["created_world_step"]) is not int or prediction["created_world_step"] < 0:
        raise ValueError("invalid prediction creation step")

    kind = prediction["kind"]
    if kind == "object_visible_at_position":
        _position(prediction["target_position"])
        if not isinstance(prediction["object_id"], str) or not prediction["object_id"]:
            raise ValueError("invalid predicted object ID")
        if type(prediction["expected"]) is not bool:
            raise ValueError("invalid object visibility expectation")
    elif kind == "resource_value_at_position":
        _position(prediction["target_position"])
        if prediction["object_id"] is not None:
            raise ValueError("resource prediction cannot name an object")
        if type(prediction["expected"]) is not int or not 0 <= prediction["expected"] <= 4:
            raise ValueError("invalid resource expectation")
    else:
        if prediction["target_position"] is not None or prediction["object_id"] is not None:
            raise ValueError("broadcast prediction cannot carry a local target")
        if type(prediction["expected"]) is not int or not 0 <= prediction["expected"] <= 9:
            raise ValueError("invalid slow signal expectation")
    return deepcopy(prediction)


def _position(value: Any) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int for item in value)
        or any(abs(item) > 2 for item in value)
    ):
        raise ValueError("prediction target must be an in-bounds position")
    return list(value)


def _result(
    prediction: dict[str, Any],
    observation: dict[str, Any],
    status: str,
    reason: str | None,
    *,
    actual: Any = None,
) -> dict[str, Any]:
    return {
        "prediction_id": prediction["prediction_id"],
        "prediction_kind": prediction["kind"],
        "source_observation_id": prediction["created_observation_id"],
        "evidence_observation_id": observation["observation_id"],
        "status": status,
        "reason": reason,
        "expected": deepcopy(prediction["expected"]),
        "actual": deepcopy(actual),
        "direct_evidence": status in {"confirmed", "refuted"},
    }
