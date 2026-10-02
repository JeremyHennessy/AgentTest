from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def evaluate_resumption_opportunities(state: dict) -> dict:
    """Classify retained Phase 42 decisions without influencing agenda policy."""

    agenda = state.get("agenda") or {}
    decisions = [
        item for item in agenda.get("decisions", [])
        if isinstance(item, dict)
    ]
    threads = {
        str(item.get("id")): item
        for item in agenda.get("threads", [])
        if isinstance(item, dict) and item.get("id")
    }
    opportunities: list[dict] = []

    for decision in decisions:
        previous_foreground = decision.get("previous_foreground_thread_id")
        selected_thread = decision.get("selected_thread_id")
        resumed_thread = decision.get("resumed_thread_id")
        selected = decision.get("selected") or {}
        summaries = decision.get("candidate_summaries") or []

        for candidate in summaries:
            if not isinstance(candidate, dict):
                continue
            question_id = str(candidate.get("question_id") or "")
            thread = next(
                (
                    item for item in threads.values()
                    if str(item.get("question_id") or "") == question_id
                ),
                None,
            )
            if thread is None:
                continue

            history = [
                item for item in thread.get("history", [])
                if isinstance(item, dict)
                and int(item.get("cycle", -1) or -1) < int(decision.get("cycle", 0) or 0)
            ]
            was_suspended = bool(history) and history[-1].get("to") == "suspended"
            if not was_suspended:
                continue

            new_refs = _refs(candidate.get("new_evidence_refs"))
            newly_executable = bool(candidate.get("active_experiment_path")) and any(
                item.get("to") == "suspended"
                and item.get("reason") == "waiting_for_executable_path_or_new_evidence"
                for item in history[-1:]
            )
            if not new_refs and not newly_executable:
                continue

            candidate_score = float(candidate.get("priority_score", 0.0) or 0.0)
            selected_score = float(selected.get("priority_score", 0.0) or 0.0)
            should_resume = candidate_score > selected_score or selected_thread == thread.get("id")
            did_resume = (
                resumed_thread == thread.get("id")
                and selected_thread == thread.get("id")
                and decision.get("foreground_changed") is True
            )
            classification = (
                "resumed"
                if did_resume
                else "handoff_or_selection_mismatch"
                if should_resume
                else "qualified_but_lower_priority"
            )
            opportunities.append(
                {
                    "decision_id": decision.get("id"),
                    "cycle": decision.get("cycle"),
                    "thread_id": thread.get("id"),
                    "question_id": question_id,
                    "new_evidence_refs": new_refs,
                    "newly_executable": newly_executable,
                    "candidate_priority": candidate_score,
                    "selected_priority": selected_score,
                    "previous_foreground_thread_id": previous_foreground,
                    "selected_thread_id": selected_thread,
                    "should_resume": should_resume,
                    "did_resume": did_resume,
                    "classification": classification,
                }
            )

    mismatches = [
        item for item in opportunities
        if item["classification"] == "handoff_or_selection_mismatch"
    ]
    lower_priority = [
        item for item in opportunities
        if item["classification"] == "qualified_but_lower_priority"
    ]
    return {
        "diagnostic_version": "phase42-resumption-opportunities-v1",
        "retained_decision_count": len(decisions),
        "opportunity_count": len(opportunities),
        "resumed_opportunity_count": sum(
            item["classification"] == "resumed" for item in opportunities
        ),
        "lower_priority_opportunity_count": len(lower_priority),
        "handoff_or_selection_mismatch_count": len(mismatches),
        "opportunities": opportunities,
        "note": (
            "Read-only classification of retained agenda decisions. "
            "This diagnostic does not alter scores, evidence, selection, or state."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state/organism.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    result = evaluate_resumption_opportunities(state)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
