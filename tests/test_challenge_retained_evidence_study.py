from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from challenge_eight_action_closed_loop import _agenda_identity, _stream_prefix
from challenge_retained_evidence_study import (
    EXPECTED_RUNTIME_HASH, SETTINGS, assert_outcome_only_delta, choice_key,
    digest, file_digest, fixed_clock, fixed_time, matched_attempt_key,
    native_outcome_pair, objective_key, repeat_measures, runtime_manifest,
    selector_pair,
)
from challenge_shadow_epistemic_selector import select_epistemic_command
from challenge_shadow_recorder import ChallengeShadowRecorder, single_transition_outcome, source_manifest
from native_observe_inquire_integration import observe_and_inquire_policy, stage_publication_inquiry
from open_object_world_challenge import initial_world, observe_world, transition


class RetainedEvidenceStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.observation = observe_world(initial_world(1))
        self.candidate = {"feature": "position", "relation": "same_next_observation"}
        self.associations = [
            self.association("position", "north", 5, 0),
            self.association("position", "east", 4, 4),
            self.association("inventory_ids", "north", 9, 0),
        ]

    @staticmethod
    def association(feature, action, count, changed):
        return {"id": feature + action, "relation": "action_associated_with_change",
                "feature": feature, "action": action,
                "action_present": {"evaluable": count, "changed": changed, "same": count - changed}}

    def test_frozen_runtime_provenance(self):
        self.assertEqual(digest(runtime_manifest()), EXPECTED_RUNTIME_HASH)
        self.assertEqual(SETTINGS["seeds"], [1, 2, 3, 4])
        self.assertEqual(SETTINGS["native_probe_steps"], [1, 8])

    def test_only_selected_feature_associations_are_ablated(self):
        prior = deepcopy([self.observation, self.candidate, self.associations])
        result = selector_pair(self.observation, self.candidate, self.associations, self.root)
        intact = json.loads((self.root / "retained.json").read_text())
        ablated = json.loads((self.root / "ablated.json").read_text())
        self.assertEqual(ablated["associations"], [self.associations[-1]])
        self.assertEqual(result["removed_association_count"], 2)
        self.assertEqual([self.observation, self.candidate, self.associations], prior)
        for field in ("observation", "feature", "relation"):
            self.assertEqual(intact[field], ablated[field])
        self.assertEqual(result["retained"], select_epistemic_command(**intact))
        self.assertEqual(result["ablated"], select_epistemic_command(**ablated))
        self.assertTrue(result["command_changed"])

    def test_null_ablation_is_valid_and_not_counted_as_change(self):
        result = selector_pair(self.observation, self.candidate, [], self.root)
        self.assertFalse(result["command_changed"])
        self.assertEqual(result["removed_association_count"], 0)
        self.assertEqual(result["retained_context_sha256"], result["ablated_context_sha256"])

    def test_unrelated_evidence_does_not_change_this_contrast(self):
        one = selector_pair(self.observation, self.candidate, self.associations, self.root / "one")
        alternate = deepcopy(self.associations)
        alternate[-1]["action_present"]["changed"] = 3
        two = selector_pair(self.observation, self.candidate, alternate, self.root / "two")
        for arm in ("retained", "ablated"):
            self.assertEqual(one[arm], two[arm])
        self.assertNotEqual(one["unrelated_associations_sha256"], two["unrelated_associations_sha256"])

    def history(self, outcome="supported", mode="seek_disconfirming_observation", probability=.75):
        selected = {"command": {"action": "north"}, "mode": mode, "falsification_probability": probability}
        return [{"step": 1, "objective_key": objective_key(self.candidate),
                 "attempt_key": matched_attempt_key(self.observation, self.candidate, selected["command"]),
                 "selection": selected, "outcome": outcome}]

    def test_effect_repeat_requires_same_context_and_disconfirmed_expectation(self):
        history = self.history()
        selected = history[0]["selection"]
        result = repeat_measures(history, self.observation, self.candidate, selected)
        self.assertTrue(result["same_context_disconfirmed_expected_effect_repeated"])
        changed_observation = deepcopy(self.observation)
        changed_observation["position"] = [1, 0]
        self.assertFalse(repeat_measures(history, changed_observation, self.candidate, selected)[
            "same_context_disconfirmed_expected_effect_repeated"])
        history = self.history(mode="reduce_action_uncertainty")
        result = repeat_measures(history, self.observation, self.candidate, selected)
        self.assertTrue(result["same_context_unsuccessful_counterexample_attempt_repeated"])
        self.assertFalse(result["same_context_disconfirmed_expected_effect_repeated"])

    def test_successful_falsification_is_not_a_disproven_action(self):
        history = self.history(outcome="falsified")
        result = repeat_measures(history, self.observation, self.candidate, history[0]["selection"])
        self.assertTrue(result["objective_previously_refuted"])
        self.assertFalse(result["same_context_disconfirmed_expected_effect_repeated"])
        self.assertFalse(result["same_context_unsuccessful_counterexample_attempt_repeated"])

    def test_chance_expectation_is_not_disconfirmed_effect(self):
        history = self.history(probability=.5)
        result = repeat_measures(history, self.observation, self.candidate, history[0]["selection"])
        self.assertFalse(result["same_context_disconfirmed_expected_effect_repeated"])

    def test_choice_endpoint_ignores_incidental_identity(self):
        first = {"question_text": "same inquiry", "intention_kind": "explore", "intention_target": None,
                 "question_id": "Q1"}
        second = dict(first, question_id="Q2")
        self.assertEqual(choice_key(first), choice_key(second))
        second["question_text"] = "other inquiry"
        self.assertNotEqual(choice_key(first), choice_key(second))

    def test_outcome_delta_rejects_unrelated_history_edit(self):
        before = {"episodes": [], "experiments": [], "reflections": [], "questions": ["keep"]}
        after = deepcopy(before)
        after["questions"] = []
        with self.assertRaisesRegex(AssertionError, "unrelated root"):
            assert_outcome_only_delta(before, after, "X1", {})

    def test_native_outcome_pair_has_valid_unmodified_withheld_branch(self):
        ora = StateStore(self.root / "source" / "ora.json")
        repo_observation = {"branch": "test", "baseline_fingerprint": "stable",
                            "tracked_files": 10, "python_files": 2, "python_source_lines": 100,
                            "test_files": 1, "working_tree_clean": True}
        with fixed_clock(fixed_time(1, 0)):
            ora.save(initial_state())
            AgentCore(ora).cycle(observation=repo_observation, _now_override=fixed_time(1, 0))
            recorder_store = StateStore(self.root / "recorder" / "recorder.json")
            recorder_store.save(initial_state())
            world, _ = _stream_prefix(recorder_store, 1)
            recorder = ChallengeShadowRecorder(recorder_store, enabled=True)
            publication = recorder.publication()
            staged = stage_publication_inquiry(
                AgentCore(ora), policy=observe_and_inquire_policy(),
                source_manifest=source_manifest(), publication=publication,
            )
        candidate = publication["selected_temporal_candidate"]
        selected = select_epistemic_command(recorder.latest_observation(), feature=candidate["feature"],
                                            relation=candidate["relation"], associations=recorder.action_associations())
        advanced, _ = transition(world, selected["command"], cycle=601)
        payload = single_transition_outcome(before=observe_world(world), after=observe_world(advanced), candidate=candidate)
        self.assertIsNotNone(payload)
        source_hash = file_digest(ora.path)
        experiment_id = staged["inquiry_result"]["experiment"]["id"]
        question_id = staged["inquiry_result"]["question"]["id"]
        pair = native_outcome_pair(ora.path, experiment_id, question_id, payload, repo_observation,
                                   self.root / "forks", fixed_time(1, 1), _agenda_identity(ora.load()))
        self.assertEqual(file_digest(ora.path), source_hash)
        self.assertTrue(pair["pre_intervention_forks_byte_identical"])
        self.assertTrue(pair["prior_history_preserved"])
        withheld = StateStore(self.root / "forks/withheld/ora.json").load()
        retained = StateStore(self.root / "forks/retained/ora.json").load()
        prior_experiment = next(row for row in withheld["experiments"] if row["id"] == experiment_id)
        resolved = next(row for row in retained["experiments"] if row["id"] == experiment_id)
        self.assertEqual(prior_experiment["readiness"], "awaiting_native_evidence")
        self.assertEqual(resolved["readiness"], "resolved")
        self.assertEqual(retained["cycles"], withheld["cycles"])
        self.assertEqual(retained["updated_at"], withheld["updated_at"])
        self.assertFalse(any(row.get("kind") == "native_inquiry_evidence"
                             and json.loads(row["content"]) == payload for row in withheld["episodes"]))


if __name__ == "__main__":
    unittest.main()
