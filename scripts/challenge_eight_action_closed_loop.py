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
from challenge_action_authority import ChallengeActionExecutor
from challenge_shadow_recorder import (
    ChallengeShadowRecorder,
    STATE_KEY as RECORDER_STATE_KEY,
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

PRODUCTION_BASE = "73d4765322efd8c7b87ed8c94bdca8bb81098d7a"
PINNED_STATE = "39b5643d66954d415ea8f1f88b0252df51ab6f04"
CHECKPOINT = 600
ACTION_BUDGET = 8


def _agenda_identity(state):
    active = {
        str(row.get("id"))
        for row in state.get("agenda", {}).get("threads", [])
        if isinstance(row, dict) and row.get("id")
    }
    archived = {
        str(row.get("id"))
        for row in state.get("agenda", {}).get("archived_threads", [])
        if isinstance(row, dict) and row.get("id")
    }
    return active | archived


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
    return world, attempts


def _expect_replay_rejection(executor_path: Path, token: dict, ora_store, recorder):
    before = executor_path.read_bytes()
    try:
        ChallengeActionExecutor(executor_path).execute(
            token, ora_store=ora_store, recorder=recorder,
        )
    except RuntimeError as exc:
        if "already consumed" not in str(exc):
            raise AssertionError(f"unexpected replay rejection: {exc}") from exc
        if executor_path.read_bytes() != before:
            raise AssertionError("replay rejection mutated executor")
        return str(exc)
    raise AssertionError("consumed capability replay unexpectedly succeeded")


def _assert_phase42_clean(
    state,
    baseline_diag,
    *,
    label: str,
):
    diag = evaluate_resumption_opportunities(state)
    if diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError(f"{label}: Phase42 mismatch introduced")
    if (
        baseline_diag["resumed_opportunity_count"] == 0
        and diag["resumed_opportunity_count"] != 0
    ):
        raise AssertionError(f"{label}: manufactured Phase42 resumption")
    return diag


def run_one(source_state: Path, seed: int, root: Path):
    layout = root / f"seed-{seed}"
    layout.mkdir(parents=True)
    ora_path = layout / "ora.json"
    recorder_path = layout / "recorder.json"
    executor_path = layout / "executor.json"
    shutil.copy2(source_state, ora_path)

    recorder_store = StateStore(recorder_path)
    recorder_store.save(initial_state())
    world, attempts = _stream_prefix(recorder_store, seed)

    ora_store = StateStore(ora_path)
    baseline = ora_store.load()
    baseline_cycle = int(baseline["cycles"])
    baseline_identity = _agenda_identity(baseline)
    baseline_diag = evaluate_resumption_opportunities(baseline)
    if baseline_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("baseline Phase42 mismatch")
    stable_repo_observation = deepcopy(baseline["environment_snapshots"][-1])

    ChallengeActionExecutor.create(
        executor_path,
        world=world,
        max_actions=ACTION_BUDGET,
    )

    rows = []
    experiment_ids = set()
    evidence_refs = set()
    recorder_chain_hashes = set()
    capability_ids = []
    selector_modes = []
    supported = 0
    falsified = 0

    for step in range(1, ACTION_BUDGET + 1):
        recorder = ChallengeShadowRecorder(
            StateStore(recorder_path),
            enabled=True,
        )
        before_observation = ChallengeActionExecutor(executor_path).observation()
        if recorder.latest_observation() != before_observation:
            raise AssertionError(f"step {step}: recorder/executor drift before staging")

        publication = recorder.publication()
        candidate = publication["selected_temporal_candidate"]
        staged = stage_publication_inquiry(
            AgentCore(StateStore(ora_path)),
            policy=observe_and_inquire_policy(),
            source_manifest=source_manifest(),
            publication=publication,
        )
        experiment_id = staged["inquiry_result"]["experiment"]["id"]
        question_id = staged["inquiry_result"]["question"]["id"]
        if experiment_id in experiment_ids:
            raise AssertionError("multi-action loop reused native experiment identity")
        experiment_ids.add(experiment_id)

        minute = seed * 10 + step
        cycle_result = AgentCore(StateStore(ora_path)).cycle(
            stimulus="continue ordinary operation",
            observation=deepcopy(stable_repo_observation),
            _now_override=f"2026-10-05T21:{minute:02d}:00+00:00",
        )
        current_ora = StateStore(ora_path).load()
        expected_cycle = baseline_cycle + step
        if int(current_ora["cycles"]) != expected_cycle:
            raise AssertionError(
                f"step {step}: ordinary cycle expected {expected_cycle}, "
                f"got {current_ora['cycles']}"
            )
        if cycle_result["action_lab_result"] is not None:
            raise AssertionError(f"step {step}: Action Lab authority appeared")
        if cycle_result["planning_lab_result"] is not None:
            raise AssertionError(f"step {step}: Planning Lab authority appeared")
        if not baseline_identity <= _agenda_identity(current_ora):
            raise AssertionError(f"step {step}: preexisting agenda identity was lost")

        experiment = next(
            row for row in current_ora["experiments"]
            if row["id"] == experiment_id
        )
        if experiment.get("readiness") != "awaiting_native_evidence":
            raise AssertionError(f"step {step}: native readiness was not preserved")

        native_summary = next(
            (
                row
                for row in cycle_result["agenda_decision"].get(
                    "candidate_summaries", []
                )
                if row.get("question_id") == question_id
            ),
            None,
        )
        if not native_summary or native_summary.get("active_experiment_path") is not True:
            raise AssertionError(f"step {step}: native inquiry missing from ordinary agenda")

        phase_before_action = _assert_phase42_clean(
            current_ora,
            baseline_diag,
            label=f"step {step} pre-action",
        )

        # Restart before issuance.
        executor = ChallengeActionExecutor(executor_path)
        issued = executor.issue(
            ora_store=StateStore(ora_path),
            recorder=ChallengeShadowRecorder(
                StateStore(recorder_path),
                enabled=True,
            ),
            experiment_id=experiment_id,
        )
        token = issued["token"]
        selection = issued["selection"]
        expected_capability = f"CAC{step:06d}"
        if token["id"] != expected_capability:
            raise AssertionError(
                f"step {step}: expected {expected_capability}, got {token['id']}"
            )
        if int(token["budget_ordinal"]) != step:
            raise AssertionError(f"step {step}: wrong budget ordinal")
        if token["recorder_chain_hash"] in recorder_chain_hashes:
            raise AssertionError(f"step {step}: recorder chain did not advance")
        recorder_chain_hashes.add(token["recorder_chain_hash"])
        capability_ids.append(token["id"])
        selector_modes.append(selection["mode"])

        unguided = choose_command(before_observation, attempts)

        # Restart again before execution.
        executed = ChallengeActionExecutor(executor_path).execute(
            token, ora_store=StateStore(ora_path), recorder=recorder,
        )
        if int(executed["actions_consumed"]) != step:
            raise AssertionError(f"step {step}: executor consumption count mismatch")
        if int(executed["remaining_budget"]) != ACTION_BUDGET - step:
            raise AssertionError(f"step {step}: remaining budget mismatch")

        replay_error = _expect_replay_rejection(
            executor_path, token, StateStore(ora_path), recorder,
        )

        # Actual selected action becomes part of the observable action history.
        attempts[
            (
                observation_signature(before_observation),
                command_key(token["command"]),
            )
        ] += 1

        recorder = ChallengeShadowRecorder(
            StateStore(recorder_path),
            enabled=True,
        )
        recorder.ingest(executed["observation"], executed["receipt"])
        recorder_cursor = recorder.store.load()[RECORDER_STATE_KEY]
        if recorder_cursor["chain"] == token["recorder_chain_hash"]:
            raise AssertionError(f"step {step}: new public evidence did not advance chain")

        outcome_payload = single_transition_outcome(
            before=before_observation,
            after=executed["observation"],
            candidate=candidate,
        )
        if outcome_payload is None:
            raise AssertionError(
                f"step {step}: selected feature not evaluable after authorized action"
            )
        evidence = AgentCore(StateStore(ora_path)).record_native_evidence(
            outcome_payload,
            enabled=True,
            persist=True,
        )
        if evidence["evidence_ref"] in evidence_refs:
            raise AssertionError(f"step {step}: native outcome evidence ref reused")
        evidence_refs.add(evidence["evidence_ref"])

        resolved = AgentCore(StateStore(ora_path)).resolve_native_inquiry(
            experiment_id,
            evidence["evidence_ref"],
            enabled=True,
            persist=True,
            _now_override=f"2026-10-05T22:{minute:02d}:00+00:00",
        )
        outcome = resolved["experiment"]["outcome"]
        if outcome == "supported":
            supported += 1
        elif outcome == "falsified":
            falsified += 1
        else:
            raise AssertionError(f"step {step}: unexpected native outcome {outcome}")

        after_resolution = StateStore(ora_path).load()
        resolved_experiment = next(
            row for row in after_resolution["experiments"]
            if row["id"] == experiment_id
        )
        if resolved_experiment.get("status") != "completed":
            raise AssertionError(f"step {step}: native experiment did not complete")
        if resolved_experiment.get("readiness") != "resolved":
            raise AssertionError(f"step {step}: native experiment readiness not resolved")

        rows.append(
            {
                "step": step,
                "ora_cycle": int(current_ora["cycles"]),
                "question_id": question_id,
                "experiment_id": experiment_id,
                "candidate": candidate,
                "capability_id": token["id"],
                "budget_ordinal": token["budget_ordinal"],
                "observation_id": token["observation_id"],
                "recorder_chain_hash": token["recorder_chain_hash"],
                "selection": selection,
                "unguided_command": unguided,
                "differs_from_unguided": token["command"] != unguided,
                "receipt": executed["receipt"],
                "result_observation_id": executed["observation"]["observation_id"],
                "replay_error": replay_error,
                "outcome": outcome,
                "outcome_evidence_ref": evidence["evidence_ref"],
                "phase42": {
                    "opportunities": phase_before_action["opportunity_count"],
                    "mismatch": phase_before_action[
                        "handoff_or_selection_mismatch_count"
                    ],
                    "resumed": phase_before_action["resumed_opportunity_count"],
                },
            }
        )

    # Budget must reject a ninth issuance before any extra action can occur.
    last_experiment = rows[-1]["experiment_id"]
    budget_error = None
    try:
        ChallengeActionExecutor(executor_path).issue(
            ora_store=StateStore(ora_path),
            recorder=ChallengeShadowRecorder(
                StateStore(recorder_path),
                enabled=True,
            ),
            experiment_id=last_experiment,
        )
    except RuntimeError as exc:
        if "budget is exhausted" not in str(exc):
            raise
        budget_error = str(exc)
    if budget_error is None:
        raise AssertionError("ninth challenge action issuance unexpectedly succeeded")

    # Final ordinary cycle verifies continuity after the eighth resolved inquiry.
    final_minute = seed * 10 + ACTION_BUDGET + 1
    final_result = AgentCore(StateStore(ora_path)).cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_repo_observation),
        _now_override=f"2026-10-05T23:{final_minute:02d}:00+00:00",
    )
    final = StateStore(ora_path).load()
    if int(final["cycles"]) != baseline_cycle + ACTION_BUDGET + 1:
        raise AssertionError("final ordinary cycle count mismatch")
    if final_result["action_lab_result"] is not None:
        raise AssertionError("final cycle gained Action Lab authority")
    if final_result["planning_lab_result"] is not None:
        raise AssertionError("final cycle gained Planning Lab authority")
    final_diag = _assert_phase42_clean(
        final,
        baseline_diag,
        label="final post-loop cycle",
    )
    if not baseline_identity <= _agenda_identity(final):
        raise AssertionError("final loop lost preexisting agenda identity")

    executor_state = ChallengeActionExecutor(executor_path).load()
    if executor_state["actions_consumed"] != ACTION_BUDGET:
        raise AssertionError("executor did not consume exact action budget")
    if len(executor_state["capabilities"]) != ACTION_BUDGET:
        raise AssertionError("executor capability ledger length mismatch")
    if len(experiment_ids) != ACTION_BUDGET:
        raise AssertionError("loop did not use a fresh experiment per action")
    if len(evidence_refs) != ACTION_BUDGET:
        raise AssertionError("loop did not record fresh native outcome per action")
    if len(recorder_chain_hashes) != ACTION_BUDGET:
        raise AssertionError("loop did not ingest fresh public evidence per action")

    return {
        "seed": seed,
        "baseline_cycle": baseline_cycle,
        "final_cycle": int(final["cycles"]),
        "actions": ACTION_BUDGET,
        "fresh_experiment_count": len(experiment_ids),
        "fresh_outcome_evidence_count": len(evidence_refs),
        "unique_pre_action_recorder_chains": len(recorder_chain_hashes),
        "capability_ids": capability_ids,
        "selector_modes": selector_modes,
        "distinct_selector_modes": sorted(set(selector_modes)),
        "supported_count": supported,
        "falsified_count": falsified,
        "differs_from_unguided_count": sum(
            row["differs_from_unguided"] for row in rows
        ),
        "budget_error": budget_error,
        "final_observation": ChallengeActionExecutor(executor_path).observation(),
        "phase42_final": {
            "opportunities": final_diag["opportunity_count"],
            "mismatch": final_diag["handoff_or_selection_mismatch_count"],
            "resumed": final_diag["resumed_opportunity_count"],
        },
        "rows": rows,
        "authority": {
            "copied_state_only": True,
            "fresh_capability_per_action": True,
            "fresh_native_experiment_per_action": True,
            "restart_before_each_execution": True,
            "replay_rejected_every_action": True,
            "exact_action_budget": ACTION_BUDGET,
            "live_challenge_authority": False,
            "phase42_credit": False,
            "action_lab": False,
            "planning_lab": False,
            "external_model_api": False,
        },
    }


def run(source_state: Path):
    source_bytes = source_state.read_bytes()
    with tempfile.TemporaryDirectory() as temp:
        rows = [
            run_one(source_state, seed, Path(temp))
            for seed in range(1, 5)
        ]
    if source_state.read_bytes() != source_bytes:
        raise AssertionError("pinned source state changed")

    passed = (
        len(rows) == 4
        and all(row["actions"] == ACTION_BUDGET for row in rows)
        and all(
            row["fresh_experiment_count"] == ACTION_BUDGET
            and row["fresh_outcome_evidence_count"] == ACTION_BUDGET
            and row["unique_pre_action_recorder_chains"] == ACTION_BUDGET
            for row in rows
        )
        and all(
            row["phase42_final"]["mismatch"] == 0
            and row["phase42_final"]["resumed"] == 0
            for row in rows
        )
    )
    return {
        "study": "challenge-eight-action-closed-loop-v1",
        "passed": passed,
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "layout_count": 4,
        "action_budget_per_layout": ACTION_BUDGET,
        "total_authorized_actions": sum(row["actions"] for row in rows),
        "total_fresh_experiments": sum(
            row["fresh_experiment_count"] for row in rows
        ),
        "total_fresh_outcome_evidence": sum(
            row["fresh_outcome_evidence_count"] for row in rows
        ),
        "supported_count": sum(row["supported_count"] for row in rows),
        "falsified_count": sum(row["falsified_count"] for row in rows),
        "differs_from_unguided_count": sum(
            row["differs_from_unguided_count"] for row in rows
        ),
        "phase42_clean_layouts": sum(
            row["phase42_final"]["mismatch"] == 0
            and row["phase42_final"]["resumed"] == 0
            for row in rows
        ),
        "rows": rows,
        "source_unchanged": True,
        "limitations": [
            "The eight-action loop runs only on copied Ora state and a shadow executor; live Ora still has no challenge-world authority.",
            "Each action gets a fresh native inquiry, but the selected temporal feature may repeat because 600 prefix observations dominate the bounded evidence totals.",
            "The executor is a local integrity/correctness capability mechanism, not a distributed-system authorization service.",
            "Four mirrored layouts and eight actions are a bounded continuity test, not a general intelligence benchmark.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run(Path(args.state))
    print(json.dumps({
        "passed": report["passed"],
        "layout_count": report["layout_count"],
        "total_authorized_actions": report["total_authorized_actions"],
        "total_fresh_experiments": report["total_fresh_experiments"],
        "total_fresh_outcome_evidence": report["total_fresh_outcome_evidence"],
        "supported_count": report["supported_count"],
        "falsified_count": report["falsified_count"],
        "differs_from_unguided_count": report["differs_from_unguided_count"],
        "phase42_clean_layouts": report["phase42_clean_layouts"],
    }, sort_keys=True))
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
