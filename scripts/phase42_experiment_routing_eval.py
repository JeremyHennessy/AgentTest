"""Independent, read-only audit of raw selected-question/experiment routes.

No production routing helper or emitted relationship is used as evidence.
Snapshot-only resolution requires an explicitly matching event cycle.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

VERSION = "raw-experiment-routing-v1"
STATUSES = ("owned", "explicit_followup", "mismatch", "no_experiment", "unknown", "unchecked")
FOLLOWUPS = {
    "resolve_pending_evidence": re.compile(
        r"what obtainable evidence would resolve pending experiment (\S+) "
        r"with the least additional assumption\?"),
    "specify_experiment": re.compile(
        r"what observable, evidence source, and resolution rule would make "
        r"experiment (\S+) evidence-ready\?"),
}


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _lookup(state: dict, collection: str, identifier: str) -> tuple[dict | None, str | None]:
    values = state.get(collection)
    if not isinstance(values, list):
        return None, "missing_ledger"
    matches = [v for v in values if isinstance(v, dict) and v.get("id") == identifier]
    if len(matches) != 1:
        return None, "duplicate_identity" if matches else "missing_record"
    return matches[0], None


def _evaluate(record: Any, state: dict | None) -> dict:
    result = {"cycle": record.get("cycle") if isinstance(record, dict) else None,
              "status": "unchecked", "reason": None, "selected_question_id": None,
              "returned_experiment_id": None, "experiment_question_id": None,
              "parsed_followup_target": None, "raw_contradictions": [],
              "telemetry_disagreements": []}
    if not isinstance(record, dict):
        result["status"], result["reason"] = "unknown", "invalid_cycle_record"
        return result

    def stop(status: str, reason: str) -> dict:
        result["status"], result["reason"] = status, reason
        return result

    question = record.get("question") if "question" in record else None
    experiment = record.get("experiment") if "experiment" in record else None
    intention = record.get("intention") if "intention" in record else None
    if "question" in record and not isinstance(question, dict):
        return stop("unknown", "invalid_selected_question")
    qid = record.get("selected_question_id", question.get("id") if question else None)
    result["selected_question_id"] = qid
    if not _identifier(qid):
        return stop("unknown" if "selected_question_id" in record or "question" in record else "unchecked",
                    "invalid_selected_question_id" if qid is not None else "selected_question_not_recorded")
    if question is not None and question.get("id") != qid:
        result["raw_contradictions"].append("selected_question_id")
        return stop("unknown", "contradictory_selected_question")
    if "experiment" not in record and "experiment_id" not in record:
        return stop("unchecked", "returned_experiment_not_recorded")
    if "experiment" in record and experiment is not None and not isinstance(experiment, dict):
        return stop("unknown", "invalid_returned_experiment")
    if isinstance(experiment, dict) and not _identifier(experiment.get("id")):
        return stop("unknown", "embedded_experiment_identity_unavailable")
    xid = record.get("experiment_id", experiment.get("id") if experiment else None)
    result["returned_experiment_id"] = xid
    if "experiment" in record and (
        (experiment is None and xid is not None)
        or (experiment is not None and experiment.get("id") != xid)
    ):
        result["raw_contradictions"].append("returned_experiment_id")
        return stop("unknown", "contradictory_returned_experiment")
    if xid is None:
        # Only an explicitly null field is no_experiment; a missing nested ID
        # cannot authorize a green null route.
        return stop("no_experiment", "explicit_null_returned_experiment")
    if not _identifier(xid):
        return stop("unknown", "invalid_returned_experiment_id")

    matching_snapshot = (
        isinstance(state, dict) and type(record.get("cycle")) is int
        and type(state.get("cycles")) is int and state["cycles"] == record["cycle"]
    )
    if matching_snapshot:
        for collection, identifier, embedded, fields in (
            ("questions", qid, question, ("id", "text")),
            ("experiments", xid, experiment, ("id", "question_id")),
        ):
            resolved, error = _lookup(state, collection, identifier)
            if error:
                return stop("unknown", collection + "_" + error)
            if embedded is not None and any(embedded.get(f) != resolved.get(f) for f in fields):
                result["raw_contradictions"].append(collection)
                return stop("unknown", "snapshot_record_contradiction")
            if collection == "questions":
                question = resolved
            else:
                experiment = resolved
    elif question is None or experiment is None:
        return stop("unknown", "event_cycle_snapshot_unavailable")
    owner = experiment.get("question_id")
    result["experiment_question_id"] = owner
    if not _identifier(owner):
        return stop("unknown", "experiment_owner_unavailable")
    if owner == qid:
        return stop("owned", "raw_question_ownership")

    if intention is not None and not isinstance(intention, dict):
        return stop("unknown", "invalid_intention_record")
    text = question.get("text")
    if not isinstance(text, str) or not text.strip():
        return stop("unknown", "question_text_unavailable")
    normalized = " ".join(text.casefold().split())
    parsed = [(kind, pattern.fullmatch(normalized)) for kind, pattern in FOLLOWUPS.items()]
    parsed = [(kind, match.group(1)) for kind, match in parsed if match is not None]
    if not parsed:
        return stop("mismatch", "unrelated_question")
    kind, target = parsed[0]
    result["parsed_followup_target"] = target
    if target != xid.casefold():
        return stop("mismatch", "followup_targets_different_experiment")
    intention_id = record.get("intention_id", intention.get("id") if intention else None)
    if matching_snapshot and _identifier(intention_id):
        resolved, error = _lookup(state, "intentions", intention_id)
        if error:
            return stop("unknown", "intention_" + error)
        if intention is not None and any(intention.get(f) != resolved.get(f) for f in ("id", "kind", "target")):
            result["raw_contradictions"].append("intention")
            return stop("unknown", "contradictory_intention")
        intention = resolved
    elif intention is not None and "intention_id" in record and intention.get("id") != record["intention_id"]:
        result["raw_contradictions"].append("intention")
        return stop("unknown", "contradictory_intention")
    if intention is None or not _identifier(intention.get("kind")) or "target" not in intention:
        return stop("unknown", "followup_intention_unavailable")
    if intention["kind"] != kind or intention["target"] != xid:
        return stop("mismatch", "followup_intention_incompatible")
    return stop("explicit_followup", "independently_parsed_targeted_followup")


def evaluate_experiment_routes(records: list, state: dict | None = None) -> dict:
    """Evaluate raw records; a later snapshot is not evidence of an older route."""
    if not isinstance(records, list):
        raise ValueError("records must be a list of raw cycle records")
    if state is not None and not isinstance(state, dict):
        raise ValueError("state must be an object containing an exact-cycle snapshot")
    results = []
    for index, record in enumerate(records):
        result = _evaluate(record, state)
        result["record_index"] = index
        telemetry = record.get("experiment_routing") if isinstance(record, dict) else None
        if isinstance(telemetry, dict) and result["status"] in {"owned", "explicit_followup", "mismatch", "no_experiment"}:
            expected = {"relationship": "unrelated" if result["status"] == "mismatch" else result["status"],
                        "selected_question_id": result["selected_question_id"],
                        "returned_experiment_id": result["returned_experiment_id"],
                        "experiment_question_id": result["experiment_question_id"]}
            result["telemetry_disagreements"] = [key for key, value in expected.items()
                                                 if key in telemetry and telemetry[key] != value]
        results.append(result)
    counts = Counter(r["status"] for r in results)
    checked = sum(counts[k] for k in ("owned", "explicit_followup", "mismatch", "no_experiment"))
    disagreement_count = sum(bool(r["telemetry_disagreements"]) for r in results)
    contradiction_count = sum(bool(r["raw_contradictions"]) for r in results)
    failed = bool(counts["mismatch"] or disagreement_count or contradiction_count)
    summary = "routing_invalid" if failed else "not_checked" if not checked else "incomplete" if counts["unknown"] or counts["unchecked"] else "routing_valid"
    return {"diagnostic_version": VERSION, "status": summary, "checked_count": checked,
            **{key + "_count": counts[key] for key in STATUSES},
            "telemetry_disagreement_count": disagreement_count,
            "raw_contradiction_count": contradiction_count, "records": results,
            "note": "Old green handoff/opportunity checks do not validate question-experiment routing. Unknown/unchecked routes are not passes."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, help="JSON record, JSON list, or JSONL raw cycle records")
    parser.add_argument("--state", help="Optional exact-cycle snapshot for journal ID resolution")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        source = Path(args.records).resolve()
        if source.name == "journal.jsonl" and ((source.parent / "journal-archives.json").exists() or (source.parent / "journal-archives.json").is_symlink()):
            raise ValueError("active journal tail is not full history; use a verified logical export")
        text = source.read_text(encoding="utf-8")
        try:
            records = json.loads(text)
            if isinstance(records, dict):
                records = [records]
        except json.JSONDecodeError:
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        state = json.loads(Path(args.state).read_text(encoding="utf-8")) if args.state else None
        result = evaluate_experiment_routes(records, state)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Routing input error: {error}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["status"] == "routing_valid" else 1 if result["status"] == "routing_invalid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
