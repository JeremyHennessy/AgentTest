from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PagesInteractionTests(unittest.TestCase):
    def test_pages_console_uses_authenticated_github_handoff_without_embedded_secret(self) -> None:
        page = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("AgentTest · Persistent Growth Console", page)
        self.assertIn("autonomous/growth/state/last_interaction.json", page)
        self.assertIn("autonomous/growth/state/organism.json", page)
        self.assertIn("Bounded Action Lab", page)
        self.assertIn("renderActionLab", page)
        self.assertIn("Phase 36 · episodic route memory", page)
        self.assertIn("Phase 37 · bounded transfer", page)
        self.assertIn("renderMemory", page)
        self.assertIn("renderTransfer", page)
        self.assertIn("transfer_probes", page)
        self.assertIn("episodic_route_memories", page)
        self.assertIn("Right now", page)
        self.assertIn("Evidence & history", page)
        self.assertIn("System internals & verified changes", page)
        self.assertIn("renderNow", page)
        self.assertIn('id="capabilityLadder"', page)
        self.assertIn("Ora, right now.", page)
        self.assertIn("Phase 38 · self-generated falsifiable experiments", page)
        self.assertIn("renderSelfExperiment", page)
        self.assertIn("self_experiments", page)
        self.assertIn("Phase 39 · self-selected objectives", page)
        self.assertIn("Phase 40 · objective information realization", page)
        self.assertIn("renderObjectiveSelection", page)
        self.assertIn("renderObjectiveRealization", page)
        self.assertIn("objective_decisions", page)
        self.assertIn("objective_realizations", page)
        self.assertIn('id="selfExperimentMarks"', page)
        self.assertIn("planningPhaseNumber", page)
        self.assertIn("Latest milestone", page)
        self.assertIn("https://github.com/JeremyHennessy/AgentTest/issues/new", page)
        self.assertIn('body: "/agent " + message', page)
        self.assertNotIn("github_pat_", page)
        self.assertNotIn("Authorization: Bearer", page)
        self.assertNotIn("OPENAI_API_KEY", page)

    def test_owner_created_issue_is_a_supported_interaction_transport(self) -> None:
        workflow = (ROOT / ".github/workflows/interact.yml").read_text(encoding="utf-8")

        self.assertIn("issues:\n    types: [opened]", workflow)
        self.assertIn("github.actor == github.repository_owner", workflow)
        self.assertIn("startsWith(github.event.issue.body, '/agent ')", workflow)
        self.assertIn('ISSUE_BODY: ${{ github.event.issue.body }}', workflow)
        self.assertIn('elif event == "issues":', workflow)
        self.assertIn("Close one-shot interaction issue", workflow)
        self.assertIn('gh issue close "$ISSUE_NUMBER" --reason completed', workflow)


if __name__ == "__main__":
    unittest.main()
