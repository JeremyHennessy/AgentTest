"""Genuine original-World API integration checks, copies only."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from agenttest.action_lab import ACTION_ORDER, STATEFUL_WORLD_VERSION, TRANSFER_WORLD_VERSION, apply_bounded_action
from agenttest.state import initial_state
from phase42_original_copy_bridge import probe_original_copy, _evidence, VERSION


def observed_row(identifier="PX000001", before=None, action="north"):
    before = list(before or [0, 0])
    after = apply_bounded_action(
        before, action, world_version=STATEFUL_WORLD_VERSION,
    )
    return {
        "source": "planning_lab",
        "source_id": identifier,
        "world_version": STATEFUL_WORLD_VERSION,
        "action": action,
        "before": before,
        "after": after["after"],
        "blocked": after["blocked"],
    }


class OriginalWorldCopyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.state = initial_state()
        self.state["cycles"] = 10
        self.state["generation"] = 10

    def test_executed_action_is_selected_inquiry_action(self):
        baseline = deepcopy(self.state)
        result = probe_original_copy(self.state, request_id="original-copy-1")
        self.assertEqual(self.state, baseline)
        self.assertEqual(result["status"], "executed_on_copy")
        self.assertEqual(result["version"], VERSION)
        self.assertIn(result["execution"]["action"], ACTION_ORDER)
        self.assertEqual(result["execution"]["action"],
                         result["provenance"]["candidate_selection"]["command"]["action"])
        self.assertEqual(result["execution"]["attempt_id"], "original-copy-1")
        self.assertTrue(result["case_id"].startswith("P42C-"))
        lab = result["state"]["planning_lab"]
        self.assertEqual(lab["executions"][-1]["case_id"], result["case_id"])
        self.assertEqual(lab["transition_observations"][-1]["source"], "investigation_action")
        self.assertEqual(lab["transition_observations"][-1]["source_id"], result["execution"]["id"])
        self.assertEqual(lab["last_action_cycle"], 10)

    def test_same_copy_cycle_cannot_consume_another_action(self):
        result = probe_original_copy(self.state, request_id="step-A")
        original = deepcopy(result["state"])
        with self.assertRaisesRegex(ValueError, "already consumed"):
            probe_original_copy(result["state"], request_id="step-B")
        self.assertEqual(result["state"], original)

    def test_default_refuses_to_interrupt_existing_goal(self):
        lab = self.state["planning_lab"]
        lab["goals"] = [{"id": "PG1", "status": "active", "target": [2, 2]}]
        lab["active_goal_id"] = "PG1"
        lab["plans"] = [{"id": "PP1", "status": "active", "actions": ["east"],
                         "next_step_index": 0}]
        lab["active_plan_id"] = "PP1"
        baseline = deepcopy(self.state)
        result = probe_original_copy(self.state, request_id="guarded")
        self.assertEqual(result["status"], "abstained_active_commitment")
        self.assertEqual(result["state"], baseline)
        self.assertIsNone(result["execution"])
        self.assertTrue(result["provenance"]["active_commitment_present"])
        self.assertEqual(self.state, baseline)

    def test_explicit_copy_interruption_exposes_displaced_plan(self):
        lab = self.state["planning_lab"]
        lab["goals"] = [{"id": "PG1", "status": "active", "target": [2, 2]}]
        lab["active_goal_id"] = "PG1"
        lab["plans"] = [{"id": "PP1", "status": "active", "actions": ["east"],
                         "next_step_index": 0}]
        lab["active_plan_id"] = "PP1"
        before = deepcopy(self.state)
        result = probe_original_copy(
            self.state, request_id="copy-interrupt",
            permit_commitment_interruption=True,
        )
        self.assertEqual(self.state, before)
        self.assertEqual(result["status"], "executed_on_copy")
        self.assertEqual(result["execution"]["displaced_plan_id"], "PP1")
        lab_after = result["state"]["planning_lab"]
        self.assertEqual(lab_after["plans"][0]["status"], "invalidated")
        self.assertEqual(lab_after["plans"][0]["invalidation_reason"],
                         "investigation_action_changed_state")
        self.assertEqual(lab_after["active_goal_id"], "PG1")
        self.assertIsNone(lab_after["active_plan_id"])

    def test_inherited_real_evidence_influences_selection(self):
        lab = self.state["planning_lab"]
        lab["position"] = [1, 0]
        lab["visit_counts"]["1,0"] = 1
        lab["transition_observations"] = [observed_row()]
        original = deepcopy(self.state)
        result = probe_original_copy(self.state, request_id="inherit-evidence")
        self.assertEqual(result["provenance"]["inherited_source_rows_used"], 1)
        selected = result["provenance"]["candidate_selection"]
        self.assertEqual(selected["command"]["action"], "north")
        self.assertEqual(selected["inquiry_mode"], "test_cross_context_prediction")
        self.assertEqual(selected["forecast"]["family_samples"], 1)
        self.assertEqual(self.state, original)

    def test_ambiguous_old_action_evidence_rejected(self):
        lab = self.state["planning_lab"]
        bad = observed_row()
        bad["after"] = [2, 2]
        lab["transition_observations"] = [bad]
        before = deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, "fails protected replay"):
            probe_original_copy(self.state, request_id="bad-history")
        self.assertEqual(self.state, before)

    def test_duplicate_original_receipts_rejected(self):
        self.state["planning_lab"]["transition_observations"] = [
            observed_row(), observed_row(),
        ]
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            probe_original_copy(self.state, request_id="duplicate-old")

    def test_incompatible_world_evidence_is_not_silently_converted(self):
        obsolete = observed_row()
        obsolete["world_version"] = TRANSFER_WORLD_VERSION
        self.state["planning_lab"]["transition_observations"] = [obsolete]
        result = probe_original_copy(self.state, request_id="different-world")
        self.assertEqual(result["provenance"]["inherited_source_rows_used"], 0)
        self.assertEqual(result["provenance"]["incompatible_world_rows_preserved_not_imported"], 1)
        self.assertEqual(result["state"]["planning_lab"]["transition_observations"][0], obsolete)

    def test_full_history_window_keeps_prior_records_and_future_forecast_bounded(self):
        lab = self.state["planning_lab"]
        lab["position"] = [1, 0]
        lab["transition_observations"] = [
            observed_row(identifier=f"PX{i:06d}") for i in range(1, 259)
        ]
        before = deepcopy(self.state)
        result = probe_original_copy(self.state, request_id="bounded-window")
        self.assertEqual(result["provenance"]["inherited_source_rows_used"], 256)
        self.assertEqual(result["provenance"]["earlier_compatible_rows_preserved_but_outside_window"], 2)
        self.assertGreaterEqual(
            result["postaction_forecast_for_same_original_context"]["family_samples"], 0,
        )
        self.assertEqual(self.state, before)
        self.assertEqual(len(result["state"]["planning_lab"]["transition_observations"]), 259)

    def test_old_or_current_request_cannot_be_replayed(self):
        self.state["planning_lab"]["executions"] = [{"id": "PX1", "attempt_id": "already"}]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            probe_original_copy(self.state, request_id="already")
        for invalid in ("", "a b", "../../evil"):
            with self.assertRaises(ValueError):
                probe_original_copy(self.state, request_id=invalid)

    def test_invalid_world_or_existing_current_action_rejected(self):
        self.state["planning_lab"]["world_version"] = TRANSFER_WORLD_VERSION
        with self.assertRaisesRegex(ValueError, "unsupported"):
            probe_original_copy(self.state, request_id="no")
        self.state["planning_lab"]["world_version"] = STATEFUL_WORLD_VERSION
        self.state["planning_lab"]["last_action_cycle"] = 10
        with self.assertRaisesRegex(ValueError, "already consumed"):
            probe_original_copy(self.state, request_id="no-2")


if __name__ == "__main__":
    unittest.main()
