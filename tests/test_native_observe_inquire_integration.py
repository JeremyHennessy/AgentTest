from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from native_observe_inquire_integration import (
    DEFAULT_POLICY,
    PUBLICATION_VERSION,
    SOURCE_MANIFEST_VERSION,
    observe_and_inquire_policy,
    source_manifest_hash,
    stage_publication_inquiry,
    validate_policy,
    validate_publication,
    validate_source_manifest,
)


def manifest():
    return {
        "version": SOURCE_MANIFEST_VERSION,
        "source_id": "research.fixture.publicstream",
        "source_kind": "public_observation_stream",
        "observation_schema": "public-fixture-v1",
        "recorder_version": "public-stream-recorder-v1",
        "provenance_mode": "hash_chained_unsigned",
        "cumulative_publications": True,
        "max_recent_observation_refs": 64,
        "signed_source": False,
        "allow_environment_actions": False,
    }


def publication(*, end_cycle=4, chain_seed="one"):
    source = manifest()
    return {
        "version": PUBLICATION_VERSION,
        "source_id": source["source_id"],
        "source_manifest_hash": source_manifest_hash(source),
        "chain_hash": hashlib.sha256(chain_seed.encode("utf-8")).hexdigest(),
        "coverage": {"start_cycle": 0, "end_cycle": end_cycle},
        "observation_refs": [
            f"{source['source_id']}:obs-{index:04d}"
            for index in range(max(2, end_cycle + 1))
        ][-64:],
        "selected_temporal_candidate": {
            "relation": "same_next_observation",
            "feature": "public_feature",
            "objective": "information_gain",
            "objective_score": 0.55,
            "evaluable": min(4, end_cycle),
            "confirmations": min(3, end_cycle),
            "refutations": min(1, end_cycle),
        },
    }


class NativeObserveInquireIntegrationTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 30
        state["generation"] = 30
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return store

    def test_default_policy_is_fully_off(self):
        self.assertEqual(validate_policy(None), DEFAULT_POLICY)
        store = self.make_store()
        before = store.path.read_bytes()
        with self.assertRaises(RuntimeError):
            stage_publication_inquiry(
                AgentCore(store),
                policy=DEFAULT_POLICY,
                source_manifest=manifest(),
                publication=publication(),
            )
        self.assertEqual(store.path.read_bytes(), before)

    def test_enabled_policy_cannot_grant_action_or_phase42_authority(self):
        for field in (
            "allow_environment_actions",
            "allow_action_lab",
            "allow_planning_lab",
            "allow_phase42_credit",
        ):
            policy = observe_and_inquire_policy()
            policy[field] = True
            with self.assertRaises(ValueError):
                validate_policy(policy)

    def test_source_manifest_is_read_only_unsigned_public_stream(self):
        checked = validate_source_manifest(manifest())
        self.assertFalse(checked["signed_source"])
        self.assertFalse(checked["allow_environment_actions"])
        for field, value in (
            ("signed_source", True),
            ("allow_environment_actions", True),
            ("cumulative_publications", False),
            ("max_recent_observation_refs", 65),
        ):
            bad = manifest()
            bad[field] = value
            with self.assertRaises(ValueError):
                validate_source_manifest(bad)

    def test_publication_is_bound_to_source_manifest_and_temporal_policy(self):
        policy = observe_and_inquire_policy()
        checked = validate_publication(publication(), manifest(), policy)
        self.assertEqual(
            checked["selected_temporal_candidate"]["relation"],
            "same_next_observation",
        )

        bad_hash = publication()
        bad_hash["source_manifest_hash"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_publication(bad_hash, manifest(), policy)

        action_relation = publication()
        action_relation["selected_temporal_candidate"][
            "relation"
        ] = "action_associated_with_change"
        with self.assertRaises(ValueError):
            validate_publication(action_relation, manifest(), policy)

    def test_observation_refs_must_remain_source_bound(self):
        bad = publication()
        bad["observation_refs"][0] = "another.source:obs-0000"
        with self.assertRaises(ValueError):
            validate_publication(
                bad,
                manifest(),
                observe_and_inquire_policy(),
            )

    def test_staging_is_atomic_and_does_not_advance_cycle(self):
        store = self.make_store()
        before = store.load()
        result = stage_publication_inquiry(
            AgentCore(store),
            policy=observe_and_inquire_policy(),
            source_manifest=manifest(),
            publication=publication(),
        )
        after = store.load()
        self.assertEqual(result["status"], "staged")
        self.assertEqual(after["cycles"], before["cycles"])
        self.assertEqual(after["generation"], before["generation"])
        self.assertEqual(after["action_lab"], before["action_lab"])
        self.assertEqual(after["planning_lab"], before["planning_lab"])
        inquiry = result["inquiry_result"]
        self.assertEqual(
            inquiry["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertTrue(
            inquiry["candidate"]["id"].startswith(
                "NIC:integration:"
                + source_manifest_hash(manifest())[:12]
                + ":"
            )
        )
        episode = next(
            item
            for item in after["episodes"]
            if item["id"] == result["evidence_result"]["evidence_ref"]
        )
        payload = json.loads(episode["content"])
        self.assertTrue(
            all(
                ref.startswith(manifest()["source_id"] + ":")
                for ref in payload["observation_refs"]
            )
        )

    def test_identical_cumulative_publication_is_idempotent(self):
        store = self.make_store()
        first = stage_publication_inquiry(
            AgentCore(store),
            policy=observe_and_inquire_policy(),
            source_manifest=manifest(),
            publication=publication(),
        )
        before_retry = store.path.read_bytes()
        second = stage_publication_inquiry(
            AgentCore(store),
            policy=observe_and_inquire_policy(),
            source_manifest=manifest(),
            publication=publication(),
        )
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertEqual(second["status"], "already_staged")
        self.assertEqual(store.path.read_bytes(), before_retry)

    def test_new_overlapping_cumulative_snapshot_is_blocked_while_inquiry_active(self):
        store = self.make_store()
        stage_publication_inquiry(
            AgentCore(store),
            policy=observe_and_inquire_policy(),
            source_manifest=manifest(),
            publication=publication(),
        )
        before = store.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "active inquiry"):
            stage_publication_inquiry(
                AgentCore(store),
                policy=observe_and_inquire_policy(),
                source_manifest=manifest(),
                publication=publication(end_cycle=5, chain_seed="two"),
            )
        self.assertEqual(store.path.read_bytes(), before)

    def test_inquiry_failure_does_not_leave_orphan_evidence(self):
        store = self.make_store()
        before = store.path.read_bytes()
        with patch.object(
            AgentCore,
            "propose_native_inquiry",
            side_effect=RuntimeError("injected inquiry failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                stage_publication_inquiry(
                    AgentCore(store),
                    policy=observe_and_inquire_policy(),
                    source_manifest=manifest(),
                    publication=publication(),
                )
        self.assertEqual(store.path.read_bytes(), before)

    def test_integration_module_has_no_environment_or_lab_execution_path(self):
        source = (
            ROOT / "experiments" / "native_observe_inquire_integration.py"
        ).read_text()
        for forbidden in (
            "action_lab=True",
            "planning_lab=True",
            "transition(",
            "subprocess",
            "requests",
            "openai",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
