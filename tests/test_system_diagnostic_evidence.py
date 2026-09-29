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
