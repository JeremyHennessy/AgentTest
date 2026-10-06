"""Remote interaction claim tests.

No GitHub API or live branch is touched. Tests operate on temporary copies of the
last-interaction sidecar and verify exact conflict/idempotency behavior.
"""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.interaction_request_claim import ClaimError, claim_sidecar, message_digest


class InteractionRequestClaimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "last_interaction.json"
        self.original = {
            "interaction": {
                "id": "H000001",
                "cycle": 7,
                "request_id": "issue-comment:old",
                "response_text": "prior response",
            },
            "response_text": "prior response",
            "current": {"question": None, "experiment": None},
        }
        self.path.write_text(
            json.dumps(self.original, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_claim_preserves_completed_sidecar_and_adds_exact_request(self):
        result = claim_sidecar(
            self.path, "issue-comment:123", "hello", "issue_comment"
        )
        self.assertTrue(result["claimed"])
        data = json.loads(self.path.read_bytes())
        self.assertEqual(data["interaction"], self.original["interaction"])
        self.assertEqual(data["response_text"], self.original["response_text"])
        self.assertEqual(
            data["pending_request"],
            {
                "version": "interaction-request-claim-v1",
                "request_id": "issue-comment:123",
                "message_sha256": message_digest("hello"),
                "event_name": "issue_comment",
            },
        )

    def test_same_claim_is_idempotent_without_rewriting(self):
        claim_sidecar(self.path, "workflow:777", "same", "workflow_dispatch")
        once = self.path.read_bytes()
        result = claim_sidecar(
            self.path, "workflow:777", "same", "workflow_dispatch"
        )
        self.assertFalse(result["claimed"])
        self.assertEqual(result["reason"], "already_claimed")
        self.assertEqual(self.path.read_bytes(), once)

    def test_conflicting_pending_request_fails_without_mutation(self):
        claim_sidecar(self.path, "issue-comment:1", "one", "issue_comment")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ClaimError, "different interaction request"):
            claim_sidecar(self.path, "issue-comment:2", "two", "issue_comment")
        self.assertEqual(self.path.read_bytes(), before)

        with self.assertRaisesRegex(ClaimError, "different interaction request"):
            claim_sidecar(self.path, "issue-comment:1", "changed", "issue_comment")
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_sidecar_does_not_create_new_tracked_path(self):
        missing = self.root / "missing.json"
        result = claim_sidecar(
            missing, "workflow:1", "first interaction", "workflow_dispatch"
        )
        self.assertFalse(result["claimed"])
        self.assertEqual(result["reason"], "sidecar_missing")
        self.assertFalse(missing.exists())

    def test_already_completed_request_does_not_add_pending_claim(self):
        result = claim_sidecar(
            self.path, "issue-comment:old", "ignored", "issue_comment"
        )
        self.assertFalse(result["claimed"])
        self.assertEqual(result["reason"], "already_completed")
        self.assertNotIn("pending_request", json.loads(self.path.read_bytes()))

    def test_invalid_existing_sidecar_fails_without_repair(self):
        self.path.write_bytes(b"{not-json")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ClaimError, "invalid last-interaction"):
            claim_sidecar(self.path, "issue-comment:1", "x", "issue_comment")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
