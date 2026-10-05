from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .action_lab import initial_action_lab_state
from .episode_identity import ensure_episode_sequence, infer_episode_sequence_cursor
from .agenda import ensure_agenda_state, initial_agenda_state
from .planning_lab import initial_planning_lab_state

SCHEMA_VERSION = 25

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
    "verified read-only inquiry-family diagnostics",
    "persistent human interaction surface with evidence-linked responses",
)

LIMITATION_CATALOG = (
    "Self-authored change manifests cannot apply or merge code.",
    "Governance and preservation files are excluded from self-authored changes.",
    "Proposal review can withhold patch authority when evidence does not identify the failing layer.",
    "Diagnostic authority is limited to verified harnesses running on isolated or read-only state.",
    "Repository intervention detection identifies changed content but does not infer why it changed.",
    "Self-model calibration records evidence status but does not prove unverified capabilities.",
    "Inquiry-family diagnostics use deterministic lexical similarity and do not establish semantic equivalence in every context.",
    "Interaction replies are deterministic state renderings and do not imply subjective experience.",
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
        "last_episode_sequence": 0,
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


def _empty_empirical_learning() -> dict[str, Any]:
    return {
        "version": "empirical-learning-v1",
        "updated_cycle": 0,
        "families": {},
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
        "next_episode_index": 1,
        "semantic_memory": _empty_semantic_memory(),
        "environment_snapshots": [],
        "surprises": [],
        "predictions": [],
        "intentions": [],
        "drives": {},
        "world_model": _empty_world_model(),
        "empirical_learning": _empty_empirical_learning(),
        "action_lab": initial_action_lab_state(),
        "planning_lab": initial_planning_lab_state(),
        "agenda": initial_agenda_state(),
        "cognition_events": [],
        "cognition_candidates": [],
        "questions": [],
        "experiments": [],
        "change_proposals": [],
        "proposal_reviews": [],
        "proposal_diagnostics": [],
        "interactions": [],
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
    ensure_episode_sequence(state)
    prior_schema_version = int(state.get("schema_version", 0) or 0)
    for key, default in (
        ("semantic_memory", _empty_semantic_memory()),
        ("environment_snapshots", []),
        ("surprises", []),
        ("predictions", []),
        ("intentions", []),
        ("drives", {}),
        ("world_model", _empty_world_model()),
        ("empirical_learning", _empty_empirical_learning()),
        ("action_lab", initial_action_lab_state()),
        ("planning_lab", initial_planning_lab_state()),
        ("agenda", initial_agenda_state()),
        ("cognition_events", []),
        ("cognition_candidates", []),
        ("episodes", []),
        ("questions", []),
        ("experiments", []),
        ("change_proposals", []),
        ("proposal_reviews", []),
        ("proposal_diagnostics", []),
        ("interactions", []),
        ("reflections", []),
        ("accepted_changes", []),
        ("concept_counts", {}),
    ):
        state.setdefault(key, default)

    semantic = state["semantic_memory"]
    semantic.setdefault("last_episode_index", 0)
    if "last_episode_sequence" not in semantic:
        semantic["last_episode_sequence"] = infer_episode_sequence_cursor(
            state.get("episodes", []),
            int(semantic.get("last_episode_index", 0) or 0),
        )
    sequence_cursor = semantic.get("last_episode_sequence")
    if type(sequence_cursor) is not int or sequence_cursor < 0:
        raise ValueError("semantic last_episode_sequence must be a non-negative integer")
    semantic.setdefault("concepts", {})
    semantic.setdefault("associations", {})

    world = state["world_model"]
    world.setdefault("claims", [])
    world.setdefault("current", {})
    world.setdefault("last_snapshot_index", 0)
    world.setdefault("seen_prediction_status", {})
    world.setdefault("seen_experiment_status", {})

    empirical = state["empirical_learning"]
    empirical.setdefault("version", "empirical-learning-v1")
    empirical.setdefault("updated_cycle", 0)
    empirical.setdefault("families", {})

    action_lab = state["action_lab"]
    action_lab.setdefault("version", "bounded-action-lab-v1")
    action_lab.setdefault("bounds", 2)
    action_lab.setdefault("position", [0, 0])
    action_lab.setdefault("visit_counts", {"0,0": 1})
    action_lab.setdefault("history", [])
    action_lab.setdefault("learned_effects", {})
    action_lab.setdefault("last_action_cycle", None)

    planning_lab = state["planning_lab"]
    for key, value in initial_planning_lab_state().items():
        planning_lab.setdefault(key, value)
    if (
        prior_schema_version < 21
        and planning_lab.get("self_experiment_started_cycle") is None
        and int(state.get("cycles", 0) or 0) > 0
    ):
        planning_lab["self_experiment_started_cycle"] = int(
            state.get("cycles", 0) or 0
        )
    if (
        prior_schema_version < 22
        and planning_lab.get("objective_selection_started_cycle") is None
        and int(state.get("cycles", 0) or 0) > 0
    ):
        planning_lab["objective_selection_started_cycle"] = int(
            state.get("cycles", 0) or 0
        )
    if (
        prior_schema_version < 23
        and planning_lab.get("objective_realization_started_cycle") is None
        and int(state.get("cycles", 0) or 0) > 0
    ):
        planning_lab["objective_realization_started_cycle"] = int(
            state.get("cycles", 0) or 0
        )
    if (
        prior_schema_version < 24
        and planning_lab.get("outcome_valuation_started_cycle") is None
        and int(state.get("cycles", 0) or 0) > 0
    ):
        planning_lab["outcome_valuation_started_cycle"] = int(
            state.get("cycles", 0) or 0
        )

    agenda = ensure_agenda_state(state)
    if (
        prior_schema_version < 25
        and agenda.get("started_cycle") is None
        and int(state.get("cycles", 0) or 0) > 0
    ):
        agenda["started_cycle"] = int(state.get("cycles", 0) or 0)

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
