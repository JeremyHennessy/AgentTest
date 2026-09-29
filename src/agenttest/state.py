from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 11

DIMENSIONS = (
    "continuity",
    "memory",
    "semantic_memory",
    "perception",
    "world_model",
    "cognition",
    "self_model",
    "curiosity",
    "agency",
    "learning",
    "adaptation",
    "reflection",
    "open_endedness",
    "reproducibility",
)


CAPABILITY_CATALOG = (
    "persistent structured state",
    "append-only event journal",
    "deterministic semantic consolidation with source episode references",
    "temporal world claims that preserve superseded observed values",
    "question generation from accumulated concepts",
    "selection of explicit falsifiable experiments",
    "narrow repository self-perception through auditable sensors",
    "one-step prediction of measured repository state",
    "endogenous evidence-driven intention selection",
    "validated boundary for optional model-generated candidate thoughts",
    "evidence-backed self-authored change manifests without code execution",
    "proposal review that distinguishes direct problem evidence from measurement gaps",
    "verified non-mutating diagnostics that can resolve measurement gaps",
    "intervention-aware prediction using a non-state repository baseline fingerprint",
    "verified read-only self-model grounding diagnostics",
    "evidence-grounded self-model calibration with explicit uncertainty",
    "baseline-scoped diagnostic re-evaluation after interventions",
)

LIMITATION_CATALOG = (
    "Self-authored change manifests cannot apply or merge code.",
    "Governance and preservation files are excluded from self-authored changes.",
    "Proposal review can withhold patch authority when evidence does not identify the failing layer.",
    "Diagnostic authority is limited to verified harnesses running on isolated or read-only state.",
    "Repository intervention detection identifies changed content but does not infer why it changed.",
    "Self-model calibration records evidence status but does not prove unverified capabilities.",
    "Semantic memory is lexical and co-occurrence based rather than embedding based.",
    "The world model currently represents only directly derived repository and evaluation claims.",
    "Perception is limited to explicitly implemented auditable sensors.",
    "Model cognition is optional and its output is untrusted until validated.",
    "Model cognition cannot directly modify evidence, metrics, tools, or code.",
    "Environmental actions are not independently executed.",
    "No evidence currently establishes consciousness or subjective experience.",
    "Code changes are proposals until independently evaluated.",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_semantic_memory() -> dict[str, Any]:
    return {
        "last_episode_index": 0,
        "concepts": {},
        "associations": {},
    }


def _empty_world_model() -> dict[str, Any]:
    return {
        "claims": [],
        "current": {},
        "last_snapshot_index": 0,
        "seen_prediction_status": {},
        "seen_experiment_status": {},
    }


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
        "semantic_memory": _empty_semantic_memory(),
        "environment_snapshots": [],
        "surprises": [],
        "predictions": [],
        "intentions": [],
        "drives": {},
        "world_model": _empty_world_model(),
        "cognition_events": [],
        "cognition_candidates": [],
        "questions": [],
        "experiments": [],
        "change_proposals": [],
        "proposal_reviews": [],
        "proposal_diagnostics": [],
        "reflections": [],
        "accepted_changes": [],
        "self_model": {
            "capabilities": list(CAPABILITY_CATALOG),
            "limitations": list(LIMITATION_CATALOG),
            "last_updated_cycle": 0,
        },
        "metrics": {dimension: 0.0 for dimension in DIMENSIONS},
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def migrate_state(state: dict[str, Any]) -> dict[str, Any]:
    for key, default in (
        ("semantic_memory", _empty_semantic_memory()),
        ("environment_snapshots", []),
        ("surprises", []),
        ("predictions", []),
        ("intentions", []),
        ("drives", {}),
        ("world_model", _empty_world_model()),
        ("cognition_events", []),
        ("cognition_candidates", []),
        ("episodes", []),
        ("questions", []),
        ("experiments", []),
        ("change_proposals", []),
        ("proposal_reviews", []),
        ("proposal_diagnostics", []),
        ("reflections", []),
        ("accepted_changes", []),
        ("concept_counts", {}),
    ):
        state.setdefault(key, default)

    semantic = state["semantic_memory"]
    semantic.setdefault("last_episode_index", 0)
    semantic.setdefault("concepts", {})
    semantic.setdefault("associations", {})

    world = state["world_model"]
    world.setdefault("claims", [])
    world.setdefault("current", {})
    world.setdefault("last_snapshot_index", 0)
    world.setdefault("seen_prediction_status", {})
    world.setdefault("seen_experiment_status", {})

    metrics = state.setdefault("metrics", {})
    for dimension in DIMENSIONS:
        metrics.setdefault(dimension, 0.0)

    self_model = state.setdefault("self_model", {})
    existing_capabilities = [
        str(capability)
        for capability in self_model.get("capabilities", [])
        if str(capability).strip()
    ]
    self_model["capabilities"] = list(
        dict.fromkeys([*existing_capabilities, *CAPABILITY_CATALOG])
    )

    existing_limitations = [
        str(limitation)
        for limitation in self_model.get("limitations", [])
        if str(limitation).strip()
    ]
    self_model["limitations"] = list(
        dict.fromkeys([*existing_limitations, *LIMITATION_CATALOG])
    )

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
