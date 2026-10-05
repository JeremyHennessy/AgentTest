"""Read-only archive eligibility diagnostic on copied AgentTest state.

This diagnostic never enables retention. It protects explicit references, raw
consumer dependencies and a hot suffix, then removes only the oldest remaining
episodes from a disposable copy and compares ordinary behavior with an intact
copy. The removed records are packaged as an external diagnostic artifact.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

EPISODE_ID = re.compile(r"E[0-9]+\Z")
PRODUCTION_BASE = "e3672c473723159232ab494a108eeca7d1903842"
PINNED_STATE = "906d216b54d76e3cb57c540cf59fd57004f29bf3"
DEFAULT_HOT_SUFFIX = 1024
DEFAULT_REMOVE_COUNT = 1000
DEFAULT_STEPS = 5


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _walk_external_episode_refs(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if path == () and key == "episodes":
                continue
            rows.extend(
                _walk_external_episode_refs(
                    item,
                    path=(*path, str(key)),
                )
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(
                _walk_external_episode_refs(
                    item,
                    path=(*path, str(index)),
                )
            )
    elif isinstance(value, str) and EPISODE_ID.fullmatch(value):
        rows.append((".".join(path), value))
    return rows


def explicit_external_refs(state: dict[str, Any]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path, identifier in _walk_external_episode_refs(state):
        grouped.setdefault(path, []).append(identifier)
    return grouped


def _planning_payload(episode: dict[str, Any]) -> dict[str, Any] | None:
    if episode.get("kind") != "planning_lab":
        return None
    content = episode.get("content")
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def pending_planning_episode_ids(state: dict[str, Any]) -> set[str]:
    from agenttest.planning_lab import EPISODIC_MEMORY_MAX_ENTRIES

    lab = state.get("planning_lab") or {}
    started = lab.get("episodic_memory_started_cycle")
    if started is None:
        return set()
    started_cycle = int(started or 0)
    world_version = str(lab.get("world_version") or "")
    completed = [
        plan
        for plan in lab.get("plans", [])
        if isinstance(plan, dict)
        and plan.get("status") == "completed"
        and int(plan.get("completed_cycle", 0) or 0) >= started_cycle
        and str(plan.get("world_version") or world_version) == world_version
    ]
    completed.sort(key=lambda plan: int(plan.get("completed_cycle", 0) or 0))
    completed = completed[-EPISODIC_MEMORY_MAX_ENTRIES:]
    existing = {
        str(item.get("source_plan_id") or "")
        for item in lab.get("episodic_route_memories", [])
        if isinstance(item, dict)
    }
    protected: set[str] = set()
    episodes = state.get("episodes", [])

    for plan in completed:
        plan_id = str(plan.get("id") or "")
        if not plan_id or plan_id in existing:
            continue
        executions = [
            item
            for item in lab.get("executions", [])
            if isinstance(item, dict)
            and item.get("plan_id") == plan_id
            and item.get("matched_prediction") is True
        ]
        if not executions:
            continue
        if any(
            int(item.get("cycle", 0) or 0) < started_cycle
            for item in executions
        ):
            continue
        execution_cycles = {
            int(item.get("cycle", 0) or 0)
            for item in executions
        }
        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            if int(episode.get("cycle", 0) or 0) not in execution_cycles:
                continue
            payload = _planning_payload(episode)
            if payload is not None and payload.get("plan_id") == plan_id:
                identifier = str(episode.get("id") or "")
                if identifier:
                    protected.add(identifier)
    return protected


def pending_world_episode_ids(state: dict[str, Any]) -> set[str]:
    snapshots = state.get("environment_snapshots", [])
    world = state.get("world_model") or {}
    start = min(
        int(world.get("last_snapshot_index", 0) or 0),
        len(snapshots),
    )
    pending_cycles = {
        int(snapshot.get("cycle", state.get("cycles", 0)) or 0)
        for snapshot in snapshots[start:]
        if isinstance(snapshot, dict)
    }
    if not pending_cycles:
        return set()
    return {
        str(episode.get("id"))
        for episode in state.get("episodes", [])
        if isinstance(episode, dict)
        and episode.get("kind") == "environment"
        and int(episode.get("cycle", 0) or 0) in pending_cycles
        and episode.get("id")
    }


def derive_protection(
    state: dict[str, Any],
    *,
    hot_suffix: int = DEFAULT_HOT_SUFFIX,
) -> dict[str, Any]:
    episodes = [
        item
        for item in state.get("episodes", [])
        if isinstance(item, dict)
    ]
    ids = [str(item.get("id") or "") for item in episodes]
    if len(ids) != len(set(ids)):
        raise ValueError("episode ledger contains duplicate identities")
    opaque = [identifier for identifier in ids if not EPISODE_ID.fullmatch(identifier)]
    if opaque:
        raise ValueError(
            "archive eligibility refuses opaque episode identities: "
            + ", ".join(opaque[:8])
        )

    external = explicit_external_refs(state)
    explicit = {
        identifier
        for values in external.values()
        for identifier in values
    }
    hot = set(ids[-max(0, hot_suffix):])
    planning = pending_planning_episode_ids(state)
    world = pending_world_episode_ids(state)
    current_cycle = int(state.get("cycles", 0) or 0)
    current_cycle_ids = {
        str(item.get("id"))
        for item in episodes
        if int(item.get("cycle", 0) or 0) >= current_cycle - 1
        and item.get("id")
    }

    protected = explicit | hot | planning | world | current_cycle_ids
    available_ids = set(ids)
    missing_external = sorted(explicit - available_ids)
    if missing_external:
        raise ValueError(
            "state already contains missing external episode refs: "
            + ", ".join(missing_external[:8])
        )

    eligible = [
        item
        for item in episodes
        if str(item.get("id")) not in protected
    ]
    return {
        "episode_count": len(episodes),
        "external_ref_occurrences": sum(
            len(values) for values in external.values()
        ),
        "external_unique_refs": len(explicit),
        "external_ref_paths": {
            path: len(values)
            for path, values in sorted(external.items())
        },
        "hot_suffix_count": len(hot),
        "pending_planning_count": len(planning),
        "pending_world_count": len(world),
        "current_cycle_protected_count": len(current_cycle_ids),
        "protected_count": len(protected),
        "eligible_count": len(eligible),
        "protected_ids": sorted(protected),
        "eligible_ids": [
            str(item.get("id"))
            for item in eligible
        ],
    }


def write_archive_segment(
    episodes: list[dict[str, Any]],
    output: Path,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8") as handle:
        for episode in episodes:
            handle.write(
                json.dumps(
                    episode,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                + "\n"
            )
    raw_digest = hashlib.sha256()
    for episode in episodes:
        raw_digest.update(
            (
                json.dumps(
                    episode,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                + "\n"
            ).encode("utf-8")
        )
    return {
        "record_count": len(episodes),
        "first_id": episodes[0]["id"] if episodes else None,
        "last_id": episodes[-1]["id"] if episodes else None,
        "canonical_records_sha256": raw_digest.hexdigest(),
        "gzip_sha256": sha256_file(output),
        "gzip_bytes": output.stat().st_size,
    }


def _stable_observation(state: dict[str, Any]) -> dict[str, Any]:
    snapshots = state.get("environment_snapshots", [])
    if not snapshots:
        raise ValueError("copied state has no environment observation")
    snapshot = deepcopy(snapshots[-1])
    snapshot.pop("cycle", None)
    return snapshot


def _normalize_state(
    state: dict[str, Any],
    archived_ids: set[str],
) -> dict[str, Any]:
    normalized = deepcopy(state)
    normalized["episodes"] = [
        item
        for item in normalized.get("episodes", [])
        if str(item.get("id") or "") not in archived_ids
    ]
    semantic = normalized.get("semantic_memory")
    if isinstance(semantic, dict):
        # Retained-list length is compatibility/observability only for numeric
        # Core episodes after PR #182. Sequence remains the newness authority.
        semantic["last_episode_index"] = len(normalized["episodes"])
    normalized.pop("updated_at", None)
    return normalized


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def cycle_worker(state_path: str, steps: int) -> dict[str, Any]:
    from agenttest.core import AgentCore
    from agenttest.evidence import known_evidence_ids
    from agenttest.state import StateStore

    store = StateStore(state_path)
    initial = store.load()
    observation = _stable_observation(initial)
    original_ids = [
        str(item.get("id"))
        for item in initial.get("episodes", [])
    ]
    rows = []

    for step in range(steps):
        now = f"2026-10-05T15:{step + 1:02d}:00+00:00"
        with ExitStack() as stack:
            for name, module in list(sys.modules.items()):
                if name.startswith("agenttest.") and hasattr(module, "utc_now"):
                    stack.enter_context(
                        patch.object(
                            module,
                            "utc_now",
                            side_effect=lambda value=now: value,
                        )
                    )
            result = AgentCore(StateStore(state_path)).cycle(
                stimulus="autonomous heartbeat",
                observation=deepcopy(observation),
                strict_experiment_admission=True,
                planning_lab=True,
                _now_override=now,
            )
        state = store.load()
        ids = [str(item.get("id")) for item in state.get("episodes", [])]
        if len(ids) != len(set(ids)):
            raise AssertionError("episode identity collision after diagnostic cycle")
        rows.append(
            {
                "step": step + 1,
                "cycle": int(state["cycles"]),
                "state": state,
                "result": result,
                "known_evidence_ids": sorted(known_evidence_ids(state)),
                "episode_ids": ids,
            }
        )

    return {
        "initial_cycle": int(initial["cycles"]),
        "initial_episode_ids": original_ids,
        "rows": rows,
    }


def _subprocess_worker(
    src: Path,
    state: Path,
    steps: int,
) -> dict[str, Any]:
    env = dict(
        os.environ,
        PYTHONPATH=str(src.resolve()),
        PYTHONDONTWRITEBYTECODE="1",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--state",
            str(state),
            "--steps",
            str(steps),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-6000:])
    return json.loads(completed.stdout)


def run_diagnostic(
    source_state: Path,
    src: Path,
    *,
    hot_suffix: int,
    remove_count: int,
    steps: int,
    output_dir: Path,
) -> dict[str, Any]:
    from agenttest.evidence import known_evidence_ids
    from agenttest.state import StateStore

    source_bytes = source_state.read_bytes()
    source_sha = sha256_bytes(source_bytes)
    source = StateStore(source_state).load()
    protection = derive_protection(source, hot_suffix=hot_suffix)
    if protection["eligible_count"] < remove_count:
        raise ValueError(
            f"only {protection['eligible_count']} episodes are conservatively eligible; "
            f"requested {remove_count}"
        )

    eligible_ids = protection["eligible_ids"][:remove_count]
    eligible_set = set(eligible_ids)
    removed = [
        deepcopy(item)
        for item in source["episodes"]
        if str(item.get("id")) in eligible_set
    ]
    if len(removed) != remove_count:
        raise AssertionError("archive candidate count mismatch")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive = write_archive_segment(
        removed,
        output_dir / "diagnostic-archive.jsonl.gz",
    )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        baseline_path = root / "baseline" / "organism.json"
        pruned_path = root / "pruned" / "organism.json"
        baseline_path.parent.mkdir()
        pruned_path.parent.mkdir()
        baseline_path.write_bytes(source_bytes)
        pruned_state = deepcopy(source)
        pruned_state["episodes"] = [
            item
            for item in pruned_state["episodes"]
            if str(item.get("id")) not in eligible_set
        ]
        StateStore(pruned_path).save(pruned_state)

        size_before = len(source_bytes)
        size_after = pruned_path.stat().st_size
        baseline = _subprocess_worker(src, baseline_path, steps)
        pruned = _subprocess_worker(src, pruned_path, steps)

    if source_state.read_bytes() != source_bytes:
        raise AssertionError("pinned source state changed")

    baseline_initial_known = known_evidence_ids(source)
    pruned_initial = deepcopy(source)
    pruned_initial["episodes"] = [
        item
        for item in pruned_initial["episodes"]
        if str(item.get("id")) not in eligible_set
    ]
    pruned_initial_known = known_evidence_ids(pruned_initial)
    expected_known = baseline_initial_known - eligible_set
    if pruned_initial_known != expected_known:
        raise AssertionError("eligibility removal altered unexpected evidence authority")

    comparisons = []
    for left, right in zip(baseline["rows"], pruned["rows"]):
        baseline_state = _normalize_state(left["state"], eligible_set)
        pruned_state = _normalize_state(right["state"], set())
        state_match = baseline_state == pruned_state
        result_match = left["result"] == right["result"]

        baseline_known = set(left["known_evidence_ids"]) - eligible_set
        pruned_known = set(right["known_evidence_ids"])
        known_match = baseline_known == pruned_known

        baseline_episode_ids = [
            identifier
            for identifier in left["episode_ids"]
            if identifier not in eligible_set
        ]
        episode_match = baseline_episode_ids == right["episode_ids"]

        comparisons.append(
            {
                "cycle": right["cycle"],
                "state_match": state_match,
                "result_match": result_match,
                "known_evidence_match_after_expected_archive_drop": known_match,
                "episode_sequence_match_after_archive_filter": episode_match,
            }
        )

    all_match = all(
        all(
            row[key]
            for key in (
                "state_match",
                "result_match",
                "known_evidence_match_after_expected_archive_drop",
                "episode_sequence_match_after_archive_filter",
            )
        )
        for row in comparisons
    )

    post_state = pruned["rows"][-1]["state"]
    post_external = explicit_external_refs(post_state)
    post_external_ids = {
        identifier
        for values in post_external.values()
        for identifier in values
    }
    archived_became_referenced = sorted(post_external_ids & eligible_set)
    if archived_became_referenced:
        raise AssertionError(
            "ordinary cycles created references to diagnostic archived IDs"
        )

    return {
        "study": "episode-archive-eligibility-copied-state-v1",
        "passed": all_match and not archived_became_referenced,
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "source_state_sha256": source_sha,
        "source_unchanged": True,
        "hot_suffix": hot_suffix,
        "remove_count": remove_count,
        "steps": steps,
        "protection": {
            key: value
            for key, value in protection.items()
            if key not in {"protected_ids", "eligible_ids"}
        },
        "archive": archive,
        "removed_ids": eligible_ids,
        "state_bytes_before": size_before,
        "state_bytes_after_prune_before_cycles": size_after,
        "state_bytes_reduction": size_before - size_after,
        "state_bytes_reduction_fraction": round(
            (size_before - size_after) / size_before,
            6,
        ),
        "comparisons": comparisons,
        "archived_became_referenced": archived_became_referenced,
        "authority": {
            "production_modified": False,
            "retention_enabled": False,
            "archive_lookup_enabled": False,
            "known_evidence_ids_broadened": False,
            "phase42_changed": False,
            "environment_actions": False,
            "external_model_api": False,
        },
        "limitations": [
            "This proves only a conservative copied-state eligibility policy over the tested hot suffix, removal count, and five ordinary cycles.",
            "Archived episode IDs intentionally leave generic known_evidence_ids because no archive authority/lookup is implemented yet.",
            "Human interaction and model cognition were not invoked in the replay; the hot suffix protects their recent raw-episode dependencies.",
            "The diagnostic archive artifact is evidence for review, not a production archive store.",
            "No physical retention policy is authorized by this result even if the copied replay matches.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--state", required=True)
    parser.add_argument("--src")
    parser.add_argument("--hot-suffix", type=int, default=DEFAULT_HOT_SUFFIX)
    parser.add_argument("--remove-count", type=int, default=DEFAULT_REMOVE_COUNT)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--output-dir")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(cycle_worker(args.state, args.steps), sort_keys=True))
        return 0

    if not args.src or not args.output_dir:
        parser.error("--src and --output-dir are required")
    result = run_diagnostic(
        Path(args.state),
        Path(args.src),
        hot_suffix=args.hot_suffix,
        remove_count=args.remove_count,
        steps=args.steps,
        output_dir=Path(args.output_dir),
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "episode_count": result["protection"]["episode_count"],
                "protected_count": result["protection"]["protected_count"],
                "eligible_count": result["protection"]["eligible_count"],
                "removed": result["remove_count"],
                "reduction_bytes": result["state_bytes_reduction"],
                "reduction_fraction": result["state_bytes_reduction_fraction"],
                "all_cycle_matches": all(
                    row["state_match"] and row["result_match"]
                    for row in result["comparisons"]
                ),
            },
            sort_keys=True,
        )
    )
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
