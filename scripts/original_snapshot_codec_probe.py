#!/usr/bin/env python3
"""Read-only exact-byte compression feasibility for a copied original Ora snapshot."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import tempfile

CHUNK = 1024 * 1024
GIT_BLOB_CEILING = 100 * 1024 * 1024

class SnapshotProbeError(ValueError):
    pass

def inspect_snapshot(path: Path) -> dict:
    path = Path(path)
    if path.is_symlink():
        raise SnapshotProbeError("snapshot symlink rejected")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SnapshotProbeError("independent regular snapshot required")
    if not 0 < info.st_size < GIT_BLOB_CEILING:
        raise SnapshotProbeError("snapshot must be nonempty and below hard limit")
    digest = hashlib.sha256()
    git_blob = hashlib.sha1(b"blob " + str(info.st_size).encode() + b"\0")
    with tempfile.TemporaryFile() as packed:
        with path.open("rb") as source, gzip.GzipFile(
                filename="", mode="wb", compresslevel=6, mtime=0, fileobj=packed) as compressor:
            total = 0
            while chunk := source.read(CHUNK):
                total += len(chunk)
                digest.update(chunk)
                git_blob.update(chunk)
                compressor.write(chunk)
        if total != info.st_size:
            raise SnapshotProbeError("snapshot changed length during packing")
        zipped = packed.tell()
        packed.seek(0)
        zipped_hash = hashlib.file_digest(packed, "sha256").hexdigest()
        packed.seek(0)
        # Compare actual reconstructed bytes, not merely self-asserted hashes.
        with path.open("rb") as original, gzip.GzipFile(fileobj=packed, mode="rb") as restored:
            read_back = 0
            while chunk := original.read(CHUNK):
                output = restored.read(len(chunk))
                if output != chunk:
                    raise SnapshotProbeError("reconstructed snapshot bytes differ")
                read_back += len(output)
            if restored.read(1):
                raise SnapshotProbeError("extra reconstructed snapshot bytes")
    if read_back != info.st_size:
        raise SnapshotProbeError("reconstructed size differs")
    return {
        "status": "READ_ONLY_BYTE_EXACT_SNAPSHOT_GZIP_VERIFIED",
        "snapshot_bytes": info.st_size,
        "snapshot_sha256": digest.hexdigest(),
        "snapshot_git_blob": git_blob.hexdigest(),
        "gzip_bytes": zipped,
        "gzip_sha256": zipped_hash,
        "gzip_ratio": round(zipped / info.st_size, 6),
        "hard_limit_headroom_bytes": GIT_BLOB_CEILING - info.st_size,
        "original_ora_actions": 0,
        "state_writes": 0,
        "codec_deployed": False,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.output.exists() or args.output.is_symlink()
            or args.output.absolute().is_relative_to(args.snapshot.resolve().parent)):
        raise SnapshotProbeError("independent new output outside state required")
    result = inspect_snapshot(args.snapshot)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
