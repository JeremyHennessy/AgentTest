from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore

from world2_native_agentcore_proposal import propose_native_question_candidate
from world2_native_endogenous import choose_native_intention

HARNESS_VERSION = "world2-native-core-harness-v0"


def run_native_core_proposal_path(state: dict[str, Any]) -> dict[str, Any]:
    """Use copied state and Core's existing private question/experiment machinery only."""
    working = deepcopy(state)
    candidate = propose_native_question_candidate(working)
    if candidate is None:
        return {"version": HARNESS_VERSION, "status": "no_candidate"}

    core = AgentCore.__new__(AgentCore)
    native_intention = choose_native_intention(working)
    intention = {
        "id": f"NI{len(working.get('intentions', [])) + 1:06d}",
        "cycle": int(working.get("cycles", 0) or 0),
        "kind": "reduce_uncertainty",
        "dominant_drive": native_intention["dominant_drive"],
        "strength": native_intention["strength"],
        "target": None,
        "rationale": "Isolated native candidate supplied by persisted native evidence and drive competition.",
        "evidence_refs": list(candidate.get("evidence_refs", [])),
    }
    working.setdefault("intentions", []).append(intention)

    question_text = core._generate_question(
        working,
        None,
        intention,
        candidate,
        strict_question_attention=False,
    )
    question = core._upsert_question(working, question_text)
    question["source"] = "world2_native_endogenous"
    question["source_evidence_refs"] = list(candidate.get("evidence_refs", []))
    experiment = core._select_or_propose_experiment(
        working,
        question,
        intention,
        candidate,
        require_grounded=True,
    )
    return {
        "version": HARNESS_VERSION,
        "status": "proposed" if experiment is not None else "not_proposed",
        "candidate": deepcopy(candidate),
        "intention": deepcopy(intention),
        "question": deepcopy(question),
        "experiment": deepcopy(experiment),
        "state": working,
    }
