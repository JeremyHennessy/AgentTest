from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore
from normalized_inquiry_objectives import rank_normalized_candidates


def normalized_candidate(entry: dict[str, Any]) -> dict[str, Any]:
    candidate = entry["candidate"]
    relation = candidate["relation"]
    feature = candidate["feature"]
    if relation == "same_next_observation":
        hypothesis = f"Observable feature {feature} tends to remain stable across consecutive evaluable observations."
        falsification = f"A later evaluable observation where {feature} changes counts against stability."
    elif relation == "changes_next_observation":
        hypothesis = f"Observable feature {feature} tends to change across consecutive evaluable observations."
        falsification = f"A later evaluable observation where {feature} remains stable counts against change."
    else:
        action = candidate["action"]
        hypothesis = f"Observed action {action} is associated with a different subsequent change rate in feature {feature} than observations without that action."
        falsification = f"Additional comparable action-present/action-absent observations reduce the observed change-rate difference for {feature} toward zero."
    return {
        "id": "NIC-" + candidate["id"],
        "question": f"What next comparable observation would most directly test: {hypothesis}",
        "hypothesis": hypothesis,
        "experiment": "Collect another legitimately observable sample that improves the relevant comparison without exposing hidden world state.",
        "falsification": falsification,
        "predicted_observation": None,
    }


def run_normalized_core_path(
    state: dict[str, Any], candidates: list[dict[str, Any]], objective: str
) -> dict[str, Any]:
    ranked = rank_normalized_candidates(candidates, objective)
    eligible = [item for item in ranked if item["eligible"]]
    if not eligible:
        return {"status": "no_candidate", "objective": objective}
    winner = eligible[0]
    grounded = normalized_candidate(winner)
    working = deepcopy(state)
    core = AgentCore.__new__(AgentCore)
    intention = {
        "id": f"NNI{len(working.get('intentions', [])) + 1:06d}",
        "cycle": int(working.get("cycles", 0) or 0),
        "kind": "reduce_uncertainty",
        "dominant_drive": "uncertainty",
        "strength": min(1.0, float(winner["score"])),
        "target": None,
        "rationale": f"Normalized inquiry selected by {objective}.",
        "evidence_refs": [],
    }
    working.setdefault("intentions", []).append(intention)
    text = core._generate_question(working, None, intention, grounded)
    question = core._upsert_question(working, text)
    question["source"] = "normalized_inquiry_objective"
    experiment = core._select_or_propose_experiment(
        working, question, intention, grounded, require_grounded=True
    )
    return {
        "status": "proposed" if experiment else "not_proposed",
        "objective": objective,
        "winner": deepcopy(winner),
        "candidate": grounded,
        "question": deepcopy(question),
        "experiment": deepcopy(experiment),
    }
