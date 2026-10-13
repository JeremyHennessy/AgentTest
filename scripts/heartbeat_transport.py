"""Git-backed heartbeat transport. No cognitive work occurs in publish.

The sidecar is a bounded current pointer; exact request receipts stay in Git
history. A local return value or commit is never a remote durability receipt.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

VERSION = "heartbeat-transport-v1"
OP_PATH = "state/heartbeat_operation.json"
REMOTE_REF = "refs/remotes/origin/autonomous/growth"
BRANCH = "autonomous/growth"
MAX_RECORD_BYTES = 64 * 1024


class TransportError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if check and result.returncode:
        raise TransportError("git_failed:" + " ".join(args[:2]))
    return result


def _sha(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise TransportError("invalid_commit_identity")
    return value


def _request(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,200}", value):
        raise TransportError("invalid_request_identity")
    return value


def _head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD").stdout.decode().strip()


def _runtime() -> dict:
    return {"implementation": platform.python_implementation(), "python": platform.python_version()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(raw: bytes) -> dict:
    if len(raw) > MAX_RECORD_BYTES:
        raise TransportError("transport_record_too_large")
    try:
        row = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise TransportError("invalid_transport_record") from error
    if not isinstance(row, dict) or row.get("version") != VERSION:
        raise TransportError("transport_version_mismatch")
    if row.get("status") not in ("pending", "completed", "abandoned"):
        raise TransportError("invalid_transport_status")
    if row.get("mode") not in ("ordinary", "current-world-investigation"):
        raise TransportError("unsupported_heartbeat_mode")
    if row.get("payload") != _payload(row["mode"]):
        raise TransportError("transport_payload_mismatch")
    if type(row.get("input_cycle")) is not int or row["input_cycle"] < 0:
        raise TransportError("invalid_input_cycle")
    _request(row.get("request_id", ""))
    _sha(row.get("source_sha", ""))
    _sha(row.get("input_commit", ""))
    if type(row.get("original_run_id")) is not int or row["original_run_id"] <= 0:
        raise TransportError("invalid_original_run_identity")
    if row.get("content_hash") != digest({k: v for k, v in row.items() if k != "content_hash"}):
        raise TransportError("transport_record_hash_mismatch")
    return row


def _read(root: Path) -> dict | None:
    path = root / OP_PATH
    return _record(path.read_bytes()) if path.exists() else None


def _seal(row: dict) -> dict:
    row["content_hash"] = digest({k: v for k, v in row.items() if k != "content_hash"})
    return row


def _write(root: Path, row: dict) -> None:
    payload = canonical(_seal(row)) + b"\n"
    _record(payload)
    path = root / OP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _commit_record(root: Path, commit: str) -> dict | None:
    # In a partial clone, showing an existing blob can fail during a lazy fetch.
    # Establish absence from the tree; an unreadable existing record is blocked.
    entry = _git(root, "ls-tree", "-z", commit, "--", OP_PATH).stdout
    if not entry:
        return None
    if len(entry.split(b"\0")) != 2 or not entry.startswith(b"100644 blob "):
        raise TransportError("unsupported_transport_record_entry")
    return _record(_git(root, "show", f"{commit}:{OP_PATH}").stdout)


def _state_manifest(root: Path, commit: str | None = None) -> dict:
    result = {}
    if commit is not None:
        for row in _git(root, "ls-tree", "-rz", commit, "--", "state/").stdout.split(b"\0"):
            if not row:
                continue
            header, name = row.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            path = name.decode()
            if path == OP_PATH:
                continue
            if kind != "blob" or mode not in ("100644", "100755"):
                raise TransportError("unsupported_state_file")
            result[path] = [mode, oid]
        return result
    names = set(_git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "state/").stdout.split(b"\0"))
    for name in sorted(names):
        if not name or name.decode() == OP_PATH:
            continue
        relative = name.decode()
        path = root / relative
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise TransportError("unsupported_state_file")
        info = path.stat()
        h = hashlib.sha1(f"blob {info.st_size}\0".encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        result[relative] = ["100755" if info.st_mode & 0o111 else "100644", h.hexdigest()]
    return result


def _state_hash(root: Path, commit: str | None = None) -> str:
    return digest(_state_manifest(root, commit))


def _source(root: Path, source_sha: str) -> None:
    _sha(source_sha)
    scope = ("--", ".", ":(exclude)state/**")
    for comparison in ((source_sha, "HEAD"), (source_sha,)):
        if _git(root, "diff", "--quiet", *comparison, *scope, check=False).returncode:
            raise TransportError("heartbeat_source_mismatch")
    others = _git(root, "ls-files", "--others", "-z").stdout.split(b"\0")
    if any(name and not name.startswith(b"state/") for name in others):
        raise TransportError("untracked_execution_source")


def _clean(root: Path) -> None:
    if _git(root, "status", "--porcelain", "--untracked-files=all").stdout.strip():
        raise TransportError("heartbeat_requires_clean_checkout")


def _remote(root: Path, *, shallow: bool = False) -> str:
    # Never conceal a failed fetch behind a stale remote-tracking ref.
    if shallow:
        depth = ("--depth=1",)
    elif _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        # A watchdog starts with only the current pointer. Historical replay
        # explicitly upgrades its metadata before proving an old ID absent.
        depth = ("--unshallow",)
    else:
        depth = ()
    _git(root, "fetch", "--no-tags", "--filter=blob:none", *depth, "origin", f"refs/heads/{BRANCH}:{REMOTE_REF}")
    return _git(root, "rev-parse", REMOTE_REF).stdout.decode().strip()


def _terminal_at(root: Path, commit: str, request_id: str) -> dict | None:
    row = _commit_record(root, commit)
    if row is None or row["request_id"] != request_id or row["status"] == "pending":
        return None
    if row["status"] == "completed" and row.get("result_state_hash") != _state_hash(root, commit):
        raise TransportError("historical_result_state_mismatch")
    return row


def _historical(root: Path, request_id: str, head: str = "HEAD") -> dict | None:
    # Publication requires this exact trailer, allowing bounded metadata search
    # rather than loading every historical organism or journal.
    marker = "Heartbeat-Request: " + _request(request_id)
    commits = _git(root, "log", "--format=%H", "--fixed-strings", "--grep=" + marker,
                   head, "--", OP_PATH).stdout.decode().splitlines()
    matches = []
    for commit in commits:
        row = _terminal_at(root, commit, request_id)
        if row is not None:
            matches.append((row["content_hash"], row))
    identities = {identity for identity, _ in matches}
    if len(identities) > 1:
        raise TransportError("conflicting_historical_request_receipts")
    if not matches and _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        raise TransportError("historical_ticket_requires_complete_git_history")
    return matches[0][1] if matches else None


def next_request_id(row: dict | None, head: str) -> str:
    if row and row["status"] == "pending":
        return row["request_id"]
    anchor = row["content_hash"] if row else _sha(head)
    return "heartbeat:v1:" + digest({"version": VERSION, "predecessor": anchor})


def inspect(root: Path, request_id: str | None = None, *, remote: bool = False, shallow: bool = False) -> dict:
    if shallow and (not remote or request_id):
        raise TransportError("shallow_inspection_requires_remote_current_pointer_only")
    head = _remote(root, shallow=shallow) if remote else _head(root)
    row = _commit_record(root, head) if remote else _read(root)
    result = {"status": "pending" if row and row["status"] == "pending" else "ready",
              "operation": row, "next_request_id": next_request_id(row, head), "head": head,
              "ticket_since": row["created_at"] if row else _git(root, "show", "-s", "--format=%cI", head).stdout.decode().strip()}
    if request_id:
        _request(request_id)
        found = row if row and row["request_id"] == request_id else _historical(root, request_id, head)
        result["request_status"] = found["status"] if found else "unseen"
    return result


def writer_check(root: Path) -> dict:
    return state_writer_check(root / "state/organism.json")


def state_writer_check(state_path: Path) -> dict:
    """Protect the actual state sibling even under an older writer workflow."""
    path = state_path.resolve().with_name("heartbeat_operation.json")
    row = _record(path.read_bytes()) if path.exists() else None
    if row and row["status"] == "pending":
        return {"status": "deferred", "reason": "heartbeat_pending", "request_id": row["request_id"],
                "original_run_id": row["original_run_id"]}
    return {"status": "ready"}


def _agent_import(root: Path) -> None:
    sys.path.insert(0, str(root / "src"))


def _payload(mode: str) -> dict:
    if mode not in ("ordinary", "current-world-investigation"):
        raise TransportError("unsupported_heartbeat_mode")
    return {"mode": mode, "planning_lab": True, "strict_experiment_admission": True,
            "cognition": False, "stimulus": "autonomous heartbeat", "observation_supplied": True}


def _input(root: Path, row: dict, source_sha: str, claim_commit: str | None = None) -> None:
    if row["source_sha"] != source_sha:
        raise TransportError("pending_source_mismatch")
    if row.get("runtime") != _runtime():
        raise TransportError("pending_runtime_mismatch")
    _source(root, source_sha)
    _clean(root)
    if row.get("input_state_hash") != _state_hash(root):
        raise TransportError("pending_input_state_mismatch")
    if claim_commit is not None:
        _sha(claim_commit)
        if _head(root) != claim_commit or _remote(root) != claim_commit:
            raise TransportError("claim_not_at_exact_remote_head")
        if _commit_record(root, claim_commit) != row:
            raise TransportError("claim_record_not_at_remote_head")
        if _git(root, "rev-parse", claim_commit + "^").stdout.decode().strip() != row["input_commit"]:
            raise TransportError("claim_parent_mismatch")


def claim(root: Path, request_id: str, source_sha: str, run_id: int, mode: str) -> dict:
    _request(request_id)
    _sha(source_sha)
    if run_id <= 0:
        raise TransportError("invalid_original_run_identity")
    row = _read(root)
    historical = _historical(root, request_id)
    if historical:
        if historical["status"] == "abandoned":
            raise TransportError("request_was_abandoned")
        return {"status": "already_completed", "request_id": request_id}
    if row and row["request_id"] == request_id and row["status"] == "completed":
        if row.get("result_state_hash") != _state_hash(root):
            raise TransportError("unpublished_completed_result_requires_publication")
        raise TransportError("completed_receipt_missing_published_history")
    if row and row["status"] == "pending":
        if row["original_run_id"] != run_id:
            raise TransportError("pending_requires_original_run")
        if row["request_id"] != request_id:
            raise TransportError("different_heartbeat_pending")
        if row.get("payload") != _payload(mode):
            raise TransportError("pending_payload_mismatch")
        _input(root, row, source_sha, _head(root))
        return {"status": "already_claimed", "request_id": request_id, "input_commit": row["input_commit"],
                "claim_commit": _head(root), "original_run_id": row["original_run_id"]}
    if row is None:
        # The first ticket belongs to the freshly fetched remote input, not a
        # later local source merge or an arbitrary dispatch-provided identity.
        genesis_head = _remote(root)
        if _commit_record(root, genesis_head) is not None:
            raise TransportError("genesis_checkout_missing_remote_operation")
        if _git(root, "merge-base", "--is-ancestor", genesis_head, "HEAD", check=False).returncode:
            raise TransportError("genesis_checkout_does_not_extend_remote")
        expected_request = next_request_id(None, genesis_head)
    else:
        expected_request = next_request_id(row, _head(root))
    if request_id != expected_request:
        raise TransportError("stale_or_unrelated_heartbeat_ticket")
    _source(root, source_sha)
    _clean(root)
    _agent_import(root)
    from agenttest.perception import repository_snapshot
    observation = repository_snapshot(root)
    state_path = root / "state/organism.json"
    from agenttest.snapshot_storage import read_snapshot_bytes
    state = json.loads(read_snapshot_bytes(state_path))
    bounded = state.get("current_world_heartbeat") or {}
    if bounded.get("pending"):
        raise TransportError("legacy_bounded_pending_requires_original_recovery")
    base = _head(root)
    journal = root / "state/journal.jsonl"
    if mode == "current-world-investigation":
        from agenttest.heartbeat_claim import claim_heartbeat
        result = claim_heartbeat(state_path, request_id)
        if result["status"] != "created":
            raise TransportError("bounded_claim_did_not_create_matching_intent")
    row = {"version": VERSION, "status": "pending", "request_id": request_id,
           "original_run_id": run_id, "source_sha": source_sha, "input_commit": base,
           "input_cycle": state.get("cycles", 0), "runtime": _runtime(), "mode": mode,
           "payload": _payload(mode), "observation": observation, "cycle_time": _now(),
           "input_state_hash": _state_hash(root), "input_journal_size": journal.stat().st_size if journal.exists() else 0,
           "created_at": _now()}
    _write(root, row)
    return {"status": "created", "request_id": request_id, "input_commit": base,
            "original_run_id": run_id, "commit_trailer": "Heartbeat-Request: " + request_id}


def cycle(root: Path, request_id: str, source_sha: str, claim_commit: str) -> dict:
    row = _read(root)
    if row is None or row["request_id"] != request_id or row["status"] != "pending":
        raise TransportError("matching_pending_request_required")
    _input(root, row, source_sha, claim_commit)
    _agent_import(root)
    from agenttest.core import AgentCore
    from agenttest.state import StateStore
    extra = {}
    if row["mode"] == "current-world-investigation":
        extra = {"current_world_investigation": True, "heartbeat_request_id": request_id,
                 "heartbeat_claim_commit": claim_commit}
    elif row["mode"] != "ordinary":
        raise TransportError("unsupported_heartbeat_mode")
    result = AgentCore(StateStore(root / "state/organism.json")).cycle(
        "autonomous heartbeat", observation=row["observation"], cognition=False,
        strict_experiment_admission=True, planning_lab=True,
        _now_override=row["cycle_time"], **extra)
    return {"status": "computed_locally", "request_id": request_id, "cycle": result["cycle"],
            "durability": "awaiting_verified_remote_commit"}


def complete(root: Path, request_id: str, source_sha: str, claim_commit: str) -> dict:
    row = _read(root)
    if row is None or row["request_id"] != request_id or row["status"] != "pending":
        raise TransportError("matching_pending_request_required")
    if row["source_sha"] != source_sha or row["runtime"] != _runtime():
        raise TransportError("completion_execution_identity_mismatch")
    _source(root, source_sha)
    _sha(claim_commit)
    if _head(root) != claim_commit or _commit_record(root, claim_commit) != row:
        raise TransportError("completion_claim_commit_mismatch")
    if _state_hash(root, claim_commit) != row["input_state_hash"]:
        raise TransportError("completion_claim_input_mismatch")
    _agent_import(root)
    from agenttest.snapshot_storage import read_snapshot_bytes
    state = json.loads(read_snapshot_bytes(root / "state/organism.json"))
    if state.get("cycles") != row["input_cycle"] + 1:
        raise TransportError("completion_must_contain_exactly_one_cycle")
    # Verify preserved journal prefix against the exact claimed Git blob.
    previous = _git(root, "show", f"{claim_commit}:state/journal.jsonl", check=False)
    before = previous.stdout if previous.returncode == 0 else b""
    with (root / "state/journal.jsonl").open("rb") as stream:
        if len(before) != row["input_journal_size"] or stream.read(len(before)) != before:
            raise TransportError("input_journal_history_changed")
        appended = stream.read()
    try:
        events = [json.loads(line) for line in appended.splitlines() if line.strip()]
    except ValueError as error:
        raise TransportError("invalid_appended_journal") from error
    cycles = [event for event in events if event.get("event") == "cycle"]
    if len(cycles) != 1 or cycles[0].get("cycle") != state["cycles"]:
        raise TransportError("completion_cycle_event_mismatch")
    if row["mode"] == "current-world-investigation":
        _agent_import(root)
        from agenttest.heartbeat_claim import verify_completed
        verify_completed(root / "state/organism.json", request_id, require_current=True)
    claim_hash = row["content_hash"]
    row.update(status="completed", claim_content_hash=claim_hash, claim_commit=claim_commit,
               result_cycle=state["cycles"], result_state_hash=_state_hash(root),
               result_event_hash=digest(cycles[0]))
    _write(root, row)
    return {"status": "completed_locally", "request_id": request_id, "result_cycle": state["cycles"],
            "commit_trailer": "Heartbeat-Request: " + request_id,
            "durability": "awaiting_verified_remote_commit"}


def publish(root: Path, candidate: str, expected_parent: str, *, attempts: int = 4,
            sleeper=time.sleep) -> dict:
    _sha(candidate)
    _sha(expected_parent)
    if attempts < 1 or attempts > 8:
        raise TransportError("invalid_publish_attempt_bound")
    if candidate == expected_parent or _git(root, "merge-base", "--is-ancestor", expected_parent, candidate, check=False).returncode:
        raise TransportError("candidate_does_not_extend_expected_parent")
    row = _commit_record(root, candidate)
    prior = _commit_record(root, expected_parent)
    if row == prior and row and row["status"] == "pending":
        raise TransportError("unrelated_writer_cannot_publish_over_pending")
    if row is not None and row != prior:
        message = _git(root, "show", "-s", "--format=%B", candidate).stdout.decode().splitlines()
        if "Heartbeat-Request: " + row["request_id"] not in message:
            raise TransportError("candidate_request_trailer_missing")
        wanted = "input_state_hash" if row["status"] == "pending" else "result_state_hash"
        if row["status"] != "abandoned" and row.get(wanted) != _state_hash(root, candidate):
            raise TransportError("candidate_state_receipt_mismatch")
    for attempt in range(1, attempts + 1):
        try:
            remote = _remote(root)
        except TransportError:
            remote = None
        if remote is not None:
            contains = _git(root, "merge-base", "--is-ancestor", candidate, remote, check=False).returncode == 0
            if contains:
                return {"status": "published", "candidate": candidate, "remote_head": remote, "attempts": attempt}
            if remote != expected_parent:
                raise TransportError("remote_advanced_incompatibly")
            _git(root, "push", "origin", f"{candidate}:refs/heads/{BRANCH}", check=False)
            try:
                remote = _remote(root)
            except TransportError:
                remote = None
            if remote is not None:
                if _git(root, "merge-base", "--is-ancestor", candidate, remote, check=False).returncode == 0:
                    return {"status": "published", "candidate": candidate, "remote_head": remote, "attempts": attempt}
                if remote != expected_parent:
                    raise TransportError("remote_advanced_incompatibly")
        if attempt < attempts:
            sleeper(min(3 * attempt, 12))
    raise TransportError("publication_unconfirmed_same_candidate_retained")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "claim", "cycle", "complete", "publish", "writer-check"):
        command = sub.add_parser(name)
        command.add_argument("--root", type=Path, default=Path.cwd())
        if name in ("inspect", "claim", "cycle", "complete"):
            command.add_argument("--request-id", required=name != "inspect")
        if name in ("claim", "cycle", "complete"):
            command.add_argument("--source-sha", required=True)
        if name in ("cycle", "complete"):
            command.add_argument("--claim-commit", required=True)
        if name == "inspect":
            command.add_argument("--remote", action="store_true")
            command.add_argument("--shallow", action="store_true")
        if name == "claim":
            command.add_argument("--run-id", type=int, required=True)
            command.add_argument("--mode", choices=("ordinary", "current-world-investigation"), default="ordinary")
        if name == "publish":
            command.add_argument("--candidate", required=True)
            command.add_argument("--expected-parent", required=True)
            command.add_argument("--attempts", type=int, default=4)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "inspect":
            result = inspect(root, args.request_id, remote=args.remote, shallow=args.shallow)
        elif args.command == "claim":
            result = claim(root, args.request_id, args.source_sha, args.run_id, args.mode)
        elif args.command == "cycle":
            result = cycle(root, args.request_id, args.source_sha, args.claim_commit)
        elif args.command == "complete":
            result = complete(root, args.request_id, args.source_sha, args.claim_commit)
        elif args.command == "publish":
            result = publish(root, args.candidate, args.expected_parent, attempts=args.attempts)
        else:
            result = writer_check(root)
        print(json.dumps(result, sort_keys=True))
        if result["status"] == "deferred":
            raise SystemExit(75)
    except (TransportError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
