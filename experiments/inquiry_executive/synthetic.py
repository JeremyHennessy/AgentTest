"""Tiny deterministic copied sources for transaction tests only.

These are deliberately authored synthetic controls, never historical or natural
selection evidence. No selector output is injected or mocked. The actual Core
will still generate a legacy question, rank its actual eligible competitors,
select a foreground thread, and return its actual routed experiment.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.core import AgentCore
from agenttest.state import DIMENSIONS, initial_state
from challenge_shadow_recorder import ChallengeShadowRecorder, source_manifest
from native_observe_inquire_integration import observe_and_inquire_policy, stage_publication_inquiry
from normalized_inquiry_objectives import rank_normalized_candidates
from open_object_world_challenge import initial_world, observe_world, transition

from .bridge import MemoryStore

FIXTURE_VERSION = "inquiry-executive-synthetic-v1"
FIXTURE_TIME = "2026-10-07T00:00:00+00:00"
PREFIX_COMMANDS = ({"action": "north"}, {"action": "south"}, {"action": "inspect", "target": "O002"})
TWO_INQUIRY_COMMANDS = ({"action": "inspect", "target": "O002"},) * 3 + ({"action": "north"}, {"action": "south"})


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode() + b"\n"


def _fixed_times(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"time", "created_at", "updated_at"} and isinstance(child, str):
                value[key] = FIXTURE_TIME
            else:
                _fixed_times(child)
    elif isinstance(value, list):
        for child in value:
            _fixed_times(child)


def proposal(question_id: str, experiment_id: str, hypotheses: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """An admission request, not a selected owner or executable capability."""
    return {
        "question_id": question_id,
        "experiment_id": experiment_id,
        "hypotheses": deepcopy(hypotheses if hypotheses is not None else [
            {"id": "same", "explanation": "The selected public value remains unchanged for this command and context.",
             "scope": "This observed command/context pair only; no causal or transfer claim.",
             "prediction": {"kind": "equal", "values": []}},
            {"id": "different", "explanation": "The selected public value changes for this command and context.",
             "scope": "This observed command/context pair only; no causal or transfer claim.",
             "prediction": {"kind": "different", "values": []}},
        ]),
    }


def _close_legacy_templates(state: dict[str, Any], core: AgentCore, target_id: str) -> list[str]:
    # All are distinct, already closed synthetic questions. The bridge neither
    # knows about these rows nor removes candidates to obtain the positive case.
    texts = [
        f"What obtainable evidence would resolve pending experiment {target_id} with the least additional assumption?",
        "Which assumption in my current decision process has gone longest without an attempt to falsify it?",
        *[f"What smallest reversible experiment could increase {name} without reducing reproducibility?" for name in DIMENSIONS],
    ]
    ranked = sorted(state["concept_counts"].items(), key=lambda item: (item[1], item[0]))
    if len(ranked) >= 2:
        texts.append(f"What observation could distinguish whether {ranked[0][0]} and {ranked[1][0]} are meaningfully related rather than merely co-occurring?")
    closed = []
    for text in texts:
        question = core._upsert_question(state, text)
        question["status"] = "closed"
        closed.append(question["id"])
    return closed


def create_sources(directory: str | Path, *, case: str = "winner") -> dict[str, Any]:
    """Write fresh synthetic input files and return their paths and provenance.

    winner: a valid native contract wins real ordinary competition. unmapped:
    the same grounded inquiry faces open legacy competition, yielding an
    ordinary winner with no native ownership. no_decision: the initial Ora
    state has fewer than two eligible questions after ordinary generation.
    two_inquiries: two distinct features were actually the top publication at
    prefix cycles 3 and 5. Their proposals identify those exact source frames.
    Ordinary routing may still defer the second selected inquiry, truthfully.
    No fixture invokes Core.cycle; the test invokes the one real bridge cycle.
    """
    if case not in {"winner", "unmapped", "no_decision", "two_inquiries"}:
        raise ValueError("unknown synthetic fixture case")
    root = Path(directory).absolute()
    if root != root.resolve():
        raise ValueError("synthetic fixture directory cannot be an alias")
    root.mkdir(parents=True, exist_ok=True)
    paths = {name: root / f"synthetic-{name}.json" for name in ("ora", "world", "observations")}
    if any(path.exists() for path in paths.values()):
        raise ValueError("synthetic fixtures require fresh source paths")
    # A benign file exists for the historical recorder's copied-store guard.
    # The recorder uses only MemoryStore; it cannot write this source file.
    state = initial_state()
    state["created_at"] = state["updated_at"] = FIXTURE_TIME
    memory = MemoryStore(state, paths["ora"])
    with paths["ora"].open("xb") as handle:
        handle.write(_canonical(state))
    recorder = ChallengeShadowRecorder(memory, enabled=True)
    world = initial_world(1)
    observation = observe_world(world)
    prefix = [{"observation": observation, "receipt": None}]
    recorder.ingest(observation)
    primary = competitor = None
    commands = TWO_INQUIRY_COMMANDS if case == "two_inquiries" else PREFIX_COMMANDS
    for cycle, command in enumerate(commands, start=1):
        world, receipt = transition(world, deepcopy(command), cycle=cycle)
        observation = observe_world(world)
        prefix.append({"observation": observation, "receipt": receipt})
        recorder.ingest(observation, receipt)
        if case == "two_inquiries" and cycle in (3, 5):
            staged = stage_publication_inquiry(AgentCore(memory), policy=observe_and_inquire_policy(),
                source_manifest=source_manifest(), publication=recorder.publication())["inquiry_result"]
            if cycle == 3:
                primary = staged
            else:
                competitor = staged

    closed: list[str] = []
    if case not in {"no_decision", "two_inquiries"}:
        core = AgentCore(memory)
        first_publication = recorder.publication()
        primary = stage_publication_inquiry(core, policy=observe_and_inquire_policy(),
            source_manifest=source_manifest(), publication=first_publication)["inquiry_result"]
        if case == "winner":
            # Select another genuinely observed feature for a passive competitor,
            # retaining its actual public measurements and normalized score.
            other = next(row for row in rank_normalized_candidates(recorder.temporal_candidates(), "information_gain")
                         if row["eligible"] and row["candidate"]["feature"] != first_publication["selected_temporal_candidate"]["feature"])
            candidate = other["candidate"]
            second_publication = deepcopy(first_publication)
            second_publication["selected_temporal_candidate"] = {
                "relation": candidate["relation"], "feature": candidate["feature"],
                "objective": "information_gain", "objective_score": other["score"],
                **{name: candidate[name] for name in ("evaluable", "confirmations", "refutations")},
            }
            competitor = stage_publication_inquiry(core, policy=observe_and_inquire_policy(),
                source_manifest=source_manifest(), publication=second_publication)["inquiry_result"]
            state = memory.load()
            # Authored synthetic prior-selection counters give several later
            # ordinary cycles room to exercise stable identity across frames.
            # These counters are not observations or scientific evidence.
            state["cycles"] = state["generation"] = 8
            second = next(q for q in state["questions"] if q["id"] == competitor["question"]["id"])
            second["times_selected"] = 8
            second["last_selected_cycle"] = 8
            closed = _close_legacy_templates(state, core, primary["experiment"]["id"])
            memory.save(state)
    if case == "two_inquiries":
        state = memory.load()
        state["cycles"] = state["generation"] = 8
        closed = _close_legacy_templates(state, AgentCore(memory), primary["experiment"]["id"])
        memory.save(state)
    state = memory.load()
    _fixed_times(state)
    paths["ora"].write_bytes(_canonical(state))
    for key, value in (("world", world), ("observations", prefix)):
        with paths[key].open("xb") as handle:
            handle.write(_canonical(value))
    details = {
        "label": "synthetic_control", "version": FIXTURE_VERSION, "case": case,
        "seed": 1, "synthetic_prefix_actions": list(deepcopy(commands)),
        "synthetic_prefix_action_count": len(commands),
        "ordinary_cycles_run_during_fixture_creation": 0,
        "fixed_timestamp": FIXTURE_TIME,
        "closed_legacy_question_ids": closed,
        "authored_prior_cycle": 8 if case in {"winner", "two_inquiries"} else 0,
        "competitor_prior_selections": 8 if case == "winner" else 0,
        "competitor_binding": "distinct_retained_actual_publication" if case == "two_inquiries" else "unbound_synthetic_competitor" if case == "winner" else None,
        "selector_overrides": False,
        "scientific_scope": "Transaction plumbing only; no spontaneous inquiry formation, natural retained-state selection, learning, or causal claim.",
        "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
    }
    primary_proposal = proposal(primary["question"]["id"], primary["experiment"]["id"]) if primary else None
    competitor_proposal = None
    if case == "two_inquiries":
        primary_proposal["origin_frame_sequence"] = 4
        competitor_proposal = proposal(competitor["question"]["id"], competitor["experiment"]["id"])
        competitor_proposal["origin_frame_sequence"] = 6
    return {
        **paths,
        "question_id": primary["question"]["id"] if primary else None,
        "experiment_id": primary["experiment"]["id"] if primary else None,
        "proposal": primary_proposal,
        "competitor_proposal": competitor_proposal,
        "provenance": details,
    }
