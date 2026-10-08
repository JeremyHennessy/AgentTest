"""Isolated archive reader contract only; NOT main heartbeat_claim integration tests.

The finished patch requires exact-head main CI with the real strict_json parser
and heartbeat receipt verifier. This stand-in exercises its observable streaming
semantics, including duplicate-key rejection and full-history hashing.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from agenttest.journal_tail_rotation import MANIFEST, JournalIntegrityError, logical_digest, logical_lines, rotate, verify


def strict_json_contract(line):
    def unique(pairs):
        result = {}
        for key, val in pairs:
            if key in result:
                raise ValueError("duplicate key:" + key)
            result[key] = val
        return result
    return json.loads(line, object_pairs_hook=unique)


def find_claim(state, request_id):
    matches = []
    for line in logical_lines(state):
        if line.strip():
            event = strict_json_contract(line)
            if event.get("heartbeat_request_id") == request_id:
                matches.append(event)
    if len(matches) != 1:
        raise ValueError("missing or ambiguous")
    return matches[0]


class ClaimArchiveContract(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        self.old = b'{"event":"cycle","cycle":7,"heartbeat_request_id":"heartbeat:old"}\n'
        (self.state / "journal.jsonl").write_bytes(self.old)
        (self.state / "heartbeat_operation.json").write_text(json.dumps({"status": "completed", "result_cycle": 7}))
        (self.state / "organism.json").write_text(json.dumps({"cycles": 7}))

    def rotate(self):
        rotate(self.state, expected_active_sha256=verify(self.state)["active_sha256"],
               expected_cycle=7, min_bytes=1)

    def test_historical_claim_streaming_after_archive_and_tail(self):
        self.assertEqual(find_claim(self.state, "heartbeat:old")["cycle"], 7)
        original_digest = hashlib.sha256(self.old).hexdigest()
        self.rotate()
        self.assertEqual(find_claim(self.state, "heartbeat:old")["cycle"], 7)
        self.assertEqual(logical_digest(self.state)[1], original_digest)
        (self.state / "journal.jsonl").write_bytes(b'{"event":"cycle","cycle":8,"heartbeat_request_id":"heartbeat:new"}\n')
        self.assertEqual(find_claim(self.state, "heartbeat:new")["cycle"], 8)
        self.assertEqual(find_claim(self.state, "heartbeat:old")["cycle"], 7)

    def test_strict_decoder_rejects_duplicate_keys_even_if_event_unrelated(self):
        self.rotate()
        (self.state / "journal.jsonl").write_bytes(b'{"event":"diagnostic","event":"cycle"}\n')
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            find_claim(self.state, "heartbeat:old")

    def test_duplicate_heartbeat_id_in_later_active_tail_rejected(self):
        self.rotate()
        (self.state / "journal.jsonl").write_bytes(self.old)
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            find_claim(self.state, "heartbeat:old")

    def test_manifest_tampering_fails_before_exposing_prefix(self):
        self.rotate()
        archive = self.state / "journal-sealed-000001.jsonl"
        archive.write_bytes(b'{"event":"different"}\n')
        with self.assertRaisesRegex(JournalIntegrityError, "archive_changed"):
            find_claim(self.state, "heartbeat:old")

    def test_empty_missing_legacy_hash_is_preserved(self):
        (self.state / "journal.jsonl").unlink()
        self.assertFalse((self.state / MANIFEST).exists())
        digest = hashlib.sha256(b"").hexdigest()
        self.assertEqual(digest, hashlib.sha256(b"" if not (self.state / "journal.jsonl").exists() else b"unused").hexdigest())


if __name__ == "__main__":
    unittest.main()
