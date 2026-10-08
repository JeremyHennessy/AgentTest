"""Software ownership/commit checks, never evidence of natural learning.

Synthetic fixtures obtain every transition from the real bounded actuator.
Local bare Git remotes model claim/final push and fresh GitHub runner snapshots.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agenttest.action_lab import BASE_WORLD_VERSION, TRANSFER_WORLD_VERSION
from agenttest.core import AgentCore
from agenttest.current_world_investigation import (
    ACTION_ALLOWANCE, consume_prepared_case, current_view, prepare_next_case,
)
from agenttest.grounded_policy.primitives import Conflict, canonical
from agenttest.heartbeat_claim import (
    DEFAULT_PAYLOAD, abandon_heartbeat, claim_heartbeat, verify_completed,
)
from agenttest.planning_lab import initial_planning_lab_state, execute_investigation_action
from agenttest.state import StateStore, initial_state

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = {**DEFAULT_PAYLOAD, "observation_supplied": False}


def selected_fixture():
    state = initial_state()
    state["planning_lab"] = initial_planning_lab_state()
    for cycle, action in enumerate(("north", "north", "north", "south", "south"), 1):
        state["cycles"] = state["generation"] = cycle
        execute_investigation_action(state, action=action,
            case_id=f"synthetic-setup:{cycle}", attempt_id=f"synthetic-setup:{cycle}")
    return state


class CurrentWorldOwnership(unittest.TestCase):
    def test_authentic_selection_owns_one_action_and_belief(self):
        state = selected_fixture()
        original = deepcopy(state["planning_lab"])
        preparation = prepare_next_case(state, request_id="heartbeat:1")
        self.assertEqual(preparation["selected_action"], "north")
        self.assertEqual(state["planning_lab"], original)
        state["cycles"] += 1
        result = consume_prepared_case(state, request_id="heartbeat:2")
        self.assertEqual(result["action"], "north")
        self.assertEqual(result["before"], [0, 0])
        self.assertEqual(result["after"], [1, 0])
        lane = state["current_world_investigation"]
        self.assertEqual(lane["actions_remaining"], ACTION_ALLOWANCE - 1)
        self.assertEqual(len(lane["attempts"]), 1)
        self.assertEqual(len(lane["outcomes"]), 1)
        self.assertEqual(len(lane["beliefs"]), 1)
        self.assertEqual(lane["attempts"][0]["case_id"], preparation["case_id"])
        self.assertEqual(len(state["planning_lab"]["executions"]), len(original["executions"]) + 1)
        self.assertIsNone(consume_prepared_case(state, request_id="heartbeat:3")["action"])

    def test_missing_stale_null_or_changed_owner_never_moves(self):
        for mutation in ("missing", "owner", "world", "evidence", "same_tick"):
            with self.subTest(mutation=mutation):
                state = selected_fixture()
                prepare_next_case(state, request_id="heartbeat:1")
                state["cycles"] += mutation != "same_tick"
                lane = state["current_world_investigation"]
                if mutation == "missing": lane["pending_authority"] = None
                if mutation == "owner": lane["pending_authority"]["owner"] = "legacy-agenda-winner"
                if mutation == "world": state["planning_lab"]["position"] = [1, 0]
                if mutation == "evidence": state["planning_lab"]["transition_observations"][0]["extra"] = "changed"
                before = deepcopy(state["planning_lab"])
                self.assertIsNone(consume_prepared_case(state, request_id="heartbeat:2")["action"])
                self.assertEqual(state["planning_lab"], before)
        state = selected_fixture()
        prepare_next_case(state, request_id="heartbeat:version")
        state["cycles"] += 1
        before = deepcopy(state["planning_lab"])
        with patch("agenttest.current_world_investigation.execution_hash", return_value="changed-code"):
            result = consume_prepared_case(state, request_id="heartbeat:after-upgrade")
        self.assertEqual(result["reason"], "prepared_execution_version_changed")
        self.assertEqual(state["planning_lab"], before)
        state = initial_state()
        state["planning_lab"] = initial_planning_lab_state()
        self.assertEqual(prepare_next_case(state, request_id="heartbeat:empty")["status"], "null")
        self.assertEqual(state["current_world_investigation"]["discovery"], [])
        self.assertIsNone(consume_prepared_case(state, request_id="heartbeat:next")["action"])

    def test_exact_duplicates_deduplicate_and_changed_bodies_fail(self):
        state = selected_fixture()
        lab = state["planning_lab"]
        expected = current_view(state)
        lab["transition_observations"].append(deepcopy(lab["transition_observations"][0]))
        self.assertEqual(current_view(state), expected)
        lab["transition_observations"][-1]["blocked"] = True
        with self.assertRaisesRegex(Conflict, "conflicting_transition_source_body"):
            current_view(state)

    def test_base_and_transfer_observations_are_excluded_and_fields_unavailable(self):
        state = selected_fixture()
        expected = current_view(state)
        for world in (BASE_WORLD_VERSION, TRANSFER_WORLD_VERSION):
            row = deepcopy(state["planning_lab"]["transition_observations"][0])
            row["world_version"] = world
            state["planning_lab"]["transition_observations"].append(row)
        self.assertEqual(current_view(state), expected)
        for row in expected["rows"]:
            self.assertIsNone(row["before_context"]["inventory_ids"])
            self.assertIsNone(row["before_context"]["visible_ids"])

    def test_frozen_discovery_remains_distinct_after_owned_outcome(self):
        state = selected_fixture()
        prepare_next_case(state, request_id="heartbeat:1")
        discovery = deepcopy(state["current_world_investigation"]["discovery"])
        state["cycles"] += 1
        consume_prepared_case(state, request_id="heartbeat:2")
        preparation = prepare_next_case(state, request_id="heartbeat:2")
        self.assertEqual(preparation["status"], "prepared")
        lane = state["current_world_investigation"]
        self.assertEqual(lane["discovery"], discovery)
        evidence_ids = {row["event_id"] for row in lane["cases"][-1]["evidence_refs"]}
        self.assertEqual(len(evidence_ids), 1)
        self.assertFalse(evidence_ids & {row["event_id"] for row in discovery})


class CurrentWorldRemoteCommit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        self.runner = self.root / "runner1"
        self.runner.mkdir()
        self.git("init", "-b", "autonomous/growth")
        self.git("config", "user.name", "Software fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("remote", "add", "origin", str(self.remote))
        self.path = self.runner / "state/organism.json"
        self.store = StateStore(self.path)
        self.store.save(selected_fixture())
        self.store.journal_path.write_text("")
        self.publish()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.runner), *args], stderr=subprocess.PIPE).decode().strip()

    def publish(self):
        self.git("add", "state")
        self.git("commit", "-m", "Software fixture snapshot")
        self.git("push", "-u", "origin", "autonomous/growth")
        self.git("fetch", "origin", "autonomous/growth:refs/remotes/origin/autonomous/growth")
        return self.git("rev-parse", "HEAD")

    def claim(self, request):
        result = claim_heartbeat(self.path, request, payload=PAYLOAD)
        self.assertEqual(result["status"], "created")
        return self.publish()

    def cycle(self, request, commit):
        return AgentCore(self.store).cycle(stimulus="autonomous heartbeat",
            strict_experiment_admission=True, planning_lab=True,
            current_world_investigation=True, heartbeat_request_id=request,
            heartbeat_claim_commit=commit, _now_override="2026-10-07T00:00:00+00:00")

    def fresh_runner(self, name):
        target = self.root / name
        subprocess.run(["git", "clone", "--branch", "autonomous/growth", str(self.remote), str(target)], check=True, capture_output=True)
        self.runner, self.path = target, target / "state/organism.json"
        self.store = StateStore(self.path)
        self.git("config", "user.name", "Software fixture")
        self.git("config", "user.email", "fixture@example.invalid")

    def test_first_tick_prepares_then_fresh_runner_consumes_once(self):
        commit = self.claim("heartbeat:1")
        original_count = len(self.store.load()["planning_lab"]["executions"])
        result = self.cycle("heartbeat:1", commit)
        self.assertIsNone(result["planning_lab_result"]["action"])
        self.assertEqual(result["current_world_preparation"]["status"], "prepared")
        verify_completed(self.path, "heartbeat:1", require_current=True)
        self.publish()
        self.fresh_runner("runner2")
        commit = self.claim("heartbeat:2")
        result = self.cycle("heartbeat:2", commit)
        self.assertEqual(result["planning_lab_result"]["action"], "north")
        self.assertEqual(len(self.store.load()["planning_lab"]["executions"]), original_count + 1)
        verify_completed(self.path, "heartbeat:2", require_current=True)
        self.publish()
        self.fresh_runner("runner3")
        before = self.path.read_bytes(), self.store.journal_path.read_bytes()
        self.assertEqual(claim_heartbeat(self.path, "heartbeat:2", payload=PAYLOAD)["status"], "already_completed")
        self.assertEqual(before, (self.path.read_bytes(), self.store.journal_path.read_bytes()))
        self.assertEqual(claim_heartbeat(self.path, "heartbeat:1", payload=PAYLOAD)["status"], "already_completed")
        with self.assertRaisesRegex(Conflict, "already_completed"):
            self.cycle("heartbeat:2", self.git("rev-parse", "HEAD"))

    def test_completed_claim_remains_verifiable_across_lossless_archive(self):
        # Actual local-Git claim and recorded event, not a synthetic fixture.
        import hashlib
        from agenttest.journal_tail_rotation import logical_digest, rotate, verify

        first_commit = self.claim("heartbeat:1")
        self.cycle("heartbeat:1", first_commit)
        verify_completed(self.path, "heartbeat:1", require_current=True)
        self.publish()
        original = self.store.journal_path.read_bytes()
        original_hash = hashlib.sha256(original).hexdigest()
        state_cycle = self.store.load()["cycles"]
        (self.path.parent / "heartbeat_operation.json").write_text(json.dumps({
            "status": "completed", "result_cycle": state_cycle,
        }))
        self.publish()

        rotate(self.path.parent,
               expected_active_sha256=verify(self.path.parent)["active_sha256"],
               expected_cycle=state_cycle, min_bytes=1)
        self.publish()
        self.assertEqual(self.store.journal_path.read_bytes(), b"")
        self.assertEqual((self.path.parent / "journal-sealed-000001.jsonl").read_bytes(), original)
        self.assertEqual(logical_digest(self.path.parent), (len(original), original_hash))
        self.assertEqual(verify_completed(self.path, "heartbeat:1")["status"], "verified")
        self.assertEqual(claim_heartbeat(self.path, "heartbeat:1", payload=PAYLOAD)["status"], "already_completed")

        second_commit = self.claim("heartbeat:2")
        self.cycle("heartbeat:2", second_commit)
        verify_completed(self.path, "heartbeat:2", require_current=True)
        self.publish()
        self.assertEqual(verify_completed(self.path, "heartbeat:1")["status"], "verified")
        self.assertEqual(verify_completed(self.path, "heartbeat:2")["status"], "verified")

    def test_exact_pending_fresh_process_resume_but_dirty_local_save_fails(self):
        commit = self.claim("heartbeat:1")
        pending = self.path.read_bytes()
        with patch.object(self.store, "append_journal", side_effect=RuntimeError("simulated crash after save")):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                self.cycle("heartbeat:1", commit)
        with self.assertRaisesRegex(Conflict, "journal_event"):
            claim_heartbeat(self.path, "heartbeat:1", payload=PAYLOAD)
        self.fresh_runner("restart")
        self.assertEqual(self.path.read_bytes(), pending)
        self.assertEqual(claim_heartbeat(self.path, "heartbeat:1", payload=PAYLOAD)["status"], "already_claimed")
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
        process = subprocess.run([sys.executable, "-B", "-m", "agenttest", "--state", str(self.path),
            "cycle", "--grounded-experiments-only", "--planning-lab", "--current-world-investigation",
            "--heartbeat-request-id", "heartbeat:1", "--heartbeat-claim-commit", commit,
            "--stimulus", "autonomous heartbeat"], cwd=self.runner, env=env, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        verify_completed(self.path, "heartbeat:1", require_current=True)

    def test_failed_final_push_recomputes_only_uncommitted_movement(self):
        commit = self.claim("heartbeat:prepare")
        self.cycle("heartbeat:prepare", commit)
        self.publish()
        commit = self.claim("heartbeat:move")
        durable_count = len(self.store.load()["planning_lab"]["executions"])
        self.cycle("heartbeat:move", commit)
        # Deliberately leave local result unpublished, modeling lost runner.
        self.fresh_runner("after_failed_final_push")
        self.assertEqual(len(self.store.load()["planning_lab"]["executions"]), durable_count)
        self.assertEqual(claim_heartbeat(self.path, "heartbeat:move", payload=PAYLOAD)["status"], "already_claimed")
        self.cycle("heartbeat:move", commit)
        verify_completed(self.path, "heartbeat:move", require_current=True)
        self.publish()
        self.fresh_runner("after_successful_final_push")
        self.assertEqual(len(self.store.load()["planning_lab"]["executions"]), durable_count + 1)
        self.assertEqual(claim_heartbeat(self.path, "heartbeat:move", payload=PAYLOAD)["status"], "already_completed")

    def test_claim_must_be_remote_clean_and_payload_exact(self):
        result = claim_heartbeat(self.path, "heartbeat:1", payload=PAYLOAD)
        self.assertEqual(result["status"], "created")
        with self.assertRaisesRegex(Conflict, "local_state_differs"):
            self.cycle("heartbeat:1", self.git("rev-parse", "HEAD"))
        commit = self.publish()
        with self.assertRaisesRegex(Conflict, "payload_changed"):
            claim_heartbeat(self.path, "heartbeat:1", payload={**PAYLOAD, "stimulus": "changed"})
        with self.assertRaisesRegex(Conflict, "different_heartbeat"):
            claim_heartbeat(self.path, "heartbeat:2", payload=PAYLOAD)
        (self.runner / "untracked.txt").write_text("interrupted runner")
        with self.assertRaisesRegex(Conflict, "clean_claim_checkout"):
            self.cycle("heartbeat:1", commit)

    def test_missing_duplicate_or_wrong_outcome_journal_cannot_publish(self):
        commit = self.claim("heartbeat:1")
        self.cycle("heartbeat:1", commit)
        journal = self.store.journal_path.read_bytes()
        self.store.journal_path.write_bytes(journal + journal)
        with self.assertRaisesRegex(Conflict, "journal_event"):
            verify_completed(self.path, "heartbeat:1", require_current=True)
        self.store.journal_path.write_bytes(b"")
        with self.assertRaisesRegex(Conflict, "journal_event"):
            verify_completed(self.path, "heartbeat:1", require_current=True)
        self.store.journal_path.write_bytes(journal)
        state = json.loads(self.path.read_bytes())
        state["current_world_investigation"]["cases"][0]["question"] = "changed owner question"
        self.path.write_bytes(canonical(state))
        with self.assertRaisesRegex(Conflict, "case_content_changed"):
            verify_completed(self.path, "heartbeat:1")

    def test_explicit_abandonment_survives_version_change_and_retains_position(self):
        self.claim("heartbeat:1")
        original = self.store.load()["planning_lab"]
        with patch("agenttest.heartbeat_claim.execution_hash", return_value="changed-code"):
            result = abandon_heartbeat(self.path, "heartbeat:1", "operator disabled pending rollout")
        self.assertEqual(result["status"], "abandoned_uncommitted")
        state = self.store.load()
        self.assertEqual(state["planning_lab"], original)
        self.assertEqual(state["current_world_heartbeat"]["abandoned"][0]["claim"]["request_id"], "heartbeat:1")
        with self.assertRaisesRegex(Conflict, "was_abandoned"):
            claim_heartbeat(self.path, "heartbeat:1", payload=PAYLOAD)

    def test_interrupted_claim_blocks_reconciliation_without_mutating_files(self):
        self.claim("heartbeat:1")
        before = self.path.read_bytes(), self.store.journal_path.read_bytes()
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/reconcile_verified_change.py"),
            "--state", str(self.path), "--commit-sha", "a" * 40, "--changed-file", "src/agenttest/core.py",
            "--verify-run-id", "1", "--pr-number", "1", "--attribution-text", "software fixture"],
            env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unfinished_heartbeat", result.stderr)
        self.assertEqual(before, (self.path.read_bytes(), self.store.journal_path.read_bytes()))

    def test_unrelated_interaction_preserves_prepared_case_and_rollback_resumes(self):
        commit = self.claim("heartbeat:1")
        self.cycle("heartbeat:1", commit)
        self.publish()
        prepared = deepcopy(self.store.load()["current_world_investigation"]["pending_authority"])
        AgentCore(self.store).cycle(stimulus="ordinary message")
        self.assertEqual(self.store.load()["current_world_investigation"]["pending_authority"], prepared)
        AgentCore(self.store).cycle(planning_lab=True)
        state = self.store.load()
        self.assertEqual(state["current_world_investigation"]["status"], "disabled")
        self.assertIsNone(state["current_world_investigation"]["pending_authority"])
        self.assertEqual(state["current_world_investigation"]["rollback"]["retired_authority"], prepared)


class CurrentWorldDefaultOff(unittest.TestCase):
    def test_explicit_false_matches_ordinary_core_state_result_and_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            stores = [StateStore(Path(temp) / str(i) / "organism.json") for i in (1, 2)]
            results = []
            seed = selected_fixture()
            with patch("agenttest.state.utc_now", return_value="2026-10-07T00:00:00+00:00"), \
                 patch("agenttest.core.utc_now", return_value="2026-10-07T00:00:00+00:00"):
                for index, store in enumerate(stores):
                    store.save(deepcopy(seed))
                    options = {"current_world_investigation": False} if index else {}
                    results.append(AgentCore(store).cycle(planning_lab=True,
                        _now_override="2026-10-07T00:00:00+00:00", **options))
            self.assertEqual(results[0], results[1])
            self.assertEqual(stores[0].path.read_bytes(), stores[1].path.read_bytes())
            self.assertEqual(stores[0].journal_path.read_bytes(), stores[1].journal_path.read_bytes())
            self.assertNotIn("current_world_investigation", stores[0].load())


if __name__ == "__main__":
    unittest.main()
