"""Discover only the reviewed scientific-extension authored-data checks."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class ScientificExtensionPublicationTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux", "Authored native receipt checks require Linux")
    def test_default_off_scientific_source_overlay(self):
        root = Path(__file__).resolve().parents[1]
        runner = root / "experiments/grounded_policy_study/scientific_extension_v3/run_zero_world_tests.py"
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
