"""Copy-only exact-byte recovery prototype. NOT imported by Ora's live runtime.

Linux/POSIX, cooperating writers, local filesystem; not a power-loss guarantee.
Use create() with an absent sandbox directory, never an existing live store.
The intent publication is a roll-forward decision. No semantic work is rerun.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Callable

try:
    import fcntl
except ImportError:  # Import remains safe on platforms not supported by the prototype.
    fcntl = None

VERSION = "ora-copy-recovery-v1"


class RecoveryError(RuntimeError):
    """An inconsistent store must be preserved for inspection, not guessed at."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def decode(raw: bytes) -> dict:
    if not isinstance(raw, bytes):
        raise RecoveryError("expected immutable bytes")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RecoveryError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise RecoveryError("nonfinite JSON value")

    def finite(text):
        number = float(text)
        if not math.isfinite(number):
            raise RecoveryError("nonfinite JSON number")
        return number

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant, parse_float=finite)
    except (ValueError, UnicodeError) as exc:
        raise RecoveryError("invalid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RecoveryError("expected a JSON object")
    return value


def journal_valid(raw: bytes) -> None:
    if not isinstance(raw, bytes):
        raise RecoveryError("expected immutable journal bytes")
    if raw and not raw.endswith(b"\n"):
        raise RecoveryError("unowned journal tail: no final newline")
    for line in raw.split(b"\n")[:-1]:
        decode(line)


def event_valid(raw: bytes | None) -> None:
    if raw is not None:
        if not isinstance(raw, bytes) or raw.count(b"\n") != 1 or not raw.endswith(b"\n"):
            raise RecoveryError("event must be exactly one newline-framed JSON object")
        decode(raw)


def _regular(path: Path) -> None:
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RecoveryError("symlink, hardlink or nonregular file: " + path.name)


def _read(path: Path) -> bytes:
    _regular(path)
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise RecoveryError("required file missing: " + path.name) from exc


def _sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class RecoveryStore:
    """Owns only deliberately created copies; marker is accident prevention, not authentication."""

    def __init__(self, root: str | Path, *, copied_only: bool = False,
                 checkpoint: Callable[[str], None] | None = None):
        if copied_only is not True or fcntl is None or not hasattr(os, "O_DIRECTORY"):
            raise RecoveryError("explicit copied-only POSIX sandbox required")
        self.root = Path(os.path.abspath(root))
        if self.root.resolve() != self.root or not self.root.is_dir():
            raise RecoveryError("absent, aliased or symlinked sandbox directory")
        marker = decode(_read(self.root / "COPY-ONLY.json"))
        if marker != {"version": VERSION, "root": str(self.root)}:
            raise RecoveryError("sandbox marker mismatch")
        self.checkpoint = checkpoint or (lambda _: None)
        self.state = self.root / "organism.json"
        self.journal = self.root / "journal.jsonl"
        self.pending = self.root / "pending.json"
        self.payload = self.root / "prepared-snapshot.json"

    @classmethod
    def create(cls, root: str | Path, state: bytes, journal: bytes,
               *, copied_only: bool = False) -> RecoveryStore:
        if copied_only is not True or fcntl is None or not hasattr(os, "O_DIRECTORY"):
            raise RecoveryError("explicit copied-only POSIX sandbox required")
        decode(state)
        journal_valid(journal)
        root = Path(os.path.abspath(root))
        if root.resolve() != root:
            raise RecoveryError("aliased sandbox directory")
        root.mkdir(mode=0o700)  # Existing destinations are always rejected.
        # An interrupted creation without this final marker is not a usable store.
        for name, raw in (("organism.json", state), ("journal.jsonl", journal),
                          ("writer.lock", b""),
                          ("COPY-ONLY.json", encode({"version": VERSION, "root": str(root)}))):
            with (root / name).open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        _sync_dir(root)
        _sync_dir(root.parent)
        return cls(root, copied_only=True)

    @contextmanager
    def _lock(self):
        path = self.root / "writer.lock"
        _regular(path)
        # Never recreate a removed lock: that can split cooperating writers.
        with path.open("r+b") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RecoveryError("sandbox writer busy") from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _write_all(self, fd: int, raw: bytes, label: str) -> None:
        while raw:
            count = os.write(fd, raw)
            if count <= 0:
                raise OSError("write made no progress")
            raw = raw[count:]
            self.checkpoint(label + ":write")

    def _atomic(self, path: Path, raw: bytes, label: str) -> None:
        temp = path.with_name(path.name + ".tmp")
        _regular(path)
        _regular(temp)
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            self._write_all(fd, raw, label)
            os.fsync(fd)
            self.checkpoint(label + ":file_synced")
        finally:
            os.close(fd)
        os.replace(temp, path)
        self.checkpoint(label + ":replaced")
        _sync_dir(self.root)
        self.checkpoint(label + ":durable")

    def _receipt_path(self, operation_id: str) -> Path:
        if not isinstance(operation_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", operation_id):
            raise RecoveryError("invalid operation identity")
        return self.root / ("receipt-" + operation_id + ".json")

    def _clean(self) -> tuple[bytes, bytes]:
        state, journal = _read(self.state), _read(self.journal)
        decode(state)
        journal_valid(journal)
        return state, journal

    def read(self) -> tuple[bytes, bytes]:
        """Read only a settled snapshot. Recovery must precede any writer/cache logic."""
        with self._lock():
            if self.pending.exists() or self.pending.is_symlink():
                raise RecoveryError("pending intent requires explicit recovery before read")
            return self._clean()

    def commit(self, operation_id: str, expected_state: str, expected_journal: str,
               next_state: bytes, event: bytes | None) -> str:
        """Commit exact caller-frozen bytes. None denotes a legitimate state-only operation."""
        path = self._receipt_path(operation_id)
        decode(next_state)
        event_valid(event)
        for expected in (expected_state, expected_journal):
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise RecoveryError("invalid expected state/journal hash")
        request = {"version": VERSION, "operation_id": operation_id,
                   "before": expected_state, "after": digest(next_state),
                   "journal_before": expected_journal,
                   "event_sha256": None if event is None else digest(event)}
        with self._lock():
            # Do not perform an unrelated recovery as a side effect of a new command.
            if self.pending.exists() or self.pending.is_symlink():
                raise RecoveryError("pending intent requires explicit recovery before commit")
            state, journal = self._clean()
            if path.exists() or path.is_symlink():
                if decode(_read(path)) != request:
                    raise RecoveryError("operation identity reused with different content")
                return "already_committed"  # Even after later operations: never roll state back.
            if digest(state) != expected_state or digest(journal) != expected_journal:
                raise RecoveryError("stale predecessor state or journal")
            intent = {"request": request, "prefix_bytes": len(journal),
                      "prefix_sha256": digest(journal),
                      "event_b64": None if event is None else base64.b64encode(event).decode("ascii")}
            intent["intent_sha256"] = digest(encode(intent))
            self._atomic(self.payload, next_state, "payload")
            self._atomic(self.pending, encode(intent), "intent")
            return self._recover()

    def recover(self) -> str:
        with self._lock():
            if not (self.pending.exists() or self.pending.is_symlink()):
                self._clean()  # Missing/corrupt files and unowned tails never initialize fresh state.
                return "no_pending_intent"
            return self._recover()

    def _recover(self) -> str:
        intent = decode(_read(self.pending))
        if set(intent) != {"request", "prefix_bytes", "prefix_sha256", "event_b64", "intent_sha256"}:
            raise RecoveryError("invalid intent fields")
        seal = intent.pop("intent_sha256")
        if seal != digest(encode(intent)):
            raise RecoveryError("intent checksum mismatch")
        request = intent["request"]
        if not isinstance(request, dict) or set(request) != {
                "version", "operation_id", "before", "after", "journal_before", "event_sha256"}:
            raise RecoveryError("invalid request fields")
        if request["version"] != VERSION:
            raise RecoveryError("unsupported recovery version")
        path = self._receipt_path(request["operation_id"])
        for key in ("before", "after", "journal_before"):
            if not isinstance(request[key], str) or not re.fullmatch(r"[0-9a-f]{64}", request[key]):
                raise RecoveryError("invalid snapshot identity")
        try:
            event = None if intent["event_b64"] is None else base64.b64decode(
                intent["event_b64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise RecoveryError("invalid exact event encoding") from exc
        event_valid(event)
        if request["event_sha256"] != (None if event is None else digest(event)):
            raise RecoveryError("event checksum mismatch")
        target = _read(self.payload)
        decode(target)
        if digest(target) != request["after"]:
            raise RecoveryError("prepared snapshot checksum mismatch")
        state, journal = _read(self.state), _read(self.journal)
        decode(state)
        current = digest(state)
        offset = intent["prefix_bytes"]
        if type(offset) is not int or offset < 0 or offset > len(journal):
            raise RecoveryError("invalid journal offset")
        prefix, tail = journal[:offset], journal[offset:]
        journal_valid(prefix)
        if (intent["prefix_sha256"] != request["journal_before"]
                or digest(prefix) != intent["prefix_sha256"]):
            raise RecoveryError("earlier journal bytes changed")
        exact = event or b""
        if not exact.startswith(tail):
            raise RecoveryError("tail does not belong to retained exact event")
        if current not in (request["before"], request["after"]):
            raise RecoveryError("snapshot is neither predecessor nor target")
        if tail and current != request["after"]:
            raise RecoveryError("journal advanced before associated snapshot")
        if path.exists() or path.is_symlink():
            if decode(_read(path)) != request or current != request["after"] or tail != exact:
                raise RecoveryError("terminal receipt conflicts with pending files")
        # Validate ALL identities before the first associated state/journal mutation.
        if current != request["after"]:
            self._atomic(self.state, target, "snapshot")
        # Re-synchronize snapshot even when an earlier process died after replace.
        with self.state.open("rb") as handle:
            os.fsync(handle.fileno())
        _sync_dir(self.root)
        _regular(self.journal)
        fd = os.open(self.journal, os.O_WRONLY | os.O_APPEND)
        try:
            self._write_all(fd, exact[len(tail):], "journal")
            os.fsync(fd)
            self.checkpoint("journal:durable")
        finally:
            os.close(fd)
        if not path.exists():
            self._atomic(path, encode(request), "receipt")
        else:
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
            _sync_dir(self.root)
        self.pending.unlink()
        self.checkpoint("intent:removed")
        _sync_dir(self.root)
        self.payload.unlink()
        self.checkpoint("payload:removed")
        _sync_dir(self.root)
        return "committed"
