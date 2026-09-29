from __future__ import annotations

from collections import Counter
from typing import Any

from .change_control import validate_change_manifest
from .state import utc_now

REVIEW_VERSION = "proposal-review-v3"


def _evidence_index(state: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    index: dict[str, tuple[str, dict[str, Any]]] = {}
    for key in (
        "episodes",
        "surprises",
        "predictions",
        "intentions",
        "questions",
        "experiments",
        "reflections",
        "cognition_events",
        "cognition_candidates",
    ):
        for item in state.get(key, []):
            identifier = item.get("id")
            if identifier:
                index[str(identifier)] = (key, item)
    for claim in state.get("world_model", {}).get("claims", []):
        identifier = claim.get("id")
        if identifier:
            index[str(identifier)] = ("world_claims", claim)
    for diagnostic in state.get("proposal_diagnostics", []):
        identifier = diagnostic.get("id")
        if identifier:
            index[str(identifier)] = ("proposal_diagnostics", diagnostic)
    return index


def _completed_diagnostic_ids(
    state: dict[str, Any],
    proposal_id: str,
) -> list[str]:
    return sorted(
        str(diagnostic["id"])
        for diagnostic in state.get("proposal_diagnostics", [])
        if diagnostic.get("proposal_id") == proposal_id
        and diagnostic.get("status") == "completed"
        and diagnostic.get("id")
    )


def _existing_review(
    state: dict[str, Any],
    proposal_id: str,
) -> dict[str, Any] | None:
    current_diagnostics = _completed_diagnostic_ids(state, proposal_id)
    for review in reversed(state.get("proposal_reviews", [])):
        if review.get("proposal_id") != proposal_id:
            continue
        if review.get("review_version") != REVIEW_VERSION:
            continue
        if review.get("considered_diagnostic_ids", []) == current_diagnostics:
            return review
    return None


def _successful_cognition_exists(state: dict[str, Any]) -> bool:
    if state.get("cognition_candidates"):
        return True
    return any(
        event.get("status") == "accepted"
        for event in state.get("cognition_events", [])
    )


def _latest_completed_diagnostic(
    state: dict[str, Any],
    proposal_id: str,
    kind: str,
) -> dict[str, Any] | None:
    for diagnostic in reversed(state.get("proposal_diagnostics", [])):
        if (
            diagnostic.get("proposal_id") == proposal_id
            and diagnostic.get("kind") == kind
            and diagnostic.get("status") == "completed"
        ):
            return diagnostic
    return None



def _learning_loop_gap(state: dict[str, Any]) -> tuple[bool, list[str]]:
    predictions = {
        str(prediction.get("id")): prediction
        for prediction in state.get("predictions", [])
        if prediction.get("status") in {"confirmed", "violated"}
        and prediction.get("id")
    }
    prediction_reflections = [
        reflection
        for reflection in state.get("reflections", [])
        if reflection.get("source") == "prediction"
        and str(reflection.get("prediction_id")) in predictions
    ]

    for experiment in state.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue
        if experiment.get("readiness") in {
            "awaiting_specification_or_evidence",
            "needs_specification",
        }:
            continue
        created_cycle = int(experiment.get("cycle", 0))
        later = [
            reflection
            for reflection in prediction_reflections
            if int(reflection.get("cycle", 0)) > created_cycle
        ]
        if later:
            refs = [str(experiment["id"])]
            for reflection in later[-2:]:
                prediction_id = str(reflection["prediction_id"])
                if prediction_id not in refs:
                    refs.append(prediction_id)
                reflection_id = str(reflection.get("id"))
                if reflection_id and reflection_id != "None" and reflection_id not in refs:
                    refs.append(reflection_id)
            return True, refs
    return False, []


def _underspecified_learning_work(state: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for experiment in state.get("experiments", []):
        if (
            experiment.get("status") == "proposed"
            and experiment.get("readiness")
            in {"awaiting_specification_or_evidence", "needs_specification"}
            and experiment.get("id")
        ):
            refs.append(str(experiment["id"]))
    return refs[-6:]


def _repeated_reflection_pattern(state: dict[str, Any]) -> tuple[bool, list[str]]:
    reflections = state.get("reflections", [])
    groups: dict[str, list[str]] = {}
    for reflection in reflections:
        lesson = " ".join(str(reflection.get("lesson", "")).lower().split())
        if not lesson:
            continue
        groups.setdefault(lesson, []).append(str(reflection.get("id")))
    repeated = [
        refs
        for refs in groups.values()
        if len([ref for ref in refs if ref and ref != "None"]) >= 2
    ]
    if not repeated:
        return False, []
    refs = max(repeated, key=len)
    return True, refs[-6:]


def classify_proposal(
    state: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    valid, validation_reason = validate_change_manifest(proposal, state)
    evidence_index = _evidence_index(state)
    cited = [
        evidence_index[ref]
        for ref in proposal.get("evidence_refs", [])
        if ref in evidence_index
    ]
    kinds = Counter(kind for kind, _ in cited)
    target = proposal.get("target_dimension")

    if not valid:
        return {
            "verdict": "needs_evidence",
            "patch_authority": "none",
            "reason": "The manifest does not currently satisfy change-control validation.",
            "required_next_evidence": validation_reason or "A structurally valid manifest.",
            "resolved_evidence_count": len(cited),
            "evidence_kinds": dict(kinds),
        }

    if target == "reproducibility":
        replay = _latest_completed_diagnostic(
            state,
            str(proposal.get("id")),
            "deterministic_replay",
        )
        if replay is not None and replay.get("outcome") in {"divergent", "failure"}:
            return {
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
                "reason": (
                    "The latest completed deterministic-replay diagnostic for this "
                    "proposal reports divergence."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": replay.get("id"),
            }

        if replay is not None and replay.get("outcome") == "stable":
            return {
                "verdict": "no_problem_observed",
                "patch_authority": "none",
                "reason": (
                    "The latest verified deterministic-replay diagnostic completed "
                    "on isolated temporary state and produced equivalent normalized "
                    "results. No reproducibility defect is currently supported."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": replay.get("id"),
            }

        return {
            "verdict": "measurement_gap",
            "patch_authority": "diagnostic_only",
            "reason": (
                "The cited evidence shows evaluated predictions and reflections, but "
                "no current deterministic-replay diagnostic resolves the question."
            ),
            "required_next_evidence": (
                "Run a non-mutating deterministic replay diagnostic on equivalent "
                "controlled inputs and record whether normalized outputs diverge."
            ),
            "resolved_evidence_count": len(cited),
            "evidence_kinds": dict(kinds),
        }


    if target == "self_model":
        grounding = _latest_completed_diagnostic(
            state,
            str(proposal.get("id")),
            "self_model_grounding",
        )
        if grounding is not None and grounding.get("outcome") == "grounding_gap":
            return {
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
                "reason": (
                    "The latest verified read-only self-model diagnostic found "
                    "capability claims without explicit calibration records. This "
                    "supports a traceability problem, not a claim that the "
                    "capabilities themselves are false."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": grounding.get("id"),
            }

        if grounding is not None and grounding.get("outcome") == "grounded":
            return {
                "verdict": "no_problem_observed",
                "patch_authority": "none",
                "reason": (
                    "The latest verified self-model diagnostic found every capability "
                    "claim explicitly calibrated as verified, observed, or unverified "
                    "with valid provenance or uncertainty rationale."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": grounding.get("id"),
            }

        return {
            "verdict": "measurement_gap",
            "patch_authority": "diagnostic_only",
            "reason": (
                "The self-model proposal concerns calibration and traceability, but "
                "no current verified grounding diagnostic has measured claim-by-claim "
                "coverage yet."
            ),
            "required_next_evidence": (
                "Run the verified read-only self-model grounding diagnostic and "
                "record whether each capability has an explicit status plus evidence "
                "or an unverified rationale."
            ),
            "resolved_evidence_count": len(cited),
            "evidence_kinds": dict(kinds),
        }

    if target == "open_endedness":
        inquiry = _latest_completed_diagnostic(
            state,
            str(proposal.get("id")),
            "inquiry_family",
        )
        if (
            inquiry is not None
            and inquiry.get("outcome") == "paraphrase_churn"
            and inquiry.get("result", {}).get("metric_status") in {"inflated", "unknown"}
        ):
            return {
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
                "reason": (
                    "The latest verified inquiry-family diagnostic found repeated "
                    "question families and showed that exact-string scoring materially "
                    "overstates family-based open-endedness."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": inquiry.get("id"),
            }

        if (
            inquiry is not None
            and inquiry.get("result", {}).get("metric_status") == "aligned"
            and inquiry.get("outcome") in {"diverse", "paraphrase_churn"}
        ):
            return {
                "verdict": "no_problem_observed",
                "patch_authority": "none",
                "reason": (
                    "The latest verified inquiry-family diagnostic found no material "
                    "inflation in the reported open-endedness metric relative to "
                    "distinct inquiry families."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": inquiry.get("id"),
            }

        if (
            inquiry is not None
            and inquiry.get("outcome") == "diverse"
            and inquiry.get("result", {}).get("metric_status") == "unknown"
        ):
            return {
                "verdict": "no_problem_observed",
                "patch_authority": "none",
                "reason": (
                    "The verified inquiry-family diagnostic found distinct question "
                    "families and no paraphrase-churn signal. Metric alignment is not "
                    "available in this legacy or synthetic context, so no corrective "
                    "patch is authorized."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": inquiry.get("id"),
            }

        if inquiry is not None and inquiry.get("outcome") == "insufficient_data":
            return {
                "verdict": "needs_evidence",
                "patch_authority": "none",
                "reason": (
                    "The verified inquiry-family diagnostic does not yet have enough "
                    "questions to evaluate metric alignment."
                ),
                "required_next_evidence": (
                    "Accumulate at least four evidence-backed questions, then rerun "
                    "the inquiry-family diagnostic."
                ),
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_diagnostic_id": inquiry.get("id"),
            }

        return {
            "verdict": "needs_evidence",
            "patch_authority": "none",
            "reason": (
                "The cited questions are real, but exact-string uniqueness does not "
                "show whether the reported metric matches distinct inquiry families."
            ),
            "required_next_evidence": (
                "Run the verified read-only inquiry-family diagnostic to compare "
                "reported open-endedness with family-based open-endedness."
            ),
            "resolved_evidence_count": len(cited),
            "evidence_kinds": dict(kinds),
        }

    if target == "learning":
        gap, direct_refs = _learning_loop_gap(state)
        if gap:
            return {
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
                "reason": (
                    "At least one experiment remains proposed despite later evaluated prediction "
                    "evidence, directly demonstrating an unresolved evidence-closure gap."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_evidence_refs": direct_refs,
            }

        underspecified_refs = _underspecified_learning_work(state)
        if underspecified_refs:
            return {
                "verdict": "no_problem_observed",
                "patch_authority": "none",
                "reason": (
                    "Outstanding proposed experiments are explicitly classified as awaiting "
                    "specification or needing specification. Their persistence is unresolved "
                    "inquiry work, not evidence that the experiment-closure code is defective."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_evidence_refs": underspecified_refs,
            }

    if target == "reflection":
        repeated, direct_refs = _repeated_reflection_pattern(state)
        if repeated:
            return {
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
                "reason": (
                    "Repeated reflections contain the same evidence-backed lesson, supporting "
                    "a need for structured pattern consolidation."
                ),
                "required_next_evidence": None,
                "resolved_evidence_count": len(cited),
                "evidence_kinds": dict(kinds),
                "direct_evidence_refs": direct_refs,
            }

    if target == "cognition" and not _successful_cognition_exists(state):
        return {
            "verdict": "needs_evidence",
            "patch_authority": "none",
            "reason": (
                "No successful cognition-provider evidence exists, so a cognition deficit "
                "cannot currently be attributed to code."
            ),
            "required_next_evidence": (
                "Configure a provider and record at least one grounded cognition attempt before "
                "diagnosing cognition code."
            ),
            "resolved_evidence_count": len(cited),
            "evidence_kinds": dict(kinds),
        }

    measurement_targets = {"memory", "perception", "semantic_memory"}
    if target in measurement_targets:
        return {
            "verdict": "measurement_gap",
            "patch_authority": "diagnostic_only",
            "reason": (
                "The manifest primarily proposes better measurement or traceability. Existing "
                "evidence does not establish a behavioral defect requiring corrective code."
            ),
            "required_next_evidence": (
                "Add or run a non-mutating diagnostic that can demonstrate a specific failure "
                "before authorizing corrective behavior changes."
            ),
            "resolved_evidence_count": len(cited),
            "evidence_kinds": dict(kinds),
        }

    return {
        "verdict": "needs_evidence",
        "patch_authority": "none",
        "reason": (
            "The cited evidence is real but does not yet demonstrate that the proposed code "
            "surface is the first layer where behavior becomes incorrect."
        ),
        "required_next_evidence": (
            "Gather a direct observation or controlled diagnostic that connects the target "
            "behavior to the proposed code layer."
        ),
        "resolved_evidence_count": len(cited),
        "evidence_kinds": dict(kinds),
    }


def review_change_proposal(
    state: dict[str, Any],
    proposal: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    if proposal is None:
        proposals = state.get("change_proposals", [])
        proposal = next(
            (
                item
                for item in proposals
                if item.get("status")
                in {
                    "proposed",
                    "reviewed_measurement_gap",
                    "reviewed_needs_evidence",
                    "reviewed_supported_problem",
                }
            ),
            None,
        )
    if proposal is None:
        return None, False

    existing = _existing_review(state, str(proposal.get("id")))
    if existing is not None:
        return existing, False

    classification = classify_proposal(state, proposal)
    verdict = classification["verdict"]
    status_by_verdict = {
        "supported_problem": "reviewed_supported_problem",
        "measurement_gap": "reviewed_measurement_gap",
        "needs_evidence": "reviewed_needs_evidence",
        "no_problem_observed": "closed_no_problem_observed",
    }
    proposal["status"] = status_by_verdict[verdict]

    review = {
        "id": f"V{len(state.get('proposal_reviews', [])) + 1:06d}",
        "proposal_id": proposal["id"],
        "target_dimension": proposal.get("target_dimension"),
        "review_version": REVIEW_VERSION,
        "created_at": utc_now(),
        "reviewed_cycle": state.get("cycles", 0),
        "considered_diagnostic_ids": _completed_diagnostic_ids(
            state,
            str(proposal["id"]),
        ),
        **classification,
    }
    state.setdefault("proposal_reviews", []).append(review)
    return review, True
