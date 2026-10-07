import unittest
from ora_study.profiles import SCIENTIFIC_PROFILE,INVARIANT_PROFILE
from ora_study.stage_adapter import dispatch_stage,dispatch_invariant_stage
from ora_study.ledger import IntegrityError
class DistinctProfiles(unittest.TestCase):
    def test_fixture_never_changes_scientific_boundary_or_ids(self):
        self.assertEqual(SCIENTIFIC_PROFILE["discovery_count"],32)
        self.assertEqual(INVARIANT_PROFILE["discovery_count"],2)
        self.assertEqual(INVARIANT_PROFILE["transition_ceiling"],6)
        self.assertEqual(INVARIANT_PROFILE["probe_transitions"],0)
        self.assertFalse(set(SCIENTIFIC_PROFILE["case_ids"])&set(INVARIANT_PROFILE["case_ids"]))
        with self.assertRaises(TypeError):
            INVARIANT_PROFILE["transition_ceiling"]=7
    def test_request_cannot_select_profile(self):
        request={"phase":"create_select","case_id":"native-invariant.R","path":"unused","research_dir":"unused","source_paths":{},"arm":"R","stage":1}
        with self.assertRaises(IntegrityError):
            dispatch_stage(None,request)
        with self.assertRaises(IntegrityError):
            dispatch_invariant_stage(None,dict(request,discovery_count=32))
if __name__ == "__main__":
    unittest.main()
