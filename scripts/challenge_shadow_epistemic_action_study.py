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
from challenge_shadow_epistemic_selector import select_epistemic_command
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

PRODUCTION_BASE = "73d4765322efd8c7b87ed8c94bdca8bb81098d7a"
PINNED_STATE = "825d2c86759f5f4065807508ab7fbfe3462feb8a"
CHECKPOINT = 600


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


def run_one(source_state: Path, seed: int, root: Path):
    state_path = root / f"seed-{seed}" / "organism.json"
    recorder_path = root / f"seed-{seed}" / "recorder.json"
    state_path.parent.mkdir(parents=True)
    shutil.copy2(source_state, state_path)
    recorder_store = StateStore(recorder_path)
    recorder_store.save(initial_state())

    store = StateStore(state_path)
    baseline = store.load()
    baseline_diag = evaluate_resumption_opportunities(baseline)
    if baseline_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("pinned baseline begins with Phase42 mismatch")
    if not baseline.get("environment_snapshots"):
        raise AssertionError("pinned baseline lacks repository observation")

    baseline_cycle = int(baseline["cycles"])
    baseline_threads = _thread_ids(baseline)
    baseline_action = deepcopy(baseline.get("action_lab"))
    baseline_planning = deepcopy(baseline.get("planning_lab"))
    stable_repo_observation = deepcopy(baseline["environment_snapshots"][-1])

    recorder, world, attempts, observation = _stream_prefix(recorder_store, seed)
    publication = recorder.publication()
    candidate = publication["selected_temporal_candidate"]

    staged = stage_publication_inquiry(
        AgentCore(store),
        policy=observe_and_inquire_policy(),
        source_manifest=source_manifest(),
        publication=publication,
    )
    experiment_id = staged["inquiry_result"]["experiment"]["id"]
    question_id = staged["inquiry_result"]["question"]["id"]

    first_core = AgentCore(StateStore(state_path))
    first_cycle = first_core.cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_repo_observation),
        _now_override=f"2026-10-05T19:0{seed}:00+00:00",
    )
    after_first = first_core.store.load()
    if after_first["cycles"] != baseline_cycle + 1:
        raise AssertionError("ordinary handoff did not advance exactly one cycle")
    if first_cycle["action_lab_result"] is not None:
        raise AssertionError("shadow inquiry granted Action Lab authority")
    if first_cycle["planning_lab_result"] is not None:
        raise AssertionError("shadow inquiry granted Planning Lab authority")

    experiment = next(
        row for row in after_first["experiments"]
        if row["id"] == experiment_id
    )
    if experiment.get("readiness") != "awaiting_native_evidence":
        raise AssertionError("native readiness did not survive ordinary cycle")

    native_summary = next(
        (
            row
            for row in first_cycle["agenda_decision"].get("candidate_summaries", [])
            if row.get("question_id") == question_id
        ),
        None,
    )
    if not native_summary or native_summary.get("active_experiment_path") is not True:
        raise AssertionError("native challenge inquiry did not enter ordinary agenda")

    if not baseline_threads <= (_thread_ids(after_first) | _archived_ids(after_first)):
        raise AssertionError("preexisting agenda thread identity was lost")
    first_diag = evaluate_resumption_opportunities(after_first)
    if first_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("challenge inquiry introduced Phase42 mismatch")
    if baseline_diag["resumed_opportunity_count"] == 0 and first_diag["resumed_opportunity_count"] != 0:
        raise AssertionError("challenge inquiry manufactured Phase42 resumption")

    associations_before = recorder.action_associations()
    selection_before = select_epistemic_command(
        observation,
        feature=candidate["feature"],
        relation=candidate["relation"],
        associations=associations_before,
    )

    reloaded = ChallengeShadowRecorder(
        StateStore(recorder_path),
        enabled=True,
    )
    associations_after = reloaded.action_associations()
    selection_after = select_epistemic_command(
        reloaded.latest_observation(),
        feature=candidate["feature"],
        relation=candidate["relation"],
        associations=associations_after,
    )
    if associations_before != associations_after:
        raise AssertionError("persisted challenge associations changed after reload")
    if selection_before != selection_after:
        raise AssertionError("epistemic selection changed after recorder reload")

    empty_control = select_epistemic_command(
        observation,
        feature=candidate["feature"],
        relation=candidate["relation"],
        associations=[],
    )
    unguided = choose_command(observation, attempts)

    selected_command = selection_after["command"]
    next_world, receipt = transition(
        world,
        selected_command,
        cycle=CHECKPOINT + 1,
    )
    next_observation = observe_world(next_world)
    reloaded.ingest(next_observation, receipt)

    outcome_payload = single_transition_outcome(
        before=observation,
        after=next_observation,
        candidate=candidate,
    )
    if outcome_payload is None:
        raise AssertionError("epistemic action did not yield an evaluable selected feature")

    evidence = AgentCore(store).record_native_evidence(
        outcome_payload,
        enabled=True,
        persist=True,
    )
    resolved = AgentCore(store).resolve_native_inquiry(
        experiment_id,
        evidence["evidence_ref"],
        enabled=True,
        persist=True,
        _now_override=f"2026-10-05T19:1{seed}:00+00:00",
    )
    if resolved["experiment"]["status"] != "completed":
        raise AssertionError("epistemic challenge outcome did not resolve inquiry")

    final_core = AgentCore(StateStore(state_path))
    final_cycle = final_core.cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_repo_observation),
        _now_override=f"2026-10-05T19:2{seed}:00+00:00",
    )
    final = final_core.store.load()
    final_diag = evaluate_resumption_opportunities(final)
    if final_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("post-resolution cycle introduced Phase42 mismatch")
    if baseline_diag["resumed_opportunity_count"] == 0 and final_diag["resumed_opportunity_count"] != 0:
        raise AssertionError("post-resolution cycle manufactured Phase42 resumption")
    if final_cycle["action_lab_result"] is not None or final_cycle["planning_lab_result"] is not None:
        raise AssertionError("shadow epistemic loop granted lab authority")

    return {
        "seed": seed,
        "baseline_cycle": baseline_cycle,
        "final_cycle": int(final["cycles"]),
        "candidate": candidate,
        "association_count": len(associations_after),
        "selection": selection_after,
        "reload_selection_exact": selection_before == selection_after,
        "empty_control_command": empty_control["command"],
        "unguided_command": unguided,
        "differs_from_empty_control": selection_after["command"] != empty_control["command"],
        "differs_from_unguided": selection_after["command"] != unguided,
        "receipt": receipt,
        "outcome": resolved["experiment"]["outcome"],
        "outcome_evidence_ref": evidence["evidence_ref"],
        "phase42_before": {
            "opportunities": baseline_diag["opportunity_count"],
            "resumed": baseline_diag["resumed_opportunity_count"],
            "mismatch": baseline_diag["handoff_or_selection_mismatch_count"],
        },
        "phase42_final": {
            "opportunities": final_diag["opportunity_count"],
            "resumed": final_diag["resumed_opportunity_count"],
            "mismatch": final_diag["handoff_or_selection_mismatch_count"],
        },
        "authority": {
            "challenge_action_selected_by_epistemic_shadow_policy": True,
            "challenge_action_selected_by_live_ora": False,
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

    evidence_sensitive = sum(row["differs_from_empty_control"] for row in rows)
    differs_unguided = sum(row["differs_from_unguided"] for row in rows)
    seek_mode = sum(row["selection"]["mode"] == "seek_disconfirming_observation" for row in rows)
    uncertainty_mode = sum(row["selection"]["mode"] == "reduce_action_uncertainty" for row in rows)
    supported = sum(row["outcome"] == "supported" for row in rows)
    falsified = sum(row["outcome"] == "falsified" for row in rows)

    passed = (
        len(rows) == 4
        and all(row["reload_selection_exact"] for row in rows)
        and all(row["association_count"] > 0 for row in rows)
        and all(row["outcome"] in {"supported","falsified"} for row in rows)
        and all(
            row["phase42_final"]["mismatch"] == 0
            and row["phase42_final"]["resumed"] == 0
            for row in rows
        )
        and evidence_sensitive >= 1
    )

    return {
        "study": "challenge-shadow-epistemic-action-v1",
        "passed": passed,
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "reviewed_source": reviewed_source_descriptor(),
        "checkpoint": CHECKPOINT,
        "layout_count": 4,
        "reload_exact_layouts": sum(row["reload_selection_exact"] for row in rows),
        "association_present_layouts": sum(row["association_count"] > 0 for row in rows),
        "evidence_sensitive_layouts": evidence_sensitive,
        "differs_from_unguided_layouts": differs_unguided,
        "seek_disconfirming_layouts": seek_mode,
        "reduce_uncertainty_layouts": uncertainty_mode,
        "supported_count": supported,
        "falsified_count": falsified,
        "phase42_clean_layouts": sum(
            row["phase42_final"]["mismatch"] == 0
            and row["phase42_final"]["resumed"] == 0
            for row in rows
        ),
        "rows": rows,
        "source_unchanged": True,
        "authority": {
            "production_modified": False,
            "live_challenge_action_authority": False,
            "phase42_credit": False,
            "external_model_api": False,
        },
        "limitations": [
            "The epistemic selector runs in a research/shadow process, not inside live Ora's action authority.",
            "The current native inquiry is temporal; action associations influence which public command is sampled, not the inquiry scoring itself.",
            "Four mirrored layouts are a bounded world family, not a generalization benchmark.",
            "Evidence sensitivity is tested against an empty-association counterfactual, not a randomized intervention study.",
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
        "reload_exact_layouts": report["reload_exact_layouts"],
        "association_present_layouts": report["association_present_layouts"],
        "evidence_sensitive_layouts": report["evidence_sensitive_layouts"],
        "differs_from_unguided_layouts": report["differs_from_unguided_layouts"],
        "seek_disconfirming_layouts": report["seek_disconfirming_layouts"],
        "reduce_uncertainty_layouts": report["reduce_uncertainty_layouts"],
        "supported_count": report["supported_count"],
        "falsified_count": report["falsified_count"],
        "phase42_clean_layouts": report["phase42_clean_layouts"],
    }, sort_keys=True))
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
