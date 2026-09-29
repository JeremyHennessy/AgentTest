from __future__ import annotations

import unittest

from agenttest.intervention import (
    CLOSED_VERIFIED_INTERVENTION,
    record_verified_intervention,
)
from agenttest.change_control import PROTECTED_PATHS
from agenttest.state import initial_state


class VerifiedInterventionTests(unittest.TestCase):
    def test_reconciliation_authority_paths_are_protected(self) -> None:
        for path in (
            ".github/workflows/reconcile.yml",
            "scripts/reconcile_verified_change.py",
            "src/agenttest/intervention.py",
        ):
            self.assertIn(path, PROTECTED_PATHS)

    def supported_state(self) -> dict:
        state = initial_state()
        state["cycles"] = 12
        state["change_proposals"].append(
            {
                "id": "M000008",
                "status": "reviewed_supported_problem",
                "target_dimension": "learning",
                "files": [
                    "src/agenttest/core.py",
                    "src/agenttest/drives.py",
                    "tests/test_core.py",
                ],
                "protected_paths": [
                    ".github/workflows/verify.yml",
                    "scripts/preservation_eval.py",
                ],
            }
        )
        return state

    def test_verified_intervention_closes_proposal_without_claiming_improvement(self) -> None:
        state = self.supported_state()

        receipt, created = record_verified_intervention(
            state,
            proposal_id="M000008",
            commit_sha="a" * 40,
            changed_files=[
                "src/agenttest/core.py",
                "src/agenttest/drives.py",
                "tests/test_core.py",
            ],
            verify_run_id=12345,
            pr_number=28,
            attribution_text="Accept M000008 after verified candidate evaluation.",
        )

        self.assertTrue(created)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["verification_scope"], "applied_and_preserved")
        self.assertEqual(receipt["improvement_claim"], "not_implied")
        self.assertEqual(receipt["verification"]["conclusion"], "success")
        self.assertEqual(state["accepted_changes"], [receipt])
        self.assertEqual(state["metrics"]["adaptation"], 1.0 / 3.0)
        proposal = state["change_proposals"][0]
        self.assertEqual(proposal["status"], CLOSED_VERIFIED_INTERVENTION)
        self.assertEqual(proposal["accepted_change_id"], receipt["id"])

    def test_reconciliation_is_idempotent_for_same_proposal_and_commit(self) -> None:
        state = self.supported_state()
        kwargs = dict(
            proposal_id="M000008",
            commit_sha="b" * 40,
            changed_files=["src/agenttest/core.py"],
            verify_run_id=222,
            pr_number=28,
            attribution_text="Accept M000008 after verified candidate evaluation.",
        )
        first, first_created = record_verified_intervention(state, **kwargs)
        second, second_created = record_verified_intervention(state, **kwargs)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first, second)
        self.assertEqual(len(state["accepted_changes"]), 1)

    def test_commit_outside_authorized_scope_is_rejected(self) -> None:
        state = self.supported_state()

        with self.assertRaises(ValueError):
            record_verified_intervention(
                state,
                proposal_id="M000008",
                commit_sha="c" * 40,
                changed_files=["src/agenttest/core.py", "README.md"],
                verify_run_id=333,
                pr_number=28,
            attribution_text="Accept M000008 after verified candidate evaluation.",
            )

        self.assertEqual(state["accepted_changes"], [])
        self.assertEqual(
            state["change_proposals"][0]["status"],
            "reviewed_supported_problem",
        )

    def test_non_successful_or_non_push_verification_is_rejected(self) -> None:
        state = self.supported_state()

        with self.assertRaises(ValueError):
            record_verified_intervention(
                state,
                proposal_id="M000008",
                commit_sha="d" * 40,
                changed_files=["src/agenttest/core.py"],
                verify_run_id=444,
                pr_number=28,
            attribution_text="Accept M000008 after verified candidate evaluation.",
                verification_conclusion="failure",
            )

        with self.assertRaises(ValueError):
            record_verified_intervention(
                state,
                proposal_id="M000008",
                commit_sha="e" * 40,
                changed_files=["src/agenttest/core.py"],
                verify_run_id=445,
                pr_number=28,
            attribution_text="Accept M000008 after verified candidate evaluation.",
                verification_event="pull_request",
            )


    def test_matching_file_scope_without_proposal_attribution_is_rejected(self) -> None:
        state = self.supported_state()

        with self.assertRaises(ValueError):
            record_verified_intervention(
                state,
                proposal_id="M000008",
                commit_sha="1" * 40,
                changed_files=["src/agenttest/core.py"],
                verify_run_id=777,
                pr_number=28,
                attribution_text="Unrelated core maintenance",
            )

    def test_scope_can_identify_single_matching_supported_proposal(self) -> None:
        state = self.supported_state()

        receipt, created = record_verified_intervention(
            state,
            commit_sha="f" * 40,
            changed_files=["src/agenttest/drives.py"],
            verify_run_id=555,
            pr_number=28,
            attribution_text="Accept M000008 after verified candidate evaluation.",
        )

        self.assertTrue(created)
        self.assertEqual(receipt["proposal_id"], "M000008")


if __name__ == "__main__":
    unittest.main()
