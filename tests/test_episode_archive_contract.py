from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from episode_archive_contract import (
    EpisodeArchiveSegment,
    build_archive_segment,
    canonical_episode_bytes,
)
from episode_archive_selection import derive_protection
from agenttest.evidence import known_evidence_ids
from agenttest.state import initial_state


def episode(identifier: str, cycle: int, *, kind: str = "stimulus") -> dict:
    return {
        "id": identifier,
        "cycle": cycle,
        "time": "2026-10-05T00:00:00+00:00",
        "kind": kind,
        "content": f"episode {identifier}",
        "concepts": ["episode"],
    }


class EpisodeArchiveContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.episodes = [
            episode("E000001", 1),
            episode("E000002", 2),
            episode("E000003", 3),
        ]

    def build(self):
        return build_archive_segment(
            self.episodes,
            self.root,
            production_base="a" * 40,
            source_state_sha256="b" * 64,
            source_episode_count=3,
        )

    def test_round_trip_preserves_exact_records_and_canonical_bytes(self):
        built = self.build()
        segment = EpisodeArchiveSegment.load(
            built["manifest_path"],
            expected_production_base="a" * 40,
            expected_source_state_sha256="b" * 64,
        )
        self.assertEqual(segment.archived_ids, ("E000001", "E000002", "E000003"))
        for item in self.episodes:
            identifier = item["id"]
            self.assertEqual(
                segment.lookup(identifier, purpose="historical_lookup"),
                item,
            )
            self.assertEqual(
                segment.canonical_record_bytes(
                    identifier,
                    purpose="recovery_restore",
                ),
                canonical_episode_bytes(item),
            )

    def test_archive_existence_does_not_grant_generic_evidence_authority(self):
        built = self.build()
        segment = EpisodeArchiveSegment.load(built["manifest_path"])
        self.assertTrue(segment.contains("E000001"))
        self.assertFalse(segment.grants_generic_evidence_authority("E000001"))
        for purpose in (
            "generic_evidence",
            "native_inquiry_grounding",
            "native_inquiry_resolution",
            "cognition_grounding",
            "self_proposal_grounding",
        ):
            with self.subTest(purpose=purpose):
                with self.assertRaises(PermissionError):
                    segment.lookup("E000001", purpose=purpose)

    def test_missing_record_is_not_invented(self):
        built = self.build()
        segment = EpisodeArchiveSegment.load(built["manifest_path"])
        self.assertFalse(segment.contains("E999999"))
        self.assertIsNone(
            segment.lookup("E999999", purpose="historical_lookup")
        )

    def test_restore_reconstructs_original_ledger(self):
        built = self.build()
        segment = EpisodeArchiveSegment.load(built["manifest_path"])
        hot = [
            episode("E000004", 4),
            episode("E000005", 5),
        ]
        restored = segment.restore_episode_ledger(hot)
        self.assertEqual(restored, [*self.episodes, *hot])

    def test_restore_rejects_hot_archive_overlap(self):
        built = self.build()
        segment = EpisodeArchiveSegment.load(built["manifest_path"])
        with self.assertRaisesRegex(ValueError, "overlap"):
            segment.restore_episode_ledger([episode("E000003", 3)])

    def test_corrupted_compressed_segment_fails_closed(self):
        built = self.build()
        path = Path(built["segment_path"])
        payload = bytearray(path.read_bytes())
        payload[-1] ^= 1
        path.write_bytes(bytes(payload))
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            EpisodeArchiveSegment.load(built["manifest_path"])

    def test_corrupted_index_fails_closed(self):
        built = self.build()
        path = Path(built["index_path"])
        payload = json.loads(path.read_text())
        payload["records"][0]["record_sha256"] = "0" * 64
        path.write_text(json.dumps(payload, sort_keys=True))
        with self.assertRaisesRegex(ValueError, "index digest mismatch"):
            EpisodeArchiveSegment.load(built["manifest_path"])

    def test_manifest_cannot_enable_generic_evidence_authority(self):
        built = self.build()
        path = Path(built["manifest_path"])
        manifest = json.loads(path.read_text())
        manifest["generic_evidence_authority"] = True
        path.write_text(json.dumps(manifest, sort_keys=True))
        with self.assertRaisesRegex(ValueError, "generic evidence authority"):
            EpisodeArchiveSegment.load(path)

    def test_duplicate_or_opaque_ids_fail_before_archive_write(self):
        duplicate = [
            episode("E000001", 1),
            episode("E000001", 2),
        ]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_archive_segment(
                duplicate,
                self.root / "duplicate",
                production_base="a" * 40,
                source_state_sha256="b" * 64,
                source_episode_count=2,
            )
        with self.assertRaisesRegex(ValueError, "numeric Core"):
            build_archive_segment(
                [episode("legacy-opaque", 1)],
                self.root / "opaque",
                production_base="a" * 40,
                source_state_sha256="b" * 64,
                source_episode_count=1,
            )

    def test_selection_protects_explicit_reference_and_hot_suffix(self):
        state = initial_state()
        state["cycles"] = 6
        state["episodes"] = [
            episode(f"E{index:06d}", index)
            for index in range(1, 7)
        ]
        state["next_episode_index"] = 7
        state["reflections"] = [
            {"id": "R000001", "evidence_refs": ["E000002"]}
        ]
        result = derive_protection(state, hot_suffix=2)
        self.assertIn("E000002", result["protected_ids"])
        self.assertIn("E000005", result["protected_ids"])
        self.assertIn("E000006", result["protected_ids"])
        self.assertIn("E000001", result["eligible_ids"])

    def test_pruned_hot_state_does_not_automatically_keep_archived_ids_known(self):
        state = initial_state()
        state["episodes"] = list(self.episodes)
        before = known_evidence_ids(state)
        self.assertTrue({"E000001", "E000002", "E000003"} <= before)
        state["episodes"] = [self.episodes[-1]]
        after = known_evidence_ids(state)
        self.assertNotIn("E000001", after)
        self.assertNotIn("E000002", after)
        self.assertIn("E000003", after)


if __name__ == "__main__":
    unittest.main()
