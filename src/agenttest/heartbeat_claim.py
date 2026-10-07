"""Scoped pre-cycle Git claim and coherent heartbeat commit verification.

Extends the interaction request claim pattern, without a local WAL or another
state owner. Pending internal calculations are not durable movement. Only a
verified final Git tree containing organism.json and its journal commits one
result. Exact pending requests may recompute from the unchanged remote snapshot.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

from .current_world_investigation import execution_hash
from .grounded_policy.primitives import Conflict, canonical, digest, label, strict_json

VERSION = "current-world-heartbeat-claim-v1"
MAX_REQUESTS = 16
KEY = "current_world_heartbeat"
DEFAULT_PAYLOAD = {"mode": "current_world_investigation", "planning_lab": True,
                   "strict_experiment_admission": True, "cognition": False,
                   "stimulus": "autonomous heartbeat", "observation_supplied": True}


def _read(path: Path) -> dict:
    value = strict_json(path.read_bytes())
    if not isinstance(value, dict):
        raise Conflict("invalid_organism_object")
    return value


def _write(path: Path, state: dict) -> None:
    temp = path.with_suffix(path.suffix + ".claim.tmp")
    temp.write_bytes(canonical(state) + b"\n")
    temp.replace(path)


def _journal_hash(path: Path) -> str:
    journal = path.parent / "journal.jsonl"
    return hashlib.sha256(journal.read_bytes() if journal.exists() else b"").hexdigest()


def _state_hash(state: dict) -> str:
    return digest({key: value for key, value in state.items() if key != KEY})


def _git(path: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(["git", "-C", str(path.parent), *args], stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, OSError) as error:
        raise Conflict("heartbeat_requires_verified_git_snapshot") from error


def verify_remote_snapshot(path: Path, commit: str) -> None:
    """Require exact tracked content at the fetched remote commit, never inodes.

The workflow fetches immediately after the claim push (or on a fresh retry).
This local check does not itself assert a network fetch or successful push.
"""
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise Conflict("invalid_claim_commit")
    head = _git(path, "rev-parse", "HEAD").decode().strip()
    remote = _git(path, "rev-parse", "refs/remotes/origin/autonomous/growth").decode().strip()
    if head != commit or remote != commit:
        raise Conflict("claim_not_at_fetched_remote_head")
    root = Path(_git(path, "rev-parse", "--show-toplevel").decode().strip())
    relative = str(path.resolve().relative_to(root.resolve()))
    if _git(path, "show", f"{commit}:{relative}") != path.read_bytes():
        raise Conflict("local_state_differs_from_remote_claim_snapshot")
    # Includes journal, source and untracked files; clean checkout proves a prior
    # interrupted local save/calculation is not silently being used as input.
    if _git(path, "status", "--porcelain", "--untracked-files=all").strip():
        raise Conflict("heartbeat_requires_clean_claim_checkout")


def claim_heartbeat(path: Path, request_id: str, *, payload: dict | None = None) -> dict:
    label(request_id, "heartbeat request ID")
    payload = deepcopy(DEFAULT_PAYLOAD if payload is None else payload)
    state = _read(path)
    ledger = state.get(KEY, {"version": VERSION, "pending": None, "completed": [], "abandoned": []})
    if ledger.get("version") != VERSION:
        raise Conflict("heartbeat_claim_version_mismatch")
    matches = [record for record in ledger["completed"] if record["request_id"] == request_id]
    if len(matches) > 1:
        raise Conflict("ambiguous_completed_heartbeat")
    if matches:
        if matches[0]["claim"].get("payload") != payload:
            raise Conflict("completed_heartbeat_payload_changed")
        verify_completed(path, request_id)
        return {"status": "already_completed", "request_id": request_id}
    if any(record["request_id"] == request_id for record in ledger["abandoned"]):
        raise Conflict("heartbeat_request_was_abandoned")
    pending = ledger.get("pending")
    if pending:
        if pending.get("request_id") != request_id:
            raise Conflict("different_heartbeat_request_pending")
        if pending.get("payload") != payload:
            raise Conflict("pending_heartbeat_payload_changed")
        _verify_input(path, state, pending)
        commit = _git(path, "rev-parse", "HEAD").decode().strip()
        verify_remote_snapshot(path, commit)
        return {"status": "already_claimed", "request_id": request_id}
    if len(ledger["completed"]) + len(ledger["abandoned"]) >= MAX_REQUESTS:
        raise Conflict("bounded_heartbeat_claim_capacity_exhausted")
    authority = (state.get("current_world_investigation") or {}).get("pending_authority")
    claim = {"version": VERSION, "request_id": request_id, "payload": payload,
             "input_cycle": state.get("cycles", 0), "input_state_hash": _state_hash(state),
             "input_journal_hash": _journal_hash(path), "execution_hash": execution_hash(),
             "prepared_authority": deepcopy(authority)}
    claim["claim_hash"] = digest(claim)
    ledger["pending"] = claim
    state[KEY] = ledger
    _write(path, state)
    return {"status": "created", "request_id": request_id, "claim_hash": claim["claim_hash"]}


def _verify_input(path: Path, state: dict, claim: dict) -> None:
    if claim.get("claim_hash") != digest({k: v for k, v in claim.items() if k != "claim_hash"}):
        raise Conflict("heartbeat_claim_content_changed")
    if claim.get("input_state_hash") != _state_hash(state) or claim.get("input_cycle") != state.get("cycles", 0):
        raise Conflict("heartbeat_claim_input_state_changed")
    if claim.get("input_journal_hash") != _journal_hash(path):
        raise Conflict("heartbeat_claim_input_journal_changed")
    if claim.get("execution_hash") != execution_hash():
        raise Conflict("heartbeat_claim_execution_version_changed")


def validate_cycle_claim(path: Path, request_id: str, commit: str, payload: dict) -> dict:
    state = _read(path)
    ledger = state.get(KEY) or {}
    if any(record.get("request_id") == request_id for record in ledger.get("completed", [])):
        raise Conflict("heartbeat_already_completed_do_not_run_core")
    pending = ledger.get("pending")
    if not pending or pending.get("request_id") != request_id:
        raise Conflict("missing_matching_remote_heartbeat_claim")
    if pending.get("payload") != payload:
        raise Conflict("heartbeat_cycle_payload_changed")
    _verify_input(path, state, pending)
    verify_remote_snapshot(path, commit)
    return deepcopy(pending)


def reject_unfinished_claim(state: dict) -> None:
    """Legacy writes cannot silently bypass a claimed, unfinished heartbeat."""
    if (state.get(KEY) or {}).get("pending"):
        raise Conflict("unfinished_heartbeat_requires_resume_or_explicit_abandonment")


def finish_heartbeat(state: dict, event: dict, claim: dict, commit: str) -> None:
    ledger = state[KEY]
    if ledger.get("pending") != claim or state["cycles"] != claim["input_cycle"] + 1:
        raise Conflict("heartbeat_completion_claim_mismatch")
    event["heartbeat_request_id"] = claim["request_id"]
    event["heartbeat_claim_hash"] = claim["claim_hash"]
    event["heartbeat_claim_commit"] = commit
    checkpoint = digest({"planning_lab": state.get("planning_lab"),
                         "investigation": state.get("current_world_investigation")})
    event["current_world_checkpoint_hash"] = checkpoint
    record = {"request_id": claim["request_id"], "claim": deepcopy(claim),
              "claim_commit": commit, "cycle": state["cycles"],
              "checkpoint_hash": checkpoint, "event_hash": digest(event),
              "action": deepcopy(event.get("planning_lab_result")),
              "preparation": deepcopy(event.get("current_world_preparation")),
              "durability": "requires_final_git_commit"}
    record["content_hash"] = digest(record)
    ledger["completed"].append(record)
    ledger["pending"] = None


def verify_completed(path: Path, request_id: str, *, require_current: bool = False) -> dict:
    """Publication gate: exactly one matching cycle event and bound outcome."""
    state = _read(path)
    ledger = state.get(KEY) or {}
    rows = [row for row in ledger.get("completed", []) if row.get("request_id") == request_id]
    if len(rows) != 1:
        raise Conflict("missing_or_ambiguous_completed_heartbeat")
    record = rows[0]
    if record.get("content_hash") != digest({k: v for k, v in record.items() if k != "content_hash"}):
        raise Conflict("completed_heartbeat_content_changed")
    journal = path.parent / "journal.jsonl"
    events = [strict_json(line) for line in journal.read_bytes().splitlines() if line.strip()]
    matches = [event for event in events if event.get("heartbeat_request_id") == request_id]
    if len(matches) != 1 or digest(matches[0]) != record["event_hash"]:
        raise Conflict("missing_duplicate_or_changed_heartbeat_journal_event")
    event = matches[0]
    if event.get("event") != "cycle" or event.get("cycle") != record["cycle"]:
        raise Conflict("heartbeat_cycle_event_mismatch")
    if event.get("planning_lab_result") != record["action"] or event.get("current_world_preparation") != record["preparation"]:
        raise Conflict("heartbeat_outcome_event_mismatch")
    if event.get("heartbeat_claim_hash") != record["claim"]["claim_hash"] or event.get("current_world_checkpoint_hash") != record["checkpoint_hash"]:
        raise Conflict("heartbeat_event_anchor_mismatch")
    # Historical receipts survive later cycles and source upgrades. Verify the
    # full current checkpoint only while this is the latest organism cycle.
    if require_current:
        if state["cycles"] != record["cycle"]:
            raise Conflict("heartbeat_finalization_cycle_changed")
        actual = digest({"planning_lab": state.get("planning_lab"),
                         "investigation": state.get("current_world_investigation")})
        if actual != record["checkpoint_hash"]:
            raise Conflict("heartbeat_state_checkpoint_mismatch")
    preparation = record.get("preparation") or {}
    if preparation.get("case_id"):
        prepared = [case for case in (state.get("current_world_investigation") or {}).get("cases", [])
                    if case.get("case_id") == preparation["case_id"]]
        if (len(prepared) != 1 or prepared[0].get("case_hash") != preparation.get("case_hash")
                or prepared[0]["case_hash"] != digest({k: v for k, v in prepared[0].items() if k != "case_hash"})):
            raise Conflict("heartbeat_prepared_case_content_changed")
        from .current_world_investigation import verify_case_revision
        verify_case_revision(state["current_world_investigation"], prepared[0])
    action = record["action"] or {}
    if action.get("action") is not None:
        lane = state.get("current_world_investigation") or {}
        cases = [row for row in lane.get("cases", []) if row.get("case_id") == action.get("case_id")]
        attempts = [row for row in lane.get("attempts", []) if row.get("attempt_id") == action.get("attempt_id")]
        outcomes = [row for row in lane.get("outcomes", []) if row.get("outcome_id") == action.get("outcome_id")]
        beliefs = [row for row in lane.get("beliefs", []) if row.get("belief_id") == action.get("belief_id")]
        if any(len(rows) != 1 for rows in (cases, attempts, outcomes, beliefs)):
            raise Conflict("heartbeat_owned_outcome_unavailable")
        case, attempt, outcome, belief = cases[0], attempts[0], outcomes[0], beliefs[0]
        if (case["case_hash"] != digest({key: value for key, value in case.items() if key != "case_hash"})
                or case["case_hash"] != action["case_hash"] or attempt["case_id"] != case["case_id"]
                or attempt["request_id"] != request_id or outcome["attempt_id"] != attempt["attempt_id"]
                or outcome["case_id"] != case["case_id"] or belief["outcome_id"] != outcome["outcome_id"]
                or outcome["execution"]["action"] != action["action"]):
            raise Conflict("heartbeat_owned_outcome_binding_mismatch")
        for body in (attempt, outcome, belief):
            if body.get("content_hash") != digest({key: value for key, value in body.items() if key != "content_hash"}):
                raise Conflict("heartbeat_owned_outcome_content_changed")
    return {"status": "verified", "request_id": request_id, "cycle": record["cycle"]}


def abandon_heartbeat(path: Path, request_id: str, reason: str) -> dict:
    """Audited operator rollback; never discard a calculated/completed outcome."""
    if not reason.strip():
        raise Conflict("abandonment_reason_required")
    state = _read(path)
    ledger = state.get(KEY) or {}
    pending = ledger.get("pending")
    if not pending or pending.get("request_id") != request_id:
        raise Conflict("no_matching_pending_heartbeat_to_abandon")
    # Do not require the old execution hash: rollback must survive code upgrades.
    if pending.get("input_state_hash") != _state_hash(state) or pending.get("input_journal_hash") != _journal_hash(path):
        raise Conflict("cannot_abandon_changed_or_ambiguous_heartbeat_input")
    ledger["abandoned"].append({"request_id": request_id, "claim": deepcopy(pending),
                                "reason": reason, "status": "abandoned_uncommitted"})
    ledger["pending"] = None
    lane = state.get("current_world_investigation")
    if lane:
        key = "revision_rollback" if lane.get("revision_attempt") else "rollback"
        lane.setdefault(key, {"cycle": state["cycles"], "reason": reason,
                              "retired_authority": deepcopy(lane.get("pending_authority"))})
        lane["pending_authority"] = None
        lane["status"] = "disabled"
    _write(path, state)
    return {"status": "abandoned_uncommitted", "request_id": request_id}
