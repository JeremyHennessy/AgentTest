import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from ora_study.ledger import IntegrityError
from ora_study.protocol import APPROVED_FILES, canonical
from ora_study.reporter import read_sealed,apply_outer_terminal

RESULTS = Path(__file__).resolve().parents[2] / "policy-study-results"
class SavedReportingBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=RESULTS, prefix="report-")
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def seal(self):
        raw = canonical({"data_kind":"synthetic_fixture", "authored_value":5})
        (self.root/"saved.json").write_bytes(raw)
        seal = {"schema":"ora.study.records-seal.v1", "protocol_manifest":APPROVED_FILES,
                "records":{"saved.json":hashlib.sha256(raw).hexdigest()},
                "saved_input":"saved.json", "records_complete":True}
        (self.root/"records-seal.json").write_bytes(canonical(seal))
    def test_invalid_candidate_dominates_late_resource_interruption(self):
        result=apply_outer_terminal({"classification":"invalid","data_kind":"synthetic_fixture","errors":["mask leak"]},{"classification":"incomplete","phase":"expiry"})
        self.assertEqual(result["classification"],"invalid")
        self.assertIn("mask leak",result["errors"])
    def test_late_failure_dominates_computed_benefit(self):
        candidate={"classification":"finite-corpus own-outcome predictive benefit with evidence-sensitive test selection", "data_kind":"synthetic_fixture"}
        result=apply_outer_terminal(candidate,{"classification":"incomplete","phase":"report_write"})
        self.assertEqual(result["classification"],"incomplete")
        self.assertIsNone(result["scientific_result"])
        self.assertEqual(result["provisional_computed_classification"],candidate["classification"])
    def test_no_unblinding_before_seal(self):
        with self.assertRaises(IntegrityError):
            read_sealed(self.root)
    def test_saved_bytes_only(self):
        self.seal()
        payload, proof = read_sealed(self.root)
        self.assertEqual(payload["authored_value"], 5)
        self.assertEqual(len(proof), 64)
    def test_changed_or_missing_records_invalid(self):
        self.seal()
        (self.root/"saved.json").write_bytes(b"{}")
        with self.assertRaises(IntegrityError):
            read_sealed(self.root)
        (self.root/"saved.json").unlink()
        with self.assertRaises(IntegrityError):
            read_sealed(self.root)
    def test_unsealed_or_external_path_rejects(self):
        self.seal()
        seal = json.loads((self.root/"records-seal.json").read_bytes())
        seal["records_complete"] = False
        (self.root/"records-seal.json").write_bytes(canonical(seal))
        with self.assertRaises(IntegrityError):
            read_sealed(self.root)
if __name__ == "__main__":
    unittest.main()
