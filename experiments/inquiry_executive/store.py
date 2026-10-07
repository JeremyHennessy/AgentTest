"""POSIX process lock, no-follow confinement and one atomic capsule commit.

The stable sibling lock is never replaced. Temporary files are never recovery
inputs. Directory fsync errors are reported as commit uncertainty: callers must
reread the authoritative capsule, never automatically replay a world action.
"""
from __future__ import annotations

import fcntl
import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path

from .contracts import (ROOT, Conflict, encoded, ensure_capacity, strict_json,
                        verify_seal)


class CommitUncertain(OSError):
    pass


def absolute(path):
    value = Path(path)
    if not value.is_absolute() or str(value) != os.path.abspath(value):
        raise Conflict("an absolute canonical path is required")
    return value


def directory(path):
    """Traverse every component without following links, returning a pinned fd."""
    path = absolute(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            new = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=fd)
            os.close(fd)
            fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_regular(path, max_bytes=256 * 1_048_576):
    path = absolute(path)
    fd = directory(path.parent)
    try:
        handle = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            info = os.fstat(handle)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise Conflict("only unaliased regular source/capsule files are allowed")
            if info.st_size > max_bytes:
                raise Conflict("input exceeds maximum serialized size")
            with os.fdopen(handle, "rb", closefd=False) as stream:
                data = stream.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise Conflict("input exceeds maximum serialized size")
            return data, info
        finally:
            os.close(handle)
    finally:
        os.close(fd)


class CapsuleStore:
    def __init__(self, path, research_dir, *, enabled=False):
        if enabled is not True:
            raise Conflict("inquiry executive is disabled by default")
        self.path, self.root = absolute(path), absolute(research_dir)
        if self.path.parent != self.root or self.path.name in {"state.json", "agent_state.json"}:
            raise Conflict("capsule must be a new named file directly in research directory")
        if self.root == ROOT or any(self.root.is_relative_to(ROOT / name)
                                    for name in ("src", "state", ".github", "scripts")):
            raise Conflict("live/default/production directory is forbidden")
        self.lock_name = self.path.name + ".lock"
        self._pinned = None

    @contextmanager
    def _locked(self, *, creating=False, shared=False):
        fd = directory(self.root)
        lock = None
        try:
            flags = os.O_RDWR | os.O_NOFOLLOW
            if creating:
                flags |= os.O_CREAT
            lock = os.open(self.lock_name, flags, 0o600, dir_fd=fd)
            info = os.fstat(lock)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise Conflict("invalid stable process lock")
            fcntl.flock(lock, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            now = os.stat(self.lock_name, dir_fd=fd, follow_symlinks=False)
            root = os.fstat(fd)
            named_root = os.stat(self.root, follow_symlinks=False)
            if (now.st_dev, now.st_ino) != (info.st_dev, info.st_ino):
                raise Conflict("lock identity changed")
            if (root.st_dev, root.st_ino) != (named_root.st_dev, named_root.st_ino):
                raise Conflict("directory identity changed")
            identities = dict(directory=[root.st_dev, root.st_ino],
                              lock=[info.st_dev, info.st_ino])
            yield fd, identities
        finally:
            if lock is not None:
                os.close(lock)
            os.close(fd)

    def _check_named_identity(self, fd, identities):
        named = os.stat(self.root, follow_symlinks=False)
        lock = os.stat(self.lock_name, dir_fd=fd, follow_symlinks=False)
        if (list((named.st_dev, named.st_ino)) != identities["directory"]
                or list((lock.st_dev, lock.st_ino)) != identities["lock"]
                or not stat.S_ISDIR(named.st_mode) or not stat.S_ISREG(lock.st_mode)
                or lock.st_nlink != 1):
            raise Conflict("directory/lock changed while transaction was staged")
        # Check every named ancestor too, without following replacement links.
        check = directory(self.root)
        try:
            info = os.fstat(check)
            if [info.st_dev, info.st_ino] != identities["directory"]:
                raise Conflict("named ancestor identity changed")
        finally:
            os.close(check)

    def _read_locked(self, fd, identities):
        self._check_named_identity(fd, identities)
        handle = os.open(self.path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            info = os.fstat(handle)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 256*1_048_576:
                raise Conflict("invalid capsule file")
            with os.fdopen(handle, "rb", closefd=False) as stream:
                data = stream.read(256*1_048_576+1)
        finally:
            os.close(handle)
        state = strict_json(data)
        verify_seal(state)
        identity = state.get("identity", {})
        if (identity.get("path") != str(self.path)
                or identity.get("research_dir") != str(self.root)
                or identity.get("filesystem") != identities):
            raise Conflict("capsule path/directory/run confinement mismatch")
        immutable = state.get("identity_hash")
        if self._pinned is not None and immutable != self._pinned:
            raise Conflict("capsule identity changed while open")
        from .executive import validate_capsule
        validate_capsule(state)
        self._pinned = immutable
        return state

    def read(self):
        with self._locked(shared=True) as (fd, identities):
            return self._read_locked(fd, identities)

    def _write_locked(self, fd, state, *, creating=False):
        from .executive import validate_capsule
        validate_capsule(state, verify_checksum=False)
        ensure_capacity(state)
        data = encoded(state)
        self._check_named_identity(fd, state["identity"]["filesystem"])
        if creating:
            try:
                os.stat(self.path.name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise Conflict("capsule output already exists")
        else:
            info = os.stat(self.path.name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise Conflict("capsule became an alias")
        name = "." + self.path.name + "." + uuid.uuid4().hex + ".tmp"
        handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=fd)
        replaced = False
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self._check_named_identity(fd, state["identity"]["filesystem"])
            os.replace(name, self.path.name, src_dir_fd=fd, dst_dir_fd=fd)
            replaced = True
            os.fsync(fd)
        except BaseException as error:
            if replaced:
                raise CommitUncertain("replacement completed; reread capsule before retry") from error
            raise
        finally:
            if not replaced:
                try:
                    os.unlink(name, dir_fd=fd)
                except FileNotFoundError:
                    pass
        self._pinned = state["identity_hash"]
