from html.parser import HTMLParser
from pathlib import Path
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
            "2026-10-06 23:55 UTC", "4671b811c854223ff15ad5d3c520c511c6434421",
            "b3da508f6ebadc778cdb3cca5b9903997685d023",
            "intentionally closed unmerged", "new-world readiness is not established",
            "Separate activation approval", "No reward or authored solution",
        ):
            self.assertIn(required, handoff)
        self.assertIn("full decoded state", handoff)
        self.assertIn("must not restore an older state snapshot", handoff)
        self.assertIn("A historical input tested on", handoff)
        self.assertIn("docs/CURRENT_OPERATIONS.md", (ROOT / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
