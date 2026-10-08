"""Explicit sealed authentic copied cycle-1803 origin for Ora 2 engineering.

This checkpoint is the preserved *planner-only copied* Timing Study 001 control,
not original live Ora. Historical Phase 41 cycle-1771 admission is unchanged.
No world, network, scheduler or model provider is accessed in this module.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .baseline import WORLD, blob_id, project, strict_json
from .learner import ProtocolError

PROFILE = "ora2-study002-authentic-planner1803-v1"
PINS = {
    "origin_profile": PROFILE,
    "origin_snapshot_sha256": "f37c788cee851622823a848a7e3b8b32f67c06bec4b94eb5b709922e7a7aa6ec",
    "origin_journal_sha256": "717b7380101ff7656b13cc5d9f8ac14ade862a6bdd1b9363ad3029d29d8e35e9",
    "origin_snapshot_git_blob": "383ec4b3ffb23c3e83cf901426197205924421f3",
    "origin_journal_git_blob": "9da7e5f3d36fbfed3a74e608407565e7034ad44e",
    "origin_cycle": 1803,
    "origin_journal_lines": 5347,
}


def validate(snapshot_bytes: bytes, journal_bytes: bytes) -> dict:
    """Validate actual historical bytes, active obligations and journal ending."""
    if (type(snapshot_bytes) is not bytes or type(journal_bytes) is not bytes or
            not 0 < len(snapshot_bytes) <= 32 * 1024 * 1024 or
            not 0 < len(journal_bytes) <= 20 * 1024 * 1024):
        raise ProtocolError("invalid bounded copied origin inputs")
    if (hashlib.sha256(snapshot_bytes).hexdigest() != PINS["origin_snapshot_sha256"] or
            hashlib.sha256(journal_bytes).hexdigest() != PINS["origin_journal_sha256"] or
            blob_id(snapshot_bytes) != PINS["origin_snapshot_git_blob"] or
            blob_id(journal_bytes) != PINS["origin_journal_git_blob"]):
        raise ProtocolError("authentic copied historical origin differs from sealed evidence")
    if (not journal_bytes.endswith(b"\n") or
            len(journal_bytes.splitlines()) != PINS["origin_journal_lines"]):
        raise ProtocolError("copied origin journal is incomplete")
    snapshot = strict_json(snapshot_bytes)
    projection = project(snapshot)
    if (projection["origin_cycle"] != 1803 or projection["world"] != WORLD or
            projection["position"] != [1, 1]):
        raise ProtocolError("copied origin environment does not match preserved control")
    lab = snapshot["planning_lab"]
    if (lab.get("active_goal_id") != "PG000448" or
            lab.get("active_plan_id") != "PP000451" or
            lab.get("active_objective_realization_id") is not None):
        raise ProtocolError("inherited active goal/plan cohort absent")
    goals = [x for x in lab.get("goals", ()) if type(x) is dict and x.get("id") == "PG000448"]
    plans = [x for x in lab.get("plans", ()) if type(x) is dict and x.get("id") == "PP000451"]
    if len(goals) != 1 or len(plans) != 1:
        raise ProtocolError("nonunique inherited goal or plan")
    goal, plan = goals[0], plans[0]
    if (goal.get("status") != "active" or goal.get("target") != [0, 2] or
            plan.get("status") != "active" or plan.get("goal_id") != "PG000448" or
            plan.get("goal") != [0, 2] or plan.get("next_step_index") != 1):
        raise ProtocolError("copied inherited obligation changed")
    final_event = strict_json(journal_bytes.splitlines()[-1])
    if (type(final_event) is not dict or final_event.get("event") != "cycle" or
            final_event.get("cycle") != 1803):
        raise ProtocolError("copied journal terminal event differs")
    projection["journal_rows"] = PINS["origin_journal_lines"]
    return projection


def read(snapshot_path: Path, journal_path: Path):
    """Read bounded independent files. Caller must store DB outside the checkout."""
    snapshot_path, journal_path = Path(snapshot_path), Path(journal_path)
    if snapshot_path.resolve() == journal_path.resolve():
        raise ProtocolError("same copied input file supplied twice")
    for path, maximum in ((snapshot_path, 32 * 1024 * 1024),
                          (journal_path, 20 * 1024 * 1024)):
        if (path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or
                not 0 < path.stat().st_size <= maximum):
            raise ProtocolError("bounded independent ordinary source file required")
    raw, journal = snapshot_path.read_bytes(), journal_path.read_bytes()
    return raw, journal, validate(raw, journal)


def verify_metadata(metadata: dict):
    """Require exact origin pins again on every cold restore."""
    if type(metadata) is not dict or any(metadata.get(key) != value for key, value in PINS.items()):
        raise ProtocolError("retained copied origin profile and pins disagree")
