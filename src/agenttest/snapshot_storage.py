"""Lossless, fail-closed reader for original Ora snapshot JSON or a gzip envelope.

Reader-only production integration. No writer cutover is authorized here.
The canonical raw JSON remains authoritative until every direct consumer is migrated.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat

FORMAT = "ora-original-gzip-v1"
CHUNK_FORMAT = "ora-original-raw-chunks-v1"
CHUNK_BYTES = 32 * 1024 * 1024
CHUNK_NAME = re.compile(r"snapshot-part-([0-9]{6})\.bin\Z")
MAX_RAW = 512 * 1024 * 1024
MAX_PACKED = 96 * 1024 * 1024
BLOCK = 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")


class SnapshotStorageError(ValueError):
    pass


def _read_regular(path: Path, maximum: int) -> bytes:
    if path.is_symlink():
        raise SnapshotStorageError("snapshot symlink rejected")
    try:
        with path.open("rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SnapshotStorageError("snapshot must be a unique regular file")
            if info.st_size > maximum:
                raise SnapshotStorageError("snapshot exceeds size limit")
            data = source.read(maximum + 1)
            if len(data) > maximum or len(data) != info.st_size:
                raise SnapshotStorageError("snapshot changed or exceeded size limit")
            return data
    except OSError as exc:
        raise SnapshotStorageError("snapshot unavailable") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_object(raw: bytes) -> dict:
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise SnapshotStorageError("snapshot is not valid JSON") from exc
    if type(value) is not dict:
        raise SnapshotStorageError("snapshot root must be an object")
    return value


def _check_envelope(obj: dict) -> None:
    fields = {"format", "raw_bytes", "raw_sha256", "gzip_bytes",
              "gzip_sha256", "gzip_file", "cycle"}
    if set(obj) != fields or obj["format"] != FORMAT:
        raise SnapshotStorageError("unknown snapshot envelope")
    for field, maximum in (("raw_bytes", MAX_RAW), ("gzip_bytes", MAX_PACKED)):
        if type(obj[field]) is not int or not 0 < obj[field] <= maximum:
            raise SnapshotStorageError("invalid snapshot length")
    for field in ("raw_sha256", "gzip_sha256"):
        if type(obj[field]) is not str or not HEX.fullmatch(obj[field]):
            raise SnapshotStorageError("invalid snapshot digest")
    expected = "snapshot-" + obj["gzip_sha256"] + ".json.gz"
    if obj["gzip_file"] not in (expected, "snapshot-current.json.gz"):
        raise SnapshotStorageError("invalid compressed snapshot filename")
    if type(obj["cycle"]) is not int or obj["cycle"] < 0:
        raise SnapshotStorageError("invalid snapshot cycle")



def prepare_chunked_copy(raw: bytes) -> tuple[bytes, dict[str, bytes]]:
    """Pure deterministic split of *all original bytes*; no state edits or writes."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RAW:
        raise SnapshotStorageError("invalid raw chunk source length")
    state = _parse_object(raw)
    if type(state.get("cycles")) is not int or state["cycles"] < 0:
        raise SnapshotStorageError("chunk source cycle invalid")
    pieces = {}
    entries = []
    for index, offset in enumerate(range(0, len(raw), CHUNK_BYTES)):
        name = f"snapshot-part-{index:06d}.bin"
        piece = raw[offset:offset + CHUNK_BYTES]
        entries.append({"name": name, "bytes": len(piece), "sha256": _sha(piece)})
        pieces[name] = piece
    manifest = {
        "format": CHUNK_FORMAT, "raw_bytes": len(raw), "raw_sha256": _sha(raw),
        "cycle": state["cycles"], "chunk_bytes": CHUNK_BYTES, "parts": entries
    }
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode(), pieces


def _read_chunked_snapshot(path: Path, manifest: dict) -> bytes:
    """Reject incomplete generations rather than mixing old and new parts."""
    required = {"format", "raw_bytes", "raw_sha256", "cycle", "chunk_bytes", "parts"}
    if set(manifest) != required or manifest["format"] != CHUNK_FORMAT:
        raise SnapshotStorageError("unknown chunk manifest")
    size = manifest["raw_bytes"]
    if type(size) is not int or not 0 < size <= MAX_RAW:
        raise SnapshotStorageError("invalid chunk original length")
    if type(manifest["chunk_bytes"]) is not int or manifest["chunk_bytes"] != CHUNK_BYTES:
        raise SnapshotStorageError("wrong chunking contract")
    if type(manifest["cycle"]) is not int or manifest["cycle"] < 0:
        raise SnapshotStorageError("invalid chunk cycle")
    if type(manifest["raw_sha256"]) is not str or not HEX.fullmatch(manifest["raw_sha256"]):
        raise SnapshotStorageError("invalid chunk full hash")
    parts = manifest["parts"]
    expected = (size + CHUNK_BYTES - 1) // CHUNK_BYTES
    if not isinstance(parts, list) or len(parts) != expected:
        raise SnapshotStorageError("missing or excess chunk entries")
    output = bytearray()
    for index, entry in enumerate(parts):
        if not isinstance(entry, dict) or set(entry) != {"name", "bytes", "sha256"}:
            raise SnapshotStorageError("invalid chunk entry")
        name = entry["name"]
        if type(name) is not str or not CHUNK_NAME.fullmatch(name) or name != f"snapshot-part-{index:06d}.bin":
            raise SnapshotStorageError("invalid chunk name or order")
        length = CHUNK_BYTES if index + 1 < len(parts) else size - index * CHUNK_BYTES
        if type(entry["bytes"]) is not int or entry["bytes"] != length:
            raise SnapshotStorageError("invalid chunk size claim")
        if type(entry["sha256"]) is not str or not HEX.fullmatch(entry["sha256"]):
            raise SnapshotStorageError("invalid chunk hash claim")
        piece = _read_regular(path.parent / name, CHUNK_BYTES)
        if len(piece) != length or _sha(piece) != entry["sha256"]:
            raise SnapshotStorageError("chunk data mismatch")
        output.extend(piece)
    restored = bytes(output)
    if len(restored) != size or _sha(restored) != manifest["raw_sha256"]:
        raise SnapshotStorageError("full chunked snapshot mismatch")
    state = _parse_object(restored)
    if type(state.get("cycles")) is not int or state["cycles"] != manifest["cycle"]:
        raise SnapshotStorageError("chunk restored cycle mismatch")
    return restored

def read_snapshot_bytes(path: str | Path) -> bytes:
    """Read exact raw JSON bytes; never fall back to an older snapshot."""
    path = Path(path)
    raw = _read_regular(path, MAX_RAW)
    obj = _parse_object(raw)
    if "format" not in obj:
        return raw
    if obj["format"] == CHUNK_FORMAT:
        return _read_chunked_snapshot(path, obj)
    _check_envelope(obj)
    packed = _read_regular(path.parent / obj["gzip_file"], MAX_PACKED)
    if len(packed) != obj["gzip_bytes"] or _sha(packed) != obj["gzip_sha256"]:
        raise SnapshotStorageError("compressed snapshot identity mismatch")
    result = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(packed), mode="rb") as stream:
            while True:
                part = stream.read(min(BLOCK, obj["raw_bytes"] - len(result) + 1))
                if not part:
                    break
                result.extend(part)
                if len(result) > obj["raw_bytes"]:
                    raise SnapshotStorageError("snapshot decompression exceeds declared size")
    except (EOFError, OSError, OverflowError) as exc:
        raise SnapshotStorageError("compressed snapshot corrupted") from exc
    decoded = bytes(result)
    if len(decoded) != obj["raw_bytes"] or _sha(decoded) != obj["raw_sha256"]:
        raise SnapshotStorageError("snapshot reconstruction mismatch")
    state = _parse_object(decoded)
    if type(state.get("cycles")) is not int or state["cycles"] != obj["cycle"]:
        raise SnapshotStorageError("snapshot cycle mismatch")
    return decoded


def prepare_compressed_copy(raw: bytes) -> tuple[bytes, str, bytes]:
    """Pure preparation only: does not publish or change original Ora state."""
    state = _parse_object(raw)
    if not 0 < len(raw) <= MAX_RAW:
        raise SnapshotStorageError("raw snapshot size invalid")
    cycle = state.get("cycles")
    if type(cycle) is not int or cycle < 0:
        raise SnapshotStorageError("invalid original cycle")
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    if len(packed) > MAX_PACKED:
        raise SnapshotStorageError("compressed snapshot exceeds limit")
    filename = "snapshot-" + _sha(packed) + ".json.gz"
    envelope = {"format": FORMAT, "raw_bytes": len(raw),
                "raw_sha256": _sha(raw), "gzip_bytes": len(packed),
                "gzip_sha256": _sha(packed), "gzip_file": filename,
                "cycle": cycle}
    encoded = (json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return encoded, filename, packed

def prepare_stable_compressed_copy(raw: bytes) -> tuple[bytes, str, bytes]:
    """Pure, default-off stable-path representation for prospective writer tests.

    The single packed filename can be overwritten *in a new Git tree together
    with its manifest*. Never publish one without the other or use this helper
    to overwrite original live state outside a reviewed exclusive-writer gate.
    Old content-addressed envelopes remain readable without migration.
    """
    manifest_bytes, _, packed = prepare_compressed_copy(raw)
    manifest = json.loads(manifest_bytes)
    manifest["gzip_file"] = "snapshot-current.json.gz"
    encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return encoded, manifest["gzip_file"], packed

# This writer is deliberately default-off for original production. The Git
# workflow must still commit the packed payload and manifest together.
STORAGE_ENV = "ORA_ORIGINAL_SNAPSHOT_GZIP"


def compression_requested() -> bool:
    setting = os.environ.get(STORAGE_ENV, "0")
    if setting not in ("0", "1"):
        raise SnapshotStorageError("unsupported snapshot write mode")
    return setting == "1"


def existing_is_compressed(path: str | Path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    existing = _read_regular(path, MAX_RAW)
    obj = _parse_object(existing)
    if "format" not in obj:
        return False
    _check_envelope(obj)
    # Never overwrite a corrupt or mismatched previously committed snapshot.
    read_snapshot_bytes(path)
    return True


def _replace_exact(path: Path, payload: bytes) -> None:
    if path.is_symlink():
        raise SnapshotStorageError("snapshot writer rejects symlinks")
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists() or temporary.is_symlink():
        raise SnapshotStorageError("stale snapshot temporary file")
    try:
        with temporary.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise SnapshotStorageError("snapshot write failed before Git publication") from exc



# Future-proof format switch is opt-in; no production workflow sets this flag.
CHUNK_WRITE_ENV = "ORA_ORIGINAL_SNAPSHOT_CHUNKS"


def chunking_requested() -> bool:
    flag = os.environ.get(CHUNK_WRITE_ENV, "0")
    if flag not in ("0", "1"):
        raise SnapshotStorageError("unsupported chunk writer mode")
    return flag == "1"


def existing_is_chunked(path: str | Path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    # A canonical chunk manifest is small. Avoid reading the 105 MiB raw JSON
    # on every legacy write just to detect a default-off storage mode.
    if path.stat().st_size > 64 * 1024:
        return False
    obj = _parse_object(_read_regular(path, 64 * 1024))
    if obj.get("format") != CHUNK_FORMAT:
        return False
    read_snapshot_bytes(path)  # all parts, cycle and hashes must agree
    return True


def write_chunked_snapshot_bytes(path: str | Path, raw: bytes) -> dict:
    """Local prepared multi-file write. Never itself publishes a Git commit.

    An interrupted partial working-tree generation fails integrity checks and
    must be discarded before re-fetching the unchanged exact remote input.
    """
    path = Path(path)
    if compression_requested():
        raise SnapshotStorageError("conflicting gzip and chunk writer requests")
    if path.exists():
        read_snapshot_bytes(path)  # reject corrupt/partial previous state
    envelope, pieces = prepare_chunked_copy(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(pieces.items()):
        _replace_exact(path.parent / name, body)
    _replace_exact(path, envelope)
    if read_snapshot_bytes(path) != raw:
        raise SnapshotStorageError("post-write chunked snapshot mismatch")
    return {"format": CHUNK_FORMAT, "raw_bytes": len(raw),
            "raw_sha256": _sha(raw), "part_count": len(pieces)}

def write_snapshot_bytes(path: str | Path, raw: bytes,
                         *, force_compressed: bool = False) -> dict:
    """Preserve raw format by default or a validated compressed format.

    Git publication must atomically commit both state/organism.json and the
    stable packed sibling in a *single expected-parent* growth commit.
    A mid-write process failure can invalidate the local copy, never causing
    a fallback to older data; discard that checkout and re-fetch the exact
    remote parent. This helper does not push, checkpoint, or authorize cycles.
    """
    path = Path(path)
    if not isinstance(raw, bytes):
        raise SnapshotStorageError("snapshot writer requires bytes")
    _parse_object(raw)
    if chunking_requested() or existing_is_chunked(path):
        if force_compressed:
            raise SnapshotStorageError("conflicting chunk and forced gzip format")
        return write_chunked_snapshot_bytes(path, raw)
    packed_mode = existing_is_compressed(path) or force_compressed
    path.parent.mkdir(parents=True, exist_ok=True)
    if not packed_mode:
        _replace_exact(path, raw)
        return {"format": "raw-json", "raw_bytes": len(raw)}
    envelope, name, packed = prepare_stable_compressed_copy(raw)
    # The order matters: a new manifest may never point to missing packed
    # bytes. An interrupted stable overwrite fails checksum verification.
    _replace_exact(path.parent / name, packed)
    _replace_exact(path, envelope)
    if read_snapshot_bytes(path) != raw:
        raise SnapshotStorageError("post-write compressed state mismatch")
    return {"format": FORMAT, "raw_bytes": len(raw), "gzip_bytes": len(packed),
            "gzip_file": name, "raw_sha256": _sha(raw)}
