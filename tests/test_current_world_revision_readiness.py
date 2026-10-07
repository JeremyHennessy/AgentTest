"""Read-only revision preflight controls using authored, non-live fixtures."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agenttest.current_world_investigation import (
    CHECKPOINT_BYTES, LEGACY_VERSION, current_view, disable_prepared_case, prepare_next_case,
)
from agenttest.grounded_policy.primitives import canonical, digest
from agenttest.planning_lab import execute_investigation_action, initial_planning_lab_state
from agenttest.state import initial_state
from scripts.current_world_readiness import inspect_full_state


def revision_fixture(*, disabled=False):
    """The original prefix has no blocked outcomes; later observations add one."""
    state = initial_state()
    state["planning_lab"] = initial_planning_lab_state()
    for action in ["north", "south"] * 16:
        state["cycles"] += 1
        execute_investigation_action(state, action=action,
            case_id=f"revision-setup:{state['cycles']}", attempt_id=f"revision-setup:{state['cycles']}")
    result = prepare_next_case(state, request_id="revision:original")
    if result["status"] != "null":
        raise AssertionError("fixture must preserve an original null case")
    # Reproduce the preserved v1 checkpoint envelope; the frozen case is unchanged.
    state["current_world_investigation"]["version"] = LEGACY_VERSION
    if disabled:
        disable_prepared_case(state)
    for action in ["north", "north", "north", "south", "south"] + ["east", "west"] * 8:
        state["cycles"] += 1
        execute_investigation_action(state, action=action,
            case_id=f"revision-later:{state['cycles']}", attempt_id=f"revision-later:{state['cycles']}")
    return state


class CurrentWorldRevisionReadiness(unittest.TestCase):
    def inspect(self, state):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "organism.json"
            payload = canonical(state)
            source.write_bytes(payload)
            with patch("agenttest.current_world_investigation.execute_investigation_action",
                       side_effect=AssertionError("preflight must not call the actuator")), \
                 patch("agenttest.current_world_investigation.consume_prepared_case",
                       side_effect=AssertionError("preflight must not consume authority")), \
                 patch("agenttest.state.StateStore",
                       side_effect=AssertionError("preflight must not open a writable store")):
                report = inspect_full_state(source, hashlib.sha256(payload).hexdigest())
            self.assertEqual(source.read_bytes(), payload)
            self.assertEqual(report["state_sha256"], report["state_sha256_after"])
            self.assertTrue(report["source_unchanged"])
            self.assertFalse(report["action_executed"])
            self.assertFalse(report["activation_performed"])
            return report

    def test_null_and_disabled_originals_report_complete_disjoint_revision_partition(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                state = revision_fixture(disabled=disabled)
                before = canonical(state)
                lane = state["current_world_investigation"]
                original = deepcopy(lane["cases"][0])
                rows = current_view(state)["rows"]
                report = self.inspect(state)
                self.assertEqual(canonical(state), before)
                self.assertEqual(report["status"], "prepared")
                self.assertEqual(report["decision_status"], "selected")
                self.assertTrue(report["complete_history_evaluated"])
                self.assertTrue(report["new_case_prepared"])
                self.assertTrue(report["discovery_revision_appended"])
                self.assertTrue(report["original_records_preserved"])
                preserved = report["old_case_preservation"][0]
                self.assertTrue(preserved["canonical_body_unchanged"])
                self.assertEqual(preserved["sha256_before"], digest(original))
                self.assertEqual(preserved["sha256_after"], digest(original))
                self.assertEqual(preserved["case_hash_before"], original["case_hash"])
                self.assertEqual(preserved["case_hash_after"], original["case_hash"])
                discovery_ids, evidence_ids = report["discovery_event_ids"], report["evidence_event_ids"]
                self.assertEqual(len(discovery_ids), report["discovery_rows"])
                self.assertEqual(len(evidence_ids), report["evidence_rows"])
                self.assertFalse(set(discovery_ids) & set(evidence_ids))
                self.assertEqual(set(discovery_ids) | set(evidence_ids), {row["event_id"] for row in rows})
                self.assertEqual(evidence_ids, [row["event_id"] for row in rows if row["event_id"] not in discovery_ids])
                self.assertTrue(report["promoted_event_ids"])
                self.assertTrue(set(report["promoted_event_ids"]) <= set(discovery_ids))
                self.assertFalse(set(report["promoted_event_ids"]) & set(evidence_ids))
                self.assertEqual(report["source_row_count"], len(rows))
                self.assertEqual(report["source_rows_hash"], digest([
                    {"event_id": row["event_id"], "sha256": digest(row)} for row in rows]))
                self.assertEqual(report["revision_source_rows_hash"], report["source_rows_hash"])
                self.assertEqual(report["parent_discovery_hash"], digest(lane["discovery"]))
                self.assertEqual(report["parent_cohort_hash"], lane["cohort"]["cohort_digest"])
                self.assertTrue(report["new_model_structures"])
                self.assertLessEqual(report["checkpoint_bytes"], CHECKPOINT_BYTES)
                self.assertLessEqual(report["maximum_serialized_rational_digits"], report["bounds"]["rational_digits"])

    def test_already_revised_snapshot_does_not_claim_new_evaluation_or_revision(self):
        state = revision_fixture()
        self.assertEqual(prepare_next_case(state, request_id="revision:once")["status"], "prepared")
        before = canonical(state)
        report = self.inspect(state)
        self.assertEqual(canonical(state), before)
        self.assertTrue(report["original_records_preserved"])
        self.assertEqual(len(report["old_case_preservation"]), 2)
        self.assertFalse(report["new_case_prepared"])
        self.assertFalse(report["discovery_revision_appended"])
        self.assertFalse(report["complete_history_evaluated"])
        self.assertNotEqual(report["decision_status"], "selected")
        self.assertEqual(report["case_count_before"], report["case_count_after"])
        self.assertEqual(report["discovery_revision_count_before"], 1)
        self.assertEqual(report["discovery_revision_count_after"], 1)
        self.assertEqual(report["newly_promoted_event_ids"], [])
        self.assertEqual(report["promoted_event_ids"], [ref["event_id"] for ref in
            state["current_world_investigation"]["discovery_revisions"][0]["promoted_refs"]])

    def test_existing_record_mutation_is_blocked_by_literal_body_comparison(self):
        state = revision_fixture()
        def corrupt_original(observed, *, request_id):
            result = prepare_next_case(observed, request_id=request_id)
            observed["current_world_investigation"]["cases"][0]["question"] = "changed"
            return result
        with patch("scripts.current_world_readiness.prepare_next_case", side_effect=corrupt_original):
            report = self.inspect(state)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason"], "readiness_original_records_changed")
        self.assertFalse(report["original_records_preserved"])
        self.assertFalse(report["old_case_preservation"][0]["canonical_body_unchanged"])

    def test_oversized_existing_checkpoint_is_rejected_before_preparation(self):
        state = revision_fixture()
        state["current_world_investigation"]["oversized"] = "x" * CHECKPOINT_BYTES
        with patch("scripts.current_world_readiness.prepare_next_case",
                   side_effect=AssertionError("oversized lane must not be prepared")):
            report = self.inspect(state)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("checkpoint exceeds schema byte bound", report["reason"])

    def test_cli_protects_journal_in_real_parent_of_symlinked_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real, visible = root / "real", root / "visible"
            real.mkdir()
            visible.mkdir()
            source = real / "organism.json"
            payload = canonical(revision_fixture())
            source.write_bytes(payload)
            alias = visible / "organism.json"
            alias.symlink_to(source)
            journal = real / "journal.jsonl"
            journal_payload = b'{"historical":"unchanged"}\n'
            journal.write_bytes(journal_payload)
            hardlink = visible / "output.json"
            hardlink.hardlink_to(journal)
            repo = Path(__file__).resolve().parents[1]
            for output in (journal, hardlink):
                result = subprocess.run([sys.executable, "-B", str(repo / "scripts/current_world_readiness.py"),
                    "--state", str(alias), "--expected-sha256", hashlib.sha256(payload).hexdigest(),
                    "--output", str(output)], capture_output=True, text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(repo / "src")})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("readiness_output_must_not_alias_state_or_journal", result.stderr)
            self.assertEqual(source.read_bytes(), payload)
            self.assertEqual(journal.read_bytes(), journal_payload)


if __name__ == "__main__":
    unittest.main()
