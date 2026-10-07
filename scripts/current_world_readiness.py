"""Read-only full-history admission check for the dormant current-world lane.

Pins the complete organism bytes. Never accepts a sampled runtime projection,
claims a heartbeat, executes an action, changes state, or enables the workflow.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from agenttest.current_world_investigation import (
    ACTION_ALLOWANCE, CHECKPOINT_BYTES, DISCOVERY_LIMIT, MAX_CASES,
    MAX_DISCOVERY_ADDITIONS, MAX_DISCOVERY_REVISIONS, MAX_OBSERVATIONS,
    MAX_REVISED_DISCOVERY, current_view, discovery_partition, execution_hash,
    model_structure_changes, prepare_next_case,
)
from agenttest.grounded_policy import policy
from agenttest.heartbeat_claim import MAX_REQUESTS
from agenttest.grounded_policy.primitives import Conflict, canonical, digest, strict_json


INTEGER = re.compile(r"-?[0-9]+\Z")


def _rational_digits(value):
    if isinstance(value, list):
        if len(value) == 2 and all(isinstance(x, str) and INTEGER.fullmatch(x) for x in value):
            return max(len(x.lstrip("-")) for x in value)
        return max((_rational_digits(item) for item in value), default=0)
    if isinstance(value, dict):
        return max((_rational_digits(item) for item in value.values()), default=0)
    return 0


def _partition_report(view, discovery, cohort, evidence):
    counts = Counter(row["action"] for row in evidence if row["before_context"] == view["context"])
    return {"discovery_rows": len(discovery), "evidence_rows": len(evidence),
            "discovery_event_ids": [row["event_id"] for row in discovery],
            "evidence_event_ids": [row["event_id"] for row in evidence],
            "discovery_hash": digest(discovery), "cohort_hash": cohort["cohort_digest"],
            "cohort_body_sha256": digest(cohort),
            "evidence_refs_hash": digest([{"event_id": row["event_id"], "sha256": digest(row)}
                                          for row in evidence]),
            "cohort_bytes": len(canonical(cohort)),
            "exact_context_evidence_counts": {action: counts[action] for action in policy.ACTIONS},
            "cohort_actions": [{"action": action["action"], "status": action["status"],
                                "models": len(action["models"])} for action in cohort["actions"]]}


def _preservation_report(original, lane):
    """Compare literal canonical bodies as well as their hashes, including old cases."""
    fields = {}
    for field in ("discovery", "cohort", "cases", "discovery_revisions"):
        before = original.get(field, [] if field == "discovery_revisions" else None)
        after = lane.get(field, [] if field == "discovery_revisions" else None)
        if field in {"cases", "discovery_revisions"} and isinstance(after, list) and isinstance(before, list):
            after = after[:len(before)]
        fields[field] = {"sha256_before": digest(before), "sha256_after": digest(after),
                         "canonical_body_unchanged": canonical(before) == canonical(after)}
    after_cases = lane.get("cases", [])
    if not isinstance(after_cases, list):
        after_cases = []
    cases = []
    for index, case in enumerate(original["cases"]):
        after = after_cases[index] if index < len(after_cases) else None
        cases.append({"case_id": case.get("case_id"), "case_hash_before": case.get("case_hash"),
                      "case_hash_after": after.get("case_hash") if isinstance(after, dict) else None,
                      "sha256_before": digest(case), "sha256_after": digest(after),
                      "canonical_body_unchanged": canonical(case) == canonical(after)})
    return {"original_records_preserved": all(item["canonical_body_unchanged"] for item in fields.values()),
            "original_record_preservation": fields, "old_case_preservation": cases}


def inspect_full_state(path: Path, expected_sha256: str) -> dict:
    payload = path.read_bytes()
    before_hash = hashlib.sha256(payload).hexdigest()
    if before_hash != expected_sha256:
        raise Conflict("full_state_sha256_mismatch")
    state = strict_json(payload)
    if (not isinstance(state, dict) or "format" in state
            or type(state.get("cycles")) is not int
            or type(state.get("schema_version")) is not int
            or not isinstance(state.get("planning_lab"), dict)
            or "transition_observations_count" in state["planning_lab"]
            or "same_world_transition_observations_sample_indexes" in state["planning_lab"]):
        raise Conflict("complete_organism_required_sampled_projection_rejected")
    lab = state["planning_lab"]
    if not isinstance(lab.get("transition_observations"), list):
        raise Conflict("complete_transition_history_required")
    # All transition rows remain present. Clone only fields read by this adapter;
    # no full-state deepcopy or writable StateStore exists.
    observed = {"cycles": state["cycles"], "planning_lab": deepcopy({
        key: lab.get(key) for key in ("position", "bounds", "world_version", "transition_observations")})}
    original_lane = state.get("current_world_investigation")
    claims = state.get("current_world_heartbeat") or {}
    completed_claims = len(claims.get("completed", []))
    abandoned_claims = len(claims.get("abandoned", []))
    pending_claims = int(bool(claims.get("pending")))
    report = {"format": "current-world-full-history-readiness-v1",
              "state_sha256": before_hash, "state_bytes": len(payload),
              "candidate_execution_hash": execution_hash(), "policy_version": policy.VERSION,
              "readiness_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cycle": state["cycles"], "schema_version": state["schema_version"],
              "world_version": lab.get("world_version"), "position": lab.get("position"),
              "total_transition_rows": len(lab["transition_observations"]),
              "same_world_delivered_rows": sum(row.get("world_version") == lab.get("world_version")
                  for row in lab["transition_observations"] if isinstance(row, dict)),
              "bounds": {"observations": MAX_OBSERVATIONS, "discovery": DISCOVERY_LIMIT,
                         "discovery_additions": MAX_DISCOVERY_ADDITIONS,
                         "discovery_revisions": MAX_DISCOVERY_REVISIONS,
                         "revised_discovery": MAX_REVISED_DISCOVERY,
                         "cases": MAX_CASES, "actions": ACTION_ALLOWANCE,
                         "checkpoint_bytes": CHECKPOINT_BYTES, "rational_digits": policy.RATIONAL_DIGITS},
              "complete_history_evaluated": False, "action_executed": False,
              "activation_performed": False, "status": "blocked", "decision_status": "blocked",
              "heartbeat_claim_budget": {"limit": MAX_REQUESTS, "completed": completed_claims,
                  "abandoned": abandoned_claims, "pending": pending_claims,
                  "remaining_new_claims": MAX_REQUESTS - completed_claims - abandoned_claims - pending_claims},
              "initialized_lane": original_lane is not None, "new_case_prepared": False,
              "discovery_revision_appended": False, "promoted_event_ids": [],
              "newly_promoted_event_ids": [],
              "structural_changes": [], "new_model_structures": []}
    try:
        if original_lane is not None:
            if (not isinstance(original_lane, dict) or not isinstance(original_lane.get("cases"), list)
                    or any(not isinstance(case, dict) for case in original_lane["cases"])):
                raise Conflict("invalid_current_world_checkpoint")
            lane_bytes = canonical(original_lane)
            if len(lane_bytes) > CHECKPOINT_BYTES:
                raise Conflict("current-world checkpoint exceeds schema byte bound")
            observed["current_world_investigation"] = strict_json(lane_bytes)
            report.update(checkpoint_bytes_before=len(lane_bytes),
                          **_preservation_report(original_lane, observed["current_world_investigation"]))
        view = current_view(observed)
        if original_lane is None:
            discovery = view["rows"][:DISCOVERY_LIMIT]
            evidence = view["rows"][len(discovery):]
            cohort = policy.build_cohort(discovery)
            policy.verify_cohort(discovery, cohort)
        else:
            discovery, cohort, evidence = discovery_partition(observed["current_world_investigation"], view)
        report.update(unique_same_world_rows=len(view["rows"]),
                      observation_headroom=MAX_OBSERVATIONS - len(view["rows"]),
                      maximum_event_id_length=max((len(row["event_id"]) for row in view["rows"]), default=0),
                      observation_hash=view["observation_hash"], source_row_count=len(view["rows"]),
                      source_rows_hash=digest([{"event_id": row["event_id"], "sha256": digest(row)}
                                               for row in view["rows"]]),
                      **_partition_report(view, discovery, cohort, evidence))
        old_case_count = len(original_lane["cases"]) if original_lane is not None else 0
        old_revision_count = len(original_lane.get("discovery_revisions", [])) if original_lane is not None else 0
        prepared = prepare_next_case(observed, request_id="readiness:full-history")
        lane = observed["current_world_investigation"]
        new_cases = lane["cases"][old_case_count:]
        new_revisions = lane.get("discovery_revisions", [])[old_revision_count:]
        if len(new_cases) > 1 or len(new_revisions) > 1:
            raise Conflict("readiness_append_limit_exceeded")
        report.update(status=prepared["status"], preparation=prepared,
                      new_case_prepared=bool(new_cases), discovery_revision_appended=bool(new_revisions),
                      case_count_before=old_case_count, case_count_after=len(lane["cases"]),
                      discovery_revision_count_before=old_revision_count,
                      discovery_revision_count_after=len(lane.get("discovery_revisions", [])),
                      checkpoint_bytes=len(canonical(lane)),
                      checkpoint_headroom_bytes=CHECKPOINT_BYTES - len(canonical(lane)))
        case = new_cases[0] if new_cases else None
        # Report a valid retained revision even if evaluation blocked. A blocked
        # preparation without one keeps its pre-inspected complete partition.
        if prepared["status"] != "blocked" or new_revisions:
            discovery, cohort, evidence = discovery_partition(lane, view, case=case)
            report.update(_partition_report(view, discovery, cohort, evidence))
        revision_id = case.get("discovery_revision_id") if case is not None else lane.get("active_discovery_revision_id")
        if revision_id is not None:
            revision = next(record for record in lane["discovery_revisions"] if record["revision_id"] == revision_id)
            changes = model_structure_changes(original_lane["cohort"], cohort)
            report.update(discovery_revision_id=revision["revision_id"],
                          discovery_revision_hash=revision["revision_hash"],
                          revision_source_row_count=revision["source_row_count"],
                          revision_source_rows_hash=revision["source_rows_hash"],
                          parent_discovery_hash=revision["parent_discovery_hash"],
                          parent_cohort_hash=revision["parent_cohort_hash"],
                          promoted_event_ids=[ref["event_id"] for ref in revision["promoted_refs"]],
                          newly_promoted_event_ids=[ref["event_id"] for record in new_revisions
                                                    for ref in record["promoted_refs"]],
                          promoted_refs=revision["promoted_refs"], structural_changes=changes,
                          new_model_structures=[{"action": item["action"], "structure": structure}
                              for item in changes for structure in item["added_structures"]])
            if canonical(changes) != canonical(revision["structural_changes"]):
                raise Conflict("readiness_revision_structure_report_mismatch")
        if prepared["status"] in {"prepared", "null"} and case is not None:
            decision = case["decision"]
            report.update(complete_history_evaluated=True, decision_bytes=len(canonical(decision)),
                          maximum_serialized_rational_digits=_rational_digits(decision),
                          decision_status="selected" if decision["selected_action"] is not None else "null",
                          selected_action=decision["selected_action"],
                          menu=[{key: item[key] for key in ("action", "cohort_status", "score_bits",
                                "selection_eligible", "selection_reason", "unresolved_mass")}
                                for item in decision["menu"]])
        else:
            report.update(reason=prepared.get("reason"),
                          decision_status="blocked" if prepared["status"] == "blocked" else "no_new_case")
    except (Conflict, KeyError, TypeError) as error:
        report.update(status="blocked", decision_status="blocked", complete_history_evaluated=False,
                      reason=str(error))
    if original_lane is not None and "current_world_investigation" in observed:
        report.update(_preservation_report(original_lane, observed["current_world_investigation"]))
        if not report["original_records_preserved"]:
            report.update(status="blocked", decision_status="blocked", complete_history_evaluated=False,
                          reason="readiness_original_records_changed")
    if execution_hash() != report["candidate_execution_hash"]:
        raise Conflict("readiness_execution_source_changed")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != report["readiness_script_sha256"]:
        raise Conflict("readiness_script_source_changed")
    report["state_sha256_after"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["source_unchanged"] = report["state_sha256_after"] == before_hash
    if not report["source_unchanged"]:
        raise Conflict("readiness_source_changed_during_inspection")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    source = Path(args.state)
    output = Path(args.output) if args.output else None
    protected = (source, source.parent / "journal.jsonl", source.resolve().parent / "journal.jsonl")
    if output and any(output.resolve() == path.resolve()
                      or output.exists() and path.exists() and output.samefile(path)
                      for path in protected):
        raise Conflict("readiness_output_must_not_alias_state_or_journal")
    result = inspect_full_state(source, args.expected_sha256)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output:
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if result["status"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
