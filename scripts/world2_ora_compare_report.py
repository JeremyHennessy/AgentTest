from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from world2_ora_compare import compare_world2_to_control

ACTIONS = [
    "north", "interact", "south", "observe", "west", "observe",
    "east", "observe", "north", "west", "observe", "south",
    "observe", "interact", "observe", "east", "observe", "west",
    "observe", "observe", "north", "observe", "south", "observe",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Pinned, isolated synthetic sensor comparison; not native World 2 learning.")
    parser.add_argument("--state", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-blob-sha", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--output", default="artifacts/world2_ora_compare_report.json")
    args = parser.parse_args()
    for name in ("source_sha", "source_blob_sha", "code_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", getattr(args, name)):
            parser.error(f"{name} must be an exact Git SHA")
    source_path = Path(args.state)
    output = Path(args.output)
    if source_path.resolve() == output.resolve():
        parser.error("report output must not overwrite its source snapshot")
    raw = source_path.read_bytes()
    actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    if actual_blob != args.source_blob_sha:
        raise ValueError("source snapshot bytes do not match the supplied Git blob")
    source = json.loads(raw)
    if (source.get("agenda") or {}).get("started_cycle") is None or not (source.get("agenda") or {}).get("threads"):
        raise ValueError("current-Ora comparison requires an active persisted agenda; no fresh-state fallback")
    report = {
        "study_version": "world2-synthetic-sensor-comparison-v2",
        "source_growth_sha": args.source_sha,
        "source_blob_sha": actual_blob,
        "source_state_sha256": hashlib.sha256(raw).hexdigest(),
        "experiment_checkout_sha": args.code_sha,
        "source_cycle": int(source["cycles"]),
        "actions": ACTIONS,
        "cognition_enabled": False,
        "action_lab_enabled": False,
        "planning_lab_enabled": False,
        "interpretation_limit": "Fixed-script repository-shaped sensor sensitivity, not native World 2 semantics or autonomous discovery. First-sample environment admission is reported separately.",
        "comparisons": [],
    }
    print(json.dumps({key: value for key, value in report.items() if key != "comparisons"}, sort_keys=True), flush=True)
    for seed in args.seeds:
        result = compare_world2_to_control(source, seed=seed, actions=ACTIONS)
        report["comparisons"].append(result)
        print(json.dumps({"completed_seed": seed, "control": result["control"], "world2": result["world2"]}, sort_keys=True), flush=True)
    if source_path.read_bytes() != raw or json.loads(raw) != source:
        raise RuntimeError("comparison mutated its source snapshot")
    report["source_unchanged"] = True
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
