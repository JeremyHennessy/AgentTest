"""Independent tests: predictive memory, actual ancestry, cold restart and no oracle."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from agenttest import transition_memory as memory
from agenttest.action_lab import apply_bounded_action, STATEFUL_WORLD_VERSION, TRANSFER_WORLD_VERSION
from agenttest.state import initial_state
from phase42_transition_memory_study import extract_verified_native, inspect_original_bytes


def example(identifier: str, index: int, before: list[int], action: str,
            after: list[int]) -> dict:
    return {
        "id": identifier, "index": index,
        "before": list(before), "action": action, "after": list(after),
        "world_version": memory.WORLD,
    }


def trace(count=100, world=STATEFUL_WORLD_VERSION):
    rows = []
    position = [0, 0]
    for index in range(1, count + 1):
        action = memory.ACTIONS[(index * 3 + position[0] + 2 * position[1]) % 4]
        observed = apply_bounded_action(position, action, world_version=world)
        rows.append(example(
            f"PX{index:06d}", index, position, action, observed["after"],
        ))
        position = observed["after"]
    return rows


class TransitionMemoryTests(unittest.TestCase):
    def test_predictor_has_no_hidden_action_table_or_planner(self):
        code = Path(memory.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from .action_lab", code)
        self.assertNotIn("apply_bounded_action", code)
        self.assertNotIn("_HIDDEN_ACTION", code)
        self.assertNotIn("openai", code.lower())
        self.assertNotIn("planning_lab", code)

    def test_five_class_forecast_not_just_moved_boolean(self):
        m = memory.TransitionMemory()
        start = m.forecast([0, 0], "north")
        self.assertEqual(set(start["distribution"]), set(memory.DELTAS))
        self.assertAlmostEqual(start["distribution"]["1,0"], 0.2)
        positions = [[-2, 0], [-1, 0], [0, 0], [1, 0]]
        for i, before in enumerate(positions, 1):
            m.add(example(f"E{i}", i, before, "north", [before[0] + 1, 0]))
        learned = m.forecast([-1, 1], "north")
        self.assertGreater(learned["distribution"]["1,0"], 0.68)
        self.assertEqual(learned["family_count"], 4)
        self.assertEqual(learned["local_count"], 0)
        self.assertNotEqual(learned["predicted_delta"], "0,0")
        self.assertAlmostEqual(sum(learned["distribution"].values()), 1.0)

    def test_state_specific_exception_is_distinct_from_family(self):
        m = memory.TransitionMemory()
        for i, before in enumerate(([1, 0], [2, 0], [0, -1], [-1, 1]), 1):
            after = apply_bounded_action(before, "south", world_version=STATEFUL_WORLD_VERSION)
            m.add(example(f"M{i}", i, before, "south", after["after"]))
        for i in range(5, 9):
            m.add(example(f"M{i}", i, [0, 2], "south", [0, 2]))
        family = m.forecast([0, 2], "south", arm="family")
        local = m.forecast([0, 2], "south", arm="hier")
        self.assertEqual(local["local_count"], 4)
        self.assertGreater(local["distribution"]["0,0"], family["distribution"]["0,0"])
        self.assertGreater(local["distribution"]["0,0"], local["distribution"]["-1,0"])

    def test_correction_of_contradiction_keeps_history(self):
        m = memory.TransitionMemory()
        for i in range(1, 4):
            m.add(example(f"E{i}", i, [0, 2], "south", [-1, 2]))
        prior = m.forecast([0, 2], "south")["distribution"]["0,0"]
        for i in range(4, 8):
            m.add(example(f"E{i}", i, [0, 2], "south", [0, 2]))
        after = m.forecast([0, 2], "south")["distribution"]["0,0"]
        self.assertGreater(after, prior)
        self.assertEqual(m.length, 7)
        self.assertEqual(m.rows[0]["delta"], "-1,0")

    def test_cold_restart_preserves_model_exactly(self):
        m = memory.TransitionMemory(trace(40))
        frozen = m.forecast([1, 0], "north")
        encoded = m.export()
        reloaded = memory.TransitionMemory.restore(encoded)
        self.assertEqual(reloaded.export(), encoded)
        self.assertEqual(reloaded.forecast([1, 0], "north"), frozen)
        self.assertEqual(reloaded.length, m.length)

    def test_corrupted_and_forged_capsule_rejected(self):
        m = memory.TransitionMemory(trace(3))
        encoded = m.export()
        modified = json.loads(encoded)
        modified["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            memory.TransitionMemory.restore(memory._json(modified))
        modified = json.loads(encoded)
        modified["body"]["rows"][0]["delta"] = "0,0" if (
            modified["body"]["rows"][0]["delta"] != "0,0"
        ) else "1,0"
        modified["sha256"] = memory.digest(modified["body"])
        with self.assertRaisesRegex(ValueError, "contradicts"):
            memory.TransitionMemory.restore(memory._json(modified))

    def test_duplicate_skip_or_wrong_world_rejected(self):
        m = memory.TransitionMemory()
        m.add(example("E1", 1, [0, 0], "north", [1, 0]))
        for invalid in (
            example("E1", 2, [1, 0], "south", [0, 0]),
            example("E2", 4, [1, 0], "south", [0, 0]),
            dict(example("E2", 2, [1, 0], "south", [0, 0]),
                 world_version=TRANSFER_WORLD_VERSION),
        ):
            with self.assertRaises(ValueError):
                m.add(invalid)
        self.assertEqual(m.length, 1)

    def test_nonadjacent_and_offgrid_outcomes_rejected(self):
        for row in (
            example("x", 1, [0, 0], "north", [2, 0]),
            example("x", 1, [2, 2], "north", [3, 2]),
            example("x", 1, [0, 0], "north", [0, -2]),
        ):
            with self.assertRaises(ValueError):
                memory.normalize(row)

    def test_scores_are_proper_and_none_prove_task_utility(self):
        m = memory.TransitionMemory()
        p = m.forecast([0, 0], "east")
        sc = memory.score(p, "0,-1")
        self.assertGreater(sc["brier"], 0)
        self.assertGreater(sc["logloss"], 0)
        self.assertFalse(sc["hit"] if p["predicted_delta"] != "0,-1" else False)
        with self.assertRaises(ValueError):
            memory.score({"distribution": {"1,0": 1.0}, "predicted_delta": "1,0"}, "1,0")

    def test_chronological_heldout_and_negative_controls_reproducible(self):
        rows = trace(100)
        first = memory.evaluate_history(rows)
        second = memory.evaluate_history(deepcopy(rows))
        self.assertEqual(first, second)
        self.assertEqual(first["evaluation_rows"], 24)
        self.assertEqual(first["training_rows"], 76)
        self.assertEqual(len(first["per_action"]), 24)
        self.assertEqual(set(first["metrics"]), {
            "HIER-1", "FAM-1", "FROZEN-1",
            "GLOBAL-1", "UNIFORM-1", "SHUFFLED-1",
        })
        self.assertEqual(first["metrics"]["HIER-1"]["evaluated"], 24)
        self.assertIn(first["status"], {"candidate_improves_over_family", "candidate_no_gain"})

    def test_first_heldout_prediction_does_not_see_later_outcome(self):
        rows = trace(100)
        original = memory.evaluate_history(rows)
        changed = deepcopy(rows)
        before = changed[-1]["before"]
        changed[-1]["after"] = list(before)  # a different (but supported) observed effect
        altered = memory.evaluate_history(changed)
        self.assertEqual(
            original["per_action"][0]["frozen_predictions"],
            altered["per_action"][0]["frozen_predictions"],
        )
        self.assertEqual(
            original["per_action"][0]["observed_delta"],
            altered["per_action"][0]["observed_delta"],
        )

    def test_inadequate_history_is_not_automatically_upgraded(self):
        value = memory.evaluate_history(trace(50))
        self.assertEqual(value["status"], "INSUFFICIENT")
        self.assertEqual(value["eligible_rows"], 50)


class AuthenticAdapterTests(unittest.TestCase):
    def setUp(self):
        self.state = initial_state()
        self.state["cycles"] = 101
        self.state["planning_lab"]["world_version"] = STATEFUL_WORLD_VERSION
        self.state["planning_lab"]["transition_observations"] = []
        for event in trace(90):
            action = event["action"]
            before = event["before"]
            outcome = apply_bounded_action(
                before, action, world_version=STATEFUL_WORLD_VERSION,
            )
            self.state["planning_lab"]["transition_observations"].append({
                "source": "planning_lab",
                "source_id": event["id"],
                "world_version": STATEFUL_WORLD_VERSION,
                "action": action,
                "before": list(before),
                "after": list(outcome["after"]),
                "delta": list(outcome["delta"]),
                "blocked": outcome["blocked"],
            })

    def test_adapter_replays_every_native_row_and_separates_other_world(self):
        foreign = deepcopy(self.state["planning_lab"]["transition_observations"][0])
        foreign["world_version"] = TRANSFER_WORLD_VERSION
        self.state["planning_lab"]["transition_observations"].append(foreign)
        data = extract_verified_native(self.state)
        self.assertEqual(data["compatible_count"], 90)
        self.assertEqual(data["incompatible_world_count"], 1)
        self.assertEqual(data["rows"][0]["index"], 1)
        self.assertEqual(data["rows"][-1]["index"], 90)
        self.assertEqual(len(data["complete_eligible_history_sha256"]), 64)

    def test_mismatched_native_physics_fails_closed(self):
        self.state["planning_lab"]["transition_observations"][0]["after"] = [2, 2]
        with self.assertRaises(ValueError):
            extract_verified_native(self.state)

    def test_duplicate_identity_and_stored_delta_forgery_fail_closed(self):
        self.state["planning_lab"]["transition_observations"][1]["source_id"] = "PX000001"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            extract_verified_native(self.state)
        self.state["planning_lab"]["transition_observations"][1]["source_id"] = "PX000002"
        self.state["planning_lab"]["transition_observations"][1]["delta"] = [0, 0] if (
            self.state["planning_lab"]["transition_observations"][1]["delta"] != [0, 0]
        ) else [1, 0]
        with self.assertRaisesRegex(ValueError, "stored delta"):
            extract_verified_native(self.state)

    def test_original_source_blob_sha_and_state_unchanged(self):
        raw = memory._json(self.state)
        commit = "1" * 40
        blob = hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\x00" + raw,
        ).hexdigest()
        sha = hashlib.sha256(raw).hexdigest()
        report = inspect_original_bytes(
            raw, original_commit=commit, original_blob=blob, sha256=sha,
        )
        self.assertEqual(report["admission"]["compatible_count"], 90)
        self.assertEqual(report["evaluation"]["evaluation_rows"], 24)
        self.assertEqual(report["source"]["original_cycle"], 101)
        self.assertFalse(report["original_ora_activation"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), sha)
        with self.assertRaisesRegex(ValueError, "digests"):
            inspect_original_bytes(
                raw, original_commit=commit, original_blob="0" * 40, sha256=sha,
            )


if __name__ == "__main__":
    unittest.main()
