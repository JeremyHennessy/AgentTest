from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .state import utc_now

COMPARABLE_FIELDS = (
    "branch",
    "tracked_files",
    "python_files",
    "python_source_lines",
    "test_files",
    "working_tree_clean",
)


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _fingerprint(snapshot: dict[str, Any]) -> str:
    stable = {field: snapshot.get(field) for field in COMPARABLE_FIELDS}
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def repository_snapshot(root: str | Path = ".") -> dict[str, Any]:
    path = Path(root).resolve()
    tracked_raw = _git(path, "ls-files")
    tracked = [] if tracked_raw is None else [line for line in tracked_raw.splitlines() if line]

    python_paths = [item for item in tracked if item.endswith(".py")]
    source_lines = 0
    for relative in python_paths:
        candidate = path / relative
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                source_lines += sum(1 for _ in handle)
        except (OSError, UnicodeError):
            continue

    status = _git(path, "status", "--porcelain")
    head = _git(path, "rev-parse", "HEAD")
    branch = _git(path, "branch", "--show-current")

    snapshot = {
        "sensor": "repository-v1",
        "observed_at": utc_now(),
        "git_available": head is not None,
        "head": head,
        "branch": branch,
        "tracked_files": len(tracked),
        "python_files": len(python_paths),
        "python_source_lines": source_lines,
        "test_files": len(
            [item for item in python_paths if item.startswith("tests/") or "/tests/" in item]
        ),
        "working_tree_clean": status == "" if status is not None else None,
    }
    snapshot["fingerprint"] = _fingerprint(snapshot)
    return snapshot


def changed_fields(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if previous is None:
        return {}
    changes: dict[str, dict[str, Any]] = {}
    for field in COMPARABLE_FIELDS:
        before = previous.get(field)
        after = current.get(field)
        if before != after:
            changes[field] = {"before": before, "after": after}
    return changes
