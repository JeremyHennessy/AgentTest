from __future__ import annotations

from typing import Any

from native_relation_discovery import evaluate_relations, propose_relations
from native_relation_family_memory import update_family_memory
from world2_ecology import initial_world2_state, observe_world2, transition_world2
from world2_native_observation import native_world2_observation
from world3_ecology import initial_world3_state, observe_world3, transition_world3
from world3_native_observation import native_world3_observation


def world2_stability_trajectory(state: dict[str, Any]) -> dict[str, Any]:
    world = initial_world2_state(seed=1)
    samples = [native_world2_observation(observe_world2(world))]
    for cycle, action in enumerate(("observe", "observe", "observe"), start=1):
        world, record = transition_world2(world, action, cycle=cycle)
        samples.append(native_world2_observation(observe_world2(world), action_receipt=record))
    return _learn(state, samples)


def world3_change_trajectory(state: dict[str, Any]) -> dict[str, Any]:
    world = initial_world3_state(seed=1)
    world["position"] = [0, 1]
    samples = [native_world3_observation(observe_world3(world))]
    for cycle in range(1, 9):
        world, record = transition_world3(world, "observe", cycle=cycle)
        samples.append(native_world3_observation(observe_world3(world), action_receipt=record))
    return _learn(state, samples)


def world3_action_trajectory(state: dict[str, Any]) -> dict[str, Any]:
    world = initial_world3_state(seed=1)
    world["position"] = [1, 1]
    samples = [native_world3_observation(observe_world3(world))]
    for cycle, action in enumerate(("interact", "observe", "observe", "observe"), start=1):
        world, record = transition_world3(world, action, cycle=cycle)
        samples.append(native_world3_observation(observe_world3(world), action_receipt=record))
    return _learn(state, samples)


def _learn(state: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    ledger = evaluate_relations(propose_relations(samples), samples)
    update_family_memory(state, ledger)
    return {"samples": samples, "ledger": ledger, "state": state}
