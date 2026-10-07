from pathlib import Path
import tempfile
import unittest
from ora_study.artifact_inventory import ALLOCATIONS,SOURCE_BOUNDS,ArtifactInventory
from ora_study.ledger import IntegrityError,CapacityError
from ora_study.protocol import registry
RESULTS=Path(__file__).resolve().parents[2]/"policy-study-results"
class ArtifactAllocations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=RESULTS,prefix="inventory-")
        self.root=Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def test_fixed_complete_arithmetic_and64_capsule_slots(self):
        self.assertEqual(sum(ALLOCATIONS.values()),192*1048576)
        self.assertLessEqual(64*sum(SOURCE_BOUNDS.values()),ALLOCATIONS["source_inputs"])
        inventory=ArtifactInventory(self.root)
        for case in registry()["arm_case_ids"]:
            inventory.register_capsule(case)
        self.assertEqual(inventory.used("capsules"),128*1048576)
        with self.assertRaises(IntegrityError):
            inventory.register_capsule(registry()["arm_case_ids"][0])
    def test_write_reserves_before_bytes_and_never_overruns(self):
        inventory=ArtifactInventory(self.root,allocations={"authored_fixture":10})
        inventory.put_new("one","authored_fixture",b"123456")
        with self.assertRaises(CapacityError):
            inventory.put_new("two","authored_fixture",b"12345")
        self.assertFalse((self.root/"two").exists())
        self.assertEqual(inventory.used("authored_fixture"),6)
    def test_single_external_writer_and_stranded_temp_fail_closed(self):
        inventory=ArtifactInventory(self.root)
        case=registry()["arm_case_ids"][0]
        inventory.register_capsule(case)
        inventory.begin_api_write(case)
        with self.assertRaises(IntegrityError):
            inventory.begin_api_write(case)
        folder=self.root/"capsules"
        folder.mkdir()
        (folder/f".{case}.json.authored.tmp").write_bytes(b"fixture")
        with self.assertRaises(IntegrityError):
            inventory.finish_api_write(case)
        self.assertTrue(inventory.halted)
if __name__ == "__main__":
    unittest.main()
