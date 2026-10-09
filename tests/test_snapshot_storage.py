"""Preservation tests for default-off original snapshot dual-format reader."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from agenttest.state import StateStore, initial_state
from agenttest.snapshot_storage import (
    SnapshotStorageError, prepare_compressed_copy, read_snapshot_bytes,
)


class SnapshotStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "organism.json"
        self.raw = (json.dumps({"cycles": 7453, "episodes": [{"v": "hello"}] * 1000})
                    + "\n").encode()

    def make_envelope(self):
        envelope, filename, packed = prepare_compressed_copy(self.raw)
        (self.root / filename).write_bytes(packed)
        self.state.write_bytes(envelope)
        return json.loads(envelope), filename, packed

    def test_original_raw_exact(self):
        self.state.write_bytes(self.raw)
        self.assertEqual(read_snapshot_bytes(self.state), self.raw)

    def test_compressed_exact_and_original_untouched(self):
        manifest, filename, packed = self.make_envelope()
        self.assertEqual(read_snapshot_bytes(self.state), self.raw)
        self.assertEqual(manifest["raw_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertLess(len(packed), len(self.raw))
        self.assertEqual((self.root / filename).read_bytes(), packed)

    def test_deterministic_preparation(self):
        self.assertEqual(prepare_compressed_copy(self.raw),
                         prepare_compressed_copy(self.raw))

    def test_missing_blob_fails_no_fallback(self):
        _, filename, _ = self.make_envelope()
        (self.root / filename).unlink()
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_corrupt_blob_fails(self):
        _, filename, packed = self.make_envelope()
        (self.root / filename).write_bytes(packed[:-2])
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_wrong_hash_fails(self):
        manifest, _, _ = self.make_envelope()
        manifest["raw_sha256"] = "0" * 64
        self.state.write_text(json.dumps(manifest))
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_decompression_size_bomb_rejected(self):
        manifest, _, _ = self.make_envelope()
        manifest["raw_bytes"] = 3
        self.state.write_text(json.dumps(manifest))
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_path_traversal_rejected(self):
        manifest, _, _ = self.make_envelope()
        manifest["gzip_file"] = "../other.gz"
        self.state.write_text(json.dumps(manifest))
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_unknown_format_fails(self):
        self.state.write_text('{"format":"unknown","cycles":7453}')
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_nonobject_rejected(self):
        self.state.write_text("[]")
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_symlink_rejected(self):
        original = self.root / "original.json"
        original.write_bytes(self.raw)
        self.state.symlink_to(original)
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_cycle_mismatch_rejected(self):
        manifest, _, _ = self.make_envelope()
        manifest["cycle"] += 1
        self.state.write_text(json.dumps(manifest))
        with self.assertRaises(SnapshotStorageError):
            read_snapshot_bytes(self.state)

    def test_state_store_reads_legacy_and_envelope(self):
        valid = initial_state()
        valid["cycles"] = 7453
        self.raw = (json.dumps(valid, sort_keys=True) + "\n").encode()
        self.state.write_bytes(self.raw)
        legacy = StateStore(self.state).load()
        self.make_envelope()
        compressed = StateStore(self.state).load()
        self.assertEqual(legacy, compressed)
        self.assertEqual(compressed["cycles"], 7453)

    def test_raw_preparation_does_not_write(self):
        self.state.write_bytes(self.raw)
        prepare_compressed_copy(self.state.read_bytes())
        self.assertEqual(self.state.read_bytes(), self.raw)
        self.assertEqual([p.name for p in self.root.iterdir()], ["organism.json"])


if __name__ == "__main__":
    unittest.main()
