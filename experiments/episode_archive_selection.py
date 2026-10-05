"""Conservative copied-state episode archive selection.

Research-only helper. This module does not mutate production state or grant
archive/evidence authority.
"""
from __future__ import annotations

import json
import re
from typing import Any

EPISODE_ID = re.compile(r"E([0-9]+)\Z")


def _walk_external_episode_refs(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if path == () and key == "episodes":
                continue
            rows.extend(
                _walk_external_episode_refs(
                    item,
                    path=(*path, str(key)),
                )
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(
                _walk_external_episode_refs(
                    item,
                    path=(*path, str(index)),
                )
            )
    elif isinstance(value, str) and EPISODE_ID.fullmatch(value):
        rows.append((".".join(path), value))
    return rows


def explicit_external_refs(state: dict[str, Any]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path, identifier in _walk_external_episode_refs(state):
        grouped.setdefault(path, []).append(identifier)
    return grouped


def _planning_payload(episode: dict[str, Any]) -> dict[str, Any] | None:
    if episode.get("kind") != "planning_lab":
        return None
    content = episode.get("content")
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def pending_planning_episode_ids(state: dict[str, Any]) -> set[str]:
    from agenttest.planning_lab import EPISODIC_MEMORY_MAX_ENTRIES

    lab = state.get("planning_lab") or {}
    started = lab.get("episodic_memory_started_cycle")
    if started is None:
        return set()
    started_cycle = int(started or 0)
    world_version = str(lab.get("world_version") or "")
    completed = [
        plan
        for plan in lab.get("plans", [])
        if isinstance(plan, dict)
        and plan.get("status") == "completed"
        and int(plan.get("completed_cycle", 0) or 0) >= started_cycle
        and str(plan.get("world_version") or world_version) == world_version
    ]
    completed.sort(key=lambda plan: int(plan.get("completed_cycle", 0) or 0))
    completed = completed[-EPISODIC_MEMORY_MAX_ENTRIES:]
    existing = {
        str(item.get("source_plan_id") or "")
        for item in lab.get("episodic_route_memories", [])
        if isinstance(item, dict)
    }
    protected: set[str] = set()
    episodes = state.get("episodes", [])

    for plan in completed:
        plan_id = str(plan.get("id") or "")
        if not plan_id or plan_id in existing:
            continue
        executions = [
            item
            for item in lab.get("executions", [])
            if isinstance(item, dict)
            and item.get("plan_id") == plan_id
            and item.get("matched_prediction") is True
        ]
        if not executions:
            continue
        if any(
            int(item.get("cycle", 0) or 0) < started_cycle
            for item in executions
        ):
            continue
        execution_cycles = {
            int(item.get("cycle", 0) or 0)
            for item in executions
        }
        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            if int(episode.get("cycle", 0) or 0) not in execution_cycles:
                continue
            payload = _planning_payload(episode)
            if payload is not None and payload.get("plan_id") == plan_id:
                identifier = str(episode.get("id") or "")
                if identifier:
                    protected.add(identifier)
    return protected


def pending_world_episode_ids(state: dict[str, Any]) -> set[str]:
    snapshots = state.get("environment_snapshots", [])
    world = state.get("world_model") or {}
    start = min(
        int(world.get("last_snapshot_index", 0) or 0),
        len(snapshots),
    )
    pending_cycles = {
        int(snapshot.get("cycle", state.get("cycles", 0)) or 0)
        for snapshot in snapshots[start:]
        if isinstance(snapshot, dict)
    }
    if not pending_cycles:
        return set()
    return {
        str(episode.get("id"))
        for episode in state.get("episodes", [])
        if isinstance(episode, dict)
        and episode.get("kind") == "environment"
        and int(episode.get("cycle", 0) or 0) in pending_cycles
        and episode.get("id")
    }


def derive_protection(
    state: dict[str, Any],
    *,
    hot_suffix: int,
) -> dict[str, Any]:
    if type(hot_suffix) is not int or hot_suffix < 0:
        raise ValueError("hot_suffix must be a non-negative integer")
    episodes = [
        item
        for item in state.get("episodes", [])
        if isinstance(item, dict)
    ]
    ids = [str(item.get("id") or "") for item in episodes]
    if len(ids) != len(set(ids)):
        raise ValueError("episode ledger contains duplicate identities")
    opaque = [identifier for identifier in ids if not EPISODE_ID.fullmatch(identifier)]
    if opaque:
        raise ValueError(
            "archive eligibility refuses opaque episode identities: "
            + ", ".join(opaque[:8])
        )

    external = explicit_external_refs(state)
    explicit = {
        identifier
        for values in external.values()
        for identifier in values
    }
    available_ids = set(ids)
    missing_external = sorted(explicit - available_ids)
    if missing_external:
        raise ValueError(
            "state already contains missing external episode refs: "
            + ", ".join(missing_external[:8])
        )

    hot = set(ids[-hot_suffix:]) if hot_suffix > 0 else set()
    planning = pending_planning_episode_ids(state)
    world = pending_world_episode_ids(state)
    current_cycle = int(state.get("cycles", 0) or 0)
    current_cycle_ids = {
        str(item.get("id"))
        for item in episodes
        if int(item.get("cycle", 0) or 0) >= current_cycle - 1
        and item.get("id")
    }
    protected = explicit | hot | planning | world | current_cycle_ids
    eligible = [
        item
        for item in episodes
        if str(item.get("id")) not in protected
    ]
    return {
        "episode_count": len(episodes),
        "external_ref_occurrences": sum(len(values) for values in external.values()),
        "external_unique_refs": len(explicit),
        "external_ref_paths": {
            path: len(values)
            for path, values in sorted(external.items())
        },
        "hot_suffix_count": len(hot),
        "pending_planning_count": len(planning),
        "pending_world_count": len(world),
        "current_cycle_protected_count": len(current_cycle_ids),
        "protected_count": len(protected),
        "eligible_count": len(eligible),
        "protected_ids": sorted(protected),
        "eligible_ids": [str(item.get("id")) for item in eligible],
    }
