"""Fixed four-cycle integration and parity check; not a learning-benefit study.

Both copies retain the exact Phase 41 source and complete historical snapshot.
The comparator executes the original CLI stages directly, without the new bridge.
Only wall-clock timestamp fields are normalized. No path or desired action is set.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from ora2.baseline import STATE_BLOB, JOURNAL_BLOB, blob_id, strict_json
from ora2.lifecycle import STIMULUS, sha
from ora2.lifecycle_store import LifecycleSession

ROOT = Path(__file__).resolve().parents[1]
ISO_TIME = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$')


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, str):
        if ISO_TIME.fullmatch(value):
            return '<wall-clock timestamp>'
        if value.startswith(('{', '[')):
            try:
                return {'encoded_json': normalized(json.loads(value))}
            except ValueError:
                pass
    return value


def baseline_tick(work, root):
    # Independent composition of the preserved historical six-command contract.
    env = os.environ.copy()
    env.update(PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONPYCACHEPREFIX=str(work / 'unused-cache'))
    env.pop('OPENAI_API_KEY', None)
    env.pop('AGENTTEST_MODEL', None)
    prefix = [sys.executable, '-B', '-s', '-m', 'agenttest', '--state', str(work / 'organism.json')]
    steps = [
        ('cycle', ['cycle', '--planning-lab', '--grounded-experiments-only', '--self-observe',
                   '--root', str(root), '--stimulus', STIMULUS]),
        ('propose', ['propose', '--output', str(work / 'next_experiment.json')]),
        ('propose-change', ['propose-change', '--output', str(work / 'next_change.json')]),
        ('review-before', ['review-change', '--output', str(work / 'next_change_review.json')]),
        ('diagnose-change', ['diagnose-change', '--output', str(work / 'next_change_diagnostic.json')]),
        ('review-after', ['review-change', '--output', str(work / 'next_change_review.json')]),
    ]
    result = {}
    for key, args in steps:
        run = subprocess.run(prefix + args, cwd=root, env=env, capture_output=True, timeout=90)
        if run.returncode:
            raise AssertionError('direct Phase 41 stage failed: ' + key + ': ' + run.stderr.decode(errors='replace')[-2000:])
        result[key] = strict_json(run.stdout)
    return result


class PinnedLifecycleTests(unittest.TestCase):
    def test_four_complete_cycles_match_phase41_and_survive_restart(self):
        snapshot, journal = ROOT / 'state/organism.json', ROOT / 'state/journal.jsonl'
        available = snapshot.is_file() and journal.is_file()
        if not available and os.getenv('GITHUB_ACTIONS') != 'true':
            self.skipTest('complete historical checkout unavailable locally; required in hosted CI')
        self.assertTrue(available, 'hosted verification must have complete baseline files')
        raw, history = snapshot.read_bytes(), journal.read_bytes()
        self.assertEqual(blob_id(raw), STATE_BLOB)
        self.assertEqual(blob_id(history), JOURNAL_BLOB)
        initial = strict_json(raw)
        checks, journal_tail = [], bytearray()
        with tempfile.TemporaryDirectory(prefix='ora2-full-lifecycle-test-') as tmp:
            work = Path(tmp) / 'comparator'
            work.mkdir()
            (work / 'organism.json').write_bytes(raw)
            (work / 'journal.jsonl').write_bytes(history)
            database = Path(tmp) / 'candidate.sqlite'
            with LifecycleSession.create(database, ROOT, snapshot, journal,
                                         enabled=True, seed=17, cycle_limit=4) as session:
                for index in range(4):
                    ordinary = baseline_tick(work, ROOT)
                    candidate = session.tick('full-cycle-' + str(index), enabled=True)['result']
                    candidate_raw = session.db.execute('SELECT snapshot FROM current').fetchone()[0]
                    base_state, new_state = strict_json((work / 'organism.json').read_bytes()), strict_json(candidate_raw)
                    self.assertEqual(normalized(base_state), normalized(new_state), 'full Phase 41 state mismatch')
                    self.assertEqual(normalized(ordinary), normalized(candidate['outputs']), 'CLI result mismatch')
                    journal_tail.extend(candidate['journal_suffix'].encode())
                    candidate_journal = [strict_json(line) for line in (history + journal_tail).splitlines()]
                    base_journal = [strict_json(line) for line in (work / 'journal.jsonl').read_bytes().splitlines()]
                    self.assertEqual(normalized(base_journal), normalized(candidate_journal), 'complete logical journal mismatch')
                    for name, text in candidate['sidecars'].items():
                        self.assertEqual(normalized(strict_json(text)), normalized(strict_json((work / name).read_bytes())))
                    self.assertEqual(new_state['identity'], initial['identity'])
                    self.assertEqual(candidate['temporal']['ora2_choices'], 0)
                    checks.append({'cycle': candidate['cycle'], 'action_owner': candidate['temporal']['action_owner'],
                                   'new_transitions': candidate['temporal']['new_planner_transitions'],
                                   'scored': candidate['temporal']['prospectively_scored'],
                                   'prediction_loss_bits': (candidate['temporal']['learning_event'] or {}).get('predictive_loss_bits'),
                                   'position': new_state['planning_lab']['position'],
                                   'full_state_parity': True, 'complete_logical_journal_parity': True,
                                   'episodes': len(new_state.get('episodes', [])),
                                   'goals': len(new_state['planning_lab'].get('goals', []))})
                expected = session.status()
                first = session.tick('full-cycle-0', enabled=True)
                self.assertTrue(first['replayed'])
                self.assertEqual(session.status(), expected)
                self.assertEqual(session.db.execute('SELECT snapshot,journal FROM origin').fetchone(), (raw, history))
            with LifecycleSession(database, ROOT) as session:
                self.assertEqual(session.status(), expected)
                self.assertTrue(session.tick('full-cycle-0', enabled=True)['replayed'])
        self.assertEqual(snapshot.read_bytes(), raw)
        self.assertEqual(journal.read_bytes(), history)
        print('ORA2_FULL_LIFECYCLE_PARITY ' + json.dumps({
            'origin_cycle': initial['cycles'], 'cycle_pairs': 4, 'records': checks,
            'original_snapshot_sha256': sha(raw), 'original_journal_sha256': sha(history),
            'ora2_selected_actions_in_bridge': 0, 'live_actions': 0,
            'diagnostics_may_run_their_own_isolated_fixtures': True,
            'claim': 'full preserved Phase 41 lifecycle plus passive temporal learning; no benefit or control claim'
        }, sort_keys=True), flush=True)


if __name__ == '__main__':
    unittest.main()
