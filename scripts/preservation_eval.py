from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Callable

from agenttest.change_control import PROTECTED_PATHS, make_change_manifest, validate_change_manifest
from agenttest.cognition import StaticCognitionProvider
from agenttest.core import AgentCore
from agenttest.evidence import known_evidence_ids
from agenttest.interaction import interact
from agenttest.intervention import record_verified_intervention
from agenttest.diagnostics import run_proposal_diagnostic
from agenttest.proposal_review import review_change_proposal
from agenttest.semantic import retrieve_semantic_memory
from agenttest.self_proposal import propose_self_change, select_change_target
from agenttest.state import StateStore
from agenttest.world import current_world_claims

SUITE = "behavioral-preservation-v16"


def observation(lines: int = 100) -> dict[str, object]:
    return {
        "sensor": "preservation-eval",
        "branch": "eval",
        "tracked_files": 10,
        "python_files": 4,
        "python_source_lines": lines,
        "test_files": 1,
        "working_tree_clean": True,
    }


def candidate(evidence_ref: str) -> dict[str, object]:
    return {
        "question": "Does a repeated measured state support short-horizon stability?",
        "hypothesis": "An identical second observation supports short-horizon stability.",
        "experiment": "Repeat the same measured observation on the next cycle.",
        "falsification": "Any comparable measured field changing falsifies the hypothesis.",
        "predicted_observation": "Comparable measured fields remain unchanged.",
        "evidence_refs": [evidence_ref],
        "confidence": 0.6,
        "novelty_note": "This turns recorded evidence into a falsifiable follow-up.",
    }


def fresh() -> tuple[tempfile.TemporaryDirectory[str], StateStore, AgentCore]:
    temp = tempfile.TemporaryDirectory()
    store = StateStore(Path(temp.name) / "organism.json")
    return temp, store, AgentCore(store)


def run_check(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        result = fn()
        return {
            "name": name,
            "passed": bool(result.pop("passed")),
            "evidence": result,
            "error": None,
        }
    except Exception as exc:
        return {
            "name": name,
            "passed": False,
            "evidence": {},
            "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}",
        }


def persistence_reload() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle("persistent memory")
        reloaded = StateStore(store.path).load()
        passed = reloaded["cycles"] == 1 and len(reloaded["episodes"]) == 1
        return {
            "passed": passed,
            "cycles": reloaded["cycles"],
            "episodes": len(reloaded["episodes"]),
        }
    finally:
        temp.cleanup()


def prediction_confirmation() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle(observation=observation(100))
        second = core.cycle(observation=observation(100))
        return {
            "passed": second["prediction_result"]["status"] == "confirmed",
            "status": second["prediction_result"]["status"],
        }
    finally:
        temp.cleanup()


def prediction_error_focus() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle(observation=observation(100))
        second = core.cycle(observation=observation(120))
        return {
            "passed": (
                second["prediction_result"]["status"] == "violated"
                and second["intention"]["kind"] == "explain_change"
                and second["drives"]["prediction_error"] == 1.0
            ),
            "prediction_status": second["prediction_result"]["status"],
            "intention": second["intention"]["kind"],
            "prediction_error": second["drives"]["prediction_error"],
        }
    finally:
        temp.cleanup()


def evidence_hunger_reuses_work() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        first = core.cycle()
        second = core.cycle()
        return {
            "passed": (
                first["experiment"]["id"] == second["experiment"]["id"]
                and second["intention"]["kind"] == "resolve_pending_evidence"
            ),
            "first_experiment": first["experiment"]["id"],
            "second_experiment": second["experiment"]["id"],
            "intention": second["intention"]["kind"],
        }
    finally:
        temp.cleanup()


def cognition_grounding_gate() -> dict[str, Any]:
    temp_a, store_a, core_a = fresh()
    temp_b, store_b, core_b = fresh()
    try:
        accepted = core_a.cycle(
            "grounded evidence",
            cognition=True,
            cognition_provider=StaticCognitionProvider(candidate("E000001")),
        )
        rejected = core_b.cycle(
            "grounded evidence",
            cognition=True,
            cognition_provider=StaticCognitionProvider(candidate("E999999")),
        )
        return {
            "passed": (
                accepted["cognition_event"]["status"] == "accepted"
                and rejected["cognition_event"]["status"] == "rejected"
                and rejected["thought"] is None
            ),
            "accepted_status": accepted["cognition_event"]["status"],
            "rejected_status": rejected["cognition_event"]["status"],
        }
    finally:
        temp_a.cleanup()
        temp_b.cleanup()


def semantic_provenance() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle("alpha beta")
        core.cycle("alpha beta")
        state = store.load()
        alpha = state["semantic_memory"]["concepts"]["alpha"]
        retrieved = retrieve_semantic_memory(state, "alpha", limit=1)
        return {
            "passed": (
                alpha["count"] == 2
                and alpha["episode_refs"] == ["E000001", "E000002"]
                and retrieved
                and retrieved[0]["concept"] == "alpha"
            ),
            "count": alpha["count"],
            "episode_refs": alpha["episode_refs"],
        }
    finally:
        temp.cleanup()


def world_revision_provenance() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle(observation=observation(100))
        core.cycle(observation=observation(120))
        state = store.load()
        claims = [
            claim
            for claim in state["world_model"]["claims"]
            if claim["subject"] == "repository"
            and claim["predicate"] == "python_source_lines"
        ]
        old = next(claim for claim in claims if claim["value"] == 100)
        new = next(claim for claim in claims if claim["value"] == 120)
        return {
            "passed": (
                old["status"] == "superseded"
                and old["superseded_by"] == new["id"]
                and new["supersedes"] == old["id"]
                and bool(new["evidence_refs"])
            ),
            "old_claim": old["id"],
            "new_claim": new["id"],
            "new_evidence_refs": new["evidence_refs"],
        }
    finally:
        temp.cleanup()


def experiment_outcome_world_claim() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        first = core.cycle("outcome evidence")
        core.record_outcome(first["experiment"]["id"], "supported", 0.8)
        claims = current_world_claims(store.load())
        matched = [
            claim
            for claim in claims
            if claim["subject"] == f"experiment.{first['experiment']['id']}"
            and claim["predicate"] == "outcome"
        ]
        return {
            "passed": bool(matched) and matched[0]["value"] == "supported",
            "claim_ids": [claim["id"] for claim in matched],
        }
    finally:
        temp.cleanup()


def self_change_proposal_governance() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle(observation=observation(100))
        core.cycle(observation=observation(120))
        state = store.load()
        adaptation_before = state["metrics"]["adaptation"]

        proposal, created = propose_self_change(state)
        valid, reason = validate_change_manifest(proposal, state) if proposal else (False, "no proposal")
        repeated, repeated_created = propose_self_change(state)
        targeted_protected = (
            sorted(PROTECTED_PATHS.intersection(proposal.get("files", [])))
            if proposal
            else []
        )

        return {
            "passed": (
                created
                and valid
                and proposal is not None
                and bool(proposal.get("evidence_refs"))
                and not targeted_protected
                and repeated is not None
                and repeated["id"] == proposal["id"]
                and not repeated_created
                and len(state.get("change_proposals", [])) == 1
                and state["metrics"]["adaptation"] == adaptation_before
                and ".github/workflows/growth.yml" in PROTECTED_PATHS
                and "src/agenttest/change_control.py" in PROTECTED_PATHS
            ),
            "proposal_id": proposal.get("id") if proposal else None,
            "target_dimension": proposal.get("target_dimension") if proposal else None,
            "manifest_valid": valid,
            "validation_reason": reason,
            "targeted_protected": targeted_protected,
            "reused": not repeated_created,
            "adaptation_before": adaptation_before,
            "adaptation_after": state["metrics"]["adaptation"],
        }
    finally:
        temp.cleanup()


def proposal_review_requires_direct_problem_evidence() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle("proposal review evidence")
        state = store.load()
        proposal = make_change_manifest(
            state,
            title="Add deterministic cycle replay checks",
            target_dimension="reproducibility",
            files=["src/agenttest/replay.py", "tests/test_core.py"],
            hypothesis="Replay measurement can reveal drift.",
            expected_effect="Equivalent controlled cycles can be compared.",
            test_plan="Run a non-mutating replay comparison.",
            falsification="Replay cannot be measured reproducibly.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M000001", "source": "preservation-eval", "created_cycle": 1})
        state["change_proposals"].append(proposal)

        review, created = review_change_proposal(state, proposal)
        repeated, repeated_created = review_change_proposal(state, proposal)
        reused_proposal, proposal_created = propose_self_change(state)

        return {
            "passed": (
                created
                and review is not None
                and review["verdict"] == "measurement_gap"
                and review["patch_authority"] == "diagnostic_only"
                and proposal["status"] == "reviewed_measurement_gap"
                and not repeated_created
                and repeated is not None
                and repeated["id"] == review["id"]
                and not proposal_created
                and reused_proposal is not None
                and reused_proposal["id"] == proposal["id"]
            ),
            "verdict": review.get("verdict") if review else None,
            "patch_authority": review.get("patch_authority") if review else None,
            "proposal_status": proposal.get("status"),
            "review_reused": not repeated_created,
            "proposal_reused": not proposal_created,
        }
    finally:
        temp.cleanup()


def verified_diagnostic_resolution() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle("diagnostic evidence")
        state = store.load()
        proposal = make_change_manifest(
            state,
            title="Add deterministic cycle replay checks",
            target_dimension="reproducibility",
            files=["src/agenttest/replay.py", "tests/test_core.py"],
            hypothesis="Replay measurement can reveal drift.",
            expected_effect="Equivalent controlled cycles can be compared.",
            test_plan="Run a non-mutating replay comparison.",
            falsification="Replay cannot be measured reproducibly.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M000001", "source": "preservation-eval", "created_cycle": 1})
        state["change_proposals"].append(proposal)

        first_review, _ = review_change_proposal(state, proposal)
        diagnostic, diagnostic_created = run_proposal_diagnostic(
            state,
            proposal,
            first_review,
        )
        second_review, second_created = review_change_proposal(state, proposal)

        store.save(state)
        post = core.cycle("post diagnostic evidence")

        required_protected = {
            "src/agenttest/proposal_review.py",
            "src/agenttest/self_proposal.py",
            "src/agenttest/diagnostics.py",
            "src/agenttest/diagnostic_replay.py",
        }

        return {
            "passed": (
                first_review is not None
                and first_review["verdict"] == "measurement_gap"
                and diagnostic_created
                and diagnostic is not None
                and diagnostic["outcome"] == "stable"
                and not diagnostic["source_state_mutated"]
                and second_created
                and second_review is not None
                and second_review["verdict"] == "no_problem_observed"
                and second_review["patch_authority"] == "none"
                and proposal["status"] == "closed_no_problem_observed"
                and post["metrics"]["reproducibility"] == 1.0
                and required_protected.issubset(PROTECTED_PATHS)
            ),
            "initial_verdict": first_review.get("verdict") if first_review else None,
            "diagnostic_id": diagnostic.get("id") if diagnostic else None,
            "diagnostic_outcome": diagnostic.get("outcome") if diagnostic else None,
            "final_verdict": second_review.get("verdict") if second_review else None,
            "proposal_status": proposal.get("status"),
            "reproducibility": post["metrics"]["reproducibility"],
            "protected": sorted(required_protected.intersection(PROTECTED_PATHS)),
        }
    finally:
        temp.cleanup()


def intervention_aware_prediction_scope() -> dict[str, Any]:
    temp_a, store_a, core_a = fresh()
    temp_b, store_b, core_b = fresh()
    try:
        first = observation(100)
        first["baseline_fingerprint"] = "baseline-a"
        intervened = observation(120)
        intervened["baseline_fingerprint"] = "baseline-b"

        core_a.cycle(observation=first)
        intervention_result = core_a.cycle(observation=intervened)

        stable_first = observation(100)
        stable_first["baseline_fingerprint"] = "baseline-a"
        unexpected = observation(100)
        unexpected["baseline_fingerprint"] = "baseline-a"
        unexpected["working_tree_clean"] = False

        core_b.cycle(observation=stable_first)
        violation_result = core_b.cycle(observation=unexpected)

        return {
            "passed": (
                intervention_result["prediction_result"]["status"]
                == "invalidated_by_intervention"
                and intervention_result["drives"]["prediction_error"] == 0.0
                and intervention_result["intention"]["kind"] != "explain_change"
                and violation_result["prediction_result"]["status"] == "violated"
                and violation_result["drives"]["prediction_error"] == 1.0
                and violation_result["intention"]["kind"] == "explain_change"
            ),
            "intervention_status": intervention_result["prediction_result"]["status"],
            "intervention_prediction_error": intervention_result["drives"]["prediction_error"],
            "intervention_intention": intervention_result["intention"]["kind"],
            "unexpected_status": violation_result["prediction_result"]["status"],
            "unexpected_prediction_error": violation_result["drives"]["prediction_error"],
            "unexpected_intention": violation_result["intention"]["kind"],
        }
    finally:
        temp_a.cleanup()
        temp_b.cleanup()


def self_model_grounding_review() -> dict[str, Any]:
    temp_gap, store_gap, core_gap = fresh()
    temp_grounded, store_grounded, core_grounded = fresh()
    try:
        core_gap.cycle("self model diagnostic gap fixture")
        gap_state = store_gap.load()
        gap_state["self_model"]["capability_claims"] = {}
        gap_proposal = make_change_manifest(
            gap_state,
            title="Calibrate self-model claims against behavioral checks",
            target_dimension="self_model",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Explicit claim calibration reduces unsupported self-description.",
            expected_effect="Capabilities distinguish supported and unverified status.",
            test_plan="Run the verified self-model grounding diagnostic.",
            falsification="Every capability is already explicitly calibrated.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        gap_proposal.update(
            {"id": "M000001", "source": "preservation-eval", "created_cycle": 1}
        )
        gap_state["change_proposals"].append(gap_proposal)

        gap_first_review, _ = review_change_proposal(gap_state, gap_proposal)
        gap_diagnostic, gap_diagnostic_created = run_proposal_diagnostic(
            gap_state,
            gap_proposal,
            gap_first_review,
        )
        gap_second_review, gap_second_created = review_change_proposal(
            gap_state,
            gap_proposal,
        )

        core_grounded.cycle("self model grounded fixture")
        grounded_state = store_grounded.load()
        grounded_state["self_model"]["capability_claims"] = {
            capability: {
                "status": "unverified",
                "evidence_refs": [],
                "reason": "Controlled preservation fixture: explicit uncertainty is grounded.",
            }
            for capability in grounded_state["self_model"]["capabilities"]
        }
        grounded_proposal = make_change_manifest(
            grounded_state,
            title="Calibrate self-model claims against behavioral checks",
            target_dimension="self_model",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Explicit claim calibration reduces unsupported self-description.",
            expected_effect="Capabilities distinguish supported and unverified status.",
            test_plan="Run the verified self-model grounding diagnostic.",
            falsification="Every capability is already explicitly calibrated.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        grounded_proposal.update(
            {"id": "M000001", "source": "preservation-eval", "created_cycle": 1}
        )
        grounded_state["change_proposals"].append(grounded_proposal)

        grounded_first_review, _ = review_change_proposal(
            grounded_state,
            grounded_proposal,
        )
        grounded_diagnostic, grounded_diagnostic_created = run_proposal_diagnostic(
            grounded_state,
            grounded_proposal,
            grounded_first_review,
        )
        grounded_second_review, grounded_second_created = review_change_proposal(
            grounded_state,
            grounded_proposal,
        )

        gap_path_passed = (
            gap_first_review is not None
            and gap_first_review["verdict"] == "measurement_gap"
            and gap_first_review["patch_authority"] == "diagnostic_only"
            and gap_diagnostic_created
            and gap_diagnostic is not None
            and gap_diagnostic["kind"] == "self_model_grounding"
            and gap_diagnostic["outcome"] == "grounding_gap"
            and not gap_diagnostic["source_state_mutated"]
            and gap_second_created
            and gap_second_review is not None
            and gap_second_review["verdict"] == "supported_problem"
            and gap_second_review["patch_authority"] == "candidate_allowed"
        )

        grounded_path_passed = (
            grounded_first_review is not None
            and grounded_first_review["verdict"] == "measurement_gap"
            and grounded_first_review["patch_authority"] == "diagnostic_only"
            and grounded_diagnostic_created
            and grounded_diagnostic is not None
            and grounded_diagnostic["kind"] == "self_model_grounding"
            and grounded_diagnostic["outcome"] == "grounded"
            and not grounded_diagnostic["source_state_mutated"]
            and grounded_second_created
            and grounded_second_review is not None
            and grounded_second_review["verdict"] == "no_problem_observed"
            and grounded_second_review["patch_authority"] == "none"
        )

        return {
            "passed": (
                gap_path_passed
                and grounded_path_passed
                and "src/agenttest/diagnostic_self_model.py" in PROTECTED_PATHS
            ),
            "gap_path": {
                "diagnostic_outcome": (
                    gap_diagnostic.get("outcome") if gap_diagnostic else None
                ),
                "missing_claim_count": (
                    len(gap_diagnostic["result"]["missing_claims"])
                    if gap_diagnostic
                    else None
                ),
                "final_verdict": (
                    gap_second_review.get("verdict")
                    if gap_second_review
                    else None
                ),
                "patch_authority": (
                    gap_second_review.get("patch_authority")
                    if gap_second_review
                    else None
                ),
            },
            "grounded_path": {
                "diagnostic_outcome": (
                    grounded_diagnostic.get("outcome")
                    if grounded_diagnostic
                    else None
                ),
                "coverage": (
                    grounded_diagnostic["result"].get("coverage")
                    if grounded_diagnostic
                    else None
                ),
                "final_verdict": (
                    grounded_second_review.get("verdict")
                    if grounded_second_review
                    else None
                ),
                "patch_authority": (
                    grounded_second_review.get("patch_authority")
                    if grounded_second_review
                    else None
                ),
            },
        }
    finally:
        temp_gap.cleanup()
        temp_grounded.cleanup()


def diagnostic_rechecks_after_intervention() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        baseline_a = observation(100)
        baseline_a["baseline_fingerprint"] = "baseline-a"
        core.cycle(observation=baseline_a)
        state = store.load()
        state["self_model"]["capability_claims"] = {}

        proposal = make_change_manifest(
            state,
            title="Calibrate self-model claims against behavioral checks",
            target_dimension="self_model",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Explicit claim calibration reduces unsupported self-description.",
            expected_effect="Capabilities distinguish supported and unverified status.",
            test_plan="Run the verified self-model grounding diagnostic.",
            falsification="Every capability is already explicitly calibrated.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update(
            {"id": "M000001", "source": "preservation-eval", "created_cycle": 1}
        )
        state["change_proposals"].append(proposal)

        gap_review, _ = review_change_proposal(state, proposal)
        first_diagnostic, first_created = run_proposal_diagnostic(
            state,
            proposal,
            gap_review,
        )
        supported_review, supported_created = review_change_proposal(
            state,
            proposal,
        )
        store.save(state)

        baseline_b = observation(100)
        baseline_b["baseline_fingerprint"] = "baseline-b"
        core.cycle(observation=baseline_b)
        post = store.load()
        post_proposal = next(
            item
            for item in post["change_proposals"]
            if item.get("id") == "M000001"
        )
        original_gap_review = next(
            item
            for item in post["proposal_reviews"]
            if item.get("proposal_id") == "M000001"
            and item.get("verdict") == "measurement_gap"
        )
        second_diagnostic, second_created = run_proposal_diagnostic(
            post,
            post_proposal,
            original_gap_review,
        )
        final_review, final_created = review_change_proposal(
            post,
            post_proposal,
        )

        return {
            "passed": (
                first_created
                and first_diagnostic is not None
                and first_diagnostic["outcome"] == "grounding_gap"
                and first_diagnostic.get("baseline_fingerprint") == "baseline-a"
                and supported_created
                and supported_review is not None
                and supported_review["verdict"] == "supported_problem"
                and second_created
                and second_diagnostic is not None
                and second_diagnostic["id"] != first_diagnostic["id"]
                and second_diagnostic.get("baseline_fingerprint") == "baseline-b"
                and second_diagnostic["outcome"] == "grounded"
                and final_created
                and final_review is not None
                and final_review["verdict"] == "no_problem_observed"
                and final_review["patch_authority"] == "none"
                and post_proposal["status"] == "closed_no_problem_observed"
            ),
            "first_diagnostic": (
                {
                    "id": first_diagnostic.get("id"),
                    "baseline": first_diagnostic.get("baseline_fingerprint"),
                    "outcome": first_diagnostic.get("outcome"),
                }
                if first_diagnostic
                else None
            ),
            "second_diagnostic": (
                {
                    "id": second_diagnostic.get("id"),
                    "baseline": second_diagnostic.get("baseline_fingerprint"),
                    "outcome": second_diagnostic.get("outcome"),
                }
                if second_diagnostic
                else None
            ),
            "intermediate_verdict": (
                supported_review.get("verdict")
                if supported_review
                else None
            ),
            "final_verdict": (
                final_review.get("verdict")
                if final_review
                else None
            ),
        }
    finally:
        temp.cleanup()


def inquiry_family_evidence_review() -> dict[str, Any]:
    temp_inflated, store_inflated, core_inflated = fresh()
    temp_aligned, store_aligned, core_aligned = fresh()
    temp_diverse, store_diverse, core_diverse = fresh()
    try:
        repeated_questions = [
            {
                "id": f"Q{index:06d}",
                "text": (
                    f"What caused repository python_files to change from {index} "
                    f"to {index + 1}, and did that change alter a verified capability?"
                ),
                "status": "open",
            }
            for index in range(1, 7)
        ]

        inflated_state = store_inflated.load()
        inflated_state["cycles"] = 6
        inflated_state["metrics"]["open_endedness"] = 1.0
        inflated_state["questions"] = json.loads(json.dumps(repeated_questions))
        inflated_proposal = make_change_manifest(
            inflated_state,
            title="Track inquiry families across cycles",
            target_dimension="open_endedness",
            files=["src/agenttest/core.py", "src/agenttest/semantic.py", "tests/test_core.py"],
            hypothesis="Question-family tracking can distinguish branching from paraphrase churn.",
            expected_effect="Open-endedness reflects distinct inquiry families.",
            test_plan="Run the verified inquiry-family diagnostic.",
            falsification="Reported open-endedness already matches inquiry-family diversity.",
            rollback="Revert.",
            evidence_refs=["Q000001", "Q000002", "Q000003"],
        )
        inflated_proposal.update(
            {"id": "M000001", "source": "preservation-eval", "created_cycle": 1}
        )
        inflated_state["change_proposals"].append(inflated_proposal)
        inflated_first, _ = review_change_proposal(
            inflated_state,
            inflated_proposal,
        )
        inflated_diag, inflated_created = run_proposal_diagnostic(
            inflated_state,
            inflated_proposal,
            inflated_first,
        )
        inflated_final, inflated_final_created = review_change_proposal(
            inflated_state,
            inflated_proposal,
        )

        aligned_state = store_aligned.load()
        aligned_state["cycles"] = 6
        aligned_state["metrics"]["open_endedness"] = 1.0 / 6.0
        aligned_state["questions"] = json.loads(json.dumps(repeated_questions))
        aligned_proposal = make_change_manifest(
            aligned_state,
            title="Track inquiry families across cycles",
            target_dimension="open_endedness",
            files=["src/agenttest/core.py", "src/agenttest/semantic.py", "tests/test_core.py"],
            hypothesis="Question-family tracking can distinguish branching from paraphrase churn.",
            expected_effect="Open-endedness reflects distinct inquiry families.",
            test_plan="Run the verified inquiry-family diagnostic.",
            falsification="Reported open-endedness already matches inquiry-family diversity.",
            rollback="Revert.",
            evidence_refs=["Q000001", "Q000002", "Q000003"],
        )
        aligned_proposal.update(
            {"id": "M000001", "source": "preservation-eval", "created_cycle": 1}
        )
        aligned_state["change_proposals"].append(aligned_proposal)
        aligned_first, _ = review_change_proposal(aligned_state, aligned_proposal)
        aligned_diag, aligned_created = run_proposal_diagnostic(
            aligned_state,
            aligned_proposal,
            aligned_first,
        )
        aligned_final, aligned_final_created = review_change_proposal(
            aligned_state,
            aligned_proposal,
        )

        diverse_state = store_diverse.load()
        diverse_state["cycles"] = 4
        diverse_state["metrics"]["open_endedness"] = 1.0
        diverse_state["questions"] = [
            {
                "id": "Q000001",
                "text": "What evidence demonstrates state persistence after restart?",
                "status": "open",
            },
            {
                "id": "Q000002",
                "text": "Which observation would falsify the current repository prediction?",
                "status": "open",
            },
            {
                "id": "Q000003",
                "text": "How should semantic memory preserve episode provenance?",
                "status": "open",
            },
            {
                "id": "Q000004",
                "text": "Can a proposed code change preserve every verified behavior?",
                "status": "open",
            },
        ]
        diverse_proposal = make_change_manifest(
            diverse_state,
            title="Track inquiry families across cycles",
            target_dimension="open_endedness",
            files=["src/agenttest/core.py", "src/agenttest/semantic.py", "tests/test_core.py"],
            hypothesis="Question-family tracking can distinguish branching from paraphrase churn.",
            expected_effect="Open-endedness reflects distinct inquiry families.",
            test_plan="Run the verified inquiry-family diagnostic.",
            falsification="Reported open-endedness already matches inquiry-family diversity.",
            rollback="Revert.",
            evidence_refs=["Q000001", "Q000002", "Q000003"],
        )
        diverse_proposal.update(
            {"id": "M000001", "source": "preservation-eval", "created_cycle": 1}
        )
        diverse_state["change_proposals"].append(diverse_proposal)
        diverse_first, _ = review_change_proposal(diverse_state, diverse_proposal)
        diverse_diag, diverse_created = run_proposal_diagnostic(
            diverse_state,
            diverse_proposal,
            diverse_first,
        )
        diverse_final, diverse_final_created = review_change_proposal(
            diverse_state,
            diverse_proposal,
        )

        return {
            "passed": (
                inflated_first is not None
                and inflated_first["verdict"] == "needs_evidence"
                and inflated_created
                and inflated_diag is not None
                and inflated_diag["outcome"] == "paraphrase_churn"
                and inflated_diag["result"]["metric_gap"] > 0.05
                and inflated_diag["result"]["metric_status"] == "inflated"
                and inflated_final_created
                and inflated_final is not None
                and inflated_final["verdict"] == "supported_problem"
                and inflated_final["patch_authority"] == "candidate_allowed"
                and aligned_first is not None
                and aligned_first["verdict"] == "needs_evidence"
                and aligned_created
                and aligned_diag is not None
                and aligned_diag["outcome"] == "paraphrase_churn"
                and aligned_diag["result"]["metric_status"] == "aligned"
                and abs(aligned_diag["result"]["metric_gap"]) <= 0.05
                and aligned_final_created
                and aligned_final is not None
                and aligned_final["verdict"] == "no_problem_observed"
                and aligned_final["patch_authority"] == "none"
                and diverse_first is not None
                and diverse_first["verdict"] == "needs_evidence"
                and diverse_created
                and diverse_diag is not None
                and diverse_diag["outcome"] == "diverse"
                and diverse_final_created
                and diverse_final is not None
                and diverse_final["verdict"] == "no_problem_observed"
                and "src/agenttest/diagnostic_inquiry.py" in PROTECTED_PATHS
            ),
            "inflated": {
                "outcome": inflated_diag.get("outcome") if inflated_diag else None,
                "metric_gap": (
                    inflated_diag["result"].get("metric_gap")
                    if inflated_diag else None
                ),
                "final_verdict": (
                    inflated_final.get("verdict")
                    if inflated_final else None
                ),
            },
            "aligned": {
                "outcome": aligned_diag.get("outcome") if aligned_diag else None,
                "metric_gap": (
                    aligned_diag["result"].get("metric_gap")
                    if aligned_diag else None
                ),
                "final_verdict": (
                    aligned_final.get("verdict")
                    if aligned_final else None
                ),
            },
            "diverse": {
                "outcome": diverse_diag.get("outcome") if diverse_diag else None,
                "family_count": (
                    diverse_diag["result"].get("family_count")
                    if diverse_diag else None
                ),
                "final_verdict": (
                    diverse_final.get("verdict")
                    if diverse_final else None
                ),
            },
        }
    finally:
        temp_inflated.cleanup()
        temp_aligned.cleanup()
        temp_diverse.cleanup()


def human_interaction_roundtrip() -> dict[str, Any]:
    temp, store, core = fresh()
    try:
        core.cycle("alpha persistence memory evidence")
        result = interact(
            "alpha interaction question",
            store=store,
            cognition=True,
            cognition_provider=None,
        )
        reloaded = StateStore(store.path).load()
        record = reloaded["interactions"][-1]
        source_episode = next(
            episode
            for episode in reloaded["episodes"]
            if episode.get("id") == record.get("input_episode_id")
        )
        prior_concepts = [
            item.get("concept")
            for item in result["memory"]["prior_semantic"]
        ]
        interaction_claim = reloaded["self_model"]["capability_claims"][
            "persistent human interaction surface with evidence-linked responses"
        ]
        response_text = result["response_text"]
        response_in_episode = any(
            episode.get("content") == response_text
            for episode in reloaded["episodes"]
        )
        response_in_world = any(
            claim.get("value") == response_text
            for claim in reloaded.get("world_model", {}).get("claims", [])
        )

        return {
            "passed": (
                record["id"] == "H000001"
                and source_episode.get("source") == "human_interaction"
                and source_episode.get("interaction_id") == record["id"]
                and "alpha" in prior_concepts
                and result["cognition"]["event"]["status"] == "unavailable"
                and result["cognition"]["candidate"] is None
                and record.get("question_id") == result["current"]["question"]["id"]
                and record.get("experiment_id") == result["current"]["experiment"]["id"]
                and interaction_claim["status"] == "observed"
                and record["input_episode_id"] in interaction_claim["evidence_refs"]
                and not response_in_episode
                and not response_in_world
            ),
            "interaction_id": record.get("id"),
            "input_episode_id": record.get("input_episode_id"),
            "prior_memory_concepts": prior_concepts,
            "cognition_status": result["cognition"]["event"].get("status"),
            "interaction_claim_status": interaction_claim.get("status"),
            "response_promoted_to_episode": response_in_episode,
            "response_promoted_to_world_claim": response_in_world,
        }
    finally:
        temp.cleanup()


def evidence_debt_evolution_governor() -> dict[str, Any]:
    temp_debt, store_debt, core_debt = fresh()
    temp_aligned, store_aligned, core_aligned = fresh()
    try:
        first = core_debt.cycle(observation=observation(100))
        for _ in range(4):
            core_debt.cycle(observation=observation(100))
        debt_state = store_debt.load()
        debt_state["metrics"]["learning"] = 1.0
        debt_state["drives"]["evidence_hunger"] = 0.8
        debt_experiment = next(
            item
            for item in debt_state["experiments"]
            if item.get("id") == first["experiment"]["id"]
        )
        # Preserve Phase 14 for genuinely evidence-ready closure debt. Phase 15
        # introduced readiness states, so an underspecified experiment is no longer
        # part of this preservation invariant; its governance semantics are tested
        # independently before they are locked into the baseline.
        debt_experiment["readiness"] = "evidence_ready"
        debt_selected = select_change_target(debt_state)

        aligned_state = store_aligned.load()
        aligned_state["cycles"] = 10
        aligned_state["metrics"].update(
            {
                "learning": 1.0,
                "reflection": 1.0,
                "self_model": 1.0,
                "agency": 1.0,
                "curiosity": 1.0,
                "reproducibility": 1.0,
                "perception": 1.0,
                "semantic_memory": 1.0,
                "world_model": 1.0,
                "memory": 1.0,
                "continuity": 1.0,
                "open_endedness": 0.3,
                "cognition": 0.0,
            }
        )
        aligned_state["semantic_memory"]["inquiry_families"] = {
            "open_endedness": 0.3,
            "family_count": 3,
            "question_count": 6,
        }
        aligned_state["questions"] = [
            {"id": "Q000001", "text": "Question one", "status": "open"},
        ]
        aligned_state["episodes"] = [
            {"id": "E000001", "kind": "stimulus", "cycle": 1, "concepts": ["one"]},
        ]
        aligned_state["cognition_candidates"] = []
        aligned_state["cognition_events"] = []
        aligned_selected = select_change_target(aligned_state)

        return {
            "passed": (
                debt_selected is not None
                and debt_selected.get("dimension") == "learning"
                and debt_selected.get("selection_signal") == "stale_evidence_debt"
                and debt_selected.get("experiment_id") == first["experiment"]["id"]
                and first["experiment"]["id"] in debt_selected.get("evidence_refs", [])
                and aligned_selected is None
            ),
            "debt_target": debt_selected.get("dimension") if debt_selected else None,
            "debt_readiness": debt_experiment.get("readiness"),
            "debt_signal": debt_selected.get("selection_signal") if debt_selected else None,
            "debt_experiment": debt_selected.get("experiment_id") if debt_selected else None,
            "aligned_open_endedness_target": (
                aligned_selected.get("dimension") if aligned_selected else None
            ),
        }
    finally:
        temp_debt.cleanup()
        temp_aligned.cleanup()




def verified_intervention_reconciliation() -> dict[str, Any]:
    temp = tempfile.TemporaryDirectory()
    state = StateStore(Path(temp.name) / "organism.json").load()
    try:
        state["cycles"] = 8
        state["change_proposals"] = [
            {
                "id": "M000001",
                "status": "reviewed_supported_problem",
                "target_dimension": "learning",
                "files": ["src/agenttest/core.py", "tests/test_core.py"],
                "protected_paths": sorted(PROTECTED_PATHS),
            }
        ]

        receipt, created = record_verified_intervention(
            state,
            proposal_id="M000001",
            commit_sha="a" * 40,
            changed_files=["src/agenttest/core.py", "tests/test_core.py"],
            verify_run_id=123,
            pr_number=10,
            attribution_text="Verified implementation of M000001",
        )
        repeated, repeated_created = record_verified_intervention(
            state,
            proposal_id="M000001",
            commit_sha="a" * 40,
            changed_files=["src/agenttest/core.py", "tests/test_core.py"],
            verify_run_id=123,
            pr_number=10,
            attribution_text="Verified implementation of M000001",
        )

        proposal = state["change_proposals"][0]
        return {
            "passed": (
                created
                and receipt is not None
                and receipt.get("verification_scope") == "applied_and_preserved"
                and receipt.get("improvement_claim") == "not_implied"
                and receipt.get("verification", {}).get("workflow") == "verify"
                and receipt.get("verification", {}).get("conclusion") == "success"
                and proposal.get("status") == "closed_verified_intervention"
                and proposal.get("accepted_change_id") == receipt.get("id")
                and len(state.get("accepted_changes", [])) == 1
                and state.get("metrics", {}).get("adaptation") == (1.0 / 3.0)
                and not repeated_created
                and repeated == receipt
                and ".github/workflows/reconcile.yml" in PROTECTED_PATHS
                and "scripts/reconcile_verified_change.py" in PROTECTED_PATHS
                and "src/agenttest/intervention.py" in PROTECTED_PATHS
            ),
            "created": created,
            "proposal_status": proposal.get("status"),
            "accepted_change_id": receipt.get("id") if receipt else None,
            "verification_scope": receipt.get("verification_scope") if receipt else None,
            "improvement_claim": receipt.get("improvement_claim") if receipt else None,
            "adaptation": state.get("metrics", {}).get("adaptation"),
            "reused": not repeated_created,
        }
    finally:
        temp.cleanup()




def system_diagnostic_evidence_governance() -> dict[str, Any]:
    temp_backlog, store_backlog, _ = fresh()
    temp_ready, store_ready, _ = fresh()
    try:
        backlog = store_backlog.load()
        backlog["cycles"] = 20
        backlog["generation"] = 20
        backlog["metrics"].update(
            {name: 1.0 for name in backlog.get("metrics", {})}
        )
        backlog["drives"] = {
            "prediction_error": 0.0,
            "specification_pressure": 0.9,
            "evidence_hunger": 0.0,
            "uncertainty": 0.8,
            "continuity_repair": 0.0,
            "calibration_gap": 0.0,
            "novelty_hunger": 0.0,
        }
        backlog["system_diagnostics"] = [
            {
                "id": "SD000001",
                "kind": "experiment_design",
                "status": "completed",
                "diagnostic_version": "experiment-design-v2",
                "outcome": "specification_backlog",
                "created_cycle": 20,
                "source_state_mutated": False,
                "result": {
                    "specification_backlog_count": 4,
                    "executable_experiment_count": 0,
                    "contracted_ratio": 0.0,
                },
            }
        ]

        proposal, proposal_created = propose_self_change(backlog)
        review, review_created = review_change_proposal(backlog, proposal)
        manifest_valid, validation_reason = (
            validate_change_manifest(proposal, backlog)
            if proposal is not None
            else (False, "no proposal")
        )

        ready = store_ready.load()
        ready["cycles"] = 20
        ready["metrics"].update({name: 1.0 for name in ready.get("metrics", {})})
        ready["system_diagnostics"] = [
            {
                "id": "SD000002",
                "kind": "experiment_design",
                "status": "completed",
                "diagnostic_version": "experiment-design-v2",
                "outcome": "evidence_ready",
                "created_cycle": 20,
                "source_state_mutated": False,
                "result": {
                    "specification_backlog_count": 0,
                    "executable_experiment_count": 2,
                    "contracted_ratio": 1.0,
                },
            }
        ]
        ready_selected = select_change_target(ready)

        return {
            "passed": (
                "SD000001" in known_evidence_ids(backlog)
                and proposal_created
                and proposal is not None
                and proposal.get("selection_signal")
                == "experiment_design_specification_backlog"
                and proposal.get("source_diagnostic_id") == "SD000001"
                and proposal.get("evidence_refs") == ["SD000001"]
                and manifest_valid
                and review_created
                and review is not None
                and review.get("review_version") == "proposal-review-v5"
                and review.get("verdict") == "supported_problem"
                and review.get("patch_authority") == "candidate_allowed"
                and review.get("direct_diagnostic_id") == "SD000001"
                and review.get("considered_system_diagnostic_ids")
                == ["SD000001"]
                and ready_selected is None
                and "src/agenttest/evidence.py" in PROTECTED_PATHS
            ),
            "proposal_id": proposal.get("id") if proposal else None,
            "selection_signal": (
                proposal.get("selection_signal") if proposal else None
            ),
            "source_diagnostic_id": (
                proposal.get("source_diagnostic_id") if proposal else None
            ),
            "manifest_valid": manifest_valid,
            "validation_reason": validation_reason,
            "review_version": review.get("review_version") if review else None,
            "verdict": review.get("verdict") if review else None,
            "patch_authority": review.get("patch_authority") if review else None,
            "ready_target": (
                ready_selected.get("dimension") if ready_selected else None
            ),
            "evidence_authority_protected": (
                "src/agenttest/evidence.py" in PROTECTED_PATHS
            ),
        }
    finally:
        temp_backlog.cleanup()
        temp_ready.cleanup()




def blocked_attention_diagnostic_governance() -> dict[str, Any]:
    temp_loop, store_loop, _ = fresh()
    temp_clean, store_clean, _ = fresh()
    try:
        loop = store_loop.load()
        loop["cycles"] = 30
        loop["metrics"].update({name: 1.0 for name in loop.get("metrics", {})})
        loop["drives"] = {
            "prediction_error": 0.0,
            "specification_pressure": 0.0,
            "evidence_hunger": 0.0,
            "uncertainty": 0.8,
            "continuity_repair": 0.0,
            "calibration_gap": 0.0,
            "novelty_hunger": 0.0,
        }
        loop["system_diagnostics"] = [
            {
                "id": "SD000009",
                "kind": "attention_control",
                "status": "completed",
                "diagnostic_version": "blocked-attention-v1",
                "outcome": "blocked_attention_loop",
                "created_cycle": 30,
                "source_state_mutated": False,
                "result": {
                    "loop_count": 1,
                    "loop_experiment_ids": ["X000011"],
                    "reselected_after_block_count": 1,
                },
            }
        ]

        proposal, proposal_created = propose_self_change(loop)
        review, review_created = review_change_proposal(loop, proposal)
        manifest_valid, validation_reason = (
            validate_change_manifest(proposal, loop)
            if proposal is not None
            else (False, "no proposal")
        )

        clean = store_clean.load()
        clean["cycles"] = 30
        clean["metrics"].update({name: 1.0 for name in clean.get("metrics", {})})
        clean["drives"] = {"uncertainty": 0.8}
        clean["system_diagnostics"] = [
            {
                "id": "SD000010",
                "kind": "attention_control",
                "status": "completed",
                "diagnostic_version": "blocked-attention-v1",
                "outcome": "attention_redirected",
                "created_cycle": 30,
                "source_state_mutated": False,
                "result": {
                    "loop_count": 0,
                    "reselected_after_block_count": 0,
                },
            }
        ]
        clean_selected = select_change_target(clean)

        addressed = store_clean.load()
        addressed["cycles"] = 44
        addressed["metrics"].update(
            {name: 1.0 for name in addressed.get("metrics", {})}
        )
        addressed["drives"] = {"uncertainty": 0.8}
        addressed["system_diagnostics"] = [
            {
                "id": "SD000013",
                "kind": "attention_control",
                "status": "completed",
                "diagnostic_version": "blocked-attention-v1",
                "outcome": "blocked_attention_loop",
                "created_cycle": 44,
                "source_state_mutated": False,
            }
        ]
        addressed["change_proposals"] = [
            {
                "id": "M000011",
                "status": "closed_verified_intervention",
                "selection_signal": "attention_control_blocked_attention_loop",
                "accepted_change_id": "A000003",
            }
        ]
        addressed["accepted_changes"] = [
            {
                "id": "A000003",
                "proposal_id": "M000011",
                "accepted_cycle": 44,
            }
        ]
        addressed_selected = select_change_target(addressed)

        newer = json.loads(json.dumps(addressed))
        newer["cycles"] = 45
        newer["system_diagnostics"][0]["id"] = "SD000014"
        newer["system_diagnostics"][0]["created_cycle"] = 45
        newer_selected = select_change_target(newer)

        return {
            "passed": (
                "SD000009" in known_evidence_ids(loop)
                and proposal_created
                and proposal is not None
                and proposal.get("target_dimension") == "agency"
                and proposal.get("selection_signal")
                == "attention_control_blocked_attention_loop"
                and proposal.get("source_diagnostic_id") == "SD000009"
                and proposal.get("evidence_refs") == ["SD000009"]
                and manifest_valid
                and review_created
                and review is not None
                and review.get("verdict") == "supported_problem"
                and review.get("patch_authority") == "candidate_allowed"
                and review.get("direct_diagnostic_id") == "SD000009"
                and clean_selected is None
                and addressed_selected is None
                and newer_selected is not None
                and newer_selected.get("source_diagnostic_id") == "SD000014"
            ),
            "proposal_id": proposal.get("id") if proposal else None,
            "target_dimension": (
                proposal.get("target_dimension") if proposal else None
            ),
            "selection_signal": (
                proposal.get("selection_signal") if proposal else None
            ),
            "source_diagnostic_id": (
                proposal.get("source_diagnostic_id") if proposal else None
            ),
            "manifest_valid": manifest_valid,
            "validation_reason": validation_reason,
            "verdict": review.get("verdict") if review else None,
            "patch_authority": review.get("patch_authority") if review else None,
            "clean_target": (
                clean_selected.get("dimension") if clean_selected else None
            ),
            "addressed_target": (
                addressed_selected.get("dimension")
                if addressed_selected else None
            ),
            "newer_source_diagnostic_id": (
                newer_selected.get("source_diagnostic_id")
                if newer_selected else None
            ),
        }
    finally:
        temp_loop.cleanup()
        temp_clean.cleanup()




def specification_backlog_lifecycle_scope() -> dict[str, Any]:
    temp_transient, store_transient, _ = fresh()
    temp_stale, store_stale, _ = fresh()
    try:
        transient = store_transient.load()
        transient["cycles"] = 45
        transient["metrics"].update(
            {name: 1.0 for name in transient.get("metrics", {})}
        )
        transient["experiments"] = [
            {
                "id": "X000020",
                "cycle": 45,
                "status": "proposed",
                "question_id": "Q000009",
            }
        ]
        transient["system_diagnostics"] = [
            {
                "id": "SD000014",
                "kind": "experiment_design",
                "status": "completed",
                "diagnostic_version": "experiment-design-v3",
                "outcome": "specification_backlog",
                "created_cycle": 45,
                "source_state_mutated": False,
                "result": {
                    "untriaged_specification_ids": ["X000020"],
                    "specification_backlog_count": 1,
                },
            }
        ]
        transient_selected = select_change_target(transient)

        stale = store_stale.load()
        stale["cycles"] = 45
        stale["metrics"].update(
            {name: 1.0 for name in stale.get("metrics", {})}
        )
        stale["experiments"] = [
            {
                "id": "X000020",
                "cycle": 43,
                "status": "proposed",
                "question_id": "Q000009",
            }
        ]
        stale["system_diagnostics"] = json.loads(
            json.dumps(transient["system_diagnostics"])
        )
        stale_selected = select_change_target(stale)

        return {
            "passed": (
                transient_selected is None
                and stale_selected is not None
                and stale_selected.get("selection_signal")
                == "experiment_design_specification_backlog"
                and stale_selected.get("source_diagnostic_id") == "SD000014"
            ),
            "transient_target": (
                transient_selected.get("dimension")
                if transient_selected else None
            ),
            "stale_target": (
                stale_selected.get("dimension") if stale_selected else None
            ),
            "stale_signal": (
                stale_selected.get("selection_signal")
                if stale_selected else None
            ),
        }
    finally:
        temp_transient.cleanup()
        temp_stale.cleanup()


CHECKS: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    ("persistence_reload", persistence_reload),
    ("prediction_confirmation", prediction_confirmation),
    ("prediction_error_focus", prediction_error_focus),
    ("evidence_hunger_reuses_work", evidence_hunger_reuses_work),
    ("cognition_grounding_gate", cognition_grounding_gate),
    ("semantic_provenance", semantic_provenance),
    ("world_revision_provenance", world_revision_provenance),
    ("experiment_outcome_world_claim", experiment_outcome_world_claim),
    ("self_change_proposal_governance", self_change_proposal_governance),
    ("proposal_review_requires_direct_problem_evidence", proposal_review_requires_direct_problem_evidence),
    ("verified_diagnostic_resolution", verified_diagnostic_resolution),
    ("intervention_aware_prediction_scope", intervention_aware_prediction_scope),
    ("self_model_grounding_review", self_model_grounding_review),
    ("diagnostic_rechecks_after_intervention", diagnostic_rechecks_after_intervention),
    ("inquiry_family_evidence_review", inquiry_family_evidence_review),
    ("human_interaction_roundtrip", human_interaction_roundtrip),
    ("evidence_debt_evolution_governor", evidence_debt_evolution_governor),
    ("verified_intervention_reconciliation", verified_intervention_reconciliation),
    ("system_diagnostic_evidence_governance", system_diagnostic_evidence_governance),
    ("blocked_attention_diagnostic_governance", blocked_attention_diagnostic_governance),
    ("specification_backlog_lifecycle_scope", specification_backlog_lifecycle_scope),
]


def evaluate() -> dict[str, Any]:
    os.environ.pop("OPENAI_API_KEY", None)
    checks = {name: run_check(name, fn) for name, fn in CHECKS}
    return {
        "suite": SUITE,
        "checks": checks,
        "all_passed": all(item["passed"] for item in checks.values()),
        "passed_count": sum(1 for item in checks.values() if item["passed"]),
        "check_count": len(checks),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    result = evaluate()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.strict and not result["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
