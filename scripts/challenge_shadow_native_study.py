from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "scripts"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from challenge_shadow_recorder import (
    ChallengeShadowRecorder,
    reviewed_source_descriptor,
    single_transition_outcome,
    source_manifest,
)
from native_observe_inquire_integration import (
    observe_and_inquire_policy,
    stage_publication_inquiry,
)
from open_object_world_challenge import initial_world, observe_world, transition
from open_object_world_challenge_explorer import (
    choose_command,
    command_key,
    observation_signature,
)
from phase42_resumption_opportunity_eval import evaluate_resumption_opportunities

PRODUCTION_BASE = "bd78db8342d267822795f59a395fe5958beeed84"
PINNED_STATE = "825d2c86759f5f4065807508ab7fbfe3462feb8a"
CHECKPOINT = 600
MAX_OUTCOME_STEPS = 96


def _thread_ids(state):
    return {
        str(item.get("id"))
        for item in state.get("agenda", {}).get("threads", [])
        if isinstance(item, dict) and item.get("id")
    }


def _archived_ids(state):
    return {
        str(item.get("id"))
        for item in state.get("agenda", {}).get("archived_threads", [])
        if isinstance(item, dict) and item.get("id")
    }


def _stream_prefix(recorder_store: StateStore, seed: int):
    recorder = ChallengeShadowRecorder(recorder_store, enabled=True)
    world = initial_world(seed)
    attempts = Counter()
    observation = observe_world(world)
    recorder.ingest(observation)

    for cycle in range(1, CHECKPOINT + 1):
        command = choose_command(observation, attempts)
        attempts[(observation_signature(observation), command_key(command))] += 1
        world, receipt = transition(world, command, cycle=cycle)
        observation = observe_world(world)
        recorder.ingest(observation, receipt)

    return recorder, world, attempts, observation


def _find_and_record_outcome(
    store: StateStore,
    recorder: ChallengeShadowRecorder,
    world,
    attempts,
    candidate,
):
    observation = observe_world(world)
    for cycle in range(CHECKPOINT + 1, CHECKPOINT + MAX_OUTCOME_STEPS + 1):
        command = choose_command(observation, attempts)
        attempts[(observation_signature(observation), command_key(command))] += 1
        next_world, receipt = transition(world, command, cycle=cycle)
        next_observation = observe_world(next_world)
        recorder.ingest(next_observation, receipt)
        payload = single_transition_outcome(
            before=observation,
            after=next_observation,
            candidate=candidate,
        )
        if payload is not None:
            evidence = AgentCore(store).record_native_evidence(
                payload,
                enabled=True,
                persist=True,
            )
            return {
                "world": next_world,
                "attempts": attempts,
                "before": observation,
                "after": next_observation,
                "command": command,
                "receipt": receipt,
                "payload": payload,
                "evidence_ref": evidence["evidence_ref"],
                "steps_after_inquiry": cycle - CHECKPOINT,
            }
        world = next_world
        observation = next_observation
    raise AssertionError("selected challenge feature never became post-inquiry evaluable")


def run_one(source_state: Path, seed: int, root: Path):
    state_path = root / f"seed-{seed}" / "organism.json"
    state_path.parent.mkdir(parents=True)
    shutil.copy2(source_state, state_path)
    store = StateStore(state_path)
    baseline = store.load()
    baseline_diag = evaluate_resumption_opportunities(baseline)
    if baseline_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("pinned baseline begins with Phase42 mismatch")
    if not baseline.get("environment_snapshots"):
        raise AssertionError("pinned baseline has no repository observation")

    baseline_cycle = int(baseline["cycles"])
    baseline_threads = _thread_ids(baseline)
    baseline_action = deepcopy(baseline.get("action_lab"))
    baseline_planning = deepcopy(baseline.get("planning_lab"))
    baseline_agenda_decisions = len(baseline.get("agenda", {}).get("decisions", []))
    stable_repo_observation = deepcopy(baseline["environment_snapshots"][-1])

    recorder_store = StateStore(root / f"seed-{seed}" / "recorder.json")
    recorder_store.save(initial_state())
    recorder, world, attempts, _ = _stream_prefix(recorder_store, seed)
    publication = recorder.publication()
    candidate = publication["selected_temporal_candidate"]

    after_stream = store.load()
    if after_stream["cycles"] != baseline_cycle:
        raise AssertionError("shadow recording advanced Ora cycle")
    if after_stream.get("action_lab") != baseline_action:
        raise AssertionError("shadow recording changed Action Lab")
    if after_stream.get("planning_lab") != baseline_planning:
        raise AssertionError("shadow recording changed Planning Lab")
    if len(after_stream.get("agenda", {}).get("decisions", [])) != baseline_agenda_decisions:
        raise AssertionError("shadow recording changed agenda decisions")

    staged = stage_publication_inquiry(
        AgentCore(store),
        policy=observe_and_inquire_policy(),
        source_manifest=source_manifest(),
        publication=publication,
    )
    after_stage = store.load()
    if after_stage["cycles"] != baseline_cycle:
        raise AssertionError("native staging advanced Ora cycle")
    if _thread_ids(after_stage) != baseline_threads:
        raise AssertionError("native staging changed agenda threads before a cycle")
    if after_stage.get("action_lab") != baseline_action:
        raise AssertionError("native staging changed Action Lab")
    if after_stage.get("planning_lab") != baseline_planning:
        raise AssertionError("native staging changed Planning Lab")

    experiment_id = staged["inquiry_result"]["experiment"]["id"]
    question_id = staged["inquiry_result"]["question"]["id"]

    ordinary = AgentCore(StateStore(state_path))
    first_cycle = ordinary.cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_repo_observation),
        _now_override=f"2026-10-05T18:0{seed}:00+00:00",
    )
    after_first = ordinary.store.load()
    if after_first["cycles"] != baseline_cycle + 1:
        raise AssertionError("ordinary handoff did not advance exactly one cycle")
    if first_cycle["action_lab_result"] is not None:
        raise AssertionError("shadow inquiry granted Action Lab authority")
    if first_cycle["planning_lab_result"] is not None:
        raise AssertionError("shadow inquiry granted Planning Lab authority")

    native_summary = next(
        (
            row
            for row in first_cycle["agenda_decision"].get("candidate_summaries", [])
            if row.get("question_id") == question_id
        ),
        None,
    )
    if not native_summary or native_summary.get("active_experiment_path") is not True:
        raise AssertionError("challenge native inquiry did not enter ordinary agenda")

    preserved = _thread_ids(after_first) | _archived_ids(after_first)
    if not baseline_threads <= preserved:
        raise AssertionError("challenge inquiry lost preexisting thread identity")
    first_diag = evaluate_resumption_opportunities(after_first)
    if first_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("challenge inquiry introduced Phase42 mismatch")
    if baseline_diag["resumed_opportunity_count"] == 0 and first_diag["resumed_opportunity_count"] != 0:
        raise AssertionError("challenge inquiry manufactured Phase42 resumption")

    outcome = _find_and_record_outcome(
        store,
        recorder,
        world,
        attempts,
        candidate,
    )
    resolved = AgentCore(store).resolve_native_inquiry(
        experiment_id,
        outcome["evidence_ref"],
        enabled=True,
        persist=True,
        _now_override=f"2026-10-05T18:1{seed}:00+00:00",
    )
    if resolved["experiment"]["status"] != "completed":
        raise AssertionError("challenge native inquiry did not resolve")

    after_resolution = store.load()
    resolved_experiment = next(
        row for row in after_resolution["experiments"]
        if row["id"] == experiment_id
    )
    if resolved_experiment["readiness"] != "resolved":
        raise AssertionError("resolved inquiry did not persist resolved readiness")

    final_core = AgentCore(StateStore(state_path))
    final_cycle = final_core.cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_repo_observation),
        _now_override=f"2026-10-05T18:2{seed}:00+00:00",
    )
    final = final_core.store.load()
    final_diag = evaluate_resumption_opportunities(final)
    if final_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("post-resolution cycle introduced Phase42 mismatch")
    if baseline_diag["resumed_opportunity_count"] == 0 and final_diag["resumed_opportunity_count"] != 0:
        raise AssertionError("post-resolution cycle manufactured Phase42 resumption")
    if final_cycle["action_lab_result"] is not None or final_cycle["planning_lab_result"] is not None:
        raise AssertionError("shadow loop granted lab authority after resolution")

    return {
        "seed": seed,
        "baseline_cycle": baseline_cycle,
        "final_cycle": int(final["cycles"]),
        "selected_candidate": candidate,
        "source_id": source_manifest()["source_id"],
        "question_id": question_id,
        "experiment_id": experiment_id,
        "first_cycle_selected_thread_id": first_cycle["agenda_decision"].get("selected_thread_id"),
        "first_cycle_foreground_changed": bool(first_cycle["agenda_decision"].get("foreground_changed")),
        "outcome_action": outcome["command"],
        "outcome_receipt_effects": outcome["receipt"].get("observed_effects", []),
        "outcome_steps_after_inquiry": outcome["steps_after_inquiry"],
        "outcome": resolved_experiment["outcome"],
        "outcome_evidence_ref": outcome["evidence_ref"],
        "phase42_before": {
            "opportunities": baseline_diag["opportunity_count"],
            "resumed": baseline_diag["resumed_opportunity_count"],
            "mismatch": baseline_diag["handoff_or_selection_mismatch_count"],
        },
        "phase42_after_first_cycle": {
            "opportunities": first_diag["opportunity_count"],
            "resumed": first_diag["resumed_opportunity_count"],
            "mismatch": first_diag["handoff_or_selection_mismatch_count"],
        },
        "phase42_final": {
            "opportunities": final_diag["opportunity_count"],
            "resumed": final_diag["resumed_opportunity_count"],
            "mismatch": final_diag["handoff_or_selection_mismatch_count"],
        },
        "authority": {
            "challenge_actions_chosen_by_live_ora": False,
            "challenge_actions_chosen_by_frozen_external_explorer": True,
            "environment_action_authority": False,
            "action_lab": False,
            "planning_lab": False,
            "phase42_credit": False,
            "external_model_api": False,
        },
    }


def run(source_state: Path):
    source_bytes = source_state.read_bytes()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        rows = [run_one(source_state, seed, root) for seed in range(1, 5)]
    if source_state.read_bytes() != source_bytes:
        raise AssertionError("pinned source state changed")
    return {
        "study": "challenge-shadow-native-resolved-loop-v1",
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "reviewed_source": reviewed_source_descriptor(),
        "checkpoint": CHECKPOINT,
        "layout_count": 4,
        "all_staged": len(rows) == 4,
        "all_resolved": all(row["outcome"] in {"supported","falsified"} for row in rows),
        "all_phase42_clean": all(
            row["phase42_final"]["mismatch"] == 0
            and row["phase42_final"]["resumed"] == 0
            for row in rows
        ),
        "supported_count": sum(row["outcome"] == "supported" for row in rows),
        "falsified_count": sum(row["outcome"] == "falsified" for row in rows),
        "max_outcome_steps": max(row["outcome_steps_after_inquiry"] for row in rows),
        "rows": rows,
        "source_unchanged": True,
        "passed": (
            len(rows) == 4
            and all(row["outcome"] in {"supported","falsified"} for row in rows)
            and all(
                row["phase42_final"]["mismatch"] == 0
                and row["phase42_final"]["resumed"] == 0
                for row in rows
            )
        ),
        "limitations": [
            "Challenge actions remain external frozen-explorer actions; live Ora has no environment action authority.",
            "The reviewed source is integrity-pinned but unsigned.",
            "Each layout uses a separate copied Ora state, so inquiries do not compete with each other.",
            "This proves a shadow public-observation/native-inquiry loop, not general problem solving or Phase42 progress.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run(Path(args.state))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(json.dumps({
        "passed": report["passed"],
        "all_staged": report["all_staged"],
        "all_resolved": report["all_resolved"],
        "all_phase42_clean": report["all_phase42_clean"],
        "supported_count": report["supported_count"],
        "falsified_count": report["falsified_count"],
        "max_outcome_steps": report["max_outcome_steps"],
    }, sort_keys=True))
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
