"""Standalone, default-off AgentTest Phase 42 owned-action research lane.

World authority stays in this bounded driver, never in the adaptive policy.
It does not read or write the original organism, heartbeat, agenda or Observer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterator

from agenttest import causal_investigator as policy
from open_object_world_challenge import initial_world, observe_world, transition
from open_object_world_challenge_explorer import candidate_commands

VERSION = "phase42-evidence-owned-capsule-v1"
MAX_STEPS = 64
MAX_BYTES = 16 * 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]{1,96}\Z")
ORIGINAL_STATE = Path(__file__).resolve().parents[1] / "state"


def _bytes(value: Any) -> bytes:
    return (json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ) + "\n").encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _sources() -> dict[str, str]:
    from open_object_world_challenge import __file__ as world_file
    from open_object_world_challenge_explorer import __file__ as menu_file
    return {
        "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy": hashlib.sha256(Path(policy.__file__).read_bytes()).hexdigest(),
        "world": hashlib.sha256(Path(world_file).read_bytes()).hexdigest(),
        "menu": hashlib.sha256(Path(menu_file).read_bytes()).hexdigest(),
    }


def _path(raw: str | Path) -> Path:
    path = Path(raw).absolute()
    if path.suffix != ".json":
        raise ValueError("research capsule must use a .json filename")
    if path.resolve().is_relative_to(ORIGINAL_STATE.resolve()):
        raise ValueError("original Ora state storage is immutable to this lane")
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("symlink research capsule rejected")
    return path


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    # Deliberately refuse stale locks rather than trying to rescue authority.
    # All automated experiments run in unique, temporary directories.
    lock = path.with_suffix(".lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("research capsule already has an owner") from exc
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.fsync(fd)
        os.close(fd)
        fd = -1
        yield
    finally:
        if fd >= 0:
            os.close(fd)
        lock.unlink(missing_ok=True)


def _persist(path: Path, content: dict) -> None:
    value = deepcopy(content)
    value.pop("digest", None)
    value["digest"] = _sha(value)
    raw = _bytes(value)
    if len(raw) > MAX_BYTES:
        raise ValueError("capsule size limit reached without truncation")
    descriptor, temporary = tempfile.mkstemp(prefix=".ora-owned-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as dst:
            dst.write(raw)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("capsule missing or not a regular file")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("capsule exceeds size limit")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("invalid capsule type")
    checksum = value.get("digest")
    remainder = {key: val for key, val in value.items() if key != "digest"}
    if checksum != _sha(remainder):
        raise ValueError("capsule checksum mismatch")
    return value


def _audit(capsule: dict) -> None:
    if capsule.get("version") != VERSION:
        raise ValueError("unsupported capsule version")
    if capsule.get("source_hashes") != _sources():
        raise ValueError("world/policy source changed: independent review required")
    events = capsule.get("events")
    seed = capsule.get("seed")
    if (type(seed) is not int or not 1 <= seed <= 4
            or not isinstance(events, list) or len(events) > MAX_STEPS
            or capsule.get("revision") != len(events)):
        raise ValueError("invalid capsule identity or counters")
    world = initial_world(seed)
    prior: list[dict] = []
    seen_requests = set()
    previous = "genesis"
    for index, record in enumerate(events, 1):
        if not isinstance(record, dict):
            raise ValueError("invalid historical event")
        request_id = record.get("request_id")
        if (not isinstance(request_id, str) or not IDENTIFIER.fullmatch(request_id)
                or request_id in seen_requests):
            raise ValueError("duplicate or invalid request")
        seen_requests.add(request_id)
        before = observe_world(world)
        if record.get("public_before") != before:
            raise ValueError("public observation chain mismatch")
        expected = policy.select_investigation(before, prior, candidate_commands(before))
        if record.get("selection") != expected or record.get("command") != expected["command"]:
            raise ValueError("non-owned action or rewritten pre-action forecast")
        null = policy.select_investigation(before, [], candidate_commands(before))
        if record.get("memory_ablated_command") != null["command"]:
            raise ValueError("invalid ablation diagnostic")
        world, receipt = transition(world, expected["command"], cycle=index)
        after = observe_world(world)
        if record.get("receipt") != receipt or record.get("public_after") != after:
            raise ValueError("world/outcome chain mismatch")
        kind = policy.classify_outcome(before, after, receipt)
        if record.get("outcome_kind") != kind:
            raise ValueError("outcome classification mismatch")
        if record.get("id") != f"INV{index:06d}":
            raise ValueError("non-monotonic inquiry identity")
        row = {key: val for key, val in record.items() if key != "event_hash"}
        if record.get("event_hash") != _sha({"parent": previous, "record": row}):
            raise ValueError("historical chain digest mismatch")
        previous = record["event_hash"]
        prior.append(record)
    if capsule.get("world") != world or capsule.get("public") != observe_world(world):
        raise ValueError("world replay or present observation mismatch")
    if capsule.get("last_event_hash") != previous:
        raise ValueError("last event digest mismatch")


def create(raw_path: str | Path, seed: int) -> dict:
    path = _path(raw_path)
    if type(seed) is not int or not 1 <= seed <= 4:
        raise ValueError("seed must identify one of four existing mirrored layouts")
    if not path.parent.is_dir():
        raise ValueError("research directory must already exist")
    with _locked(path):
        if path.exists():
            raise FileExistsError("refusing to replace existing investigation")
        world = initial_world(seed)
        capsule = {
            "version": VERSION,
            "seed": seed,
            "source_hashes": _sources(),
            "revision": 0,
            "world": world,
            "public": observe_world(world),
            "events": [],
            "last_event_hash": "genesis",
        }
        _persist(path, capsule)
        return inspect(path)


def inspect(raw_path: str | Path) -> dict:
    path = _path(raw_path)
    capsule = _read(path)
    _audit(capsule)
    return {
        "version": capsule["version"],
        "seed": capsule["seed"],
        "revision": capsule["revision"],
        "digest": capsule["digest"],
        "public": deepcopy(capsule["public"]),
        "summary": policy.summarize(capsule["events"]),
    }


def step(raw_path: str | Path, *, request_id: str, expected_revision: int) -> dict:
    path = _path(raw_path)
    if not isinstance(request_id, str) or not IDENTIFIER.fullmatch(request_id):
        raise ValueError("invalid idempotent action request")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("invalid expected revision")
    with _locked(path):
        capsule = _read(path)
        _audit(capsule)
        # Completed requests are returned without re-executing even when another
        # request has since advanced the stream. Stale *new* requests fail CAS.
        for prior in capsule["events"]:
            if prior["request_id"] == request_id:
                return {"status": "already_committed", "record": deepcopy(prior),
                        "revision": capsule["revision"]}
        if capsule["revision"] != expected_revision:
            raise ValueError("stale attempt: no action performed")
        if capsule["revision"] >= MAX_STEPS:
            raise ValueError("bounded research action budget exhausted")
        before = observe_world(capsule["world"])
        menu = candidate_commands(before)
        selection = policy.select_investigation(before, capsule["events"], menu)
        if selection["command"] not in menu:
            raise RuntimeError("candidate not in observed public command menu")
        memory_ablated = policy.select_investigation(before, [], menu)["command"]
        next_world, receipt = transition(
            capsule["world"], selection["command"], cycle=capsule["revision"] + 1,
        )
        after = observe_world(next_world)
        kind = policy.classify_outcome(before, after, receipt)
        record = {
            "id": selection["owner_id"],
            "request_id": request_id,
            "public_before": before,
            "selection": selection,
            "memory_ablated_command": memory_ablated,
            "command": deepcopy(selection["command"]),
            "receipt": receipt,
            "outcome_kind": kind,
            "public_after": after,
        }
        record["event_hash"] = _sha({
            "parent": capsule["last_event_hash"], "record": record,
        })
        updated = deepcopy(capsule)
        updated["events"].append(record)
        updated["revision"] += 1
        updated["world"] = next_world
        updated["public"] = after
        updated["last_event_hash"] = record["event_hash"]
        _audit(updated)
        _persist(path, updated)
        return {"status": "committed", "record": record, "revision": updated["revision"]}


def study(steps: int = 32) -> dict:
    if type(steps) is not int or not 1 <= steps <= MAX_STEPS:
        raise ValueError("invalid bounded study horizon")
    rows = []
    with tempfile.TemporaryDirectory() as root:
        for seed in range(1, 5):
            path = Path(root) / f"seed-{seed}.json"
            create(path, seed)
            for index in range(steps):
                result = step(path, request_id=f"S{seed}-R{index + 1}", expected_revision=index)
                if result["status"] != "committed":
                    raise AssertionError("study step not committed")
            row = inspect(path)
            # Whole-trace verification runs again from the captured policy/world
            # source and all recorded historical public frames.
            capsule = _read(path)
            summary = row["summary"]
            choices = sum(
                e["command"] != e["memory_ablated_command"]
                for e in capsule["events"]
            )
            # One-step *evaluation only*: compare actual and memory-masked
            # commands from the exact same prior world. The mask's outcome is
            # never returned to the investigator, stored in its capsule, or
            # used to choose a subsequent action.
            replay_world = initial_world(seed)
            actual_public_changes = 0
            ablated_public_changes = 0
            actual_blocked = 0
            ablated_blocked = 0
            memory_better_changes = 0
            ablation_better_changes = 0
            for index, event in enumerate(capsule["events"], 1):
                counter_world, counter_receipt = transition(
                    replay_world, event["memory_ablated_command"], cycle=index,
                )
                counter_public = observe_world(counter_world)
                before_public = policy.project_public(event["public_before"])
                actual_change = (
                    policy.project_public(event["public_after"]) != before_public
                )
                counter_change = (
                    policy.project_public(counter_public) != before_public
                )
                actual_public_changes += int(actual_change)
                ablated_public_changes += int(counter_change)
                actual_blocked += int(event["outcome_kind"] == "blocked")
                ablated_blocked += int(
                    policy.classify_outcome(
                        event["public_before"], counter_public, counter_receipt,
                    ) == "blocked"
                )
                if event["command"] != event["memory_ablated_command"]:
                    memory_better_changes += int(actual_change and not counter_change)
                    ablation_better_changes += int(counter_change and not actual_change)
                replay_world, _ = transition(
                    replay_world, event["command"], cycle=index,
                )
                if observe_world(replay_world) != event["public_after"]:
                    raise AssertionError("one-step comparison lost exact world history")
            family_samples = [
                e["selection"]["forecast"]["family_samples"]
                for e in capsule["events"]
            ]
            local_samples = [
                e["selection"]["forecast"]["local_samples"]
                for e in capsule["events"]
            ]
            global_scores = []
            earlier_outcomes = Counter()
            for index, item in enumerate(capsule["events"]):
                # An independent, constant-form predictor that ignores action,
                # context, and selection; it uses only earlier class frequencies.
                baseline = {
                    outcome: (earlier_outcomes[outcome] + 0.5) /
                             (index + 0.5 * len(policy.OUTCOMES))
                    for outcome in policy.OUTCOMES
                }
                global_scores.append(policy.brier(baseline, item["outcome_kind"]))
                earlier_outcomes[item["outcome_kind"]] += 1
            mean_global = sum(global_scores) / len(global_scores)
            rows.append({
                "seed": seed,
                "events": summary["events"],
                "mean_prequential_brier": summary["mean_prequential_brier"],
                "global_prior_brier": round(mean_global, 8),
                "beats_global_prior": summary["mean_prequential_brier"] < mean_global,
                "uniform_brier": summary["uniform_brier"],
                "forecast_improves_on_uniform": summary["forecast_improves_on_uniform"],
                "memory_changes_choice_count": choices,
                "actual_public_changes": actual_public_changes,
                "ablated_public_changes": ablated_public_changes,
                "actual_blocked": actual_blocked,
                "ablated_blocked": ablated_blocked,
                "memory_only_public_change_advantages": memory_better_changes,
                "ablation_only_public_change_advantages": ablation_better_changes,
                "decisions_with_family_evidence": sum(n > 0 for n in family_samples),
                "decisions_with_local_evidence": sum(n > 0 for n in local_samples),
                "cross_context_followups": sum(
                    e["selection"]["inquiry_mode"] == "test_cross_context_prediction"
                    for e in capsule["events"]
                ),
                "family_sample_counts": family_samples,
                "local_sample_counts": local_samples,
                "outcomes": summary["outcomes"],
                "unique_public_contexts": summary["unique_public_contexts"],
                "validated_capsule_digest": row["digest"],
            })
    return {
        "study": "agenttest-evidence-owned-phase42-exploratory-v1",
        "worlds": 4,
        "actions_per_world": steps,
        "status": "exploratory_not_preregistered_scientific_test",
        "rows": rows,
        "limitations": [
            "Four deterministic mirrored layouts are not independent organisms.",
            "Repeated checks of a fixed authored world are software/mechanism evidence only.",
            "Uniform and pooled-global-history forecasts are simple controls; any advantage is not task benefit.",
            "One-step memory ablation measures public change and blocked actions from identical starting worlds; it does not isolate long-term task utility.",
            "No long-term learning, new world, organism, self-maintenance, consciousness, or live activation is claimed.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init_cmd = sub.add_parser("init")
    init_cmd.add_argument("--capsule", required=True)
    init_cmd.add_argument("--seed", type=int, choices=(1, 2, 3, 4), required=True)
    action_cmd = sub.add_parser("step")
    action_cmd.add_argument("--capsule", required=True)
    action_cmd.add_argument("--request-id", required=True)
    action_cmd.add_argument("--expected-revision", type=int, required=True)
    info_cmd = sub.add_parser("inspect")
    info_cmd.add_argument("--capsule", required=True)
    pilot_cmd = sub.add_parser("study")
    pilot_cmd.add_argument("--steps", type=int, default=32)
    args = parser.parse_args()
    if args.command == "init":
        result = create(args.capsule, args.seed)
    elif args.command == "step":
        result = step(args.capsule, request_id=args.request_id, expected_revision=args.expected_revision)
    elif args.command == "inspect":
        result = inspect(args.capsule)
    else:
        result = study(args.steps)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
