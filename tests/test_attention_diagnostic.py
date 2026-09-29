from __future__ import annotations

import copy
import unittest

from agenttest.change_control import PROTECTED_PATHS
from agenttest.diagnostic_attention import evaluate_blocked_attention


class BlockedAttentionDiagnosticTests(unittest.TestCase):
    def test_diagnostic_authority_is_protected(self) -> None:
        self.assertIn("src/agenttest/diagnostic_attention.py", PROTECTED_PATHS)
        self.assertIn("scripts/blocked_attention_eval.py", PROTECTED_PATHS)

    def test_reselection_after_block_is_detected_as_loop(self) -> None:
        state = {
            "questions": [
                {
                    "id": "Q000001",
                    "text": "Which assumption remains untested?",
                    "times_selected": 8,
                }
            ],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "proposed",
                    "times_selected": 3,
                    "last_selected_cycle": 12,
                    "specification": {
                        "actionability": "blocked",
                        "evaluated_cycle": 12,
                        "missing_fields": [
                            "observable",
                            "evidence_source",
                            "resolution_rule",
                        ],
                        "blocking_reason": "No grounded source.",
                    },
                }
            ],
        }
        before = copy.deepcopy(state)

        result = evaluate_blocked_attention(state)

        self.assertEqual(result["outcome"], "blocked_attention_loop")
        self.assertEqual(result["reselected_after_block_ids"], ["X000001"])
        self.assertEqual(result["loop_experiment_ids"], ["X000001"])
        self.assertEqual(result["max_blocked_question_times_selected"], 8)
        self.assertFalse(result["source_state_mutated"])
        self.assertEqual(state, before)

    def test_blocked_work_not_reselected_is_attention_redirected(self) -> None:
        state = {
            "questions": [
                {"id": "Q000001", "text": "Blocked question", "times_selected": 5}
            ],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "proposed",
                    "times_selected": 1,
                    "last_selected_cycle": 5,
                    "specification": {
                        "actionability": "blocked",
                        "evaluated_cycle": 8,
                    },
                }
            ],
        }

        result = evaluate_blocked_attention(state)

        self.assertEqual(result["outcome"], "attention_redirected")
        self.assertEqual(result["reselected_after_block_count"], 0)

    def test_single_post_block_contact_is_not_overcalled_as_loop(self) -> None:
        state = {
            "questions": [
                {"id": "Q000001", "text": "New blocked question", "times_selected": 1}
            ],
            "experiments": [
                {
                    "id": "X000001",
                    "question_id": "Q000001",
                    "status": "proposed",
                    "times_selected": 1,
                    "last_selected_cycle": 8,
                    "specification": {
                        "actionability": "blocked",
                        "evaluated_cycle": 8,
                    },
                }
            ],
        }

        result = evaluate_blocked_attention(state)

        self.assertEqual(result["outcome"], "blocked_attention_contact")
        self.assertEqual(result["loop_count"], 0)

    def test_no_blocked_work_is_clean(self) -> None:
        result = evaluate_blocked_attention(
            {
                "questions": [],
                "experiments": [
                    {
                        "id": "X000001",
                        "status": "completed",
                    }
                ],
            }
        )

        self.assertEqual(result["outcome"], "no_blocked_work")
        self.assertEqual(result["blocked_experiment_count"], 0)


if __name__ == "__main__":
    unittest.main()
