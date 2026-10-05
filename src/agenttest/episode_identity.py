"""Persistent episode numbering; this module grants no retention authority.

The watermark must be migrated and saved before any later archival scheme can
remove records. Missing metadata cannot recover history that was already lost.
"""
from __future__ import annotations

import re
from typing import Any

EPISODE_SEQUENCE_FIELD = "next_episode_index"
_NUMERIC_EPISODE_ID = re.compile(r"E([0-9]+)\Z")


def ensure_episode_sequence(state: dict[str, Any]) -> int:
    """Preserve a valid watermark and advance it past every retained episode.

    Historical records and reference strings are never rewritten. Duplicate
    IDs and corrupt metadata fail closed rather than being silently repaired.
    This is a single-writer contract, not a distributed sequence allocator.
    """
    index = state.get(EPISODE_SEQUENCE_FIELD, 1)
    if type(index) is not int or index < 1:
        raise ValueError("next_episode_index must be a positive integer")
    episodes = state.get("episodes", [])
    if not isinstance(episodes, list):
        raise ValueError("episode ledger must be a list")
    seen: set[str] = set()
    for episode in episodes:
        if not isinstance(episode, dict):
            raise ValueError("episode ledger entries must be objects")
        identifier = episode.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("episode identity must be a non-empty string")
        if identifier in seen:
            raise ValueError(f"duplicate episode identity: {identifier}")
        seen.add(identifier)
        match = _NUMERIC_EPISODE_ID.fullmatch(identifier)
        if match:
            index = max(index, int(match.group(1)) + 1)
    # Retain legacy numbering when opaque historical IDs occupy ledger slots.
    index = max(index, len(episodes) + 1)
    state[EPISODE_SEQUENCE_FIELD] = index
    return index


def allocate_episode_id(state: dict[str, Any]) -> str:
    """Reserve an ID in this state; persistence belongs to the caller's save."""
    index = ensure_episode_sequence(state)
    state[EPISODE_SEQUENCE_FIELD] = index + 1
    return f"E{index:06d}"
