"""Finite integration checks against the complete preserved Phase 41 snapshot.

Eight free choices in an ISOLATED COPY; no learning-benefit acceptance threshold.
No original source/state or autonomous branch is written by this test.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from ora2.baseline import (ACTUATOR_BLOB, STATE_BLOB, JOURNAL_BLOB,
                           blob_id, read_origin, SOURCE_COMMIT, STATE_COMMIT)
from ora2.session import Session

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = (ROOT/'state/organism.json').is_file() and (ROOT/'src/agenttest/action_lab.py').is_file()


@unittest.skipUnless(AVAILABLE, 'full pinned Phase 41 checkout unavailable in this local workspace')
class PinnedPhase41IntegrationTests(unittest.TestCase):
    def test_full_origin_and_eight_unforced_copy_actions_survive_restart(self):
        snapshot, journal = ROOT/'state/organism.json', ROOT/'state/journal.jsonl'
        raw, history, origin = read_origin(snapshot, journal)
        self.assertEqual(blob_id(raw), STATE_BLOB)
        self.assertEqual(blob_id(history), JOURNAL_BLOB)
        self.assertEqual(blob_id((ROOT/'src/agenttest/action_lab.py').read_bytes()), ACTUATOR_BLOB)
        # This branch's historical source tree must remain exactly the Phase 41 tree.
        tree = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD:src'], text=True).strip()
        self.assertEqual(tree, '9b0f880af84a0b1b69fd6aa9009ab738acd7dfad')
        hashes_before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (snapshot, journal)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'ora2-copy.sqlite'
            with Session.create(path, snapshot, journal, enabled=True, seed=17, action_limit=8) as session:
                self.assertEqual(session.status()['new_actions'], 0)
                records = []
                for i in range(8):
                    value = session.tick(f'copy-smoke-{i}', enabled=True)
                    self.assertFalse(value['replayed'])
                    self.assertEqual(len(value['result']['experience']['choice']['menu']), 4)
                    records.append(value['result'])
                final = session.status()
                self.assertEqual(final['new_actions'], 8)
                self.assertTrue(session.tick('copy-smoke-0', enabled=True)['replayed'])
                self.assertEqual(session.status(), final)
                self.assertEqual(session.db.execute('SELECT snapshot,journal FROM origin').fetchone(), (raw, history))
            with Session(path) as reopened:
                self.assertEqual(reopened.status(), final)
            receipt = {'source_commit': SOURCE_COMMIT, 'state_commit': STATE_COMMIT,
                       'origin_cycle': origin['origin_cycle'], 'identity': origin['identity'],
                       'delivered_rows': origin['delivered_rows'], 'inherited_rows': len(origin['rows']),
                       'other_world_rows': origin['other_world_rows'], 'duplicate_rows': origin['duplicate_rows'],
                       'free_choice_actions_in_copy': 8, 'live_actions': 0,
                       'final_position': final['position'], 'head': final['head'],
                       'records': records,
                       'scope': 'software integration smoke only; no learning-benefit or live milestone claim'}
            print('ORA2_PINNED_INTEGRATION ' + json.dumps(receipt, sort_keys=True), flush=True)
        self.assertEqual(hashes_before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in (snapshot, journal)])
