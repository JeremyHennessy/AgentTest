"""Finite copied-world engineering continuation of an authentic inherited goal.

Neither a behavioral study nor a persistent pilot: no live state, API or model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .baseline import strict_json
from .inherited_origin import PROFILE
from .lifecycle_store import LifecycleSession
from .opportunity import propose


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(collection, ident: str):
    matches = [x for x in collection if type(x) is dict and x.get("id") == ident]
    if len(matches) != 1:
        raise AssertionError("inherited goal or plan identity became ambiguous: " + ident)
    return matches[0]


def run(root: Path, database: Path, snapshot: Path, journal: Path, cycles: int = 4) -> dict:
    root, database, snapshot, journal = map(lambda p: Path(p).resolve(), (root, database, snapshot, journal))
    if not 1 <= cycles <= 8 or database.exists() or database.is_relative_to(root):
        raise ValueError("new bounded isolated external copied database required")
    protected = {
        "source": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD:src"], text=True).strip(),
        "checkout_snapshot": digest(root / "state/organism.json"),
        "checkout_journal": digest(root / "state/journal.jsonl"),
        "inherited_snapshot": digest(snapshot),
        "inherited_journal": digest(journal),
    }
    with LifecycleSession.create(
            database, root, snapshot, journal, enabled=True, seed=5,
            cycle_limit=cycles, allow_ora2=True, timing_policy="manual",
            origin_profile=PROFILE) as session:
        initial = session.status()
        if (initial["completed_cycles"] != 0 or initial["cycle"] != 1803 or
                initial.get("origin_profile") != PROFILE):
            raise AssertionError("not the real inherited-goal initial cohort")
    events = []
    previous_owner = None
    for index in range(1, cycles + 1):
        with LifecycleSession(database, root) as session:
            agent, meta, old_origin, count, _, raw, _ = session._restore()
            if count != index - 1:
                raise AssertionError("durable copied event sequence differs")
            state = strict_json(raw)
            lab = state["planning_lab"]
            goal = one(lab["goals"], "PG000448")
            plan = one(lab["plans"], "PP000451")
            if (goal.get("target") != [0, 2] or plan.get("goal_id") != "PG000448" or
                    plan.get("goal") != [0, 2]):
                raise AssertionError("original inherited obligation changed identity")
            opportunity = propose(agent, state, previous_owner=previous_owner)
            commitment = any(lab.get(k) is not None for k in (
                "active_goal_id", "active_plan_id", "active_objective_realization_id"
            ))
            if commitment and opportunity["owner"] != "phase41":
                raise AssertionError("opportunity would interrupt genuine inherited commitment")
            request = "genuine-inherited-continuity-" + str(index)
            response = session.tick(request, enabled=True, owner=opportunity["owner"])
            if response["replayed"]:
                raise AssertionError("new copied request wrongly replayed")
            record = response["result"]
            if session.tick(request, enabled=True, owner=opportunity["owner"]) != {
                    "replayed": True, "result": record}:
                raise AssertionError("identical request changed durable state")
            if opportunity["owner"] == "ora2":
                if record.get("control", {}).get("choice") != opportunity["choice_record"]:
                    raise AssertionError("learner action not exactly attributed")
            elif record.get("control") is not None:
                raise AssertionError("planner result has false learner control")
            _, _, _, _, _, after_raw, _ = session._restore()
            finished = strict_json(after_raw)["planning_lab"]
            end_goal = one(finished["goals"], "PG000448")
            end_plan = one(finished["plans"], "PP000451")
            if end_goal.get("target") != [0, 2] or end_plan.get("goal_id") != "PG000448":
                raise AssertionError("original obligation changed after copied action")
            events.append({
                "cycle": record["cycle"], "owner": opportunity["owner"],
                "active_goal_before": lab.get("active_goal_id"),
                "active_plan_before": lab.get("active_plan_id"),
                "inherited_goal_status_after": end_goal.get("status"),
                "inherited_plan_status_after": end_plan.get("status"),
                "action_sha256": record["after_snapshot_sha256"],
            })
            previous_owner = opportunity["owner"]
        # Separate Python process rechecks all durable rows at every boundary.
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        env.pop("AGENTTEST_MODEL", None)
        restored = subprocess.run(
            [sys.executable, "-B", "-m", "ora2.lifecycle_store", "status",
             "--database", str(database), "--root", str(root)],
            cwd=root, env=env, capture_output=True, text=True, timeout=120, check=True,
        )
        if json.loads(restored.stdout)["completed_cycles"] != index:
            raise AssertionError("cold-process reconstruction failed")
    latest = {
        "source": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD:src"], text=True).strip(),
        "checkout_snapshot": digest(root / "state/organism.json"),
        "checkout_journal": digest(root / "state/journal.jsonl"),
        "inherited_snapshot": digest(snapshot),
        "inherited_journal": digest(journal),
    }
    if latest != protected:
        raise AssertionError("original and/or copied inputs mutated during verification")
    return {
        "status": "FINITE_COPIED_LIFECYCLE_ENGINEERING_ONLY",
        "profile": PROFILE,
        "cycles": cycles,
        "initial_goal": "PG000448",
        "initial_plan": "PP000451",
        "events": events,
        "live_original_ora_actions": 0,
        "study002_registered": False,
        "benefit_gate": "NOT_EVALUATED",
        "persistent_pilot_enabled": False,
        "protected_hashes": protected,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--cycles", type=int, default=4)
    args = p.parse_args()
    result = run(args.root, args.database, args.snapshot, args.journal, cycles=args.cycles)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
