"""Copy-only proof-of-concept for lossless Ora journal-tail rotation.

Not deployed. Rotation keeps the physical name `journal.jsonl` as the ACTIVE
heartbeat-writer tail, seals its old exact bytes under a distinct name, and
adds a checked manifest for ordered logical-history reconstruction. Git
workflow serialization, exact-head CAS and verified source are required from
the caller; this module deliberately does not invent remote authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile

from .snapshot_storage import read_snapshot_bytes
from typing import Iterator

MANIFEST = "journal-archives.json"
ACTIVE = "journal.jsonl"
ARCHIVE_RE = re.compile(r"journal-sealed-(\d{6})\.jsonl\Z")
VERSION = "ora-journal-tail-v1"
GIT_HARD_BLOB_BYTES = 100 * 1024 * 1024
SAFE_MAX_BLOB_BYTES = 96 * 1024 * 1024
ROTATE_AT_BYTES = 80 * 1024 * 1024
CHUNK = 1024 * 1024


class JournalIntegrityError(RuntimeError):
    pass


def _regular(path: Path, *, required: bool = True) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if required:
            raise JournalIntegrityError("missing_file:" + path.name)
        return False
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise JournalIntegrityError("unsafe_file:" + path.name)
    return True


def _jsonl_file(path: Path) -> tuple[int, str, int]:
    """Return (bytes, SHA-256, parsed-event count) without buffering the file."""
    _regular(path)
    digest = hashlib.sha256()
    total = 0
    records = 0
    with path.open("rb") as stream:
        for line in stream:
            digest.update(line)
            total += len(line)
            if not line.endswith(b"\n"):
                raise JournalIntegrityError("incomplete_event:" + path.name)
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except (UnicodeError, ValueError) as error:
                raise JournalIntegrityError("invalid_event:" + path.name) from error
            if not isinstance(value, dict):
                raise JournalIntegrityError("invalid_event_type:" + path.name)
            records += 1
    if total >= GIT_HARD_BLOB_BYTES:
        raise JournalIntegrityError("over_git_blob_limit:" + path.name)
    return total, digest.hexdigest(), records


def _validated_manifest(state_dir: Path) -> list[dict]:
    manifest_path = state_dir / MANIFEST
    if not _regular(manifest_path, required=False):
        if any(ARCHIVE_RE.fullmatch(p.name) for p in state_dir.iterdir()):
            raise JournalIntegrityError("orphan_archive_without_manifest")
        return []
    try:
        manifest = json.loads(manifest_path.read_bytes())
    except (ValueError, UnicodeError) as error:
        raise JournalIntegrityError("invalid_manifest") from error
    if not isinstance(manifest, dict) or set(manifest) != {"version", "archives"} or manifest.get("version") != VERSION:
        raise JournalIntegrityError("unsupported_manifest")
    entries = manifest["archives"]
    if not isinstance(entries, list) or not entries:
        raise JournalIntegrityError("invalid_archive_list")
    known = set()
    for index, row in enumerate(entries, start=1):
        if not isinstance(row, dict) or set(row) != {"name", "bytes", "sha256", "events"}:
            raise JournalIntegrityError("invalid_archive_entry")
        name = f"journal-sealed-{index:06d}.jsonl"
        if row["name"] != name or name in known:
            raise JournalIntegrityError("noncanonical_archive_sequence")
        known.add(name)
        if any(type(row[k]) is not int or row[k] < 0 for k in ("bytes", "events")):
            raise JournalIntegrityError("invalid_archive_size")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise JournalIntegrityError("invalid_archive_hash")
        if tuple(row[k] for k in ("bytes", "sha256", "events")) != _jsonl_file(state_dir / name):
            raise JournalIntegrityError("archive_changed:" + name)
    extras = {p.name for p in state_dir.iterdir() if ARCHIVE_RE.fullmatch(p.name)} - known
    if extras:
        raise JournalIntegrityError("unrecorded_archive:" + sorted(extras)[0])
    return entries


def verify(state_dir: str | Path) -> dict:
    state_dir = Path(state_dir)
    _regular(state_dir / ACTIVE)
    entries = _validated_manifest(state_dir)
    active = _jsonl_file(state_dir / ACTIVE)
    return {"version": VERSION, "archive_count": len(entries),
            "archive_bytes": sum(row["bytes"] for row in entries),
            "archive_events": sum(row["events"] for row in entries),
            "active_bytes": active[0], "active_sha256": active[1],
            "active_events": active[2], "logical_events": sum(row["events"] for row in entries) + active[2]}


def _names(state_dir: Path) -> list[Path]:
    # Verify *everything* before yielding a single byte: never silently emit a
    # truncated prefix when one archived file is missing or altered.
    summary = verify(state_dir)
    entries = _validated_manifest(state_dir) if summary["archive_count"] else []
    return [state_dir / e["name"] for e in entries] + [state_dir / ACTIVE]


def logical_bytes(state_dir: str | Path) -> Iterator[bytes]:
    for file in _names(Path(state_dir)):
        with file.open("rb") as stream:
            while data := stream.read(CHUNK):
                yield data


def logical_lines(state_dir: str | Path) -> Iterator[bytes]:
    """Yield complete raw JSONL lines, for legacy strict-decoder compatibility.

    Historical receipt verification deliberately applies its original
    strict_json decoder to each returned byte string, rather than using our
    less-strict json.loads parser. Archive boundaries cannot split lines.
    """
    for file in _names(Path(state_dir)):
        with file.open("rb") as stream:
            yield from stream


def _strict_event(line: bytes) -> dict:
    """Decode without silently collapsing duplicate keys or nonfinite values.

    Raw history remains unchanged and available through logical_lines().
    The public decoded iterator must not alter the meaning of evidence through
    permissive JSON decoding. Historical raw-file preservation is separate.
    """
    def pairs(items: list[tuple[str, object]]) -> dict:
        parsed = {}
        for key, value in items:
            if key in parsed:
                raise JournalIntegrityError("duplicate_event_key:" + key)
            parsed[key] = value
        return parsed

    def nonfinite(value: str) -> None:
        raise JournalIntegrityError("nonfinite_event_value:" + value)

    def finite_float(value: str) -> float:
        result = float(value)
        # Valid-looking JSON exponents can overflow a binary float. Reject
        # the resulting infinity rather than turning evidence into a nonfinite
        # number that a later digest or JSON writer cannot reproduce.
        if not math.isfinite(result):
            raise JournalIntegrityError("nonfinite_event_value:" + value)
        return result

    try:
        event = json.loads(line, object_pairs_hook=pairs, parse_constant=nonfinite,
                           parse_float=finite_float)
    except (ValueError, UnicodeError) as error:
        raise JournalIntegrityError("invalid_decoded_event") from error
    if not isinstance(event, dict):
        raise JournalIntegrityError("invalid_decoded_event_type")
    return event


def logical_events(state_dir: str | Path) -> Iterator[dict]:
    for line in logical_lines(state_dir):
        if line.strip():
            yield _strict_event(line)


def logical_digest(state_dir: str | Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    for block in logical_bytes(state_dir):
        size += len(block)
        digest.update(block)
    return size, digest.hexdigest()


def export_logical(state_dir: str | Path, destination: str | Path) -> dict:
    """Export a complete history stream to a new file, never overwriting data.

    Publication is atomic, and the output is not exposed on failure. The caller
    must still provide a read-stable state checkout (e.g. a Git snapshot).
    """
    state_dir = Path(state_dir)
    destination = Path(destination)
    if destination.resolve().is_relative_to(state_dir.resolve()):
        # A complete logical export may grow beyond GitHub's per-file limit.
        # Refuse to deposit a second whole-history blob inside live state/.
        raise JournalIntegrityError("export_target_inside_live_state")
    if destination.exists() or destination.is_symlink():
        raise JournalIntegrityError("export_target_exists")
    if not destination.parent.is_dir():
        raise JournalIntegrityError("export_parent_missing")
    initial = verify(state_dir)
    tmp_path = None
    digest = hashlib.sha256()
    total = 0
    try:
        fd, name = tempfile.mkstemp(prefix=".ora-journal-export-", dir=destination.parent)
        tmp_path = Path(name)
        with os.fdopen(fd, "wb") as stream:
            for part in logical_bytes(state_dir):
                stream.write(part)
                digest.update(part)
                total += len(part)
            stream.flush()
            os.fsync(stream.fileno())
        if verify(state_dir) != initial or (total, digest.hexdigest()) != logical_digest(state_dir):
            raise JournalIntegrityError("history_changed_during_export")
        os.link(tmp_path, destination)  # refuses to replace existing path
        return {"bytes": total, "sha256": digest.hexdigest(), "destination": str(destination)}
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def publication_preflight(state_dir: str | Path) -> dict:
    """Refuse any local state file beyond a conservative Git blob budget.

    Filesystem check only. A caller must still verify exact Git index/tree,
    expected remote parent and immutable source before publishing.
    """
    state_dir = Path(state_dir)
    items = []
    for path in state_dir.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        if not _regular(path):
            continue
        size = path.stat().st_size
        if size >= SAFE_MAX_BLOB_BYTES:
            raise JournalIntegrityError("state_blob_exceeds_safe_budget:" + path.name)
        items.append((size, path.relative_to(state_dir).as_posix()))
    verify(state_dir)
    return {"file_count": len(items), "largest_files": [
        {"path": name, "bytes": size} for size, name in sorted(items, reverse=True)[:5]],
        "safe_max_blob_bytes": SAFE_MAX_BLOB_BYTES}


def _heartbeat_quiescent(state_dir: Path) -> int:
    """Require completed receipt matched to current persisted cycle."""
    operation = state_dir / "heartbeat_operation.json"
    organism = state_dir / "organism.json"
    _regular(operation)
    _regular(organism)
    try:
        op = json.loads(operation.read_bytes())
        state = json.loads(read_snapshot_bytes(organism))
    except (ValueError, UnicodeError) as error:
        raise JournalIntegrityError("invalid_state_or_heartbeat") from error
    if op.get("status") != "completed" or type(op.get("result_cycle")) is not int:
        raise JournalIntegrityError("heartbeat_not_terminal")
    if type(state.get("cycles")) is not int or op["result_cycle"] != state["cycles"]:
        raise JournalIntegrityError("terminal_cycle_mismatch")
    return state["cycles"]


def rotate(state_dir: str | Path, *, expected_active_sha256: str, expected_cycle: int,
           min_bytes: int = ROTATE_AT_BYTES, fail_at: str | None = None) -> dict:
    """Perform *local, unstaged* rotation, requiring external serial/CAS guard.

    Caller must require clean exact growth Git head; run under the existing
    exclusive GH Actions writer lane and ensure the new reader source is already
    on main. If failure occurs between renaming and manifest publication, abort
    the job and DO NOT stage/push or try automatic local recovery. Next job gets
    a fresh checkout of the unchanged remote commit.
    """
    state_dir = Path(state_dir)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_active_sha256):
        raise JournalIntegrityError("bad_expected_hash")
    if type(expected_cycle) is not int or expected_cycle < 0:
        raise JournalIntegrityError("bad_expected_cycle")
    before = verify(state_dir)
    if _heartbeat_quiescent(state_dir) != expected_cycle:
        raise JournalIntegrityError("stale_cycle")
    if before["active_sha256"] != expected_active_sha256:
        raise JournalIntegrityError("stale_active_tail")
    if before["active_bytes"] < min_bytes:
        raise JournalIntegrityError("below_rotation_floor")
    if before["active_bytes"] >= SAFE_MAX_BLOB_BYTES:
        raise JournalIntegrityError("active_exceeds_preferred_budget")
    old_size, old_sha = logical_digest(state_dir)
    previous = _validated_manifest(state_dir)
    target = state_dir / f"journal-sealed-{len(previous)+1:06d}.jsonl"
    if target.exists() or target.is_symlink():
        raise JournalIntegrityError("archive_target_exists")
    entry = {"name": target.name, "bytes": before["active_bytes"],
             "sha256": before["active_sha256"], "events": before["active_events"]}
    manifest = {"version": VERSION, "archives": previous + [entry]}
    if fail_at == "before_rename":
        raise JournalIntegrityError("injected_before_rename")
    os.replace(state_dir / ACTIVE, target)  # same inode/bytes, no reserialization
    if fail_at == "after_rename":
        raise JournalIntegrityError("injected_after_rename")
    # exclusive creation intentionally fails on unexpected path reappearance
    with (state_dir / ACTIVE).open("xb") as file:
        file.flush()
        os.fsync(file.fileno())
    if fail_at == "after_new_tail":
        raise JournalIntegrityError("injected_after_new_tail")
    tmp_path = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".journal-archives-", dir=state_dir)
        tmp_path = Path(tmp)
        with os.fdopen(fd, "wb") as output:
            output.write(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            output.flush()
            os.fsync(output.fileno())
        if fail_at == "before_manifest":
            raise JournalIntegrityError("injected_before_manifest")
        os.replace(tmp_path, state_dir / MANIFEST)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    after = verify(state_dir)
    publication_preflight(state_dir)
    size, digest = logical_digest(state_dir)
    if (size, digest) != (old_size, old_sha) or after["active_bytes"] != 0:
        raise JournalIntegrityError("lossless_rotation_proof_failed")
    return {"cycle": expected_cycle, "archive": entry, "archive_count": after["archive_count"],
            "logical_bytes": size, "logical_sha256": digest,
            "active_bytes": 0, "requires_remote_cas": True, "published": False}