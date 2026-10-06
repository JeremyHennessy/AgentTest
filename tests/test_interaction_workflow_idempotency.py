"""Static governance checks for interaction workflow idempotency.

Network behavior is not executed here. These checks make the protected workflow
contract explicit while normal functional interaction tests cover state behavior.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InteractionWorkflowIdempotencyTests(unittest.TestCase):
    def test_workflow_uses_stable_event_identities_and_reuse_gate(self):
        workflow = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")
        self.assertIn('request_id = "workflow:" + os.environ["RUN_ID"]', workflow)
        self.assertIn('request_id = "issue-comment:" + os.environ["COMMENT_ID"]', workflow)
        self.assertIn('request_id = "issue:" + os.environ["ISSUE_ID"]', workflow)
        self.assertIn('request_id = "push:" + os.environ["PUSH_SHA"]', workflow)
        self.assertIn("REUSE_INTERACTION", workflow)
        self.assertIn("row.get(\"request_id\") == request_id", workflow)
        self.assertIn("--request-id \"$INTERACTION_REQUEST_ID\"", workflow)
        self.assertIn("env.REUSE_INTERACTION != 'true'", workflow)
        self.assertIn("filter: blob:none", workflow)
        self.assertIn("Claim interaction request remotely", workflow)
        self.assertIn("scripts/interaction_request_claim.py", workflow)
        self.assertIn('git commit -m "Claim human interaction request"', workflow)
        self.assertIn("git push origin autonomous/growth", workflow)

    def test_workflow_reuses_history_and_deduplicates_reply(self):
        workflow = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")
        self.assertIn("/tmp/agenttest-reused-interaction.json", workflow)
        self.assertIn("Ambiguous persisted interaction request identity.", workflow)
        self.assertIn("agenttest-request:$INTERACTION_REQUEST_ID", workflow)
        self.assertIn("grep -Fq -- \"$MARKER\"", workflow)
        self.assertIn('gh issue view "$ISSUE_NUMBER" --json state --jq .state', workflow)
        self.assertGreaterEqual(workflow.count("          import os"), 2)
        self.assertIn('source = Path(os.environ["INTERACTION_RESPONSE_SOURCE"])', workflow)

    def test_growth_and_interaction_share_versioned_serialization_group(self):
        interaction = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")
        growth = (ROOT / ".github/workflows/growth.yml").read_text(encoding="utf-8")
        group = "group: agenttest-autonomous-growth-v2"
        self.assertIn(group, interaction)
        self.assertIn(group, growth)
        self.assertNotIn("group: agenttest-autonomous-growth\n", interaction)
        self.assertNotIn("group: agenttest-autonomous-growth\n", growth)

    def test_workflow_does_not_use_message_text_as_request_identity(self):
        workflow = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")
        self.assertNotIn("request_id = message", workflow)
        self.assertNotIn("hash(message", workflow.lower())


if __name__ == "__main__":
    unittest.main()
