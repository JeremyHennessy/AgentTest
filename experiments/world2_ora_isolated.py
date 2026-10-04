from __future__ import annotations

import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.core import AgentCore
from agenttest.state import StateStore
from world2_ecology import initial_world2_state, observe_world2, transition_world2


def world2_repository_shaped_observation(
    world_observation: dict[str, Any],
) -> dict[str, Any]:
    """Encode bounded World 2 readings into an isolated auditable observation.

    This adapter deliberately does not add action authority. It provides a
    synthetic observation payload to a temporary AgentCore only.
    """

    payload = json.dumps(world_observation, sort_keys=True)
    return {
        "branch": "isolated/world2",
        "baseline_fingerprint": "world2:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
        "tracked_files": 100 + len(world_observation.get("visible_objects", [])),
        "python_files": 20,
        "python_source_lines": 5000 + int(world_observation.get("slow_signal", 0) or 0),
        "test_files": 12 + (
            int(world_observation["local_resource"])
            if world_observation.get("local_resource") is not None
            else 0
        ),
        "working_tree_clean": True,
    }


def run_isolated_ora_world2_trial(
    source_state: dict[str, Any],
    *,
    seed: int,
    actions: list[str],
) -> dict[str, Any]:
    """Run copied Ora state against World 2 entirely inside a temp directory."""

    source_before = deepcopy(source_state)
    world = initial_world2_state(seed=seed)
    cycle_results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as temp:
        store = StateStore(Path(temp) / "organism.json")
        store.save(deepcopy(source_state))
        core = AgentCore(store)

        for index, action in enumerate(actions, start=1):
            world, world_record = transition_world2(world, action, cycle=index)
            observation = world2_repository_shaped_observation(
                observe_world2(world)
            )
            result = core.cycle(
                stimulus="isolated World 2 observation",
                observation=observation,
                cognition=False,
                strict_experiment_admission=True,
            )
            cycle_results.append(
                {
                    "world": world_record,
                    "ora_cycle": result.get("cycle"),
                    "intention": deepcopy(result.get("intention")),
                    "question": deepcopy(result.get("question")),
                    "agenda_decision": deepcopy(result.get("agenda_decision")),
                }
            )

        isolated_state = store.load()

    if source_state != source_before:
        raise RuntimeError("isolated trial mutated caller source state")

    return {
        "seed": seed,
        "actions": list(actions),
        "world_final": world,
        "ora_final": isolated_state,
        "cycles": cycle_results,
    }
