"""Isolated, default-off lossless Git-friendly chunk representation research.

No production Core, StateStore, heartbeat, Observer, or writer uses this module.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

FORMAT = "ora-original-raw-chunks-research-v1"
CHUNK_BYTES = 32 * 1024 * 1024
MAX_RAW = 512 * 1024 * 1024
NAME = re.compile(r"snapshot-part-([0-9]{6})\.bin\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")


class ChunkStudyError(ValueError):
    pass


def _digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _object(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RAW:
        raise ChunkStudyError("invalid raw bytes")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ChunkStudyError("invalid original JSON") from error
    if not isinstance(value, dict) or type(value.get("cycles")) is not int or value["cycles"] < 0:
        raise ChunkStudyError("invalid cycle or state")
    return value


def prepare_parts(raw: bytes) -> tuple[bytes, dict[str, bytes]]:
    value = _object(raw)
    parts = {}
    descriptions = []
    for index, pos in enumerate(range(0, len(raw), CHUNK_BYTES)):
        part = raw[pos:pos+CHUNK_BYTES]
        name = f"snapshot-part-{index:06d}.bin"
        descriptions.append({"name": name, "bytes": len(part), "sha256": _digest(part)})
        parts[name] = part
    manifest = {"format": FORMAT, "raw_bytes": len(raw), "raw_sha256": _digest(raw),
                "cycle": value["cycles"], "chunk_bytes": CHUNK_BYTES, "parts": descriptions}
    envelope = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return envelope, parts


def _regular(path: Path, maximum: int) -> bytes:
    if path.is_symlink():
        raise ChunkStudyError("symlink rejected")
    try:
        with path.open("rb") as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
                raise ChunkStudyError("invalid regular chunk file")
            body = f.read(maximum + 1)
            if len(body) != info.st_size:
                raise ChunkStudyError("chunk size changed")
            return body
    except OSError as error:
        raise ChunkStudyError("missing chunk") from error


def read_parts(directory: str | Path) -> bytes:
    directory = Path(directory)
    envelope = _regular(directory / "organism.json", 64 * 1024)
    try:
        manifest = json.loads(envelope)
    except ValueError as error:
        raise ChunkStudyError("invalid manifest JSON") from error
    if not isinstance(manifest, dict) or set(manifest) != {"format","raw_bytes","raw_sha256","cycle","chunk_bytes","parts"}:
        raise ChunkStudyError("invalid manifest fields")
    if manifest["format"] != FORMAT or manifest["chunk_bytes"] != CHUNK_BYTES:
        raise ChunkStudyError("unrecognized representation")
    raw_len = manifest["raw_bytes"]
    if type(raw_len) is not int or not 0 < raw_len <= MAX_RAW:
        raise ChunkStudyError("invalid declared length")
    if type(manifest["cycle"]) is not int or manifest["cycle"] < 0:
        raise ChunkStudyError("invalid declared cycle")
    if type(manifest["raw_sha256"]) is not str or not HEX.fullmatch(manifest["raw_sha256"]):
        raise ChunkStudyError("invalid raw digest")
    descriptions=manifest["parts"]
    if not isinstance(descriptions,list) or len(descriptions)!=(raw_len + CHUNK_BYTES - 1)//CHUNK_BYTES:
        raise ChunkStudyError("missing or extra parts")
    output=bytearray()
    for index,description in enumerate(descriptions):
        if not isinstance(description,dict) or set(description)!={"name","bytes","sha256"}:
            raise ChunkStudyError("invalid part metadata")
        name=description["name"]
        if type(name) is not str or not NAME.fullmatch(name) or name!=f"snapshot-part-{index:06d}.bin":
            raise ChunkStudyError("invalid part path or ordering")
        expected=CHUNK_BYTES if index < len(descriptions)-1 else raw_len - index*CHUNK_BYTES
        if type(description["bytes"]) is not int or description["bytes"]!=expected:
            raise ChunkStudyError("invalid part boundary")
        if type(description["sha256"]) is not str or not HEX.fullmatch(description["sha256"]):
            raise ChunkStudyError("invalid part digest")
        chunk=_regular(directory / name, CHUNK_BYTES)
        if len(chunk)!=expected or _digest(chunk)!=description["sha256"]:
            raise ChunkStudyError("part identity mismatch")
        output.extend(chunk)
    data=bytes(output)
    if len(data)!=raw_len or _digest(data)!=manifest["raw_sha256"]:
        raise ChunkStudyError("original bytes mismatch")
    if _object(data)["cycles"]!=manifest["cycle"]:
        raise ChunkStudyError("cycle mismatch")
    return data


def write_isolated_parts(directory: str | Path, raw: bytes) -> None:
    """For disposable experiment repositories only; NOT an atomic Git publisher."""
    directory=Path(directory)
    envelope, parts=prepare_parts(raw)
    directory.mkdir(parents=True,exist_ok=True)
    for name,body in parts.items():
        (directory/name).write_bytes(body)
    # Seal only after every piece has been placed in the disposable worktree.
    (directory/"organism.json").write_bytes(envelope)
    if read_parts(directory)!=raw:
        raise ChunkStudyError("post-write copy mismatch")
