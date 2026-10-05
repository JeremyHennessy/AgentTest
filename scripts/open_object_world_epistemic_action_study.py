from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from normalized_inquiry_objectives import rank_normalized_candidates
from open_object_world import initial_world, observe_world, transition
from open_object_world_epistemic_actions import select_epistemic_command
from open_object_world_explorer import (
    choose_command,
    command_key,
    observation_signature,
)
from open_object_world_native_bridge import (
    public_features,
    temporal_candidates,
)

CHECKPOINTS = (200, 400, 600, 800)


def run_to_checkpoint(seed: int, checkpoint: int):
    world = initial_world(seed=seed)
    attempts: Counter[tuple] = Counter()
    observations = [observe_world(world)]
    receipts = []
    for cycle in range(1, checkpoint + 1):
        observation = observations[-1]
        command = choose_command(observation, attempts)
        attempts[
            (observation_signature(observation), command_key(command))
        ] += 1
        world, receipt = transition(
            world,
            command,
            cycle=cycle,
        )
        receipts.append(receipt)
        observations.append(observe_world(world))
    return world, attempts, observations, receipts


def evaluate_action(
    world: dict,
    command: dict,
    *,
    cycle: int,
    feature: str,
    relation: str,
) -> dict:
    before_observation = observe_world(world)
    next_world, receipt = transition(
        deepcopy(world),
        command,
        cycle=cycle,
    )
    after_observation = observe_world(next_world)
    before = public_features(before_observation)
    after = public_features(after_observation)
    if feature not in before or feature not in after:
        return {
            "evaluable": False,
            "changed": None,
            "falsified": None,
            "receipt": receipt,
        }
    changed = before[feature] != after[feature]
    falsified = (
        changed
        if relation == "same_next_observation"
        else not changed
    )
    return {
        "evaluable": True,
        "changed": changed,
        "falsified": falsified,
        "receipt": receipt,
    }


def ranked_temporal(observations):
    return [
        item
        for item in rank_normalized_candidates(
            temporal_candidates(observations),
            "information_gain",
        )
        if item["eligible"]
    ]


def inquiry_action_case(
    world,
    attempts,
    observations,
    receipts,
    selected,
    checkpoint,
):
    observation = observations[-1]
    candidate = selected["candidate"]
    epistemic = select_epistemic_command(
        observation,
        feature=candidate["feature"],
        relation=candidate["relation"],
        prefix_observations=observations,
        prefix_receipts=receipts,
    )
    baseline = choose_command(observation, attempts)
    return {
        "feature": candidate["feature"],
        "relation": candidate["relation"],
        "inquiry_score": selected["score"],
        "epistemic_selection": epistemic,
        "epistemic_outcome": evaluate_action(
            world,
            epistemic["command"],
            cycle=checkpoint + 1,
            feature=candidate["feature"],
            relation=candidate["relation"],
        ),
        "unguided_command": baseline,
        "unguided_outcome": evaluate_action(
            world,
            baseline,
            cycle=checkpoint + 1,
            feature=candidate["feature"],
            relation=candidate["relation"],
        ),
        "different_from_unguided": epistemic["command"] != baseline,
    }


def main() -> None:
    rows = []
    for seed in range(1, 5):
        for checkpoint in CHECKPOINTS:
            world, attempts, observations, receipts = run_to_checkpoint(
                seed,
                checkpoint,
            )
            ranked = ranked_temporal(observations)
            selected = ranked[0]
            top_case = inquiry_action_case(
                world,
                attempts,
                observations,
                receipts,
                selected,
                checkpoint,
            )

            visible_features = public_features(observations[-1])
            state_selected = next(
                (
                    item
                    for item in ranked
                    if str(item["candidate"]["feature"]).endswith(".state")
                    and item["candidate"]["feature"] in visible_features
                ),
                None,
            )
            state_case = (
                inquiry_action_case(
                    world,
                    attempts,
                    observations,
                    receipts,
                    state_selected,
                    checkpoint,
                )
                if state_selected is not None
                else None
            )

            rows.append(
                {
                    "seed": seed,
                    "checkpoint": checkpoint,
                    "top_inquiry": top_case,
                    "best_currently_visible_entity_state_inquiry": state_case,
                }
            )

    top_evaluable = [
        row["top_inquiry"]
        for row in rows
        if row["top_inquiry"]["epistemic_outcome"]["evaluable"]
    ]
    state_cases = [
        row["best_currently_visible_entity_state_inquiry"]
        for row in rows
        if row["best_currently_visible_entity_state_inquiry"] is not None
    ]
    state_evaluable = [
        row
        for row in state_cases
        if row["epistemic_outcome"]["evaluable"]
    ]

    report = {
        "study": "open-object-world-epistemic-action-v1",
        "policy": "public-falsification-oriented-v1",
        "world_reward": False,
        "authored_goal": False,
        "hidden_mechanic_access": False,
        "rows": rows,
        "summary": {
            "case_count": len(rows),
            "top_inquiry_features": sorted(
                {
                    row["top_inquiry"]["feature"]
                    for row in rows
                }
            ),
            "top_epistemic_falsification_rate": (
                round(
                    sum(
                        bool(row["epistemic_outcome"]["falsified"])
                        for row in top_evaluable
                    )
                    / len(top_evaluable),
                    6,
                )
                if top_evaluable
                else None
            ),
            "top_unguided_falsification_rate": (
                round(
                    sum(
                        bool(row["unguided_outcome"]["falsified"])
                        for row in top_evaluable
                    )
                    / len(top_evaluable),
                    6,
                )
                if top_evaluable
                else None
            ),
            "top_different_from_unguided_count": sum(
                bool(row["top_inquiry"]["different_from_unguided"])
                for row in rows
            ),
            "visible_entity_state_case_count": len(state_cases),
            "entity_state_epistemic_falsification_rate": (
                round(
                    sum(
                        bool(row["epistemic_outcome"]["falsified"])
                        for row in state_evaluable
                    )
                    / len(state_evaluable),
                    6,
                )
                if state_evaluable
                else None
            ),
            "entity_state_unguided_falsification_rate": (
                round(
                    sum(
                        bool(row["unguided_outcome"]["falsified"])
                        for row in state_evaluable
                    )
                    / len(state_evaluable),
                    6,
                )
                if state_evaluable
                else None
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
