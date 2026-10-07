"""Run new research controls in their required fresh import-first interpreter."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class IsolatedContractTests(unittest.TestCase):
    def test_contract_contract_controls(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT/"src")+os.pathsep+str(ROOT/"experiments"))
        result = subprocess.run([sys.executable,"-B",str(ROOT/"tests/inquiry_executive_cases/contract_cases.py"),"-v"],cwd=ROOT,env=env,text=True,capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout+result.stderr)
