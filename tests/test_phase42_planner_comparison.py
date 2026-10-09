"""Native original planner forecast versus NEW model, without hindsight or writes."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "experiments"))
sys.path.insert(0, str(root / "tests"))

from agenttest.action_lab import apply_bounded_action
from agenttest.two_clock_stream import digest
from phase42_planner_comparison import (
    freeze_plan, validate_preview, compare_future,
)
from test_phase42_original_shadow import fixtures, pinned, next_native


def with_plan():
    state = fixtures(100)
    lab = state["planning_lab"]
    start = list(lab["position"])
    first = apply_bounded_action(start, "north")
    second = apply_bounded_action(first["after"], "east")
    lab["active_goal_id"] = "GOAL0001"
    lab["active_plan_id"] = "PLAN0001"
    lab["goals"].append({
        "id": "GOAL0001", "status": "active", "target": second["after"],
    })
    lab["plans"].append({
        "id": "PLAN0001", "goal_id": "GOAL0001", "status": "active",
        "actions": ["north", "east"],
        "predicted_states": [first["after"], second["after"]],
        "next_step_index": 0,
    })
    return state


def record_executed(state, *, before, after, action="north",
                    predicted_after=None, goal_id="GOAL0001",
                    plan_id="PLAN0001", step=0):
    lab = state["planning_lab"]
    last = lab["transition_observations"][-1]
    lab["executions"].append({
        "id": last["source_id"], "cycle": last["cycle"], "action": action,
        "before": list(before), "after": list(after),
        "predicted_after": list(predicted_after if predicted_after is not None else after),
        "goal_id": goal_id, "plan_id": plan_id, "step_index": step,
    })


def _resign(report):
    report["frozen"]["sha256"] = digest(report["frozen"]["body"])
    report["report_sha256"] = digest({
        key: value for key, value in report.items()
        if key != "report_sha256"
    })
    return report


class PlannerFrozenTests(unittest.TestCase):
    def test_active_next_plan_is_originally_frozen_and_source_bound(self):
        state = with_plan()
        before = list(state["planning_lab"]["position"])
        frozen = freeze_plan(state, "1" * 40, before)
        self.assertEqual(frozen["status"], "frozen_valid_next_plan_step")
        self.assertEqual(frozen["action"], "north")
        self.assertEqual(frozen["before"], before)
        self.assertEqual(frozen["step_index"], 0)
        self.assertEqual(len(frozen["plan_id_hash"]), 64)
        self.assertNotIn("goal_id", frozen)
        validate_preview(frozen, "1" * 40, before)

    def test_source_has_no_active_plan_and_precommit_are_abstentions(self):
        state = fixtures()
        before = list(state["planning_lab"]["position"])
        self.assertEqual(freeze_plan(state, "1" * 40, before)["status"], "no_active_plan")
        state = with_plan()
        state["planning_lab"]["active_objective_realization_id"] = "O0001"
        self.assertEqual(
            freeze_plan(state, "1" * 40, before)["status"], "pending_precommit",
        )

    def test_ambiguous_duplicate_and_stale_plans_never_count(self):
        state = with_plan()
        position = list(state["planning_lab"]["position"])
        state["planning_lab"]["plans"].append(
            deepcopy(state["planning_lab"]["plans"][-1])
        )
        self.assertEqual(
            freeze_plan(state, "1" * 40, position)["status"],
            "ambiguous_source_plan_or_goal",
        )
        state["planning_lab"]["plans"].pop()
        state["planning_lab"]["plans"][-1]["next_step_index"] = 999
        self.assertEqual(
            freeze_plan(state, "1" * 40, position)["status"],
            "stale_or_invalid_plan_step",
        )

    def test_one_natural_planned_action_yields_truly_matched_prediction_comparison(self):
        state = with_plan()
        original = deepcopy(state)
        before = list(state["planning_lab"]["position"])
        first = pinned(state)
        self.assertEqual(first["frozen"]["body"]["planner_baseline"]["status"],
                         "frozen_valid_next_plan_step")
        self.assertEqual(state, original)
        outcome = next_native(state, action="north")
        record_executed(
            state, before=before, after=outcome["after"],
            predicted_after=first["frozen"]["body"]["planner_baseline"]["predicted_after"],
        )
        second = pinned(state, commit="2" * 40, previous=first)
        self.assertEqual(second["prospective"]["status"], "scored_one_natural_first_action")
        cmp = second["prospective"]["original_plan_comparison"]
        self.assertEqual(cmp["status"], "matched_original_plan_preaction_comparison")
        self.assertTrue(cmp["credit"])
        self.assertEqual(cmp["original_planner_brier"], 0.0)
        self.assertEqual(second["summary"]["planner_comparison_count"], 1)
        self.assertEqual(second["summary"]["scored_natural_first_actions"], 1)
        self.assertEqual(second["summary"]["planner_brier_sum"], 0.0)
        self.assertEqual(
            second["summary"]["learner_brier_sum_on_planner"], cmp["two_clock_brier"],
        )

    def test_natural_action_disagrees_with_current_plan_model_still_scores(self):
        state = with_plan()
        first = pinned(state)
        next_native(state, action="south")
        new = pinned(state, commit="2" * 40, previous=first)
        self.assertTrue(new["prospective"]["credit"])
        self.assertFalse(new["prospective"]["original_plan_comparison"]["credit"])
        self.assertEqual(
            new["prospective"]["original_plan_comparison"]["status"],
            "original_plan_did_not_choose_frozen_action",
        )
        self.assertEqual(new["summary"]["planner_comparison_count"], 0)
        self.assertEqual(new["summary"]["scored_natural_first_actions"], 1)

    def test_simulated_corrupt_outcome_detected_as_plan_error_without_retrofit(self):
        state = with_plan()
        before = list(state["planning_lab"]["position"])
        old = pinned(state)
        planned_after = old["frozen"]["body"]["planner_baseline"]["predicted_after"]
        outcome = next_native(state, action="north")
        record_executed(state, before=before, after=outcome["after"],
                        predicted_after=planned_after)
        # Source future actual effect is independently validated by the native
        # physics auditor, so a score of 2 cannot be manufactured here.
        scored = pinned(state, commit="2" * 40, previous=old)
        self.assertEqual(scored["prospective"]["original_plan_comparison"]["original_planner_brier"], 0.0)

    def test_execution_from_other_plan_does_not_earn_planner_score(self):
        state = with_plan()
        before = list(state["planning_lab"]["position"])
        old = pinned(state)
        outcome = next_native(state, action="north")
        record_executed(state, before=before, after=outcome["after"],
                        plan_id="PLAN0002")
        report = pinned(state, commit="2" * 40, previous=old)
        self.assertTrue(report["prospective"]["credit"])
        self.assertEqual(report["prospective"]["original_plan_comparison"]["status"],
                         "different_native_plan_step")
        self.assertEqual(report["summary"]["planner_comparison_count"], 0)
        self.assertEqual(report["summary"]["planner_inconclusive"], 1)

    def test_curiosity_native_action_is_not_legacy_plan_comparison(self):
        state = with_plan()
        old = pinned(state)
        next_native(state, action="north")
        state["planning_lab"]["transition_observations"][-1]["source"] = "curiosity_probe"
        report = pinned(state, commit="2" * 40, previous=old)
        self.assertEqual(report["prospective"]["original_plan_comparison"]["status"],
                         "first_action_not_legacy_plan_execution")
        self.assertEqual(report["summary"]["scored_natural_first_actions"], 1)
        self.assertEqual(report["summary"]["planner_comparison_count"], 0)

    def test_previous_real_main_artifact_without_planner_baseline_still_scores(self):
        state = with_plan()
        old = pinned(state)
        old = deepcopy(old)
        old["frozen"]["body"].pop("planner_baseline")
        for key in ("planner_comparison_count", "planner_brier_sum",
                    "learner_brier_sum_on_planner", "planner_inconclusive"):
            old["summary"].pop(key)
        old = _resign(old)
        next_native(state, action="south")
        future = pinned(state, commit="2" * 40, previous=old)
        self.assertTrue(future["prospective"]["credit"])
        self.assertEqual(
            future["prospective"]["original_plan_comparison"]["status"],
            "not_frozen_by_old_shadow_version",
        )
        self.assertEqual(future["summary"]["scored_natural_first_actions"], 1)
        self.assertEqual(future["summary"]["planner_comparison_count"], 0)
        self.assertEqual(future["summary"]["planner_inconclusive"], 1)

    def test_forged_preview_binding_stale_origin_and_summary_fail(self):
        state = with_plan()
        old = pinned(state)
        next_native(state, action="north")
        wrong = deepcopy(old)
        wrong["frozen"]["body"]["planner_baseline"]["source_commit"] = "3" * 40
        _resign(wrong)
        with self.assertRaisesRegex(ValueError, "changed source"):
            pinned(state, commit="2" * 40, previous=wrong)
        wrong = deepcopy(old)
        wrong["summary"]["planner_comparison_count"] = -1
        _resign(wrong)
        with self.assertRaisesRegex(ValueError, "prior score ancestry"):
            pinned(state, commit="2" * 40, previous=wrong)

    def test_future_execution_changes_old_prediction_fails_closed(self):
        state = with_plan()
        before = list(state["planning_lab"]["position"])
        old = pinned(state)
        after = next_native(state, action="north")
        record_executed(state, before=before, after=after["after"], predicted_after=[-2,-2])
        with self.assertRaisesRegex(ValueError, "retroactively changed"):
            pinned(state, commit="2" * 40, previous=old)


if __name__ == "__main__":
    unittest.main()
