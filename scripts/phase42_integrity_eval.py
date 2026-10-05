from __future__ import annotations

import argparse
import json
from pathlib import Path

from agenttest.semantic import question_has_active_experiment_path


def _intervention_invalidated_refs(state: dict) -> set[str]:
    """Reconstruct exclusions from raw records, never the agenda collector."""
    prediction_ids = {
        str(item["id"])
        for item in state.get("predictions", [])
        if isinstance(item, dict) and item.get("id")
        and item.get("status") == "invalidated_by_intervention"
    }
    experiment_ids: set[str] = set()
    refs = set(prediction_ids)
    for experiment in state.get("experiments", []):
        if not isinstance(experiment, dict):
            continue
        contract = experiment.get("evidence_contract") or {}
        prediction_id = contract.get("prediction_id") if isinstance(contract, dict) else None
        if not (
            experiment.get("observed_prediction_status") == "invalidated_by_intervention"
            or experiment.get("completion_source")
            == "prediction_contract_invalidated_by_intervention"
            or prediction_id in prediction_ids
        ):
            continue
        experiment_id = experiment.get("id")
        if isinstance(experiment_id, str) and experiment_id:
            experiment_ids.add(experiment_id)
            refs.add(experiment_id)
        if isinstance(prediction_id, str) and prediction_id:
            prediction_ids.add(prediction_id)
            refs.add(prediction_id)
        refs.update(
            ref for ref in experiment.get("evidence_refs", [])
            if isinstance(ref, str) and ref
        )
    for reflection in state.get("reflections", []):
        if not isinstance(reflection, dict):
            continue
        if (
            reflection.get("outcome") == "invalidated_by_intervention"
            or reflection.get("prediction_id") in prediction_ids
            or reflection.get("experiment_id") in experiment_ids
        ):
            reflection_id = reflection.get("id")
            if isinstance(reflection_id, str) and reflection_id:
                refs.add(reflection_id)
    return refs


def evaluate(state: dict) -> dict:
    agenda = state.get("agenda") or {}
    decisions = agenda.get("decisions") or []
    latest = decisions[-1] if decisions else None
    failures: list[dict] = []

    if not isinstance(latest, dict):
        return {
            "ok": True,
            "checked": False,
            "reason": "no_phase42_agenda_decision",
            "failures": [],
        }

    # Historical provenance may retain these refs. Neither a selected nor a
    # suspended candidate may credit them as direct progress or fresh evidence.
    invalidated_refs = _intervention_invalidated_refs(state)
    candidates = [("selected", latest.get("selected"))]
    candidates.extend(
        ("candidate_summaries", item)
        for item in latest.get("candidate_summaries", [])
    )
    for surface, candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        credited_refs = {
            ref for field in ("thread_progress_evidence_refs", "new_evidence_refs")
            for ref in candidate.get(field, [])
            if isinstance(ref, str)
        }
        contaminated = credited_refs & invalidated_refs
        if contaminated:
            failures.append(
                {
                    "kind": "intervention_invalidated_thread_progress",
                    "question_id": candidate.get("question_id"),
                    "surface": surface,
                    "refs": sorted(contaminated),
                }
            )

    questions = {
        str(item.get("id")): item
        for item in state.get("questions", [])
        if isinstance(item, dict) and item.get("id")
    }

    for candidate in latest.get("candidate_summaries", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("source") != "repository_stability_prediction":
            continue
        question_id = str(candidate.get("question_id") or "")
        question = questions.get(question_id)
        if question is None:
            failures.append(
                {
                    "kind": "missing_candidate_question",
                    "question_id": question_id,
                }
            )
            continue

        final_active = question_has_active_experiment_path(state, question)
        agenda_active = candidate.get("active_experiment_path") is True
        if final_active and not agenda_active:
            failures.append(
                {
                    "kind": "stale_replication_actionability_snapshot",
                    "question_id": question_id,
                    "decision_id": latest.get("id"),
                    "cycle": latest.get("cycle"),
                    "agenda_active_experiment_path": agenda_active,
                    "final_active_experiment_path": final_active,
                }
            )

    selected = latest.get("selected")
    if isinstance(selected, dict):
        progress_refs = {
            str(ref)
            for ref in selected.get("thread_progress_evidence_refs", [])
            if isinstance(ref, str)
        }
        new_refs = {
            str(ref)
            for ref in selected.get("new_evidence_refs", [])
            if isinstance(ref, str)
        }
        ungrounded_new_refs = new_refs - progress_refs
        if ungrounded_new_refs:
            failures.append(
                {
                    "kind": "new_evidence_not_grounded_in_thread_progress",
                    "question_id": selected.get("question_id"),
                    "refs": sorted(ungrounded_new_refs),
                }
            )

    return {
        "ok": not failures,
        "checked": True,
        "decision_id": latest.get("id"),
        "cycle": latest.get("cycle"),
        "policy_version": latest.get("policy_version"),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state/organism.json")
    args = parser.parse_args()

    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    result = evaluate(state)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
