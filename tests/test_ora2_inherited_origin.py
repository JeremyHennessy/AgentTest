"""Default-off authentic inherited goal checkpoint admission guards."""
from pathlib import Path
import tempfile
import unittest

from ora2 import inherited_origin as origin
from ora2.learner import ProtocolError


class AuthenticOriginGuardTests(unittest.TestCase):
    def test_metadata_binding_rejects_all_tampered_pins(self):
        meta = origin.PINS.copy()
        origin.verify_metadata(meta)
        for field in origin.PINS:
            with self.subTest(field=field):
                corrupt = meta.copy()
                corrupt[field] = "changed"
                with self.assertRaises(ProtocolError):
                    origin.verify_metadata(corrupt)
        with self.assertRaises(ProtocolError):
            origin.verify_metadata({})

    def test_mixed_or_incomplete_historical_inputs_rejected(self):
        for snapshot, journal in ((b"{}", b"{}\n"), (b"", b"{}\n"),
                                  (b"{}\n", b""), (b"{}" * 3, b"\n")):
            with self.subTest(snapshot=len(snapshot), journal=len(journal)):
                with self.assertRaises(ProtocolError):
                    origin.validate(snapshot, journal)

    def test_alias_and_nonregular_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "snapshot.json"
            source.write_bytes(b"{}")
            alias = root / "alias.json"
            alias.symlink_to(source)
            with self.assertRaises(ProtocolError):
                origin.read(source, source)
            with self.assertRaises(ProtocolError):
                origin.read(alias, source)
            with self.assertRaises(ProtocolError):
                origin.read(source, root / "absent.json")


if __name__ == "__main__":
    unittest.main()
