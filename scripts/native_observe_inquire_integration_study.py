from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "scripts"))

from agenttest.core import AgentCore
from agenttest.state import StateStore
from native_observe_inquire_integration import (
    PUBLICATION_VERSION,
    SOURCE_MANIFEST_VERSION,
    observe_and_inquire_policy,
    source_manifest_hash,
    stage_publication_inquiry,
)
from phase42_resumption_opportunity_eval import evaluate_resumption_opportunities

PRODUCTION_BASE = "eb906904d4a30d7427075987f928e0b97699cfe3"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_manifest() -> dict:
    return {
        "version": SOURCE_MANIFEST_VERSION,
        "source_id": "research.fixture.observe_inquire",
        "source_kind": "public_observation_stream",
        "observation_schema": "public-fixture-v1",
        "recorder_version": "public-stream-recorder-v1",
        "provenance_mode": "hash_chained_unsigned",
        "cumulative_publications": True,
        "max_recent_observation_refs": 64,
        "signed_source": False,
        "allow_environment_actions": False,
    }


def publication() -> dict:
    manifest = source_manifest()
    return {
        "version": PUBLICATION_VERSION,
        "source_id": manifest["source_id"],
        "source_manifest_hash": source_manifest_hash(manifest),
        "chain_hash": _hash_text("fixed-observe-inquire-integration-fixture"),
        "coverage": {"start_cycle": 0, "end_cycle": 4},
        "observation_refs": [
            f"{manifest['source_id']}:obs-{index:04d}"
            for index in range(5)
        ],
        "selected_temporal_candidate": {
            "relation": "same_next_observation",
            "feature": "public_feature",
            "objective": "information_gain",
            "objective_score": 0.2,
            "evaluable": 4,
            "confirmations": 3,
            "refutations": 1,
        },
    }


def _thread_ids(state: dict) -> set[str]:
    return {
        str(item.get("id"))
        for item in state.get("agenda", {}).get("threads", [])
        if isinstance(item, dict) and item.get("id")
    }


def _archived_threads(state: dict) -> dict[str, dict]:
    return {
        str(item.get("id")): item
        for item in state.get("agenda", {}).get("archived_threads", [])
        if isinstance(item, dict) and item.get("id")
    }


def run(state_path: Path, live_state_sha: str) -> dict:
    store = StateStore(state_path)
    baseline = store.load()
    baseline_diag = evaluate_resumption_opportunities(baseline)
    if baseline_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("pinned live-state copy begins with Phase42 mismatch")

    baseline_cycle = int(baseline["cycles"])
    baseline_threads = _thread_ids(baseline)
    baseline_action = deepcopy(baseline.get("action_lab"))
    baseline_planning = deepcopy(baseline.get("planning_lab"))
    if not baseline.get("environment_snapshots"):
        raise AssertionError("pinned live-state copy has no repository observation")
    stable_observation = deepcopy(baseline["environment_snapshots"][-1])
    phase42_thread_id = (
        baseline_diag["opportunities"][-1]["thread_id"]
        if baseline_diag.get("opportunities")
        else None
    )
    phase42_question_id = (
        baseline_diag["opportunities"][-1]["question_id"]
        if baseline_diag.get("opportunities")
        else None
    )
    baseline_agenda_decision_count = len(
        baseline.get("agenda", {}).get("decisions", [])
    )

    staged = stage_publication_inquiry(
        AgentCore(store),
        policy=observe_and_inquire_policy(),
        source_manifest=source_manifest(),
        publication=publication(),
    )
    after_stage = store.load()
    if after_stage["cycles"] != baseline_cycle:
        raise AssertionError("native staging advanced organism cycle")
    if after_stage.get("action_lab") != baseline_action:
        raise AssertionError("native staging changed Action Lab state")
    if after_stage.get("planning_lab") != baseline_planning:
        raise AssertionError("native staging changed Planning Lab state")
    if len(after_stage.get("agenda", {}).get("decisions", [])) != baseline_agenda_decision_count:
        raise AssertionError("native staging created an agenda decision outside a cycle")
    if _thread_ids(after_stage) != baseline_threads:
        raise AssertionError("native staging changed persisted agenda threads outside a cycle")

    question_id = staged["inquiry_result"]["question"]["id"]
    reloaded = AgentCore(StateStore(state_path))
    cycle_result = reloaded.cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_observation),
        _now_override="2026-10-05T12:00:00+00:00",
    )
    after_cycle = reloaded.store.load()

    if after_cycle["cycles"] != baseline_cycle + 1:
        raise AssertionError("ordinary Core handoff did not advance exactly one cycle")
    if cycle_result["action_lab_result"] is not None:
        raise AssertionError("observe/inquire integration granted Action Lab authority")
    if cycle_result["planning_lab_result"] is not None:
        raise AssertionError("observe/inquire integration granted Planning Lab authority")

    decision = cycle_result["agenda_decision"]
    if not isinstance(decision, dict):
        raise AssertionError("ordinary cycle produced no agenda decision")
    native_summary = next(
        (
            item
            for item in decision.get("candidate_summaries", [])
            if item.get("question_id") == question_id
        ),
        None,
    )
    if native_summary is None:
        raise AssertionError("staged native inquiry did not reach ordinary agenda")
    if native_summary.get("active_experiment_path") is not True:
        raise AssertionError("native inquiry lost its active experiment path")

    after_threads = _thread_ids(after_cycle)
    after_archived = _archived_threads(after_cycle)
    preserved_thread_ids = after_threads | set(after_archived)
    if not baseline_threads <= preserved_thread_ids:
        raise AssertionError(
            "ordinary integration cycle lost preexisting agenda thread identity"
        )
    moved_to_archive = sorted(baseline_threads - after_threads)
    for thread_id in moved_to_archive:
        archived = after_archived.get(thread_id)
        if not isinstance(archived, dict):
            raise AssertionError("bounded agenda eviction did not preserve thread")
        if archived.get("archive_reason") != "outside_current_bounded_agenda":
            raise AssertionError("preexisting thread archived for unexpected reason")

    after_diag = evaluate_resumption_opportunities(after_cycle)
    if after_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("integration cycle introduced Phase42 selection mismatch")
    if (
        baseline_diag["resumed_opportunity_count"] == 0
        and after_diag["resumed_opportunity_count"] != 0
    ):
        raise AssertionError(
            "observe/inquire integration manufactured Phase42 resumption credit"
        )

    phase42_trajectory = []
    trajectory_core = AgentCore(StateStore(state_path))
    for offset in range(1, 5):
        result = trajectory_core.cycle(
            stimulus="continue ordinary operation",
            observation=deepcopy(stable_observation),
            _now_override=f"2026-10-05T12:0{offset}:00+00:00",
        )
        current = trajectory_core.store.load()
        active = {
            str(item.get("id")): item
            for item in current.get("agenda", {}).get("threads", [])
            if isinstance(item, dict) and item.get("id")
        }
        archived = _archived_threads(current)
        location = (
            "active"
            if phase42_thread_id in active
            else "archived"
            if phase42_thread_id in archived
            else "missing"
        )
        if location == "missing":
            raise AssertionError("Phase42 thread identity disappeared during copied heartbeats")
        diagnostic = evaluate_resumption_opportunities(current)
        if diagnostic["handoff_or_selection_mismatch_count"] != 0:
            raise AssertionError("copied heartbeat introduced Phase42 selection mismatch")
        thread = active.get(phase42_thread_id) or archived.get(phase42_thread_id) or {}
        phase42_trajectory.append(
            {
                "cycle": int(current["cycles"]),
                "location": location,
                "thread_id": phase42_thread_id,
                "question_id": phase42_question_id,
                "thread_status": thread.get("status"),
                "thread_priority_score": thread.get("priority_score"),
                "selected_thread_id": result.get("agenda_decision", {}).get(
                    "selected_thread_id"
                ),
                "resumed_thread_id": result.get("agenda_decision", {}).get(
                    "resumed_thread_id"
                ),
                "resumed_opportunity_count": diagnostic[
                    "resumed_opportunity_count"
                ],
                "handoff_or_selection_mismatch_count": diagnostic[
                    "handoff_or_selection_mismatch_count"
                ],
            }
        )

    source_hash = source_manifest_hash(source_manifest())
    return {
        "study": "native-observe-inquire-copied-live-state-v1",
        "production_base": PRODUCTION_BASE,
        "pinned_live_state_sha": live_state_sha,
        "baseline_cycle": baseline_cycle,
        "after_cycle": int(after_cycle["cycles"]),
        "source_id": source_manifest()["source_id"],
        "source_manifest_hash": source_hash,
        "candidate_id": staged["candidate_id"],
        "question_id": question_id,
        "staging": {
            "cycle_unchanged": True,
            "agenda_decisions_unchanged": True,
            "agenda_threads_unchanged": True,
            "action_lab_state_unchanged": True,
            "planning_lab_state_unchanged": True,
        },
        "ordinary_cycle": {
            "used_stable_repository_observation": True,
            "native_inquiry_reached_agenda": True,
            "active_experiment_path": True,
            "action_lab_result": None,
            "planning_lab_result": None,
            "preexisting_thread_identity_preserved": True,
            "preexisting_active_threads_moved_to_archive": moved_to_archive,
            "bounded_active_thread_count": len(after_threads),
            "selected_question_id": decision.get("selected", {}).get("question_id"),
            "selected_thread_id": decision.get("selected_thread_id"),
            "foreground_changed": bool(decision.get("foreground_changed")),
            "resumed_thread_id": decision.get("resumed_thread_id"),
        },
        "phase42_thread_id": phase42_thread_id,
        "phase42_question_id": phase42_question_id,
        "phase42_followup_trajectory": phase42_trajectory,
        "phase42_before": {
            "opportunity_count": baseline_diag["opportunity_count"],
            "resumed_opportunity_count": baseline_diag[
                "resumed_opportunity_count"
            ],
            "lower_priority_opportunity_count": baseline_diag[
                "lower_priority_opportunity_count"
            ],
            "handoff_or_selection_mismatch_count": baseline_diag[
                "handoff_or_selection_mismatch_count"
            ],
        },
        "phase42_after": {
            "opportunity_count": after_diag["opportunity_count"],
            "resumed_opportunity_count": after_diag[
                "resumed_opportunity_count"
            ],
            "lower_priority_opportunity_count": after_diag[
                "lower_priority_opportunity_count"
            ],
            "handoff_or_selection_mismatch_count": after_diag[
                "handoff_or_selection_mismatch_count"
            ],
        },
        "authority": {
            "environment_actions": False,
            "action_lab": False,
            "planning_lab": False,
            "phase42_credit": False,
            "external_model_api": False,
        },
        "limitations": [
            "The source is a fixed public-stream fixture; authenticity is not proven by a signed registry.",
            "The recorder publication is cumulative and must be treated as a current snapshot, not added to overlapping snapshots.",
            "This is copied-state observation/inquiry integration only; no environment action authority is activated.",
            "Rollback after later ordinary cycles must disable future staging rather than automatically rewind unrelated organism progress.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--live-state-sha", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run(Path(args.state), args.live_state_sha)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
