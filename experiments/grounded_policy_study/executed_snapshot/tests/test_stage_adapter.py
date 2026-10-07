from copy import deepcopy
import unittest
from ora_study.cold_api_worker import execute_native_stage
from ora_study.ledger import IntegrityError
from ora_study.protocol import registry, digest
from ora_study.resource_plan import arithmetic
from ora_study.stage_adapter import dispatch_stage

class FakeExecutive:
    """Authored lifecycle fixture only; no simulation or policy invocation."""
    state = None
    calls = []
    @classmethod
    def reset(cls):
        cls.state = {"revision":0, "decisions":[], "attempts":[], "outcomes":[], "beliefs":[], "frames":[{"authored_frame":i} for i in range(33)], "cohort":{"authored_cohort":True}, "identity":{"run_id":"authored-run","filesystem":{"directory":[1,2],"lock":[1,3]}}}
        cls.calls = []
    def __init__(self, path, **kwargs):
        self.calls.append("constructor")
    @classmethod
    def create(cls, path, **kwargs):
        cls.calls.append(("create", kwargs))
        return cls(path)
    def read(self):
        self.calls.append("read")
        return deepcopy(self.state)
    def select_next(self, revision):
        assert revision == self.state["revision"]
        self.calls.append("select")
        ordinal = len(self.state["decisions"])+1
        row = {"id":f"d{ordinal}", "ordinal":ordinal, "status":"selected"}
        self.state["decisions"].append(row)
        self.state["attempts"].append({"id":f"a{ordinal}","decision_id":row["id"],"status":"prepared","outcome_id":None})
        self.state["revision"] += 1
        return deepcopy(row)
    def execute(self, attempt_id, revision):
        assert revision == self.state["revision"]
        self.calls.append("execute")
        row = {"id":"o"+attempt_id, "fixture_integer":5}
        self.state["outcomes"].append(row)
        self.state["attempts"][-1].update(status="committed", outcome_id=row["id"])
        self.state["revision"] += 1
        return deepcopy(row)
    def interpret(self, outcome_id, revision):
        assert revision == self.state["revision"]
        self.calls.append("interpret")
        row = {"id":"b"+outcome_id, "fixture_only":True}
        self.state["beliefs"].append(row)
        self.state["attempts"][-1]["status"]="interpreted"
        self.state["revision"] += 1
        return deepcopy(row)

class StageAdapterTests(unittest.TestCase):
    def setUp(self):
        FakeExecutive.reset()
        self.request = {"phase":"create_select", "case_id":registry()["arm_case_ids"][0], "path":"authored-no-file",
                        "research_dir":"authored-no-directory", "source_paths":{}, "arm":"R", "stage":1}
    def dispatch(self, phase, stage=1):
        def binder(case_id, frames, cohort, identity):
            d_hash, cohort_hash = digest(frames), digest(cohort)
            FakeExecutive.calls.append("cohort_bound")
            return {"case_id":case_id,"D_sha256":d_hash,"cohort_sha256":cohort_hash,"durable_ack_sha256":"a"*64}
        return dispatch_stage(FakeExecutive, dict(self.request,phase=phase,stage=stage),cohort_binder=binder)
    def test_native_binding_is_disabled_before_import(self):
        with self.assertRaises(RuntimeError):
            execute_native_stage(self.request, "/missing-and-never-accessed")
    def test_exact_two_stage_native_method_order_on_fake(self):
        self.dispatch("create_select")
        for stage in (1,2):
            for phase in (("execute","interpret") if stage==1 else ("select","execute","interpret")):
                result=self.dispatch(phase,stage)
        self.assertEqual(result["state"]["revision"],6)
        self.assertEqual(FakeExecutive.calls.count("select"),2)
        self.assertEqual(FakeExecutive.calls.count("execute"),2)
        self.assertEqual(FakeExecutive.calls.count("interpret"),2)
        self.assertEqual(FakeExecutive.calls.count("read"),12)
    def test_committed_execute_cannot_replay(self):
        self.dispatch("create_select")
        self.dispatch("execute")
        with self.assertRaises(IntegrityError):
            self.dispatch("execute")
        result=self.dispatch("terminal_reconcile")
        self.assertFalse(result["scientific_continuation_permitted"])
        self.assertEqual(FakeExecutive.calls.count("execute"),1)
    def test_null_has_no_substitute_action(self):
        self.dispatch("create_select")
        FakeExecutive.state["decisions"][-1]["status"]="policy_null"
        with self.assertRaises(IntegrityError):
            self.dispatch("execute")
        self.assertEqual(FakeExecutive.calls.count("execute"),0)
    def test_no_caller_winner_field(self):
        with self.assertRaises(IntegrityError):
            dispatch_stage(FakeExecutive,dict(self.request,winner="north"))
    def test_resource_math_is_explicitly_conditional(self):
        plan=arithmetic()
        self.assertEqual(plan["candidate_whole_tree_cpu_wall_bound_seconds"],850)
        self.assertEqual(plan["scientific_cpu_margin_seconds"],50)
        self.assertEqual(plan["candidate_summed_as_bytes"],512*1048576)
        self.assertTrue(plan["within_numeric_limits"])
        self.assertFalse(plan["hard_scientific_enforcement_demonstrated"])
if __name__ == "__main__":
    unittest.main()
