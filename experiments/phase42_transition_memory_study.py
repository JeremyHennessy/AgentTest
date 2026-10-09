"""Read-only, exact-growth-original audit for Phase 42 transition memory.

The adapter alone imports the protected current-world transition oracle, solely
to reject invalid historical receipts. The learned model receives only public
before/action/after rows after complete validation and ordering.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from agenttest.action_lab import (
    ACTION_ORDER, STATEFUL_WORLD_VERSION, apply_bounded_action,
)
from agenttest.transition_memory import VERSION, delta_key, evaluate_history, digest

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_NATIVE_OBSERVATIONS = 4096


def extract_verified_native(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("original state must be a mapping")
    lab = state.get("planning_lab")
    if not isinstance(lab, dict) or lab.get("world_version") != STATEFUL_WORLD_VERSION:
        raise ValueError("the original active world is not the authorized stateful world")
    bounds = lab.get("bounds")
    if type(bounds) is not int or bounds != 2:
        raise ValueError("original 5x5 world bounds are unsupported or changed")
    history = lab.get("transition_observations")
    if not isinstance(history, list) or len(history) > MAX_NATIVE_OBSERVATIONS * 2:
        raise ValueError("unexpected or excessive original observation count")
    rows = []
    incompatible = 0
    seen: set[str] = set()
    missing_stored_delta = 0
    for item in history:
        if not isinstance(item, dict):
            raise ValueError("malformed native historical observation")
        if item.get("world_version") != STATEFUL_WORLD_VERSION:
            incompatible += 1
            continue
        ident = item.get("source_id")
        before, after, action = item.get("before"), item.get("after"), item.get("action")
        blocked = item.get("blocked")
        if (not isinstance(ident, str) or not ident or ident in seen
                or action not in ACTION_ORDER or type(blocked) is not bool):
            raise ValueError("duplicate or invalid original stateful-world receipt")
        seen.add(ident)
        delta = delta_key(before, after)
        actual = apply_bounded_action(
            before, action, bounds=bounds, world_version=STATEFUL_WORLD_VERSION,
        )
        if actual["after"] != after or actual["blocked"] != blocked:
            raise ValueError(f"protected native receipt replay mismatch for {ident}")
        observed_delta = item.get("delta")
        if observed_delta is None:
            missing_stored_delta += 1
        elif observed_delta != actual["delta"]:
            raise ValueError("original stored delta contradicts its observed transition")
        rows.append({
            "id": ident,
            "index": len(rows) + 1,
            "before": list(before),
            "after": list(after),
            "action": action,
            "world_version": STATEFUL_WORLD_VERSION,
        })
    if len(rows) > MAX_NATIVE_OBSERVATIONS:
        raise ValueError("eligible source exceeds bounded memory")
    return {
        "rows": rows,
        "original_cycle": state.get("cycles"),
        "compatible_count": len(rows),
        "incompatible_world_count": incompatible,
        "missing_optional_stored_delta_count": missing_stored_delta,
        "complete_eligible_history_sha256": digest(rows),
    }


def inspect_original_bytes(
    raw: bytes, *, original_commit: str, original_blob: str, sha256: str,
) -> dict[str, Any]:
    if (not HEX40.fullmatch(original_commit)
            or not HEX40.fullmatch(original_blob)
            or not HEX64.fullmatch(sha256)):
        raise ValueError("expected exact Git source identifiers")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("original snapshot exceeds copy-only size limit")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
    if actual_sha256 != sha256 or blob != original_blob:
        raise ValueError("original snapshot bytes do not match both exact digests")
    try:
        state = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid original raw snapshot") from exc
    verified = extract_verified_native(state)
    evaluation = evaluate_history(verified["rows"])
    return {
        "version": VERSION,
        "source": {
            "repository": "JeremyHennessy/AgentTest",
            "branch": "autonomous/growth",
            "exact_commit": original_commit,
            "original_state_blob": original_blob,
            "original_state_sha256": actual_sha256,
            "original_state_bytes": len(raw),
            "original_cycle": verified["original_cycle"],
        },
        "admission": {
            field: value for field, value in verified.items() if field != "rows"
        },
        "evaluation": evaluation,
        "original_state_modified": False,
        "scientific_claim": "retrospective_prediction_only_not_agent_benefit",
        "original_ora_activation": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--original-commit", required=True)
    parser.add_argument("--original-blob", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = args.state.absolute()
    destination = args.output.absolute()
    if not state.is_file() or state.is_symlink():
        raise ValueError("input must be a concrete immutable original source copy")
    if state == destination or destination.is_symlink() or not destination.parent.is_dir():
        raise ValueError("output must use a separate already-existing scratch directory")
    initial = state.read_bytes()
    report = inspect_original_bytes(
        initial,
        original_commit=args.original_commit, original_blob=args.original_blob,
        sha256=args.expected_sha256,
    )
    if state.read_bytes() != initial:
        raise RuntimeError("original source bytes changed during read-only replay")
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    destination.write_text(payload, encoding="utf-8")
    if report["evaluation"]["status"] == "INSUFFICIENT":
        raise SystemExit("no admitted study: insufficient authentic original-world events")
    print(json.dumps({
        "original_cycle": report["source"]["original_cycle"],
        "eligible": report["admission"]["compatible_count"],
        "incompatible_worlds": report["admission"]["incompatible_world_count"],
        "training": report["evaluation"]["training_rows"],
        "heldout": report["evaluation"]["evaluation_rows"],
        "status": report["evaluation"]["status"],
        "brier": {key: value["mean_multiclass_brier"] for key, value in
                  report["evaluation"]["metrics"].items()},
        "source_unchanged": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
