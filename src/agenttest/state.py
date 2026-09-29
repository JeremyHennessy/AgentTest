from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DIMENSIONS = (
    "continuity",
    "memory",
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
        "schema_version": 1,
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
            ],
            "limitations": [
                "No external perception unless observations are supplied.",
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


class StateStore:
    def __init__(self, path: str | Path = "state/organism.json") -> None:
        self.path = Path(path)
        self.journal_path = self.path.parent / "journal.jsonl"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return initial_state()
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
