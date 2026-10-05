from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.semantic import consolidate_semantic_memory
from agenttest.state import StateStore, initial_state
from scripts.episode_archive_reference_diagnostic import analyze, collect_external_episode_refs
from tests.test_native_inquiry_resolution import temporal_candidate, temporal_evidence


class EpisodeArchiveReferenceDiagnosticTests(unittest.TestCase):
    def test_reference_collector_excludes_episode_ledger_but_finds_external_refs(self):
        state = initial_state()
        state["episodes"] = [{"id": "E000001"}, {"id": "E000002"}]
        state["questions"] = [{"id": "Q1", "source_evidence_refs": ["E000001"]}]
        state["semantic_memory"]["concepts"] = {
            "x": {"episode_refs": ["E000002"], "count": 1, "first_cycle": 1, "last_cycle": 1}
        }
        refs = collect_external_episode_refs(state)
        self.assertEqual(refs["ids"], ["E000001", "E000002"])
        self.assertEqual(refs["occurrence_count"], 2)

    def test_analysis_reports_missing_and_unreferenced_ids_without_mutation(self):
        state = initial_state()
        state["episodes"] = [{"id": "E000001"}, {"id": "E000002"}, {"id": "E000003"}]
        state["questions"] = [{"id": "Q1", "source_evidence_refs": ["E000001", "E000099"]}]
        before = repr(state)
        report = analyze(state, state_bytes=1234)
        self.assertEqual(report["referenced_episode_ids_missing_from_hot_ledger"], ["E000099"])
        self.assertEqual(report["unreferenced_hot_episode_count"], 2)
        self.assertEqual(repr(state), before)

    def test_prefix_deletion_causes_positional_semantic_cursor_to_skip_new_episode(self):
        state = initial_state()
        state["episodes"] = [
            {"id": "E000001", "cycle": 1, "concepts": ["one"]},
            {"id": "E000002", "cycle": 2, "concepts": ["two"]},
            {"id": "E000003", "cycle": 3, "concepts": ["three"]},
        ]
        consolidate_semantic_memory(state)
        self.assertEqual(state["semantic_memory"]["last_episode_index"], 3)
        del state["episodes"][:2]
        state["episodes"].append({"id": "E000004", "cycle": 4, "concepts": ["four"]})
        result = consolidate_semantic_memory(state)
        self.assertEqual(result["episodes_consolidated"], 0)
        self.assertNotIn("four", state["semantic_memory"]["concepts"])

    def test_prefix_deletion_causes_fresh_native_outcome_to_fail_old_list_index_floor(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        store.save(initial_state())
        core = AgentCore(store)

        unrelated = temporal_evidence()
        unrelated["relation"]["feature"] = "other_signal"
        core.record_native_evidence(unrelated, enabled=True, persist=True)

        grounding = core.record_native_evidence(
            temporal_evidence(),
            enabled=True,
            persist=True,
        )
        inquiry = core.propose_native_inquiry(
            temporal_candidate(grounding["evidence_ref"]),
            enabled=True,
            persist=True,
        )
        self.assertEqual(
            inquiry["experiment"]["native_inquiry"]["resolution_evidence_floor_episode_count"],
            2,
        )

        state = store.load()
        state["episodes"] = state["episodes"][1:]
        store.save(state)

        fresh = core.record_native_evidence(
            temporal_evidence(refs=["after-a", "after-b"]),
            enabled=True,
            persist=True,
        )
        with self.assertRaisesRegex(ValueError, "predates the inquiry"):
            AgentCore(store).resolve_native_inquiry(
                inquiry["experiment"]["id"],
                fresh["evidence_ref"],
                enabled=True,
                persist=True,
            )

    def test_report_marks_prefix_deletion_unsafe_when_cursor_is_current(self):
        state = initial_state()
        state["episodes"] = [{"id": f"E{i:06d}"} for i in range(1, 101)]
        state["semantic_memory"]["last_episode_index"] = 100
        state["next_episode_index"] = 101
        report = analyze(state, state_bytes=10000)
        one = next(row for row in report["deletion_risk_simulation"] if row["removed_prefix_count"] == 1)
        self.assertFalse(one["semantic_would_process_new_episode"])
        self.assertTrue(one["hypothetical_fresh_outcome_rejected_as_predating_inquiry"])
        self.assertFalse(report["conclusion"]["physical_prefix_deletion_safe_now"])


if __name__ == "__main__":
    unittest.main()
