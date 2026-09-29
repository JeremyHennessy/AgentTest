from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

DIMENSIONS = (
    "continuity",
    "memory",
    "perception",
    "self_model",
    "curiosity",
    "agency",
    "learning",
    "adaptation",
    "reflection",
    "open_endedness",
    "reproducibility",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initial_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "designation": "Genesis-0",
            "chosen_name": None,
            "origin": "2026-09-29",
            "description": "A persistent experimental process, not a claim of consciousness.",
        },
        "cycles": 0,
        "generation": 0,
        "concept_counts": {},
        "episodes": [],
        "environment_snapshots": [],
        "surprises": [],
        "questions": [],
        "experiments": [],
        "reflections": [],
        "accepted_changes": [],
        "self_model": {
            "capabilities": [
                "persistent structured state",
                "append-only event journal",
                "question generation from accumulated concepts",
                "selection of explicit falsifiable experiments",
                "narrow repository self-perception through auditable sensors",
            ],
            "limitations": [
                "Perception is limited to explicitly implemented auditable sensors.",
                "No model-backed generative cognition is configured.",
                "No evidence currently establishes consciousness or subjective experience.",
                "Code changes are proposals until independently evaluated.",
            ],
            "last_updated_cycle": 0,
        },
        "metrics": {dimension: 0.0 for dimension in DIMENSIONS},
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def migrate_state(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("environment_snapshots", [])
    state.setdefault("surprises", [])
    state.setdefault("episodes", [])
    state.setdefault("questions", [])
    state.setdefault("experiments", [])
    state.setdefault("reflections", [])
    state.setdefault("accepted_changes", [])
    state.setdefault("concept_counts", {})

    metrics = state.setdefault("metrics", {})
    for dimension in DIMENSIONS:
        metrics.setdefault(dimension, 0.0)

    self_model = state.setdefault("self_model", {})
    capabilities = self_model.setdefault("capabilities", [])
    perception_capability = "narrow repository self-perception through auditable sensors"
    if perception_capability not in capabilities:
        capabilities.append(perception_capability)

    limitations = self_model.setdefault("limitations", [])
    old_limitation = "No external perception unless observations are supplied."
    if old_limitation in limitations:
        limitations.remove(old_limitation)
    new_limitation = "Perception is limited to explicitly implemented auditable sensors."
    if new_limitation not in limitations:
        limitations.append(new_limitation)

    state["schema_version"] = SCHEMA_VERSION
    return state


class StateStore:
    def __init__(self, path: str | Path = "state/organism.json") -> None:
        self.path = Path(path)
        self.journal_path = self.path.parent / "journal.jsonl"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return initial_state()
        with self.path.open("r", encoding="utf-8") as handle:
            return migrate_state(json.load(handle))

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = migrate_state(state)
        state["updated_at"] = utc_now()
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(self.path)

    def append_journal(self, event: dict[str, Any]) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
