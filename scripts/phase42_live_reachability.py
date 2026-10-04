from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MAX_EVIDENCE_CHANGE_VALUE = 0.30


def analyze(state: dict[str, Any]) -> dict[str, Any]:
    agenda = state.get("agenda", {})
    decisions = agenda.get("decisions", [])
    if not decisions:
        return {
            "status": "no_agenda_decision",
            "evidence_only_reachable": None,
            "candidates": [],
        }

    latest = decisions[-1]
    selected = latest.get("selected") or {}
    selected_score = float(selected.get("priority_score", 0.0) or 0.0)
    selected_id = str(selected.get("question_id") or "")

    rows = []
    for candidate in latest.get("candidate_summaries", []):
        if str(candidate.get("question_id") or "") == selected_id:
            continue

        legacy = float(candidate.get("legacy_focus_value", 0.0) or 0.0)
        actionability = float(candidate.get("actionability_value", 0.0) or 0.0)
        frontier = float(candidate.get("frontier_value", 0.0) or 0.0)
        saturation_cost = float(
            candidate.get("replication_saturation_cost", 0.0) or 0.0
        )
        current_evidence = float(candidate.get("evidence_change_value", 0.0) or 0.0)
        max_evidence_priority = round(
            legacy
            + actionability
            + frontier
            + MAX_EVIDENCE_CHANGE_VALUE
            - saturation_cost,
            6,
        )
        rows.append(
            {
                "question_id": candidate.get("question_id"),
                "question_text": candidate.get("question_text"),
                "source": candidate.get("source"),
                "current_priority": float(candidate.get("priority_score", 0.0) or 0.0),
                "current_evidence_change_value": current_evidence,
                "max_evidence_change_value": MAX_EVIDENCE_CHANGE_VALUE,
                "max_evidence_only_priority": max_evidence_priority,
                "selected_priority": selected_score,
                "evidence_only_gap": round(selected_score - max_evidence_priority, 6),
                "evidence_only_can_overtake": max_evidence_priority > selected_score,
                "active_experiment_path": bool(candidate.get("active_experiment_path")),
                "new_evidence_refs": list(candidate.get("new_evidence_refs", [])),
            }
        )

    any_reachable = any(row["evidence_only_can_overtake"] for row in rows)
    return {
        "status": "evaluated",
        "cycle": latest.get("cycle"),
        "selected_question_id": selected_id,
        "selected_question_text": selected.get("question_text"),
        "selected_priority": selected_score,
        "selected_legacy_focus_value": float(
            selected.get("legacy_focus_value", 0.0) or 0.0
        ),
        "selected_frontier_value": float(selected.get("frontier_value", 0.0) or 0.0),
        "evidence_only_reachable": any_reachable,
        "interpretation": (
            "At least one suspended candidate can overtake the current foreground "
            "through the existing evidence-change bonus alone."
            if any_reachable
            else (
                "No suspended candidate can overtake the current foreground through "
                "the existing evidence-change bonus alone. A resumption requires an "
                "upstream change such as a different legacy/current question, "
                "actionability/source change, frontier change, or other state change."
            )
        ),
        "candidates": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    state = json.loads(Path(args.state).read_text())
    result = analyze(state)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
