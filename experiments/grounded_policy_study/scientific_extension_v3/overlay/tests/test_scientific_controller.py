"""Authored metadata and JSON only. No API, world, policy or chooser calls."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from ora_study.scientific_controller import ScientificController, ScientificReferences, reserve_controller_inventory
from ora_study.scientific_transport import ScientificInventory, ScientificLedger
from ora_study.protocol import canonical, digest, registry, MIB
from ora_study.ledger import IntegrityError, CapacityError
from test_scientific_transport import authored_mixed_discovery


class ScientificControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.files = ScientificInventory(Path(self.tmp.name)/"authored-controller")
        reserve_controller_inventory(self.files)
        self.ledger = ScientificLedger(self.files.root/"ledger.jsonl", authored_fixture=True)
        self.wire = SimpleNamespace(files=self.files, ledger=self.ledger, authored_fixture_only=True,
            config={"api_manifest": {}, "api_runtime_manifest": {}}, bound_identities={})
        self.controller = ScientificController(self.wire)

    def tearDown(self):
        self.ledger.close(); self.files.close(); self.tmp.cleanup()

    def test_all_metadata_slots_fit_before_any_dispatch(self):
        self.assertEqual(len(self.controller.index["anchors"]), 32)
        self.assertEqual({row["neutral_t"] for row in self.controller.index["anchors"]}, {32,36,40,44,48,52,56,60})
        self.assertEqual(len(self.files.capsules), 64)
        total = sum(record["reserved_bytes"] for record in self.files.records.values())
        self.assertLessEqual(total, 192*MIB)
        for category, maximum in self.files.allocations.items():
            self.assertLessEqual(self.files.used(category), maximum)
        self.assertTrue(all(record["reserved_bytes"] <= 2*MIB for record in self.files.records.values()))
        self.assertEqual(self.files.used("reports"), 6*MIB)
        self.assertEqual(self.ledger.counters()["actual_entries"]["transition"], 0)
        self.assertEqual(self.files.used("source_inputs"), 64*312*1024 + 4*216*1024 + 32*96*1024)

    def test_real_entry_rejects_before_any_worker(self):
        from ora_study.scientific_controller import main
        with patch("ora_study.scientific_controller.SCIENTIFIC_ADMISSION_REVIEWED", False):
            with self.assertRaises(IntegrityError): self.controller.run()
            with self.assertRaisesRegex(RuntimeError, "disabled"): main()
        self.assertEqual(self.ledger._events("worker_admitted"), [])

    def test_python_c_main_import_binds_helpers_to_captured_package(self):
        package = Path(__file__).parents[1]/"ora_study"
        script = r'''
import ast,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
package=Path(sys.argv[1])
blocked=[]
class NoWorldImports:
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split(".")[0] in ("grounded_policy_v2","agenttest","open_object_world_challenge","open_object_world_challenge_explorer"):
            blocked.append(fullname)
            raise ImportError("API/world imports blocked in authored helper check")
        return None
sys.meta_path.insert(0,NoWorldImports())
manifest={str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob("*.py")}
bootstrap=package/"source_bootstrap.py"
scope={"__name__":"captured_helper_test_bootstrap","__file__":str(bootstrap)}
exec(compile(bootstrap.read_bytes(),str(bootstrap),"exec"),scope)
scope["PinnedSources"](package,manifest).install()
controller=package/"scientific_controller.py"
tree=ast.parse(controller.read_bytes(),filename=str(controller))
assert isinstance(tree.body[-1],ast.If) and ast.unparse(tree.body[-1].test)=="__name__ == '__main__'"
# Omit only automatic main invocation; keep original helper definitions/imports.
exec(compile(ast.Module(body=tree.body[:-1],type_ignores=[]),str(controller),"exec"),globals())
assert __name__=="__main__" and __package__ is None
main_node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="main")
binding=next(node for node in main_node.body if isinstance(node,ast.ImportFrom) and node.module=="ora_study.scientific_controller")
import ora_study.native_fixture_transport as fixture_transport
class AuthoredStop(RuntimeError): pass
def stop_before_marker(path,maximum):
    assert path=="authored-never-read" and maximum==4096
    raise AuthoredStop("no GO or marker I/O")
fixture_transport.read_regular=stop_before_marker
def probe_helpers(helpers):
    results={}
    for name,helper in helpers.items():
        try:
            if name=="claim_started_marker":
                try: helper(None,{"admission_receipt_path":"authored-never-read"},"a"*64,"b"*64)
                except AuthoredStop: value="stopped_before_marker_io"
            elif name=="failure_status":
                value=helper(ValueError("authored integrity failure"),{"evidence_loss":False},[])
            else:
                events=[]
                counts={"actual_entries_exact":{"transition":0,"selecting_backend":0,"producer":0},"decisions_durable_verified":0}
                ledger=SimpleNamespace(counters=lambda:counts,_events=lambda kind:[])
                helper(SimpleNamespace(emit=lambda *row:events.append(row)),ledger,"invalid")
                value=events
            results[name]={"module":helper.__module__,"value":value}
        except Exception as error:
            results[name]={"module":helper.__module__,"error":type(error).__name__+": "+str(error)}
    return results
names=("claim_started_marker","failure_status","emit_native_terminal")
before=probe_helpers({name:globals()[name] for name in names})
# Execute main's exact import with its real local-name binding semantics.
probe=ast.parse('def exercise_main_binding():\n    return probe_helpers({"claim_started_marker":claim_started_marker,"failure_status":failure_status,"emit_native_terminal":emit_native_terminal})').body[0]
probe.body.insert(0,binding)
exec(compile(ast.fix_missing_locations(ast.Module(body=[probe],type_ignores=[])),str(controller),"exec"),globals())
results=exercise_main_binding()
assert __package__ is None and all(globals()[name].__module__=="__main__" for name in names)
assert not blocked
assert not any(name.split(".")[0] in ("grounded_policy_v2","agenttest","open_object_world_challenge","open_object_world_challenge_explorer") for name in sys.modules)
print(json.dumps({"package_context":__package__,"before_binding":before,"helpers":results,"api_world_import_attempts":blocked,"main_invoked":False,"marker_io":False},sort_keys=True))
'''
        checked = subprocess.run([sys.executable,"-I","-S","-B","-c",script,str(package)],
            capture_output=True,text=True,timeout=10,env={"LANG":"C","LC_ALL":"C"})
        self.assertEqual(checked.returncode,0,checked.stderr)
        result=json.loads(checked.stdout)
        self.assertIsNone(result["package_context"])
        self.assertFalse(result["main_invoked"])
        self.assertFalse(result["marker_io"])
        for helper in result["before_binding"].values():
            self.assertEqual(helper["module"],"__main__")
            self.assertIn("ImportError: attempted relative import",helper["error"])
        for helper in result["helpers"].values():
            self.assertNotIn("error",helper,result)
            self.assertEqual(helper["module"],"ora_study.scientific_controller")
        self.assertEqual(result["helpers"]["claim_started_marker"]["value"],"stopped_before_marker_io")
        self.assertEqual(result["helpers"]["failure_status"]["value"],"invalid")
        self.assertEqual(result["helpers"]["emit_native_terminal"]["value"],[[10,0,0],[11,0,0],[12,0,0],[9,0,2]])

    def test_complete_raw_D_and_cohort_bind_to_first_declared_case(self):
        frames, rows = authored_mixed_discovery()
        self.controller.discovery[1] = {"frames": frames, "projected_rows": rows}
        cohort = {"discovery_events": [{"event_id": row["event_id"], "digest": digest(row)} for row in rows],
                  "authored_model_order": ["zero", "movement", "N"]}
        references = self.wire.references
        with self.assertRaises(IntegrityError):
            references.bind("layout1.t32.W", frames, cohort, {"run_id": "authored-W"})
        first = references.bind("layout1.t32.R", frames, cohort, {"run_id": "authored-R"})
        second = references.bind("layout1.t32.W", deepcopy(frames), deepcopy(cohort), {"run_id": "authored-W"})
        self.assertEqual(first["reference_bytes_sha256"], second["reference_bytes_sha256"])
        changed = deepcopy(cohort); changed["authored_model_order"].reverse()
        with self.assertRaises(IntegrityError):
            references.bind("layout1.t36.R", frames, changed, {"run_id": "authored-R2"})
        changed_frames = deepcopy(frames)
        changed_frames[1]["receipt"]["observed_effects"].append("changed authored evidence")
        with self.assertRaises(IntegrityError):
            references.bind("layout1.t36.R", changed_frames, cohort, {"run_id": "authored-R2"})
        self.assertEqual(self.ledger.counters()["actual_entries"]["producer"], 0)

    def test_pair_sources_use_two_distinct_copies_of_same_authored_prefix(self):
        # Stored scalar rows exercise source-copy slicing and identity only;
        # they are deliberately not valid API or scientific observations.
        anchor = registry()["anchors"][0]
        value = {"frames": [{"authored_scalar": index} for index in range(33)]}
        self.controller._put("neutral/layout1-frames.json", "source_inputs", value)
        self.controller._put("neutral/layout1.t32-world.json", "source_inputs", {"world": {"authored_scalar": 7}})
        self.controller.prepare_pair(anchor)
        left, right = (self.controller.source_proofs[anchor["cases"][a]] for a in ("R", "W"))
        for key in ("ora", "world", "observations"):
            self.assertEqual(left[key]["sha256"], right[key]["sha256"])
            self.assertNotEqual(left[key]["inode"], right[key]["inode"])
        with self.assertRaises(IntegrityError): self.controller.prepare_pair(anchor)
        self.assertEqual(self.ledger._events("worker_admitted"), [])

    def test_case_swap_refused_before_native_dispatch(self):
        anchor = registry()["anchors"][0]; case = anchor["cases"]["R"]
        self.controller._put("neutral/layout1-frames.json", "source_inputs", {"frames": [{"authored_scalar": 0}]*33})
        self.controller._put("neutral/layout1.t32-world.json", "source_inputs", {"world": {"authored_scalar": 1}})
        self.controller.prepare_pair(anchor)
        previous = {"identity": {"run_id": "authored-right-case"}, "authored_state": True}
        self.controller.states[case] = previous
        self.controller.identities[case] = digest(previous["identity"])
        self.files.put_new(f"capsules/{case}.json", "capsules", {"identity": {"run_id": "wrong-case"}})
        with self.assertRaisesRegex(IntegrityError, "identity/history"):
            self.controller.api_stage(anchor, "R", "select", 2)
        self.assertEqual(self.ledger._events("worker_admitted"), [])

    def test_one_calling_layer_owns_each_worker_reservation(self):
        from ora_study import driver
        tree = ast.parse(Path(driver.__file__).read_bytes())
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr == "claim_worker" for node in ast.walk(tree)))
        self.assertEqual(self.ledger.counters()["actual_entries"]["transition"], 0)

    def test_closed_worker_projection_failure_stays_invalid(self):
        from ora_study.scientific_controller import failure_status, emit_native_terminal
        from ora_study.native_projection import NativeProjectionError
        self.ledger.claim_worker("reporter")
        self.ledger.append("worker_complete", {"worker_id": "reporter", "result_sha256": digest({"authored": True})})
        counts = self.ledger.counters()
        self.assertFalse(counts["evidence_loss"])
        for error in (NativeProjectionError("authored mask mismatch"), KeyError("native hash"), ValueError("broken seal")):
            self.assertEqual(failure_status(error, counts, []), "invalid")
        self.assertEqual(failure_status(CapacityError("fixed allocation"), counts, []), "incomplete")
        self.assertEqual(failure_status(CapacityError("fixed allocation"), counts, [{"reason": "mismatch"}]), "invalid")
        self.assertEqual(failure_status(CapacityError("late report allocation"), counts, [], "invalid"), "invalid")
        emitted = []
        emit_native_terminal(SimpleNamespace(emit=lambda *row: emitted.append(row)), self.ledger, "invalid")
        self.assertEqual(emitted, [(10, 0, 0), (11, 0, 0), (12, 0, 0), (9, 0, 2)])


if __name__ == "__main__": unittest.main()
