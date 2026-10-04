from __future__ import annotations

from copy import deepcopy
from typing import Any

from world2_native_observation import validate_native_world2_observation
from world2_native_prediction import evaluate_prediction, make_prediction

CONSUMER_VERSION = "world2-native-consumer-v0"
NATIVE_STATE_KEY = "world2_native_experiment"


def ensure_native_state(state: dict[str, Any]) -> dict[str, Any]:
    """Attach experiment-only memory to a copied state without changing production schema."""
    return state.setdefault(
        NATIVE_STATE_KEY,
        {
            "version": CONSUMER_VERSION,
            "observations": [],
            "predictions": [],
            "evidence": [],
            "hypotheses": {},
        },
    )


def consume_native_observation(
    state: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Persist observed facts and resolve only legitimately evaluable predictions."""
    sample = validate_native_world2_observation(observation)
    native = ensure_native_state(state)
    native["observations"].append(deepcopy(sample))

    resolved = []
    for pred in native["predictions"]:
        if pred.get("status") != "pending":
            continue
        result = evaluate_prediction(pred["prediction"], sample)
        if result["status"] == "unevaluable":
            continue
        pred["status"] = result["status"]
        pred["result"] = deepcopy(result)
        evidence = {
            "id": f"NW2E{len(native['evidence']) + 1:06d}",
            "kind": "native_prediction_result",
            "prediction_id": pred["prediction"]["prediction_id"],
            "observation_id": sample["observation_id"],
            "status": result["status"],
            "expected": deepcopy(result["expected"]),
            "actual": deepcopy(result["actual"]),
            "direct_evidence": bool(result["direct_evidence"]),
        }
        native["evidence"].append(evidence)
        pred["evidence_id"] = evidence["id"]
        _update_hypothesis(native, pred["prediction"], evidence)
        resolved.append(evidence["id"])

    proposed = _propose_from_observation(native, sample)
    return {
        "observation_id": sample["observation_id"],
        "resolved_evidence_ids": resolved,
        "proposed_prediction_ids": proposed,
        "native_state": deepcopy(native),
    }


def _propose_from_observation(
    native: dict[str, Any], sample: dict[str, Any]
) -> list[str]:
    """Create conservative persistence predictions from observed facts, not hidden truth."""
    proposals: list[dict[str, Any]] = []
    position = sample["position"]

    for object_id in sample["visible_object_ids"]:
        proposals.append(
            make_prediction(
                prediction_id=_next_prediction_id(native, len(proposals)),
                kind="object_visible_at_position",
                created_observation=sample,
                target_position=position,
                object_id=object_id,
                expected=True,
            )
        )

    resource = sample["local_resource"]
    if resource["status"] == "measured":
        proposals.append(
            make_prediction(
                prediction_id=_next_prediction_id(native, len(proposals)),
                kind="resource_value_at_position",
                created_observation=sample,
                target_position=position,
                expected=resource["value"],
            )
        )

    proposals.append(
        make_prediction(
            prediction_id=_next_prediction_id(native, len(proposals)),
            kind="slow_signal_value",
            created_observation=sample,
            expected=sample["slow_signal"]["value"],
        )
    )

    added = []
    for proposal in proposals:
        key = _prediction_key(proposal)
        if any(
            item.get("status") == "pending"
            and _prediction_key(item["prediction"]) == key
            for item in native["predictions"]
        ):
            continue
        native["predictions"].append(
            {"prediction": proposal, "status": "pending", "result": None, "evidence_id": None}
        )
        added.append(proposal["prediction_id"])
    return added


def _update_hypothesis(
    native: dict[str, Any],
    prediction: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    key = _prediction_key(prediction)
    record = native["hypotheses"].setdefault(
        key,
        {
            "kind": prediction["kind"],
            "target_position": deepcopy(prediction["target_position"]),
            "object_id": prediction["object_id"],
            "confirmed": 0,
            "refuted": 0,
            "evidence_refs": [],
            "stance": "unresolved",
        },
    )
    if evidence["status"] == "confirmed":
        record["confirmed"] += 1
    elif evidence["status"] == "refuted":
        record["refuted"] += 1
    record["evidence_refs"].append(evidence["id"])
    if record["confirmed"] > record["refuted"]:
        record["stance"] = "supported"
    elif record["refuted"] > record["confirmed"]:
        record["stance"] = "challenged"
    else:
        record["stance"] = "mixed"


def _prediction_key(prediction: dict[str, Any]) -> str:
    return "|".join(
        [
            prediction["kind"],
            repr(prediction.get("target_position")),
            str(prediction.get("object_id")),
        ]
    )


def _next_prediction_id(native: dict[str, Any], offset: int) -> str:
    return f"NW2P{len(native['predictions']) + offset + 1:06d}"
