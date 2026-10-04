from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_VERSION
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION

from normalized_inquiry_objectives import rank_normalized_candidates
from normalized_relation_evidence import (
    normalized_evidence,
    normalized_relation_candidates,
)


def stage_information_gain_inquiry(
    core: AgentCore,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Stage the verified temporal information-gain winner through public APIs.

    Action-association winners are deliberately not translated here because the
    public evidence contract's confirmation/refutation semantics for normalized
    two-exposure associations have not been separately defined.
    """
    evidence_table = normalized_evidence(observations)
    candidates = normalized_relation_candidates(evidence_table)
    ranked = rank_normalized_candidates(candidates, "information_gain")
    winner = next(item for item in ranked if item["eligible"])
    relation_candidate = winner["candidate"]

    if relation_candidate["relation"] not in {
        "same_next_observation",
        "changes_next_observation",
    }:
        raise ValueError(
            "public pipeline currently supports only normalized temporal relations"
        )

    relation = {
        "kind": relation_candidate["relation"],
        "feature": relation_candidate["feature"],
        "action": None,
        "comparison_status": "not_applicable",
    }
    observation_refs = [
        str(item.get("observation_id"))
        for item in observations
        if item.get("observation_id")
    ]
    normalized_payload = {
        "version": NATIVE_EVIDENCE_VERSION,
        "relation": relation,
        "observation_refs": observation_refs,
        "evaluable": int(relation_candidate["evaluable"]),
        "confirmations": int(relation_candidate["confirmations"]),
        "refutations": int(relation_candidate["refutations"]),
        "action_present": None,
        "action_absent": None,
    }
    evidence_result = core.record_native_evidence(
        normalized_payload,
        enabled=True,
        persist=True,
    )

    feature = relation_candidate["feature"]
    if relation_candidate["relation"] == "same_next_observation":
        hypothesis = (
            f"Observed {feature} tends to remain stable across consecutive "
            "evaluable observations."
        )
        falsification = (
            f"A later evaluable {feature} value that differs counts against stability."
        )
        predicted = f"The next evaluable {feature} observation matches the prior value."
    else:
        hypothesis = (
            f"Observed {feature} tends to change across consecutive evaluable observations."
        )
        falsification = (
            f"A later evaluable {feature} value that remains the same counts against change."
        )
        predicted = f"The next evaluable {feature} observation differs from the prior value."

    inquiry = {
        "version": NATIVE_INQUIRY_VERSION,
        "id": f"NIC:public:{relation_candidate['id']}",
        "objective": "information_gain",
        "objective_score": float(winner["score"]),
        "relation": relation,
        "question": (
            f"What next observation would most directly test whether {feature} "
            f"{'remains stable' if relation['kind'] == 'same_next_observation' else 'changes'}?"
        ),
        "hypothesis": hypothesis,
        "method": (
            f"Collect one later legitimate {feature} observation and compare it "
            "with the prior measured value."
        ),
        "falsification": falsification,
        "predicted_observation": predicted,
        "evidence_refs": [evidence_result["evidence_ref"]],
    }
    inquiry_result = core.propose_native_inquiry(
        inquiry,
        enabled=True,
        persist=True,
    )
    return {
        "winner": deepcopy(winner),
        "evidence_result": evidence_result,
        "inquiry_result": inquiry_result,
    }
