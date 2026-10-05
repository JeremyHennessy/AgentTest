"""Immutable external episode archive segment contract.

Research-only. Archived record existence is deliberately separate from generic
evidence authority; nothing here mutates AgentCore or known_evidence_ids().
"""
from __future__ import annotations

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.episode_identity import episode_sequence

SEGMENT_VERSION = "episode-archive-segment-v1"
INDEX_VERSION = "episode-archive-index-v1"
AUTHORITY_VERSION = "episode-archive-authority-v1"

ALLOWED_PURPOSES = frozenset(
    {
        "historical_lookup",
        "provenance_lookup",
        "recovery_restore",
    }
)
DENIED_EVIDENCE_PURPOSES = frozenset(
    {
        "generic_evidence",
        "native_inquiry_grounding",
        "native_inquiry_resolution",
        "cognition_grounding",
        "self_proposal_grounding",
    }
)

_MANIFEST_FIELDS = {
    "version",
    "authority_version",
    "segment_id",
    "production_base",
    "source_state_sha256",
    "source_episode_count",
    "record_count",
    "first_sequence",
    "last_sequence",
    "segment_file",
    "index_file",
    "segment_sha256",
    "index_sha256",
    "canonical_records_sha256",
    "episode_ids_sha256",
    "allowed_purposes",
    "generic_evidence_authority",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_episode_bytes(episode: dict[str, Any]) -> bytes:
    if not isinstance(episode, dict):
        raise ValueError("episode record must be an object")
    return _canonical_json(episode) + b"\n"


def _validated_episode_rows(
    episodes: list[dict[str, Any]],
) -> list[tuple[int, str, dict[str, Any], bytes]]:
    rows: list[tuple[int, str, dict[str, Any], bytes]] = []
    seen: set[str] = set()
    previous_sequence = 0
    for item in episodes:
        if not isinstance(item, dict):
            raise ValueError("archive episode must be an object")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("archive episode ID must be non-empty text")
        if identifier in seen:
            raise ValueError(f"duplicate archive episode ID: {identifier}")
        sequence = episode_sequence(identifier)
        if sequence is None:
            raise ValueError(
                f"archive v1 supports numeric Core episode IDs only: {identifier}"
            )
        if sequence <= previous_sequence:
            raise ValueError("archive episodes must be in strictly increasing sequence")
        payload = canonical_episode_bytes(item)
        rows.append((sequence, identifier, deepcopy(item), payload))
        seen.add(identifier)
        previous_sequence = sequence
    if not rows:
        raise ValueError("archive segment requires at least one episode")
    return rows


def build_archive_segment(
    episodes: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    production_base: str,
    source_state_sha256: str,
    source_episode_count: int,
) -> dict[str, Any]:
    if not isinstance(production_base, str) or len(production_base) != 40:
        raise ValueError("production_base must be a 40-character commit SHA")
    if not isinstance(source_state_sha256, str) or len(source_state_sha256) != 64:
        raise ValueError("source_state_sha256 must be sha256 hex")
    if type(source_episode_count) is not int or source_episode_count < len(episodes):
        raise ValueError("source_episode_count is invalid")

    rows = _validated_episode_rows(episodes)
    canonical_records = b"".join(row[3] for row in rows)
    canonical_digest = _sha256(canonical_records)
    identifiers = [row[1] for row in rows]
    ids_digest = _sha256(_canonical_json(identifiers))
    first_sequence = rows[0][0]
    last_sequence = rows[-1][0]
    segment_id = (
        f"AS1-{first_sequence:06d}-{last_sequence:06d}-"
        f"{canonical_digest[:16]}"
    )

    index_payload = {
        "version": INDEX_VERSION,
        "segment_id": segment_id,
        "records": [
            {
                "id": identifier,
                "sequence": sequence,
                "record_sha256": _sha256(payload),
            }
            for sequence, identifier, _item, payload in rows
        ],
    }
    index_bytes = _canonical_json(index_payload) + b"\n"
    compressed = gzip.compress(canonical_records, compresslevel=9, mtime=0)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    segment_name = f"{segment_id}.jsonl.gz"
    index_name = f"{segment_id}.index.json"
    manifest_name = f"{segment_id}.manifest.json"
    (output / segment_name).write_bytes(compressed)
    (output / index_name).write_bytes(index_bytes)

    manifest = {
        "version": SEGMENT_VERSION,
        "authority_version": AUTHORITY_VERSION,
        "segment_id": segment_id,
        "production_base": production_base,
        "source_state_sha256": source_state_sha256,
        "source_episode_count": source_episode_count,
        "record_count": len(rows),
        "first_sequence": first_sequence,
        "last_sequence": last_sequence,
        "segment_file": segment_name,
        "index_file": index_name,
        "segment_sha256": _sha256(compressed),
        "index_sha256": _sha256(index_bytes),
        "canonical_records_sha256": canonical_digest,
        "episode_ids_sha256": ids_digest,
        "allowed_purposes": sorted(ALLOWED_PURPOSES),
        "generic_evidence_authority": False,
    }
    (output / manifest_name).write_bytes(_canonical_json(manifest) + b"\n")
    return {
        "manifest": manifest,
        "manifest_path": str(output / manifest_name),
        "index_path": str(output / index_name),
        "segment_path": str(output / segment_name),
    }


class EpisodeArchiveSegment:
    def __init__(
        self,
        manifest: dict[str, Any],
        records: dict[str, dict[str, Any]],
        record_bytes: dict[str, bytes],
        ordered_ids: list[str],
    ) -> None:
        self.manifest = deepcopy(manifest)
        self._records = deepcopy(records)
        self._record_bytes = dict(record_bytes)
        self._ordered_ids = list(ordered_ids)

    @classmethod
    def load(
        cls,
        manifest_path: str | Path,
        *,
        expected_production_base: str | None = None,
        expected_source_state_sha256: str | None = None,
    ) -> "EpisodeArchiveSegment":
        manifest_file = Path(manifest_path)
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS:
            raise ValueError("archive manifest fields do not match v1 contract")
        if manifest["version"] != SEGMENT_VERSION:
            raise ValueError("unsupported archive segment version")
        if manifest["authority_version"] != AUTHORITY_VERSION:
            raise ValueError("unsupported archive authority version")
        if manifest["allowed_purposes"] != sorted(ALLOWED_PURPOSES):
            raise ValueError("archive purpose allowlist does not match v1 contract")
        if manifest["generic_evidence_authority"] is not False:
            raise ValueError("archive v1 cannot grant generic evidence authority")
        if expected_production_base is not None and (
            manifest["production_base"] != expected_production_base
        ):
            raise ValueError("archive production baseline mismatch")
        if expected_source_state_sha256 is not None and (
            manifest["source_state_sha256"] != expected_source_state_sha256
        ):
            raise ValueError("archive source-state digest mismatch")

        segment_path = manifest_file.parent / str(manifest["segment_file"])
        index_path = manifest_file.parent / str(manifest["index_file"])
        compressed = segment_path.read_bytes()
        index_bytes = index_path.read_bytes()
        if _sha256(compressed) != manifest["segment_sha256"]:
            raise ValueError("archive compressed segment digest mismatch")
        if _sha256(index_bytes) != manifest["index_sha256"]:
            raise ValueError("archive index digest mismatch")

        try:
            canonical_records = gzip.decompress(compressed)
        except (OSError, EOFError) as exc:
            raise ValueError("archive segment cannot be decompressed") from exc
        if _sha256(canonical_records) != manifest["canonical_records_sha256"]:
            raise ValueError("archive canonical record digest mismatch")

        index_payload = json.loads(index_bytes)
        if (
            not isinstance(index_payload, dict)
            or set(index_payload) != {"version", "segment_id", "records"}
            or index_payload["version"] != INDEX_VERSION
            or index_payload["segment_id"] != manifest["segment_id"]
            or not isinstance(index_payload["records"], list)
        ):
            raise ValueError("archive index contract mismatch")

        lines = canonical_records.splitlines(keepends=True)
        if len(lines) != manifest["record_count"]:
            raise ValueError("archive record count mismatch")
        if len(index_payload["records"]) != len(lines):
            raise ValueError("archive index record count mismatch")

        records: dict[str, dict[str, Any]] = {}
        record_bytes: dict[str, bytes] = {}
        ordered_ids: list[str] = []
        previous_sequence = 0
        for line, index_row in zip(lines, index_payload["records"]):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("archive record is not valid JSON") from exc
            if not isinstance(item, dict):
                raise ValueError("archive record is not an object")
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("archive record ID is unavailable")
            sequence = episode_sequence(identifier)
            if sequence is None or sequence <= previous_sequence:
                raise ValueError("archive episode sequence is invalid")
            if identifier in records:
                raise ValueError(f"duplicate archive episode ID: {identifier}")
            if (
                not isinstance(index_row, dict)
                or set(index_row) != {"id", "sequence", "record_sha256"}
                or index_row["id"] != identifier
                or index_row["sequence"] != sequence
                or index_row["record_sha256"] != _sha256(line)
            ):
                raise ValueError("archive index entry does not match record")
            records[identifier] = item
            record_bytes[identifier] = bytes(line)
            ordered_ids.append(identifier)
            previous_sequence = sequence

        if _sha256(_canonical_json(ordered_ids)) != manifest["episode_ids_sha256"]:
            raise ValueError("archive episode ID digest mismatch")
        if previous_sequence != manifest["last_sequence"]:
            raise ValueError("archive last sequence mismatch")
        first_sequence = episode_sequence(ordered_ids[0])
        if first_sequence != manifest["first_sequence"]:
            raise ValueError("archive first sequence mismatch")

        return cls(manifest, records, record_bytes, ordered_ids)

    @property
    def archived_ids(self) -> tuple[str, ...]:
        return tuple(self._ordered_ids)

    def contains(self, identifier: str) -> bool:
        return identifier in self._records

    def lookup(
        self,
        identifier: str,
        *,
        purpose: str,
    ) -> dict[str, Any] | None:
        if purpose in DENIED_EVIDENCE_PURPOSES:
            raise PermissionError(
                f"archive v1 does not grant {purpose} evidence authority"
            )
        if purpose not in ALLOWED_PURPOSES:
            raise PermissionError(f"archive purpose is not allowed: {purpose}")
        record = self._records.get(identifier)
        return deepcopy(record) if record is not None else None

    def canonical_record_bytes(
        self,
        identifier: str,
        *,
        purpose: str,
    ) -> bytes | None:
        self.lookup(identifier, purpose=purpose)
        payload = self._record_bytes.get(identifier)
        return bytes(payload) if payload is not None else None

    def restore_episode_ledger(
        self,
        hot_episodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[tuple[int, str, dict[str, Any]]] = []
        seen: set[str] = set()
        for item in [*self._records.values(), *hot_episodes]:
            if not isinstance(item, dict):
                raise ValueError("episode ledger item must be an object")
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("episode ledger ID is unavailable")
            if identifier in seen:
                raise ValueError(f"hot/archive episode overlap: {identifier}")
            sequence = episode_sequence(identifier)
            if sequence is None:
                raise ValueError(
                    "archive restore v1 requires numeric Core episode IDs"
                )
            rows.append((sequence, identifier, deepcopy(item)))
            seen.add(identifier)
        rows.sort(key=lambda row: row[0])
        for index in range(1, len(rows)):
            if rows[index][0] <= rows[index - 1][0]:
                raise ValueError("restored episode sequence is not strictly increasing")
        return [row[2] for row in rows]

    def grants_generic_evidence_authority(self, identifier: str) -> bool:
        # Explicitly false even for a present archived record. Future authority
        # must be a separate reviewed contract.
        _ = identifier
        return False
