from __future__ import annotations

from copy import deepcopy
from typing import Any

WORLD3_MEMORY_KEY = "world3_native_experiment"


def consume_world3(state: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any]:
    memory = state.setdefault(
        WORLD3_MEMORY_KEY,
        {"observations": [], "predictions": [], "evidence": [], "hypotheses": {}},
    )
    memory["observations"].append(deepcopy(sample))
    resolved = []
    for item in memory["predictions"]:
        if item["status"] != "pending":
            continue
        pred = item["prediction"]
        if sample["position"] != pred["target_position"]:
            continue
        if pred["kind"] == "object_visible_at_position":
            actual = pred["object_id"] in sample["visible_object_ids"]
        else:
            cue = sample["local_cue"]
            if cue["status"] != "measured":
                continue
            actual = cue["value"]
        status = "confirmed" if actual == pred["expected"] else "refuted"
        item["status"] = status
        evidence = {
            "id": f"W3E{len(memory['evidence']) + 1:06d}",
            "prediction_id": pred["id"],
            "status": status,
            "expected": deepcopy(pred["expected"]),
            "actual": deepcopy(actual),
            "observation_id": sample["observation_id"],
        }
        memory["evidence"].append(evidence)
        resolved.append(evidence["id"])

    proposals = []
    for object_id in sample["visible_object_ids"]:
        proposals.append({
            "id": f"W3P{len(memory['predictions']) + len(proposals) + 1:06d}",
            "kind": "object_visible_at_position",
            "target_position": deepcopy(sample["position"]),
            "object_id": object_id,
            "expected": True,
        })
    cue = sample["local_cue"]
    if cue["status"] == "measured":
        proposals.append({
            "id": f"W3P{len(memory['predictions']) + len(proposals) + 1:06d}",
            "kind": "local_cue_value_at_position",
            "target_position": deepcopy(sample["position"]),
            "object_id": None,
            "expected": cue["value"],
        })
    for pred in proposals:
        key = _key(pred)
        if any(x["status"] == "pending" and _key(x["prediction"]) == key for x in memory["predictions"]):
            continue
        memory["predictions"].append({"prediction": pred, "status": "pending"})
    return {"resolved_evidence_ids": resolved, "memory": deepcopy(memory)}


def world3_candidate(state: dict[str, Any]) -> dict[str, Any] | None:
    memory = state.get(WORLD3_MEMORY_KEY, {})
    refuted = [e for e in memory.get("evidence", []) if e["status"] == "refuted"]
    pending = [p for p in memory.get("predictions", []) if p["status"] == "pending"]
    if refuted:
        evidence = refuted[-1]
        pred = next(p["prediction"] for p in memory["predictions"] if p["prediction"]["id"] == evidence["prediction_id"])
        drive = "prediction_error"
        refs = [evidence["id"]]
    elif pending:
        pred = pending[0]["prediction"]
        drive = "evidence_hunger"
        refs = []
    else:
        return None
    position = pred["target_position"]
    if pred["kind"] == "object_visible_at_position":
        subject = f"whether object {pred['object_id']} persists at observed position {position}"
        experiment = f"Observe position {position} again and record whether object {pred['object_id']} is visible."
        falsification = f"Object {pred['object_id']} being absent at {position} counts against persistence."
    else:
        subject = f"whether the local cue at observed position {position} is stable"
        experiment = f"Observe position {position} again and compare the local cue with its prior measured value."
        falsification = f"A different measured local cue at {position} counts against stability."
    return {
        "id": "W3C-" + pred["id"],
        "question": f"What observation would most directly test {subject}?",
        "hypothesis": "The selected locally observed feature will remain stable when legitimately measured again.",
        "experiment": experiment,
        "falsification": falsification,
        "predicted_observation": None,
        "dominant_drive": drive,
        "evidence_refs": refs,
    }


def _key(pred: dict[str, Any]) -> str:
    return "|".join((pred["kind"], repr(pred["target_position"]), str(pred.get("object_id"))))
