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
from agenttest.state import CAPABILITY_CATALOG, LIMITATION_CATALOG, SCHEMA_VERSION, StateStore, initial_state
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

        self.assertEqual(snapshot["sensor"], "repository-v2")
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
        experiment = next(
            item for item in state["experiments"]
            if item["id"] == first["experiment"]["id"]
        )
        experiment["readiness"] = "evidence_ready"
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

    def test_verified_replay_diagnostic_closes_clean_measurement_gap(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.diagnostics import run_proposal_diagnostic
        from agenttest.proposal_review import review_change_proposal

        self.core.cycle("replay gap evidence")
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

        first_review, first_created = review_change_proposal(state, proposal)
        self.assertTrue(first_created)
        self.assertEqual(first_review["verdict"], "measurement_gap")
        self.assertEqual(first_review["patch_authority"], "diagnostic_only")

        diagnostic, diagnostic_created = run_proposal_diagnostic(
            state,
            proposal,
            first_review,
        )
        self.assertTrue(diagnostic_created)
        self.assertEqual(diagnostic["status"], "completed")
        self.assertEqual(diagnostic["outcome"], "stable")
        self.assertFalse(diagnostic["source_state_mutated"])
        self.assertEqual(diagnostic["mutation_scope"], "isolated_temp_state")
        self.assertIsNone(diagnostic["result"]["first_difference"])

        second_review, second_created = review_change_proposal(state, proposal)
        self.assertTrue(second_created)
        self.assertEqual(second_review["verdict"], "no_problem_observed")
        self.assertEqual(second_review["patch_authority"], "none")
        self.assertEqual(
            second_review["direct_diagnostic_id"],
            diagnostic["id"],
        )
        self.assertEqual(proposal["status"], "closed_no_problem_observed")

        self.store.save(state)
        result = self.core.cycle("post diagnostic evidence")
        self.assertEqual(result["metrics"]["reproducibility"], 1.0)

    def test_diagnostic_and_review_authority_paths_are_protected(self) -> None:
        from agenttest.change_control import PROTECTED_PATHS

        for path in (
            "src/agenttest/change_control.py",
            "src/agenttest/proposal_review.py",
            "src/agenttest/self_proposal.py",
            "src/agenttest/diagnostics.py",
            "src/agenttest/diagnostic_replay.py",
        ):
            self.assertIn(path, PROTECTED_PATHS)

    def test_replay_divergence_would_authorize_candidate_not_diagnostic_code(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal

        self.core.cycle("replay divergence evidence")
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
        first_review, _ = review_change_proposal(state, proposal)

        state["proposal_diagnostics"].append(
            {
                "id": "D000001",
                "proposal_id": proposal["id"],
                "review_id": first_review["id"],
                "target_dimension": "reproducibility",
                "kind": "deterministic_replay",
                "diagnostic_version": "deterministic-replay-v1",
                "status": "completed",
                "outcome": "divergent",
                "source_state_mutated": False,
            }
        )
        second_review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertEqual(second_review["verdict"], "supported_problem")
        self.assertEqual(second_review["patch_authority"], "candidate_allowed")
        self.assertEqual(second_review["direct_diagnostic_id"], "D000001")

    def test_repository_intervention_invalidates_prediction_without_error_drive(self) -> None:
        first_observation = observation(100)
        first_observation["baseline_fingerprint"] = "baseline-a"
        second_observation = observation(120)
        second_observation["baseline_fingerprint"] = "baseline-b"

        self.core.cycle(observation=first_observation)
        result = self.core.cycle(observation=second_observation)

        self.assertEqual(
            result["prediction_result"]["status"],
            "invalidated_by_intervention",
        )
        self.assertEqual(result["drives"]["prediction_error"], 0.0)
        self.assertNotEqual(result["intention"]["kind"], "explain_change")
        state = self.store.load()
        self.assertEqual(
            state["reflections"][-1]["outcome"],
            "invalidated_by_intervention",
        )

    def test_same_baseline_unexpected_change_still_violates_prediction(self) -> None:
        first_observation = observation(100)
        first_observation["baseline_fingerprint"] = "baseline-a"
        second_observation = observation(100)
        second_observation["baseline_fingerprint"] = "baseline-a"
        second_observation["working_tree_clean"] = False

        self.core.cycle(observation=first_observation)
        result = self.core.cycle(observation=second_observation)

        self.assertEqual(result["prediction_result"]["status"], "violated")
        self.assertEqual(result["drives"]["prediction_error"], 1.0)
        self.assertEqual(result["intention"]["kind"], "explain_change")

    def test_baseline_fingerprint_excludes_persistent_state_files(self) -> None:
        from agenttest.perception import baseline_content_fingerprint

        root = Path(self.tmp.name)
        (root / "src").mkdir()
        (root / "state").mkdir()
        (root / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")
        (root / "state" / "organism.json").write_text('{"cycle": 1}\n', encoding="utf-8")
        tracked = ["src/module.py", "state/organism.json"]

        first = baseline_content_fingerprint(root, tracked)
        (root / "state" / "organism.json").write_text('{"cycle": 2}\n', encoding="utf-8")
        second = baseline_content_fingerprint(root, tracked)
        self.assertEqual(first, second)

        (root / "src" / "module.py").write_text("value = 2\n", encoding="utf-8")
        third = baseline_content_fingerprint(root, tracked)
        self.assertNotEqual(second, third)

    def test_self_model_grounding_diagnostic_supports_traceability_problem(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.diagnostics import run_proposal_diagnostic
        from agenttest.proposal_review import review_change_proposal

        self.core.cycle("self model evidence")
        state = self.store.load()
        # The diagnostic must still detect an explicit grounding defect even
        # after production begins calibrating claims by default.
        state["self_model"]["capability_claims"] = {}
        proposal = make_change_manifest(
            state,
            title="Calibrate self-model claims against behavioral checks",
            target_dimension="self_model",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Explicit claim calibration reduces unsupported self-description.",
            expected_effect="Capabilities distinguish supported and unverified status.",
            test_plan="Run the verified self-model grounding diagnostic.",
            falsification="Every capability is already explicitly calibrated.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M000001", "source": "test", "created_cycle": 1})
        state["change_proposals"].append(proposal)

        first_review, created = review_change_proposal(state, proposal)
        self.assertTrue(created)
        self.assertEqual(first_review["verdict"], "measurement_gap")
        self.assertEqual(first_review["patch_authority"], "diagnostic_only")

        diagnostic, diagnostic_created = run_proposal_diagnostic(
            state,
            proposal,
            first_review,
        )
        self.assertTrue(diagnostic_created)
        self.assertEqual(diagnostic["kind"], "self_model_grounding")
        self.assertEqual(diagnostic["outcome"], "grounding_gap")
        self.assertFalse(diagnostic["source_state_mutated"])
        self.assertGreater(
            len(diagnostic["result"]["missing_claims"]),
            0,
        )

        second_review, second_created = review_change_proposal(state, proposal)
        self.assertTrue(second_created)
        self.assertEqual(second_review["verdict"], "supported_problem")
        self.assertEqual(second_review["patch_authority"], "candidate_allowed")
        self.assertEqual(
            second_review["direct_diagnostic_id"],
            diagnostic["id"],
        )
        self.assertEqual(proposal["status"], "reviewed_supported_problem")

    def test_self_model_grounding_diagnostic_accepts_explicit_uncertainty(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.diagnostics import run_proposal_diagnostic
        from agenttest.proposal_review import review_change_proposal

        self.core.cycle("self model evidence")
        state = self.store.load()
        state["self_model"]["capability_claims"] = {
            capability: {
                "status": "unverified",
                "evidence_refs": [],
                "reason": "No explicit behavior evidence is attached yet.",
            }
            for capability in state["self_model"]["capabilities"]
        }
        proposal = make_change_manifest(
            state,
            title="Calibrate self-model claims against behavioral checks",
            target_dimension="self_model",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Explicit claim calibration reduces unsupported self-description.",
            expected_effect="Capabilities distinguish supported and unverified status.",
            test_plan="Run the verified self-model grounding diagnostic.",
            falsification="Every capability is already explicitly calibrated.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M000001", "source": "test", "created_cycle": 1})
        state["change_proposals"].append(proposal)

        first_review, _ = review_change_proposal(state, proposal)
        diagnostic, diagnostic_created = run_proposal_diagnostic(
            state,
            proposal,
            first_review,
        )
        self.assertTrue(diagnostic_created)
        self.assertEqual(diagnostic["outcome"], "grounded")
        self.assertEqual(diagnostic["result"]["coverage"], 1.0)
        self.assertEqual(diagnostic["result"]["missing_claims"], [])
        self.assertEqual(diagnostic["result"]["invalid_claims"], [])

        second_review, second_created = review_change_proposal(state, proposal)
        self.assertTrue(second_created)
        self.assertEqual(second_review["verdict"], "no_problem_observed")
        self.assertEqual(second_review["patch_authority"], "none")
        self.assertEqual(proposal["status"], "closed_no_problem_observed")

    def test_self_model_diagnostic_authority_is_protected(self) -> None:
        from agenttest.change_control import PROTECTED_PATHS

        self.assertIn(
            "src/agenttest/diagnostic_self_model.py",
            PROTECTED_PATHS,
        )


    def test_runtime_self_model_calibration_closes_grounding_gap(self) -> None:
        from agenttest.diagnostic_self_model import evaluate_self_model_grounding

        result = self.core.cycle(
            "self model calibration evidence",
            observation=observation(100),
        )
        state = self.store.load()
        diagnostic = evaluate_self_model_grounding(state)

        self.assertEqual(diagnostic["outcome"], "grounded")
        self.assertEqual(diagnostic["coverage"], 1.0)
        self.assertEqual(state["metrics"]["self_model"], 1.0)
        self.assertEqual(result["self_model_calibration"]["coverage"], 1.0)

        claims = state["self_model"]["capability_claims"]
        statuses = {claim["status"] for claim in claims.values()}
        self.assertIn("observed", statuses)
        self.assertIn("unverified", statuses)

        for claim in claims.values():
            if claim["status"] in {"observed", "verified"}:
                self.assertTrue(claim["evidence_refs"])
            else:
                self.assertEqual(claim["status"], "unverified")
                self.assertTrue(claim["reason"].strip())

    def test_self_model_does_not_treat_unavailable_cognition_as_verified(self) -> None:
        self.core.cycle(
            "provider unavailable calibration",
            cognition=True,
            cognition_provider=None,
        )
        state = self.store.load()
        claim = state["self_model"]["capability_claims"][
            "validated boundary for optional model-generated candidate thoughts"
        ]

        self.assertEqual(claim["status"], "unverified")
        self.assertEqual(claim["evidence_refs"], [])
        self.assertIn("No accepted live cognition candidate", claim["reason"])

    def test_accepted_cognition_candidate_can_ground_cognition_claim(self) -> None:
        provider = StaticCognitionProvider(candidate("E000001"))
        self.core.cycle(
            "grounded stimulus",
            cognition=True,
            cognition_provider=provider,
        )
        state = self.store.load()
        claim = state["self_model"]["capability_claims"][
            "validated boundary for optional model-generated candidate thoughts"
        ]

        self.assertEqual(claim["status"], "observed")
        self.assertTrue(claim["evidence_refs"])
        self.assertIn("C000001", claim["evidence_refs"])

    def test_unknown_future_self_model_capability_defaults_to_unverified(self) -> None:
        state = self.store.load()
        state["self_model"]["capabilities"].append(
            "future capability without calibration rule"
        )
        self.store.save(state)

        self.core.cycle("future capability evidence")
        reloaded = self.store.load()
        claim = reloaded["self_model"]["capability_claims"][
            "future capability without calibration rule"
        ]

        self.assertEqual(claim["status"], "unverified")
        self.assertEqual(claim["evidence_refs"], [])
        self.assertIn("No explicit calibration rule", claim["reason"])


    def test_canonical_capability_catalog_is_unique_and_used_by_initial_state(self) -> None:
        state = initial_state()

        self.assertEqual(len(CAPABILITY_CATALOG), len(set(CAPABILITY_CATALOG)))
        self.assertEqual(len(LIMITATION_CATALOG), len(set(LIMITATION_CATALOG)))
        self.assertEqual(
            state["self_model"]["capabilities"],
            list(CAPABILITY_CATALOG),
        )
        self.assertEqual(
            state["self_model"]["limitations"],
            list(LIMITATION_CATALOG),
        )
        self.assertIn(
            "baseline-scoped diagnostic re-evaluation after interventions",
            CAPABILITY_CATALOG,
        )
        self.assertIn(
            "evidence-grounded self-model calibration with explicit uncertainty",
            CAPABILITY_CATALOG,
        )

    def test_state_migration_deduplicates_and_adds_canonical_self_model_entries(self) -> None:
        legacy = {
            "schema_version": 10,
            "cycles": 3,
            "generation": 3,
            "self_model": {
                "capabilities": [
                    "persistent structured state",
                    "persistent structured state",
                    "custom experimental capability",
                ],
                "limitations": [
                    "Custom limitation.",
                    "Custom limitation.",
                ],
            },
            "metrics": {},
        }
        self.state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()
        capabilities = migrated["self_model"]["capabilities"]
        limitations = migrated["self_model"]["limitations"]

        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(len(capabilities), len(set(capabilities)))
        self.assertEqual(len(limitations), len(set(limitations)))
        self.assertIn("custom experimental capability", capabilities)
        self.assertIn("Custom limitation.", limitations)
        for capability in CAPABILITY_CATALOG:
            self.assertIn(capability, capabilities)
        for limitation in LIMITATION_CATALOG:
            self.assertIn(limitation, limitations)


    def test_inquiry_family_diagnostic_detects_paraphrase_churn_without_mutation(self) -> None:
        from agenttest.diagnostic_inquiry import evaluate_inquiry_families

        state = self.store.load()
        state["cycles"] = 8
        state["metrics"]["open_endedness"] = 1.0
        state["questions"] = [
            {
                "id": f"Q{index:06d}",
                "text": (
                    f"What caused repository python_files to change from {index} "
                    f"to {index + 1}, and did that change alter a verified capability?"
                ),
                "status": "open",
            }
            for index in range(1, 7)
        ]
        state["questions"].extend(
            [
                {
                    "id": "Q000007",
                    "text": "What evidence would distinguish memory from stored history?",
                    "status": "open",
                },
                {
                    "id": "Q000008",
                    "text": "Which prediction failed after an unexpected observation?",
                    "status": "open",
                },
            ]
        )
        before = json.dumps(state, sort_keys=True)

        diagnostic = evaluate_inquiry_families(state)

        self.assertEqual(diagnostic["outcome"], "paraphrase_churn")
        self.assertGreaterEqual(diagnostic["largest_family_size"], 6)
        self.assertGreaterEqual(diagnostic["duplicate_pressure"], 0.5)
        self.assertGreater(diagnostic["metric_gap"], 0.05)
        self.assertEqual(diagnostic["metric_status"], "inflated")
        self.assertFalse(diagnostic["source_state_mutated"])
        self.assertEqual(before, json.dumps(state, sort_keys=True))

    def test_inquiry_family_diagnostic_accepts_distinct_question_families(self) -> None:
        from agenttest.diagnostic_inquiry import evaluate_inquiry_families

        state = self.store.load()
        state["cycles"] = 4
        state["metrics"]["open_endedness"] = 1.0
        state["questions"] = [
            {
                "id": "Q000001",
                "text": "What evidence would demonstrate state persistence after restart?",
                "status": "open",
            },
            {
                "id": "Q000002",
                "text": "Which observation would falsify the current repository prediction?",
                "status": "open",
            },
            {
                "id": "Q000003",
                "text": "How should semantic memory preserve episode provenance?",
                "status": "open",
            },
            {
                "id": "Q000004",
                "text": "Can a proposed code change preserve every verified behavior?",
                "status": "open",
            },
        ]

        diagnostic = evaluate_inquiry_families(state)

        self.assertEqual(diagnostic["outcome"], "diverse")
        self.assertEqual(diagnostic["largest_family_size"], 1)
        self.assertEqual(diagnostic["duplicate_pressure"], 0.0)

    def test_open_endedness_proposal_requires_and_uses_inquiry_diagnostic(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.diagnostics import run_proposal_diagnostic
        from agenttest.proposal_review import review_change_proposal

        state = self.store.load()
        state["cycles"] = 6
        state["metrics"]["open_endedness"] = 1.0
        state["questions"] = [
            {
                "id": f"Q{index:06d}",
                "text": (
                    f"What caused repository python_files to change from {index} "
                    f"to {index + 1}, and did that change alter a verified capability?"
                ),
                "status": "open",
            }
            for index in range(1, 7)
        ]
        proposal = make_change_manifest(
            state,
            title="Track inquiry families across cycles",
            target_dimension="open_endedness",
            files=[
                "src/agenttest/core.py",
                "src/agenttest/semantic.py",
                "tests/test_core.py",
            ],
            hypothesis=(
                "Explicit question-family tracking can distinguish genuine branching "
                "from paraphrase churn."
            ),
            expected_effect=(
                "Open-endedness reflects distinct evidence-grounded inquiry families."
            ),
            test_plan="Run the verified inquiry-family diagnostic.",
            falsification="No paraphrase churn is detected.",
            rollback="Revert.",
            evidence_refs=["Q000001", "Q000002", "Q000003"],
        )
        proposal.update(
            {"id": "M000001", "source": "test", "created_cycle": 1}
        )
        state["change_proposals"].append(proposal)

        first_review, first_created = review_change_proposal(state, proposal)
        diagnostic, diagnostic_created = run_proposal_diagnostic(
            state,
            proposal,
            first_review,
        )
        second_review, second_created = review_change_proposal(state, proposal)

        self.assertTrue(first_created)
        self.assertEqual(first_review["verdict"], "needs_evidence")
        self.assertEqual(first_review["patch_authority"], "none")
        self.assertTrue(diagnostic_created)
        self.assertEqual(diagnostic["kind"], "inquiry_family")
        self.assertEqual(diagnostic["outcome"], "paraphrase_churn")
        self.assertFalse(diagnostic["source_state_mutated"])
        self.assertTrue(second_created)
        self.assertEqual(second_review["verdict"], "supported_problem")
        self.assertEqual(second_review["patch_authority"], "candidate_allowed")
        self.assertEqual(second_review["direct_diagnostic_id"], diagnostic["id"])

    def test_inquiry_family_diagnostic_can_recognize_aligned_metric_despite_history(self) -> None:
        from agenttest.diagnostic_inquiry import evaluate_inquiry_families

        state = self.store.load()
        state["cycles"] = 6
        state["questions"] = [
            {
                "id": f"Q{index:06d}",
                "text": (
                    f"What caused repository python_files to change from {index} "
                    f"to {index + 1}, and did that change alter a verified capability?"
                ),
                "status": "open",
            }
            for index in range(1, 7)
        ]
        state["metrics"]["open_endedness"] = 1.0 / 6.0

        diagnostic = evaluate_inquiry_families(state)

        self.assertEqual(diagnostic["outcome"], "paraphrase_churn")
        self.assertEqual(diagnostic["metric_status"], "aligned")
        self.assertAlmostEqual(diagnostic["metric_gap"], 0.0)
        self.assertEqual(diagnostic["family_count"], 1)


    def test_inquiry_family_diagnostic_authority_is_protected(self) -> None:
        from agenttest.change_control import PROTECTED_PATHS

        self.assertIn(
            "src/agenttest/diagnostic_inquiry.py",
            PROTECTED_PATHS,
        )


    def test_runtime_inquiry_metric_collapses_paraphrase_family_without_deleting_history(self) -> None:
        from agenttest.diagnostic_inquiry import evaluate_inquiry_families
        from agenttest.semantic import consolidate_inquiry_families

        state = self.store.load()
        state["cycles"] = 6
        state["questions"] = [
            {
                "id": f"Q{index:06d}",
                "text": (
                    f"What caused repository python_files to change from {index} "
                    f"to {index + 1}, and did that change alter a verified capability?"
                ),
                "status": "open",
            }
            for index in range(1, 7)
        ]
        original_questions = json.loads(json.dumps(state["questions"]))

        summary = consolidate_inquiry_families(state)
        self.core._update_metrics(state)
        diagnostic = evaluate_inquiry_families(state)

        self.assertEqual(summary["question_count"], 6)
        self.assertEqual(summary["family_count"], 1)
        self.assertEqual(summary["open_endedness"], 1.0 / 6.0)
        self.assertEqual(state["metrics"]["open_endedness"], 1.0 / 6.0)
        self.assertEqual(state["questions"], original_questions)
        self.assertEqual(set(summary["question_to_family"].values()), {"F001"})
        self.assertEqual(diagnostic["outcome"], "paraphrase_churn")
        self.assertEqual(diagnostic["metric_status"], "aligned")
        self.assertAlmostEqual(diagnostic["metric_gap"], 0.0)

    def test_runtime_inquiry_metric_preserves_distinct_question_families(self) -> None:
        from agenttest.diagnostic_inquiry import evaluate_inquiry_families
        from agenttest.semantic import consolidate_inquiry_families

        state = self.store.load()
        state["cycles"] = 4
        state["questions"] = [
            {
                "id": "Q000001",
                "text": "What evidence would demonstrate state persistence after restart?",
                "status": "open",
            },
            {
                "id": "Q000002",
                "text": "Which observation would falsify the current repository prediction?",
                "status": "open",
            },
            {
                "id": "Q000003",
                "text": "How should semantic memory preserve episode provenance?",
                "status": "open",
            },
            {
                "id": "Q000004",
                "text": "Can a proposed code change preserve every verified behavior?",
                "status": "open",
            },
        ]

        summary = consolidate_inquiry_families(state)
        self.core._update_metrics(state)
        diagnostic = evaluate_inquiry_families(state)

        self.assertEqual(summary["family_count"], 4)
        self.assertEqual(state["metrics"]["open_endedness"], 1.0)
        self.assertEqual(diagnostic["outcome"], "diverse")
        self.assertEqual(diagnostic["metric_status"], "aligned")
        self.assertAlmostEqual(diagnostic["metric_gap"], 0.0)

    def test_cycle_persists_inquiry_family_summary(self) -> None:
        result = self.core.cycle("inquiry family runtime evidence")
        state = self.store.load()

        self.assertIn("inquiry_update", result)
        self.assertIn("inquiry_families", state["semantic_memory"])
        summary = state["semantic_memory"]["inquiry_families"]
        self.assertEqual(summary["updated_cycle"], state["cycles"])
        self.assertEqual(summary["question_count"], len(state["questions"]))
        self.assertEqual(
            state["metrics"]["open_endedness"],
            summary["open_endedness"],
        )


    def test_interaction_persists_turn_and_links_source_episode(self) -> None:
        from agenttest.interaction import interact

        result = interact(
            "How do you remember what I say?",
            store=self.store,
        )
        state = self.store.load()

        self.assertEqual(len(state["interactions"]), 1)
        interaction = state["interactions"][0]
        self.assertEqual(interaction["id"], "H000001")
        self.assertEqual(result["interaction"]["id"], interaction["id"])
        self.assertIsNotNone(interaction["input_episode_id"])
        episode = next(
            item
            for item in state["episodes"]
            if item["id"] == interaction["input_episode_id"]
        )
        self.assertEqual(episode["source"], "human_interaction")
        self.assertEqual(episode["interaction_id"], interaction["id"])
        self.assertEqual(interaction["question_id"], result["current"]["question"]["id"])
        self.assertEqual(
            interaction["experiment_id"],
            result["current"]["experiment"]["id"],
        )
        self.assertIn("I recorded your message", result["response_text"])

    def test_interaction_retrieves_prior_memory_before_writing_new_turn(self) -> None:
        from agenttest.interaction import interact

        self.core.cycle("alpha persistence memory evidence")
        result = interact(
            "alpha continuity",
            store=self.store,
        )

        concepts = [
            item["concept"]
            for item in result["memory"]["prior_semantic"]
        ]
        self.assertIn("alpha", concepts)
        self.assertEqual(
            result["interaction"]["prior_memory_concepts"],
            concepts,
        )

    def test_interaction_unavailable_cognition_never_fakes_candidate(self) -> None:
        from agenttest.interaction import interact

        result = interact(
            "What are you thinking about?",
            store=self.store,
            cognition=True,
            cognition_provider=None,
        )

        self.assertEqual(
            result["cognition"]["event"]["status"],
            "unavailable",
        )
        self.assertIsNone(result["cognition"]["candidate"])
        self.assertIn(
            "deterministic evidence loop",
            result["response_text"],
        )

    def test_interaction_capability_is_observed_only_after_real_turn(self) -> None:
        from agenttest.interaction import interact

        initial = self.store.load()
        self.core.cycle("calibration baseline")
        before = self.store.load()
        before_claim = before["self_model"]["capability_claims"][
            "persistent human interaction surface with evidence-linked responses"
        ]
        self.assertEqual(before_claim["status"], "unverified")

        interact(
            "This is a real interaction turn.",
            store=self.store,
        )
        after = self.store.load()
        after_claim = after["self_model"]["capability_claims"][
            "persistent human interaction surface with evidence-linked responses"
        ]

        self.assertEqual(after_claim["status"], "observed")
        self.assertTrue(after_claim["evidence_refs"])
        self.assertIn("E000002", after_claim["evidence_refs"])

    def test_interaction_exposes_prior_world_claims_without_promoting_them(self) -> None:
        from agenttest.interaction import interact

        self.core.cycle(observation=observation(100))
        result = interact(
            "What do you know about your environment?",
            store=self.store,
        )

        claims = result["world"]["prior_current_claims"]
        self.assertTrue(claims)
        self.assertTrue(
            all(claim.get("status") == "current" for claim in claims)
        )
        self.assertTrue(
            all(claim.get("evidence_refs") for claim in claims)
        )

    def test_interaction_rejects_empty_message(self) -> None:
        from agenttest.interaction import interact

        with self.assertRaises(ValueError):
            interact("   ", store=self.store)

    def test_v12_state_migrates_interaction_history_without_loss(self) -> None:
        legacy = {
            "schema_version": 12,
            "cycles": 4,
            "generation": 4,
            "episodes": [{"id": "E000001", "cycle": 1, "concepts": ["alpha"]}],
            "metrics": {"continuity": 1.0},
            "self_model": {"capabilities": [], "limitations": []},
        }
        self.state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["episodes"][0]["id"], "E000001")
        self.assertEqual(migrated["interactions"], [])
        self.assertIn(
            "persistent human interaction surface with evidence-linked responses",
            migrated["self_model"]["capabilities"],
        )


    def test_human_interaction_workflow_is_protected(self) -> None:
        from agenttest.change_control import PROTECTED_PATHS, make_change_manifest

        self.assertIn(".github/workflows/interact.yml", PROTECTED_PATHS)

        self.core.cycle("interaction governance evidence")
        state = self.store.load()
        with self.assertRaises(ValueError):
            make_change_manifest(
                state,
                title="Rewrite interaction authority",
                target_dimension="adaptation",
                files=[".github/workflows/interact.yml"],
                hypothesis="Changing the human interaction channel may alter behavior.",
                expected_effect="Different interaction behavior.",
                test_plan="Run checks.",
                falsification="No behavior change.",
                rollback="Revert.",
                evidence_refs=["E000001"],
            )


    def test_self_proposal_prioritizes_stale_evidence_debt_over_saturated_learning_metric(self) -> None:
        from agenttest.self_proposal import select_change_target

        first = self.core.cycle(observation=observation(100))
        for _ in range(4):
            self.core.cycle(observation=observation(100))
        state = self.store.load()
        state["metrics"]["learning"] = 1.0
        state["metrics"]["open_endedness"] = 0.1
        state["drives"]["evidence_hunger"] = 0.8
        stale = next(
            item for item in state["experiments"]
            if item["id"] == first["experiment"]["id"]
        )
        stale["readiness"] = "evidence_ready"

        selected = select_change_target(state)

        self.assertIsNotNone(selected)
        self.assertEqual(selected["dimension"], "learning")
        self.assertEqual(selected["selection_signal"], "stale_evidence_debt")
        self.assertEqual(selected["experiment_id"], first["experiment"]["id"])
        self.assertIn(first["experiment"]["id"], selected["evidence_refs"])
        self.assertGreaterEqual(selected["age_cycles"], 3)

    def test_self_proposal_does_not_treat_needs_specification_as_code_debt(self) -> None:
        from agenttest.self_proposal import select_change_target

        first = self.core.cycle(observation=observation(100))
        for _ in range(4):
            self.core.cycle(observation=observation(100))
        state = self.store.load()
        stale = next(
            item for item in state["experiments"]
            if item["id"] == first["experiment"]["id"]
        )

        self.assertEqual(stale["readiness"], "needs_specification")
        selected = select_change_target(state)
        self.assertTrue(
            selected is None
            or selected.get("dimension") != "learning"
            or selected.get("experiment_id") != stale["id"]
        )

    def test_learning_review_closes_underspecified_work_as_non_code_problem(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal

        first = self.core.cycle(observation=observation(100))
        for _ in range(4):
            self.core.cycle(observation=observation(100))
        state = self.store.load()
        stale = next(
            item for item in state["experiments"]
            if item["id"] == first["experiment"]["id"]
        )
        self.assertEqual(stale["readiness"], "needs_specification")

        proposal = make_change_manifest(
            state,
            title="Resolve stale experiment evidence debt",
            target_dimension="learning",
            files=["src/agenttest/core.py", "src/agenttest/drives.py", "tests/test_core.py"],
            hypothesis="Readiness-aware closure should separate code debt from specification debt.",
            expected_effect="Underspecified work does not authorize a corrective code patch.",
            test_plan="Review explicit readiness state.",
            falsification="An evidence-ready unresolved experiment still fails to authorize review.",
            rollback="Revert.",
            evidence_refs=[stale["id"]],
        )
        proposal.update({"id": "M999998", "source": "test", "created_cycle": state["cycles"]})
        state["change_proposals"].append(proposal)

        review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertEqual(review["review_version"], "proposal-review-v3")
        self.assertEqual(review["verdict"], "no_problem_observed")
        self.assertEqual(review["patch_authority"], "none")
        self.assertEqual(proposal["status"], "closed_no_problem_observed")

    def test_review_cache_is_invalidated_when_review_semantics_change(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal

        self.core.cycle("review version evidence")
        state = self.store.load()
        proposal = make_change_manifest(
            state,
            title="Versioned review fixture",
            target_dimension="memory",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Review semantics may change across versions.",
            expected_effect="Old reviews are not reused under new semantics.",
            test_plan="Seed an old-version review and request review.",
            falsification="The old review is reused.",
            rollback="Revert.",
            evidence_refs=["E000001"],
        )
        proposal.update({"id": "M999999", "source": "test", "created_cycle": 1})
        state["change_proposals"].append(proposal)
        state["proposal_reviews"].append(
            {
                "id": "V999999",
                "proposal_id": proposal["id"],
                "review_version": "proposal-review-v2",
                "considered_diagnostic_ids": [],
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
            }
        )

        review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertNotEqual(review["id"], "V999999")
        self.assertEqual(review["review_version"], "proposal-review-v3")

    def test_aligned_open_endedness_is_not_reproposed_as_defect(self) -> None:
        from agenttest.self_proposal import select_change_target

        state = self.store.load()
        state["cycles"] = 10
        state["metrics"].update(
            {
                "learning": 1.0,
                "reflection": 1.0,
                "self_model": 1.0,
                "agency": 1.0,
                "curiosity": 1.0,
                "reproducibility": 1.0,
                "perception": 1.0,
                "semantic_memory": 1.0,
                "world_model": 1.0,
                "memory": 1.0,
                "continuity": 1.0,
                "open_endedness": 0.3,
                "cognition": 0.0,
            }
        )
        state["semantic_memory"]["inquiry_families"] = {
            "open_endedness": 0.3,
            "family_count": 3,
            "question_count": 6,
        }
        state["questions"] = [
            {"id": "Q000001", "text": "Question one", "status": "open"},
        ]
        state["episodes"] = [
            {"id": "E000001", "kind": "stimulus", "cycle": 1, "concepts": ["one"]},
        ]
        state["cognition_candidates"] = []
        state["cognition_events"] = []

        selected = select_change_target(state)

        self.assertIsNone(selected)

    def test_misaligned_open_endedness_remains_eligible_for_governance_review(self) -> None:
        from agenttest.self_proposal import select_change_target

        state = self.store.load()
        state["cycles"] = 10
        state["metrics"].update(
            {
                "learning": 1.0,
                "reflection": 1.0,
                "self_model": 1.0,
                "agency": 1.0,
                "curiosity": 1.0,
                "reproducibility": 1.0,
                "perception": 1.0,
                "semantic_memory": 1.0,
                "world_model": 1.0,
                "memory": 1.0,
                "continuity": 1.0,
                "open_endedness": 0.8,
                "cognition": 0.0,
            }
        )
        state["semantic_memory"]["inquiry_families"] = {
            "open_endedness": 0.3,
            "family_count": 3,
            "question_count": 6,
        }
        state["questions"] = [
            {"id": "Q000001", "text": "Question one", "status": "open"},
            {"id": "Q000002", "text": "Question two", "status": "open"},
        ]
        state["episodes"] = [
            {"id": "E000001", "kind": "stimulus", "cycle": 1, "concepts": ["one"]},
        ]
        state["cognition_candidates"] = []
        state["cognition_events"] = []

        selected = select_change_target(state)

        self.assertIsNotNone(selected)
        self.assertEqual(selected["dimension"], "open_endedness")


    def test_stale_underspecified_experiment_is_preserved_but_not_resolvable_pressure(self) -> None:
        first = self.core.cycle(observation=observation(100))
        for _ in range(3):
            self.core.cycle(observation=observation(100))

        state = self.store.load()
        stale = next(
            item for item in state["experiments"]
            if item["id"] == first["experiment"]["id"]
        )

        self.assertEqual(stale["status"], "proposed")
        self.assertEqual(stale["readiness"], "needs_specification")
        self.assertTrue(stale["readiness_evidence_refs"])
        self.assertEqual(len(stale["readiness_history"]), 1)
        resolvable_pending = [
            item for item in state["experiments"]
            if item.get("status") == "proposed"
            and item.get("readiness") != "needs_specification"
        ]
        self.assertNotIn(stale["id"], [item["id"] for item in resolvable_pending])
        resolvable_at_drive_time = [
            item for item in resolvable_pending
            if int(item.get("cycle", 0)) < state["cycles"]
        ]
        self.assertEqual(
            state["drives"]["evidence_hunger"],
            min(0.8, len(resolvable_at_drive_time) / 4.0),
        )
        self.assertNotEqual(
            state["intentions"][-1].get("target"),
            stale["id"],
        )

    def test_prediction_contract_resolves_only_matching_experiment(self) -> None:
        first = self.core.cycle(observation=observation(100))
        state = self.store.load()
        experiment = next(
            item for item in state["experiments"]
            if item["id"] == first["experiment"]["id"]
        )
        experiment["evidence_contract"] = {
            "kind": "prediction_status",
            "prediction_id": first["prediction"]["id"],
            "expected_status": "confirmed",
        }
        self.store.save(state)

        second = self.core.cycle(observation=observation(100))
        after = self.store.load()
        resolved = next(
            item for item in after["experiments"]
            if item["id"] == experiment["id"]
        )

        self.assertEqual(second["prediction_result"]["status"], "confirmed")
        self.assertEqual(resolved["status"], "completed")
        self.assertEqual(resolved["readiness"], "resolved")
        self.assertEqual(resolved["outcome"], "supported")
        self.assertIn(first["prediction"]["id"], resolved["evidence_refs"])
        self.assertIn(
            resolved["id"],
            second["prediction_result"]["resolved_experiment_ids"],
        )

    def test_unrelated_prediction_evidence_does_not_close_contract(self) -> None:
        first = self.core.cycle(observation=observation(100))
        state = self.store.load()
        experiment = next(
            item for item in state["experiments"]
            if item["id"] == first["experiment"]["id"]
        )
        experiment["evidence_contract"] = {
            "kind": "prediction_status",
            "prediction_id": "P999999",
            "expected_status": "confirmed",
        }
        self.store.save(state)

        self.core.cycle(observation=observation(100))
        after = self.store.load()
        unresolved = next(
            item for item in after["experiments"]
            if item["id"] == experiment["id"]
        )

        self.assertEqual(unresolved["status"], "proposed")
        self.assertEqual(unresolved["readiness"], "evidence_ready")
        self.assertNotIn("outcome", unresolved)


    def test_same_question_method_reuses_active_experiment(self) -> None:
        state = self.store.load()
        state["cycles"] = 1
        question = {
            "id": "Q000001",
            "text": "Which assumption should be falsified?",
            "status": "open",
        }
        state["questions"].append(question)
        intention = {
            "id": "I000001",
            "kind": "reduce_uncertainty",
            "target": None,
        }

        first = self.core._select_or_propose_experiment(
            state,
            question,
            intention,
            None,
        )
        state["cycles"] = 2
        intention["id"] = "I000002"
        second = self.core._select_or_propose_experiment(
            state,
            question,
            intention,
            None,
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(state["experiments"]), 1)
        self.assertEqual(second["times_selected"], 2)
        self.assertEqual(second["last_selected_cycle"], 2)

    def test_duplicate_reconciliation_preserves_history_and_supersedes_extra_active_copy(self) -> None:
        from agenttest.core import _reconcile_duplicate_experiments

        state = self.store.load()
        state["cycles"] = 9
        state["experiments"] = [
            {
                "id": "X000001",
                "cycle": 3,
                "question_id": "Q000001",
                "status": "proposed",
                "hypothesis": "H",
                "method": "Seek one disconfirming observation.",
            },
            {
                "id": "X000002",
                "cycle": 5,
                "question_id": "Q000001",
                "status": "proposed",
                "hypothesis": "H",
                "method": "Seek one disconfirming observation.",
                "readiness": "needs_specification",
            },
        ]

        update = _reconcile_duplicate_experiments(state)

        self.assertEqual(len(state["experiments"]), 2)
        self.assertEqual(state["experiments"][0]["status"], "proposed")
        duplicate = state["experiments"][1]
        self.assertEqual(duplicate["status"], "superseded_duplicate")
        self.assertEqual(duplicate["duplicate_of"], "X000001")
        self.assertEqual(duplicate["hypothesis"], "H")
        self.assertEqual(
            duplicate["status_history"][-1]["reason"],
            "exact_uncontracted_question_method_duplicate",
        )
        self.assertEqual(update["superseded_experiment_ids"], ["X000002"])

    def test_contracted_experiment_is_not_collapsed_with_uncontracted_history(self) -> None:
        from agenttest.core import _reconcile_duplicate_experiments

        state = self.store.load()
        state["cycles"] = 9
        state["experiments"] = [
            {
                "id": "X000001",
                "cycle": 3,
                "question_id": "Q000001",
                "status": "proposed",
                "method": "Observe the next prediction.",
                "evidence_contract": {
                    "kind": "prediction_status",
                    "prediction_id": "P000001",
                    "expected_status": "confirmed",
                },
            },
            {
                "id": "X000002",
                "cycle": 5,
                "question_id": "Q000001",
                "status": "proposed",
                "method": "Observe the next prediction.",
            },
        ]

        update = _reconcile_duplicate_experiments(state)

        self.assertEqual(update["superseded_experiment_ids"], [])
        self.assertEqual(
            [item["status"] for item in state["experiments"]],
            ["proposed", "proposed"],
        )



    def test_specification_backlog_becomes_dominant_control_pressure(self) -> None:
        from agenttest.drives import choose_intention, compute_drives

        state = initial_state()
        state["cycles"] = 8
        state["metrics"]["continuity"] = 1.0
        state["metrics"]["self_model"] = 1.0
        state["questions"] = [
            {"id": f"Q{index:06d}", "status": "open"}
            for index in range(1, 7)
        ]
        state["experiments"] = [
            {
                "id": f"X{index:06d}",
                "cycle": index,
                "status": "proposed",
                "readiness": "needs_specification",
            }
            for index in range(1, 5)
        ]

        drives = compute_drives(state)
        intention = choose_intention(state, drives)

        self.assertEqual(drives["specification_pressure"], 0.9)
        self.assertEqual(drives["uncertainty"], 0.8)
        self.assertEqual(intention["dominant_drive"], "specification_pressure")
        self.assertEqual(intention["kind"], "specify_experiment")
        self.assertEqual(intention["target"], "X000001")

    def test_prediction_error_still_outranks_specification_pressure(self) -> None:
        from agenttest.drives import choose_intention, compute_drives

        state = initial_state()
        state["cycles"] = 8
        state["experiments"] = [
            {
                "id": f"X{index:06d}",
                "cycle": index,
                "status": "proposed",
                "readiness": "needs_specification",
            }
            for index in range(1, 5)
        ]
        state["surprises"] = [{"id": "S000001"}]

        drives = compute_drives(
            state,
            surprise={"id": "S000001"},
            prediction_result={"status": "violated"},
        )
        intention = choose_intention(state, drives)

        self.assertEqual(drives["prediction_error"], 1.0)
        self.assertEqual(drives["specification_pressure"], 0.9)
        self.assertEqual(intention["kind"], "explain_change")

    def test_specification_intention_reuses_target_and_asks_for_contract_fields(self) -> None:
        state = self.store.load()
        state["cycles"] = 8
        experiment = {
            "id": "X000001",
            "cycle": 1,
            "question_id": "Q000001",
            "status": "proposed",
            "readiness": "needs_specification",
            "method": "Seek a discriminating observation.",
        }
        state["experiments"] = [experiment]
        intention = {
            "id": "I000001",
            "kind": "specify_experiment",
            "target": "X000001",
        }

        text = self.core._generate_question(state, None, intention, None)
        question = {
            "id": "Q000002",
            "text": text,
            "status": "open",
        }
        selected = self.core._select_or_propose_experiment(
            state,
            question,
            intention,
            None,
        )

        self.assertIn("observable", text)
        self.assertIn("evidence source", text)
        self.assertIn("resolution rule", text)
        self.assertEqual(selected["id"], "X000001")
        self.assertEqual(len(state["experiments"]), 1)
        self.assertEqual(selected["specification_attempts"], 1)
        self.assertEqual(selected["last_selected_cycle"], 8)



if __name__ == "__main__":
    unittest.main()
