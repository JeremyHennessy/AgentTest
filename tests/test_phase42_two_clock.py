"""Two-clock mechanism and entire frozen-panel integrity tests, offline."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from agenttest import two_clock_memory as brain
from phase42_two_clock_study import (
    PANEL, SCENARIOS, _differential, _run_one, _observed, run_study,
)


def row(index, before, action, after):
    return {
        "id": f"E{index:06d}", "index": index,
        "before": list(before), "action": action, "after": list(after),
    }


class TwoClockMemoryTests(unittest.TestCase):
    def test_no_privileged_world_or_intervention_signal_enters_learner(self):
        code = Path(brain.__file__).read_text(encoding="utf-8")
        for banned in (
            "from .action_lab", "apply_bounded_action",
            "_HIDDEN_STATEFUL_BLOCKS", "_HIDDEN_TRANSFER_BLOCKS",
            "STATEFUL_WORLD_VERSION", "TRANSFER_WORLD_VERSION",
            "intervention_label", "openai",
        ):
            self.assertNotIn(banned, code)

    def test_one_conflicting_outcome_does_not_trigger_global_forgetting(self):
        mem = brain.TwoClockMemory()
        for index in range(1, 7):
            self.assertEqual(mem.observe(row(index, [0, 2], "south", [0, 2])), [])
        previous = mem.predict([0, 2], "south", arm="two_clock")
        self.assertEqual(mem.observe(row(7, [0, 2], "south", [-1, 2])), [])
        updated = mem.predict([0, 2], "south", arm="two_clock")
        self.assertEqual(updated["basis"], "lifetime_local")
        self.assertIsNone(updated["active_local_marker"])
        self.assertGreater(updated["distribution"]["-1,0"],
                           previous["distribution"]["-1,0"])
        self.assertEqual(len(mem.events), 7)

    def test_two_matching_contradictions_change_only_local_view(self):
        mem = brain.TwoClockMemory()
        for index in range(1, 7):
            mem.observe(row(index, [0, 2], "south", [0, 2]))
        mem.observe(row(7, [0, 2], "south", [-1, 2]))
        predicted_before = mem.predict([0, 2], "south", arm="two_clock")
        change = mem.observe(row(8, [0, 2], "south", [-1, 2]))
        self.assertEqual(len(change), 1)
        marker = change[0]
        self.assertEqual(marker["start_index"], 7)
        self.assertEqual(marker["confirmation_index"], 8)
        self.assertEqual(marker["prior_modal"], "0,0")
        self.assertEqual(marker["recent_modal"], "-1,0")
        after = mem.predict([0, 2], "south", arm="two_clock")
        static = mem.predict([0, 2], "south", arm="lifetime")
        self.assertEqual(after["basis"], "confirmed_local_change")
        self.assertGreater(after["distribution"]["-1,0"],
                           predicted_before["distribution"]["-1,0"])
        self.assertGreater(after["distribution"]["-1,0"],
                           static["distribution"]["-1,0"])
        # Other locations cannot inherit this intervention for free.
        independent = mem.predict([0, -2], "south", arm="two_clock")
        self.assertEqual(independent["basis"], "lifetime_local")
        self.assertIsNone(independent["active_local_marker"])
        self.assertEqual(len(mem.events), 8)

    def test_reverse_change_and_cold_reload_are_exact(self):
        mem = brain.TwoClockMemory()
        for index in range(1, 7):
            mem.observe(row(index, [0, -2], "south", [-1, -2]))
        mem.observe(row(7, [0, -2], "south", [0, -2]))
        mem.observe(row(8, [0, -2], "south", [0, -2]))
        self.assertEqual(len(mem.markers), 1)
        before = mem.predict([0, -2], "south", arm="two_clock")
        encoded = mem.dump()
        loaded = brain.TwoClockMemory.load(encoded)
        self.assertEqual(loaded.dump(), encoded)
        self.assertEqual(loaded.predict([0, -2], "south", arm="two_clock"), before)
        self.assertEqual(loaded.markers, mem.markers)

    def test_corruption_even_with_recomputed_outer_hash_is_rejected(self):
        mem = brain.TwoClockMemory()
        mem.observe(row(1, [0, 0], "east", [0, -1]))
        frozen = mem.dump()
        doc = json.loads(frozen)
        doc["body"]["events"][0]["delta"] = "0,0"
        doc["sha256"] = brain.sha(doc["body"])
        with self.assertRaisesRegex(ValueError, "contradicts"):
            brain.TwoClockMemory.load(brain.canonical(doc))
        doc = json.loads(frozen)
        doc["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "integrity"):
            brain.TwoClockMemory.load(brain.canonical(doc))

    def test_wrong_index_duplicate_and_unphysical_effect_rejected(self):
        mem = brain.TwoClockMemory()
        mem.observe(row(1, [0, 0], "north", [1, 0]))
        for bad in (
            row(1, [0, 0], "east", [0, -1]),
            row(3, [0, 0], "east", [0, -1]),
            dict(row(2, [0, 0], "east", [0, -1]), id="E000001"),
            row(2, [0, 0], "east", [2, 0]),
        ):
            with self.assertRaises(ValueError):
                mem.observe(bad)
        self.assertEqual(len(mem.events), 1)

    def test_distribution_is_calibratable_five_outcomes(self):
        p = brain.TwoClockMemory().predict([0, 0], "west", arm="two_clock")
        self.assertEqual(set(p["distribution"]), set(brain.DELTAS))
        self.assertAlmostEqual(sum(p["distribution"].values()), 1)
        truth = brain.scored(p, "0,1")
        self.assertGreater(truth["brier"], 0)
        self.assertGreater(truth["logloss"], 0)
        with self.assertRaises(ValueError):
            brain.scored(p, "2,0")


class FrozenWorldPanelTests(unittest.TestCase):
    def test_every_position_action_is_sampled_and_two_laws_differ_in_two(self):
        self.assertEqual(len(PANEL), 100)
        self.assertEqual(len({(tuple(p), a) for p, a in PANEL}), 100)
        self.assertEqual(_differential(), {(0, 2, "south"), (0, -2, "south")})
        self.assertEqual(len(SCENARIOS), 4)

    def test_independent_no_change_control_preserves_local_memory(self):
        report = _run_one("no_change", _differential())
        self.assertEqual(report["change_marker_count"], 0)
        self.assertEqual(report["evaluation_probes"], 400)
        self.assertEqual(report["metrics"]["TWOCLOCK-1"]["sensitive"]["count"], 8)
        self.assertEqual(report["metrics"]["TWOCLOCK-1"]["other"]["count"], 392)
        self.assertTrue(all(v == 1000 for v in report["memory_rows_retained"].values()))

    def test_single_fault_is_always_reported_and_not_promoted_to_physics(self):
        report = _run_one("single_faulty_sensor", _differential())
        self.assertEqual(report["actual_sensor_faults"], 1)
        faulty = [row for row in report["per_probe"] if row["injected_sensor_error"]]
        self.assertEqual(len(faulty), 1)
        self.assertNotEqual(faulty[0]["reported_delta"], faulty[0]["true_delta"])
        self.assertEqual(report["change_marker_count"], 0)
        self.assertEqual(len(report["per_probe"]), 400)

    def test_first_changed_world_forecast_cannot_know_switch_in_advance(self):
        baseline = _run_one("no_change", _differential())
        changed = _run_one("forward_change", _differential())
        # All training evidence is identical, so first prediction is identical.
        self.assertEqual(
            baseline["per_probe"][0]["predictions"],
            changed["per_probe"][0]["predictions"],
        )

    def test_all_four_scenarios_and_all_denominators_reproducible(self):
        one = run_study()
        two = run_study()
        self.assertEqual(one, two)
        self.assertEqual(set(one["scenarios"]), set(SCENARIOS))
        self.assertEqual(len(one["conditions"]), 6)
        self.assertIn(one["status"], {"mechanism_pass", "negative_or_mixed"})
        for name, report in one["scenarios"].items():
            self.assertEqual(report["training_probes"], 600)
            self.assertEqual(report["evaluation_probes"], 400)
            self.assertEqual(report["metrics"]["LIFETIME-1"]["late_sensitive"]["count"], 4)
            self.assertEqual(report["metrics"]["TWOCLOCK-1"]["all"]["count"], 400)
            self.assertEqual(len(report["per_probe"]), 400)
            self.assertGreater(len(report["sample_identity_sha256"]), 40)


if __name__ == "__main__":
    unittest.main()
