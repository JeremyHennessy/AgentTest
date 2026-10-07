"""Read-only full-history admission check for the dormant current-world lane.

Pins the complete organism bytes. Never accepts a sampled runtime projection,
claims a heartbeat, executes an action, changes state, or enables the workflow.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from agenttest.current_world_investigation import (
    ACTION_ALLOWANCE, CHECKPOINT_BYTES, DISCOVERY_LIMIT, MAX_CASES,
    MAX_OBSERVATIONS, current_view, execution_hash, prepare_next_case,
)
from agenttest.grounded_policy import policy
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
    if state.get("current_world_investigation") is not None:
        raise Conflict("pre_activation_readiness_requires_uninitialized_lane")
    lab = state["planning_lab"]
    if not isinstance(lab.get("transition_observations"), list):
        raise Conflict("complete_transition_history_required")
    # All transition rows remain present. Project only the state fields actually
    # read by this adapter; no full-state deepcopy or writable StateStore exists.
    observed = {"cycles": state["cycles"], "planning_lab": {
        key: lab.get(key) for key in ("position", "bounds", "world_version", "transition_observations")}}
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
                         "cases": MAX_CASES, "actions": ACTION_ALLOWANCE,
                         "checkpoint_bytes": CHECKPOINT_BYTES, "rational_digits": policy.RATIONAL_DIGITS},
              "complete_history_evaluated": False, "action_executed": False,
              "activation_performed": False, "status": "blocked"}
    try:
        view = current_view(observed)
        discovery = view["rows"][:DISCOVERY_LIMIT]
        evidence = view["rows"][len(discovery):]
        cohort = policy.build_cohort(discovery)
        policy.verify_cohort(discovery, cohort)
        counts = Counter(row["action"] for row in evidence if row["before_context"] == view["context"])
        report.update(unique_same_world_rows=len(view["rows"]),
                      observation_headroom=MAX_OBSERVATIONS - len(view["rows"]),
                      maximum_event_id_length=max((len(row["event_id"]) for row in view["rows"]), default=0),
                      discovery_rows=len(discovery), evidence_rows=len(evidence),
                      discovery_hash=digest(discovery), observation_hash=view["observation_hash"],
                      cohort_bytes=len(canonical(cohort)),
                      exact_context_evidence_counts={action: counts[action] for action in policy.ACTIONS},
                      cohort_actions=[{"action": action["action"], "status": action["status"],
                                       "models": len(action["models"])} for action in cohort["actions"]])
        prepared = prepare_next_case(observed, request_id="readiness:full-history")
        lane = observed["current_world_investigation"]
        report.update(status=prepared["status"], preparation=prepared,
                      checkpoint_bytes=len(canonical(lane)),
                      checkpoint_headroom_bytes=CHECKPOINT_BYTES - len(canonical(lane)))
        if prepared["status"] in {"prepared", "null"}:
            decision = lane["cases"][0]["decision"]
            report.update(complete_history_evaluated=True, decision_bytes=len(canonical(decision)),
                          maximum_serialized_rational_digits=_rational_digits(decision),
                          selected_action=decision["selected_action"],
                          menu=[{key: item[key] for key in ("action", "cohort_status", "score_bits",
                                "selection_eligible", "selection_reason", "unresolved_mass")}
                                for item in decision["menu"]])
        else:
            report["reason"] = prepared.get("reason")
    except (Conflict, KeyError, TypeError) as error:
        report["reason"] = str(error)
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
