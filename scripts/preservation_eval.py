from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Callable

from agenttest.cognition import StaticCognitionProvider
from agenttest.core import AgentCore
from agenttest.semantic import retrieve_semantic_memory
from agenttest.state import StateStore
from agenttest.world import current_world_claims

SUITE = "behavioral-preservation-v1"


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


CHECKS: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    ("persistence_reload", persistence_reload),
    ("prediction_confirmation", prediction_confirmation),
    ("prediction_error_focus", prediction_error_focus),
    ("evidence_hunger_reuses_work", evidence_hunger_reuses_work),
    ("cognition_grounding_gate", cognition_grounding_gate),
    ("semantic_provenance", semantic_provenance),
    ("world_revision_provenance", world_revision_provenance),
    ("experiment_outcome_world_claim", experiment_outcome_world_claim),
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
