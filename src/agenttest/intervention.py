from __future__ import annotations

import re
from typing import Any

from .state import utc_now

CLOSED_VERIFIED_INTERVENTION = "closed_verified_intervention"
_VERIFIED_SHA = re.compile(r"^[0-9a-f]{40}$")


def _find_proposal(
    state: dict[str, Any],
    proposal_id: str | None,
    changed_files: list[str],
) -> dict[str, Any] | None:
    proposals = [
        proposal
        for proposal in state.get("change_proposals", [])
        if proposal.get("status") == "reviewed_supported_problem"
    ]
    if proposal_id is not None:
        return next(
            (proposal for proposal in proposals if proposal.get("id") == proposal_id),
            None,
        )

    changed = set(changed_files)
    matches = []
    for proposal in proposals:
        authorized = {
            str(path)
            for path in proposal.get("files", [])
            if isinstance(path, str) and path
        }
        if changed and changed.issubset(authorized):
            matches.append(proposal)

    if len(matches) > 1:
        raise ValueError("multiple supported proposals match the verified commit scope")
    return matches[0] if matches else None


def record_verified_intervention(
    state: dict[str, Any],
    *,
    commit_sha: str,
    changed_files: list[str],
    verify_run_id: int,
    pr_number: int,
    proposal_id: str | None = None,
    workflow_name: str = "verify",
    verification_event: str = "push",
    verification_conclusion: str = "success",
    authority: str = "trusted_verification_workflow",
    attribution_text: str = "",
) -> tuple[dict[str, Any] | None, bool]:
    """Record that an authorized intervention was applied and preserved.

    This records deployment/governance evidence, not a claim that the intervention
    improved the target dimension. Benefit still requires later behavioral evidence.
    """

    if not _VERIFIED_SHA.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a full lowercase 40-character Git SHA")
    if not changed_files or any(
        not isinstance(path, str) or not path.strip() for path in changed_files
    ):
        raise ValueError("changed_files must contain at least one non-empty repository path")
    if workflow_name != "verify":
        raise ValueError("only the protected verify workflow can authorize reconciliation")
    if verification_event != "push":
        raise ValueError("only a verified main-branch push can authorize reconciliation")
    if verification_conclusion != "success":
        raise ValueError("verification must have concluded successfully")
    if not isinstance(verify_run_id, int) or verify_run_id <= 0:
        raise ValueError("verify_run_id must be a positive integer")
    if not isinstance(pr_number, int) or pr_number <= 0:
        raise ValueError("pr_number must be a positive integer")

    normalized_changed = sorted(set(changed_files))

    existing = next(
        (
            item
            for item in state.get("accepted_changes", [])
            if item.get("proposal_id") == proposal_id
            and proposal_id is not None
        ),
        None,
    )
    if existing is not None:
        if existing.get("commit_sha") != commit_sha:
            raise ValueError("proposal already reconciled to a different commit")
        return existing, False

    proposal = _find_proposal(state, proposal_id, normalized_changed)
    if proposal is None:
        return None, False

    proposal_id = str(proposal["id"])
    if proposal_id not in attribution_text:
        raise ValueError(
            "verified commit attribution does not identify the matched proposal"
        )

    existing = next(
        (
            item
            for item in state.get("accepted_changes", [])
            if item.get("proposal_id") == proposal_id
        ),
        None,
    )
    if existing is not None:
        if existing.get("commit_sha") != commit_sha:
            raise ValueError("proposal already reconciled to a different commit")
        return existing, False

    authorized = {
        str(path)
        for path in proposal.get("files", [])
        if isinstance(path, str) and path
    }
    changed = set(normalized_changed)
    unauthorized = sorted(changed - authorized)
    if unauthorized:
        raise ValueError(
            "verified commit changed files outside proposal scope: "
            + ", ".join(unauthorized)
        )

    protected = {
        str(path)
        for path in proposal.get("protected_paths", [])
        if isinstance(path, str) and path
    }
    protected_changed = sorted(changed.intersection(protected))
    if protected_changed:
        raise ValueError(
            "verified intervention touched proposal-protected paths: "
            + ", ".join(protected_changed)
        )

    accepted = state.setdefault("accepted_changes", [])
    receipt = {
        "id": f"A{len(accepted) + 1:06d}",
        "proposal_id": proposal_id,
        "target_dimension": proposal.get("target_dimension"),
        "commit_sha": commit_sha,
        "changed_files": normalized_changed,
        "pr_number": pr_number,
        "accepted_at": utc_now(),
        "accepted_cycle": int(state.get("cycles", 0)),
        "authority": authority,
        "verification": {
            "workflow": workflow_name,
            "event": verification_event,
            "conclusion": verification_conclusion,
            "run_id": verify_run_id,
        },
        "verification_scope": "applied_and_preserved",
        "improvement_claim": "not_implied",
        "prior_proposal_status": proposal.get("status"),
    }
    accepted.append(receipt)

    proposal["status"] = CLOSED_VERIFIED_INTERVENTION
    proposal["accepted_change_id"] = receipt["id"]
    proposal["verified_commit_sha"] = commit_sha
    proposal["verification_run_id"] = verify_run_id
    proposal["verification_scope"] = receipt["verification_scope"]
    proposal["improvement_claim"] = receipt["improvement_claim"]

    state.setdefault("metrics", {})["adaptation"] = min(1.0, len(accepted) / 3.0)
    return receipt, True
