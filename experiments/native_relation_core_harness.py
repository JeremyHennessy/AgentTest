from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore

from native_relation_discovery import (
    evaluate_relations,
    grounded_relation_candidate,
    propose_relations,
    select_relation_inquiry,
)


def run_relation_core_path(
    state: dict[str, Any], observations: list[dict[str, Any]]
) -> dict[str, Any]:
    proposals = propose_relations(observations)
    ledger = evaluate_relations(proposals, observations)
    selected = select_relation_inquiry(ledger)
    candidate = grounded_relation_candidate(selected)
    if candidate is None:
        return {"status": "no_candidate", "ledger": ledger}

    working = deepcopy(state)
    core = AgentCore.__new__(AgentCore)
    dominant = (
        "prediction_error"
        if selected["status"] in {"challenged", "mixed"}
        else "evidence_hunger"
    )
    intention = {
        "id": f"NRI{len(working.get('intentions', [])) + 1:06d}",
        "cycle": int(working.get("cycles", 0) or 0),
        "kind": "reduce_uncertainty",
        "dominant_drive": dominant,
        "strength": 1.0 if dominant == "prediction_error" else 0.5,
        "target": None,
        "rationale": "Compositional native relation selected from observable contradiction/evidence.",
        "evidence_refs": [],
    }
    working.setdefault("intentions", []).append(intention)
    question_text = core._generate_question(working, None, intention, candidate)
    question = core._upsert_question(working, question_text)
    question["source"] = "native_relation_discovery"
    experiment = core._select_or_propose_experiment(
        working, question, intention, candidate, require_grounded=True
    )
    return {
        "status": "proposed" if experiment else "not_proposed",
        "ledger": ledger,
        "selected": selected,
        "candidate": candidate,
        "intention": intention,
        "question": deepcopy(question),
        "experiment": deepcopy(experiment),
        "state": working,
    }
