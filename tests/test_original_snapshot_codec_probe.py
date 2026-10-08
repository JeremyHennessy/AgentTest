"""Read-only lossless original-snapshot codec unit checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.original_snapshot_codec_probe import SnapshotProbeError, inspect_snapshot


class SnapshotCodecProofTests(unittest.TestCase):
    def test_exact_roundtrip_never_changes_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "organism.json"
            payload = json.dumps({"cycles": 5, "episodes": [{"event": "repeat"}] * 4000}).encode()
            path.write_bytes(payload)
            receipt = inspect_snapshot(path)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(receipt["snapshot_bytes"], len(payload))
            self.assertEqual(receipt["snapshot_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(receipt["state_writes"], 0)
            self.assertFalse(receipt["codec_deployed"])
            self.assertLess(receipt["gzip_bytes"], len(payload))

    def test_empty_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.json"
            path.write_bytes(b"")
            with self.assertRaisesRegex(SnapshotProbeError, "nonempty"):
                inspect_snapshot(path)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            link = Path(directory) / "alias.json"
            path.write_bytes(b"{}")
            link.symlink_to(path)
            with self.assertRaisesRegex(SnapshotProbeError, "symlink"):
                inspect_snapshot(link)


if __name__ == "__main__":
    unittest.main()
