from __future__ import annotations

import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

PRODUCTION = "d1a4046b0941788ddf642cf64a279380f08ed1a6"
FIELD = "last_episode_sequence"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized_state(state):
    result = deepcopy(state)
    semantic = result.get("semantic_memory", {})
    semantic.pop(FIELD, None)
    return result


def worker(state_file, steps):
    from agenttest.core import AgentCore
    from agenttest.evidence import known_evidence_ids
    from agenttest.state import StateStore

    store = StateStore(state_file)
    clock = ["2026-10-05T14:00:00+00:00"]
    with ExitStack() as patches:
        for name, module in list(sys.modules.items()):
            if name.startswith("agenttest.") and hasattr(module, "utc_now"):
                patches.enter_context(
                    patch.object(module, "utc_now", side_effect=lambda: clock[0])
                )
        state = store.load()
        source = deepcopy(state["environment_snapshots"][-1])
        initial = normalized_state(state)
        original_episodes = deepcopy(state["episodes"])
        rows = []
        for step in range(steps):
            clock[0] = f"2026-10-05T14:{step+1:02d}:00+00:00"
            result = AgentCore(StateStore(state_file)).cycle(
                stimulus="autonomous heartbeat",
                observation=deepcopy(source),
                strict_experiment_admission=True,
                planning_lab=True,
                _now_override=clock[0],
            )
            state = store.load()
            if state["episodes"][: len(original_episodes)] != original_episodes:
                raise AssertionError("historical episodes changed")
            rows.append(
                {
                    "cycle": state["cycles"],
                    "state_hash": digest(normalized_state(state)),
                    "result_hash": digest(result),
                    "known_ids_hash": digest(sorted(known_evidence_ids(state))),
                    "episode_count": len(state["episodes"]),
                    "last_episode_id": state["episodes"][-1]["id"],
                    "semantic_last_episode_index": state["semantic_memory"]["last_episode_index"],
                    "semantic_last_episode_sequence": state["semantic_memory"].get(FIELD),
                    "semantic_hash_without_cursor": digest(
                        {
                            key: value
                            for key, value in state["semantic_memory"].items()
                            if key != FIELD
                        }
                    ),
                }
            )
        return {
            "initial_hash": digest(initial),
            "initial_known_ids_hash": digest(sorted(known_evidence_ids(state))),
            "initial_cycle": initial["cycles"],
            "initial_episode_count": len(original_episodes),
            "initial_last_episode_index": initial["semantic_memory"]["last_episode_index"],
            "initial_last_episode_sequence": state["semantic_memory"].get(FIELD),
            "rows": rows,
        }


def deletion_probe(state_file):
    from agenttest.episode_identity import allocate_episode_id
    from agenttest.semantic import consolidate_semantic_memory
    from agenttest.state import StateStore

    store = StateStore(state_file)
    state = store.load()
    before_sequence = state["semantic_memory"][FIELD]
    remove = min(1000, max(1, len(state["episodes"]) // 10))
    del state["episodes"][:remove]
    new_id = allocate_episode_id(state)
    state["episodes"].append(
        {
            "id": new_id,
            "cycle": int(state["cycles"]) + 1,
            "time": "2026-10-05T14:59:00+00:00",
            "kind": "semantic_cursor_probe",
            "content": "semantic cursor deletion recovery probe",
            "concepts": ["semantic_cursor_probe_unique"],
        }
    )
    result = consolidate_semantic_memory(state)
    concept = state["semantic_memory"]["concepts"].get("semantic_cursor_probe_unique")
    if result["episodes_consolidated"] != 1 or not concept:
        raise AssertionError("sequence cursor did not recover after prefix removal")
    if state["semantic_memory"][FIELD] <= before_sequence:
        raise AssertionError("semantic sequence cursor did not advance")
    return {
        "removed_prefix_count": remove,
        "new_episode_id": new_id,
        "episodes_consolidated": result["episodes_consolidated"],
        "new_concept_count": concept["count"],
        "before_sequence": before_sequence,
        "after_sequence": state["semantic_memory"][FIELD],
        "retained_episode_count": len(state["episodes"]),
    }


def run(args):
    source = Path(args.state).resolve()
    source_hash = file_hash(source)
    reports = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, src in (("baseline", args.baseline_src), ("candidate", args.candidate_src)):
            target = Path(tmp) / name / "organism.json"
            target.parent.mkdir()
            target.write_bytes(source.read_bytes())
            env = dict(
                os.environ,
                PYTHONPATH=str(Path(src).resolve()),
                PYTHONDONTWRITEBYTECODE="1",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--state",
                    str(target),
                    "--steps",
                    str(args.steps),
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=300,
                check=False,
            )
            if completed.returncode:
                raise RuntimeError(f"{name} worker failed: {completed.stderr[-4000:]}")
            reports[name] = json.loads(completed.stdout)

        probe_target = Path(tmp) / "probe" / "organism.json"
        probe_target.parent.mkdir()
        probe_target.write_bytes(source.read_bytes())
        env = dict(
            os.environ,
            PYTHONPATH=str(Path(args.candidate_src).resolve()),
            PYTHONDONTWRITEBYTECODE="1",
        )
        probe = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--probe",
                "--state",
                str(probe_target),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
        )
        if probe.returncode:
            raise RuntimeError(f"deletion probe failed: {probe.stderr[-4000:]}")
        deletion = json.loads(probe.stdout)

    baseline = reports["baseline"]
    candidate = reports["candidate"]
    if baseline["initial_hash"] != candidate["initial_hash"]:
        raise AssertionError("semantic cursor migration changed normalized initial state")

    fields = (
        "state_hash",
        "result_hash",
        "known_ids_hash",
        "episode_count",
        "last_episode_id",
        "semantic_last_episode_index",
        "semantic_hash_without_cursor",
    )
    comparisons = []
    for left, right in zip(baseline["rows"], candidate["rows"]):
        checks = {field: left[field] == right[field] for field in fields}
        checks["sequence_matches_latest_numeric_id"] = (
            right["semantic_last_episode_sequence"]
            == int(str(right["last_episode_id"])[1:])
        )
        comparisons.append({"cycle": right["cycle"], "checks": checks})

    if len(comparisons) != args.steps or not all(
        all(row["checks"].values()) for row in comparisons
    ):
        raise AssertionError("baseline/candidate parity mismatch: " + json.dumps(comparisons))
    if file_hash(source) != source_hash:
        raise AssertionError("pinned source state was modified")

    return {
        "study": "semantic-episode-sequence-cursor-v1",
        "passed": True,
        "production_base": PRODUCTION,
        "source_sha": args.source_sha,
        "source_sha256": source_hash,
        "source_unchanged": True,
        "matched_cycles": len(comparisons),
        "comparison": comparisons,
        "baseline": baseline,
        "candidate": candidate,
        "deletion_recovery_probe": deletion,
        "retention_enabled": False,
        "resolver_floor_changed": False,
        "evidence_authority_changed": False,
        "phase42_changed": False,
        "limitations": [
            "Only numeric Core E-episode identities are deletion-safe under the new cursor; opaque future episode IDs retain legacy positional fallback.",
            "No archive, pruning, tombstone, reference retrieval or evidence-authority semantics are implemented.",
            "Native inquiry resolution still uses a positional episode-count freshness floor and remains a separate blocker.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--baseline-src")
    parser.add_argument("--candidate-src")
    parser.add_argument("--source-sha")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(worker(args.state, args.steps), sort_keys=True))
        return
    if args.probe:
        print(json.dumps(deletion_probe(args.state), sort_keys=True))
        return

    report = run(args)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "matched_cycles": report["matched_cycles"],
                "deletion_recovery_probe": report["deletion_recovery_probe"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
