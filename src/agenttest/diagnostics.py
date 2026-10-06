from __future__ import annotations

import hashlib
import json
from typing import Any

from .diagnostic_inquiry import DIAGNOSTIC_VERSION as INQUIRY_VERSION, evaluate_inquiry_families
from .diagnostic_replay import DIAGNOSTIC_VERSION as REPLAY_VERSION, compare_replays
from .diagnostic_self_model import DIAGNOSTIC_VERSION as SELF_MODEL_VERSION, evaluate_self_model_grounding
from .evidence import known_evidence_ids
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
            review.get("verdict") in {"measurement_gap", "needs_evidence"}
            and review.get("patch_authority") in {"diagnostic_only", "none"}
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
    input_fingerprint: str,
) -> dict[str, Any] | None:
    for diagnostic in reversed(state.get("proposal_diagnostics", [])):
        if (
            diagnostic.get("proposal_id") == proposal_id
            and diagnostic.get("kind") == kind
            and diagnostic.get("diagnostic_version") == diagnostic_version
            and diagnostic.get("status") == "completed"
            and diagnostic.get("baseline_fingerprint") == baseline_fingerprint
            and diagnostic.get("input_fingerprint") == input_fingerprint
        ):
            return diagnostic
    return None


def diagnostic_input_fingerprint(state: dict[str, Any], kind: str) -> str:
    """Hash evaluator inputs only; metadata and unrelated evidence are excluded."""
    if kind == "inquiry_family":
        cycles = int(state.get("cycles", 0))
        metric_present = cycles > 0 and "open_endedness" in state.get("metrics", {})
        inputs = {
            "questions": [{"id": str(row["id"]), "text": str(row.get("text", ""))}
                          for row in state.get("questions", [])
                          if isinstance(row, dict) and row.get("id")
                          and str(row.get("text", "")).strip()],
            "cycles": cycles,
            "reported_open_endedness": float(state["metrics"]["open_endedness"])
                if metric_present else None,
        }
    elif kind == "self_model_grounding":
        model = state.get("self_model", {})
        capabilities = [str(value) for value in model.get("capabilities", []) if str(value).strip()]
        registry = model.get("capability_claims", {})
        if not isinstance(registry, dict): registry = {}
        known = known_evidence_ids(state)
        claims = []
        for capability in capabilities:
            claim = registry.get(capability)
            if not isinstance(claim, dict):
                claims.append({"capability": capability, "claim": None})
                continue
            refs = claim.get("evidence_refs", [])
            valid_refs = isinstance(refs, list) and all(isinstance(ref, str) for ref in refs)
            claims.append({
                "capability": capability, "status": claim.get("status"),
                "refs": sorted(set(refs)) if valid_refs else refs,
                "refs_valid": valid_refs,
                "known_refs": sorted(set(refs) & known) if valid_refs else [],
                "unverified_reason_present": bool(str(claim.get("reason", "")).strip())
                    if claim.get("status") == "unverified" else None,
            })
        inputs = {"claims": claims}
    elif kind == "deterministic_replay":
        inputs = {}  # compare_replays uses its fixed isolated fixture, no live state.
    else:
        raise ValueError(f"Unsupported proposal diagnostic kind: {kind}")
    return hashlib.sha256(json.dumps(
        {"input_schema": "proposal-diagnostic-inputs-v1", "kind": kind, "inputs": inputs},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def diagnostic_matches_current_inputs(state: dict[str, Any], diagnostic: dict[str, Any]) -> bool:
    kind = diagnostic.get("kind")
    versions = {"inquiry_family": INQUIRY_VERSION, "self_model_grounding": SELF_MODEL_VERSION,
                "deterministic_replay": REPLAY_VERSION}
    if kind not in versions:
        return True
    return (diagnostic.get("diagnostic_version") == versions[kind]
            and diagnostic.get("baseline_fingerprint") == _current_baseline_fingerprint(state)
            and diagnostic.get("input_fingerprint") == diagnostic_input_fingerprint(state, kind))


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
    elif target == "open_endedness":
        kind = "inquiry_family"
        diagnostic_version = INQUIRY_VERSION
    else:
        return None, False

    baseline_fingerprint = _current_baseline_fingerprint(state)
    input_fingerprint = diagnostic_input_fingerprint(state, kind)
    existing = _existing(
        state,
        str(proposal["id"]),
        kind,
        diagnostic_version,
        baseline_fingerprint,
        input_fingerprint,
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
        "input_fingerprint": input_fingerprint,
    }
    context_hash = hashlib.sha256(
        json.dumps(
            request_context,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    if target == "reproducibility":
        result = compare_replays()
    elif target == "self_model":
        result = evaluate_self_model_grounding(state)
    else:
        result = evaluate_inquiry_families(state)
    diagnostic = {
        "id": f"D{len(state.get('proposal_diagnostics', [])) + 1:06d}",
        "proposal_id": proposal["id"],
        "review_id": review["id"],
        "target_dimension": proposal.get("target_dimension"),
        "kind": kind,
        "diagnostic_version": diagnostic_version,
        "baseline_fingerprint": baseline_fingerprint,
        "input_fingerprint": input_fingerprint,
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
