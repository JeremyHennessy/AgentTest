from __future__ import annotations

import argparse
import json
from pathlib import Path

from agenttest.semantic import question_has_active_experiment_path


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
        source_refs = {
            str(ref)
            for ref in selected.get("source_provenance_refs", [])
            if isinstance(ref, str)
        }
        new_refs = {
            str(ref)
            for ref in selected.get("new_evidence_refs", [])
            if isinstance(ref, str)
        }
        provenance_only = source_refs & new_refs
        if provenance_only:
            failures.append(
                {
                    "kind": "source_provenance_scored_as_new_progress",
                    "question_id": selected.get("question_id"),
                    "overlap": sorted(provenance_only),
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
