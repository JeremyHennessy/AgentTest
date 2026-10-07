import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "policy-study-work" / "ora_study" / "limit_probe.py"
class RlimitAlternatives(unittest.TestCase):
    def run_probe(self, mode):
        with tempfile.TemporaryDirectory(dir=ROOT/"policy-study-results", prefix="rlimit-") as directory:
            start = time.monotonic_ns()
            process = subprocess.run([sys.executable, "-I", "-S", "-B", str(PROBE), mode], cwd=directory,
                env={"LANG":"C.UTF-8", "PYTHONHASHSEED":"0"}, capture_output=True, timeout=5)
            return process, time.monotonic_ns()-start
    def test_address_space_refuses_large_allocation(self):
        process, _ = self.run_probe("as")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(json.loads(process.stdout)["blocked"])
    def test_file_size_caps_one_regular_file(self):
        process, _ = self.run_probe("fsize")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["size"], 4096)
    def test_cpu_hard_limit_kills_busy_stub(self):
        process, wall_ns = self.run_probe("cpu")
        self.assertEqual(process.returncode, -signal.SIGKILL)
        self.assertLess(wall_ns, 5_000_000_000)
    def test_nproc_evidence_is_recorded_without_assuming_root_enforcement(self):
        process, _ = self.run_probe("nproc")
        self.assertEqual(process.returncode, 0, process.stderr)
        row = json.loads(process.stdout)
        self.assertIs(type(row["blocked"]), bool)
        if row["euid"] != 0:
            self.assertTrue(row["blocked"])
if __name__ == "__main__":
    unittest.main()
