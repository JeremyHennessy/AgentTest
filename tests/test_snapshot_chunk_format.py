"""Separate non-mutating tests of the original Ora chunk reader."""
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from agenttest import snapshot_storage as storage


class ChunkedReaderTests(TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir=Path(d.name)
        self.pointer=self.dir/"organism.json"
        self.original=(json.dumps({"cycles":9904,"records":["event"]*31},sort_keys=True)+"\n").encode()

    def write(self):
        with patch.object(storage,"CHUNK_BYTES",128):
            envelope,parts=storage.prepare_chunked_copy(self.original)
            self.pointer.write_bytes(envelope)
            for name,data in parts.items(): (self.dir/name).write_bytes(data)
        return json.loads(envelope),parts

    def read(self):
        with patch.object(storage,"CHUNK_BYTES",128):
            return storage.read_snapshot_bytes(self.pointer)

    def test_exact_roundtrip_multiple_parts(self):
        manifest,parts=self.write()
        self.assertGreater(len(parts),1)
        self.assertEqual(self.read(),self.original)
        self.assertEqual(manifest["raw_bytes"],len(self.original))

    def test_absent_or_corrupt_part_is_rejected(self):
        manifest,parts=self.write()
        name=next(iter(parts))
        (self.dir/name).unlink()
        with self.assertRaises(storage.SnapshotStorageError): self.read()
        (self.dir/name).write_bytes(parts[name]+b"!")
        with self.assertRaises(storage.SnapshotStorageError): self.read()

    def test_wrong_hash_and_order_and_path_rejected(self):
        manifest,_=self.write()
        manifest["raw_sha256"]="0"*64
        self.pointer.write_text(json.dumps(manifest))
        with self.assertRaises(storage.SnapshotStorageError): self.read()
        manifest,_=self.write()
        manifest["parts"][0]["name"]="../escape"
        self.pointer.write_text(json.dumps(manifest))
        with self.assertRaises(storage.SnapshotStorageError): self.read()
        manifest,_=self.write()
        manifest["parts"][0],manifest["parts"][1]=manifest["parts"][1],manifest["parts"][0]
        self.pointer.write_text(json.dumps(manifest))
        with self.assertRaises(storage.SnapshotStorageError): self.read()

    def test_mismatched_cycle_and_declaration_rejected(self):
        manifest,_=self.write()
        manifest["cycle"]+=1
        self.pointer.write_text(json.dumps(manifest))
        with self.assertRaises(storage.SnapshotStorageError): self.read()
        manifest,_=self.write()
        manifest["parts"].pop()
        self.pointer.write_text(json.dumps(manifest))
        with self.assertRaises(storage.SnapshotStorageError): self.read()

    def test_symlinked_part_rejected(self):
        _,parts=self.write()
        name=next(iter(parts))
        (self.dir/name).unlink()
        target=self.dir/"other"
        target.write_bytes(parts[name])
        (self.dir/name).symlink_to(target)
        with self.assertRaises(storage.SnapshotStorageError): self.read()

    def test_raw_and_gzip_paths_still_supported(self):
        self.pointer.write_bytes(self.original)
        self.assertEqual(storage.read_snapshot_bytes(self.pointer),self.original)
        manifest,name,packed=storage.prepare_stable_compressed_copy(self.original)
        self.pointer.write_bytes(manifest)
        (self.dir/name).write_bytes(packed)
        self.assertEqual(storage.read_snapshot_bytes(self.pointer),self.original)

    def test_writer_must_fail_closed_if_given_chunked_state(self):
        # Reader-only release: existing compressed writer does not silently
        # rewrite a new chunked generation as an old gzip format.
        self.write()
        with self.assertRaises(storage.SnapshotStorageError):
            storage.write_snapshot_bytes(self.pointer,self.original)
