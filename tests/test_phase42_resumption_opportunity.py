from __future__ import annotations

import copy
import unittest

from scripts.phase42_resumption_opportunity_eval import evaluate_resumption_opportunities


class Phase42ResumptionOpportunityDiagnosticTests(unittest.TestCase):
    def _state(self) -> dict:
        return {
            "agenda": {
                "threads": [
                    {
                        "id": "AT1",
                        "question_id": "Q1",
                        "history": [
                            {
                                "cycle": 10,
                                "from": "foreground",
                                "to": "suspended",
                                "reason": "waiting_for_executable_path_or_new_evidence",
                            }
                        ],
                    },
                    {
                        "id": "AT2",
                        "question_id": "Q2",
                        "history": [],
                    },
                ],
                "decisions": [
                    {
                        "id": "AD11",
                        "cycle": 11,
                        "previous_foreground_thread_id": "AT2",
                        "selected_thread_id": "AT2",
                        "resumed_thread_id": None,
                        "foreground_changed": False,
                        "selected": {"question_id": "Q2", "priority_score": 0.9},
                        "candidate_summaries": [
                            {
                                "question_id": "Q1",
                                "priority_score": 0.8,
                                "active_experiment_path": True,
                                "new_evidence_refs": ["X1"],
                            },
                            {"question_id": "Q2", "priority_score": 0.9},
                        ],
                    }
                ],
            }
        }

    def test_new_evidence_below_foreground_is_classified_not_forced(self) -> None:
        result = evaluate_resumption_opportunities(self._state())
        self.assertEqual(result["opportunity_count"], 1)
        self.assertEqual(result["lower_priority_opportunity_count"], 1)
        self.assertEqual(result["handoff_or_selection_mismatch_count"], 0)

    def test_expected_resume_without_selection_is_flagged(self) -> None:
        state = self._state()
        state["agenda"]["decisions"][0]["candidate_summaries"][0]["priority_score"] = 1.1
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["handoff_or_selection_mismatch_count"], 1)
        self.assertTrue(result["opportunities"][0]["should_resume"])

    def test_real_resume_is_classified(self) -> None:
        state = self._state()
        decision = state["agenda"]["decisions"][0]
        decision["candidate_summaries"][0]["priority_score"] = 1.1
        decision["selected"] = decision["candidate_summaries"][0]
        decision["selected_thread_id"] = "AT1"
        decision["resumed_thread_id"] = "AT1"
        decision["foreground_changed"] = True
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["resumed_opportunity_count"], 1)
        self.assertEqual(result["handoff_or_selection_mismatch_count"], 0)

    def test_no_new_evidence_or_executable_transition_is_not_opportunity(self) -> None:
        state = self._state()
        candidate = state["agenda"]["decisions"][0]["candidate_summaries"][0]
        candidate["new_evidence_refs"] = []
        candidate["active_experiment_path"] = False
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["opportunity_count"], 0)

    def test_diagnostic_does_not_mutate_state(self) -> None:
        state = self._state()
        before = copy.deepcopy(state)
        evaluate_resumption_opportunities(state)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
