from __future__ import annotations

from typing import Any


EVIDENCE_COLLECTIONS = (
    "episodes",
    "surprises",
    "predictions",
    "intentions",
    "questions",
    "experiments",
    "reflections",
    "cognition_events",
    "cognition_candidates",
    "proposal_reviews",
    "proposal_diagnostics",
)


def known_evidence_ids(state: dict[str, Any]) -> set[str]:
    """Return IDs allowed to ground manifests and cognition candidates.

    System diagnostics are admitted only when they are completed. This module is
    protected change-control authority so self-authored candidates cannot broaden
    their own evidence universe.
    """

    ids: set[str] = set()
    for key in EVIDENCE_COLLECTIONS:
        for item in state.get(key, []):
            identifier = item.get("id")
            if identifier:
                ids.add(str(identifier))

    for diagnostic in state.get("system_diagnostics", []):
        identifier = diagnostic.get("id")
        if identifier and diagnostic.get("status") == "completed":
            ids.add(str(identifier))

    for claim in state.get("world_model", {}).get("claims", []):
        identifier = claim.get("id")
        if identifier:
            ids.add(str(identifier))
    return ids
