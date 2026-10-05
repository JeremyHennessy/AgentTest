from __future__ import annotations

from typing import Any

from agenttest.core import AgentCore

from open_object_world_copied_loop import run_mature_copied_loop


def run_resolved_loop(
    core: AgentCore,
    *,
    seed: int,
    checkpoint: int,
) -> dict[str, Any]:
    result = run_mature_copied_loop(
        core,
        seed=seed,
        checkpoint=checkpoint,
    )
    if result["status"] != "completed":
        return result
    evidence_ref = result.get("outcome_evidence_ref")
    if not evidence_ref:
        return {
            **result,
            "resolution_status": "not_evaluable",
        }

    resolution = core.resolve_native_inquiry(
        result["experiment_id"],
        evidence_ref,
        enabled=True,
        persist=True,
    )
    after = core.store.load()
    experiment = next(
        item
        for item in after["experiments"]
        if item["id"] == result["experiment_id"]
    )
    return {
        **result,
        "resolution_status": "resolved",
        "resolved_experiment_status": experiment.get("status"),
        "resolved_experiment_readiness": experiment.get("readiness"),
        "resolved_experiment_outcome": experiment.get("outcome"),
        "resolution_evidence_refs": list(
            experiment.get("evidence_refs", [])
        ),
        "resolution_reflection": resolution["reflection"],
        "resolution_matches_observation": (
            experiment.get("outcome")
            == (
                "falsified"
                if result["falsified_hypothesis"]
                else "supported"
            )
        ),
    }
