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
from challenge_action_authority import (
    ChallengeActionExecutor,
    _unsafe_replace_world_for_adversarial_test,
)
from challenge_shadow_epistemic_selector import select_epistemic_command
from challenge_shadow_recorder import (
    ChallengeShadowRecorder,
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


def _threads(state):
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
    return active, archived


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


def _expect_rejection(fn, expected: str):
    try:
        fn()
    except (ValueError, RuntimeError) as exc:
        if expected not in str(exc):
            raise AssertionError(
                f"expected rejection containing {expected!r}, got {exc!r}"
            ) from exc
        return str(exc)
    raise AssertionError(f"expected rejection containing {expected!r}")


def _adversarial_checks(
    *,
    root: Path,
    executor_path: Path,
    token: dict,
    world: dict,
    attempts: Counter,
):
    checks = {}

    # Mutated command.
    mutation_path = root / "mutation.json"
    shutil.copy2(executor_path, mutation_path)
    mutated = deepcopy(token)
    mutated["command"] = {"action": "south"}
    before = mutation_path.read_bytes()
    checks["command_mutation"] = _expect_rejection(
        lambda: ChallengeActionExecutor(mutation_path).execute(mutated),
        "modified",
    )
    if mutation_path.read_bytes() != before:
        raise AssertionError("command mutation changed executor state")

    # Wrong source.
    source_path = root / "source-mismatch.json"
    shutil.copy2(executor_path, source_path)
    wrong_source = deepcopy(token)
    wrong_source["source_id"] = "research.challenge-other"
    before = source_path.read_bytes()
    checks["source_mismatch"] = _expect_rejection(
        lambda: ChallengeActionExecutor(source_path).execute(wrong_source),
        "source mismatch",
    )
    if source_path.read_bytes() != before:
        raise AssertionError("source mismatch changed executor state")

    # Stale world observation.
    stale_path = root / "stale.json"
    shutil.copy2(executor_path, stale_path)
    observation = observe_world(world)
    alternate = choose_command(observation, attempts)
    advanced, _ = transition(
        world,
        alternate,
        cycle=int(observation["cycle"]) + 1,
    )
    _unsafe_replace_world_for_adversarial_test(stale_path, advanced)
    before = stale_path.read_bytes()
    checks["stale_observation"] = _expect_rejection(
        lambda: ChallengeActionExecutor(stale_path).execute(token),
        "stale",
    )
    if stale_path.read_bytes() != before:
        raise AssertionError("stale capability attempt changed executor state")

    # Restart-safe execution then replay rejection.
    replay_path = root / "replay.json"
    shutil.copy2(executor_path, replay_path)
    first = ChallengeActionExecutor(replay_path).execute(token)
    consumed = replay_path.read_bytes()
    checks["restart_first_execution"] = {
        "capability_id": first["capability_id"],
        "actions_consumed": first["actions_consumed"],
        "remaining_budget": first["remaining_budget"],
    }
    checks["restart_replay"] = _expect_rejection(
        lambda: ChallengeActionExecutor(replay_path).execute(token),
        "already consumed",
    )
    if replay_path.read_bytes() != consumed:
        raise AssertionError("replay rejection changed consumed executor state")

    return checks


def run_one(source_state: Path, seed: int, root: Path):
    layout_root = root / f"seed-{seed}"
    layout_root.mkdir(parents=True)
    ora_path = layout_root / "ora.json"
    recorder_path = layout_root / "recorder.json"
    executor_path = layout_root / "executor.json"
    shutil.copy2(source_state, ora_path)

    recorder_store = StateStore(recorder_path)
    recorder_store.save(initial_state())
    recorder, world, attempts, observation = _stream_prefix(
        recorder_store,
        seed,
    )

    ora_store = StateStore(ora_path)
    baseline = ora_store.load()
    baseline_diag = evaluate_resumption_opportunities(baseline)
    baseline_cycle = int(baseline["cycles"])
    active_before, archived_before = _threads(baseline)
    baseline_identity = active_before | archived_before
    stable_repo_observation = deepcopy(baseline["environment_snapshots"][-1])

    publication = recorder.publication()
    candidate = publication["selected_temporal_candidate"]
    staged = stage_publication_inquiry(
        AgentCore(ora_store),
        policy=observe_and_inquire_policy(),
        source_manifest=source_manifest(),
        publication=publication,
    )
    experiment_id = staged["inquiry_result"]["experiment"]["id"]
    question_id = staged["inquiry_result"]["question"]["id"]

    first = AgentCore(StateStore(ora_path)).cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_repo_observation),
        _now_override=f"2026-10-05T20:0{seed}:00+00:00",
    )
    after_first = StateStore(ora_path).load()
    experiment = next(
        row for row in after_first["experiments"]
        if row["id"] == experiment_id
    )
    if experiment.get("readiness") != "awaiting_native_evidence":
        raise AssertionError("native readiness was not preserved")
    active_after, archived_after = _threads(after_first)
    if not baseline_identity <= (active_after | archived_after):
        raise AssertionError("preexisting agenda identity was lost")

    first_diag = evaluate_resumption_opportunities(after_first)
    if first_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("authority prelude introduced Phase42 mismatch")
    if baseline_diag["resumed_opportunity_count"] == 0 and first_diag["resumed_opportunity_count"] != 0:
        raise AssertionError("authority prelude manufactured Phase42 resumption")
    if first["action_lab_result"] is not None or first["planning_lab_result"] is not None:
        raise AssertionError("ordinary cycle granted lab action authority")

    executor = ChallengeActionExecutor.create(
        executor_path,
        world=world,
        max_actions=1,
    )
    issued = executor.issue(
        ora_store=StateStore(ora_path),
        recorder=recorder,
        experiment_id=experiment_id,
    )
    token = issued["token"]
    selection = issued["selection"]

    direct_selection = select_epistemic_command(
        observation,
        feature=candidate["feature"],
        relation=candidate["relation"],
        associations=recorder.action_associations(),
    )
    if selection != direct_selection:
        raise AssertionError("authority did not reproduce verified selector result")
    unguided = choose_command(observation, attempts)

    checks = _adversarial_checks(
        root=layout_root,
        executor_path=executor_path,
        token=token,
        world=world,
        attempts=attempts,
    )

    # Restart before the real execution.
    executed = ChallengeActionExecutor(executor_path).execute(token)
    if executed["actions_consumed"] != 1 or executed["remaining_budget"] != 0:
        raise AssertionError("single-action capability budget was not consumed")

    consumed_bytes = executor_path.read_bytes()
    replay_error = _expect_rejection(
        lambda: ChallengeActionExecutor(executor_path).execute(token),
        "already consumed",
    )
    if executor_path.read_bytes() != consumed_bytes:
        raise AssertionError("real replay rejection changed executor state")

    budget_error = _expect_rejection(
        lambda: ChallengeActionExecutor(executor_path).issue(
            ora_store=StateStore(ora_path),
            recorder=recorder,
            experiment_id=experiment_id,
        ),
        "budget is exhausted",
    )

    recorder.ingest(executed["observation"], executed["receipt"])
    outcome_payload = single_transition_outcome(
        before=observation,
        after=executed["observation"],
        candidate=candidate,
    )
    if outcome_payload is None:
        raise AssertionError("authorized action did not yield evaluable native outcome")

    evidence = AgentCore(StateStore(ora_path)).record_native_evidence(
        outcome_payload,
        enabled=True,
        persist=True,
    )
    resolved = AgentCore(StateStore(ora_path)).resolve_native_inquiry(
        experiment_id,
        evidence["evidence_ref"],
        enabled=True,
        persist=True,
        _now_override=f"2026-10-05T20:1{seed}:00+00:00",
    )
    if resolved["experiment"]["status"] != "completed":
        raise AssertionError("authorized action outcome did not resolve inquiry")

    final_result = AgentCore(StateStore(ora_path)).cycle(
        stimulus="continue ordinary operation",
        observation=deepcopy(stable_repo_observation),
        _now_override=f"2026-10-05T20:2{seed}:00+00:00",
    )
    final = StateStore(ora_path).load()
    final_diag = evaluate_resumption_opportunities(final)
    if final_diag["handoff_or_selection_mismatch_count"] != 0:
        raise AssertionError("authorized post-cycle introduced Phase42 mismatch")
    if baseline_diag["resumed_opportunity_count"] == 0 and final_diag["resumed_opportunity_count"] != 0:
        raise AssertionError("authorized action manufactured Phase42 resumption")
    if final_result["action_lab_result"] is not None or final_result["planning_lab_result"] is not None:
        raise AssertionError("authorized loop granted lab authority")

    return {
        "seed": seed,
        "baseline_cycle": baseline_cycle,
        "final_cycle": int(final["cycles"]),
        "question_id": question_id,
        "experiment_id": experiment_id,
        "candidate": candidate,
        "selection": selection,
        "unguided_command": unguided,
        "differs_from_unguided": selection["command"] != unguided,
        "capability_id": token["id"],
        "capability_observation_id": token["observation_id"],
        "capability_command": token["command"],
        "adversarial_checks": checks,
        "real_replay_error": replay_error,
        "budget_error": budget_error,
        "receipt": executed["receipt"],
        "outcome": resolved["experiment"]["outcome"],
        "outcome_evidence_ref": evidence["evidence_ref"],
        "phase42_final": {
            "opportunities": final_diag["opportunity_count"],
            "mismatch": final_diag["handoff_or_selection_mismatch_count"],
            "resumed": final_diag["resumed_opportunity_count"],
        },
        "authority": {
            "single_action_budget": True,
            "atomic_world_and_consumption": True,
            "restart_replay_rejected": True,
            "live_production_state_modified": False,
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
        and all(row["outcome"] in {"supported", "falsified"} for row in rows)
        and all(
            row["phase42_final"]["mismatch"] == 0
            and row["phase42_final"]["resumed"] == 0
            for row in rows
        )
        and all(row["authority"]["restart_replay_rejected"] for row in rows)
    )
    return {
        "study": "challenge-bounded-action-authority-v1",
        "passed": passed,
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "layout_count": 4,
        "authorized_layouts": len(rows),
        "resolved_layouts": sum(
            row["outcome"] in {"supported", "falsified"} for row in rows
        ),
        "supported_count": sum(row["outcome"] == "supported" for row in rows),
        "falsified_count": sum(row["outcome"] == "falsified" for row in rows),
        "differs_from_unguided_layouts": sum(
            row["differs_from_unguided"] for row in rows
        ),
        "phase42_clean_layouts": sum(
            row["phase42_final"]["mismatch"] == 0
            and row["phase42_final"]["resumed"] == 0
            for row in rows
        ),
        "restart_replay_rejected_layouts": sum(
            row["authority"]["restart_replay_rejected"] for row in rows
        ),
        "rows": rows,
        "source_unchanged": True,
        "limitations": [
            "Authority is confined to copied Ora plus a separate research executor; live Ora still cannot act in the challenge world.",
            "Atomicity covers capability consumption and shadow-world persistence in one executor file, not distributed external systems.",
            "The executor is an integrity/correctness capability gate, not a cryptographic adversarial-security boundary.",
            "Each layout authorizes exactly one action; multi-action continuity is a separate next experiment.",
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
        "authorized_layouts": report["authorized_layouts"],
        "resolved_layouts": report["resolved_layouts"],
        "supported_count": report["supported_count"],
        "falsified_count": report["falsified_count"],
        "differs_from_unguided_layouts": report["differs_from_unguided_layouts"],
        "phase42_clean_layouts": report["phase42_clean_layouts"],
        "restart_replay_rejected_layouts": report["restart_replay_rejected_layouts"],
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
