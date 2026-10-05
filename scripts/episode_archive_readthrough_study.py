"""Copied-state immutable archive read-through study.

Builds one external archive segment from the conservative PR #184 selection,
removes only those records from a disposable hot state, proves exact lookup and
recovery, and compares five ordinary cycles with an untouched copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from episode_archive_contract import (
    EpisodeArchiveSegment,
    build_archive_segment,
    canonical_episode_bytes,
)
from episode_archive_selection import derive_protection

PRODUCTION_BASE = "e3672c473723159232ab494a108eeca7d1903842"
PINNED_STATE = "906d216b54d76e3cb57c540cf59fd57004f29bf3"
HOT_SUFFIX = 1024
ARCHIVE_COUNT = 1000
STEPS = 5


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_observation(state: dict) -> dict:
    snapshots = state.get("environment_snapshots", [])
    if not snapshots:
        raise ValueError("copied state has no environment observation")
    observation = deepcopy(snapshots[-1])
    observation.pop("cycle", None)
    return observation


def _normalize_state(state: dict, archived_ids: set[str]) -> dict:
    normalized = deepcopy(state)
    normalized["episodes"] = [
        item
        for item in normalized.get("episodes", [])
        if str(item.get("id") or "") not in archived_ids
    ]
    semantic = normalized.get("semantic_memory")
    if isinstance(semantic, dict):
        semantic["last_episode_index"] = len(normalized["episodes"])
    normalized.pop("updated_at", None)
    return normalized


def cycle_worker(state_path: str, steps: int) -> dict:
    from agenttest.core import AgentCore
    from agenttest.evidence import known_evidence_ids
    from agenttest.state import StateStore

    store = StateStore(state_path)
    initial = store.load()
    observation = _stable_observation(initial)
    rows = []
    for step in range(steps):
        now = f"2026-10-05T16:{step + 1:02d}:00+00:00"
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
        rows.append(
            {
                "cycle": int(state["cycles"]),
                "state": state,
                "result": result,
                "known_evidence_ids": sorted(known_evidence_ids(state)),
                "episode_ids": [
                    str(item.get("id"))
                    for item in state.get("episodes", [])
                ],
            }
        )
    return {
        "initial_cycle": int(initial["cycles"]),
        "rows": rows,
    }


def _worker(src: Path, state_path: Path, steps: int) -> dict:
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join(
            [
                str(src.resolve()),
                str((ROOT / "experiments").resolve()),
            ]
        ),
        PYTHONDONTWRITEBYTECODE="1",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--state",
            str(state_path),
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


def _assert_corruption_fails(
    manifest_path: Path,
    workdir: Path,
) -> dict[str, bool]:
    original_root = manifest_path.parent

    segment_case = workdir / "segment-corrupt"
    shutil.copytree(original_root, segment_case)
    segment_manifest = next(segment_case.glob("*.manifest.json"))
    manifest = json.loads(segment_manifest.read_text())
    segment_path = segment_case / manifest["segment_file"]
    payload = bytearray(segment_path.read_bytes())
    payload[-1] ^= 1
    segment_path.write_bytes(bytes(payload))
    segment_failed = False
    try:
        EpisodeArchiveSegment.load(segment_manifest)
    except ValueError:
        segment_failed = True

    index_case = workdir / "index-corrupt"
    shutil.copytree(original_root, index_case)
    index_manifest = next(index_case.glob("*.manifest.json"))
    manifest = json.loads(index_manifest.read_text())
    index_path = index_case / manifest["index_file"]
    index_payload = json.loads(index_path.read_text())
    index_payload["records"][0]["record_sha256"] = "0" * 64
    index_path.write_text(json.dumps(index_payload, sort_keys=True))
    index_failed = False
    try:
        EpisodeArchiveSegment.load(index_manifest)
    except ValueError:
        index_failed = True

    authority_case = workdir / "authority-corrupt"
    shutil.copytree(original_root, authority_case)
    authority_manifest = next(authority_case.glob("*.manifest.json"))
    manifest = json.loads(authority_manifest.read_text())
    manifest["generic_evidence_authority"] = True
    authority_manifest.write_text(json.dumps(manifest, sort_keys=True))
    authority_failed = False
    try:
        EpisodeArchiveSegment.load(authority_manifest)
    except ValueError:
        authority_failed = True

    return {
        "segment_corruption_rejected": segment_failed,
        "index_corruption_rejected": index_failed,
        "authority_escalation_rejected": authority_failed,
    }


def run(source_state: Path, src: Path, output_dir: Path) -> dict:
    from agenttest.evidence import known_evidence_ids
    from agenttest.state import StateStore

    source_bytes = source_state.read_bytes()
    source_sha = _sha256(source_bytes)
    source = StateStore(source_state).load()
    protection = derive_protection(source, hot_suffix=HOT_SUFFIX)

    expected = {
        "episode_count": 12948,
        "protected_count": 5829,
        "eligible_count": 7119,
    }
    for key, value in expected.items():
        if protection[key] != value:
            raise AssertionError(
                f"pinned eligibility changed for {key}: "
                f"{protection[key]} != {value}"
            )

    selected_ids = protection["eligible_ids"][:ARCHIVE_COUNT]
    selected = set(selected_ids)
    archive_records = [
        deepcopy(item)
        for item in source["episodes"]
        if str(item.get("id")) in selected
    ]
    if [item["id"] for item in archive_records] != selected_ids:
        raise AssertionError("archive selection order changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    built = build_archive_segment(
        archive_records,
        output_dir / "archive",
        production_base=PRODUCTION_BASE,
        source_state_sha256=source_sha,
        source_episode_count=len(source["episodes"]),
    )
    segment = EpisodeArchiveSegment.load(
        built["manifest_path"],
        expected_production_base=PRODUCTION_BASE,
        expected_source_state_sha256=source_sha,
    )
    if list(segment.archived_ids) != selected_ids:
        raise AssertionError("archive index does not preserve selected IDs")

    original_by_id = {
        str(item["id"]): item
        for item in archive_records
    }
    exact_lookup_count = 0
    exact_bytes_count = 0
    for identifier in selected_ids:
        restored = segment.lookup(
            identifier,
            purpose="historical_lookup",
        )
        if restored != original_by_id[identifier]:
            raise AssertionError(f"archive lookup mismatch: {identifier}")
        exact_lookup_count += 1
        payload = segment.canonical_record_bytes(
            identifier,
            purpose="recovery_restore",
        )
        if payload != canonical_episode_bytes(original_by_id[identifier]):
            raise AssertionError(f"archive canonical bytes mismatch: {identifier}")
        exact_bytes_count += 1
        if segment.grants_generic_evidence_authority(identifier):
            raise AssertionError("archive unexpectedly grants evidence authority")

    authority_denials = 0
    for purpose in (
        "generic_evidence",
        "native_inquiry_grounding",
        "native_inquiry_resolution",
        "cognition_grounding",
        "self_proposal_grounding",
    ):
        try:
            segment.lookup(selected_ids[0], purpose=purpose)
        except PermissionError:
            authority_denials += 1

    hot_source = deepcopy(source)
    hot_source["episodes"] = [
        item
        for item in hot_source["episodes"]
        if str(item.get("id")) not in selected
    ]
    if known_evidence_ids(hot_source) & selected:
        raise AssertionError(
            "archived records remained in generic evidence authority"
        )
    restored_initial = segment.restore_episode_ledger(
        hot_source["episodes"]
    )
    if restored_initial != source["episodes"]:
        raise AssertionError("archive recovery did not reconstruct source ledger")

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        baseline_path = root / "baseline" / "organism.json"
        hot_path = root / "hot" / "organism.json"
        baseline_path.parent.mkdir()
        hot_path.parent.mkdir()
        baseline_path.write_bytes(source_bytes)
        StateStore(hot_path).save(hot_source)
        hot_bytes_before_cycles = hot_path.stat().st_size

        baseline = _worker(src, baseline_path, STEPS)
        hot = _worker(src, hot_path, STEPS)

    comparisons = []
    recovery_after_cycle_count = 0
    for left, right in zip(baseline["rows"], hot["rows"]):
        normalized_baseline = _normalize_state(left["state"], selected)
        normalized_hot = _normalize_state(right["state"], set())
        state_match = normalized_baseline == normalized_hot
        result_match = left["result"] == right["result"]

        baseline_known = set(left["known_evidence_ids"]) - selected
        hot_known = set(right["known_evidence_ids"])
        known_match = baseline_known == hot_known

        baseline_episode_ids = [
            identifier
            for identifier in left["episode_ids"]
            if identifier not in selected
        ]
        episode_match = baseline_episode_ids == right["episode_ids"]

        restored = segment.restore_episode_ledger(
            right["state"]["episodes"]
        )
        full_recovery_match = restored == left["state"]["episodes"]
        if full_recovery_match:
            recovery_after_cycle_count += 1

        comparisons.append(
            {
                "cycle": right["cycle"],
                "state_match": state_match,
                "result_match": result_match,
                "known_evidence_match": known_match,
                "episode_sequence_match": episode_match,
                "full_ledger_recovery_match": full_recovery_match,
            }
        )

    all_cycle_matches = all(
        all(
            row[key]
            for key in (
                "state_match",
                "result_match",
                "known_evidence_match",
                "episode_sequence_match",
                "full_ledger_recovery_match",
            )
        )
        for row in comparisons
    )

    corruption = _assert_corruption_fails(
        Path(built["manifest_path"]),
        output_dir / "corruption-probes",
    )
    if not all(corruption.values()):
        raise AssertionError("archive corruption probe did not fail closed")

    if source_state.read_bytes() != source_bytes:
        raise AssertionError("pinned source state changed")

    manifest = segment.manifest
    archive_total_bytes = sum(
        Path(path).stat().st_size
        for path in (
            built["manifest_path"],
            built["index_path"],
            built["segment_path"],
        )
    )
    return {
        "study": "episode-archive-readthrough-contract-v1",
        "passed": (
            all_cycle_matches
            and exact_lookup_count == ARCHIVE_COUNT
            and exact_bytes_count == ARCHIVE_COUNT
            and authority_denials == 5
            and recovery_after_cycle_count == STEPS
            and all(corruption.values())
        ),
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "source_state_sha256": source_sha,
        "source_unchanged": True,
        "source_episode_count": len(source["episodes"]),
        "protected_count": protection["protected_count"],
        "eligible_count": protection["eligible_count"],
        "archived_count": ARCHIVE_COUNT,
        "first_archived_id": selected_ids[0],
        "last_archived_id": selected_ids[-1],
        "archive_manifest": manifest,
        "exact_lookup_count": exact_lookup_count,
        "exact_canonical_bytes_count": exact_bytes_count,
        "generic_authority_denial_count": authority_denials,
        "archive_total_bytes": archive_total_bytes,
        "hot_state_bytes_before_cycles": hot_bytes_before_cycles,
        "original_state_bytes": len(source_bytes),
        "hot_state_reduction_bytes": len(source_bytes) - hot_bytes_before_cycles,
        "combined_hot_plus_archive_bytes": (
            hot_bytes_before_cycles + archive_total_bytes
        ),
        "combined_reduction_bytes": (
            len(source_bytes)
            - (hot_bytes_before_cycles + archive_total_bytes)
        ),
        "comparisons": comparisons,
        "full_ledger_recovery_match_count": recovery_after_cycle_count,
        "corruption": corruption,
        "authority": {
            "archive_location_only": True,
            "generic_evidence_authority": False,
            "production_modified": False,
            "retention_enabled": False,
            "phase42_changed": False,
            "environment_actions": False,
            "external_model_api": False,
        },
        "limitations": [
            "The archive reader is isolated research code and is not wired into production consumers.",
            "The segment is loaded as a whole for lookup; random-access scaling is not established.",
            "No archived ID is admitted to generic evidence authority in v1.",
            "The replay covers five ordinary cycles on one pinned state and one 1,000-record segment.",
            "Production deletion, archive storage, retention policy, and journal rollover remain disabled.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--state", required=True)
    parser.add_argument("--src")
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--output-dir")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(cycle_worker(args.state, args.steps), sort_keys=True))
        return 0

    if not args.src or not args.output_dir:
        parser.error("--src and --output-dir are required")
    report = run(
        Path(args.state),
        Path(args.src),
        Path(args.output_dir),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "archived_count": report["archived_count"],
                "exact_lookup_count": report["exact_lookup_count"],
                "authority_denials": report["generic_authority_denial_count"],
                "full_recovery_matches": report[
                    "full_ledger_recovery_match_count"
                ],
                "archive_total_bytes": report["archive_total_bytes"],
                "hot_state_reduction_bytes": report[
                    "hot_state_reduction_bytes"
                ],
                "combined_reduction_bytes": report[
                    "combined_reduction_bytes"
                ],
                "all_cycle_matches": all(
                    row["state_match"] and row["result_match"]
                    for row in report["comparisons"]
                ),
            },
            sort_keys=True,
        )
    )
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
