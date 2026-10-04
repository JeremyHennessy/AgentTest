from __future__ import annotations

from typing import Any

from agenttest.core import AgentCore
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION

from action_association_semantics import (
    interpret_action_association,
    public_evidence_payload,
)


def stage_association_inquiry(
    core: AgentCore,
    candidate: dict[str, Any],
    *,
    observation_refs: list[str],
) -> dict[str, Any]:
    interpretation = interpret_action_association(candidate)
    payload = public_evidence_payload(
        interpretation,
        observation_refs=observation_refs,
    )
    evidence_result = core.record_native_evidence(
        payload,
        enabled=True,
        persist=True,
    )
    relation = payload["relation"]
    direction = interpretation["direction"].replace("_", " ")
    hypothesis = (
        f"Observed action {relation['action']} is associated with a {direction} "
        f"change rate in {relation['feature']} than observations without that action."
    )
    inquiry = {
        "version": NATIVE_INQUIRY_VERSION,
        "id": f"NIC:association:{candidate['id']}",
        "objective": "information_gain",
        "objective_score": min(
            1.0,
            float(interpretation["effect_magnitude"]),
        ),
        "relation": relation,
        "question": (
            f"What next comparable observation would most directly test whether "
            f"{relation['action']} remains associated with a different change rate "
            f"in {relation['feature']}?"
        ),
        "hypothesis": hypothesis,
        "method": (
            "Collect additional legitimate action-present and action-absent "
            "transitions and compare their observed feature-change rates."
        ),
        "falsification": (
            "Comparable held-out evidence that reverses the observed direction "
            "or reduces the absolute change-rate difference below the material "
            "association threshold counts against this association."
        ),
        "predicted_observation": (
            "Additional comparable exposure groups preserve a material "
            f"{direction} change-rate difference."
        ),
        "evidence_refs": [evidence_result["evidence_ref"]],
    }
    inquiry_result = core.propose_native_inquiry(
        inquiry,
        enabled=True,
        persist=True,
    )
    return {
        "interpretation": interpretation,
        "evidence_result": evidence_result,
        "inquiry_result": inquiry_result,
    }
