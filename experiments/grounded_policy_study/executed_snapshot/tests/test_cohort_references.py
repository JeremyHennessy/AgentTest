from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from ora_study.cohort_references import CohortReferences
from ora_study.ledger import Ledger, IntegrityError
from ora_study.protocol import registry,digest
from ora_study.resources import BudgetedFiles

RESULTS=Path(__file__).resolve().parents[2]/"policy-study-results"
class ReferenceHandshake(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=RESULTS,prefix="cohort-")
        self.root=Path(self.tmp.name)
        self.files=BudgetedFiles(self.root)
        self.ledger=Ledger(self.root/"ledger.jsonl",create=True)
        self.references=CohortReferences(self.ledger,self.files,{1:[]})
        self.frames=[{"authored_frame":n} for n in range(33)]
        self.cohort={"authored_cohort":True,"discovery_events":[]}
        self.r=registry()["arm_case_ids"][0]
        self.w=registry()["arm_case_ids"][1]
    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()
    def bind(self,case,run,frames=None,cohort=None):
        return self.references.bind(case,self.frames if frames is None else frames,self.cohort if cohort is None else cohort,{"run_id":run})
    def test_durable_complete_bytes_before_ack_and_identical_copy(self):
        ack=self.bind(self.r,"r")
        reference=self.root/"layout1-D-cohort-reference.json"
        self.assertTrue(reference.exists())
        self.assertEqual(ack["durable_ack_sha256"],self.ledger.records[-1]["hash"])
        second=self.bind(self.w,"w")
        self.assertEqual(ack["reference_bytes_sha256"],second["reference_bytes_sha256"])
    def test_wrong_first_case_cannot_replace_reference(self):
        with self.assertRaises(IntegrityError):
            self.bind(self.w,"w")
    def test_changed_D_or_cohort_rejects_and_preserves_reference(self):
        self.bind(self.r,"r")
        path=self.root/"layout1-D-cohort-reference.json"
        original=path.read_bytes()
        changed=deepcopy(self.frames)
        changed[0]["authored_frame"]=999
        with self.assertRaises(IntegrityError):
            self.bind(self.w,"w",frames=changed)
        with self.assertRaises(IntegrityError):
            self.bind(self.w,"w",cohort={"authored_cohort":False,"discovery_events":[]})
        self.assertEqual(path.read_bytes(),original)
    def test_native_identity_cannot_be_reused(self):
        self.bind(self.r,"native-identity")
        with self.assertRaises(IntegrityError):
            self.bind(self.w,"native-identity")
    def test_missing_entity_state_normalizes_digest_without_changing_raw_D(self):
        row={"event_id":"authored-row","before_context":{"position":[0,0],"inventory_ids":[],"visible_ids":["O001"],"entity.O001.position":[0,1]},"action":"north","after_position":[0,0],"refs":{"before":"a"*64,"receipt":"b"*64,"after":"c"*64}}
        self.references.projected_d[1]=[row]
        normalized=deepcopy(row)
        normalized["before_context"]["entity.O001.state"]=None
        cohort={"authored_cohort":True,"discovery_events":[{"event_id":"authored-row","digest":digest(normalized)}]}
        self.bind(self.r,"r",cohort=cohort)
        self.assertNotIn("entity.O001.state",row["before_context"])
    def test_projected_D_must_match_discovery_derivations(self):
        with self.assertRaises(IntegrityError):
            self.bind(self.r,"r",cohort={"discovery_events":[{"event_id":"invented","digest":"0"*64}]})
if __name__ == "__main__":
    unittest.main()
