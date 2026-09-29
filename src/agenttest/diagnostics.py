from __future__ import annotations

import hashlib
import json
from typing import Any

from .diagnostic_replay import DIAGNOSTIC_VERSION as REPLAY_VERSION, compare_replays
from .diagnostic_self_model import DIAGNOSTIC_VERSION as SELF_MODEL_VERSION, evaluate_self_model_grounding
from .state import utc_now


def _proposal_by_id(
    state: dict[str, Any],
    proposal_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            proposal
            for proposal in state.get("change_proposals", [])
            if proposal.get("id") == proposal_id
        ),
        None,
    )


def _latest_diagnostic_review(
    state: dict[str, Any],
    proposal_id: str | None = None,
) -> dict[str, Any] | None:
    for review in reversed(state.get("proposal_reviews", [])):
        if proposal_id is not None and review.get("proposal_id") != proposal_id:
            continue
        if (
            review.get("verdict") == "measurement_gap"
            and review.get("patch_authority") == "diagnostic_only"
        ):
            return review
    return None


def _current_baseline_fingerprint(state: dict[str, Any]) -> str | None:
    for snapshot in reversed(state.get("environment_snapshots", [])):
        fingerprint = snapshot.get("baseline_fingerprint")
        if isinstance(fingerprint, str) and fingerprint:
            return fingerprint
    return None


def _existing(
    state: dict[str, Any],
    proposal_id: str,
    kind: str,
    diagnostic_version: str,
    baseline_fingerprint: str | None,
) -> dict[str, Any] | None:
    for diagnostic in reversed(state.get("proposal_diagnostics", [])):
        if (
            diagnostic.get("proposal_id") == proposal_id
            and diagnostic.get("kind") == kind
            and diagnostic.get("diagnostic_version") == diagnostic_version
            and diagnostic.get("status") == "completed"
            and diagnostic.get("baseline_fingerprint") == baseline_fingerprint
        ):
            return diagnostic
    return None


def run_proposal_diagnostic(
    state: dict[str, Any],
    proposal: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    if review is None:
        review = _latest_diagnostic_review(
            state,
            str(proposal.get("id")) if proposal is not None else None,
        )
    if review is None:
        return None, False

    if proposal is None:
        proposal = _proposal_by_id(state, str(review.get("proposal_id")))
    if proposal is None:
        return None, False

    target = proposal.get("target_dimension")
    if target == "reproducibility":
        kind = "deterministic_replay"
        diagnostic_version = REPLAY_VERSION
    elif target == "self_model":
        kind = "self_model_grounding"
        diagnostic_version = SELF_MODEL_VERSION
    else:
        return None, False

    baseline_fingerprint = _current_baseline_fingerprint(state)
    existing = _existing(
        state,
        str(proposal["id"]),
        kind,
        diagnostic_version,
        baseline_fingerprint,
    )
    if existing is not None:
        return existing, False

    request_context = {
        "proposal_id": proposal["id"],
        "review_id": review["id"],
        "target_dimension": target,
        "required_next_evidence": review.get("required_next_evidence"),
        "diagnostic_version": diagnostic_version,
        "baseline_fingerprint": baseline_fingerprint,
    }
    context_hash = hashlib.sha256(
        json.dumps(
            request_context,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    result = (
        compare_replays()
        if target == "reproducibility"
        else evaluate_self_model_grounding(state)
    )
    diagnostic = {
        "id": f"D{len(state.get('proposal_diagnostics', [])) + 1:06d}",
        "proposal_id": proposal["id"],
        "review_id": review["id"],
        "target_dimension": proposal.get("target_dimension"),
        "kind": kind,
        "diagnostic_version": diagnostic_version,
        "baseline_fingerprint": baseline_fingerprint,
        "status": "completed",
        "outcome": result["outcome"],
        "created_at": utc_now(),
        "completed_at": utc_now(),
        "created_cycle": state.get("cycles", 0),
        "request_context_hash": context_hash,
        "mutation_scope": (
            "isolated_temp_state"
            if target == "reproducibility"
            else "read_only_live_state"
        ),
        "source_state_mutated": False,
        "result": result,
    }
    state.setdefault("proposal_diagnostics", []).append(diagnostic)
    return diagnostic, True
