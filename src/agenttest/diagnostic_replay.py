from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from .core import AgentCore
from .state import StateStore

DIAGNOSTIC_VERSION = "deterministic-replay-v1"

_VOLATILE_KEYS = {
    "created_at",
    "updated_at",
    "time",
    "observed_at",
    "evaluated_at",
    "completed_at",
}


def _observation(lines: int) -> dict[str, Any]:
    return {
        "sensor": "deterministic-replay",
        "branch": "diagnostic",
        "tracked_files": 10,
        "python_files": 4,
        "python_source_lines": lines,
        "test_files": 1,
        "working_tree_clean": True,
    }


def normalize(value: Any, key: str | None = None) -> Any:
    if key in _VOLATILE_KEYS:
        return "<volatile>"
    if isinstance(value, dict):
        return {
            str(item_key): normalize(item_value, str(item_key))
            for item_key, item_value in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _first_difference(left: Any, right: Any, path: str = "$") -> dict[str, Any] | None:
    if type(left) is not type(right):
        return {
            "path": path,
            "left": left,
            "right": right,
            "reason": "type_mismatch",
        }

    if isinstance(left, dict):
        left_keys = set(left)
        right_keys = set(right)
        if left_keys != right_keys:
            return {
                "path": path,
                "left_only": sorted(left_keys - right_keys),
                "right_only": sorted(right_keys - left_keys),
                "reason": "key_mismatch",
            }
        for key in sorted(left):
            difference = _first_difference(left[key], right[key], f"{path}.{key}")
            if difference is not None:
                return difference
        return None

    if isinstance(left, list):
        if len(left) != len(right):
            return {
                "path": path,
                "left_length": len(left),
                "right_length": len(right),
                "reason": "length_mismatch",
            }
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            difference = _first_difference(
                left_item,
                right_item,
                f"{path}[{index}]",
            )
            if difference is not None:
                return difference
        return None

    if left != right:
        return {
            "path": path,
            "left": left,
            "right": right,
            "reason": "value_mismatch",
        }
    return None


def run_fixture() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        store = StateStore(Path(directory) / "organism.json")
        core = AgentCore(store)

        first = core.cycle(
            "replay alpha",
            observation=_observation(100),
            cognition=False,
        )
        second = core.cycle(
            "replay alpha",
            observation=_observation(100),
            cognition=False,
        )
        third = core.cycle(
            "replay beta",
            observation=_observation(120),
            cognition=False,
        )
        outcome = core.record_outcome(
            first["experiment"]["id"],
            "diagnostic-supported",
            0.8,
        )

        journal = []
        if store.journal_path.exists():
            for line in store.journal_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    journal.append(json.loads(line))

        rendered = {
            "cycles": [first, second, third],
            "recorded_outcome": outcome,
            "state": store.load(),
            "journal": journal,
        }
        normalized = normalize(rendered)
        return {
            "normalized": normalized,
            "digest": _digest(normalized),
        }


def compare_replays() -> dict[str, Any]:
    first = run_fixture()
    second = run_fixture()
    difference = _first_difference(first["normalized"], second["normalized"])
    stable = difference is None and first["digest"] == second["digest"]
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "outcome": "stable" if stable else "divergent",
        "run_count": 2,
        "digest_a": first["digest"],
        "digest_b": second["digest"],
        "first_difference": difference,
        "normalization": {
            "volatile_keys": sorted(_VOLATILE_KEYS),
            "other_fields_preserved": True,
        },
        "isolated_temp_state": True,
    }
