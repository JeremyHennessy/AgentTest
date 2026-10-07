import hashlib
from pathlib import Path
import tempfile
import unittest
from ora_study.freeze import validate_manifest
from ora_study.ledger import IntegrityError
from ora_study.protocol import digest

RESULTS=Path(__file__).resolve().parents[2]/"policy-study-results"
class FreezeTests(unittest.TestCase):
    def test_exact_bytes_not_filename_or_cached_module(self):
        with tempfile.TemporaryDirectory(dir=RESULTS,prefix="manifest-") as name:
            root=Path(name)
            (root/"source.py").write_bytes(b"# authored source-only fixture\n")
            expected={"source.py":hashlib.sha256((root/"source.py").read_bytes()).hexdigest()}
            self.assertEqual(validate_manifest(root,expected),digest(expected))
            (root/"source.py").write_bytes(b"# changed\n")
            with self.assertRaises(IntegrityError):
                validate_manifest(root,expected)
    def test_path_escape_or_alias_rejects(self):
        with tempfile.TemporaryDirectory(dir=RESULTS,prefix="manifest-") as name:
            root=Path(name)
            (root/"source").write_bytes(b"authored")
            (root/"alias").symlink_to(root/"source")
            wanted=hashlib.sha256(b"authored").hexdigest()
            with self.assertRaises(IntegrityError):
                validate_manifest(root,{"alias":wanted})
            with self.assertRaises(IntegrityError):
                validate_manifest(root,{"../../outside":wanted})
if __name__ == "__main__":
    unittest.main()
