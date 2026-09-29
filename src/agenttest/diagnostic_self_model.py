from __future__ import annotations

from typing import Any

from .cognition import known_evidence_ids

DIAGNOSTIC_VERSION = "self-model-grounding-v1"
VALID_STATUSES = {"verified", "observed", "unverified"}


def evaluate_self_model_grounding(state: dict[str, Any]) -> dict[str, Any]:
    self_model = state.get("self_model", {})
    capabilities = [
        str(capability)
        for capability in self_model.get("capabilities", [])
        if str(capability).strip()
    ]
    registry = self_model.get("capability_claims", {})
    if not isinstance(registry, dict):
        registry = {}

    known_ids = known_evidence_ids(state)
    missing: list[str] = []
    invalid: list[dict[str, Any]] = []
    valid: list[str] = []

    for capability in capabilities:
        claim = registry.get(capability)
        if not isinstance(claim, dict):
            missing.append(capability)
            continue

        status = claim.get("status")
        if status not in VALID_STATUSES:
            invalid.append(
                {
                    "capability": capability,
                    "reason": "invalid_status",
                    "status": status,
                }
            )
            continue

        refs = claim.get("evidence_refs", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            invalid.append(
                {
                    "capability": capability,
                    "reason": "invalid_evidence_refs",
                }
            )
            continue

        unknown = sorted(set(refs) - known_ids)
        if unknown:
            invalid.append(
                {
                    "capability": capability,
                    "reason": "unknown_evidence_refs",
                    "unknown": unknown,
                }
            )
            continue

        if status in {"verified", "observed"} and not refs:
            invalid.append(
                {
                    "capability": capability,
                    "reason": "supported_status_without_evidence",
                    "status": status,
                }
            )
            continue

        if status == "unverified" and not str(claim.get("reason", "")).strip():
            invalid.append(
                {
                    "capability": capability,
                    "reason": "unverified_without_reason",
                }
            )
            continue

        valid.append(capability)

    total = len(capabilities)
    grounded = len(valid)
    coverage = 1.0 if total == 0 else grounded / total
    outcome = "grounded" if not missing and not invalid else "grounding_gap"

    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "outcome": outcome,
        "capability_count": total,
        "grounded_count": grounded,
        "coverage": coverage,
        "missing_claims": missing,
        "invalid_claims": invalid,
        "valid_claims": valid,
        "source_state_mutated": False,
    }
