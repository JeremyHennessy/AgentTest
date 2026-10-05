from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.evidence import known_evidence_ids
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.state import StateStore, initial_state


def temporal_evidence(feature: str) -> dict:
    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": "same_next_observation",
            "feature": feature,
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": [
            f"retention.fixture:{feature}:before",
            f"retention.fixture:{feature}:after",
        ],
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": 1,
            "confirmations": 1,
            "refutations": 0,
        },
    }


class NativeEvidenceRetentionHazardTests(unittest.TestCase):
    def make_store(self) -> StateStore:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 4
        state["generation"] = 4
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return store

    def record(self, store: StateStore, feature: str) -> str:
        return AgentCore(store).record_native_evidence(
            temporal_evidence(feature),
            enabled=True,
            persist=True,
        )["evidence_ref"]

    def test_middle_deletion_causes_duplicate_future_episode_id(self):
        store = self.make_store()
        refs = [self.record(store, feature) for feature in ("a", "b", "c")]
        self.assertEqual(refs, ["E000001", "E000002", "E000003"])

        state = store.load()
        state["episodes"] = [
            episode
            for episode in state["episodes"]
            if episode["id"] != "E000002"
        ]
        store.save(state)

        new_ref = self.record(store, "d")
        ids = [episode["id"] for episode in store.load()["episodes"]]
        self.assertEqual(new_ref, "E000003")
        self.assertEqual(ids.count("E000003"), 2)

    def test_state_save_does_not_reject_dangling_evidence_reference(self):
        store = self.make_store()
        ref = self.record(store, "referenced")
        state = store.load()
        state["questions"].append(
            {
                "id": "QRETENTION",
                "text": "Does retention preserve cited evidence?",
                "status": "open",
                "created_cycle": 4,
                "times_selected": 0,
                "last_selected_cycle": None,
                "source_evidence_refs": [ref],
            }
        )
        state["episodes"] = [
            episode for episode in state["episodes"] if episode["id"] != ref
        ]
        store.save(state)

        loaded = store.load()
        question = next(
            item for item in loaded["questions"]
            if item["id"] == "QRETENTION"
        )
        self.assertEqual(question["source_evidence_refs"], [ref])
        self.assertNotIn(ref, known_evidence_ids(loaded))

    def test_tombstone_episode_remains_in_generic_known_evidence_universe(self):
        store = self.make_store()
        ref = self.record(store, "tombstone")
        state = store.load()
        episode = next(item for item in state["episodes"] if item["id"] == ref)
        episode["kind"] = "native_evidence_tombstone"
        episode["content"] = json.dumps(
            {"status": "compacted", "original_kind": "native_inquiry_evidence"}
        )
        store.save(state)

        loaded = store.load()
        self.assertIn(ref, known_evidence_ids(loaded))
        retained = next(item for item in loaded["episodes"] if item["id"] == ref)
        self.assertEqual(retained["kind"], "native_evidence_tombstone")

    def test_invalid_compacted_native_payload_remains_known_but_not_native_valid(self):
        store = self.make_store()
        ref = self.record(store, "invalid-content")
        state = store.load()
        episode = next(item for item in state["episodes"] if item["id"] == ref)
        episode["content"] = "{}"
        store.save(state)

        loaded = store.load()
        self.assertIn(ref, known_evidence_ids(loaded))
        payload = json.loads(
            next(item for item in loaded["episodes"] if item["id"] == ref)[
                "content"
            ]
        )
        with self.assertRaises(ValueError):
            AgentCore(store).record_native_evidence(
                payload,
                enabled=True,
                persist=False,
            )


if __name__ == "__main__":
    unittest.main()
