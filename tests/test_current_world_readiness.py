"""Schema-capacity and read-only precheck controls; no live admission evidence."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from agenttest.current_world_investigation import (
    ACTION_ALLOWANCE, CHECKPOINT_BYTES, MAX_OBSERVATIONS,
    consume_prepared_case, current_view, prepare_next_case,
)
from agenttest.grounded_policy import policy
from agenttest.grounded_policy.primitives import Conflict, canonical
from agenttest.planning_lab import execute_investigation_action, initial_planning_lab_state
from agenttest.state import initial_state
from scripts.current_world_readiness import inspect_full_state


def capacity_fixture(count, *, exact_context=False):
    """Authored record-size control, not historical/scientific observation data."""
    state = initial_state()
    state["planning_lab"] = initial_planning_lab_state()
    setup = ["north", "north", "north", "south", "south"] * 6 + ["north", "south"]
    for cycle, action in enumerate(setup, 1):
        state["cycles"] = cycle
        execute_investigation_action(state, action=action,
            case_id=f"capacity-setup:{cycle}", attempt_id=f"capacity-setup:{cycle}")
    lab = state["planning_lab"]
    source = "planning_lab"
    prefix = "X" * (128 - len(source) - 1 - 6)
    for index, row in enumerate(lab["transition_observations"], 1):
        row["source"], row["source_id"] = source, prefix + f"{index:06d}"
    for index in range(33, count + 1):
        # Explicit authored schema rows make maximum identifier storage and
        # exact-arithmetic rejection measurable without thousands of actions.
        lab["transition_observations"].append({
            "source": source, "source_id": prefix + f"{index:06d}", "cycle": index,
            "world_version": lab["world_version"],
            "action": "north" if exact_context else "west",
            "before": [0, 0] if exact_context else [-2, 2],
            "after": [1, 0] if exact_context else [-2, 2],
            "delta": [1, 0] if exact_context else [0, 0], "blocked": not exact_context,
        })
    state["cycles"] = state["generation"] = count
    return state


class CurrentWorldReadiness(unittest.TestCase):
    def test_8192_rows_retained_8193_rejected_and_completion_slots_reserved(self):
        self.assertEqual(MAX_OBSERVATIONS, 8192)
        state = capacity_fixture(MAX_OBSERVATIONS)
        original = canonical(state["planning_lab"]["transition_observations"])
        self.assertEqual(len(current_view(state)["rows"]), MAX_OBSERVATIONS)
        prepared = prepare_next_case(state, request_id="capacity:full")
        self.assertEqual(prepared["status"], "blocked")
        self.assertEqual(prepared["reason"], "insufficient_observation_completion_reserve")
        self.assertEqual(canonical(state["planning_lab"]["transition_observations"]), original)
        row = deepcopy(state["planning_lab"]["transition_observations"][-1])
        row["source_id"] = "overflow"
        state["planning_lab"]["transition_observations"].append(row)
        with self.assertRaisesRegex(Conflict, "current_observation_capacity_exhausted"):
            current_view(state)

    def test_two_owned_completions_with_longest_ids_fit_unchanged_checkpoint(self):
        state = capacity_fixture(MAX_OBSERVATIONS - ACTION_ALLOWANCE)
        original = deepcopy(state["planning_lab"]["transition_observations"])
        self.assertEqual(len(current_view(state)["rows"][0]["event_id"]), 128)
        prepared = prepare_next_case(state, request_id="capacity:prepare")
        self.assertEqual(prepared["status"], "prepared")
        for index in (1, 2):
            state["cycles"] += 1
            result = consume_prepared_case(state, request_id=f"capacity:action{index}")
            self.assertEqual(result["action"], "north")
            prepared = prepare_next_case(state, request_id=f"capacity:action{index}")
            self.assertLessEqual(len(canonical(state["current_world_investigation"])), CHECKPOINT_BYTES)
        self.assertEqual(prepared["status"], "exhausted")
        self.assertEqual(len(state["planning_lab"]["transition_observations"]), MAX_OBSERVATIONS)
        self.assertEqual(state["planning_lab"]["transition_observations"][:len(original)], original)
        self.assertEqual(CHECKPOINT_BYTES, 4 * 1024 * 1024)

    def test_complete_history_inspection_is_read_only_and_reports_full_count(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "organism.json"
            payload = canonical(capacity_fixture(6330))
            path.write_bytes(payload)
            with patch("agenttest.current_world_investigation.execute_investigation_action",
                       side_effect=AssertionError("readiness must not call actuator")), \
                 patch("agenttest.current_world_investigation.consume_prepared_case",
                       side_effect=AssertionError("readiness must not consume authority")):
                report = inspect_full_state(path, hashlib.sha256(payload).hexdigest())
            self.assertTrue(report["complete_history_evaluated"])
            self.assertTrue(report["source_unchanged"])
            self.assertEqual(len(report["candidate_execution_hash"]), 64)
            self.assertEqual(report["unique_same_world_rows"], 6330)
            self.assertEqual(report["evidence_rows"], 6330 - 32)
            self.assertEqual(report["maximum_event_id_length"], 128)
            self.assertFalse(report["action_executed"])
            self.assertFalse(report["activation_performed"])
            self.assertEqual(path.read_bytes(), payload)
            with self.assertRaisesRegex(Conflict, "sha256_mismatch"):
                inspect_full_state(path, "0" * 64)
            projection = canonical({"format": "current-runtime-projection-v1", "state": {"cycles": 6500},
                                    "planning_lab": {"transition_observations": []}})
            path.write_bytes(projection)
            with self.assertRaisesRegex(Conflict, "sampled_projection_rejected"):
                inspect_full_state(path, hashlib.sha256(projection).hexdigest())

    def test_cli_cannot_overwrite_journal_or_its_hardlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "organism.json"
            payload = canonical(capacity_fixture(32))
            source.write_bytes(payload)
            journal = root / "journal.jsonl"
            journal.write_bytes(b'{"event":"historical"}\n')
            alias = root / "journal-alias.json"
            alias.hardlink_to(journal)
            repo = Path(__file__).resolve().parents[1]
            for output in (journal, alias, source):
                result = subprocess.run([sys.executable, "-B", str(repo / "scripts/current_world_readiness.py"),
                    "--state", str(source), "--expected-sha256", hashlib.sha256(payload).hexdigest(),
                    "--output", str(output)], capture_output=True, text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(repo / "src")})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("readiness_output_must_not_alias_state_or_journal", result.stderr)
            self.assertEqual(source.read_bytes(), payload)
            self.assertEqual(journal.read_bytes(), b'{"event":"historical"}\n')

    def test_exact_rational_overflow_stays_blocked_without_tuning_or_truncation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "organism.json"
            payload = canonical(capacity_fixture(332, exact_context=True))
            path.write_bytes(payload)
            report = inspect_full_state(path, hashlib.sha256(payload).hexdigest())
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["reason"], "rational_component_overflow")
            self.assertEqual(report["exact_context_evidence_counts"]["north"], 300)
            self.assertFalse(report["complete_history_evaluated"])
            self.assertEqual(policy.RATIONAL_DIGITS, 256)
            self.assertEqual(path.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
