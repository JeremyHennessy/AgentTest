"""Compare positional versus monotonic native-inquiry freshness on copied state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PRODUCTION_BASE = "404ea4be0127d14fe419e635b239c2e51e9c4532"
PINNED_STATE = "e39688f1037b9e83db3ad37f3b94e22e937782cb"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _temporal_evidence(feature: str, refs: list[str]) -> dict:
    from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": "same_next_observation",
            "feature": feature,
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": refs,
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": 1,
            "confirmations": 1,
            "refutations": 0,
        },
    }


def _candidate(evidence_ref: str) -> dict:
    from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION
    return {
        "version": NATIVE_INQUIRY_VERSION,
        "id": "NIC:study:sequence-floor",
        "objective": "information_gain",
        "objective_score": 0.6,
        "relation": {
            "kind": "same_next_observation",
            "feature": "retention_probe_signal",
            "action": None,
            "comparison_status": "not_applicable",
        },
        "question": "What next observation tests whether retention_probe_signal remains stable?",
        "hypothesis": "Observed retention_probe_signal tends to remain stable.",
        "method": "Collect one later public retention_probe_signal observation.",
        "falsification": "A later changed value counts against stability.",
        "predicted_observation": "The next evaluable value matches the prior value.",
        "evidence_refs": [evidence_ref],
    }


def worker(state_path: str, remove_prefix: int) -> dict:
    from agenttest.core import AgentCore
    from agenttest.episode_identity import episode_sequence
    from agenttest.state import StateStore

    store = StateStore(state_path)
    core = AgentCore(store)
    initial = store.load()
    initial_cycle = int(initial["cycles"])
    initial_count = len(initial["episodes"])

    core.record_native_evidence(
        _temporal_evidence("unrelated_probe_signal", ["u0", "u1"]),
        enabled=True,
        persist=True,
    )
    grounding = core.record_native_evidence(
        _temporal_evidence("retention_probe_signal", ["obs-0", "obs-1"]),
        enabled=True,
        persist=True,
    )
    stale = core.record_native_evidence(
        _temporal_evidence("retention_probe_signal", ["obs-1", "obs-2"]),
        enabled=True,
        persist=True,
    )
    inquiry = core.propose_native_inquiry(
        _candidate(grounding["evidence_ref"]),
        enabled=True,
        persist=True,
    )
    native = inquiry["experiment"]["native_inquiry"]
    count_floor = native.get("resolution_evidence_floor_episode_count")
    sequence_floor = native.get("resolution_evidence_floor_episode_sequence")

    staged = store.load()
    if len(staged["episodes"]) <= remove_prefix:
        raise AssertionError("prefix removal exceeds copied episode ledger")
    removed_ids = [item["id"] for item in staged["episodes"][:remove_prefix]]
    staged["episodes"] = staged["episodes"][remove_prefix:]
    store.save(staged)

    after_removal = store.load()
    fresh = AgentCore(store).record_native_evidence(
        _temporal_evidence(
            "retention_probe_signal",
            ["obs-2", "obs-3"],
        ),
        enabled=True,
        persist=True,
    )
    fresh_sequence = episode_sequence(fresh["evidence_ref"])

    stale_error = None
    try:
        AgentCore(store).resolve_native_inquiry(
            inquiry["experiment"]["id"],
            stale["evidence_ref"],
            enabled=True,
            persist=False,
        )
    except ValueError as exc:
        stale_error = str(exc)

    fresh_result = None
    fresh_error = None
    try:
        fresh_result = AgentCore(store).resolve_native_inquiry(
            inquiry["experiment"]["id"],
            fresh["evidence_ref"],
            enabled=True,
            persist=False,
        )
    except ValueError as exc:
        fresh_error = str(exc)

    final = store.load()
    return {
        "initial_cycle": initial_cycle,
        "initial_episode_count": initial_count,
        "count_floor": count_floor,
        "sequence_floor": sequence_floor,
        "grounding_ref": grounding["evidence_ref"],
        "stale_ref": stale["evidence_ref"],
        "fresh_ref": fresh["evidence_ref"],
        "fresh_sequence": fresh_sequence,
        "removed_prefix_count": remove_prefix,
        "removed_first_id": removed_ids[0],
        "removed_last_id": removed_ids[-1],
        "episode_count_after_removal_before_fresh": len(after_removal["episodes"]),
        "next_episode_index_after_removal": after_removal["next_episode_index"],
        "stale_rejected": stale_error is not None,
        "stale_error": stale_error,
        "fresh_resolved": bool(
            fresh_result
            and fresh_result["experiment"]["status"] == "completed"
        ),
        "fresh_error": fresh_error,
        "final_cycle": final["cycles"],
        "final_episode_count": len(final["episodes"]),
    }


def _run_worker(src: str, state: Path, remove_prefix: int) -> dict:
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
            str(state),
            "--remove-prefix",
            str(remove_prefix),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-4000:])
    return json.loads(completed.stdout)


def run(
    source_state: Path,
    baseline_src: str,
    candidate_src: str,
    remove_prefix: int,
) -> dict:
    source_hash = _sha256(source_state)
    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        baseline_state = temp_path / "baseline" / "organism.json"
        candidate_state = temp_path / "candidate" / "organism.json"
        baseline_state.parent.mkdir()
        candidate_state.parent.mkdir()
        shutil.copy2(source_state, baseline_state)
        shutil.copy2(source_state, candidate_state)

        baseline = _run_worker(
            baseline_src,
            baseline_state,
            remove_prefix,
        )
        candidate = _run_worker(
            candidate_src,
            candidate_state,
            remove_prefix,
        )

    if _sha256(source_state) != source_hash:
        raise AssertionError("pinned source state changed")
    if baseline["fresh_resolved"]:
        raise AssertionError("baseline positional resolver unexpectedly survived removal")
    if "predates the inquiry" not in str(baseline["fresh_error"]):
        raise AssertionError("baseline failed for an unexpected reason")
    if not candidate["fresh_resolved"]:
        raise AssertionError("candidate rejected a genuinely fresh outcome")
    if not candidate["stale_rejected"]:
        raise AssertionError("candidate accepted a pre-inquiry outcome")
    if "predates the inquiry" not in str(candidate["stale_error"]):
        raise AssertionError("candidate stale rejection reason changed")
    if candidate["sequence_floor"] is None:
        raise AssertionError("candidate did not record a monotonic sequence floor")
    if candidate["fresh_sequence"] <= candidate["sequence_floor"]:
        raise AssertionError("fresh outcome sequence did not advance past inquiry floor")
    if baseline["initial_cycle"] != candidate["initial_cycle"]:
        raise AssertionError("baseline/candidate source cycles differ")
    if baseline["final_cycle"] != candidate["final_cycle"]:
        raise AssertionError("native APIs unexpectedly advanced organism cycles")

    return {
        "study": "native-inquiry-sequence-floor-archival-shift-v1",
        "passed": True,
        "production_base": PRODUCTION_BASE,
        "pinned_state": PINNED_STATE,
        "source_state_sha256": source_hash,
        "source_unchanged": True,
        "remove_prefix": remove_prefix,
        "baseline": baseline,
        "candidate": candidate,
        "authority": {
            "retention_enabled": False,
            "live_state_modified": False,
            "environment_actions": False,
            "phase42_credit": False,
            "external_model_api": False,
        },
        "limitations": [
            "Prefix deletion occurs only on disposable copied state; production retention remains disabled.",
            "Sequence freshness does not make archived grounding or outcome evidence discoverable by itself.",
            "Legacy inquiries without sequence floors intentionally fail closed if ledger removal is detectable.",
            "Reference-preserving archive authority and archive loading remain separate prerequisites.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--state", required=True)
    parser.add_argument("--remove-prefix", type=int, default=1000)
    parser.add_argument("--baseline-src")
    parser.add_argument("--candidate-src")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(worker(args.state, args.remove_prefix), sort_keys=True))
        return 0

    if not args.baseline_src or not args.candidate_src:
        parser.error("--baseline-src and --candidate-src are required")
    report = run(
        Path(args.state),
        args.baseline_src,
        args.candidate_src,
        args.remove_prefix,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "baseline_fresh_resolved": report["baseline"]["fresh_resolved"],
                "candidate_fresh_resolved": report["candidate"]["fresh_resolved"],
                "candidate_stale_rejected": report["candidate"]["stale_rejected"],
                "sequence_floor": report["candidate"]["sequence_floor"],
                "fresh_sequence": report["candidate"]["fresh_sequence"],
            },
            sort_keys=True,
        )
    )
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
