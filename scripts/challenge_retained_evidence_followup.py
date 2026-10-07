"""Qualify a frozen copied study and replay its native probes with strict/planning flags.

This does not execute any challenge-world actions or change the original report.
Exact archived pre-probe bytes and original outcome hashes are required. Native
probes remain copied, one-cycle outcome-availability tests, not live activation.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.state import StateStore
from challenge_eight_action_closed_loop import _agenda_identity
from challenge_retained_evidence_study import (
    EXPECTED_RUNTIME_HASH, apply_outcome, assert_outcome_only_delta,
    choice_key, decision_summary, digest, file_digest, fixed_clock,
    matched_attempt_key, objective_key, persist_json, repeat_measures,
    runtime_manifest,
)
from challenge_shadow_recorder import SOURCE_ID
from phase42_resumption_opportunity_eval import evaluate_resumption_opportunities

DEFAULT_FLAGS = {"cognition": False, "strict_experiment_admission": False,
                 "action_lab": False, "planning_lab": False}
PRODUCTION_FLAGS = {"cognition": False, "strict_experiment_admission": True,
                    "action_lab": False, "planning_lab": True}


def verified_payload(row):
    """Recover an already-measured outcome; verify its original cryptographic hash."""
    pair = row["native_outcome_pair"]
    cycle = row["receipt"]["cycle"]
    outcome = row["outcome"]
    if outcome not in {"supported", "falsified"}:
        raise ValueError("unknown original native outcome")
    candidate = row["candidate"]
    payload = {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {"kind": candidate["relation"], "feature": candidate["feature"],
                     "action": None, "comparison_status": "not_applicable"},
        "observation_refs": [f"{SOURCE_ID}:owc-{cycle - 1:06d}", f"{SOURCE_ID}:owc-{cycle:06d}"],
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {"evaluable": 1, "confirmations": int(outcome == "supported"),
                        "refutations": int(outcome == "falsified")},
    }
    if digest(payload) != pair["outcome_payload_sha256"]:
        raise ValueError("reconstructed outcome does not match original payload hash")
    return payload


def resumption_accounting(report):
    """Separate recorded foreground returns from evidence-backed resumption."""
    returns, study_telemetry, genuine_deltas = [], [], []
    for layout in report["layouts"]:
        study_ids = {row["question_id"] for row in layout["rows"]}
        decisions = [row["pre_action_native_cycle"] for row in layout["rows"]]
        if layout.get("final_choice"):
            decisions.append(layout["final_choice"])
        for decision in decisions:
            study_telemetry.extend(decision.get("study_question_telemetry", []))
            if decision.get("resumed_thread_id") and decision.get("foreground_changed"):
                returns.append({**decision, "returns_to_study_question": decision.get("selected_question_id") in study_ids})
        if "prior_genuine_resumption_count" in layout and "final_metadata" in layout:
            genuine_deltas.append(layout["final_metadata"]["genuine_resumption_count"] - layout["prior_genuine_resumption_count"])
    return {
        "original_raw_foreground_returns": len(returns),
        "original_returns_with_new_evidence_priority_support": sum(bool(row.get("priority_change_supported_by_new_evidence")) for row in returns),
        "original_genuine_resumption_count_increase": sum(genuine_deltas) if len(genuine_deltas) == len(report["layouts"]) else None,
        "original_raw_foreground_returns_to_study_question": sum(row["returns_to_study_question"] for row in returns),
        "original_study_question_relevance_opportunities": sum(bool(row.get("resumption_opportunity")) for row in study_telemetry),
        "original_study_question_selected_after_relevance": sum(bool(row.get("resumption_opportunity") and row.get("selected")) for row in study_telemetry),
        "original_returned_question_ids": sorted({row["selected_question_id"] for row in returns}),
    }


def qualify_report(report, contexts):
    """Read-only qualifications with matched-context opportunity denominators."""
    history, counts, context_manifest = [], {}, {}
    rows = [row for layout in report["layouts"] for row in layout["rows"]]
    foreground = sum(row["pre_action_native_cycle"]["selected_question_id"] == row["question_id"] for row in rows)
    for arm in ("retained", "ablated"):
        counts[arm] = {"matched_disconfirmed_effect_opportunities": 0,
                      "repeated_disconfirmed_effects": 0, "avoided_disconfirmed_effects": 0}
    qualified_rows = []
    for layout in report["layouts"]:
        history = []
        for row in layout["rows"]:
            folder = contexts / f"seed-{layout['seed']}" / f"selector-{row['step']:02d}"
            retained = json.loads((folder / "retained.json").read_text())
            ablated = json.loads((folder / "ablated.json").read_text())
            pair = row["selector_pair"]
            for arm, context in (("retained", retained), ("ablated", ablated)):
                if digest(context) != pair[f"{arm}_context_sha256"]:
                    raise ValueError("saved selector context does not match frozen execution")
                context_manifest[str((folder / f'{arm}.json').relative_to(contexts))] = digest(context)
            observation = retained["observation"]
            candidate = row["candidate"]
            current_key = matched_attempt_key(observation, candidate, pair["retained"]["command"])
            eligible = [prior for prior in history
                        if prior["attempt_key"][:2] == current_key[:2]
                        and prior["outcome"] == "supported"
                        and prior["selection"]["mode"] == "seek_disconfirming_observation"
                        and prior["selection"]["falsification_probability"] > .5]
            arm_rows = {}
            for arm in ("retained", "ablated"):
                measured = repeat_measures(history, observation, candidate, pair[arm])
                if measured != row["repetitions"][arm]:
                    raise AssertionError("frozen repeat counts failed context replay")
                repeated = measured["same_context_disconfirmed_expected_effect_repeated"]
                opportunity = bool(eligible)
                avoided = opportunity and not repeated
                counts[arm]["matched_disconfirmed_effect_opportunities"] += int(opportunity)
                counts[arm]["repeated_disconfirmed_effects"] += int(repeated)
                counts[arm]["avoided_disconfirmed_effects"] += int(avoided)
                arm_rows[arm] = {"opportunity": opportunity, "repeated": repeated, "avoided": avoided}
            qualified_rows.append({"seed": layout["seed"], "step": row["step"],
                                   "study_question_foreground_selected": row["pre_action_native_cycle"]["selected_question_id"] == row["question_id"],
                                   "repeat_effect_qualification": arm_rows})
            history.append({"step": row["step"], "objective_key": objective_key(candidate),
                            "attempt_key": current_key, "selection": pair["retained"], "outcome": row["outcome"]})
    return {
        "original_cycle_flags": DEFAULT_FLAGS,
        "resumption_accounting": resumption_accounting(report),
        "harness_scheduled_challenge_actions": len(rows),
        "study_question_foreground_selections_before_action": foreground,
        "actions_without_study_question_foreground_selection": len(rows) - foreground,
        "native_outcome_pairs": sum(row["native_outcome_pair"] is not None for row in rows),
        "matched_repeat_effect_counts": counts,
        "objective_recurrence_is_observational_only": True,
        "selector_context_manifest": context_manifest,
        "rows": qualified_rows,
        "qualification": [
            "Challenge actions were scheduled by the research harness through the capability gate, whether or not the ordinary agenda selected that inquiry.",
            "No ordinary agenda selection or resumption was forced. This statement does not imply the challenge actions were autonomously selected by the native foreground agenda.",
            "Original native cycles used default flags, including strict_experiment_admission=false and planning_lab=false.",
            "The temporal objective is held fixed in the selector contrast. Repeated refuted objectives are observational harness counts, not an ablation effect on objective selection.",
            "A zero repeated-effect numerator with zero matched opportunities cannot establish avoidance. Partial observability and probabilistic uncertainty limit any matched-context inference.",
            "Raw foreground returns are not genuine evidence-backed resumptions. The separate accounting records evidence-supported returns, genuine-counter increases, and returns to the staged inquiry.",
            "Persistence/restart coverage means fresh objects reloaded from disk, not an OS-process crash/restart.",
        ],
    }


def production_cycle(path, observation, now, question_id, prior_ids):
    before = StateStore(path).load()
    with fixed_clock(now):
        result = AgentCore(StateStore(path)).cycle(
            stimulus="continue ordinary operation", observation=deepcopy(observation),
            _now_override=now, **PRODUCTION_FLAGS,
        )
    after = StateStore(path).load()
    if after["cycles"] != before["cycles"] + 1:
        raise AssertionError("production-flag probe did not advance exactly once")
    if result["action_lab_result"] is not None:
        raise AssertionError("unexpected Action Lab authority")
    if not prior_ids <= _agenda_identity(after):
        raise AssertionError("production-flag probe lost prior agenda identities")
    diag = evaluate_resumption_opportunities(after)
    if diag["handoff_or_selection_mismatch_count"]:
        raise AssertionError("production-flag probe contains a Phase 42 mismatch")
    return {"choice": decision_summary(result, question_id),
            "flags": deepcopy(PRODUCTION_FLAGS),
            "cycle": after["cycles"],
            "planning_lab_result": result["planning_lab_result"],
            "genuine_resumption_count": after.get("agenda", {}).get("genuine_resumption_count", 0),
            "phase42_mismatch_count": diag["handoff_or_selection_mismatch_count"],
            "final_state_sha256": file_digest(path)}


def production_pair(input_path, row, directory):
    pair = row["native_outcome_pair"]
    expected = pair["pre_intervention_state_sha256"]
    if file_digest(input_path) != expected:
        raise ValueError("archived pre-probe state does not match original byte hash")
    payload = verified_payload(row)
    before = StateStore(input_path).load()
    observation = deepcopy(before["environment_snapshots"][-1])
    if digest(observation) != pair["shared_observation_sha256"]:
        # The main loop reuses its baseline snapshot, including that snapshot's
        # original cycle number; subsequent cycles append updated cycle values.
        matching = [snapshot for snapshot in before["environment_snapshots"]
                    if digest(snapshot) == pair["shared_observation_sha256"]]
        if not matching:
            raise ValueError("original matched repository observation is unavailable")
        observation = deepcopy(matching[-1])
    pending = next(exp for exp in before["experiments"] if exp["id"] == row["experiment_id"])
    if pending["readiness"] != "awaiting_native_evidence" or pending["question_id"] != row["question_id"]:
        raise ValueError("archived inquiry is not the original valid pending inquiry")
    prior_ids = _agenda_identity(before)
    paths = {}
    for arm in ("retained", "withheld"):
        path = directory / arm / "ora.json"
        path.parent.mkdir(parents=True)
        shutil.copy2(input_path, path)
        if file_digest(path) != expected:
            raise AssertionError("production-flag fork is not byte-identical")
        paths[arm] = path
    evidence_ref, outcome = apply_outcome(paths["retained"], row["experiment_id"], payload, pair["shared_time"])
    changed = assert_outcome_only_delta(before, StateStore(paths["retained"]).load(), row["experiment_id"], payload)
    if file_digest(paths["withheld"]) != expected:
        raise AssertionError("production-flag withheld fork changed before its cycle")
    del before
    results = {arm: production_cycle(path, observation, pair["shared_time"], row["question_id"], prior_ids)
               for arm, path in paths.items()}
    if file_digest(input_path) != expected:
        raise AssertionError("production-flag probe changed archived input")
    return {
        "step": row["step"], "experiment_id": row["experiment_id"], "question_id": row["question_id"],
        "pre_intervention_state_sha256": expected,
        "original_pre_probe_hash_verified": True,
        "shared_observation_sha256": digest(observation),
        "shared_time": pair["shared_time"], "outcome_payload_sha256": digest(payload),
        "outcome_evidence_ref": evidence_ref, "outcome": outcome,
        "normal_api_changed_root_fields": changed, "prior_history_preserved": True,
        "source_unchanged": True, "restart_kind": "fresh_objects_from_persisted_files",
        **results,
        "choice_changed": choice_key(results["retained"]["choice"]) != choice_key(results["withheld"]["choice"]),
        "default_flag_choice_changed": pair["choice_changed"],
        "retained_choice_changed_from_default_flags": choice_key(results["retained"]["choice"]) != choice_key(pair["retained"]["choice"]),
        "withheld_choice_changed_from_default_flags": choice_key(results["withheld"]["choice"]) != choice_key(pair["withheld"]["choice"]),
    }


def run(base_report, inputs, contexts, output):
    base_hash = file_digest(base_report)
    report = json.loads(base_report.read_text())
    if report["study"] != "challenge-retained-evidence-v1" or not report["integrity_passed"]:
        raise ValueError("requires a completed original retained-evidence study")
    manifest = runtime_manifest()
    if digest(manifest) != EXPECTED_RUNTIME_HASH or manifest != report["provenance"]["runtime_manifest"]:
        raise ValueError("runtime source differs from original frozen execution")
    qualification = qualify_report(report, contexts)
    results, unsupported = [], []
    with tempfile.TemporaryDirectory(prefix="ora-production-flag-probes-") as temp:
        for layout in report["layouts"]:
            for row in layout["rows"]:
                if not row["native_outcome_pair"]:
                    continue
                path = inputs / f"seed-{layout['seed']}-step-{row['step']}.json"
                if not path.exists():
                    unsupported.append({"seed": layout["seed"], "step": row["step"], "reason": "exact pre-probe input unavailable"})
                    continue
                if file_digest(path) != row["native_outcome_pair"]["pre_intervention_state_sha256"]:
                    unsupported.append({"seed": layout["seed"], "step": row["step"], "reason": "pre-probe byte hash mismatch; no probe executed"})
                    continue
                with tempfile.TemporaryDirectory(dir=temp) as pair_dir:
                    result = production_pair(path, row, Path(pair_dir))
                result["seed"] = layout["seed"]
                results.append(result)
                print(json.dumps({"progress": "production_flag_pair", "seed": layout["seed"],
                                  "step": row["step"], "choice_changed": result["choice_changed"]}), flush=True)
    if file_digest(base_report) != base_hash or runtime_manifest() != manifest:
        raise AssertionError("original report or runtime source changed")
    qualified = [entry for result in results
                 for entry in result["retained"]["choice"]["study_question_telemetry"]
                 if entry["resumption_opportunity"]]
    result = {
        "study": "challenge-retained-evidence-qualified-production-flags-v1",
        "integrity_passed": True,
        "original_report_sha256": base_hash,
        "followup_script_sha256": file_digest(Path(__file__)),
        "runtime_manifest_sha256": digest(manifest),
        "original_report_unchanged": True,
        "qualification": qualification,
        "production_flag_probe_settings": {"flags": PRODUCTION_FLAGS, "steps": [1, 8], "seeds": [1, 2, 3, 4],
                                           "cycles_per_arm": 1, "further_challenge_actions": 0},
        "summary": {"requested_pairs": 8, "verified_completed_pairs": len(results),
                    "all_requested_pairs_completed": len(results) == 8,
                    "unsupported_pairs": len(unsupported),
                    "native_choice_changes": sum(row["choice_changed"] for row in results),
                    "retained_choices_changed_from_default_flags": sum(row["retained_choice_changed_from_default_flags"] for row in results),
                    "withheld_choices_changed_from_default_flags": sum(row["withheld_choice_changed_from_default_flags"] for row in results),
                    "study_question_relevance_opportunities": len(qualified),
                    "study_question_selected_after_relevance": sum(entry["selected"] for entry in qualified),
                    **qualification["resumption_accounting"]},
        "pairs": results, "unsupported": unsupported,
        "authority": {"copied_only": True, "new_challenge_actions": False,
                      "live_activation": False, "phase42_credit": False,
                      "external_model_api": False, "global_score_override": False},
        "limitations": [
            "This is an additional, separately labelled one-cycle outcome-availability intervention on exact historical pre-probe inputs.",
            "Strict admission and Planning Lab match the requested production flags, but source state remains the historical 4599-cycle baseline lineage, not current live state.",
            "A changed choice can result from evidence and normal completion consequences together. No claim of pure historical-memory causality is made.",
            "No challenge action follows these probes. They neither validate native challenge scheduling nor grant new-world activation.",
        ],
    }
    persist_json(output, result)
    return result


def refresh_qualifications(base_report, raw_report, execution_source, contexts, output):
    """Recompute reporting fields only, retaining exact execution provenance."""
    base_hash, raw_hash = file_digest(base_report), file_digest(raw_report)
    original = json.loads(base_report.read_text())
    raw = json.loads(raw_report.read_text())
    if raw.get("original_report_sha256") != base_hash:
        raise ValueError("raw followup report does not identify this original report")
    execution_hash = file_digest(execution_source)
    if execution_hash != raw.get("followup_script_sha256"):
        raise ValueError("execution source snapshot does not match raw report provenance")
    result = deepcopy(raw)
    result["qualification"] = qualify_report(original, contexts)
    result["summary"].update(result["qualification"]["resumption_accounting"])
    result["reporting_provenance"] = {
        "mode": "qualification_only_refresh",
        "execution_script_sha256": execution_hash,
        "raw_production_report_sha256": raw_hash,
        "reporting_script_sha256": file_digest(Path(__file__)),
        "additional_native_cycles": 0,
        "additional_challenge_actions": 0,
    }
    if file_digest(base_report) != base_hash or file_digest(raw_report) != raw_hash:
        raise AssertionError("qualification refresh changed an immutable execution report")
    persist_json(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-report", required=True, type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--raw-production-report", type=Path)
    parser.add_argument("--execution-source", type=Path)
    parser.add_argument("--contexts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    protected = [args.base_report, args.raw_production_report, args.execution_source]
    if output.is_relative_to(ROOT) or any(path and output == path.resolve() for path in protected) or (args.inputs and output.is_relative_to(args.inputs.resolve())) or output.is_relative_to(args.contexts.resolve()):
        parser.error("output must be outside source and all immutable input locations")
    if args.raw_production_report:
        if not args.execution_source:
            parser.error("qualification refresh requires the exact execution-source snapshot")
        result = refresh_qualifications(args.base_report, args.raw_production_report, args.execution_source, args.contexts, output)
    else:
        if not args.inputs:
            parser.error("native replay requires --inputs")
        result = run(args.base_report, args.inputs, args.contexts, output)
    print(json.dumps({"integrity_passed": result["integrity_passed"], **result["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
