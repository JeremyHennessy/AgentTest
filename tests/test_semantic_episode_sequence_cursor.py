from __future__ import annotations

from copy import deepcopy
import unittest

from agenttest.episode_identity import allocate_episode_id, infer_episode_sequence_cursor
from agenttest.semantic import consolidate_semantic_memory
from agenttest.state import initial_state, migrate_state


class SemanticEpisodeSequenceCursorTests(unittest.TestCase):
    def episode(self, identifier: str, cycle: int, concept: str):
        return {
            "id": identifier,
            "cycle": cycle,
            "time": f"2026-10-05T00:{cycle:02d}:00+00:00",
            "kind": "test",
            "content": concept,
            "concepts": [concept],
        }

    def test_legacy_dense_cursor_migrates_without_rewriting_semantic_content(self):
        state = initial_state()
        state["episodes"] = [
            self.episode("E000001", 1, "one"),
            self.episode("E000002", 2, "two"),
        ]
        state["next_episode_index"] = 3
        state["semantic_memory"] = {
            "last_episode_index": 2,
            "concepts": {"existing": {"count": 4}},
            "associations": {"a|b": {"count": 2}},
        }
        original = deepcopy(state["semantic_memory"])
        migrated = migrate_state(state)
        self.assertEqual(migrated["semantic_memory"]["last_episode_sequence"], 2)
        comparable = deepcopy(migrated["semantic_memory"])
        comparable.pop("last_episode_sequence")
        self.assertEqual(comparable, original)

    def test_sparse_legacy_cursor_uses_retained_numeric_identity_not_list_position(self):
        episodes = [
            self.episode("E000001", 1, "one"),
            self.episode("E000099", 2, "ninety-nine"),
        ]
        self.assertEqual(infer_episode_sequence_cursor(episodes, 2), 99)

    def test_normal_consolidation_preserves_counts_and_advances_both_cursors(self):
        state = initial_state()
        state["episodes"] = [
            self.episode("E000001", 1, "one"),
            self.episode("E000002", 2, "two"),
            self.episode("E000003", 3, "three"),
        ]
        state["next_episode_index"] = 4
        result = consolidate_semantic_memory(state)
        self.assertEqual(result["episodes_consolidated"], 3)
        self.assertEqual(state["semantic_memory"]["last_episode_index"], 3)
        self.assertEqual(state["semantic_memory"]["last_episode_sequence"], 3)
        self.assertEqual(state["semantic_memory"]["concepts"]["three"]["count"], 1)

    def test_prefix_removal_no_longer_skips_new_numeric_episode(self):
        state = initial_state()
        state["episodes"] = [
            self.episode("E000001", 1, "one"),
            self.episode("E000002", 2, "two"),
            self.episode("E000003", 3, "three"),
        ]
        state["next_episode_index"] = 4
        consolidate_semantic_memory(state)
        three_before = state["semantic_memory"]["concepts"]["three"]["count"]

        del state["episodes"][:2]
        new_id = allocate_episode_id(state)
        self.assertEqual(new_id, "E000004")
        state["episodes"].append(self.episode(new_id, 4, "four"))
        result = consolidate_semantic_memory(state)

        self.assertEqual(result["episodes_consolidated"], 1)
        self.assertEqual(state["semantic_memory"]["concepts"]["four"]["count"], 1)
        self.assertEqual(state["semantic_memory"]["concepts"]["three"]["count"], three_before)
        self.assertEqual(state["semantic_memory"]["last_episode_sequence"], 4)
        self.assertEqual(state["semantic_memory"]["last_episode_index"], 2)

    def test_middle_removal_does_not_reprocess_retained_numeric_history(self):
        state = initial_state()
        state["episodes"] = [
            self.episode("E000001", 1, "one"),
            self.episode("E000002", 2, "two"),
            self.episode("E000003", 3, "three"),
        ]
        state["next_episode_index"] = 4
        consolidate_semantic_memory(state)
        counts = {
            key: value["count"]
            for key, value in state["semantic_memory"]["concepts"].items()
        }
        state["episodes"].pop(1)
        consolidate_semantic_memory(state)
        self.assertEqual(
            {key: value["count"] for key, value in state["semantic_memory"]["concepts"].items()},
            counts,
        )
        self.assertEqual(state["semantic_memory"]["last_episode_sequence"], 3)

    def test_opaque_legacy_episode_uses_positional_fallback_without_reprocessing(self):
        state = initial_state()
        state["episodes"] = [
            self.episode("E000001", 1, "one"),
            self.episode("external.episode", 2, "opaque"),
        ]
        state["next_episode_index"] = 3
        state["semantic_memory"].pop("last_episode_sequence")
        state["semantic_memory"]["last_episode_index"] = 2
        state["semantic_memory"]["concepts"] = {
            "one": {"concept": "one", "count": 1, "first_cycle": 1, "last_cycle": 1, "episode_refs": ["E000001"]},
            "opaque": {"concept": "opaque", "count": 1, "first_cycle": 2, "last_cycle": 2, "episode_refs": ["external.episode"]},
        }
        result = consolidate_semantic_memory(state)
        self.assertEqual(result["episodes_consolidated"], 0)
        self.assertEqual(state["semantic_memory"]["last_episode_sequence"], 1)

    def test_invalid_semantic_sequence_cursor_fails_closed(self):
        for value in (-1, True, "3", 1.5, None):
            with self.subTest(value=value):
                state = initial_state()
                state["semantic_memory"]["last_episode_sequence"] = value
                with self.assertRaises(ValueError):
                    migrate_state(state)

    def test_raw_legacy_state_can_consolidate_without_prior_store_migration(self):
        state = initial_state()
        state["episodes"] = [
            self.episode("E000001", 1, "one"),
            self.episode("E000002", 2, "two"),
        ]
        state["semantic_memory"].pop("last_episode_sequence")
        state["semantic_memory"]["last_episode_index"] = 2
        state["semantic_memory"]["concepts"] = {
            "one": {"concept": "one", "count": 1, "first_cycle": 1, "last_cycle": 1, "episode_refs": ["E000001"]},
            "two": {"concept": "two", "count": 1, "first_cycle": 2, "last_cycle": 2, "episode_refs": ["E000002"]},
        }
        result = consolidate_semantic_memory(state)
        self.assertEqual(result["episodes_consolidated"], 0)
        self.assertEqual(state["semantic_memory"]["last_episode_sequence"], 2)


if __name__ == "__main__":
    unittest.main()
