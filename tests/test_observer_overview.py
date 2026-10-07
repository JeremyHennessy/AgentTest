"""Checks the new served Observer. Existing test_pages.py still protects legacy.html.
The source index.html is deliberately unchanged, not a substitute for these checks.
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
        super().__init__();self.ids=[];self.links=[];self.tabs=[];self.panels=[];self.feed(source)
    def handle_starttag(self, tag, pairs):
        attrs=dict(pairs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='a':self.links.append(attrs)
        if attrs.get('role')=='tab':self.tabs.append(attrs)
        if attrs.get('role')=='tabpanel':self.panels.append(attrs)

class ObserverOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'observer.html').read_text()
        cls.page=Page(cls.source)
        cls.script=(ROOT/'observer.js').read_text()
        cls.source += '\n' + cls.script
    def test_new_home_and_preserved_legacy_are_both_built(self):
        workflow=(ROOT/'.github/workflows/pages.yml').read_text()
        self.assertIn('cp observer.html _site/index.html',workflow)
        self.assertIn('cp index.html _site/legacy.html',workflow)
        self.assertIn('cmp observer.html _site/index.html',workflow)
        self.assertIn('cmp index.html _site/legacy.html',workflow)
        self.assertTrue(any(a.get('href')=='legacy.html' for a in self.page.links))
    def test_ids_unique_and_tabs_have_explicit_owners(self):
        self.assertEqual(len(self.page.ids),len(set(self.page.ids)))
        self.assertEqual({p['id'] for p in self.page.panels},{'panel-lab','panel-live'})
        self.assertEqual({t['aria-controls'] for t in self.page.tabs},{'panel-lab','panel-live'})
        self.assertEqual(sum(t['aria-selected']=='true' for t in self.page.tabs),1)
    def test_copy_and_live_scope_remain_explicit(self):
        for phrase in ['Recorded copied experiment · not a live pilot','Learner-selected actions',
                       'Planner-selected transitions','Live actions in this test',
                       'The test scheduled the opportunity. The learner chose the command.',
                       'A passing old test does not verify the correction.']:
            self.assertIn(phrase,self.source)
    def test_negative_results_and_real_source_links_remain_visible(self):
        for phrase in ['Three comparisons favored random exploration.','Longer recent history added no measurable benefit.',
                       '38.9 versus 23.8']:
            self.assertIn(phrase,self.source)
        self.assertIn('37694360216',self.source)
        self.assertIn('58e79e4a15566d4e20c807f78e67e7709fdca192',self.source)
        self.assertIn('6048629547',self.source)
    def test_reader_has_no_write_or_model_authority(self):
        self.assertIn("method:'GET'",self.script)
        for forbidden in ('Authorization','github_pat_','OPENAI_API_KEY','method:\'POST\'',
                          'method:\'PATCH\'','method:\'PUT\'','WebSocket','XMLHttpRequest','eval('):
            self.assertNotIn(forbidden,self.script)
        self.assertNotIn('localStorage',self.script)
        self.assertNotIn('innerHTML',self.script)
    def test_explicit_large_snapshot_read_is_pinned(self):
        self.assertIn("RAW+'/'+pinned+'/state/organism.json'",self.script)
        self.assertIn("$('load-live-map').addEventListener('click',loadMap)",self.script)
        self.assertIn("if(refreshing||document.hidden)return",self.script)
        self.assertIn('300000',self.script)
        self.assertIn('last successful read',self.script)
        self.assertIn('newer heartbeat exists',self.script)
    def test_external_links_do_not_gain_opener(self):
        for link in self.page.links:
            if link.get('target')=='_blank':
                self.assertIn('noopener',link.get('rel',''))
                self.assertTrue(link['href'].startswith('https://github.com/JeremyHennessy/AgentTest'))
    def test_javascript_parses(self):
        node=shutil.which('node')
        self.assertIsNotNone(node,'Node is required for the served-page syntax check')
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'observer.js';source.write_text(self.script)
            run=subprocess.run([node,'--check',str(source)],capture_output=True,text=True,timeout=15)
            self.assertEqual(run.returncode,0,run.stderr)

if __name__=='__main__':unittest.main()
