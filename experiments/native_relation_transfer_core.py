from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore

from native_relation_discovery import grounded_relation_candidate
from native_relation_family_memory import rank_held_out_proposals


def run_held_out_relation_core_path(
    state: dict[str, Any], proposals: list[dict[str, Any]]
) -> dict[str, Any]:
    ranked = rank_held_out_proposals(state, proposals)
    if not ranked:
        return {"status": "no_candidate"}
    top = ranked[0]
    pseudo_selected = {
        "proposal": deepcopy(top["proposal"]),
        "evaluable": int(top["family_evidence"]["evaluable"]),
        "confirmations": int(top["family_evidence"]["confirmations"]),
        "refutations": int(top["family_evidence"]["refutations"]),
        "support": None,
        "status": "mixed" if top["family_evidence"]["refutations"] else "supported",
    }
    candidate = grounded_relation_candidate(pseudo_selected)
    working = deepcopy(state)
    core = AgentCore.__new__(AgentCore)
    intention = {
        "id": f"TRI{len(working.get('intentions', [])) + 1:06d}",
        "cycle": int(working.get("cycles", 0) or 0),
        "kind": "reduce_uncertainty",
        "dominant_drive": "uncertainty",
        "strength": min(1.0, float(top["score"])),
        "target": None,
        "rationale": "Held-out relation prioritized by persisted family evidence.",
        "evidence_refs": [],
    }
    working.setdefault("intentions", []).append(intention)
    text = core._generate_question(working, None, intention, candidate)
    question = core._upsert_question(working, text)
    question["source"] = "native_relation_family_transfer"
    experiment = core._select_or_propose_experiment(
        working, question, intention, candidate, require_grounded=True
    )
    return {
        "status": "proposed" if experiment else "not_proposed",
        "ranked": ranked,
        "selected": top,
        "candidate": candidate,
        "question": deepcopy(question),
        "experiment": deepcopy(experiment),
    }
