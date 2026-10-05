from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION

from normalized_inquiry_objectives import rank_normalized_candidates
from open_object_world import initial_world, observe_world, transition
from open_object_world_explorer import (
    choose_command,
    command_key,
    observation_signature,
)


def collect_trace(seed: int, steps: int) -> dict[str, Any]:
    world = initial_world(seed=seed)
    attempts: Counter[tuple[Any, ...]] = Counter()
    observations = [observe_world(world)]
    receipts = []

    for cycle in range(1, steps + 1):
        observation = observations[-1]
        command = choose_command(observation, attempts)
        attempts[(observation_signature(observation), command_key(command))] += 1
        world, receipt = transition(world, command, cycle=cycle)
        receipts.append(receipt)
        observations.append(observe_world(world))

    return {
        "seed": int(seed),
        "steps": int(steps),
        "observations": observations,
        "receipts": receipts,
    }


def public_features(observation: dict[str, Any]) -> dict[str, Any]:
    features: dict[str, Any] = {
        "position": tuple(observation.get("position") or []),
        "inventory_ids": tuple(sorted(observation.get("inventory_ids") or [])),
        "visible_ids": tuple(
            sorted(
                str(item.get("id") or "")
                for item in observation.get("visible_entities", [])
                if item.get("id")
            )
        ),
    }
    for item in observation.get("visible_entities", []):
        entity_id = str(item.get("id") or "")
        if not entity_id:
            continue
        features[f"entity.{entity_id}.position"] = tuple(
            item.get("position") or []
        )
        if item.get("observable_state") is not None:
            features[f"entity.{entity_id}.state"] = str(
                item["observable_state"]
            )
    return features


def temporal_candidates(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    feature_names = sorted(
        {
            name
            for observation in observations
            for name in public_features(observation)
        }
    )
    candidates = []
    index = 1
    for feature in feature_names:
        same = 0
        changed = 0
        for left, right in zip(observations, observations[1:]):
            left_features = public_features(left)
            right_features = public_features(right)
            if feature not in left_features or feature not in right_features:
                continue
            if left_features[feature] == right_features[feature]:
                same += 1
            else:
                changed += 1
        evaluable = same + changed
        if evaluable < 3:
            continue
        if same >= changed:
            relation = "same_next_observation"
            confirmations, refutations = same, changed
        else:
            relation = "changes_next_observation"
            confirmations, refutations = changed, same
        candidates.append(
            {
                "id": f"OWC{index:04d}",
                "relation": relation,
                "feature": feature,
                "action": None,
                "status": "evaluated",
                "evaluable": evaluable,
                "confirmations": confirmations,
                "refutations": refutations,
            }
        )
        index += 1
    return candidates


def choose_information_gain_candidate(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = temporal_candidates(observations)
    ranked = rank_normalized_candidates(candidates, "information_gain")
    return next(item for item in ranked if item["eligible"])


def held_out_evaluation(
    candidate: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    feature = candidate["feature"]
    relation = candidate["relation"]
    confirmations = 0
    refutations = 0

    for left, right in zip(observations, observations[1:]):
        left_features = public_features(left)
        right_features = public_features(right)
        if feature not in left_features or feature not in right_features:
            continue
        same = left_features[feature] == right_features[feature]
        supported = (
            same
            if relation == "same_next_observation"
            else not same
        )
        if supported:
            confirmations += 1
        else:
            refutations += 1

    evaluable = confirmations + refutations
    return {
        "feature": feature,
        "relation": relation,
        "evaluable": evaluable,
        "confirmations": confirmations,
        "refutations": refutations,
        "support_rate": (
            round(confirmations / evaluable, 6)
            if evaluable
            else None
        ),
    }


def stage_in_copied_core(
    core: AgentCore,
    selected: dict[str, Any],
    prefix_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate = selected["candidate"]
    relation = {
        "kind": candidate["relation"],
        "feature": candidate["feature"],
        "action": None,
        "comparison_status": "not_applicable",
    }
    observation_refs = [
        str(item.get("observation_id"))
        for item in prefix_observations
        if item.get("observation_id")
    ][-64:]
    evidence = {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": relation,
        "observation_refs": observation_refs,
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": int(candidate["evaluable"]),
            "confirmations": int(candidate["confirmations"]),
            "refutations": int(candidate["refutations"]),
        },
    }
    evidence_result = core.record_native_evidence(
        evidence,
        enabled=True,
        persist=True,
    )

    feature = candidate["feature"]
    stable = candidate["relation"] == "same_next_observation"
    inquiry = {
        "version": NATIVE_INQUIRY_VERSION,
        "id": f"NIC:object-world:{candidate['id']}",
        "objective": "information_gain",
        "objective_score": float(selected["score"]),
        "relation": relation,
        "question": (
            f"What next local observation would most directly test whether "
            f"{feature} {'remains stable' if stable else 'changes'}?"
        ),
        "hypothesis": (
            f"Observed feature {feature} tends to "
            f"{'remain stable' if stable else 'change'} across consecutive "
            "evaluable local observations."
        ),
        "method": (
            f"Collect another local observation where {feature} is observable "
            "and compare it with the previous evaluable value."
        ),
        "falsification": (
            f"A later evaluable {feature} value that "
            f"{'differs' if stable else 'remains the same'} counts against "
            "the current temporal hypothesis."
        ),
        "predicted_observation": (
            f"The next evaluable {feature} observation "
            f"{'matches' if stable else 'differs from'} the previous value."
        ),
        "evidence_refs": [evidence_result["evidence_ref"]],
    }
    inquiry_result = core.propose_native_inquiry(
        inquiry,
        enabled=True,
        persist=True,
    )
    return {
        "selected": deepcopy(selected),
        "evidence_result": evidence_result,
        "inquiry_result": inquiry_result,
    }
