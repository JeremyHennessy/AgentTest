"""Discover only the isolated authored-data study foundation checks.

The completed real fixture and the prospective scientific study are never run.
"""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class StudyFoundationTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux", "Native resource checks require Linux")
    def test_reviewed_zero_world_suite(self):
        root = Path(__file__).resolve().parents[1]
        runner = root / "experiments/grounded_policy_study/run_zero_world_tests.py"
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-W", "error::ResourceWarning", str(runner)],
            cwd=root, env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
        )
        sys.stderr.write(result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt["passed"], receipt)
        print(result.stdout, end="")


if __name__ == "__main__":
    unittest.main()
