"""Static contracts, not a simulation of GitHub's hosted scheduler."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github/workflows'


def concurrency(text):
    match = re.search(r'^concurrency:\n((?:[ \t]+[^\n]*\n|\n)+)', text, re.M)
    if not match:
        return {}
    return dict(re.findall(r'^  ([\w-]+): ([^\n]+)$', match.group(1), re.M))


class StateWriterConcurrencyTests(unittest.TestCase):
    def test_all_growth_branch_writers_share_one_non_cancelling_queue(self):
        writers = {}
        for path in WORKFLOWS.glob('*.yml'):
            text = path.read_text(encoding='utf-8')
            if re.search(r'git\s+push\s+origin\s+autonomous/growth(?:\s|$)', text):
                writers[path.name] = text
        self.assertEqual(set(writers), {'growth.yml', 'interact.yml', 'reconcile.yml'})
        for name, text in writers.items():
            with self.subTest(workflow=name):
                self.assertEqual(concurrency(text), {
                    'group': 'agenttest-autonomous-growth-v2',
                    'queue': 'max',
                    'cancel-in-progress': 'false',
                })
                self.assertIn('fetch-depth: 0', text)
                self.assertIn('filter: blob:none', text)
                self.assertNotIn('gh run watch', text)
                self.assertNotIn('gh workflow run', text)
                self.assertNotIn('gh run cancel', text)

    def test_dispatching_controller_never_holds_the_writer_group(self):
        text = (WORKFLOWS / 'heartbeat-controller.yml').read_text(encoding='utf-8')
        self.assertEqual(concurrency(text)['group'], 'agenttest-heartbeat-controller-v2')
        self.assertNotEqual(concurrency(text)['group'], 'agenttest-autonomous-growth-v2')
        self.assertIn('Wait for reconciliation lane', text)
        self.assertIn('gh run watch', text)
        self.assertNotIn('git push origin autonomous/growth', text)

    def test_reconciliation_keeps_verified_main_event_guard(self):
        text = (WORKFLOWS / 'reconcile.yml').read_text(encoding='utf-8')
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.event == 'push'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)
        self.assertIn('git merge --no-edit origin/main', text)
        self.assertNotIn('git push --force', text)
        self.assertNotIn('git reset --hard', text)


if __name__ == '__main__':
    unittest.main()
