"""Future OD numbering and honest lookup of retained objective provenance.

Historical rows/citations are never rewritten. Missing bounded history is
unavailable evidence; duplicate identities remain quarantined after retention.
This is the existing single-writer state-save contract, not a transaction fix.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

_NUMERIC_OD = re.compile(r"OD([0-9]+)\Z")


def _sequence(value: Any) -> int | None:
    match = _NUMERIC_OD.fullmatch(value) if isinstance(value, str) else None
    return int(match[1]) if match and int(match[1]) > 0 else None


def ensure_objective_identity(lab: dict[str, Any]) -> int:
    index = lab.get("next_objective_decision_index", 1)
    if type(index) is not int or index < 1:
        raise ValueError("next_objective_decision_index must be a positive integer")
    quarantine = lab.get("objective_decision_ambiguous_ids", [])
    if not isinstance(quarantine, list) or any(not isinstance(v, str) or not v for v in quarantine):
        raise ValueError("objective_decision_ambiguous_ids must contain nonempty identities")
    rows = lab.get("objective_decisions", [])
    if not isinstance(rows, list):
        raise ValueError("objective_decisions must be a list")
    counts = Counter(row.get("id") for row in rows if isinstance(row, dict)
                     and isinstance(row.get("id"), str) and row["id"])
    ambiguous = set(quarantine) | {key for key, count in counts.items() if count > 1}
    observed = list(counts) + list(ambiguous)
    for goal in lab.get("goals", []):
        selection = goal.get("selection") if isinstance(goal, dict) else None
        if isinstance(selection, dict):
            observed.append(selection.get("objective_decision_id"))
    for collection in ("objective_realization_decisions", "objective_realizations"):
        for row in lab.get(collection, []):
            if isinstance(row, dict):
                observed.append(row.get("objective_decision_id"))
    sequences = [n for n in (_sequence(value) for value in observed) if n is not None]
    index = max(index, max(sequences, default=0) + 1, len(rows) + 1)
    # Commit additive metadata only after all validation/computation succeeds.
    lab["next_objective_decision_index"] = index
    lab["objective_decision_ambiguous_ids"] = sorted(ambiguous)
    return index


def allocate_objective_decision_id(lab: dict[str, Any]) -> str:
    index = ensure_objective_identity(lab)
    lab["next_objective_decision_index"] = index + 1
    return f"OD{index:06d}"


def resolve_objective_decision(lab: dict[str, Any], identifier: Any) -> dict[str, Any]:
    """Read-only tagged lookup; no first/last-record winner is permitted."""
    if not isinstance(identifier, str) or not identifier:
        return {"status": "invalid", "match_count": 0, "record": None}
    matches = [row for row in lab.get("objective_decisions", [])
               if isinstance(row, dict) and row.get("id") == identifier]
    if identifier in lab.get("objective_decision_ambiguous_ids", []) or len(matches) > 1:
        status = "ambiguous"
    else:
        status = "unique" if len(matches) == 1 else "unavailable"
    return {"status": status, "match_count": len(matches),
            "record": matches[0] if status == "unique" else None}
