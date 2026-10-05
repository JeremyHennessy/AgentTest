"""Purpose-scoped archive provenance read-through.

Research-only adapter. It can resolve historical/provenance records from hot
state or immutable archive segments without broadening AgentTest evidence
authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from agenttest.evidence import known_evidence_ids
from episode_archive_contract import EpisodeArchiveSegment

PROVENANCE_PURPOSES = frozenset({"historical_lookup", "provenance_lookup"})


class ArchiveProvenanceResolver:
    def __init__(
        self,
        state: dict[str, Any],
        segments: Iterable[EpisodeArchiveSegment],
    ) -> None:
        self._state = deepcopy(state)
        self._hot: dict[str, dict[str, Any]] = {}
        for item in self._state.get("episodes", []):
            if not isinstance(item, dict):
                continue
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier:
                continue
            if identifier in self._hot:
                raise ValueError(f"duplicate hot episode ID: {identifier}")
            self._hot[identifier] = deepcopy(item)

        self._segments = list(segments)
        locations: dict[str, list[EpisodeArchiveSegment]] = {}
        for segment in self._segments:
            for identifier in segment.archived_ids:
                locations.setdefault(identifier, []).append(segment)
        overlap = sorted(set(self._hot) & set(locations))
        if overlap:
            raise ValueError(
                "hot/archive episode overlap: " + ", ".join(overlap[:8])
            )
        ambiguous = sorted(
            identifier
            for identifier, owners in locations.items()
            if len(owners) != 1
        )
        if ambiguous:
            raise ValueError(
                "episode exists in multiple archive segments: "
                + ", ".join(ambiguous[:8])
            )
        self._archive_locations = {
            identifier: owners[0]
            for identifier, owners in locations.items()
        }
        self._hot_known_evidence = known_evidence_ids(self._state)

    def location(self, identifier: str) -> str | None:
        if identifier in self._hot:
            return "hot"
        if identifier in self._archive_locations:
            return "archive"
        return None

    def is_generic_evidence_known(self, identifier: str) -> bool:
        """Return current AgentTest authority only; archive membership adds none."""
        return identifier in self._hot_known_evidence

    def resolve(
        self,
        identifier: str,
        *,
        purpose: str,
    ) -> dict[str, Any] | None:
        if purpose not in PROVENANCE_PURPOSES:
            raise PermissionError(
                f"provenance resolver does not authorize purpose: {purpose}"
            )
        hot = self._hot.get(identifier)
        if hot is not None:
            return {
                "id": identifier,
                "location": "hot",
                "segment_id": None,
                "source_state_sha256": None,
                "record": deepcopy(hot),
            }
        segment = self._archive_locations.get(identifier)
        if segment is None:
            return None
        record = segment.lookup(identifier, purpose=purpose)
        if record is None:
            raise ValueError("archive location index disagrees with segment")
        return {
            "id": identifier,
            "location": "archive",
            "segment_id": segment.manifest["segment_id"],
            "source_state_sha256": segment.manifest[
                "source_state_sha256"
            ],
            "record": record,
        }

    def resolve_refs(
        self,
        identifiers: Iterable[str],
        *,
        purpose: str,
    ) -> list[dict[str, Any]]:
        resolved = []
        for identifier in identifiers:
            result = self.resolve(str(identifier), purpose=purpose)
            if result is None:
                raise KeyError(f"episode provenance is unavailable: {identifier}")
            resolved.append(result)
        return resolved
