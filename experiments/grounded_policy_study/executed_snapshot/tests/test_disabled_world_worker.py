import sys
import unittest
from ora_study.world_worker import run_neutral,run_probes
class DisabledWorldSource(unittest.TestCase):
    def test_neutral_refuses_before_any_import_or_materialization(self):
        before=set(sys.modules)
        with self.assertRaises(RuntimeError):
            run_neutral("/never-accessed",1,lambda row:self.fail("must not emit"))
        self.assertFalse(any(name.startswith(("grounded_policy_v2","open_object_world_challenge")) for name in set(sys.modules)-before))
    def test_probe_refuses_before_private_source_or_callback(self):
        with self.assertRaises(RuntimeError):
            run_probes("/never-accessed","layout1.t32",None,None,lambda row:self.fail("must not emit"))
if __name__ == "__main__":
    unittest.main()
