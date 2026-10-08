"""Synthetic preflight of registered evaluator. Never use study seeds 0..11 here."""
from __future__ import annotations

import math
import unittest

from ora2.blind_context_study001 import (
    DOMAIN, InvalidStudy, evaluate_world, schedule, stream, strong_spatial,
    validate,
)
from ora2.blind_context_world import ACTIONS, BlindContextWorld
from ora2.pilot_worker import forecast


class BlindContextStudyPreflight(unittest.TestCase):
    def test_schedule_is_deterministic_and_opaque(self):
        self.assertEqual(schedule(99, 1), schedule(99, 1))
        self.assertIn(schedule(99, 40), ACTIONS)
        self.assertEqual(len(stream(99)), 32)
        self.assertNotEqual(stream(99), stream(100))

    def test_strong_spatial_equals_candidate_without_local_counterevidence(self):
        world = BlindContextWorld(seed=99, stream_id=stream(99), budget=64)
        view = world.public_view()
        self.assertEqual(strong_spatial(view, [], ACTIONS[0]),
                         forecast(view, [], ACTIONS[0]))
        self.assertEqual(len(DOMAIN), 25)

    def test_reject_invalid_probability(self):
        with self.assertRaises(InvalidStudy):
            validate([0.0] * 25)
        with self.assertRaises(InvalidStudy):
            validate([1/24] * 24 + [float('nan')])
        validate([1/25] * 25)

    def test_full_synthetic_seed_outside_registered_cohort(self):
        result = evaluate_world(99)
        self.assertEqual(result["seed"], 99)
        self.assertEqual(result["actions"], 64)
        self.assertEqual(result["warmup"], 16)
        self.assertEqual(result["scored"], 48)
        self.assertEqual(len(result["cases"]), 48)
        self.assertTrue(math.isfinite(result["mean_advantage_bits"]))
        self.assertEqual([c["index"] for c in result["cases"]], list(range(17, 65)))
        for case in result["cases"]:
            self.assertEqual(case["action"], schedule(99, case["index"]))
            self.assertEqual(list(case["receipt"]["after"]), case["actual_after"])
            self.assertEqual(case["receipt"]["digest"], case["evidence"]["source_id"])
            self.assertTrue(math.isfinite(case["advantage_bits"]))


if __name__ == "__main__":
    unittest.main()
