"""Independent invariants for the new default-off evidence-owned study."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from agenttest import causal_investigator as policy
import phase42_evidence_loop as loop
from open_object_world_challenge import observe_world, initial_world
from open_object_world_challenge_explorer import candidate_commands


class InvestigationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.public = {
            "position": [0, 0],
            "inventory_ids": [],
            "visible_entities": [],
        }
        self.menu = [{"action": name} for name in ("north", "east", "south", "west")]

    def test_policy_has_no_world_import_or_external_model(self):
        source = Path(policy.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from open_object_world_challenge", source)
        self.assertNotIn("from agenttest.world", source)
        self.assertNotIn("openai", source.lower())

    def test_public_projection_is_explicitly_allowlisted(self):
        extra = dict(self.public, secret_future_answer="west", cycle=100)
        self.assertEqual(policy.project_public(self.public), policy.project_public(extra))
        self.assertEqual(
            policy.select_investigation(self.public, [], self.menu),
            policy.select_investigation(extra, [], self.menu),
        )

    def test_menu_rejects_duplicate_and_unrecognized_commands(self):
        with self.assertRaises(ValueError):
            policy.select_investigation(self.public, [], self.menu + [self.menu[0]])
        with self.assertRaises(ValueError):
            policy.command_key({"action": "north", "hidden_target": "solution"})

    def test_duplicate_visible_identity_and_bad_probability_rejected(self):
        bogus = dict(self.public, visible_entities=[
            {"id": "x", "position": [0, 0]},
            {"id": "x", "position": [1, 0]},
        ])
        with self.assertRaises(ValueError):
            policy.project_public(bogus)
        with self.assertRaises(ValueError):
            policy.brier({o: 0.0 for o in policy.OUTCOMES}, "moved")

    def test_previous_observations_update_action_prediction(self):
        before = self.public
        after = dict(before, position=[1, 0])
        evidence = [
            {"id": f"INV{i:06d}", "public_before": before,
             "command": {"action": "north"}, "outcome_kind": "moved"}
            for i in (1, 2, 3)
        ]
        baseline = policy.forecast(before, {"action": "north"}, [])
        learned = policy.forecast(before, {"action": "north"}, evidence)
        self.assertGreater(learned["probabilities"]["moved"],
                           baseline["probabilities"]["moved"])
        self.assertEqual(learned["local_samples"], 3)
        self.assertEqual(len(learned["evidence_refs"]), 3)
        self.assertEqual(policy.classify_outcome(before, after, {"blocked": False}), "moved")

    def test_local_failure_overrides_pooled_action_success(self):
        origin = self.public
        other = dict(origin, position=[2, 0])
        evidence = [
            {"id": f"INV{i:06d}", "public_before": other,
             "command": {"action": "north"}, "outcome_kind": "moved"}
            for i in range(1, 5)
        ]
        pooled = policy.forecast(origin, {"action": "north"}, evidence)
        evidence.extend([
            {"id": f"INV{i:06d}", "public_before": origin,
             "command": {"action": "north"}, "outcome_kind": "blocked"}
            for i in range(5, 8)
        ])
        current = policy.forecast(origin, {"action": "north"}, evidence)
        self.assertGreater(current["probabilities"]["blocked"],
                           pooled["probabilities"]["blocked"])
        self.assertEqual(current["local_blocked"], 3)

    def test_selection_deterministic_no_mutation(self):
        observation = deepcopy(self.public)
        history = []
        menu = deepcopy(self.menu)
        first = policy.select_investigation(observation, history, menu)
        self.assertEqual(first, policy.select_investigation(observation, history, menu))
        self.assertEqual(observation, self.public)
        self.assertEqual(history, [])
        self.assertEqual(menu, self.menu)
        self.assertIn(first["command"], menu)
        self.assertEqual(first["owner_id"], "INV000001")
        self.assertEqual(first["history_length"], 0)

    def test_forecasts_are_proper_probabilities(self):
        for cmd in self.menu:
            expected = policy.forecast(self.public, cmd, [])
            self.assertAlmostEqual(sum(expected["probabilities"].values()), 1.0)
            self.assertEqual(set(expected["probabilities"]), set(policy.OUTCOMES))

    def test_report_names_weak_uniform_control(self):
        self.assertEqual(policy.summarize([])["events"], 0)
        self.assertIsNone(policy.summarize([])["mean_prequential_brier"])
        self.assertIn("not establish useful goal progress",
                      policy.summarize([])["interpretation"])


class DurableOwnedLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "investigation.json"

    def _new(self):
        return loop.create(self.path, seed=1)

    def _original(self):
        return self.path.read_bytes()

    def test_only_existing_public_world_and_actions_used(self):
        self._new()
        row = loop.step(self.path, request_id="t-1", expected_revision=0)
        self.assertEqual(row["status"], "committed")
        event = row["record"]
        self.assertEqual(event["id"], "INV000001")
        self.assertEqual(event["selection"]["command"], event["command"])
        self.assertEqual(event["selection"]["history_length"], 0)
        self.assertIn(event["command"],
                      candidate_commands(observe_world(initial_world(1))))
        self.assertEqual(event["outcome_kind"], policy.classify_outcome(
            event["public_before"], event["public_after"], event["receipt"],
        ))
        self.assertEqual(loop.inspect(self.path)["revision"], 1)

    def test_restart_uses_memory_and_committed_history(self):
        self._new()
        first = loop.step(self.path, request_id="req-1", expected_revision=0)
        second = loop.step(self.path, request_id="req-2", expected_revision=1)
        self.assertEqual(first["record"]["id"], "INV000001")
        self.assertEqual(second["record"]["id"], "INV000002")
        # Cold read audits every stored selection, world transition and receipt.
        view = loop.inspect(self.path)
        self.assertEqual(view["summary"]["events"], 2)
        self.assertEqual(view["revision"], 2)

    def test_idempotent_replay_without_second_action(self):
        self._new()
        first = loop.step(self.path, request_id="same", expected_revision=0)
        original = self._original()
        retry = loop.step(self.path, request_id="same", expected_revision=0)
        self.assertEqual(retry["status"], "already_committed")
        self.assertEqual(first["record"], retry["record"])
        self.assertEqual(self._original(), original)
        self.assertEqual(loop.inspect(self.path)["revision"], 1)

    def test_stale_new_request_does_not_mutate(self):
        self._new()
        loop.step(self.path, request_id="one", expected_revision=0)
        before = self._original()
        with self.assertRaisesRegex(ValueError, "stale attempt"):
            loop.step(self.path, request_id="two", expected_revision=0)
        self.assertEqual(self._original(), before)

    def test_corruption_rejected_even_if_outer_checksum_recomputed(self):
        self._new()
        loop.step(self.path, request_id="one", expected_revision=0)
        original = json.loads(self._original())
        forged = deepcopy(original)
        forged["events"][0]["command"] = {"action": "west"}
        forged["digest"] = loop._sha({k: v for k, v in forged.items() if k != "digest"})
        self.path.write_bytes(loop._bytes(forged))
        with self.assertRaisesRegex(ValueError, "non-owned action"):
            loop.inspect(self.path)

    def test_world_forgery_rejected_on_replay(self):
        self._new()
        loop.step(self.path, request_id="one", expected_revision=0)
        forged = json.loads(self._original())
        forged["world"]["position"] = [2, 2]
        forged["digest"] = loop._sha({k: v for k, v in forged.items() if k != "digest"})
        self.path.write_bytes(loop._bytes(forged))
        with self.assertRaisesRegex(ValueError, "world replay"):
            loop.inspect(self.path)

    def test_source_change_rejected_without_any_action(self):
        self._new()
        original = json.loads(self._original())
        original["source_hashes"]["policy"] = "0" * 64
        original["digest"] = loop._sha({k: v for k, v in original.items() if k != "digest"})
        self.path.write_bytes(loop._bytes(original))
        prior = self._original()
        with self.assertRaisesRegex(ValueError, "source changed"):
            loop.step(self.path, request_id="next", expected_revision=0)
        self.assertEqual(self._original(), prior)

    def test_no_overwrite_ever_and_reject_live_state_path(self):
        self._new()
        before = self._original()
        with self.assertRaises(FileExistsError):
            self._new()
        self.assertEqual(self._original(), before)
        with self.assertRaisesRegex(ValueError, "immutable"):
            loop._path(loop.ORIGINAL_STATE / "organism.json")

    def test_existing_lock_fails_closed(self):
        self._new()
        lock = self.path.with_suffix(".lock")
        lock.write_text("simulated unfinished writer")
        original = self._original()
        with self.assertRaisesRegex(RuntimeError, "already has an owner"):
            loop.step(self.path, request_id="blocked", expected_revision=0)
        self.assertEqual(self._original(), original)
        self.assertTrue(lock.exists())

    def test_two_step_four_layout_exploratory_study(self):
        result = loop.study(2)
        self.assertEqual(result["worlds"], 4)
        self.assertEqual(result["actions_per_world"], 2)
        self.assertEqual(len(result["rows"]), 4)
        self.assertTrue(all(x["events"] == 2 for x in result["rows"]))
        self.assertIn("not_preregistered", result["status"])
        self.assertIn("not independent", " ".join(result["limitations"]))


if __name__ == "__main__":
    unittest.main()
