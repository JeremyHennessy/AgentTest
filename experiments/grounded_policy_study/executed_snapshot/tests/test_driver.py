from pathlib import Path
import tempfile
import unittest
from ora_study.driver import FiniteDriver
from ora_study.ledger import Ledger,IntegrityError
from ora_study.protocol import MOVEMENTS,digest
RESULTS=Path(__file__).resolve().parents[2]/"policy-study-results"
class AuthoredNullTransport:
    """Schedule-only authored records. No world/state/source/API is constructed."""
    authored_fixture_only=True
    def __init__(self):
        self.states={}
        self.calls=[]
        self.saved=0
        self.diverge=False
    def neutral(self,layout):
        self.calls.append(("neutral",layout))
    def prepare_pair(self,anchor):
        self.calls.append(("prepare",anchor["anchor_id"]))
        return {"logical_inputs_sha256":digest({"fixture_input_label":anchor["anchor_id"]})}
    def api_stage(self,anchor,arm,phase,stage):
        self.calls.append((phase,anchor["anchor_id"],arm,stage))
        case=anchor["cases"][arm]
        if phase=="create_select":
            self.states[case]={"decisions":[],"outcomes":[],"world":{"authored_scalar":5}}
        assert phase in ("create_select","select"),"Null fixture must never execute/interpret"
        state=self.states[case]
        decision={"ordinal":stage,"status":"policy_null","hash":digest({"fixture_case":case,"stage":stage})}
        state["decisions"].append(decision)
        return state
    def first_decision_semantics(self,state):
        return {"authored_all_null":True}
    def first_lifecycle_semantics(self,state):
        return {"completed":1,"authored_null":True}
    def decision_semantics(self,state,ordinal):
        return {"forecasts":{a:{"status":"unavailable","reason":"authored_fixture"} for a in MOVEMENTS},"null":True}
    def freeze_forecast_set(self,anchor,F,second,*,commitment):
        assert F==[]
        return {"fixture_anchor":anchor["anchor_id"],"F":F}
    def probes(self,anchor,commitment,state):
        self.calls.append(("probes",anchor["anchor_id"]))
        return {a:{"authored_stub":a} for a in MOVEMENTS}
    def public_outcome_semantics(self,outcome):
        return outcome
    def save_anchor(self,*args):
        self.saved+=1
    def seal_saved_records(self,head):
        assert self.saved==32
        self.calls.append(("seal",))
        return {"fixture_seal":head}
    def report_saved(self,seal):
        self.calls.append(("report",))
        return {"classification":"authored_schedule_fixture_only","science_calls":0}

class DriverSchedule(unittest.TestCase):
    def test_all128_null_decisions_are_kept_and_reporting_waits_for_seal(self):
        with tempfile.TemporaryDirectory(dir=RESULTS,prefix="driver-") as tmp:
            ledger=Ledger(Path(tmp)/"ledger.jsonl",create=True)
            try:
                transport=AuthoredNullTransport()
                result=FiniteDriver(transport,ledger).run_authored_fixture()
                self.assertEqual(result["candidate_report"]["science_calls"],0)
                self.assertTrue(result["requires_outer_terminal_seal"])
                self.assertIsNone(result["scientific_classification"])
                self.assertEqual(ledger.counters()["null_decisions_verified"],128)
                self.assertEqual(ledger.counters()["actual_invocations"],0)
                self.assertEqual(transport.calls[:4],[("neutral",n) for n in (1,2,3,4)])
                self.assertEqual(transport.calls[-2:],[('seal',),('report',)])
                self.assertEqual(sum(c[0]=="probes" for c in transport.calls),32)
            finally:
                ledger.close()
    def test_native_path_always_refuses(self):
        with tempfile.TemporaryDirectory(dir=RESULTS,prefix="driver-") as tmp:
            ledger=Ledger(Path(tmp)/"ledger.jsonl",create=True)
            try:
                transport=AuthoredNullTransport()
                with self.assertRaises(IntegrityError):
                    FiniteDriver(transport,ledger).run()
                self.assertEqual(transport.calls,[])
            finally:
                ledger.close()
if __name__ == "__main__":
    unittest.main()
