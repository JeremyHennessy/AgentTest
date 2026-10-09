"""Original Ora full-ancestry prospective shadow: zero writes, no hindsight."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from agenttest.action_lab import apply_bounded_action, STATEFUL_WORLD_VERSION, TRANSFER_WORLD_VERSION
from agenttest.state import initial_state
from agenttest.two_clock_memory import TwoClockMemory as OriginalTwoClock
from agenttest.two_clock_stream import (
    TwoClockStream, VERSION, MAX_EVENTS, brier, digest, _json,
)
from phase42_original_shadow import inspect
from phase42_transition_memory_study import extract_verified_native


def public_row(i, before, action, after):
    return {
        "id": f"OA{i:07d}", "index": i, "before": list(before),
        "after": list(after), "action": action,
    }


def fixtures(count=90, *, original=STATEFUL_WORLD_VERSION):
    state = initial_state()
    state["cycles"] = count + 10
    lab = state["planning_lab"]
    lab["world_version"] = STATEFUL_WORLD_VERSION
    lab["bounds"] = 2
    lab["transition_observations"] = []
    position = [0, 0]
    actions = ("north", "east", "south", "west")
    for index in range(1, count + 1):
        action = actions[(index + position[0] + 2 * position[1]) % 4]
        outcome = apply_bounded_action(
            position, action, bounds=2, world_version=original
        )
        lab["transition_observations"].append({
            "source": "planning_lab",
            "source_id": f"OA{index:07d}", "cycle": index,
            "world_version": STATEFUL_WORLD_VERSION,
            "action": action, "before": list(position),
            "after": list(outcome["after"]), "delta": list(outcome["delta"]),
            "blocked": outcome["blocked"],
        })
        position = list(outcome["after"])
    lab["position"] = list(position)
    lab["last_action_cycle"] = count
    return state


def pinned(state, commit="1" * 40, previous=None):
    raw = _json(state)
    blob = hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\x00" + raw
    ).hexdigest()
    sha = hashlib.sha256(raw).hexdigest()
    return inspect(
        raw, original_commit=commit, original_blob=blob,
        expected_sha256=sha, previous_report=previous,
    )


def next_native(state, before=None, action="north", *,
                world=STATEFUL_WORLD_VERSION):
    lab = state["planning_lab"]
    position = list(before if before is not None else lab["position"])
    outcome = apply_bounded_action(
        position, action, world_version=world, bounds=2,
    )
    number = len(lab["transition_observations"]) + 1
    lab["transition_observations"].append({
        "source": "planning_lab",
        "source_id": f"OA{number:07d}", "cycle": state["cycles"] + 1,
        "world_version": world, "action": action,
        "before": list(position), "after": list(outcome["after"]),
        "delta": list(outcome["delta"]), "blocked": outcome["blocked"],
    })
    lab["position"] = list(outcome["after"])
    state["cycles"] += 1
    lab["last_action_cycle"] = state["cycles"]
    return outcome


class FullHistoryTests(unittest.TestCase):
    def test_pure_model_does_not_import_hidden_physics_or_decision_policy(self):
        file = Path(sys.modules[TwoClockStream.__module__].__file__).read_text()
        for bad in (
            "from .action_lab", "apply_bounded_action",
            "_HIDDEN_ACTION_DELTAS", "TRANSFER_WORLD_VERSION",
            "from .planning_lab", "openai",
        ):
            self.assertNotIn(bad, file.lower() if bad == "openai" else file)

    def test_exact_original_v1_parity_before_and_after_first_switch(self):
        v1, v2 = OriginalTwoClock(), TwoClockStream()
        data = []
        for index in range(1, 25):
            before = [0, 2]
            after = [0, 2] if index <= 6 else [-1, 2]
            event = public_row(index, before, "south", after)
            data.append(event)
            v1.observe(event)
            v2.observe(event)
            for arm in ("lifetime", "two_clock", "action", "uniform"):
                self.assertEqual(
                    v1.predict(before, "south", arm=arm)["distribution"],
                    v2.predict(before, "south", arm=arm)["distribution"],
                )

    def test_two_local_reversals_without_ever_deleting_old_memory(self):
        model = TwoClockStream()
        directions = (["0,0"] * 6 + ["-1,0"] * 6 + ["0,0"] * 2)
        for i, effect in enumerate(directions, 1):
            after = [0, 2] if effect == "0,0" else [-1, 2]
            model.observe(public_row(i, [0, 2], "south", after))
        ctxt = "0,2|south"
        self.assertEqual(len(model.markers[ctxt]), 2)
        self.assertEqual([m["start_index"] for m in model.markers[ctxt]], [7, 13])
        self.assertEqual([m["evidence_ids"] for m in model.markers[ctxt]], [
            ["OA0000007", "OA0000008"],
            ["OA0000013", "OA0000014"],
        ])
        self.assertEqual(len(model.events), 14)
        self.assertEqual(model.events[0]["delta"], "0,0")
        forecast = model.predict([0, 2], "south", arm="two_clock")
        self.assertEqual(forecast["change_marker_count"], 2)
        self.assertEqual(forecast["active_rows"], 2)
        self.assertGreater(forecast["distribution"]["0,0"],
                           forecast["distribution"]["-1,0"])
        self.assertEqual(
            model.predict([0, -2], "south", arm="two_clock")["basis"],
            "full_lifetime_local",
        )

    def test_one_single_contradiction_does_not_revise_context(self):
        model = TwoClockStream()
        for i in range(1, 7):
            model.observe(public_row(i, [0, 2], "south", [0, 2]))
        model.observe(public_row(7, [0, 2], "south", [-1, 2]))
        self.assertFalse(model.markers)
        self.assertEqual(model.predict([0, 2], "south", arm="two_clock")["basis"],
                         "full_lifetime_local")

    def test_eight_thousand_full_source_rows_and_cold_restore(self):
        memory = TwoClockStream()
        for i in range(1, 8201):
            memory.observe(public_row(i, [0, 2], "south", [0, 2]))
        self.assertEqual(len(memory.events), 8200)
        self.assertEqual(len(memory.known), 8200)
        self.assertEqual(memory.events[0]["id"], "OA0000001")
        self.assertEqual(memory.events[-1]["id"], "OA0008200")
        before = memory.predict([0, 2], "south", arm="two_clock")
        encoded = memory.capsule()
        self.assertLess(len(encoded), 16 * 1024 * 1024)
        restored = TwoClockStream.from_capsule(encoded)
        self.assertEqual(restored.predict([0, 2], "south", arm="two_clock"), before)
        self.assertEqual(restored.capsule(), encoded)
        self.assertEqual(len(restored.events), 8200)
        self.assertEqual(restored.markers, memory.markers)

    def test_bound_rejects_next_row_without_truncation(self):
        with patch("agenttest.two_clock_stream.MAX_EVENTS", 2):
            memory = TwoClockStream()
            for i in (1, 2):
                memory.observe(public_row(i, [0, 0], "north", [1, 0]))
            with self.assertRaisesRegex(ValueError, "capacity"):
                memory.observe(public_row(3, [0, 0], "north", [1, 0]))
            self.assertEqual(len(memory.events), 2)

    def test_replay_skip_corrupt_and_foreign_grammar_rejected(self):
        memory = TwoClockStream()
        memory.observe(public_row(1, [0, 0], "north", [1, 0]))
        for invalid in (
            public_row(2, [0, 0], "north", [2, 0]),
            public_row(1, [0, 0], "north", [1, 0]),
            public_row(3, [0, 0], "north", [1, 0]),
            dict(public_row(2, [0, 0], "north", [1, 0]), id="OA0000001"),
            dict(public_row(2, [0, 0], "north", [1, 0]), delta="0,0"),
        ):
            with self.assertRaises(ValueError):
                memory.observe(invalid)
        self.assertEqual(len(memory.events), 1)
        serialized = json.loads(memory.capsule())
        serialized["body"]["events"][0]["delta"] = "0,0"
        serialized["sha256"] = digest(serialized["body"])
        with self.assertRaisesRegex(ValueError, "contradicts"):
            TwoClockStream.from_capsule(_json(serialized))
        serialized["body"]["events"][0]["delta"] = "1,0"
        with self.assertRaisesRegex(ValueError, "envelope"):
            TwoClockStream.from_capsule(_json(serialized))


class AuthenticSourceShadowTests(unittest.TestCase):
    def test_frozen_forecasts_from_real_native_shape_and_no_prior(self):
        state = fixtures()
        before = deepcopy(state)
        result = pinned(state)
        self.assertEqual(state, before)
        self.assertEqual(result["prospective"]["status"], "no_previous_receipt")
        self.assertFalse(result["prospective"]["credit"])
        frozen = result["frozen"]["body"]
        self.assertFalse(frozen["study_owns_action"])
        self.assertEqual(frozen["compatible_native_rows"], 90)
        self.assertEqual(frozen["total_native_rows"], 90)
        self.assertEqual(set(frozen["forecasts"]), {"north", "east", "south", "west"})
        for alternatives in frozen["forecasts"].values():
            self.assertEqual(set(alternatives), {"two_clock", "lifetime", "action", "uniform"})
            for forecast in alternatives.values():
                self.assertEqual(forecast["lifetime_rows"], 90)
        self.assertTrue(result["source_not_modified"])
        self.assertEqual(len(result["report_sha256"]), 64)

    def test_next_genuine_natural_first_action_scores_only_future(self):
        state = fixtures()
        initial = pinned(state)
        direction = "east"
        original_effect = next_native(state, action=direction)
        subsequent = next_native(state, action="north")
        scored = pinned(state, commit="2" * 40, previous=initial)
        self.assertEqual(scored["prospective"]["status"],
                         "scored_one_natural_first_action")
        self.assertTrue(scored["prospective"]["credit"])
        self.assertEqual(scored["prospective"]["naturally_chosen_action"], "east")
        self.assertEqual(scored["prospective"]["later_natural_events_not_scored"], 1)
        self.assertEqual(scored["prospective"]["native_source_id"], "OA0000091")
        self.assertEqual(scored["summary"]["scored_natural_first_actions"], 1)
        self.assertEqual(scored["frozen"]["body"]["compatible_native_rows"], 92)
        outcome = original_effect["delta"]
        expected_delta = f"{outcome[0]},{outcome[1]}"
        self.assertEqual(scored["prospective"]["actual_public_delta"], expected_delta)
        expected_forecast = initial["frozen"]["body"]["forecasts"]["east"]["two_clock"]
        self.assertEqual(
            scored["prospective"]["preaction_scores"]["two_clock"]["brier"],
            brier(expected_forecast, expected_delta)["brier"],
        )
        self.assertEqual(state["planning_lab"]["position"], subsequent["after"])

    def test_no_native_event_never_creates_a_score(self):
        state = fixtures()
        previous = pinned(state)
        state["cycles"] += 1
        result = pinned(state, commit="2" * 40, previous=previous)
        self.assertEqual(result["prospective"]["status"], "no_new_native_event")
        self.assertEqual(result["summary"]["scored_natural_first_actions"], 0)
        self.assertEqual(result["summary"]["inconclusive_intervals"], 2)

    def test_identical_pinned_snapshot_never_counts_as_second_prospective(self):
        state = fixtures()
        initial = pinned(state)
        same = pinned(state, previous=initial)
        self.assertEqual(same["prospective"]["status"], "identical_snapshot")
        self.assertFalse(same["prospective"]["credit"])

    def test_no_convenient_later_match_if_first_action_wrong_position(self):
        state = fixtures()
        previous = pinned(state)
        old_position = list(state["planning_lab"]["position"])
        other = [2, 2] if old_position != [2, 2] else [-2, -2]
        next_native(state, before=other, action="north")
        next_native(state, before=old_position, action="west")
        result = pinned(state, commit="2" * 40, previous=previous)
        self.assertEqual(result["prospective"]["status"], "unexpected_first_context")
        self.assertFalse(result["prospective"]["credit"])
        self.assertEqual(result["summary"]["scored_natural_first_actions"], 0)

    def test_foreign_world_first_does_not_get_credited(self):
        state = fixtures()
        previous = pinned(state)
        next_native(state, action="west", world=TRANSFER_WORLD_VERSION)
        result = pinned(state, commit="2" * 40, previous=previous)
        self.assertEqual(result["prospective"]["status"], "other_world_first")
        self.assertEqual(result["frozen"]["body"]["compatible_native_rows"], 90)
        self.assertEqual(result["frozen"]["body"]["total_native_rows"], 91)

    def test_rewritten_prefix_fails_even_if_every_physical_move_is_valid(self):
        state = fixtures()
        previous = pinned(state)
        state["planning_lab"]["transition_observations"][0]["source_id"] = "OTHER-1"
        next_native(state)
        with self.assertRaisesRegex(ValueError, "changed old native"):
            pinned(state, commit="2" * 40, previous=previous)

    def test_fake_prior_probabilities_and_modified_cumulative_score_rejected(self):
        state = fixtures()
        previous = pinned(state)
        next_native(state)
        forged = deepcopy(previous)
        forged["frozen"]["body"]["forecasts"]["east"]["two_clock"]["distribution"]["0,0"] = 0.99
        with self.assertRaisesRegex(ValueError, "report hash"):
            pinned(state, commit="2" * 40, previous=forged)
        forged = deepcopy(previous)
        forged["summary"]["scored_natural_first_actions"] = 1000
        with self.assertRaisesRegex(ValueError, "report hash"):
            pinned(state, commit="2" * 40, previous=forged)

    def test_different_source_world_and_origin_bytes_fail_closed(self):
        state = fixtures()
        source = pinned(state)
        state["planning_lab"]["world_version"] = TRANSFER_WORLD_VERSION
        with self.assertRaisesRegex(ValueError, "not the authorized"):
            pinned(state, commit="2" * 40, previous=source)
        state = fixtures()
        raw = _json(state)
        with self.assertRaisesRegex(ValueError, "provenance"):
            inspect(raw, original_commit="1" * 40, original_blob="0" * 40,
                    expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_previous_source_has_to_be_same_known_schema(self):
        state = fixtures()
        previous = pinned(state)
        next_native(state)
        forged = deepcopy(previous)
        forged["frozen"]["body"]["world_version"] = TRANSFER_WORLD_VERSION
        forged["frozen"]["sha256"] = digest(forged["frozen"]["body"])
        forged["report_sha256"] = digest({k: v for k, v in forged.items()
                                         if k != "report_sha256"})
        with self.assertRaisesRegex(ValueError, "old observation|invalid old"):
            pinned(state, commit="2" * 40, previous=forged)


if __name__ == "__main__":
    unittest.main()
