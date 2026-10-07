from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs.get("href"))
        if "id" in attrs:
            self.ids.append(attrs["id"])


class CurrentOperationalHandoffTests(unittest.TestCase):
    def test_observer_separates_live_copied_and_activation(self):
        page = (ROOT / "index.html").read_text(encoding="utf-8")
        section = page.split('<details id="worldReadiness">', 1)[1].split("</details>", 1)[0]
        for required in (
            "Live:", "Current-code compatibility:", "Before a new world:",
            "Activation:", "separately withheld", "Null results stay visible",
            "separate owner approval", "historical archive",
            "not current live achievements", "422-test compatibility check",
        ):
            self.assertIn(required, section)
        parsed = Links()
        parsed.feed(page)
        self.assertEqual(len(parsed.ids), len(set(parsed.ids)))
        self.assertIn("https://github.com/JeremyHennessy/AgentTest/pull/213", parsed.links)
        self.assertIn("https://github.com/JeremyHennessy/AgentTest/blob/main/docs/CURRENT_OPERATIONS.md", parsed.links)

    def test_handoff_carries_dated_evidence_and_unmet_gates(self):
        handoff = (ROOT / "docs/CURRENT_OPERATIONS.md").read_text(encoding="utf-8")
        for required in (
            "2026-10-07 02:05 UTC", "2af18427c42c80cb61391d802fa07b80f3513cf6",
            "b3da508f6ebadc778cdb3cca5b9903997685d023",
            "intentionally closed unmerged", "New-world readiness is not established",
            "Separate owner activation decision", "an authored solution or a hidden reward target",
        ):
            self.assertIn(required, handoff)
        self.assertIn("full decoded", handoff)
        self.assertIn("restore an older state as rollback", handoff)
        self.assertIn("Input was historical cycle 4599, not the current organism", handoff)
        self.assertIn("docs/CURRENT_OPERATIONS.md", (ROOT / "README.md").read_text())


class CurrentOperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = (ROOT / "docs/CURRENT_OPERATIONS.md").read_text(encoding="utf-8")

    def section(self, heading: str) -> str:
        start = self.document.index("## " + heading + "\n")
        return self.document[start:].split("\n## ", 1)[0]

    def test_operations_identify_a_dated_checkpoint_and_remaining_storage_limit(self) -> None:
        checkpoint = self.section("Authority and checkpoint")
        self.assertIn("2af18427c42c80cb61391d802fa07b80f3513cf6", checkpoint)
        self.assertIn("dcef1bed0881178f1b804cea806b0eb5c6b12963", checkpoint)
        self.assertIn("Later growth is not measured by these figures", checkpoint)
        operations = self.section("Completed operations and remaining limits")
        for expected in ("#214", "#215", "#216", "queue: max", "cancel-in-progress: false"):
            self.assertIn(expected, operations)
        self.assertIn("journal is still unbounded", operations)
        self.assertIn("no\nsegmentation", operations)

    def test_frozen_study_keeps_its_negative_and_unevaluated_results(self) -> None:
        evidence = self.section("Frozen research: what the evidence actually says")
        for expected in (
            "historical cycle 4599", "influence, not benefit", "0/8 default-flag",
            "0/8 production-flag", "4/32", "5/5", "Alternate commands were not executed",
            "zero genuine evidence-backed", "Held-out execution never ran",
            "protocol is not a readiness\n  prerequisite",
        ):
            self.assertIn(expected, evidence)

    def test_legacy_counter_is_preserved_but_not_a_forward_gate(self) -> None:
        audit = self.section("Why Phase 42 is being redesigned")
        self.assertIn("127 qualified alternatives", audit)
        self.assertIn("retained-window", audit)
        self.assertIn("retire it as a mandatory new-world gate", audit)
        self.assertIn("withholds current repository-prediction evaluation only", audit)
        self.assertIn("No forced resumption, score tuning", audit)

    def test_proposed_slice_and_science_are_separate_from_safety(self) -> None:
        plan = self.section("Proposed ground-up architecture and next steps")
        for expected in (
            "durable investigation", "pre-action predictions", "versioned belief",
            "copied-only", "single-use action", "slice is not yet implemented",
            "source-general causal measure", "policy/science",
        ):
            self.assertIn(expected, plan)
        science = self.section("Science acceptance gates")
        for expected in ("Selection controls action", "independent fixed scorers", "lifecycle", "null and adverse"):
            self.assertIn(expected, science)
        safety = self.section("Safety and operational acceptance gates")
        for expected in ("Authority", "Persistence and replay", "Sustainable lossless history", "Baseline preservation", "Reviewed rollout"):
            self.assertIn(expected, safety)

    def test_activation_requires_a_separate_owner_decision(self) -> None:
        activation = self.section("Separate owner activation decision")
        self.assertIn("owner must explicitly authorize new-world", activation)
        self.assertIn("do not grant that activation", activation)
        self.assertIn("spending or expanded access", activation)

    def test_relative_document_links_exist(self) -> None:
        links = re.findall(r"\]\(([^)]+)\)", self.document)
        for target in links:
            if "://" not in target and not target.startswith("#"):
                with self.subTest(target=target):
                    self.assertTrue((ROOT / "docs" / target.split("#", 1)[0]).is_file())


if __name__ == "__main__":
    unittest.main()
