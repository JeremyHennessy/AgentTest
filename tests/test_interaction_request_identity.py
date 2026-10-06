"""Stable transport identity for human interactions.

These tests verify duplicate transport IDs fail before another Core cycle while
ordinary interaction calls without a transport ID preserve their previous shape.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agenttest.interaction import interact
from agenttest.state import StateStore


class InteractionRequestIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StateStore(Path(self.tmp.name) / "organism.json")

    def test_request_identity_is_persisted_in_record_and_journal(self):
        result = interact(
            "stable transport request",
            store=self.store,
            request_id="issue-comment:12345",
        )
        state = self.store.load()
        self.assertEqual(result["interaction"]["request_id"], "issue-comment:12345")
        self.assertEqual(state["interactions"][-1]["request_id"], "issue-comment:12345")
        event = json.loads(self.store.journal_path.read_bytes().splitlines()[-1])
        self.assertEqual(event["event"], "human_interaction")
        self.assertEqual(event["request_id"], "issue-comment:12345")

    def test_duplicate_request_fails_before_another_core_cycle(self):
        interact(
            "same transport request",
            store=self.store,
            request_id="workflow:777",
        )
        before_state = self.store.path.read_bytes()
        before_journal = self.store.journal_path.read_bytes()
        with patch("agenttest.interaction.AgentCore.cycle") as cycle:
            with self.assertRaisesRegex(ValueError, "already recorded"):
                interact(
                    "same transport request",
                    store=self.store,
                    request_id="workflow:777",
                )
        cycle.assert_not_called()
        self.assertEqual(self.store.path.read_bytes(), before_state)
        self.assertEqual(self.store.journal_path.read_bytes(), before_journal)

    def test_same_text_with_distinct_transport_ids_is_not_deduplicated(self):
        first = interact(
            "same text is allowed as a new request",
            store=self.store,
            request_id="issue-comment:100",
        )
        second = interact(
            "same text is allowed as a new request",
            store=self.store,
            request_id="issue-comment:101",
        )
        self.assertNotEqual(first["interaction"]["id"], second["interaction"]["id"])
        self.assertEqual(self.store.load()["cycles"], 2)
        self.assertEqual(len(self.store.load()["interactions"]), 2)

    def test_default_interaction_shape_does_not_gain_transport_field(self):
        result = interact("legacy/default interaction", store=self.store)
        record = result["interaction"]
        self.assertNotIn("request_id", record)
        event = json.loads(self.store.journal_path.read_bytes().splitlines()[-1])
        self.assertNotIn("request_id", event)

    def test_invalid_request_identity_rejects_before_cycle(self):
        with patch("agenttest.interaction.AgentCore.cycle") as cycle:
            with self.assertRaisesRegex(ValueError, "stable transport identifier"):
                interact(
                    "invalid request",
                    store=self.store,
                    request_id="bad request with spaces",
                )
        cycle.assert_not_called()
        self.assertFalse(self.store.path.exists())


if __name__ == "__main__":
    unittest.main()
