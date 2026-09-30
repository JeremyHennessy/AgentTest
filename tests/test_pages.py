from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PagesInteractionTests(unittest.TestCase):
    def test_pages_observer_uses_live_state_and_authenticated_handoff_without_embedded_secret(self) -> None:
        page = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("AgentTest · Live Observer", page)
        self.assertIn("autonomous/growth/state/last_interaction.json", page)
        self.assertIn("autonomous/growth/state/organism.json", page)
        self.assertIn("Exploration space", page)
        self.assertIn("Learned causal model", page)
        self.assertIn("Phase 32 learned-choice gate", page)
        self.assertIn("renderWorld", page)
        self.assertIn("renderEvidence", page)
        self.assertIn("https://github.com/JeremyHennessy/AgentTest/issues/new", page)
        self.assertIn('body:"/agent "+m', page)
        self.assertNotIn("github_pat_", page)
        self.assertNotIn("Authorization: Bearer", page)
        self.assertNotIn("OPENAI_API_KEY", page)

    def test_owner_created_issue_is_a_supported_interaction_transport(self) -> None:
        workflow = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")

        self.assertIn("issues:\n    types: [opened]", workflow)
        self.assertIn("github.actor == github.repository_owner", workflow)
        self.assertIn("startsWith(github.event.issue.body, '/agent ')", workflow)
        self.assertIn('ISSUE_BODY: \${{ github.event.issue.body }}', workflow)
        self.assertIn('elif event == "issues":', workflow)
        self.assertIn("Close one-shot interaction issue", workflow)
        self.assertIn('gh issue close "$ISSUE_NUMBER" --reason completed', workflow)


if __name__ == "__main__":
    unittest.main()
