"""Fresh-process pure-policy and tiny transaction invariant wrappers."""
import os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GroundedPolicyV2(unittest.TestCase):
    def run_suite(self,name):
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'experiments'))
        result=subprocess.run([sys.executable,'-B',str(ROOT/'tests/grounded_policy_v2_cases'/name),'-v'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);print(result.stdout+result.stderr)
    def test_pure_policy_invariants(self):self.run_suite('policy_cases.py')
    def test_owned_transaction_invariants(self):self.run_suite('transaction_cases.py')
