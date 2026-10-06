from __future__ import annotations

import unittest

from agenttest.change_control import PROTECTED_PATHS, make_change_manifest
from agenttest.cognition import build_context
from agenttest.evidence import known_evidence_ids
from agenttest.proposal_review import review_change_proposal
from agenttest.self_proposal import propose_self_change, select_change_target
from agenttest.state import DIMENSIONS, initial_state


def saturated_state() -> dict:
    state = initial_state()
    state["cycles"] = 40
    state["generation"] = 40
    state["metrics"].update({dimension: 1.0 for dimension in DIMENSIONS})
    state["drives"] = {
        "prediction_error": 0.0,
        "specification_pressure": 0.9,
        "evidence_hunger": 0.0,
        "uncertainty": 0.8,
        "continuity_repair": 0.0,
        "calibration_gap": 0.0,
        "novelty_hunger": 0.0,
    }
    return state


def system_diagnostic(
    *,
    identifier: str = "SD000001",
    outcome: str = "specification_backlog",
    status: str = "completed",
) -> dict:
    return {
        "id": identifier,
        "kind": "experiment_design",
        "status": status,
        "diagnostic_version": "experiment-design-v2",
        "outcome": outcome,
        "created_cycle": 40,
        "source_state_mutated": False,
        "result": {
            "outcome": outcome,
            "specification_backlog_count": 11,
            "executable_experiment_count": 0,
            "contracted_ratio": 0.0,
        },
    }


class SystemDiagnosticEvidenceTests(unittest.TestCase):
    def test_completed_system_diagnostic_is_known_evidence(self) -> None:
        state = saturated_state()
        state["system_diagnostics"] = [system_diagnostic()]

        self.assertIn("SD000001", known_evidence_ids(state))

        manifest = make_change_manifest(
            state,
            title="Use protected diagnostic evidence",
            target_dimension="learning",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Protected diagnostics can ground a bounded candidate.",
            expected_effect="The manifest cites the diagnostic rather than an inferred defect.",
            test_plan="Validate the manifest.",
            falsification="The diagnostic is not accepted as evidence.",
            rollback="Revert.",
            evidence_refs=["SD000001"],
        )
        self.assertEqual(manifest["evidence_refs"], ["SD000001"])

    def test_incomplete_system_diagnostic_is_not_known_evidence(self) -> None:
        state = saturated_state()
        state["system_diagnostics"] = [
            system_diagnostic(status="running"),
        ]

        self.assertNotIn("SD000001", known_evidence_ids(state))

        with self.assertRaises(ValueError):
            make_change_manifest(
                state,
                title="Do not cite incomplete diagnostics",
                target_dimension="learning",
                files=["src/agenttest/core.py"],
                hypothesis="Incomplete diagnostics must not authorize changes.",
                expected_effect="Manifest validation fails.",
                test_plan="Validate the manifest.",
                falsification="The manifest validates.",
                rollback="Revert.",
                evidence_refs=["SD000001"],
            )

    def test_system_diagnostic_evidence_authority_is_protected(self) -> None:
        self.assertIn("src/agenttest/evidence.py", PROTECTED_PATHS)

    def test_grounded_cognition_context_exposes_completed_system_diagnostic(self) -> None:
        state = saturated_state()
        state["system_diagnostics"] = [system_diagnostic()]
        intention = {
            "id": "I000001",
            "cycle": 40,
            "kind": "specify_experiment",
            "dominant_drive": "specification_pressure",
            "strength": 0.9,
            "target": "X000001",
            "rationale": "Specification backlog is the strongest current pressure.",
        }

        context = build_context(state, intention)

        matching = [
            item for item in context["evidence"]
            if item["id"] == "SD000001"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["kind"], "system_diagnostic")

    def test_backlog_diagnostic_can_originate_and_authorize_self_proposal(self) -> None:
        state = saturated_state()
        state["system_diagnostics"] = [system_diagnostic()]

        selected = select_change_target(state)
        proposal, created = propose_self_change(state)
        review, review_created = review_change_proposal(state, proposal)

        self.assertIsNotNone(selected)
        self.assertEqual(
            selected["selection_signal"],
            "experiment_design_specification_backlog",
        )
        self.assertEqual(selected["evidence_refs"], ["SD000001"])
        self.assertTrue(created)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal["title"], "Triage experiment specification backlog")
        self.assertEqual(proposal["selection_signal"], selected["selection_signal"])
        self.assertEqual(proposal["source_diagnostic_id"], "SD000001")
        self.assertEqual(proposal["evidence_refs"], ["SD000001"])
        self.assertTrue(review_created)
        self.assertEqual(review["review_version"], "proposal-review-v4")
        self.assertEqual(review["verdict"], "supported_problem")
        self.assertEqual(review["patch_authority"], "candidate_allowed")
        self.assertEqual(review["direct_diagnostic_id"], "SD000001")
        self.assertEqual(
            review["considered_system_diagnostic_ids"],
            ["SD000001"],
        )
        self.assertEqual(proposal["status"], "reviewed_supported_problem")

    def test_same_cycle_new_experiment_backlog_does_not_trigger_self_change(self) -> None:
        from agenttest.self_proposal import select_change_target

        state = saturated_state()
        state["cycles"] = 45
        state["metrics"].update({name: 1.0 for name in state["metrics"]})
        state["experiments"] = [
            {
                "id": "X000020",
                "cycle": 45,
                "status": "proposed",
                "question_id": "Q000009",
            }
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000014",
                "kind": "experiment_design",
                "status": "completed",
                "diagnostic_version": "experiment-design-v3",
                "outcome": "specification_backlog",
                "created_cycle": 45,
                "result": {
                    "untriaged_specification_ids": ["X000020"],
                    "specification_backlog_count": 1,
                },
            }
        ]

        selected = select_change_target(state)

        self.assertIsNone(selected)

    def test_older_untriaged_backlog_remains_self_change_evidence(self) -> None:
        from agenttest.self_proposal import select_change_target

        state = saturated_state()
        state["cycles"] = 45
        state["metrics"].update({name: 1.0 for name in state["metrics"]})
        state["experiments"] = [
            {
                "id": "X000020",
                "cycle": 43,
                "status": "proposed",
                "question_id": "Q000009",
            }
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000014",
                "kind": "experiment_design",
                "status": "completed",
                "diagnostic_version": "experiment-design-v3",
                "outcome": "specification_backlog",
                "created_cycle": 45,
                "result": {
                    "untriaged_specification_ids": ["X000020"],
                    "specification_backlog_count": 1,
                },
            }
        ]

        selected = select_change_target(state)

        self.assertIsNotNone(selected)
        self.assertEqual(
            selected["selection_signal"],
            "experiment_design_specification_backlog",
        )

    def test_same_cycle_backlog_proposal_closes_as_expected_latency(self) -> None:
        from agenttest.change_control import make_change_manifest
        from agenttest.proposal_review import review_change_proposal

        state = saturated_state()
        state["cycles"] = 45
        state["experiments"] = [
            {
                "id": "X000020",
                "cycle": 45,
                "status": "proposed",
                "question_id": "Q000009",
            }
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000014",
                "kind": "experiment_design",
                "status": "completed",
                "diagnostic_version": "experiment-design-v3",
                "outcome": "specification_backlog",
                "created_cycle": 45,
                "result": {
                    "untriaged_specification_ids": ["X000020"],
                },
            }
        ]
        proposal = make_change_manifest(
            state,
            title="Triage experiment specification backlog",
            target_dimension="learning",
            files=[
                "src/agenttest/core.py",
                "src/agenttest/drives.py",
                "tests/test_core.py",
            ],
            hypothesis="Trace specification fields without invention.",
            expected_effect="Classify specification work.",
            test_plan="Review backlog lifecycle.",
            falsification="Older untriaged work persists.",
            rollback="Revert.",
            evidence_refs=["SD000014"],
        )
        proposal.update(
            {
                "id": "M000012",
                "source": "test",
                "created_cycle": 45,
                "selection_signal": "experiment_design_specification_backlog",
                "source_diagnostic_id": "SD000014",
            }
        )
        state["change_proposals"].append(proposal)

        review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertEqual(review["review_version"], "proposal-review-v4")
        self.assertEqual(review["verdict"], "no_problem_observed")
        self.assertEqual(review["patch_authority"], "none")
        self.assertEqual(proposal["status"], "closed_no_problem_observed")

    def test_cached_same_cycle_supported_review_is_rechecked(self) -> None:
        state = saturated_state()
        state["cycles"] = 45
        state["experiments"] = [
            {
                "id": "X000020",
                "cycle": 45,
                "status": "proposed",
                "question_id": "Q000009",
            }
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000014",
                "kind": "experiment_design",
                "status": "completed",
                "diagnostic_version": "experiment-design-v3",
                "outcome": "specification_backlog",
                "created_cycle": 45,
                "result": {
                    "untriaged_specification_ids": ["X000020"],
                    "specification_backlog_count": 1,
                },
            }
        ]
        proposal = make_change_manifest(
            state,
            title="Triage experiment specification backlog",
            target_dimension="learning",
            files=[
                "src/agenttest/core.py",
                "src/agenttest/drives.py",
                "tests/test_core.py",
            ],
            hypothesis="Trace specification fields without invention.",
            expected_effect="Classify specification work.",
            test_plan="Review backlog lifecycle.",
            falsification="Older untriaged work persists.",
            rollback="Revert.",
            evidence_refs=["SD000014"],
        )
        proposal.update(
            {
                "id": "M000012",
                "source": "test",
                "created_cycle": 45,
                "selection_signal": "experiment_design_specification_backlog",
                "source_diagnostic_id": "SD000014",
                "status": "reviewed_supported_problem",
            }
        )
        state["change_proposals"].append(proposal)
        state["proposal_reviews"].append(
            {
                "id": "V999999",
                "proposal_id": "M000012",
                "target_dimension": "learning",
                "review_version": "proposal-review-v4",
                "considered_diagnostic_ids": [],
                "considered_system_diagnostic_ids": ["SD000014"],
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
            }
        )

        review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertNotEqual(review["id"], "V999999")
        self.assertEqual(review["review_version"], "proposal-review-v4")
        self.assertEqual(review["verdict"], "no_problem_observed")
        self.assertEqual(review["patch_authority"], "none")
        self.assertEqual(proposal["status"], "closed_no_problem_observed")

    def test_old_baseline_attention_diagnostic_cannot_author_self_change(self) -> None:
        state = saturated_state()
        state["drives"] = {
            "prediction_error": 0.0,
            "specification_pressure": 0.0,
            "evidence_hunger": 0.0,
            "uncertainty": 0.8,
            "continuity_repair": 0.0,
            "calibration_gap": 0.0,
            "novelty_hunger": 0.0,
        }
        state["environment_snapshots"] = [
            {"baseline_fingerprint": "current-baseline"}
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000017",
                "kind": "attention_control",
                "status": "completed",
                "baseline_fingerprint": "old-baseline",
                "outcome": "blocked_attention_loop",
                "created_cycle": 46,
                "result": {"loop_count": 1},
            }
        ]

        proposal, created = propose_self_change(state)

        self.assertFalse(created)
        self.assertIsNone(proposal)

    def test_current_baseline_attention_diagnostic_can_author_self_change(self) -> None:
        state = saturated_state()
        state["drives"] = {
            "prediction_error": 0.0,
            "specification_pressure": 0.0,
            "evidence_hunger": 0.0,
            "uncertainty": 0.8,
            "continuity_repair": 0.0,
            "calibration_gap": 0.0,
            "novelty_hunger": 0.0,
        }
        state["environment_snapshots"] = [
            {"baseline_fingerprint": "current-baseline"}
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000020",
                "kind": "attention_control",
                "status": "completed",
                "baseline_fingerprint": "current-baseline",
                "outcome": "blocked_attention_loop",
                "created_cycle": 48,
                "result": {"loop_count": 1},
            }
        ]

        proposal, created = propose_self_change(state)

        self.assertTrue(created)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal["source_diagnostic_id"], "SD000020")

    def test_old_baseline_experiment_diagnostic_cannot_author_self_change(self) -> None:
        state = saturated_state()
        state["environment_snapshots"] = [
            {"baseline_fingerprint": "current-baseline"}
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000018",
                "kind": "experiment_design",
                "status": "completed",
                "baseline_fingerprint": "old-baseline",
                "diagnostic_version": "experiment-design-v3",
                "outcome": "specification_backlog",
                "created_cycle": 47,
                "result": {
                    "specification_backlog_count": 10,
                    "untriaged_specification_ids": [],
                },
            }
        ]

        selected = select_change_target(state)

        self.assertTrue(
            selected is None
            or selected.get("selection_signal")
            != "experiment_design_specification_backlog"
        )

    def test_cached_old_baseline_attention_review_closes_on_current_redirect(self) -> None:
        state = saturated_state()
        state["cycles"] = 48
        state["environment_snapshots"] = [
            {"baseline_fingerprint": "current-baseline"}
        ]
        state["system_diagnostics"] = [
            {
                "id": "SD000017",
                "kind": "attention_control",
                "status": "completed",
                "baseline_fingerprint": "old-baseline",
                "outcome": "blocked_attention_loop",
                "created_cycle": 46,
                "result": {"loop_count": 1},
            },
            {
                "id": "SD000019",
                "kind": "attention_control",
                "status": "completed",
                "baseline_fingerprint": "current-baseline",
                "outcome": "attention_redirected",
                "created_cycle": 47,
                "result": {"loop_count": 0},
            },
        ]
        proposal = make_change_manifest(
            state,
            title="Redirect inquiry away from blocked experiments",
            target_dimension="agency",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="Blocked questions should not monopolize inquiry.",
            expected_effect="Attention moves to eligible unresolved inquiry.",
            test_plan="Compare blocked and eligible selection.",
            falsification="Blocked attention still loops.",
            rollback="Revert.",
            evidence_refs=["SD000017"],
        )
        proposal.update(
            {
                "id": "M000013",
                "source": "test",
                "created_cycle": 47,
                "selection_signal": "attention_control_blocked_attention_loop",
                "source_diagnostic_id": "SD000017",
                "status": "reviewed_supported_problem",
            }
        )
        state["change_proposals"].append(proposal)
        state["proposal_reviews"].append(
            {
                "id": "V000025",
                "proposal_id": "M000013",
                "review_version": "proposal-review-v4",
                "considered_diagnostic_ids": [],
                "considered_system_diagnostic_ids": ["SD000017"],
                "verdict": "supported_problem",
                "patch_authority": "candidate_allowed",
            }
        )

        review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertNotEqual(review["id"], "V000025")
        self.assertEqual(review["verdict"], "no_problem_observed")
        self.assertEqual(review["patch_authority"], "none")
        self.assertEqual(review["direct_diagnostic_id"], "SD000019")
        self.assertEqual(proposal["status"], "closed_no_problem_observed")

    def test_evidence_ready_system_diagnostic_does_not_trigger_self_change(self) -> None:
        state = saturated_state()
        state["system_diagnostics"] = [
            system_diagnostic(outcome="evidence_ready"),
        ]

        selected = select_change_target(state)
        proposal, created = propose_self_change(state)

        self.assertIsNone(selected)
        self.assertFalse(created)
        self.assertIsNone(proposal)

    def test_diagnostic_signal_with_mismatched_outcome_cannot_authorize_patch(self) -> None:
        state = saturated_state()
        diagnostic = system_diagnostic(outcome="specification_churn")
        state["system_diagnostics"] = [diagnostic]
        proposal = make_change_manifest(
            state,
            title="Mismatched diagnostic fixture",
            target_dimension="learning",
            files=["src/agenttest/core.py", "tests/test_core.py"],
            hypothesis="A mismatch must fail closed.",
            expected_effect="No patch authority.",
            test_plan="Review the proposal.",
            falsification="Patch authority is granted.",
            rollback="Revert.",
            evidence_refs=["SD000001"],
        )
        proposal.update(
            {
                "id": "M000001",
                "source": "test",
                "created_cycle": 40,
                "selection_signal": "experiment_design_specification_backlog",
                "source_diagnostic_id": "SD000001",
            }
        )
        state["change_proposals"].append(proposal)

        review, created = review_change_proposal(state, proposal)

        self.assertTrue(created)
        self.assertEqual(review["verdict"], "needs_evidence")
        self.assertEqual(review["patch_authority"], "none")


if __name__ == "__main__":
    unittest.main()
