"""Purpose-scoped archive provenance read-through on real referenced episodes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from archive_provenance_resolver import ArchiveProvenanceResolver
from episode_archive_contract import EpisodeArchiveSegment, build_archive_segment

PRODUCTION_BASE = "e3672c473723159232ab494a108eeca7d1903842"
PINNED_STATE = "906d216b54d76e3cb57c540cf59fd57004f29bf3"
STEPS = 5
EPISODE_ID = re.compile(r"E([0-9]+)\Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _walk_refs(
    value,
    *,
    path: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if path == () and key == "episodes":
                continue
            rows.extend(_walk_refs(item, path=(*path, str(key))))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk_refs(item, path=(*path, str(index))))
    elif isinstance(value, str) and EPISODE_ID.fullmatch(value):
        rows.append((".".join(path), value))
    return rows


def _category(path: str) -> str:
    if path.startswith("semantic_memory.") and ".episode_refs." in path:
        return "semantic_memory"
    if path.startswith("world_model.") and ".evidence_refs." in path:
        return "world_model"
    if path.startswith("planning_lab.") and ".memory_episode_refs." in path:
        return "planning_memory"
    if path.startswith("planning_lab.") and ".source_episode_refs." in path:
        return "planning_source_ref"
    if path.startswith("planning_lab.") and ".source_episode_ids." in path:
        return "planning_source_id"
    if path.startswith("interactions.") and ".input_episode_id" in path:
        return "interaction"
    if path.startswith("self_model.") and ".evidence_refs." in path:
        return "self_model"
    return "other"


def choose_referenced_archive_ids(state: dict) -> list[dict]:
    rows = _walk_refs(state)
    paths_by_id: dict[str, list[str]] = {}
    categories_by_id: dict[str, set[str]] = {}
    for path, identifier in rows:
        paths_by_id.setdefault(identifier, []).append(path)
        categories_by_id.setdefault(identifier, set()).add(_category(path))

    targets = [
        "world_model",
        "semantic_memory",
        "planning_memory",
    ]
    selected = []
    for target in targets:
        candidates = []
        for identifier, categories in categories_by_id.items():
            match = EPISODE_ID.fullmatch(identifier)
            if not match or categories != {target}:
                continue
            candidates.append((int(match.group(1)), identifier))
        if not candidates:
            raise AssertionError(f"no archive candidate for category {target}")
        _, identifier = min(candidates)
        episode = next(
            (
                item
                for item in state.get("episodes", [])
                if str(item.get("id")) == identifier
            ),
            None,
        )
        if episode is None:
            raise AssertionError(f"referenced episode missing: {identifier}")
        selected.append(
            {
                "category": target,
                "id": identifier,
                "reference_paths": sorted(paths_by_id[identifier]),
                "episode": deepcopy(episode),
            }
        )
    selected.sort(key=lambda row: int(row["id"][1:]))
    return selected


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
        now = f"2026-10-05T17:{step + 1:02d}:00+00:00"
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
            }
        )
    return {"rows": rows}


def _run_worker(src: Path, state_path: Path, steps: int) -> dict:
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


def run(source_state: Path, src: Path, output_dir: Path) -> dict:
    from agenttest.evidence import known_evidence_ids
    from agenttest.state import StateStore

    source_bytes = source_state.read_bytes()
    source_sha = _sha256(source_bytes)
    source = StateStore(source_state).load()
    selected = choose_referenced_archive_ids(source)
    selected_ids = [row["id"] for row in selected]
    selected_set = set(selected_ids)
    records = [row["episode"] for row in selected]

    output_dir.mkdir(parents=True, exist_ok=True)
    built = build_archive_segment(
        records,
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

    hot = deepcopy(source)
    hot["episodes"] = [
        item
        for item in hot["episodes"]
        if str(item.get("id")) not in selected_set
    ]
    hot_known = known_evidence_ids(hot)
    if hot_known & selected_set:
        raise AssertionError(
            "archived referenced records unexpectedly remain generic evidence"
        )

    resolver = ArchiveProvenanceResolver(hot, [segment])
    provenance = []
    for row in selected:
        identifier = row["id"]
        resolved = resolver.resolve(
            identifier,
            purpose="provenance_lookup",
        )
        if resolved is None or resolved["record"] != row["episode"]:
            raise AssertionError(f"provenance lookup mismatch: {identifier}")
        if resolved["location"] != "archive":
            raise AssertionError(f"referenced record is not archive-backed: {identifier}")
        if resolver.is_generic_evidence_known(identifier):
            raise AssertionError(
                f"archive broadened generic evidence authority: {identifier}"
            )
        provenance.append(
            {
                "id": identifier,
                "category": row["category"],
                "reference_paths": row["reference_paths"],
                "record_kind": row["episode"].get("kind"),
                "record_cycle": row["episode"].get("cycle"),
                "segment_id": resolved["segment_id"],
                "location": resolved["location"],
                "generic_evidence_known": False,
            }
        )

    denied = 0
    for purpose in (
        "generic_evidence",
        "native_inquiry_grounding",
        "native_inquiry_resolution",
        "cognition_grounding",
        "self_proposal_grounding",
    ):
        try:
            resolver.resolve(selected_ids[0], purpose=purpose)
        except PermissionError:
            denied += 1

    restored = segment.restore_episode_ledger(hot["episodes"])
    if restored != source["episodes"]:
        raise AssertionError("initial referenced-record recovery mismatch")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        baseline_path = root / "baseline" / "organism.json"
        hot_path = root / "hot" / "organism.json"
        baseline_path.parent.mkdir()
        hot_path.parent.mkdir()
        baseline_path.write_bytes(source_bytes)
        StateStore(hot_path).save(hot)
        baseline = _run_worker(src, baseline_path, STEPS)
        pruned = _run_worker(src, hot_path, STEPS)

    comparisons = []
    post_lookup_matches = 0
    post_reference_matches = 0
    for left, right in zip(baseline["rows"], pruned["rows"]):
        state_match = (
            _normalize_state(left["state"], selected_set)
            == _normalize_state(right["state"], set())
        )
        result_match = left["result"] == right["result"]
        known_match = (
            set(left["known_evidence_ids"]) - selected_set
            == set(right["known_evidence_ids"])
        )
        restored_ledger = segment.restore_episode_ledger(
            right["state"]["episodes"]
        )
        recovery_match = restored_ledger == left["state"]["episodes"]

        post_resolver = ArchiveProvenanceResolver(
            right["state"],
            [segment],
        )
        lookup_match = all(
            (
                (resolved := post_resolver.resolve(
                    row["id"],
                    purpose="provenance_lookup",
                ))
                is not None
                and resolved["record"] == row["episode"]
                and resolved["location"] == "archive"
                and not post_resolver.is_generic_evidence_known(row["id"])
            )
            for row in selected
        )
        if lookup_match:
            post_lookup_matches += 1

        current_refs = _walk_refs(right["state"])
        referenced_ids = {
            identifier
            for _path, identifier in current_refs
        }
        refs_preserved = selected_set <= referenced_ids
        if refs_preserved:
            post_reference_matches += 1

        comparisons.append(
            {
                "cycle": right["cycle"],
                "state_match": state_match,
                "result_match": result_match,
                "known_evidence_match_after_expected_archive_drop": known_match,
                "full_ledger_recovery_match": recovery_match,
                "archive_provenance_lookup_match": lookup_match,
                "external_references_preserved": refs_preserved,
            }
        )

    all_matches = all(
        all(
            row[key]
            for key in (
                "state_match",
                "result_match",
                "known_evidence_match_after_expected_archive_drop",
                "full_ledger_recovery_match",
                "archive_provenance_lookup_match",
                "external_references_preserved",
            )
        )
        for row in comparisons
    )

    if source_state.read_bytes() != source_bytes:
        raise AssertionError("pinned source state changed")

    return {
        "study": "archive-provenance-readthrough-real-refs-v1",
        "passed": (
            all_matches
            and denied == 5
            and post_lookup_matches == STEPS
            and post_reference_matches == STEPS
        ),
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "source_state_sha256": source_sha,
        "source_unchanged": True,
        "selected_referenced_records": provenance,
        "archive_manifest": segment.manifest,
        "authority_denial_count": denied,
        "comparisons": comparisons,
        "post_cycle_lookup_match_count": post_lookup_matches,
        "post_cycle_reference_preservation_count": post_reference_matches,
        "authority": {
            "historical_provenance_lookup": True,
            "generic_evidence_authority": False,
            "native_grounding_authority": False,
            "production_modified": False,
            "retention_enabled": False,
            "phase42_changed": False,
            "environment_actions": False,
            "external_model_api": False,
        },
        "limitations": [
            "Only three referenced historical records are archived in this purpose-scoped proof.",
            "The resolver is isolated research code and is not wired into production state consumers.",
            "No generic/native/cognition/self-proposal grounding is granted from archived records.",
            "Five ordinary cycles on one pinned state do not establish indefinite retention.",
            "Archive storage, compaction, journal rollover and richer-world live activation remain separate.",
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
                "selected": [
                    {
                        "id": row["id"],
                        "category": row["category"],
                        "kind": row["record_kind"],
                        "cycle": row["record_cycle"],
                    }
                    for row in report["selected_referenced_records"]
                ],
                "authority_denials": report["authority_denial_count"],
                "post_cycle_lookup_matches": report[
                    "post_cycle_lookup_match_count"
                ],
                "post_cycle_reference_preservation": report[
                    "post_cycle_reference_preservation_count"
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
