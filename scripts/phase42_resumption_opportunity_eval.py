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
    """Classify Phase 42 opportunities, preferring decision-time telemetry."""

    agenda = state.get("agenda") or {}
    decisions = [
        item for item in agenda.get("decisions", [])
        if isinstance(item, dict)
    ]
    opportunities: list[dict] = []
    telemetry_decision_count = 0

    for decision in decisions:
        telemetry = decision.get("candidate_telemetry")
        if not isinstance(telemetry, list):
            continue
        telemetry_decision_count += 1
        selected = decision.get("selected") or {}
        selected_priority = float(selected.get("priority_score", 0.0) or 0.0)
        for item in telemetry:
            if not isinstance(item, dict) or not item.get("resumption_opportunity"):
                continue
            candidate_priority = float(item.get("priority_score", 0.0) or 0.0)
            did_resume = bool(
                item.get("selected")
                and decision.get("resumed_thread_id") == item.get("thread_id")
                and decision.get("foreground_changed") is True
            )
            should_resume = bool(item.get("selected") or candidate_priority > selected_priority)
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
                    "thread_id": item.get("thread_id"),
                    "question_id": item.get("question_id"),
                    "lifecycle_source": item.get("lifecycle_source"),
                    "previous_status": item.get("previous_status"),
                    "new_evidence_refs": _refs(item.get("new_evidence_refs")),
                    "newly_executable": bool(item.get("newly_executable")),
                    "candidate_priority": candidate_priority,
                    "selected_priority": selected_priority,
                    "selected_thread_id": decision.get("selected_thread_id"),
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
        "diagnostic_version": "phase42-resumption-opportunities-v2",
        "retained_decision_count": len(decisions),
        "telemetry_decision_count": telemetry_decision_count,
        "pre_telemetry_decision_count": len(decisions) - telemetry_decision_count,
        "opportunity_count": len(opportunities),
        "resumed_opportunity_count": sum(
            item["classification"] == "resumed" for item in opportunities
        ),
        "lower_priority_opportunity_count": len(lower_priority),
        "handoff_or_selection_mismatch_count": len(mismatches),
        "opportunities": opportunities,
        "note": (
            "Prospective counts use candidate facts recorded at decision time. "
            "Older decisions without telemetry are reported separately and are "
            "not reconstructed into the opportunity totals."
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
