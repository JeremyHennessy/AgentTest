"""Node-backed checksum/fail-closed browser data loader test; no UI mutation."""
from pathlib import Path
import subprocess
import shutil
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ClientSnapshotLoaderTests(unittest.TestCase):
    def test_raw_gzip_chunks_and_immutability(self):
        self.assertIsNotNone(shutil.which("node"))
        result=subprocess.run(["node","-e",(ROOT/"tests/snapshot_reader_node_test.js").read_text()],
                              cwd=ROOT,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stdout+"\n"+result.stderr)

    def test_loader_syntax(self):
        result=subprocess.run(["node","--check",str(ROOT/"snapshot-reader.js")],
                              cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
