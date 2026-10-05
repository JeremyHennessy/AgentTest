from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION

from open_object_world import observe_world, transition
from open_object_world_epistemic_actions import select_epistemic_command
from open_object_world_epistemic_action_study import (
    ranked_temporal,
    run_to_checkpoint,
)
from open_object_world_native_bridge import (
    public_features,
    stage_in_copied_core,
)


def run_mature_copied_loop(
    core: AgentCore,
    *,
    seed: int,
    checkpoint: int,
) -> dict[str, Any]:
    world, attempts, observations, receipts = run_to_checkpoint(
        seed,
        checkpoint,
    )
    ranked = ranked_temporal(observations)
    selected = ranked[0]
    candidate = selected["candidate"]

    epistemic = select_epistemic_command(
        observations[-1],
        feature=candidate["feature"],
        relation=candidate["relation"],
        prefix_observations=observations,
        prefix_receipts=receipts,
    )
    if epistemic["mode"] != "seek_disconfirming_observation":
        return {
            "status": "not_mature",
            "seed": seed,
            "checkpoint": checkpoint,
            "epistemic_selection": deepcopy(epistemic),
        }

    staged = stage_in_copied_core(
        core,
        selected,
        observations,
    )
    experiment_id = staged["inquiry_result"]["experiment"]["id"]
    question_id = staged["inquiry_result"]["question"]["id"]

    before_observation = observe_world(world)
    next_world, receipt = transition(
        deepcopy(world),
        epistemic["command"],
        cycle=checkpoint + 1,
    )
    after_observation = observe_world(next_world)
    before_features = public_features(before_observation)
    after_features = public_features(after_observation)
    feature = candidate["feature"]

    evaluable = feature in before_features and feature in after_features
    changed = (
        before_features.get(feature) != after_features.get(feature)
        if evaluable
        else None
    )
    supports = (
        (not changed)
        if candidate["relation"] == "same_next_observation"
        else bool(changed)
    ) if evaluable else None

    outcome_result = None
    if evaluable:
        evidence = {
            "version": NATIVE_EVIDENCE_V2_VERSION,
            "relation": {
                "kind": candidate["relation"],
                "feature": feature,
                "action": None,
                "comparison_status": "not_applicable",
            },
            "observation_refs": [
                str(before_observation["observation_id"]),
                str(after_observation["observation_id"]),
            ],
            "measurement_kind": "binary_transition_outcomes",
            "measurement": {
                "evaluable": 1,
                "confirmations": 1 if supports else 0,
                "refutations": 0 if supports else 1,
            },
        }
        outcome_result = core.record_native_evidence(
            evidence,
            enabled=True,
            persist=True,
        )

    after_state = core.store.load()
    experiment = next(
        item
        for item in after_state["experiments"]
        if item["id"] == experiment_id
    )
    question = next(
        item
        for item in after_state["questions"]
        if item["id"] == question_id
    )
    return {
        "status": "completed",
        "seed": seed,
        "checkpoint": checkpoint,
        "feature": feature,
        "relation": candidate["relation"],
        "inquiry_score": selected["score"],
        "question_id": question_id,
        "experiment_id": experiment_id,
        "epistemic_selection": deepcopy(epistemic),
        "action_receipt": receipt,
        "before_observation": before_observation,
        "after_observation": after_observation,
        "evaluable": evaluable,
        "changed": changed,
        "supports_hypothesis": supports,
        "falsified_hypothesis": (
            not supports if supports is not None else None
        ),
        "outcome_evidence_ref": (
            outcome_result["evidence_ref"]
            if outcome_result is not None
            else None
        ),
        "question_source": question.get("source"),
        "experiment_status_after_outcome": experiment.get("status"),
        "experiment_readiness_after_outcome": experiment.get("readiness"),
        "native_outcome_auto_resolved": (
            experiment.get("status") == "completed"
        ),
    }
