from __future__ import annotations

import json
from typing import Any

from .perception import COMPARABLE_FIELDS
from .state import utc_now


def _world(state: dict[str, Any]) -> dict[str, Any]:
    world = state.setdefault(
        "world_model",
        {
            "claims": [],
            "current": {},
            "last_snapshot_index": 0,
            "seen_prediction_status": {},
            "seen_experiment_status": {},
        },
    )
    world.setdefault("claims", [])
    world.setdefault("current", {})
    world.setdefault("last_snapshot_index", 0)
    world.setdefault("seen_prediction_status", {})
    world.setdefault("seen_experiment_status", {})
    return world


def _claim_key(subject: str, predicate: str) -> str:
    return f"{subject}::{predicate}"


def _new_claim_id(world: dict[str, Any]) -> str:
    return f"W{len(world['claims']) + 1:06d}"


def _episode_ref_for_cycle(state: dict[str, Any], cycle: int) -> str | None:
    for episode in reversed(state.get("episodes", [])):
        if episode.get("cycle") == cycle and episode.get("kind") == "environment":
            return episode.get("id")
    return None


def _reflection_ref(
    state: dict[str, Any],
    field: str,
    value: str,
) -> str | None:
    for reflection in reversed(state.get("reflections", [])):
        if reflection.get(field) == value:
            return reflection.get("id")
    return None


def _upsert_claim(
    state: dict[str, Any],
    subject: str,
    predicate: str,
    value: Any,
    evidence_refs: list[str],
    confidence: float,
    source_type: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    world = _world(state)
    key = _claim_key(subject, predicate)
    current_id = world["current"].get(key)
    current = next(
        (claim for claim in world["claims"] if claim.get("id") == current_id),
        None,
    )

    if current is not None and current.get("value") == value:
        for ref in evidence_refs:
            if ref and ref not in current["evidence_refs"]:
                current["evidence_refs"].append(ref)
                current["evidence_refs"] = current["evidence_refs"][-32:]
        current["last_seen_cycle"] = state.get("cycles", 0)
        current["observed_at"] = observed_at or current.get("observed_at")
        return current

    claim = {
        "id": _new_claim_id(world),
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "status": "current",
        "confidence": confidence,
        "source_type": source_type,
        "evidence_refs": [ref for ref in evidence_refs if ref],
        "created_cycle": state.get("cycles", 0),
        "last_seen_cycle": state.get("cycles", 0),
        "created_at": utc_now(),
        "observed_at": observed_at,
        "supersedes": current.get("id") if current else None,
        "superseded_by": None,
    }

    if current is not None:
        current["status"] = "superseded"
        current["superseded_by"] = claim["id"]

    world["claims"].append(claim)
    world["current"][key] = claim["id"]
    return claim


def consolidate_world(state: dict[str, Any]) -> dict[str, int]:
    world = _world(state)
    new_claims_before = len(world["claims"])
    snapshots = state.get("environment_snapshots", [])
    start = min(int(world.get("last_snapshot_index", 0)), len(snapshots))

    for snapshot in snapshots[start:]:
        cycle = int(snapshot.get("cycle", state.get("cycles", 0)))
        episode_ref = _episode_ref_for_cycle(state, cycle)
        for field in COMPARABLE_FIELDS:
            _upsert_claim(
                state,
                subject="repository",
                predicate=field,
                value=snapshot.get(field),
                evidence_refs=[episode_ref] if episode_ref else [],
                confidence=1.0,
                source_type="observed_sensor",
                observed_at=snapshot.get("observed_at"),
            )
    world["last_snapshot_index"] = len(snapshots)

    seen_predictions = world["seen_prediction_status"]
    for prediction in state.get("predictions", []):
        prediction_id = prediction.get("id")
        status = prediction.get("status")
        if not prediction_id or status not in {"confirmed", "violated"}:
            continue
        if seen_predictions.get(prediction_id) == status:
            continue
        refs = [prediction_id]
        reflection_ref = _reflection_ref(state, "prediction_id", prediction_id)
        if reflection_ref:
            refs.append(reflection_ref)
        _upsert_claim(
            state,
            subject=f"prediction.{prediction_id}",
            predicate="status",
            value=status,
            evidence_refs=refs,
            confidence=float(prediction.get("evidence_strength", 1.0)),
            source_type="prediction_evaluation",
            observed_at=prediction.get("evaluated_at"),
        )
        seen_predictions[prediction_id] = status

    seen_experiments = world["seen_experiment_status"]
    for experiment in state.get("experiments", []):
        experiment_id = experiment.get("id")
        status = experiment.get("status")
        if not experiment_id or status != "completed":
            continue
        marker = json.dumps(
            [status, experiment.get("outcome"), experiment.get("evidence_strength")],
            sort_keys=True,
        )
        if seen_experiments.get(experiment_id) == marker:
            continue
        refs = [experiment_id]
        reflection_ref = _reflection_ref(state, "experiment_id", experiment_id)
        if reflection_ref:
            refs.append(reflection_ref)
        _upsert_claim(
            state,
            subject=f"experiment.{experiment_id}",
            predicate="outcome",
            value=experiment.get("outcome"),
            evidence_refs=refs,
            confidence=float(experiment.get("evidence_strength", 0.5)),
            source_type="experiment_outcome",
            observed_at=experiment.get("completed_at"),
        )
        seen_experiments[experiment_id] = marker

    return {
        "new_claims": len(world["claims"]) - new_claims_before,
        "current_claims": len(world["current"]),
        "total_claims": len(world["claims"]),
    }


def current_world_claims(
    state: dict[str, Any],
    limit: int = 20,
) -> list[dict[str, Any]]:
    world = _world(state)
    current_ids = set(world["current"].values())
    claims = [
        claim
        for claim in world["claims"]
        if claim.get("id") in current_ids and claim.get("status") == "current"
    ]
    claims.sort(
        key=lambda claim: (
            -int(claim.get("last_seen_cycle", 0)),
            str(claim.get("subject")),
            str(claim.get("predicate")),
        )
    )
    return claims[: max(0, limit)]
