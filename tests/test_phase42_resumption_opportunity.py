from __future__ import annotations

import copy
import unittest

from scripts.phase42_resumption_opportunity_eval import evaluate_resumption_opportunities


class Phase42ResumptionOpportunityDiagnosticTests(unittest.TestCase):
    def _decision(self, *, opportunity=True, selected=False) -> dict:
        return {
            "id": "AD11",
            "cycle": 11,
            "previous_foreground_thread_id": "AT2",
            "selected_thread_id": "AT1" if selected else "AT2",
            "resumed_thread_id": "AT1" if selected else None,
            "foreground_changed": selected,
            "selected": {"question_id": "Q1" if selected else "Q2", "priority_score": 1.1 if selected else 0.9},
            "candidate_telemetry": [
                {
                    "thread_id": "AT1",
                    "question_id": "Q1",
                    "lifecycle_source": "active",
                    "previous_status": "suspended",
                    "status": "foreground" if selected else "suspended",
                    "active_experiment_path": True,
                    "newly_executable": opportunity,
                    "new_evidence_refs": [],
                    "priority_score": 1.1 if selected else 0.8,
                    "selected": selected,
                    "resumption_opportunity": opportunity,
                }
            ],
        }

    def test_decision_time_opportunity_below_foreground_is_classified(self) -> None:
        state = {"agenda": {"decisions": [self._decision()]}}
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["diagnostic_version"], "phase42-resumption-opportunities-v2")
        self.assertEqual(result["telemetry_decision_count"], 1)
        self.assertEqual(result["opportunity_count"], 1)
        self.assertEqual(result["lower_priority_opportunity_count"], 1)

    def test_decision_time_resume_is_classified(self) -> None:
        state = {"agenda": {"decisions": [self._decision(selected=True)]}}
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["resumed_opportunity_count"], 1)
        self.assertEqual(result["handoff_or_selection_mismatch_count"], 0)

    def test_expected_resume_without_selection_is_flagged(self) -> None:
        decision = self._decision()
        decision["candidate_telemetry"][0]["priority_score"] = 1.1
        state = {"agenda": {"decisions": [decision]}}
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["handoff_or_selection_mismatch_count"], 1)
        self.assertTrue(result["opportunities"][0]["should_resume"])

    def test_non_opportunity_is_not_counted(self) -> None:
        state = {"agenda": {"decisions": [self._decision(opportunity=False)]}}
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["opportunity_count"], 0)

    def test_pre_telemetry_decisions_are_not_reconstructed(self) -> None:
        old = {"id": "AD10", "cycle": 10, "candidate_summaries": [{"question_id": "Q1", "new_evidence_refs": ["E1"]}]}
        state = {"agenda": {"decisions": [old, self._decision(opportunity=False)]}}
        result = evaluate_resumption_opportunities(state)
        self.assertEqual(result["retained_decision_count"], 2)
        self.assertEqual(result["telemetry_decision_count"], 1)
        self.assertEqual(result["pre_telemetry_decision_count"], 1)
        self.assertEqual(result["opportunity_count"], 0)

    def test_diagnostic_does_not_mutate_state(self) -> None:
        state = {"agenda": {"decisions": [self._decision()]}}
        before = copy.deepcopy(state)
        evaluate_resumption_opportunities(state)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
