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

    def test_workflow_reuses_history_and_deduplicates_reply(self):
        workflow = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")
        self.assertIn("/tmp/agenttest-reused-interaction.json", workflow)
        self.assertIn("Ambiguous persisted interaction request identity.", workflow)
        self.assertIn("agenttest-request:$INTERACTION_REQUEST_ID", workflow)
        self.assertIn("grep -Fq -- \"$MARKER\"", workflow)
        self.assertIn('gh issue view "$ISSUE_NUMBER" --json state --jq .state', workflow)

    def test_workflow_does_not_use_message_text_as_request_identity(self):
        workflow = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")
        self.assertNotIn("request_id = message", workflow)
        self.assertNotIn("hash(message", workflow.lower())


if __name__ == "__main__":
    unittest.main()
