"""Copied-only matched evidence study of the existing PR #213 challenge loop.

No policy tuning, reward target, world replacement, live-state writes, or Phase 42
credit. A changed selector command and a changed ordinary-cycle choice are
separate endpoints. A null scientific endpoint is not a harness failure.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "scripts"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from challenge_action_authority import ChallengeActionExecutor
from challenge_eight_action_closed_loop import _agenda_identity, _stream_prefix
from challenge_shadow_epistemic_selector import select_epistemic_command
from challenge_shadow_recorder import (
    ChallengeShadowRecorder, public_features, single_transition_outcome,
    source_manifest,
)
from native_observe_inquire_integration import (
    observe_and_inquire_policy, stage_publication_inquiry,
)
from open_object_world_challenge_explorer import command_key, observation_signature
from phase42_resumption_opportunity_eval import evaluate_resumption_opportunities

SOURCE_REVISION = "b3da508f6ebadc778cdb3cca5b9903997685d023"
EXPECTED_RUNTIME_HASH = "6315f511737d231f10947c2c53fa752eedcd131ab88ff33dcf884adfe986f3bb"
HISTORICAL_STATE_REVISION = "bc4de8cb09aff13db0e123043bee84b38b511d79"
HISTORICAL_STATE_SHA256 = "276c7e6da74388a330b47390753eb8d9cc18126558712dff149964b85d164471"
SETTINGS = {
    "seeds": [1, 2, 3, 4],
    "prefix_transitions": 600,
    "actions_per_seed": 8,
    "native_probe_steps": [1, 8],
    "native_probe_cycles": 1,
    "selector_ablation": "omit_only_current_feature_action_associations",
    "native_intervention": "withhold_only_current_outcome_and_its_normal_resolution",
    "repeat_context": "same_public_observation_signature_feature_relation_and_command",
    "fixed_start_utc": "2026-10-07T00:00:00+00:00",
    "objective": "information_gain",
    "selection_policy": "public-falsification-oriented-v1",
}


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def runtime_manifest():
    paths = sorted([
        path for directory in (ROOT / "src/agenttest", ROOT / "experiments")
        for path in directory.rglob("*.py")
    ] + [ROOT / "scripts/challenge_eight_action_closed_loop.py",
         ROOT / "scripts/phase42_resumption_opportunity_eval.py"])
    return {str(path.relative_to(ROOT)): file_digest(path) for path in paths}


def fixed_time(seed, step, phase=0):
    start = datetime.fromisoformat(SETTINGS["fixed_start_utc"])
    return (start + timedelta(minutes=seed * 100 + step * 4 + phase)).isoformat()


@contextmanager
def fixed_clock(now):
    """Freeze timestamps only; no selection, evidence, or world policy is patched."""
    with ExitStack() as stack:
        for name, module in list(sys.modules.items()):
            if name.startswith("agenttest.") and hasattr(module, "utc_now"):
                stack.enter_context(patch.object(module, "utc_now", return_value=now))
        yield


def persist_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    loaded = json.loads(path.read_text())
    if loaded != value:
        raise AssertionError("persisted context did not round trip")
    return loaded


def selector_pair(observation, candidate, associations, directory):
    """Intervene on a valid selector input, never on a sealed recorder or ledger."""
    original_hash = digest([observation, candidate, associations])
    intact = {
        "observation": deepcopy(observation),
        "feature": candidate["feature"],
        "relation": candidate["relation"],
        "associations": deepcopy(associations),
    }
    ablated = deepcopy(intact)
    removed = [row for row in ablated["associations"]
               if row["feature"] == candidate["feature"]]
    ablated["associations"] = [row for row in ablated["associations"]
                               if row["feature"] != candidate["feature"]]
    if any(intact[key] != ablated[key]
           for key in ("observation", "feature", "relation")):
        raise AssertionError("ablation changed the matched context")
    intact = persist_json(directory / "retained.json", intact)
    ablated = persist_json(directory / "ablated.json", ablated)
    choices = {name: select_epistemic_command(**context)
               for name, context in (("retained", intact), ("ablated", ablated))}
    if digest([observation, candidate, associations]) != original_hash:
        raise AssertionError("selector study mutated its source inputs")
    return {
        "intervention": SETTINGS["selector_ablation"],
        "retained_context_sha256": digest(intact),
        "ablated_context_sha256": digest(ablated),
        "shared_observation_sha256": digest(observation),
        "removed_association_count": len(removed),
        "removed_associations": removed,
        "unrelated_associations_preserved": True,
        "unrelated_associations_sha256": digest(ablated["associations"]),
        "persisted_and_reloaded": True,
        **choices,
        "command_changed": choices["retained"]["command"] != choices["ablated"]["command"],
    }


def objective_key(candidate):
    return (candidate["feature"], candidate["relation"])


def matched_attempt_key(observation, candidate, command):
    return (observation_signature(observation), objective_key(candidate), command_key(command))


def repeat_measures(history, observation, candidate, selection):
    """A failed counterexample is not proof that an action is universally bad."""
    objective = objective_key(candidate)
    key = matched_attempt_key(observation, candidate, selection["command"])
    previous_refutations = [row for row in history
                            if row["objective_key"] == objective and row["outcome"] == "falsified"]
    failures = [row for row in history
                if row["attempt_key"] == key and row["outcome"] == "supported"]
    # Stronger, limited measure: a prior command was selected in effect-seeking
    # mode with a strictly >1/2 expected counterexample probability, yet its
    # observed transition did not falsify this feature/relation in this context.
    contradicted = [row for row in failures
                    if row["selection"]["mode"] == "seek_disconfirming_observation"
                    and row["selection"]["falsification_probability"] > 0.5]
    return {
        "objective_previously_refuted": bool(previous_refutations),
        "prior_objective_refutation_count": len(previous_refutations),
        "same_context_unsuccessful_counterexample_attempt_repeated": bool(failures),
        "same_context_disconfirmed_expected_effect_repeated": bool(contradicted),
        "prior_matched_failure_steps": [row["step"] for row in failures],
        "prior_matched_disconfirmed_effect_steps": [row["step"] for row in contradicted],
    }


def decision_summary(result, question_id=None):
    agenda = result.get("agenda_decision") or {}
    selected = agenda.get("selected") or {}
    telemetry = agenda.get("candidate_telemetry", [])
    relevant = [row for row in telemetry if row.get("question_id") == question_id]
    opportunities = [row for row in telemetry if row.get("resumption_opportunity")]
    return {
        "question_id": (result.get("question") or {}).get("id"),
        "question_text": (result.get("question") or {}).get("text"),
        "intention_kind": (result.get("intention") or {}).get("kind"),
        "intention_target": (result.get("intention") or {}).get("target"),
        "selected_thread_id": agenda.get("selected_thread_id"),
        "selected_question_id": selected.get("question_id"),
        "resumed_thread_id": agenda.get("resumed_thread_id"),
        "foreground_changed": bool(agenda.get("foreground_changed")),
        "new_evidence_refs": selected.get("new_evidence_refs", []),
        "priority_change_supported_by_new_evidence": bool(agenda.get("priority_change_supported_by_new_evidence")),
        "study_question_telemetry": relevant,
        "resumption_opportunities": opportunities,
        "suspended_thread_ids": agenda.get("suspended_thread_ids", []),
    }


def choice_key(summary):
    # IDs generated by additional episodes are not a change of chosen objective.
    return (summary["question_text"], summary["intention_kind"], summary["intention_target"])


def ordinary_cycle(path, observation, now, baseline_ids, question_id=None):
    before = StateStore(path).load()
    with fixed_clock(now):
        result = AgentCore(StateStore(path)).cycle(
            stimulus="continue ordinary operation", observation=deepcopy(observation),
            _now_override=now,
        )
    after = StateStore(path).load()
    if after["cycles"] != before["cycles"] + 1:
        raise AssertionError("ordinary cycle did not advance exactly once")
    if result["action_lab_result"] is not None or result["planning_lab_result"] is not None:
        raise AssertionError("unexpected laboratory authority")
    if not baseline_ids <= _agenda_identity(after):
        raise AssertionError("unrelated agenda identity was lost")
    diag = evaluate_resumption_opportunities(after)
    if diag["handoff_or_selection_mismatch_count"]:
        raise AssertionError("ordinary cycle introduced a Phase 42 mismatch")
    return decision_summary(result, question_id), {
        "cycle": after["cycles"],
        "genuine_resumption_count": after.get("agenda", {}).get("genuine_resumption_count", 0),
        "phase42_diagnostic": {key: diag[key] for key in (
            "opportunity_count", "resumed_opportunity_count",
            "handoff_or_selection_mismatch_count",
        )},
    }


def apply_outcome(path, experiment_id, payload, now):
    with fixed_clock(now):
        evidence = AgentCore(StateStore(path)).record_native_evidence(
            payload, enabled=True, persist=True, _now_override=now,
        )
        # Fresh objects model restart between persistence and resolution.
        resolved = AgentCore(StateStore(path)).resolve_native_inquiry(
            experiment_id, evidence["evidence_ref"], enabled=True, persist=True,
            _now_override=now,
        )
    return evidence["evidence_ref"], resolved["experiment"]["outcome"]


def assert_outcome_only_delta(before, after, experiment_id, payload):
    allowed = {"episodes", "next_episode_index", "concept_counts", "experiments", "reflections", "updated_at"}
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    if set(changed) - allowed:
        raise AssertionError(f"outcome modified unrelated root fields: {changed}")
    if after["episodes"][:-1] != before["episodes"]:
        raise AssertionError("outcome changed prior evidence")
    if json.loads(after["episodes"][-1]["content"]) != payload:
        raise AssertionError("outcome payload changed")
    if after["reflections"][:-1] != before["reflections"]:
        raise AssertionError("outcome changed prior reflection")
    if len(after["experiments"]) != len(before["experiments"]):
        raise AssertionError("outcome changed experiment count")
    for prior, current in zip(before["experiments"], after["experiments"]):
        if prior["id"] != experiment_id and prior != current:
            raise AssertionError("outcome changed an unrelated experiment")
    return changed


def native_outcome_pair(source_path, experiment_id, question_id, payload,
                        observation, directory, now, baseline_ids):
    """Valid outcome-delivery forks, not destructive historical ledger erasure."""
    directory.mkdir(parents=True)
    paths = {name: directory / name / "ora.json" for name in ("retained", "withheld")}
    source_hash = file_digest(source_path)
    for path in paths.values():
        path.parent.mkdir()
        shutil.copy2(source_path, path)
        if file_digest(path) != source_hash:
            raise AssertionError("pre-intervention fork was not byte-identical")
    before = StateStore(paths["withheld"]).load()
    evidence_ref, outcome = apply_outcome(paths["retained"], experiment_id, payload, now)
    after_delivery = StateStore(paths["retained"]).load()
    changed_fields = assert_outcome_only_delta(before, after_delivery, experiment_id, payload)
    if file_digest(paths["withheld"]) != source_hash:
        raise AssertionError("withheld branch received outcome or another edit")
    pending = next(row for row in before["experiments"] if row["id"] == experiment_id)
    if pending["readiness"] != "awaiting_native_evidence":
        raise AssertionError("withheld branch is not a valid pending native inquiry")
    del before, after_delivery
    outputs = {}
    for name, path in paths.items():
        summary, metadata = ordinary_cycle(path, observation, now, baseline_ids, question_id)
        outputs[name] = {"choice": summary, "metadata": metadata,
                         "final_state_sha256": file_digest(path)}
    if file_digest(source_path) != source_hash:
        raise AssertionError("native probe changed its source state")
    return {
        "intervention": SETTINGS["native_intervention"],
        "pre_intervention_forks_byte_identical": True,
        "pre_intervention_state_sha256": source_hash,
        "shared_observation_sha256": digest(observation),
        "shared_time": now,
        "outcome_payload_sha256": digest(payload),
        "outcome_evidence_ref": evidence_ref,
        "outcome": outcome,
        "normal_api_changed_root_fields": changed_fields,
        "prior_history_preserved": True,
        "withheld_fork_unmodified_before_cycle": True,
        "restart_before_cycle": True,
        **outputs,
        "choice_changed": choice_key(outputs["retained"]["choice"]) != choice_key(outputs["withheld"]["choice"]),
        "qualification": "Short outcome availability plus normal completion consequences; not pure long-term memory erasure.",
    }


def run_layout(source_state, seed, directory):
    directory.mkdir(parents=True)
    ora_path = directory / "ora" / "ora.json"
    ora_path.parent.mkdir()
    shutil.copy2(source_state, ora_path)
    baseline = StateStore(ora_path).load()
    if not baseline["environment_snapshots"]:
        raise ValueError("source state needs an existing repository observation; no observation is invented")
    observation = deepcopy(baseline["environment_snapshots"][-1])
    baseline_ids = _agenda_identity(baseline)
    baseline_cycle = baseline["cycles"]
    prior_genuine = baseline.get("agenda", {}).get("genuine_resumption_count", 0)
    del baseline
    recorder_path = directory / "recorder" / "recorder.json"
    with fixed_clock(fixed_time(seed, 0)):
        StateStore(recorder_path).save(initial_state())
        world, _ = _stream_prefix(StateStore(recorder_path), seed)
    executor_path = directory / "executor.json"
    ChallengeActionExecutor.create(executor_path, world=world, max_actions=SETTINGS["actions_per_seed"])
    del world
    rows, history = [], []
    for step in range(1, SETTINGS["actions_per_seed"] + 1):
        recorder = ChallengeShadowRecorder(StateStore(recorder_path), enabled=True)
        publication = recorder.publication()
        candidate = publication["selected_temporal_candidate"]
        before_observation = recorder.latest_observation()
        recorder_hash = file_digest(recorder_path)
        pair = selector_pair(before_observation, candidate, recorder.action_associations(),
                             directory / f"selector-{step:02d}")
        if file_digest(recorder_path) != recorder_hash:
            raise AssertionError("ablation altered the sealed recorder")
        repeat = {name: repeat_measures(history, before_observation, candidate, pair[name])
                  for name in ("retained", "ablated")}
        with fixed_clock(fixed_time(seed, step)):
            staged = stage_publication_inquiry(
                AgentCore(StateStore(ora_path)), policy=observe_and_inquire_policy(),
                source_manifest=source_manifest(), publication=publication,
            )
        experiment_id = staged["inquiry_result"]["experiment"]["id"]
        question_id = staged["inquiry_result"]["question"]["id"]
        del staged
        native_before, cycle_metadata = ordinary_cycle(
            ora_path, observation, fixed_time(seed, step, 1), baseline_ids, question_id,
        )
        issued = ChallengeActionExecutor(executor_path).issue(
            ora_store=StateStore(ora_path), recorder=recorder, experiment_id=experiment_id,
        )
        if issued["selection"] != pair["retained"]:
            raise AssertionError("actual authority did not select the retained-context command")
        token = issued["token"]
        executed = ChallengeActionExecutor(executor_path).execute(
            token, ora_store=StateStore(ora_path),
            recorder=ChallengeShadowRecorder(StateStore(recorder_path), enabled=True),
        )
        before_replay = file_digest(executor_path)
        try:
            ChallengeActionExecutor(executor_path).execute(token, ora_store=StateStore(ora_path), recorder=recorder)
        except RuntimeError as exc:
            if "already consumed" not in str(exc):
                raise
        else:
            raise AssertionError("capability replay accepted")
        if file_digest(executor_path) != before_replay:
            raise AssertionError("rejected replay changed executor")
        with fixed_clock(fixed_time(seed, step, 2)):
            recorder.ingest(executed["observation"], executed["receipt"])
        payload = single_transition_outcome(before=before_observation, after=executed["observation"], candidate=candidate)
        if payload is None:
            raise AssertionError("authorized action outcome is not evaluable")
        native_pair = None
        if step in SETTINGS["native_probe_steps"]:
            with tempfile.TemporaryDirectory(dir=directory, prefix=f"native-{step}-") as temp:
                native_pair = native_outcome_pair(
                    ora_path, experiment_id, question_id, payload, observation,
                    Path(temp) / "forks", fixed_time(seed, step, 3), baseline_ids,
                )
        evidence_ref, outcome = apply_outcome(ora_path, experiment_id, payload, fixed_time(seed, step, 2))
        history.append({
            "step": step, "objective_key": objective_key(candidate),
            "attempt_key": matched_attempt_key(before_observation, candidate, token["command"]),
            "selection": pair["retained"], "outcome": outcome,
        })
        rows.append({
            "step": step, "experiment_id": experiment_id, "question_id": question_id,
            "candidate": candidate, "selector_pair": pair, "repetitions": repeat,
            "pre_action_native_cycle": native_before, "cycle_metadata": cycle_metadata,
            "native_outcome_pair": native_pair, "capability_id": token["id"],
            "receipt": executed["receipt"], "outcome": outcome,
            "outcome_evidence_ref": evidence_ref, "replay_rejected": True,
            "recorder_pre_action_sha256": recorder_hash,
        })
        print(json.dumps({"progress": "completed_action", "seed": seed, "step": step,
                          "selector_changed": pair["command_changed"],
                          "native_changed": native_pair["choice_changed"] if native_pair else None}), flush=True)
    final_choice, final_metadata = ordinary_cycle(
        ora_path, observation, fixed_time(seed, SETTINGS["actions_per_seed"] + 1), baseline_ids,
        rows[-1]["question_id"],
    )
    if final_metadata["cycle"] != baseline_cycle + SETTINGS["actions_per_seed"] + 1:
        raise AssertionError("unexpected ordinary-cycle horizon")
    if ChallengeActionExecutor(executor_path).load()["actions_consumed"] != SETTINGS["actions_per_seed"]:
        raise AssertionError("incorrect action budget consumption")
    # Do not manufacture Phase 42 success or suppress genuine telemetry.
    return {"seed": seed, "baseline_cycle": baseline_cycle, "prior_genuine_resumption_count": prior_genuine,
            "final_choice": final_choice, "final_metadata": final_metadata, "rows": rows}


def summarize(layouts):
    rows = [row for layout in layouts for row in layout["rows"]]
    pairs = [row["native_outcome_pair"] for row in rows if row["native_outcome_pair"]]
    ordinary = [row["pre_action_native_cycle"] for row in rows] + [row["final_choice"] for row in layouts]
    opportunities = [entry for decision in ordinary for entry in decision["resumption_opportunities"]]
    study_telemetry = [entry for decision in ordinary for entry in decision["study_question_telemetry"]]
    native_probe_telemetry = [entry for pair in pairs for entry in pair["retained"]["choice"]["study_question_telemetry"]]
    return {
        "authorized_actions": len(rows),
        "selector_pairs": len(rows),
        "selector_command_changes": sum(row["selector_pair"]["command_changed"] for row in rows),
        "native_outcome_pairs": len(pairs),
        "native_choice_changes": sum(pair["choice_changed"] for pair in pairs),
        "native_supported": sum(row["outcome"] == "supported" for row in rows),
        "native_falsified": sum(row["outcome"] == "falsified" for row in rows),
        "ordinary_cycles": len(ordinary),
        "ordinary_resumption_opportunities": len(opportunities),
        "ordinary_revisits": sum(bool(row["resumed_thread_id"]) for row in ordinary),
        "study_question_suspended_observations": sum(entry["status"] == "suspended" for entry in study_telemetry),
        "study_question_relevance_opportunities": sum(entry["resumption_opportunity"] for entry in study_telemetry),
        "native_probe_study_question_relevance_opportunities": sum(entry["resumption_opportunity"] for entry in native_probe_telemetry),
        "native_probe_study_question_selected_after_relevance": sum(entry["resumption_opportunity"] and entry["selected"] for entry in native_probe_telemetry),
        "repetition_counts": {
            name: {key: sum(row["repetitions"][name][key] for row in rows) for key in (
                "objective_previously_refuted",
                "same_context_unsuccessful_counterexample_attempt_repeated",
                "same_context_disconfirmed_expected_effect_repeated",
            )} for name in ("retained", "ablated")
        },
    }


def run(source_state):
    source_state = Path(source_state).resolve()
    source_hash = file_digest(source_state)
    manifest = runtime_manifest()
    if digest(manifest) != EXPECTED_RUNTIME_HASH:
        raise ValueError("runtime source is not the frozen PR #213 study baseline")
    settings = deepcopy(SETTINGS)
    layouts = []
    with tempfile.TemporaryDirectory(prefix="ora-retained-evidence-") as temp:
        for seed in settings["seeds"]:
            layouts.append(run_layout(source_state, seed, Path(temp) / f"seed-{seed}"))
    if runtime_manifest() != manifest or file_digest(source_state) != source_hash:
        raise AssertionError("runtime source or source state changed")
    if SETTINGS != settings:
        raise AssertionError("settings changed during experiment")
    summary = summarize(layouts)
    return {
        "study": "challenge-retained-evidence-v1",
        "integrity_passed": True,
        "scientific_endpoints_required_to_pass": False,
        "settings": settings, "settings_sha256": digest(settings),
        "provenance": {"runtime_revision": SOURCE_REVISION, "runtime_manifest": manifest,
                       "runtime_manifest_sha256": digest(manifest),
                       "study_script_sha256": file_digest(Path(__file__)),
                       "source_state_sha256": source_hash,
                       "source_state_revision": HISTORICAL_STATE_REVISION if source_hash == HISTORICAL_STATE_SHA256 else None,
                       "historical_pinned_state_verified": source_hash == HISTORICAL_STATE_SHA256,
                       "source_unchanged": True, "runtime_source_unchanged": True},
        "summary": summary, "layouts": layouts,
        "authority": {"copied_only": True, "live_activation": False, "phase42_credit": False,
                      "action_lab": False, "planning_lab": False, "external_model_api": False,
                      "global_score_override": False, "selector_override": False},
        "interpretation": [
            "Association-input command changes establish dependence of the frozen research selector on retained public evidence in matched contexts only.",
            "Native pairs withhold one outcome and its normal completion consequences from a valid pending inquiry. They test short outcome availability, not pure historical memory erasure or general learning.",
            "Only retained commands execute in the copied world. Ablated choices are counterfactual selector decisions, not alternate world trajectories or measured alternate rewards.",
            "An objective refuted once may merit further sampling; recurrence is not automatically an error. A failed counterexample is not proof the action is universally disproven.",
            "The stronger repeated-effect metric requires identical public context and a previously failed >0.5 expected counterexample in effect-seeking mode; partial observability and probabilistic uncertainty still limit the conclusion.",
            "Relevance and resumption are observed from ordinary decision telemetry without modifying agenda priorities, forcing selection, or granting a live Phase 42 milestone.",
            "Four mirrored layouts with eight actions each and two fixed native probes per layout are a bounded historical-state study, not current live readiness or new-world activation evidence.",
        ],
        "remaining_readiness_gates": [
            "Demonstrate durable retained-evidence benefit on independent held-out contexts, including relevant suspended inquiries and calibrated avoidance of disconfirmed expected effects.",
            "Separate pure historical-memory influence from current outcome delivery and inquiry completion in native full-cycle controls.",
            "Independently review authority, replay, recovery and preservation behavior against the intended deployment state.",
            "Obtain separate explicit approval before any live new-world activation.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # A report must never overwrite source inputs or repository live state.
    output = args.output.resolve()
    if output == args.state.resolve() or output.is_relative_to(ROOT / "state"):
        parser.error("output must not overwrite input or repository live state")
    report = run(args.state)
    persist_json(output, report)
    print(json.dumps({"integrity_passed": report["integrity_passed"], **report["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
