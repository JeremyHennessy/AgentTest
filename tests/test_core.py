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
from agenttest.semantic import retrieve_semantic_memory
from agenttest.state import SCHEMA_VERSION, StateStore
from agenttest.world import current_world_claims


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
        claims = current_world_claims(state)
        self.assertTrue(
            any(
                claim["subject"] == f"experiment.{experiment_id}"
                and claim["predicate"] == "outcome"
                for claim in claims
            )
        )

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

    def test_semantic_memory_consolidates_once_with_provenance(self) -> None:
        self.core.cycle("alpha beta")
        first = self.store.load()
        self.assertEqual(first["semantic_memory"]["concepts"]["alpha"]["count"], 1)
        self.assertEqual(
            first["semantic_memory"]["concepts"]["alpha"]["episode_refs"],
            ["E000001"],
        )
        self.assertEqual(
            first["semantic_memory"]["associations"]["alpha|beta"]["count"],
            1,
        )

        self.core.cycle("alpha beta")
        second = self.store.load()
        self.assertEqual(second["semantic_memory"]["concepts"]["alpha"]["count"], 2)
        self.assertEqual(len(second["episodes"]), 2)
        retrieved = retrieve_semantic_memory(second, "alpha", limit=1)
        self.assertEqual(retrieved[0]["concept"], "alpha")
        self.assertEqual(retrieved[0]["count"], 2)

    def test_world_claim_preserves_superseded_value(self) -> None:
        self.core.cycle(observation=observation(100))
        self.core.cycle(observation=observation(120))
        state = self.store.load()

        matching = [
            claim
            for claim in state["world_model"]["claims"]
            if claim["subject"] == "repository"
            and claim["predicate"] == "python_source_lines"
        ]
        self.assertEqual(len(matching), 2)
        old = next(claim for claim in matching if claim["value"] == 100)
        new = next(claim for claim in matching if claim["value"] == 120)
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], new["id"])
        self.assertEqual(new["supersedes"], old["id"])
        self.assertEqual(new["status"], "current")
        self.assertTrue(new["evidence_refs"])

    def test_world_claim_can_ground_cognition(self) -> None:
        provider = StaticCognitionProvider(candidate("W000001"))
        result = self.core.cycle(
            observation=observation(100),
            cognition=True,
            cognition_provider=provider,
        )

        self.assertEqual(result["cognition_event"]["status"], "accepted")
        self.assertEqual(result["thought"]["evidence_refs"], ["W000001"])

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

    def test_v4_state_migrates_without_erasing_history(self) -> None:
        legacy = {
            "schema_version": 4,
            "cycles": 2,
            "generation": 2,
            "episodes": [{"id": "E000001", "cycle": 1, "concepts": ["alpha"]}],
            "environment_snapshots": [],
            "surprises": [],
            "predictions": [],
            "intentions": [],
            "drives": {},
            "cognition_events": [],
            "cognition_candidates": [],
            "questions": [],
            "experiments": [],
            "reflections": [],
            "accepted_changes": [],
            "concept_counts": {"alpha": 1},
            "metrics": {"continuity": 1.0},
            "self_model": {"capabilities": [], "limitations": []},
        }
        self.state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["episodes"][0]["id"], "E000001")
        self.assertIn("semantic_memory", migrated)
        self.assertIn("world_model", migrated)
        self.assertIn("semantic_memory", migrated["metrics"])
        self.assertIn("world_model", migrated["metrics"])

    def test_repository_sensor_is_safe_outside_git(self) -> None:
        snapshot = repository_snapshot(self.tmp.name)

        self.assertEqual(snapshot["sensor"], "repository-v1")
        self.assertFalse(snapshot["git_available"])
        self.assertIn("fingerprint", snapshot)

    def test_change_manifest_rejects_protected_evaluator_path(self) -> None:
        from agenttest.change_control import make_change_manifest

        self.core.cycle("change evidence")
        state = self.store.load()
        with self.assertRaises(ValueError):
            make_change_manifest(
                state,
                title="Weaken evaluator",
                target_dimension="adaptation",
                files=["scripts/preservation_eval.py"],
                hypothesis="Changing the evaluator would raise apparent performance.",
                expected_effect="Higher apparent score.",
                test_plan="Run checks.",
                falsification="No apparent score change.",
                rollback="Revert the commit.",
                evidence_refs=["E000001"],
            )

    def test_change_manifest_requires_existing_evidence(self) -> None:
        from agenttest.change_control import make_change_manifest

        self.core.cycle("change evidence")
        state = self.store.load()
        with self.assertRaises(ValueError):
            make_change_manifest(
                state,
                title="Unsupported change",
                target_dimension="adaptation",
                files=["src/agenttest/core.py"],
                hypothesis="A code change may help.",
                expected_effect="Improved adaptation.",
                test_plan="Run preservation checks.",
                falsification="Adaptation does not improve.",
                rollback="Revert the commit.",
                evidence_refs=["E999999"],
            )

    def test_valid_change_manifest_records_baseline_and_rollback(self) -> None:
        from agenttest.change_control import make_change_manifest

        self.core.cycle("change evidence")
        state = self.store.load()
        manifest = make_change_manifest(
            state,
            title="Candidate reversible change",
            target_dimension="adaptation",
            files=["src/agenttest/core.py"],
            hypothesis="A bounded change may improve adaptation.",
            expected_effect="Increase evidence for adaptation without regression.",
            test_plan="Run unit tests and the behavioral preservation gate.",
            falsification="Any preserved capability regresses or adaptation evidence does not improve.",
            rollback="Revert the candidate commit.",
            evidence_refs=["E000001"],
        )
        self.assertEqual(manifest["status"], "proposed")
        self.assertEqual(manifest["target_dimension"], "adaptation")
        self.assertIn("scripts/preservation_eval.py", manifest["protected_paths"])
        self.assertEqual(manifest["evidence_refs"], ["E000001"])

    def test_self_change_proposal_is_grounded_and_reused(self) -> None:
        from agenttest.change_control import validate_change_manifest
        from agenttest.self_proposal import propose_self_change

        self.core.cycle(observation=observation(100))
        self.core.cycle(observation=observation(120))
        state = self.store.load()
        adaptation_before = state["metrics"]["adaptation"]

        proposal, created = propose_self_change(state)
        self.assertTrue(created)
        self.assertIsNotNone(proposal)
        valid, reason = validate_change_manifest(proposal, state)
        self.assertTrue(valid, reason)
        self.assertTrue(proposal["evidence_refs"])
        self.assertNotEqual(proposal["target_dimension"], "cognition")
        self.assertEqual(state["metrics"]["adaptation"], adaptation_before)

        second, second_created = propose_self_change(state)
        self.assertFalse(second_created)
        self.assertEqual(second["id"], proposal["id"])
        self.assertEqual(len(state["change_proposals"]), 1)

    def test_missing_cognition_provider_is_not_treated_as_code_defect(self) -> None:
        from agenttest.self_proposal import select_change_target

        self.core.cycle("evidence")
        state = self.store.load()
        state["metrics"].update(
            {
                "cognition": 0.0,
                "learning": 0.4,
                "reflection": 0.4,
                "self_model": 0.9,
                "agency": 0.9,
                "curiosity": 0.9,
                "reproducibility": 0.9,
                "perception": 1.0,
                "semantic_memory": 1.0,
                "world_model": 1.0,
                "memory": 1.0,
                "continuity": 1.0,
                "open_endedness": 1.0,
            }
        )
        state["cognition_events"] = [
            {
                "id": "G000001",
                "status": "unavailable",
                "rejection_reason": "no cognition provider configured",
            }
        ]

        selected = select_change_target(state)
        self.assertIsNotNone(selected)
        self.assertNotEqual(selected["dimension"], "cognition")

    def test_change_manifest_protects_growth_and_change_control(self) -> None:
        from agenttest.change_control import make_change_manifest

        self.core.cycle("governance evidence")
        state = self.store.load()
        for path in (
            ".github/workflows/growth.yml",
            "src/agenttest/change_control.py",
        ):
            with self.assertRaises(ValueError):
                make_change_manifest(
                    state,
                    title="Governance mutation",
                    target_dimension="adaptation",
                    files=[path],
                    hypothesis="Changing governance might alter behavior.",
                    expected_effect="Unknown.",
                    test_plan="Run tests.",
                    falsification="Any regression.",
                    rollback="Revert.",
                    evidence_refs=["E000001"],
                )

    def test_v5_state_migrates_change_proposals_without_erasing_history(self) -> None:
        legacy = {
            "schema_version": 5,
            "cycles": 4,
            "generation": 4,
            "episodes": [{"id": "E000001", "cycle": 1, "concepts": ["alpha"]}],
            "semantic_memory": {
                "last_episode_index": 1,
                "concepts": {},
                "associations": {},
            },
            "environment_snapshots": [],
            "surprises": [],
            "predictions": [],
            "intentions": [],
            "drives": {},
            "world_model": {
                "claims": [],
                "current": {},
                "last_snapshot_index": 0,
                "seen_prediction_status": {},
                "seen_experiment_status": {},
            },
            "cognition_events": [],
            "cognition_candidates": [],
            "questions": [],
            "experiments": [],
            "reflections": [],
            "accepted_changes": [],
            "concept_counts": {"alpha": 1},
            "metrics": {"continuity": 1.0},
            "self_model": {"capabilities": [], "limitations": []},
        }
        self.state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["cycles"], 4)
        self.assertEqual(migrated["episodes"][0]["id"], "E000001")
        self.assertIn("change_proposals", migrated)
        self.assertEqual(migrated["change_proposals"], [])

    def test_reproducibility_proposal_is_measurement_gap_without_direct_failure(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal

        self.core.cycle("replay evidence context")
        state = self.store.load()
        proposal = make_change_manifest(
            state,
            title="Add deterministic cycle replay checks",
            target_dimension="reproducibility",
            files=["src/agenttest/replay.py", "tests/test_core.py"],
            hypothesis="Replay measurement can reveal drift.",
            expected_effect="Equivalent controlled cycles can be compared.",
            test_plan="Run a non-mutating replay comparison.",
            falsification="Replay cannot be measured reproducibly.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M000001", "source": "test", "created_cycle": 1})
        state["change_proposals"].append(proposal)

        review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertEqual(review["verdict"], "measurement_gap")
        self.assertEqual(review["patch_authority"], "diagnostic_only")
        self.assertEqual(proposal["status"], "reviewed_measurement_gap")

    def test_direct_replay_divergence_supports_reproducibility_problem(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal

        self.core.cycle("replay evidence context")
        state = self.store.load()
        proposal = make_change_manifest(
            state,
            title="Add deterministic cycle replay checks",
            target_dimension="reproducibility",
            files=["src/agenttest/replay.py", "tests/test_core.py"],
            hypothesis="Replay measurement can reveal drift.",
            expected_effect="Equivalent controlled cycles can be compared.",
            test_plan="Run a non-mutating replay comparison.",
            falsification="Replay cannot be measured reproducibly.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M000001", "source": "test", "created_cycle": 1})
        state["change_proposals"].append(proposal)
        state["proposal_diagnostics"].append(
            {
                "id": "D000001",
                "proposal_id": "M000001",
                "kind": "deterministic_replay",
                "status": "completed",
                "outcome": "divergent",
            }
        )

        review, _ = review_change_proposal(state, proposal)

        self.assertEqual(review["verdict"], "supported_problem")
        self.assertEqual(review["patch_authority"], "candidate_allowed")
        self.assertEqual(review["direct_diagnostic_id"], "D000001")
        self.assertEqual(proposal["status"], "reviewed_supported_problem")

    def test_review_is_reused_and_blocks_proposal_proliferation(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal
        from agenttest.self_proposal import propose_self_change

        self.core.cycle("replay evidence context")
        state = self.store.load()
        proposal = make_change_manifest(
            state,
            title="Add deterministic cycle replay checks",
            target_dimension="reproducibility",
            files=["src/agenttest/replay.py", "tests/test_core.py"],
            hypothesis="Replay measurement can reveal drift.",
            expected_effect="Equivalent controlled cycles can be compared.",
            test_plan="Run a non-mutating replay comparison.",
            falsification="Replay cannot be measured reproducibly.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M000001", "source": "test", "created_cycle": 1})
        state["change_proposals"].append(proposal)

        first, first_created = review_change_proposal(state, proposal)
        second, second_created = review_change_proposal(state, proposal)
        reused_proposal, proposal_created = propose_self_change(state)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first["id"], second["id"])
        self.assertFalse(proposal_created)
        self.assertEqual(reused_proposal["id"], "M000001")
        self.assertEqual(len(state["change_proposals"]), 1)

    def test_learning_gap_can_be_supported_by_later_unclosed_evidence(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal

        first = self.core.cycle(observation=observation(100))
        self.core.cycle(observation=observation(120))
        state = self.store.load()
        proposal = make_change_manifest(
            state,
            title="Close measurable experiment loops",
            target_dimension="learning",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Later measured evidence can close eligible experiments.",
            expected_effect="Matching pending experiments close with provenance.",
            test_plan="Use later evaluated prediction evidence.",
            falsification="No matching experiment closes or an unrelated one closes.",
            rollback="Revert.",
            evidence_refs=[first["experiment"]["id"], "P000001"],
        )
        proposal.update({"id": "M000001", "source": "test", "created_cycle": 2})
        state["change_proposals"].append(proposal)

        review, _ = review_change_proposal(state, proposal)

        self.assertEqual(review["verdict"], "supported_problem")
        self.assertEqual(review["patch_authority"], "candidate_allowed")
        self.assertTrue(review["direct_evidence_refs"])

    def test_v6_state_migrates_proposal_review_state_without_history_loss(self) -> None:
        legacy = {
            "schema_version": 6,
            "cycles": 6,
            "generation": 6,
            "episodes": [{"id": "E000001", "cycle": 1, "concepts": ["alpha"]}],
            "semantic_memory": {
                "last_episode_index": 1,
                "concepts": {},
                "associations": {},
            },
            "environment_snapshots": [],
            "surprises": [],
            "predictions": [],
            "intentions": [],
            "drives": {},
            "world_model": {
                "claims": [],
                "current": {},
                "last_snapshot_index": 0,
                "seen_prediction_status": {},
                "seen_experiment_status": {},
            },
            "cognition_events": [],
            "cognition_candidates": [],
            "questions": [],
            "experiments": [],
            "change_proposals": [{"id": "M000001", "status": "proposed"}],
            "reflections": [],
            "accepted_changes": [],
            "concept_counts": {"alpha": 1},
            "metrics": {"continuity": 1.0},
            "self_model": {"capabilities": [], "limitations": []},
        }
        self.state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["cycles"], 6)
        self.assertEqual(migrated["change_proposals"][0]["id"], "M000001")
        self.assertEqual(migrated["proposal_reviews"], [])
        self.assertEqual(migrated["proposal_diagnostics"], [])


if __name__ == "__main__":
    unittest.main()
