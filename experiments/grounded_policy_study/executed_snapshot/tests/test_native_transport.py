from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from ora_study.call_accounting import CallAccounting
from ora_study.cohort_references import CohortReferences
from ora_study.ledger import IntegrityError, Ledger
from ora_study.native_transport import serve_bound_api,handle_cohort_message
from ora_study.protocol import digest,registry
from ora_study.resources import BudgetedFiles
from test_stage_adapter import FakeExecutive

RESULTS=Path(__file__).resolve().parents[2]/"policy-study-results"
def authored_scalar():
    return 2+3
class NativeHandshakeTests(unittest.TestCase):
    def setUp(self):
        FakeExecutive.reset()
        FakeExecutive.state["cohort"]["discovery_events"]=[]
        self.request={"phase":"create_select","case_id":registry()["arm_case_ids"][0],"path":"fixture-no-file",
                      "research_dir":"fixture-no-directory","source_paths":{},"arm":"R","stage":1}
    def test_parent_durable_reference_ack_precedes_selection(self):
        with tempfile.TemporaryDirectory(dir=RESULTS,prefix="handshake-") as tmp:
            root=Path(tmp)
            files=BudgetedFiles(root)
            ledger=Ledger(root/"ledger.jsonl",create=True)
            try:
                references=CohortReferences(ledger,files,{1:[]})
                def exchange(message):
                    self.assertNotIn("select",FakeExecutive.calls)
                    response=handle_cohort_message(message,references)
                    self.assertTrue((root/"layout1-D-cohort-reference.json").exists())
                    return response
                result=serve_bound_api(FakeExecutive,self.request,exchange)
                self.assertEqual(result["result"]["state"]["revision"],1)
                self.assertEqual(FakeExecutive.calls.count("select"),1)
            finally:
                ledger.close()
    def test_unbound_or_denied_ack_never_selects(self):
        for reply in ({"accepted":False},{"accepted":True,"request_sha256":"0"*64}):
            FakeExecutive.reset()
            with self.assertRaises(IntegrityError):
                serve_bound_api(FakeExecutive,self.request,lambda message:reply)
            self.assertNotIn("select",FakeExecutive.calls)
    def test_source_qualified_actual_call_evidence(self):
        records=[]
        identity={(authored_scalar.__code__.co_filename,"authored_scalar"):"authored_fixture"}
        def exchange(message):
            records.append(message)
            return True
        with CallAccounting(identity,exchange):
            self.assertEqual(authored_scalar(),5)
        self.assertEqual([r["event"] for r in records],["actual_call_entered","actual_call_exited"])
        self.assertEqual(records[0]["call_id"],records[1]["call_id"])
    def test_failed_accounting_ack_stops_function_body(self):
        identity={(authored_scalar.__code__.co_filename,"authored_scalar"):"authored_fixture"}
        with self.assertRaises(IntegrityError):
            with CallAccounting(identity,lambda message:False):
                authored_scalar()
if __name__ == "__main__":
    unittest.main()
