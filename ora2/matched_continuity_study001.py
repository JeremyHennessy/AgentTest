"""Registered matched continuity on authentic inherited goal, copied only.

One finite 4-seed × 2-arm × 4-cycle comparison. No live original Ora actions,
new world, model API, persistent scheduler, or unbounded experiment extension.
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

VERSION = "ora2-matched-inherited-continuity-study001-v1"
PROTOCOL_BLOB = None  # Set to the frozen protocol Git blob before execution.
SEEDS = (0, 1, 2, 3)
ARMS = ("control", "candidate")
CYCLES = 4
SNAPSHOT_SHA = "f37c788cee851622823a848a7e3b8b32f67c06bec4b94eb5b709922e7a7aa6ec"
JOURNAL_SHA = "717b7380101ff7656b13cc5d9f8ac14ade862a6bdd1b9363ad3029d29d8e35e9"
SOURCE_TREE = "9b0f880af84a0b1b69fd6aa9009ab738acd7dfad"


class InvalidStudy(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def one(items, identity):
    matches = [x for x in items if type(x) is dict and x.get("id") == identity]
    if len(matches) != 1:
        raise InvalidStudy("missing or ambiguous authentic inherited record")
    return matches[0]


def inspect(state):
    lab = state["planning_lab"]
    goal, plan = one(lab["goals"], "PG000448"), one(lab["plans"], "PP000451")
    if goal.get("target") != [0, 2] or plan.get("goal_id") != "PG000448" or plan.get("goal") != [0, 2]:
        raise InvalidStudy("inherited goal or plan identity mutated")
    return {
        "cycle": state["cycles"], "goal_status": goal.get("status"),
        "plan_status": plan.get("status"), "active_goal": lab.get("active_goal_id"),
        "active_plan": lab.get("active_plan_id"),
        "active_precommit": lab.get("active_objective_realization_id"),
    }


def protected(root, snapshot, journal):
    return {
        "source_tree": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD:src"], text=True).strip(),
        "checkout_snapshot": digest(root / "state/organism.json"),
        "checkout_journal": digest(root / "state/journal.jsonl"),
        "origin_snapshot": digest(snapshot), "origin_journal": digest(journal),
    }


def run_arm(root, snapshot, journal, db, seed, arm):
    with LifecycleSession.create(
            db, root, snapshot, journal, enabled=True, seed=seed, cycle_limit=CYCLES,
            allow_ora2=True, timing_policy="manual", origin_profile=PROFILE) as session:
        status = session.status()
        if status["cycle"] != 1803 or status["completed_cycles"] != 0 or status["origin_profile"] != PROFILE:
            raise InvalidStudy("not authentic inherited start")
    events = []
    previous_owner = None
    for step in range(1, CYCLES + 1):
        with LifecycleSession(db, root) as session:
            agent, meta, origin, count, previous, raw, logical = session._restore()
            if count != step - 1:
                raise InvalidStudy("unexpected copied-cycle sequence")
            before = inspect(strict_json(raw))
            if step == 1 and (before["active_goal"] != "PG000448" or
                              before["active_plan"] != "PP000451"):
                raise InvalidStudy("nonempty inherited active cohort absent")
            if arm == "candidate":
                proposal = propose(agent, strict_json(raw), previous_owner=previous_owner)
                owner = proposal["owner"]
            else:
                proposal, owner = None, "phase41"
            if any(before[key] is not None for key in ("active_goal", "active_plan", "active_precommit")) and owner != "phase41":
                raise InvalidStudy("interrupted inherited commitment")
            request = f"matched-continuity-{seed}-{arm}-{step}"
            outcome = session.tick(request, enabled=True, owner=owner)
            if outcome["replayed"]:
                raise InvalidStudy("new action was replayed")
            record = outcome["result"]
            if session.tick(request, enabled=True, owner=owner) != {"replayed": True, "result": record}:
                raise InvalidStudy("same request failed idempotent replay")
            if owner == "ora2":
                if record.get("control", {}).get("choice") != proposal["choice_record"]:
                    raise InvalidStudy("learner-owned command attribution mismatch")
            elif record.get("control") is not None:
                raise InvalidStudy("planner-owned action falsely attributed to learner")
            after = inspect(strict_json(session._restore()[5]))
            if after["cycle"] != 1803 + step:
                raise InvalidStudy("wrong copied lifecycle advancement")
            events.append({
                "cycle": after["cycle"], "owner": owner,
                "before": before, "after": after,
                "before_snapshot_sha256": record["before_snapshot_sha256"],
                "after_snapshot_sha256": record["after_snapshot_sha256"],
                "journal_suffix_sha256": hashlib.sha256(record["journal_suffix"].encode()).hexdigest(),
                "proposal": proposal,
            })
            previous_owner = owner
        # Cold independent process must verify the complete saved ledger.
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        env.pop("AGENTTEST_MODEL", None)
        check = subprocess.run(
            [sys.executable, "-B", "-m", "ora2.lifecycle_store", "status",
             "--database", str(db), "--root", str(root)],
            cwd=root, env=env, capture_output=True, text=True, timeout=120, check=True)
        if json.loads(check.stdout)["completed_cycles"] != step:
            raise InvalidStudy("cold process reconstruction failed")
    completion = next((event["cycle"] for event in events
                       if event["after"]["goal_status"] == "completed"), None)
    learner_cycles = [event["cycle"] for event in events if event["owner"] == "ora2"]
    if any(cycle <= completion for cycle in learner_cycles) if completion is not None else bool(learner_cycles):
        raise InvalidStudy("learner action preceded inherited completion")
    return {"seed": seed, "arm": arm, "initial": events[0]["before"],
            "completion_cycle": completion, "learner_cycles": learner_cycles,
            "events": events, "final_status": after}


def run(root, snapshot, journal, database_dir):
    root, snapshot, journal, database_dir = map(
        lambda p: Path(p).resolve(), (root, snapshot, journal, database_dir))
    if not database_dir.is_dir() or database_dir.is_relative_to(root):
        raise InvalidStudy("external independent database directory required")
    initial = protected(root, snapshot, journal)
    if (initial["source_tree"] != SOURCE_TREE or initial["origin_snapshot"] != SNAPSHOT_SHA or
            initial["origin_journal"] != JOURNAL_SHA):
        raise InvalidStudy("frozen authentic source mismatch")
    if PROTOCOL_BLOB is None:
        raise InvalidStudy("unregistered protocol blob: cannot execute")
    actual_blob = subprocess.check_output(["git", "-C", str(root), "hash-object",
                                           "docs/ORA2_MATCHED_INHERITED_CONTINUITY_STUDY001.md"],
                                          text=True).strip()
    if actual_blob != PROTOCOL_BLOB:
        raise InvalidStudy("protocol was changed")
    arms = []
    for seed in SEEDS:
        for arm in ARMS:
            db = database_dir / f"matched-{seed}-{arm}.sqlite"
            if db.exists():
                raise InvalidStudy("study databases must be new and independent")
            arms.append(run_arm(root, snapshot, journal, db, seed, arm))
    if protected(root, snapshot, journal) != initial:
        raise InvalidStudy("original or historical source was modified")
    pairs = []
    for seed in SEEDS:
        control = next(a for a in arms if a["seed"] == seed and a["arm"] == "control")
        candidate = next(a for a in arms if a["seed"] == seed and a["arm"] == "candidate")
        pass_pair = (control["completion_cycle"] is not None and
                     candidate["completion_cycle"] is not None and
                     candidate["completion_cycle"] <= control["completion_cycle"] and
                     bool(candidate["learner_cycles"]) and
                     all(any(e["owner"] == "phase41" and e["cycle"] > cycle
                             for e in candidate["events"])
                         for cycle in candidate["learner_cycles"]))
        pairs.append({"seed": seed, "pass": pass_pair,
                      "control_completion": control["completion_cycle"],
                      "candidate_completion": candidate["completion_cycle"],
                      "candidate_learner_cycles": candidate["learner_cycles"]})
    return {
        "version": VERSION, "status": "VALID_CONTINUITY_POSITIVE" if all(p["pass"] for p in pairs)
        else "VALID_CONTINUITY_NEGATIVE",
        "protocol_blob": PROTOCOL_BLOB, "source_sha256": digest(Path(__file__)),
        "origin_sha256": {"snapshot": SNAPSHOT_SHA, "journal": JOURNAL_SHA},
        "pairs": pairs, "arms": arms, "copied_cycles": 32,
        "original_live_ora_actions": 0, "persistent_pilot_enabled": False,
        "limitations": "Matched copied-world inherited-goal preservation, not autonomous learning benefit.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--enable-registered-study", action="store_true")
    args = parser.parse_args()
    if not args.enable_registered_study or args.report.exists():
        raise SystemExit("explicit new finite study enablement and report required")
    result = run(args.root, args.snapshot, args.journal, args.database_dir)
    args.report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("version", "status", "pairs", "copied_cycles")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
