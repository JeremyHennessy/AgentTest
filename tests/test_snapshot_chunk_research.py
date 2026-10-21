"""Synthetic fail-closed tests; the authentic cost comparison is independent."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from agenttest.snapshot_chunk_research import ChunkStudyError, prepare_parts, read_parts, write_isolated_parts


class ChunkStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.raw=(json.dumps({"cycles":9904,"history":["observation"]*12000},sort_keys=True)+"\n").encode()
        write_isolated_parts(self.root,self.raw)

    def test_exact_roundtrip(self):
        self.assertEqual(read_parts(self.root),self.raw)

    def test_stable_piece_names_after_new_generation(self):
        changed=(json.dumps({"cycles":9905,"history":["observation"]*12000,"new":"real bytes"},sort_keys=True)+"\n").encode()
        first=sorted(p.name for p in self.root.glob("snapshot-part-*.bin"))
        write_isolated_parts(self.root,changed)
        self.assertEqual(read_parts(self.root),changed)
        self.assertEqual(sorted(p.name for p in self.root.glob("snapshot-part-*.bin")),first)

    def test_corrupt_piece_rejected(self):
        piece=next(self.root.glob("snapshot-part-*.bin"))
        piece.write_bytes(piece.read_bytes()[:-1])
        with self.assertRaises(ChunkStudyError): read_parts(self.root)

    def test_missing_piece_rejected(self):
        next(self.root.glob("snapshot-part-*.bin")).unlink()
        with self.assertRaises(ChunkStudyError): read_parts(self.root)

    def test_wrong_declared_hash_rejected(self):
        path=self.root/"organism.json"
        row=json.loads(path.read_bytes())
        row["raw_sha256"]="0"*64
        path.write_text(json.dumps(row))
        with self.assertRaises(ChunkStudyError): read_parts(self.root)

    def test_changed_cycle_rejected(self):
        path=self.root/"organism.json"
        row=json.loads(path.read_bytes())
        row["cycle"]+=1
        path.write_text(json.dumps(row))
        with self.assertRaises(ChunkStudyError): read_parts(self.root)

    def test_traversal_rejected(self):
        path=self.root/"organism.json"
        row=json.loads(path.read_bytes())
        row["parts"][0]["name"]="../escape.bin"
        path.write_text(json.dumps(row))
        with self.assertRaises(ChunkStudyError): read_parts(self.root)

    def test_unknown_format_rejected(self):
        path=self.root/"organism.json"
        row=json.loads(path.read_bytes())
        row["format"]="legacy-unknown"
        path.write_text(json.dumps(row))
        with self.assertRaises(ChunkStudyError): read_parts(self.root)

    def test_symlink_rejected(self):
        part=next(self.root.glob("snapshot-part-*.bin"))
        copy=self.root/"valid-copy"
        copy.write_bytes(part.read_bytes())
        part.unlink()
        part.symlink_to(copy)
        with self.assertRaises(ChunkStudyError): read_parts(self.root)

    def test_raw_copy_is_unchanged_during_preparation(self):
        before=hashlib.sha256(self.raw).hexdigest()
        prepare_parts(self.raw)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),before)

if __name__=="__main__":
    unittest.main()
