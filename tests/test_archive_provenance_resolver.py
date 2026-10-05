from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from archive_provenance_resolver import ArchiveProvenanceResolver
from episode_archive_contract import EpisodeArchiveSegment, build_archive_segment
from agenttest.state import initial_state


def episode(identifier: str, cycle: int) -> dict:
    return {
        "id": identifier,
        "cycle": cycle,
        "time": "2026-10-05T00:00:00+00:00",
        "kind": "stimulus",
        "content": identifier,
        "concepts": [],
    }


class ArchiveProvenanceResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archived = [episode("E000001", 1), episode("E000002", 2)]
        built = build_archive_segment(
            self.archived,
            self.root / "archive",
            production_base="a" * 40,
            source_state_sha256="b" * 64,
            source_episode_count=4,
        )
        self.segment = EpisodeArchiveSegment.load(built["manifest_path"])
        self.state = initial_state()
        self.state["episodes"] = [episode("E000003", 3), episode("E000004", 4)]
        self.state["next_episode_index"] = 5

    def test_hot_and_archive_locations_are_distinct(self):
        resolver = ArchiveProvenanceResolver(self.state, [self.segment])
        self.assertEqual(resolver.location("E000001"), "archive")
        self.assertEqual(resolver.location("E000004"), "hot")
        self.assertIsNone(resolver.location("E999999"))

    def test_provenance_lookup_reads_exact_archive_record(self):
        resolver = ArchiveProvenanceResolver(self.state, [self.segment])
        result = resolver.resolve("E000001", purpose="provenance_lookup")
        self.assertEqual(result["location"], "archive")
        self.assertEqual(result["record"], self.archived[0])
        self.assertEqual(result["segment_id"], self.segment.manifest["segment_id"])

    def test_historical_lookup_reads_hot_record_without_archive_authority(self):
        resolver = ArchiveProvenanceResolver(self.state, [self.segment])
        result = resolver.resolve("E000004", purpose="historical_lookup")
        self.assertEqual(result["location"], "hot")
        self.assertEqual(result["record"]["id"], "E000004")

    def test_archived_membership_does_not_broaden_generic_evidence(self):
        resolver = ArchiveProvenanceResolver(self.state, [self.segment])
        self.assertFalse(resolver.is_generic_evidence_known("E000001"))
        self.assertTrue(resolver.is_generic_evidence_known("E000003"))
        for purpose in (
            "generic_evidence",
            "native_inquiry_grounding",
            "native_inquiry_resolution",
            "cognition_grounding",
            "self_proposal_grounding",
        ):
            with self.assertRaises(PermissionError):
                resolver.resolve("E000001", purpose=purpose)

    def test_missing_provenance_fails_explicitly_in_batch_lookup(self):
        resolver = ArchiveProvenanceResolver(self.state, [self.segment])
        with self.assertRaises(KeyError):
            resolver.resolve_refs(
                ["E000001", "E999999"],
                purpose="provenance_lookup",
            )

    def test_hot_archive_overlap_fails_closed(self):
        state = initial_state()
        state["episodes"] = [episode("E000001", 1)]
        with self.assertRaisesRegex(ValueError, "overlap"):
            ArchiveProvenanceResolver(state, [self.segment])

    def test_duplicate_archive_ownership_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "multiple archive segments"):
            ArchiveProvenanceResolver(
                self.state,
                [self.segment, self.segment],
            )


if __name__ == "__main__":
    unittest.main()
