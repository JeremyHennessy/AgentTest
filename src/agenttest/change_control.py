from __future__ import annotations

from typing import Any

from .evidence import known_evidence_ids
from .state import DIMENSIONS, utc_now

PROTECTED_PATHS = {
    ".github/workflows/verify.yml",
    ".github/workflows/growth.yml",
    ".github/workflows/interact.yml",
    ".github/workflows/reconcile.yml",
    "scripts/preservation_eval.py",
    "scripts/reconcile_verified_change.py",
    "scripts/experiment_design_eval.py",
    "scripts/blocked_attention_eval.py",
    "src/agenttest/intervention.py",
    "src/agenttest/evidence.py",
    "scripts/compare_eval.py",
    "src/agenttest/change_control.py",
    "src/agenttest/proposal_review.py",
    "src/agenttest/self_proposal.py",
    "src/agenttest/diagnostics.py",
    "src/agenttest/diagnostic_replay.py",
    "src/agenttest/diagnostic_self_model.py",
    "src/agenttest/diagnostic_inquiry.py",
    "src/agenttest/diagnostic_experiments.py",
    "src/agenttest/diagnostic_attention.py",
    "src/agenttest/action_lab.py",
}


def validate_change_manifest(
    manifest: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    if not isinstance(manifest, dict):
        return False, "manifest is not an object"

    required_strings = (
        "title",
        "target_dimension",
        "hypothesis",
        "expected_effect",
        "test_plan",
        "falsification",
        "rollback",
    )
    for field in required_strings:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            return False, f"{field} must be a non-empty string"

    if manifest["target_dimension"] not in DIMENSIONS:
        return False, f"unknown target dimension: {manifest['target_dimension']}"

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return False, "files must contain at least one repository path"
    if any(not isinstance(path, str) or not path.strip() for path in files):
        return False, "files must contain only non-empty paths"

    protected = sorted(PROTECTED_PATHS.intersection(files))
    if protected:
        return False, f"protected evaluation paths cannot be modified: {', '.join(protected)}"

    refs = manifest.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return False, "evidence_refs must contain at least one evidence ID"
    if any(not isinstance(ref, str) or not ref for ref in refs):
        return False, "evidence_refs must contain only non-empty strings"

    if state is not None:
        unknown = sorted(set(refs) - known_evidence_ids(state))
        if unknown:
            return False, f"unknown evidence refs: {', '.join(unknown)}"

    return True, None


def make_change_manifest(
    state: dict[str, Any],
    *,
    title: str,
    target_dimension: str,
    files: list[str],
    hypothesis: str,
    expected_effect: str,
    test_plan: str,
    falsification: str,
    rollback: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "status": "proposed",
        "title": title,
        "target_dimension": target_dimension,
        "baseline_metric": state.get("metrics", {}).get(target_dimension),
        "files": list(files),
        "hypothesis": hypothesis,
        "expected_effect": expected_effect,
        "test_plan": test_plan,
        "falsification": falsification,
        "rollback": rollback,
        "evidence_refs": list(evidence_refs),
        "protected_paths": sorted(PROTECTED_PATHS),
    }
    valid, reason = validate_change_manifest(manifest, state)
    if not valid:
        raise ValueError(reason)
    return manifest
