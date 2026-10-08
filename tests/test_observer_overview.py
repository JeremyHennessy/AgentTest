"""Structural contracts for the fully rebuilt read-only Observer.

Legacy console remains unchanged; this test owns only the served Observer.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.links, self.tabs, self.panels, self.buttons = [], [], [], [], []
        self.feed(source)

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs)
        if attrs.get('role') == 'tab':
            self.tabs.append(attrs)
        if attrs.get('role') == 'tabpanel':
            self.panels.append(attrs)
        if tag == 'button':
            self.buttons.append(attrs)


class ObserverOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'observer.html').read_text()
        cls.js = (ROOT / 'observer.js').read_text()
        cls.css = (ROOT / 'observer.css').read_text()
        cls.page = Page(cls.html)

    def test_served_observer_replaced_without_changing_legacy_contract(self):
        workflow = (ROOT / '.github/workflows/pages.yml').read_text()
        self.assertIn('cp index.html _site/index.html', workflow)
        self.assertIn('cp legacy.html _site/legacy.html', workflow)
        self.assertIn('cmp index.html observer.html', workflow)
        self.assertIn('cmp legacy.html _site/legacy.html', workflow)
        self.assertEqual((ROOT / 'index.html').read_bytes(), (ROOT / 'observer.html').read_bytes())
        self.assertIn('AgentTest · Persistent Growth Console', (ROOT / 'legacy.html').read_text())
        self.assertTrue(any(a.get('href') == 'legacy.html' for a in self.page.links))
        self.assertIn('Ora Observatory', self.html)
        self.assertIn('Question the evidence.', self.html)

    def test_three_independent_accessible_views(self):
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        panels = {'panel-overview', 'panel-live', 'panel-research'}
        self.assertEqual({p['id'] for p in self.page.panels}, panels)
        self.assertEqual({t['aria-controls'] for t in self.page.tabs}, panels)
        self.assertEqual(sum(t['aria-selected'] == 'true' for t in self.page.tabs), 1)
        self.assertIn('ArrowDown', self.js)
        self.assertIn('ArrowRight', self.js)
        self.assertIn('data-go="live"', self.html)

    def test_scientific_truth_and_original_separation(self):
        for phrase in ('Original Ora and Ora 2 are deliberately separate.',
                       '12 / 12', '13 / 16', '1 / 4', '0 / 4',
                       '4 / 4', 'Not verified',
                       'Actions were evaluator-scripted',
                       '−0.002088', '−0.002784',
                       'Passive prediction is not autonomous control'):
            self.assertIn(phrase, self.html)
        self.assertNotIn('Ora 2 is conscious', self.html)
        self.assertNotIn('continuous pilot enabled', self.html.lower())

    def test_all_dynamic_sources_are_get_only_and_fail_closed(self):
        for value in ("method:'GET'", "credentials:'omit'", "cache:'no-store'",
                      'normalizeReceipt', 'normalizeSnapshot',
                      "status==='completed'", "result_cycle!==value.input_cycle+1",
                      "RAW+'/'+pinned+'/state/organism.json'",
                      "if(refreshing||document.hidden)return"):
            self.assertIn(value, self.js)
        for forbidden in ("Authorization", "github_pat_", "OPENAI_API_KEY",
                          "method:'POST'", "method:'PATCH'", "method:'PUT'",
                          "localStorage", "innerHTML", "eval(", "WebSocket"):
            self.assertNotIn(forbidden, self.js)
        self.assertIn("No completed result verified", self.js)
        self.assertIn('last successful read', self.js)

    def test_large_snapshot_explicit_only_and_pinned(self):
        self.assertIn("getJson(API+'/git/ref/heads/autonomous/growth')", self.js)
        self.assertIn("$('load-world').addEventListener('click',loadWorld)", self.js)
        self.assertIn('115*1024*1024', self.js)
        self.assertIn('This snapshot will not auto-refresh.', self.js)
        self.assertIn('Select a cell', self.html)

    def test_external_links_are_source_scoped_and_safe(self):
        for link in self.page.links:
            if link.get('target') == '_blank':
                self.assertIn('noopener', link.get('rel', ''))
                self.assertTrue(link['href'].startswith('https://github.com/JeremyHennessy/AgentTest'))

    def test_mobile_and_accessibility_rules_exist(self):
        for width in ('1180px', '900px', '680px', '390px'):
            self.assertIn('@media(max-width:' + width + ')', self.css)
        self.assertIn(':focus-visible', self.css)
        self.assertIn('prefers-reduced-motion', self.css)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('role="status"', self.html)

    def test_javascript_parses(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'observer.js'
            path.write_text(self.js)
            run = subprocess.run([node, '--check', str(path)], capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == '__main__':
    unittest.main()
