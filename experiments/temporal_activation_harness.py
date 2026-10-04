from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore
from agenttest.native_activation import validate_native_activation_policy
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION


def activate_temporal_inquiry(
    core: AgentCore,
    *,
    policy: dict[str, Any],
    relation: str,
    feature: str,
    observation_refs: list[str],
    evaluable: int,
    confirmations: int,
    refutations: int,
    objective_score: float,
) -> dict[str, Any]:
    checked = validate_native_activation_policy(policy)
    if not checked["enabled"]:
        raise RuntimeError("native activation policy is off")
    if relation not in checked["allowed_relations"]:
        raise ValueError("temporal relation is not allowed by activation policy")

    evidence = {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": relation,
            "feature": feature,
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": list(observation_refs),
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": int(evaluable),
            "confirmations": int(confirmations),
            "refutations": int(refutations),
        },
    }
    evidence_result = core.record_native_evidence(
        evidence,
        enabled=True,
        persist=checked["allow_persist_evidence"],
    )

    stable = relation == "same_next_observation"
    inquiry = {
        "version": NATIVE_INQUIRY_VERSION,
        "id": f"NIC:activation:{relation}:{feature}",
        "objective": checked["objective"],
        "objective_score": float(objective_score),
        "relation": evidence["relation"],
        "question": (
            f"What next observation would most directly test whether {feature} "
            f"{'remains stable' if stable else 'changes'}?"
        ),
        "hypothesis": (
            f"Observed {feature} tends to "
            f"{'remain stable' if stable else 'change'} across consecutive "
            "evaluable observations."
        ),
        "method": (
            f"Collect one later legitimate {feature} observation and compare it "
            "with the prior measured value."
        ),
        "falsification": (
            f"A later evaluable {feature} value that "
            f"{'differs' if stable else 'remains the same'} counts against the hypothesis."
        ),
        "predicted_observation": (
            f"The next evaluable {feature} observation "
            f"{'matches' if stable else 'differs from'} the prior value."
        ),
        "evidence_refs": [evidence_result["evidence_ref"]],
    }
    inquiry_result = core.propose_native_inquiry(
        inquiry,
        enabled=True,
        persist=checked["allow_persist_inquiry"],
    )
    return {
        "policy": deepcopy(checked),
        "evidence_result": evidence_result,
        "inquiry_result": inquiry_result,
    }


def rollback_temporal_activation_state(
    state: dict[str, Any],
    *,
    candidate_id: str,
    evidence_ref: str,
) -> dict[str, Any]:
    """Return a copy with one staged native activation removed.

    This is an isolated recovery primitive for tests/design review. It never
    writes a store itself.
    """
    rolled = deepcopy(state)
    question_ids = {
        str(item.get("id"))
        for item in rolled.get("questions", [])
        if item.get("native_inquiry_candidate_id") == candidate_id
    }
    rolled["questions"] = [
        item for item in rolled.get("questions", [])
        if item.get("native_inquiry_candidate_id") != candidate_id
    ]
    rolled["experiments"] = [
        item for item in rolled.get("experiments", [])
        if item.get("native_inquiry_candidate_id") != candidate_id
        and str(item.get("question_id")) not in question_ids
    ]
    rolled["intentions"] = [
        item for item in rolled.get("intentions", [])
        if item.get("native_inquiry_candidate_id") != candidate_id
    ]
    rolled["episodes"] = [
        item for item in rolled.get("episodes", [])
        if str(item.get("id")) != evidence_ref
    ]
    return rolled
