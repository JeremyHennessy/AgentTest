from __future__ import annotations

import copy
import unittest

from agenttest.change_control import PROTECTED_PATHS
from agenttest.diagnostic_experiments import evaluate_experiment_design


class ExperimentDesignDiagnosticTests(unittest.TestCase):
    def test_diagnostic_authority_is_protected(self) -> None:
        self.assertIn("src/agenttest/diagnostic_experiments.py", PROTECTED_PATHS)
        self.assertIn("scripts/experiment_design_eval.py", PROTECTED_PATHS)

    def test_duplicate_uncontracted_experiments_are_specification_churn(self) -> None:
        state = {
            "questions": [
                {
                    "id": "Q000001",
                    "text": "Which assumption needs falsification?",
                    "times_selected": 8,
                }
            ],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "proposed",
                    "readiness": "needs_specification",
                    "method": "Seek one disconfirming observation.",
                },
                {
                    "id": "X000002",
                    "question_id": "Q000001",
                    "status": "proposed",
                    "readiness": "awaiting_specification_or_evidence",
                    "method": "Seek one disconfirming observation.",
                },
            ],
        }
        before = copy.deepcopy(state)

        result = evaluate_experiment_design(state)

        self.assertEqual(result["outcome"], "specification_churn")
        self.assertEqual(result["active_experiment_count"], 2)
        self.assertEqual(result["active_question_count"], 1)
        self.assertEqual(result["specification_backlog_count"], 2)
        self.assertEqual(result["largest_duplicate_cluster"], 2)
        self.assertEqual(result["contracted_ratio"], 0.0)
        self.assertFalse(result["source_state_mutated"])
        self.assertEqual(state, before)

    def test_valid_contracts_are_evidence_ready(self) -> None:
        state = {
            "questions": [{"id": "Q000001", "text": "Will the prediction hold?"}],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "proposed",
                    "readiness": "evidence_ready",
                    "method": "Observe the next prediction result.",
                    "evidence_contract": {
                        "kind": "prediction_status",
                        "prediction_id": "P000001",
                        "expected_status": "confirmed",
                    },
                }
            ],
        }

        result = evaluate_experiment_design(state)

        self.assertEqual(result["outcome"], "evidence_ready")
        self.assertEqual(result["contracted_count"], 1)
        self.assertEqual(result["specification_backlog_count"], 0)
        self.assertEqual(result["contracted_ratio"], 1.0)
        self.assertEqual(result["duplicate_cluster_count"], 0)

    def test_single_uncontracted_experiment_is_backlog_not_churn(self) -> None:
        state = {
            "questions": [{"id": "Q000001", "text": "What should be tested?"}],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "proposed",
                    "method": "Specify a discriminating observation.",
                }
            ],
        }

        result = evaluate_experiment_design(state)

        self.assertEqual(result["outcome"], "specification_backlog")
        self.assertEqual(result["uncontracted_count"], 1)
        self.assertEqual(result["specification_backlog_count"], 1)
        self.assertEqual(result["largest_duplicate_cluster"], 0)

    def test_explicit_needs_specification_status_is_backlog_not_active_work(self) -> None:
        state = {
            "questions": [{"id": "Q000001", "text": "What should be specified?"}],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "needs_specification",
                    "readiness": "needs_specification",
                    "method": "Name a discriminating observation.",
                }
            ],
        }

        result = evaluate_experiment_design(state)

        self.assertEqual(result["outcome"], "specification_backlog")
        self.assertEqual(result["active_experiment_count"], 0)
        self.assertEqual(result["specification_backlog_count"], 1)
        self.assertEqual(result["unresolved_experiment_count"], 1)
        self.assertEqual(result["contracted_ratio"], 0.0)

    def test_completed_experiments_are_not_active_design_debt(self) -> None:
        state = {
            "questions": [{"id": "Q000001", "text": "Resolved?"}],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "completed",
                    "method": "Observe evidence.",
                }
            ],
        }

        result = evaluate_experiment_design(state)

        self.assertEqual(result["outcome"], "no_active_experiments")
        self.assertEqual(result["active_experiment_count"], 0)


if __name__ == "__main__":
    unittest.main()
