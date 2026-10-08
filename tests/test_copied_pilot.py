"""Finite copied-pilot engineering tests, not a scientific benefit gate."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from ora2.copied_pilot import advance, canonical, digest, files, restore, worker
from ora2.blind_context_world import BlindContextWorld


STREAM = 'abcdef0123456789abcdef0123456789'


class CopiedPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'copied-ledger.json'

    def test_requires_explicit_enable(self):
        with self.assertRaisesRegex(ValueError, 'explicit'):
            advance(self.path, seed=3, stream_id=STREAM, budget=8)
        self.assertFalse(self.path.exists())

    def test_ledger_replay_and_exact_budget_across_restarts(self):
        before = tuple(digest(p) for p in files())
        first = advance(self.path, enabled=True, seed=3, stream_id=STREAM, budget=8, steps=3)
        self.assertEqual(first['completed_actions'], 3)
        second = advance(self.path, enabled=True, resume=True, steps=5)
        self.assertEqual(second['completed_actions'], 8)
        self.assertEqual(second['learner_actions'], 8)
        self.assertEqual(second['original_live_ora_actions'], 0)
        self.assertFalse(second['persistent_original_ora2_enabled'])
        world, history, head = restore(json.loads(self.path.read_bytes()))
        self.assertEqual(len(history), 8)
        self.assertEqual(head, second['head'])
        self.assertEqual(world.public_view()['remaining_budget'], 0)
        self.assertEqual(tuple(digest(p) for p in files()), before)
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            advance(self.path, enabled=True, resume=True, steps=1)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_reject_tamper_and_preserve_ledger(self):
        advance(self.path, enabled=True, seed=4, stream_id=STREAM, budget=8, steps=2)
        saved = json.loads(self.path.read_bytes())
        for field, changed in [('head', 'f'*64), ('log_loss_bits', 0.0)]:
            tampered = copy.deepcopy(saved)
            tampered['records'][0][field] = changed
            self.path.write_bytes(canonical(tampered))
            raw = self.path.read_bytes()
            with self.assertRaises(ValueError):
                advance(self.path, enabled=True, resume=True, steps=1)
            self.assertEqual(self.path.read_bytes(), raw)
        self.path.write_bytes(canonical(saved))
        self.assertEqual(restore(saved)[1][-1], saved['records'][-1]['evidence'])

    def test_worker_sees_only_public_fields_and_no_hidden_rules(self):
        world = BlindContextWorld(seed=42, stream_id=STREAM, budget=8)
        view = world.public_view()
        answer = worker(view, [])
        self.assertIn(answer['action'], view['available_actions'])
        self.assertEqual(len(answer['forecast']), 25)
        self.assertNotIn('seed', view)
        self.assertNotIn('barriers', view)
        self.assertNotIn('change_at', view)
        self.assertNotIn('rules', view)
        with self.assertRaises(ValueError):
            worker({**view, 'seed': 42}, [])

    def test_ledger_cannot_be_written_inside_source_checkout(self):
        source = Path(__file__).resolve().parents[1] / 'state' / 'pilot.json'
        with self.assertRaisesRegex(ValueError, 'independent'):
            advance(source, enabled=True, seed=3, stream_id=STREAM, budget=8)


if __name__ == '__main__':
    unittest.main()
