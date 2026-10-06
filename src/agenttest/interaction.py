from __future__ import annotations

import re
from typing import Any

from .core import AgentCore, _calibrate_self_model
from .semantic import retrieve_semantic_memory
from .state import StateStore, utc_now
from .world import current_world_claims


def _latest_stimulus_episode(
    state: dict[str, Any],
    cycle: int,
    content: str,
) -> dict[str, Any] | None:
    for episode in reversed(state.get("episodes", [])):
        if (
            episode.get("cycle") == cycle
            and episode.get("kind") == "stimulus"
            and episode.get("content") == content
        ):
            return episode
    return None


def _self_model_view(state: dict[str, Any]) -> dict[str, Any]:
    self_model = state.get("self_model", {})
    claims = self_model.get("capability_claims", {})
    observed = []
    verified = []
    unverified = []

    if isinstance(claims, dict):
        for capability, claim in claims.items():
            if not isinstance(claim, dict):
                continue
            status = claim.get("status")
            row = {
                "capability": capability,
                "status": status,
                "evidence_refs": list(claim.get("evidence_refs", [])),
            }
            if status == "unverified":
                row["reason"] = claim.get("reason")
                unverified.append(row)
            elif status == "verified":
                verified.append(row)
            elif status == "observed":
                observed.append(row)

    return {
        "verified": verified,
        "observed": observed,
        "unverified": unverified,
        "coverage": self_model.get("calibration", {}).get("coverage"),
    }


def _render_response(
    *,
    cycle_result: dict[str, Any],
    prior_memory: list[dict[str, Any]],
    self_model: dict[str, Any],
    cognition_event: dict[str, Any] | None,
) -> str:
    intention = cycle_result.get("intention") or {}
    question = cycle_result.get("question") or {}
    experiment = cycle_result.get("experiment") or {}
    drives = cycle_result.get("drives") or {}

    dominant = intention.get("dominant_drive")
    strength = intention.get("strength")
    intention_kind = intention.get("kind")

    memory_names = [
        str(item.get("concept"))
        for item in prior_memory[:4]
        if item.get("concept")
    ]
    memory_clause = (
        "Prior memory brought up: " + ", ".join(memory_names) + "."
        if memory_names
        else "No strong prior semantic match was retrieved."
    )

    cognition_clause = ""
    if cognition_event is not None:
        status = cognition_event.get("status")
        if status == "unavailable":
            cognition_clause = (
                " Model-backed cognition was unavailable, so this response uses only "
                "the deterministic evidence loop."
            )
        elif status == "rejected":
            cognition_clause = (
                " A model candidate was rejected by the grounding boundary and was not "
                "used as evidence."
            )
        elif status == "accepted":
            cognition_clause = (
                " A grounded model candidate was accepted as a proposal, not as fact."
            )
        elif status == "error":
            cognition_clause = (
                " Model-backed cognition errored, so the deterministic loop continued."
            )

    unverified_count = len(self_model.get("unverified", []))
    strength_text = (
        f"{float(strength):.3f}"
        if isinstance(strength, (int, float))
        else "unknown"
    )
    return (
        f"I recorded your message in cycle {cycle_result.get('cycle')}. "
        f"My strongest current control pressure is {dominant or 'unknown'} "
        f"({strength_text}), selecting the intention {intention_kind or 'unknown'}. "
        f"{memory_clause} "
        f"The question this raised is: {question.get('text', 'none')}. "
        f"The current proposed test is: {experiment.get('method', 'none')}. "
        f"{unverified_count} self-model capability claims remain explicitly unverified."
        f"{cognition_clause}"
    )


def interact(
    message: str,
    *,
    store: StateStore | None = None,
    cognition: bool = False,
    cognition_provider=None,
    observation: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    clean = message.strip()
    if not clean:
        raise ValueError("interaction message must not be empty")

    store = store or StateStore()
    prior_state = store.load()
    if request_id is not None:
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[A-Za-z0-9:_-]{1,200}", request_id
        ):
            raise ValueError("interaction request_id must be a stable transport identifier")
        matching = [
            item
            for item in prior_state.get("interactions", [])
            if item.get("request_id") == request_id
        ]
        if matching:
            raise ValueError(f"interaction request already recorded: {request_id}")
    prior_memory = retrieve_semantic_memory(prior_state, clean, limit=6)
    prior_world_claims = current_world_claims(prior_state, limit=8)

    core = AgentCore(store)
    cycle_result = core.cycle(
        clean,
        observation=observation,
        cognition=cognition,
        cognition_provider=cognition_provider,
    )
    state = store.load()

    stimulus_episode = _latest_stimulus_episode(
        state,
        int(cycle_result["cycle"]),
        clean,
    )
    interaction_id = f"H{len(state.get('interactions', [])) + 1:06d}"
    if stimulus_episode is not None:
        stimulus_episode["source"] = "human_interaction"
        stimulus_episode["interaction_id"] = interaction_id

    cognition_event = cycle_result.get("cognition_event")

    record = {
        "id": interaction_id,
        "cycle": cycle_result["cycle"],
        "created_at": utc_now(),
        "input_episode_id": stimulus_episode.get("id") if stimulus_episode else None,
        "input": clean,
        "response_text": None,
        "intention_id": (cycle_result.get("intention") or {}).get("id"),
        "question_id": (cycle_result.get("question") or {}).get("id"),
        "experiment_id": (cycle_result.get("experiment") or {}).get("id"),
        "cognition_event_id": cognition_event.get("id") if cognition_event else None,
        "cognition_candidate_id": (
            (cycle_result.get("thought") or {}).get("id")
            if cycle_result.get("thought")
            else None
        ),
        "prior_memory_concepts": [
            item.get("concept")
            for item in prior_memory
            if item.get("concept")
        ],
        "prior_world_claim_refs": [
            claim.get("id")
            for claim in prior_world_claims
            if claim.get("id")
        ],
    }
    if request_id is not None:
        record["request_id"] = request_id
    state.setdefault("interactions", []).append(record)
    _calibrate_self_model(state)
    self_model = _self_model_view(state)
    response_text = _render_response(
        cycle_result=cycle_result,
        prior_memory=prior_memory,
        self_model=self_model,
        cognition_event=cognition_event,
    )
    record["response_text"] = response_text
    store.save(state)
    interaction_event = {
        "event": "human_interaction",
        "time": utc_now(),
        "cycle": cycle_result["cycle"],
        "interaction_id": interaction_id,
        "input_episode_id": record["input_episode_id"],
        "question_id": record["question_id"],
        "experiment_id": record["experiment_id"],
    }
    if request_id is not None:
        interaction_event["request_id"] = request_id
    store.append_journal(interaction_event)

    return {
        "interaction": record,
        "response_text": response_text,
        "memory": {
            "prior_semantic": prior_memory,
        },
        "world": {
            "prior_current_claims": prior_world_claims,
        },
        "self_model": self_model,
        "current": {
            "drives": cycle_result.get("drives"),
            "intention": cycle_result.get("intention"),
            "question": cycle_result.get("question"),
            "experiment": cycle_result.get("experiment"),
            "prediction": cycle_result.get("prediction"),
        },
        "cognition": {
            "event": cognition_event,
            "candidate": cycle_result.get("thought"),
        },
        "metrics": cycle_result.get("metrics"),
    }
