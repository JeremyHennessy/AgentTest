"""Copied-only executor source contracts; no native-selection milestone claims."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_challenge_multi_action_authority as fixtures
import challenge_action_authority as authority
import challenge_shadow_recorder as recorder_module
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from native_observe_inquire_integration import (
    observe_and_inquire_policy, source_manifest_hash, stage_publication_inquiry,
)


class ChallengeSourceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        builder = fixtures.ChallengeMultiActionAuthorityTests()
        builder.root = self.root
        self.recorder, self.world = builder._prefix(steps=12)

    def _prepared(self, case="control"):
        manifest = recorder_module.source_manifest()
        publication = self.recorder.publication()
        if case == "wrong_source":
            old_source = manifest["source_id"]
            manifest["source_id"] = "research.challenge-v1." + "0" * 16
            publication["source_id"] = manifest["source_id"]
            publication["observation_refs"] = [
                manifest["source_id"] + ref[len(old_source):]
                for ref in publication["observation_refs"]
            ]
        elif case == "wrong_schema":
            manifest["observation_schema"] = "incompatible-world-v1"
        elif case == "wrong_recorder":
            manifest["recorder_version"] = "incompatible-recorder-v1"
        elif case in {"unknown_feature", "public_inlet_feature"}:
            publication["selected_temporal_candidate"]["feature"] = (
                "unknown.valid.feature" if case == "unknown_feature"
                else "pub." + "a" * 40
            )
        elif case == "unavailable_feature":
            cursor = self.recorder.store.load()[recorder_module.STATE_KEY]
            currently_visible = recorder_module.public_features(
                self.recorder.latest_observation()
            )
            historical = sorted(set(cursor["totals"]) - set(currently_visible))
            self.assertTrue(historical, "fixture must contain an occluded known feature")
            publication["selected_temporal_candidate"]["feature"] = historical[0]
        publication["source_manifest_hash"] = source_manifest_hash(manifest)
        ora = StateStore(self.root / (case + "-ora.json"))
        ora.save(initial_state())
        staged = stage_publication_inquiry(
            AgentCore(ora), policy=observe_and_inquire_policy(),
            source_manifest=manifest, publication=publication,
        )
        experiment_id = staged["inquiry_result"]["experiment"]["id"]
        executor = authority.ChallengeActionExecutor.create(
            self.root / (case + "-executor.json"),
            world=deepcopy(self.world), max_actions=1,
        )
        return ora, executor, experiment_id

    def _bytes(self, ora, executor):
        return {
            str(path): path.read_bytes()
            for path in (ora.path, self.recorder.store.path, executor.path)
        }

    def test_incompatible_public_staging_cannot_issue(self):
        for case in ("wrong_source", "wrong_schema", "wrong_recorder",
                     "unknown_feature", "public_inlet_feature"):
            with self.subTest(case=case):
                ora, executor, experiment_id = self._prepared(case)
                before = self._bytes(ora, executor)
                with self.assertRaisesRegex(ValueError, "source contract|unknown feature"):
                    executor.issue(ora_store=ora, recorder=self.recorder,
                                   experiment_id=experiment_id)
                self.assertEqual(self._bytes(ora, executor), before)

    def test_known_occluded_feature_is_unavailable_not_disproven(self):
        ora, executor, experiment_id = self._prepared("unavailable_feature")
        before = self._bytes(ora, executor)
        with self.assertRaisesRegex(ValueError, "temporarily unavailable"):
            executor.issue(ora_store=ora, recorder=self.recorder,
                           experiment_id=experiment_id)
        self.assertEqual(self._bytes(ora, executor), before)
        experiment = next(x for x in ora.load()["experiments"] if x["id"] == experiment_id)
        self.assertEqual(experiment["readiness"], "awaiting_native_evidence")
        self.assertNotIn("outcome", experiment)

    def test_execute_rechecks_contract_before_any_transition(self):
        # A synthetic issuer bypass creates an otherwise fresh invalid token.
        # This separately exercises execution's boundary, never a production path.
        for case in ("wrong_source", "wrong_schema", "wrong_recorder",
                     "unknown_feature", "public_inlet_feature", "unavailable_feature"):
            with self.subTest(case=case):
                ora, executor, experiment_id = self._prepared(case)
                with patch.object(authority, "_validate_inquiry_source", create=True):
                    token = executor.issue(ora_store=ora, recorder=self.recorder,
                                           experiment_id=experiment_id)["token"]
                before = self._bytes(ora, executor)
                with self.assertRaisesRegex(
                    ValueError, "source contract|unknown feature|temporarily unavailable"
                ):
                    executor.execute(token, ora_store=ora, recorder=self.recorder)
                self.assertEqual(self._bytes(ora, executor), before)

    def test_complete_grounding_and_unique_ownership_are_required(self):
        for case in ("changed_evidence", "duplicate_evidence", "duplicate_question",
                     "changed_question_binding", "changed_candidate_identity"):
            with self.subTest(case=case):
                ora, executor, experiment_id = self._prepared(case)
                state = ora.load()
                experiment = next(x for x in state["experiments"] if x["id"] == experiment_id)
                ref = experiment["native_inquiry"]["evidence_refs"][0]
                episode = next(x for x in state["episodes"] if x["id"] == ref)
                question = next(x for x in state["questions"] if x["id"] == experiment["question_id"])
                if case == "changed_evidence":
                    payload = json.loads(episode["content"])
                    payload["observation_refs"] = ["other-source:observation"]
                    episode["content"] = json.dumps(payload, sort_keys=True)
                elif case == "duplicate_evidence":
                    state["episodes"].append(deepcopy(episode))
                elif case == "duplicate_question":
                    state["questions"].append(deepcopy(question))
                elif case == "changed_question_binding":
                    question["source_evidence_refs"] = []
                else:
                    experiment["native_inquiry"]["candidate_id"] = "NIC:other"
                if case == "duplicate_evidence":
                    before = self._bytes(ora, executor)
                    # The existing StateStore contract rejects this even before
                    # executor admission; do not bypass that stronger boundary.
                    with self.assertRaisesRegex(ValueError, "duplicate episode identity"):
                        ora.save(state)
                    self.assertEqual(self._bytes(ora, executor), before)
                    continue
                ora.save(state)
                before = self._bytes(ora, executor)
                with self.assertRaisesRegex(ValueError, "source contract"):
                    executor.issue(ora_store=ora, recorder=self.recorder,
                                   experiment_id=experiment_id)
                self.assertEqual(self._bytes(ora, executor), before)

    def test_unchanged_legacy_stage_executes_once_and_budget_remains_bounded(self):
        ora, executor, experiment_id = self._prepared()
        ora_before = ora.path.read_bytes()
        recorder_before = self.recorder.store.path.read_bytes()
        original_selection = authority.select_epistemic_command(
            self.recorder.latest_observation(),
            feature=self.recorder.publication()["selected_temporal_candidate"]["feature"],
            relation=self.recorder.publication()["selected_temporal_candidate"]["relation"],
            associations=self.recorder.action_associations(),
        )
        issued = executor.issue(ora_store=ora, recorder=self.recorder,
                                experiment_id=experiment_id)
        self.assertEqual(issued["selection"], original_selection)
        self.assertEqual(issued["selection"]["mode"], "reduce_action_uncertainty")
        self.assertLess(issued["selection"]["present_evaluable"], 2)
        result = authority.ChallengeActionExecutor(executor.path).execute(
            issued["token"], ora_store=ora, recorder=self.recorder,
        )
        self.assertEqual(result["actions_consumed"], 1)
        self.assertEqual(result["remaining_budget"], 0)
        self.assertEqual(ora.path.read_bytes(), ora_before)
        self.assertEqual(self.recorder.store.path.read_bytes(), recorder_before)
        before = self._bytes(ora, executor)
        with self.assertRaisesRegex(RuntimeError, "already consumed"):
            executor.execute(issued["token"], ora_store=ora, recorder=self.recorder)
        with self.assertRaisesRegex(RuntimeError, "budget is exhausted"):
            executor.issue(ora_store=ora, recorder=self.recorder,
                           experiment_id=experiment_id)
        self.assertEqual(self._bytes(ora, executor), before)


if __name__ == "__main__":
    unittest.main()
