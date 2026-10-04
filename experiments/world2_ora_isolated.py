from __future__ import annotations

import hashlib
import json
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agenttest.core import AgentCore
from agenttest.state import StateStore
from world2_ecology import initial_world2_state, observe_world2, transition_world2

ADAPTER_VERSION = "world2-repository-shaped-sensor-pilot-v2"
TRIAL_STIMULUS = "isolated sensor-response trial"


def world2_repository_shaped_observation(
    world_observation: dict[str, Any],
    *,
    world_seed: int = 1,
) -> dict[str, Any]:
    """Synthetic sensor-response pilot, NOT a native World 2 perception layer.

    The baseline identifies fixed experiment configuration, never sensor values
    or elapsed time. Repository field names remain explicit proxy channels;
    outcomes do not establish object understanding or autonomous exploration.
    """
    configuration = {
        "adapter_version": ADAPTER_VERSION,
        "world_version": world_observation["world_version"],
        "world_seed": int(world_seed),
    }
    payload = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return {
        "branch": "isolated/world2-sensor-pilot",
        "baseline_fingerprint": "world2:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
        "tracked_files": 100 + len(world_observation.get("visible_objects", [])),
        "python_files": 20,
        "python_source_lines": 5000 + int(world_observation.get("slow_signal", 0) or 0),
        "test_files": 12 + (
            int(world_observation["local_resource"])
            if world_observation.get("local_resource") is not None else 0
        ),
        "working_tree_clean": True,
    }


def trial_start_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "cycle": int(source.get("cycles", 0)),
        "question_ids": [item["id"] for item in source.get("questions", [])],
        "question_texts": [item.get("text", "") for item in source.get("questions", [])],
        "counts": {
            key: len(source.get(key, []))
            for key in ("surprises", "predictions", "experiments", "reflections")
        },
        "empirical_family_count": len((source.get("empirical_learning") or {}).get("families", {})),
        "genuine_resumption_count": int((source.get("agenda") or {}).get("genuine_resumption_count", 0)),
    }


def trial_time(source: dict[str, Any], offset: int) -> str:
    start = datetime.fromisoformat(str(source.get("updated_at") or "2000-01-01T00:00:00+00:00").replace("Z", "+00:00"))
    return (start + timedelta(seconds=offset)).isoformat()


def trial_cycle_record(result: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "cycle": result["cycle"],
        "observation": deepcopy(observation),
        "prediction_result": deepcopy(result.get("prediction_result")),
        "surprise": deepcopy(result.get("surprise")),
        "drives": deepcopy(result.get("drives")),
        "intention": deepcopy(result.get("intention")),
        "question": deepcopy(result.get("question")),
        "agenda_decision": deepcopy(result.get("agenda_decision")),
    }


def run_isolated_ora_world2_trial(
    source_state: dict[str, Any], *, seed: int, actions: list[str],
) -> dict[str, Any]:
    """Scripted World 2 observations; copied Ora state; no real-world writes."""
    source_before = deepcopy(source_state)
    start = trial_start_metadata(source_state)
    world = initial_world2_state(seed=seed)
    cycle_results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "organism.json"
        StateStore(path).save(deepcopy(source_state))
        for index, action in enumerate(actions, start=1):
            world, world_record = transition_world2(world, action, cycle=index)
            observation = world2_repository_shaped_observation(observe_world2(world), world_seed=seed)
            result = AgentCore(StateStore(path)).cycle(
                stimulus=TRIAL_STIMULUS, observation=observation,
                cognition=False, strict_experiment_admission=True,
                _now_override=trial_time(source_state, index),
            )
            record = trial_cycle_record(result, observation)
            record["world"] = world_record
            cycle_results.append(record)
        isolated_state = StateStore(path).load()
    if source_state != source_before:
        raise RuntimeError("isolated trial mutated caller source state")
    return {
        "seed": seed, "actions": list(actions), "world_final": world,
        "ora_final": isolated_state, "cycles": cycle_results, "trial_start": start,
    }
