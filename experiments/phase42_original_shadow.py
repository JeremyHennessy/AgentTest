"""Ora original: prospective prediction receipts from immutable live history.

This is a read-only STUDY. It observes the natural original-world action,
never chooses, instructs, changes, or initiates the action. The private
admission adapter validates native source physics; the learner only receives
its own earlier public before/action/after observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from agenttest.action_lab import ACTION_ORDER, STATEFUL_WORLD_VERSION
from agenttest.two_clock_stream import TwoClockStream, VERSION, brier, digest, _json
from phase42_transition_memory_study import extract_verified_native

STUDY = "phase42-original-prospective-shadow-v1"
SOURCE_REPO = "JeremyHennessy/AgentTest"
SOURCE_BRANCH = "autonomous/growth"
ARMS = ("two_clock", "lifetime", "action", "uniform")
HEXSHA = re.compile(r"[0-9a-f]{40}\Z")
HEX256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_RAW_SOURCE = 128 * 1024 * 1024
MAX_PREVIOUS_ARTIFACT = 128 * 1024


def _source(raw: bytes, commit: str, blob: str, sha256: str) -> dict[str, Any]:
    if (not isinstance(raw, bytes) or len(raw) > MAX_RAW_SOURCE
            or not all(isinstance(value, str) and HEXSHA.fullmatch(value)
                       for value in (commit, blob))
            or not isinstance(sha256, str) or not HEX256.fullmatch(sha256)):
        raise ValueError("invalid pinned original source identifiers or size")
    actual = hashlib.sha256(raw).hexdigest()
    actual_blob = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
    ).hexdigest()
    if sha256 != actual or blob != actual_blob:
        raise ValueError("exact original source bytes fail both git and sha256 provenance")
    return {
        "repository": SOURCE_REPO, "branch": SOURCE_BRANCH,
        "commit": commit, "git_blob": blob, "raw_sha256": actual,
        "raw_bytes": len(raw),
    }


def _bounded_position(value: Any) -> list[int]:
    if (not isinstance(value, list) or len(value) != 2
            or any(type(x) is not int or x < -2 or x > 2 for x in value)):
        raise ValueError("invalid original live current 5x5 position")
    return list(value)


def _adapt_verified(rows: list[dict]) -> list[dict]:
    return [{
        key: item[key] for key in ("id", "index", "before", "after", "action")
    } for item in rows]


def _unpack_previous(previous: dict[str, Any] | None) -> dict[str, Any] | None:
    if previous is None:
        return None
    if (not isinstance(previous, dict)
            or set(previous) != {"protocol", "frozen", "prospective",
                                "summary", "source_not_modified"}):
        raise ValueError("invalid previous signed observational report envelope")
    if previous["protocol"] != STUDY or previous["source_not_modified"] is not True:
        raise ValueError("wrong prior source experiment or writer authority")
    data = previous["frozen"]
    if not isinstance(data, dict) or set(data) != {"body", "sha256"}:
        raise ValueError("missing previously frozen evidence receipt")
    body = data["body"]
    if not isinstance(body, dict) or data["sha256"] != digest(body):
        raise ValueError("prior forecast capsule integrity hash mismatch")
    required = {
        "version", "original_source", "cycle", "world_version", "public_position",
        "total_native_rows", "original_history_prefix_sha256",
        "compatible_native_rows", "compatible_history_prefix_sha256",
        "last_compatible_id", "model_full_evidence_sha256", "forecasts",
        "original_active_commitment", "original_last_action_cycle",
        "study_owns_action",
    }
    if set(body) != required or body["version"] != VERSION:
        raise ValueError("different frozen memory/receipt schema")
    orig = body["original_source"]
    if (not isinstance(orig, dict) or orig.get("repository") != SOURCE_REPO
            or orig.get("branch") != SOURCE_BRANCH
            or not all(HEXSHA.fullmatch(str(orig.get(k) or ""))
                       for k in ("commit", "git_blob"))
            or not HEX256.fullmatch(str(orig.get("raw_sha256") or ""))):
        raise ValueError("prior source branch/commit not authenticated")
    if (type(body["cycle"]) is not int or body["cycle"] < 0
            or body["world_version"] != STATEFUL_WORLD_VERSION
            or type(body["total_native_rows"]) is not int
            or type(body["compatible_native_rows"]) is not int
            or body["total_native_rows"] < body["compatible_native_rows"] > 0
            or body["total_native_rows"] < 0):
        raise ValueError("invalid old observation count/world binding")
    _bounded_position(body["public_position"])
    if set(body["forecasts"]) != set(ACTION_ORDER):
        raise ValueError("missing frozen public command")
    for action in ACTION_ORDER:
        if set(body["forecasts"][action]) != set(ARMS):
            raise ValueError("missing precommitted comparison arms")
        for arm in ARMS:
            forecast = body["forecasts"][action][arm]
            if not isinstance(forecast, dict) or forecast.get("action") != action:
                raise ValueError("prior prediction bound to another action")
            if forecast.get("before") != body["public_position"]:
                raise ValueError("prediction position changed after freeze")
            # Also validates grammar and probability normalization.
            brier(forecast, "0,0")
    summary = previous["summary"]
    if not isinstance(summary, dict) or set(summary) != {
        "scored_natural_first_actions", "by_arm_brier_sum",
        "by_arm_logloss_sum", "inconclusive_intervals",
    }:
        raise ValueError("invalid prior prospective evidence ledger")
    if (type(summary["scored_natural_first_actions"]) is not int
            or type(summary["inconclusive_intervals"]) is not int
            or min(summary["scored_natural_first_actions"],
                   summary["inconclusive_intervals"]) < 0
            or set(summary["by_arm_brier_sum"]) != set(ARMS)
            or set(summary["by_arm_logloss_sum"]) != set(ARMS)):
        raise ValueError("prior score ancestry invalid")
    return body


def _score_prior(
    previous: dict | None, *,
    source: dict, cycle: int,
    native: list[dict], compatible: list[dict],
) -> dict[str, Any]:
    old = _unpack_previous(previous)
    if old is None:
        return {"status": "no_previous_receipt", "credit": False}
    if source["commit"] == old["original_source"]["commit"]:
        return {"status": "identical_snapshot", "credit": False}
    if cycle < old["cycle"]:
        raise ValueError("original cycles regressed across shadow observations")
    old_total = old["total_native_rows"]
    old_eligible = old["compatible_native_rows"]
    if len(native) < old_total or len(compatible) < old_eligible:
        raise ValueError("original native history truncated after prior frozen forecast")
    if (digest(native[:old_total]) != old["original_history_prefix_sha256"]
            or digest(compatible[:old_eligible])
            != old["compatible_history_prefix_sha256"]):
        raise ValueError("changed old native evidence; cannot credit any new outcome")
    if len(native) == old_total:
        return {"status": "no_new_native_event", "credit": False}
    first = native[old_total]
    if (not isinstance(first, dict)
            or first.get("world_version") != old["world_version"]):
        return {"status": "other_world_first", "credit": False}
    if first.get("before") != old["public_position"]:
        return {
            "status": "unexpected_first_context",
            "credit": False,
            "expected_position": old["public_position"],
            "actual_position": first.get("before"),
        }
    action = first.get("action")
    if action not in ACTION_ORDER:
        return {"status": "unknown_natural_first_action", "credit": False}
    if len(compatible) <= old_eligible:
        raise ValueError("compatible first action absent from validated native series")
    actual = compatible[old_eligible]
    if (actual["id"] != first.get("source_id") or actual["action"] != action
            or actual["before"] != old["public_position"]
            or actual["after"] != first.get("after")):
        raise ValueError("first scored natural action has a broken native source link")
    physical_delta = (
        f"{actual['after'][0] - actual['before'][0]},"
        f"{actual['after'][1] - actual['before'][1]}"
    )
    scores = {
        arm: brier(old["forecasts"][action][arm], physical_delta)
        for arm in ARMS
    }
    return {
        "status": "scored_one_natural_first_action", "credit": True,
        "prior_source_commit": old["original_source"]["commit"],
        "new_source_commit": source["commit"],
        "prior_cycle": old["cycle"], "current_cycle": cycle,
        "old_compatible_count": old_eligible,
        "old_native_count": old_total,
        "native_source_id": actual["id"],
        "public_before": old["public_position"],
        "naturally_chosen_action": action,
        "actual_public_delta": physical_delta,
        "preaction_scores": scores,
        "prior_active_commitment": old["original_active_commitment"],
        "prediction_not_action_selection": True,
        "later_natural_events_not_scored": max(0, len(native) - old_total - 1),
    }


def _summary(previous: dict | None, result: dict) -> dict:
    if previous is None:
        previous_summary = {
            "scored_natural_first_actions": 0,
            "inconclusive_intervals": 0,
            "by_arm_brier_sum": {key: 0.0 for key in ARMS},
            "by_arm_logloss_sum": {key: 0.0 for key in ARMS},
        }
    else:
        previous_summary = previous["summary"]
    total = {
        "scored_natural_first_actions": previous_summary["scored_natural_first_actions"],
        "inconclusive_intervals": previous_summary["inconclusive_intervals"],
        "by_arm_brier_sum": dict(previous_summary["by_arm_brier_sum"]),
        "by_arm_logloss_sum": dict(previous_summary["by_arm_logloss_sum"]),
    }
    if result["credit"]:
        total["scored_natural_first_actions"] += 1
        for arm, value in result["preaction_scores"].items():
            total["by_arm_brier_sum"][arm] += value["brier"]
            total["by_arm_logloss_sum"][arm] += value["logloss"]
    else:
        total["inconclusive_intervals"] += 1
    return total


def inspect(
    raw: bytes, *,
    original_commit: str, original_blob: str, expected_sha256: str,
    previous_report: dict | None = None,
) -> dict[str, Any]:
    source = _source(raw, original_commit, original_blob, expected_sha256)
    try:
        full_state = json.loads(raw)
    except (TypeError, UnicodeError, ValueError) as exc:
        raise ValueError("unreadable authentic original state") from exc
    verified = extract_verified_native(full_state)
    lab = full_state["planning_lab"]
    cycle = full_state.get("cycles")
    if (type(cycle) is not int or cycle < 0
            or type(lab.get("last_action_cycle")) not in (int, type(None))
            or (type(lab.get("last_action_cycle")) is int
                and lab["last_action_cycle"] > cycle)):
        raise ValueError("invalid original cycle/last-action provenance")
    position = _bounded_position(lab.get("position"))
    all_native = lab["transition_observations"]
    compatible = verified["rows"]
    if len(compatible) < 80:
        raise ValueError("insufficient independently validated original evidence")
    memory = TwoClockStream(_adapt_verified(compatible))
    frozen_memory = memory.capsule()
    restored = TwoClockStream.from_capsule(frozen_memory)
    if frozen_memory != restored.capsule():
        raise ValueError("full-history cold-replay bytes changed")
    forecasts = {
        action: {
            arm: memory.predict(position, action, arm=arm)
            for arm in ARMS
        }
        for action in ACTION_ORDER
    }
    if any(
        restored.predict(position, action, arm=arm) != forecasts[action][arm]
        for action in ACTION_ORDER for arm in ARMS
    ):
        raise ValueError("cold-reload predictions differ from full live evidence")
    if len(memory.events) != verified["compatible_count"]:
        raise ValueError("silent alteration of inherited historical evidence")
    source_position = list(position)
    pending = any(lab.get(k) is not None for k in (
        "active_goal_id", "active_plan_id", "active_objective_realization_id",
    ))
    body = {
        "version": VERSION,
        "original_source": source,
        "cycle": cycle, "world_version": STATEFUL_WORLD_VERSION,
        "public_position": source_position,
        "total_native_rows": len(all_native),
        "original_history_prefix_sha256": digest(all_native),
        "compatible_native_rows": len(compatible),
        "compatible_history_prefix_sha256": digest(compatible),
        "last_compatible_id": compatible[-1]["id"],
        "model_full_evidence_sha256": hashlib.sha256(frozen_memory).hexdigest(),
        "forecasts": forecasts,
        "original_active_commitment": pending,
        "original_last_action_cycle": lab.get("last_action_cycle"),
        "study_owns_action": False,
    }
    prospective = _score_prior(
        previous_report, source=source, cycle=cycle,
        native=all_native, compatible=compatible,
    )
    result = {
        "protocol": STUDY,
        "frozen": {"body": body, "sha256": digest(body)},
        "prospective": prospective,
        "summary": _summary(previous_report, prospective),
        "source_not_modified": True,
    }
    if len(_json(result)) > MAX_PREVIOUS_ARTIFACT:
        raise ValueError("future shadow artifact exceeds source-safe limit")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--original-commit", required=True)
    parser.add_argument("--original-blob", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original, output = args.state.resolve(), args.output.resolve()
    if (args.state.is_symlink() or not original.is_file()
            or original == output or not output.parent.is_dir()):
        raise ValueError("must use a separate original file and scratch output")
    old = args.previous
    prior = None
    if old is not None:
        if not old.is_file() or old.is_symlink() or old.resolve() == original:
            raise ValueError("invalid prior source-linked shadow file")
        if old.stat().st_size > MAX_PREVIOUS_ARTIFACT:
            raise ValueError("prior report is over the bounded experimental limit")
        prior = json.loads(old.read_bytes())
    raw = original.read_bytes()
    report = inspect(
        raw, original_commit=args.original_commit,
        original_blob=args.original_blob,
        expected_sha256=args.expected_sha256, previous_report=prior,
    )
    if original.read_bytes() != raw:
        raise ValueError("original full-state source changed during read-only study")
    output.write_bytes(json.dumps(report, sort_keys=True, indent=2,
                                  allow_nan=False).encode("utf-8") + b"\n")
    # Never print full history; experimental read-only public summary only.
    print(json.dumps({
        "source_cycle": report["frozen"]["body"]["cycle"],
        "source_commit": report["frozen"]["body"]["original_source"]["commit"],
        "inherited_compatible": report["frozen"]["body"]["compatible_native_rows"],
        "total_native": report["frozen"]["body"]["total_native_rows"],
        "active_commitment": report["frozen"]["body"]["original_active_commitment"],
        "source_integrity": True,
        "cold_full_history": True,
        "prior": report["prospective"]["status"],
        "cumulative_scored_events": report["summary"]["scored_natural_first_actions"],
        "original_world_writes": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
