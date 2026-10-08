"""Proposed maintenance entrypoint, to run ONLY in verified exclusive GH Actions.

This script mutates an isolated local checkout and does NOT publish it. The
workflow must use the main source-verification guard and exact-parent GitHub
publisher after all independent tests pass. Unused until properly integrated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from agenttest.journal_tail_rotation import (
    JournalIntegrityError, ROTATE_AT_BYTES, publication_preflight, rotate, verify, export_logical,
)

SHA = re.compile(r"[0-9a-f]{40}\Z")
BRANCH_REF = "refs/remotes/origin/autonomous/growth"


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, check=False)
    if check and result.returncode:
        raise JournalIntegrityError("git_check_failed:" + " ".join(args[:2]))
    return result.stdout.strip()


def authority(root: Path, expected_remote_head: str) -> dict:
    if not SHA.fullmatch(expected_remote_head):
        raise JournalIntegrityError("invalid_expected_remote_head")
    if git(root, "rev-parse", BRANCH_REF) != expected_remote_head:
        raise JournalIntegrityError("remote_tracking_ref_changed")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise JournalIntegrityError("dirty_checkout_before_rotation")
    check = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor",
                            expected_remote_head, "HEAD"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)
    if check.returncode:
        raise JournalIntegrityError("candidate_does_not_extend_growth_head")
    # Source upgrades may be merged before maintenance, but must not alter ANY
    # original state file. Journal/op checks alone would miss a silently changed
    # organism, diagnostics, or interaction receipt from a main-side merge.
    state_diff = git(root, "diff", "--name-only", expected_remote_head, "HEAD", "--", "state/")
    if state_diff:
        raise JournalIntegrityError("source_merge_changed_original_state:" + state_diff.splitlines()[0])
    path = root / "state/journal.jsonl"
    original_blob = git(root, "rev-parse", expected_remote_head + ":state/journal.jsonl")
    present_blob = git(root, "hash-object", str(path))
    if original_blob != present_blob:
        raise JournalIntegrityError("active_tail_is_not_original_remote_blob")
    operation = root / "state/heartbeat_operation.json"
    operation_blob = git(root, "rev-parse", expected_remote_head + ":state/heartbeat_operation.json")
    if operation_blob != git(root, "hash-object", str(operation)):
        raise JournalIntegrityError("receipt_differs_from_remote")
    return {"expected_remote_head": expected_remote_head,
            "current_source_head": git(root, "rev-parse", "HEAD"),
            "original_journal_blob": original_blob}


def execute(root: Path, expected_remote_head: str, min_bytes: int) -> dict:
    pinned = authority(root, expected_remote_head)
    publication_preflight(root / "state")
    before = verify(root / "state")
    status = json.loads((root / "state/heartbeat_operation.json").read_bytes())
    if status.get("status") != "completed" or type(status.get("result_cycle")) is not int:
        raise JournalIntegrityError("not_between_heartbeat_claims")
    report = rotate(root / "state", expected_active_sha256=before["active_sha256"],
                    expected_cycle=status["result_cycle"], min_bytes=min_bytes)
    publication_preflight(root / "state")
    sealed = root / "state" / report["archive"]["name"]
    if pinned["original_journal_blob"] != git(root, "hash-object", str(sealed)):
        raise JournalIntegrityError("archived_git_blob_mismatch")
    return {**pinned, **report,
            "publication_state": "NOT_PUBLISHED_LOCAL_WORKTREE_ONLY",
            "archive_verified_same_git_blob": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("rotate", "verify", "export"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-remote-head", default=None)
    parser.add_argument("--min-bytes", type=int, default=ROTATE_AT_BYTES)
    parser.add_argument("--destination", type=Path, default=None)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            result = {**verify(args.root / "state"),
                      "publication": publication_preflight(args.root / "state")}
        elif args.command == "export":
            if args.destination is None:
                raise JournalIntegrityError("export_destination_required")
            result = export_logical(args.root / "state", args.destination)
        else:
            if args.expected_remote_head is None:
                raise JournalIntegrityError("expected_remote_head_required")
            result = execute(args.root, args.expected_remote_head, args.min_bytes)
        print(json.dumps(result, sort_keys=True))
    except (JournalIntegrityError, OSError, ValueError) as error:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(error)}), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
