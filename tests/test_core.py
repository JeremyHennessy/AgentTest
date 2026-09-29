from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agenttest.core import AgentCore
from agenttest.evolution import propose_growth_experiment
from agenttest.perception import changed_fields, repository_snapshot
from agenttest.state import SCHEMA_VERSION, StateStore


class AgentCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "organism.json"
        self.store = StateStore(self.state_path)
        self.core = AgentCore(self.store)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cycle_persists_memory_and_question(self) -> None:
        result = self.core.cycle("memory curiosity evidence continuity")
        state = self.store.load()

        self.assertEqual(state["cycles"], 1)
        self.assertEqual(len(state["episodes"]), 1)
        self.assertGreaterEqual(len(state["questions"]), 1)
        self.assertEqual(result["question"]["status"], "open")
        self.assertTrue(self.store.journal_path.exists())

    def test_continuity_increases_only_after_multiple_cycles(self) -> None:
        first = self.core.cycle("first observation")
        second = self.core.cycle("second observation")

        self.assertLess(first["metrics"]["continuity"], second["metrics"]["continuity"])
        self.assertEqual(second["metrics"]["continuity"], 1.0)

    def test_recorded_outcome_creates_reflection_and_learning_evidence(self) -> None:
        result = self.core.cycle("test evidence")
        experiment_id = result["experiment"]["id"]

        reflection = self.core.record_outcome(experiment_id, "Prediction was not supported.", 0.8)
        state = self.store.load()

        self.assertEqual(reflection["experiment_id"], experiment_id)
        self.assertEqual(state["experiments"][0]["status"], "completed")
        self.assertGreater(state["metrics"]["learning"], 0.0)
        self.assertGreater(state["metrics"]["reflection"], 0.0)

    def test_growth_proposal_is_falsifiable(self) -> None:
        self.core.cycle()
        proposal = propose_growth_experiment(self.store.load())

        self.assertIn("target_dimension", proposal)
        self.assertIn("falsification", proposal)
        self.assertEqual(proposal["status"], "proposed")

    def test_environment_change_becomes_surprise(self) -> None:
        first = {
            "sensor": "test",
            "branch": "main",
            "tracked_files": 10,
            "python_files": 4,
            "python_source_lines": 100,
            "test_files": 1,
            "working_tree_clean": True,
        }
        second = dict(first)
        second["python_source_lines"] = 120

        self.core.cycle(observation=first)
        result = self.core.cycle(observation=second)

        self.assertIsNotNone(result["surprise"])
        self.assertIn("python_source_lines", result["surprise"]["changes"])
        self.assertIn("python_source_lines", result["question"]["text"])
        self.assertGreater(result["metrics"]["perception"], 0.0)

    def test_v1_state_migrates_without_erasing_history(self) -> None:
        legacy = {
            "schema_version": 1,
            "cycles": 2,
            "generation": 2,
            "episodes": [{"id": "E000001"}],
            "questions": [],
            "experiments": [],
            "reflections": [],
            "accepted_changes": [],
            "concept_counts": {},
            "metrics": {"continuity": 1.0},
            "self_model": {
                "capabilities": [],
                "limitations": ["No external perception unless observations are supplied."],
            },
        }
        self.state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["episodes"][0]["id"], "E000001")
        self.assertIn("perception", migrated["metrics"])
        self.assertIn("environment_snapshots", migrated)

    def test_repository_sensor_is_safe_outside_git(self) -> None:
        snapshot = repository_snapshot(self.tmp.name)

        self.assertEqual(snapshot["sensor"], "repository-v1")
        self.assertFalse(snapshot["git_available"])
        self.assertIn("fingerprint", snapshot)


if __name__ == "__main__":
    unittest.main()
