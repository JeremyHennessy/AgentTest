from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agenttest.cognition import StaticCognitionProvider
from agenttest.core import AgentCore
from agenttest.evolution import propose_growth_experiment
from agenttest.perception import repository_snapshot
from agenttest.state import SCHEMA_VERSION, StateStore


def observation(lines: int = 100) -> dict[str, object]:
    return {
        "sensor": "test",
        "branch": "main",
        "tracked_files": 10,
        "python_files": 4,
        "python_source_lines": lines,
        "test_files": 1,
        "working_tree_clean": True,
    }


def candidate(evidence_ref: str) -> dict[str, object]:
    return {
        "question": "Can the observed repository state distinguish stability from change?",
        "hypothesis": "A second identical observation will support short-horizon stability.",
        "experiment": "Observe the same measured repository fields on the next cycle.",
        "falsification": "Any comparable field changing falsifies short-horizon stability.",
        "predicted_observation": "The comparable repository fields remain unchanged.",
        "evidence_refs": [evidence_ref],
        "confidence": 0.6,
        "novelty_note": "This converts an observation into an explicit falsifiable candidate.",
    }


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
        self.core.cycle(observation=observation(100))
        result = self.core.cycle(observation=observation(120))

        self.assertIsNotNone(result["surprise"])
        self.assertIn("python_source_lines", result["surprise"]["changes"])
        self.assertIn("python_source_lines", result["question"]["text"])
        self.assertGreater(result["metrics"]["perception"], 0.0)

    def test_prediction_is_closed_on_next_observation(self) -> None:
        first = self.core.cycle(observation=observation(100))
        self.assertEqual(first["prediction"]["status"], "pending")

        second = self.core.cycle(observation=observation(100))
        state = self.store.load()

        self.assertEqual(second["prediction_result"]["status"], "confirmed")
        self.assertEqual(state["predictions"][0]["status"], "confirmed")
        self.assertEqual(state["predictions"][1]["status"], "pending")
        self.assertGreater(second["metrics"]["learning"], 0.0)

    def test_prediction_error_changes_intention(self) -> None:
        self.core.cycle(observation=observation(100))
        result = self.core.cycle(observation=observation(130))

        self.assertEqual(result["prediction_result"]["status"], "violated")
        self.assertEqual(result["drives"]["prediction_error"], 1.0)
        self.assertEqual(result["intention"]["kind"], "explain_change")

    def test_evidence_hunger_reuses_pending_experiment(self) -> None:
        first = self.core.cycle()
        second = self.core.cycle()
        state = self.store.load()

        self.assertEqual(first["experiment"]["id"], second["experiment"]["id"])
        self.assertEqual(len(state["experiments"]), 1)
        self.assertEqual(second["intention"]["kind"], "resolve_pending_evidence")

    def test_valid_cognition_can_drive_question_and_experiment(self) -> None:
        provider = StaticCognitionProvider(candidate("E000001"))
        result = self.core.cycle(
            "grounded stimulus",
            cognition=True,
            cognition_provider=provider,
        )
        state = self.store.load()

        self.assertEqual(result["cognition_event"]["status"], "accepted")
        self.assertEqual(result["question"]["text"], candidate("E000001")["question"])
        self.assertEqual(
            result["experiment"]["cognition_candidate_id"],
            result["thought"]["id"],
        )
        self.assertEqual(
            result["experiment"]["hypothesis"],
            candidate("E000001")["hypothesis"],
        )
        self.assertGreater(state["metrics"]["cognition"], 0.0)

    def test_unknown_cognition_evidence_is_rejected(self) -> None:
        provider = StaticCognitionProvider(candidate("E999999"))
        result = self.core.cycle(
            "grounded stimulus",
            cognition=True,
            cognition_provider=provider,
        )
        state = self.store.load()

        self.assertEqual(result["cognition_event"]["status"], "rejected")
        self.assertIsNone(result["thought"])
        self.assertEqual(len(state["cognition_candidates"]), 0)
        self.assertNotEqual(result["question"]["text"], candidate("E999999")["question"])

    def test_missing_cognition_provider_fails_closed(self) -> None:
        result = self.core.cycle("stimulus", cognition=True, cognition_provider=None)

        self.assertEqual(result["cognition_event"]["status"], "unavailable")
        self.assertIsNone(result["thought"])

    def test_v3_state_migrates_without_erasing_history(self) -> None:
        legacy = {
            "schema_version": 3,
            "cycles": 2,
            "generation": 2,
            "episodes": [{"id": "E000001"}],
            "environment_snapshots": [],
            "surprises": [],
            "predictions": [],
            "intentions": [],
            "drives": {},
            "questions": [],
            "experiments": [],
            "reflections": [],
            "accepted_changes": [],
            "concept_counts": {},
            "metrics": {"continuity": 1.0},
            "self_model": {"capabilities": [], "limitations": []},
        }
        self.state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["episodes"][0]["id"], "E000001")
        self.assertIn("cognition", migrated["metrics"])
        self.assertIn("cognition_events", migrated)
        self.assertIn("cognition_candidates", migrated)

    def test_repository_sensor_is_safe_outside_git(self) -> None:
        snapshot = repository_snapshot(self.tmp.name)

        self.assertEqual(snapshot["sensor"], "repository-v1")
        self.assertFalse(snapshot["git_available"])
        self.assertIn("fingerprint", snapshot)


if __name__ == "__main__":
    unittest.main()
