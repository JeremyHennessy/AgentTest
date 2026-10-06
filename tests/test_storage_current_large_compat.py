from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from agenttest.core import AgentCore
from agenttest.state import StateStore, migrate_state

PINNED_GROWTH_SHA = "343890f4e594003197f2c22e671d52c7532d2f82"
PINNED_CYCLE = 5658
PINNED_STATE_BYTES = 87187097
PINNED_JOURNAL_BYTES = 77545001
NOW = "2026-10-06T18:10:00+00:00"


class LegacyPrettyStore(StateStore):
    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = migrate_state(state)
        state["updated_at"] = NOW
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def append_journal(self, event):
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def fixed_clocks():
    stack = ExitStack()
    for name, module in list(sys.modules.items()):
        if name.startswith("agenttest.") and hasattr(module, "utc_now"):
            stack.enter_context(patch.object(module, "utc_now", return_value=NOW))
    return stack


class CurrentLargeStorageCompatibility(unittest.TestCase):
    def test_pinned_post_dispatch_state_and_journal(self):
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_path = root / "source" / "organism.json"
            journal_path = root / "source" / "journal.jsonl"
            state_path.parent.mkdir(parents=True)

            subprocess.run(
                ["git", "fetch", "--no-tags", "--depth=1", "origin", PINNED_GROWTH_SHA],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            with state_path.open("wb") as handle:
                subprocess.run(
                    ["git", "show", f"{PINNED_GROWTH_SHA}:state/organism.json"],
                    check=True,
                    stdout=handle,
                )
            with journal_path.open("wb") as handle:
                subprocess.run(
                    ["git", "show", f"{PINNED_GROWTH_SHA}:state/journal.jsonl"],
                    check=True,
                    stdout=handle,
                )

            self.assertEqual(state_path.stat().st_size, PINNED_STATE_BYTES)
            self.assertEqual(journal_path.stat().st_size, PINNED_JOURNAL_BYTES)

            original = json.loads(state_path.read_bytes())
            self.assertEqual(original["cycles"], PINNED_CYCLE)
            compact_state = (
                json.dumps(original, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            self.assertEqual(json.loads(compact_state), original)
            self.assertLess(len(compact_state), PINNED_STATE_BYTES)

            journal_compact_bytes = 0
            journal_events = 0
            with journal_path.open("rb") as handle:
                for raw_line in handle:
                    value = json.loads(raw_line)
                    encoded = (
                        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
                    ).encode("utf-8")
                    self.assertEqual(json.loads(encoded), value)
                    journal_compact_bytes += len(encoded)
                    journal_events += 1
            self.assertLess(journal_compact_bytes, PINNED_JOURNAL_BYTES)

            observation = deepcopy(original.get("environment_snapshots", [None])[-1])
            with fixed_clocks():
                legacy = LegacyPrettyStore(root / "legacy" / "organism.json")
                compact = StateStore(root / "compact" / "organism.json")
                legacy.save(deepcopy(original))
                compact.save(deepcopy(original))
                self.assertEqual(legacy.load(), compact.load())

                for index in range(3):
                    old = AgentCore(LegacyPrettyStore(legacy.path)).cycle(
                        "autonomous heartbeat",
                        observation=deepcopy(observation),
                        strict_experiment_admission=True,
                        planning_lab=True,
                        _now_override=NOW,
                    )
                    new = AgentCore(StateStore(compact.path)).cycle(
                        "autonomous heartbeat",
                        observation=deepcopy(observation),
                        strict_experiment_admission=True,
                        planning_lab=True,
                        _now_override=NOW,
                    )
                    self.assertEqual(old, new, f"result mismatch at copied cycle {index + 1}")
                    self.assertEqual(
                        LegacyPrettyStore(legacy.path).load(),
                        StateStore(compact.path).load(),
                        f"decoded state mismatch at copied cycle {index + 1}",
                    )

                old_events = [
                    json.loads(line)
                    for line in legacy.journal_path.read_text().splitlines()
                ]
                new_events = [
                    json.loads(line)
                    for line in compact.journal_path.read_text().splitlines()
                ]
                self.assertEqual(old_events, new_events)

            elapsed = time.monotonic() - started
            print(json.dumps({
                "classification": "synthetic copied current-large-state compatibility; no natural milestone credit",
                "pinned_growth_sha": PINNED_GROWTH_SHA,
                "source_cycle": PINNED_CYCLE,
                "original_state_bytes": PINNED_STATE_BYTES,
                "compact_state_bytes": len(compact_state),
                "state_saved_bytes": PINNED_STATE_BYTES - len(compact_state),
                "state_saved_percent": (PINNED_STATE_BYTES - len(compact_state)) / PINNED_STATE_BYTES * 100.0,
                "original_journal_bytes": PINNED_JOURNAL_BYTES,
                "compact_journal_bytes": journal_compact_bytes,
                "journal_saved_bytes": PINNED_JOURNAL_BYTES - journal_compact_bytes,
                "journal_saved_percent": (PINNED_JOURNAL_BYTES - journal_compact_bytes) / PINNED_JOURNAL_BYTES * 100.0,
                "journal_events": journal_events,
                "copied_cycle_pairs": 3,
                "ordinary_cycle_parity": True,
                "journal_parity": True,
                "elapsed_seconds": elapsed,
            }, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
