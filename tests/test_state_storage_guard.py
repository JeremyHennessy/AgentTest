from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agenttest.state as state_module
from agenttest.state import StateStore, initial_state


class StateStorageGuardTests(unittest.TestCase):
    def make_store(self) -> tuple[tempfile.TemporaryDirectory[str], StateStore]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return temp, StateStore(Path(temp.name) / "organism.json")

    def test_snapshot_is_written_as_deterministic_compact_json(self) -> None:
        _temp, store = self.make_store()
        state = initial_state()
        state["episodes"] = [
            {
                "id": "E000001",
                "text": "compact storage must preserve semantic content",
                "nested": {"values": [1, 2, 3], "flag": True},
            }
        ]

        store.save(state)

        rendered = store.path.read_text(encoding="utf-8")
        parsed = json.loads(rendered)
        expected = json.dumps(
            parsed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ) + "\n"
        self.assertEqual(rendered, expected)
        self.assertEqual(StateStore(store.path).load()["episodes"], state["episodes"])

    def test_journal_rollover_preserves_every_event_in_order(self) -> None:
        _temp, store = self.make_store()
        events = [
            {"event": "test", "sequence": index, "payload": "x" * 40}
            for index in range(8)
        ]

        with patch.object(
            state_module,
            "JOURNAL_SEGMENT_BYTES",
            180,
            create=True,
        ):
            for event in events:
                store.append_journal(event)

        segments = sorted(store.path.parent.glob("journal.[0-9][0-9][0-9][0-9][0-9][0-9].jsonl"))
        self.assertGreaterEqual(len(segments), 1)
        self.assertTrue(store.journal_path.exists())

        recovered = []
        for path in [*segments, store.journal_path]:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    recovered.append(json.loads(line))

        self.assertEqual(recovered, events)
        self.assertEqual(len(segments), len({path.name for path in segments}))


if __name__ == "__main__":
    unittest.main()
