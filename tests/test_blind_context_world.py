"""Engineering tests only: do NOT certify a behavioral study or world benefit."""
from dataclasses import replace
import json
import unittest

from ora2.blind_context_world import (
    ACTIONS, GENESIS, VERSION, BlindContextWorld, InvalidWorldEvidence,
)


STREAM = "ef0e7ddc570f4a07a7aabbccddeeff00"


class BlindContextWorldTest(unittest.TestCase):
    def test_public_initial_state_never_exposes_rules_or_seed(self):
        worlds = [BlindContextWorld(stream_id=STREAM, seed=i) for i in (0, 1, 2, 2026)]
        views = [w.public_view() for w in worlds]
        self.assertTrue(all(v == views[0] for v in views))
        self.assertEqual(views[0]['position'], [0, 0])
        self.assertEqual(views[0]['available_actions'], list(ACTIONS))
        for name in ('seed', 'barriers', 'rule', 'change_at', 'reward', 'solution'):
            self.assertNotIn(name, json.dumps(views[0]).lower())

    def test_receipts_are_precise_and_linked_across_change_point(self):
        world = BlindContextWorld(stream_id=STREAM, seed=715, budget=64)
        receipts = [world.step(ACTIONS[i % 4]) for i in range(64)]
        self.assertEqual([r.index for r in receipts], list(range(1, 65)))
        self.assertEqual(receipts[0].predecessor, GENESIS)
        for previous, current in zip(receipts, receipts[1:]):
            self.assertEqual(current.predecessor, previous.digest)
        for r in receipts:
            self.assertEqual(len(r.digest), 64)
            self.assertEqual(r.version, VERSION)
            self.assertEqual(r.blocked, r.before == r.after)
            self.assertTrue(all(-2 <= p <= 2 for p in r.after))
            self.assertNotIn('seed', r.evidence())
            self.assertNotIn('regime', r.evidence())
        with self.assertRaises(InvalidWorldEvidence):
            world.step(ACTIONS[0])

    def test_reconstruction_is_byte_exact_and_admits_repeated_actions(self):
        world = BlindContextWorld(stream_id=STREAM, seed=406, budget=56)
        actions = [ACTIONS[(i * i + i + 1) % 4] for i in range(56)]
        for action in actions:
            world.step(action)
        restored = BlindContextWorld.reconstruct(stream_id=STREAM, seed=406, budget=56,
                                                  receipts=world.recorded())
        self.assertEqual(restored.recorded(), world.recorded())
        self.assertEqual(restored.public_view(), world.public_view())
        with self.assertRaises(InvalidWorldEvidence):
            BlindContextWorld.reconstruct(stream_id=STREAM, seed=407, budget=56,
                                          receipts=world.recorded())

    def test_tamper_and_reorder_fail_closed(self):
        world = BlindContextWorld(stream_id=STREAM, seed=44, budget=32)
        for action in ACTIONS * 8:
            world.step(action)
        receipts = list(world.recorded())
        for bad in (
            [replace(receipts[0], digest='f' * 64), *receipts[1:]],
            [*receipts[:2], receipts[3], receipts[2], *receipts[4:]],
            [*receipts, receipts[-1]],
            [dict(receipts[0].evidence()), *receipts[1:]],
        ):
            with self.subTest(case=str(type(bad[0]))):
                with self.assertRaises(InvalidWorldEvidence):
                    BlindContextWorld.reconstruct(stream_id=STREAM, seed=44, budget=32, receipts=bad)

    def test_illegal_actions_seeds_and_budget_do_not_advance_state(self):
        for seed in (-1, 2**63, True, 1.0, '1'):
            with self.subTest(seed=seed):
                with self.assertRaises(InvalidWorldEvidence):
                    BlindContextWorld(stream_id=STREAM, seed=seed)
        for budget in (0, 65, True, 12.5):
            with self.subTest(budget=budget):
                with self.assertRaises(InvalidWorldEvidence):
                    BlindContextWorld(stream_id=STREAM, seed=4, budget=budget)
        world = BlindContextWorld(stream_id=STREAM, seed=12, budget=2)
        for action in ('north', 'TOKEN-A', '', None, True):
            with self.subTest(action=action):
                with self.assertRaises(InvalidWorldEvidence):
                    world.step(action)
        self.assertEqual(world.public_view()['steps_completed'], 0)

    def test_multiple_seeds_exhibit_distinct_outcomes_not_staged_solutions(self):
        streams = []
        for seed in range(20):
            world = BlindContextWorld(stream_id=STREAM, seed=seed)
            stream = tuple((r.before, r.after, r.blocked)
                           for r in (world.step(ACTIONS[i % 4]) for i in range(64)))
            streams.append(stream)
        self.assertGreater(len(set(streams)), 10)

    def test_distinct_world_streams_have_distinct_provenance_for_same_outcome(self):
        streams = ("ef0e7ddc570f4a07a7aabbccddeeff00", "ef0e7ddc570f4a07a7aabbccddeeff01")
        a, b = [BlindContextWorld(seed=120, stream_id=x) for x in streams]
        self.assertEqual(a.public_view(), b.public_view())
        ar, br = a.step(ACTIONS[0]), b.step(ACTIONS[0])
        self.assertEqual(ar.after, br.after)
        self.assertNotEqual(ar.digest, br.digest)
        self.assertNotEqual(ar.evidence()['source'], br.evidence()['source'])

    def test_no_action_or_goal_runs_without_explicit_step(self):
        world = BlindContextWorld(stream_id=STREAM, seed=900)
        self.assertEqual(world.recorded(), ())
        self.assertEqual(world.public_view()['steps_completed'], 0)
        self.assertEqual(world.public_view()['remaining_budget'], 64)


if __name__ == '__main__':
    unittest.main()
