"""Read-only cycle-1803 reconstruction from the frozen negative timing study.

Reads a separately downloaded, SHA-pinned original planner-only artifact.
No historical study reruns, new world actions, live state changes or model APIs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from .inherited_origin import validate
from .learner import ProtocolError

ARCHIVE_SHA256 = "859df0d4b24abf4b856b1c66eb19782361e980dc749b5a3fc5878e9dd65ab3b4"
INITIAL_SNAPSHOT = "078a7150df55863930c8e1db25975b57e5ef8b1bd0a9d33fa796aa05af76fa38"
INITIAL_JOURNAL = "b82b76150986bfed51f731b82aea26b853394113e444589c013e7701d1376e16"
MAX_SQLITE = 128 * 1024 * 1024


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reconstruct(artifact: Path, directory: Path) -> dict:
    if (not artifact.is_file() or artifact.is_symlink() or
            sha(artifact.read_bytes()) != ARCHIVE_SHA256):
        raise ProtocolError("unknown or modified frozen original planner artifact")
    if not directory.is_dir() or any(directory.iterdir()):
        raise ProtocolError("new empty independent output directory required")
    with zipfile.ZipFile(artifact) as archive:
        names = set(archive.namelist())
        if not {"report.json", "session.sqlite.gz"}.issubset(names):
            raise ProtocolError("planner evidence archive missing components")
        report = json.loads(archive.read("report.json"))
        if report.get("policy") != "planner" or report.get("seed") != 0:
            raise ProtocolError("not the original planner-only control")
        compressed = archive.read("session.sqlite.gz")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as unpack:
        database_bytes = unpack.read(MAX_SQLITE + 1)
    if len(database_bytes) > MAX_SQLITE:
        raise ProtocolError("recorded SQLite evidence exceeds fixed bound")
    with tempfile.TemporaryDirectory(prefix="ora2-authentic-planner-db-") as tmp:
        db = Path(tmp) / "planner.sqlite"
        db.write_bytes(database_bytes)
        with sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True) as cx:
            if cx.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ProtocolError("original database is corrupt")
            original = cx.execute("SELECT meta,snapshot,journal FROM origin WHERE id=1").fetchone()
            current = cx.execute("SELECT seq,seal,snapshot FROM current WHERE id=1").fetchone()
            records = cx.execute(
                "SELECT seq,request,body,prior,seal FROM events ORDER BY seq"
            ).fetchall()
    if not original or not current or current[0] != 32 or len(records) != 32:
        raise ProtocolError("original copied study has wrong lifecycle history")
    meta, initial_state, initial_journal = original
    if (sha(initial_state) != INITIAL_SNAPSHOT or sha(initial_journal) != INITIAL_JOURNAL or
            json.loads(meta).get("mode") != "ora2-phase41-timed-cycle-v1"):
        raise ProtocolError("original Phase41 inheritance differs")
    journal = bytearray(initial_journal)
    prior_checksum = None
    for number, request, body, prior, checksum in records:
        if (number != len(journal.splitlines()) - len(initial_journal.splitlines()) + 1
                and number < 1):
            raise ProtocolError("invalid event counter")
        if (prior_checksum is not None and prior != prior_checksum or
                sha((prior + "\n" + body).encode()) != checksum):
            raise ProtocolError("copied evidence event chain differs")
        event = json.loads(body)
        if (event["sequence"] != number or event["cycle"] != 1771 + number or
                event["request"] != request or event.get("owner", "phase41") != "phase41"):
            raise ProtocolError("non-planner or unmatched historical evidence")
        suffix = event["journal_suffix"].encode()
        if not suffix.endswith(b"\n"):
            raise ProtocolError("historical journal suffix truncated")
        journal.extend(suffix)
        prior_checksum = checksum
    if current[1] != prior_checksum:
        raise ProtocolError("current head does not match immutable event chain")
    snapshot = current[2]
    projection = validate(snapshot, bytes(journal))
    state_out = directory / "study002_snapshot.json"
    journal_out = directory / "study002_journal.jsonl"
    state_out.write_bytes(snapshot)
    journal_out.write_bytes(journal)
    return {
        "status": "SEALED_COPIED_INHERITED_GOAL_RECONSTRUCTED",
        "source_artifact_sha256": ARCHIVE_SHA256,
        "snapshot_sha256": sha(snapshot),
        "journal_sha256": sha(bytes(journal)),
        "checkpoint_cycle": projection["origin_cycle"],
        "inherited_active_goal": "PG000448",
        "inherited_active_plan": "PP000451",
        "replayed_world_actions": 0,
        "original_live_ora_actions": 0,
        "successor_behavioral_study_executed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reconstruct(args.artifact, args.output_directory), sort_keys=True))


if __name__ == "__main__":
    main()
