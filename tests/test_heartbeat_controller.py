"""Focused decision tests: fake Actions transport, no Core cycles or live dispatch."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("heartbeat_controller", ROOT / "scripts/heartbeat_controller.py")
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)

NOW = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)
TICKET = "heartbeat:v1:" + "a" * 64
NEXT = "heartbeat:v1:" + "b" * 64
SOURCE = "c" * 40
LEGACY_RUN = 37642389633
LEGACY_SOURCE = "7948bdf33f11c5f98bdbdbcb718c04118c7354a4"


def run(run_id=42, workflow="growth.yml", status="completed", conclusion="failure", ticket=TICKET, **overrides):
    value = {
        "id": run_id, "status": status, "conclusion": conclusion if status == "completed" else None,
        "run_attempt": 1, "head_sha": SOURCE, "head_branch": "main", "event": "workflow_dispatch",
        "path": ".github/workflows/" + workflow,
        "display_title": controller.title(workflow, ticket), "created_at": "2026-10-07T17:00:00Z",
    }
    value.update(overrides)
    return value


def pending():
    return {"status": "pending", "next_request_id": TICKET, "request_status": "pending", "ticket_since": "2026-10-07T17:01:00Z", "operation": {
        "status": "pending", "request_id": TICKET, "original_run_id": 42,
        "source_sha": SOURCE, "created_at": "2026-10-07T17:01:00Z",
    }}


def ready():
    return {"status": "ready", "next_request_id": TICKET, "request_status": "unseen", "ticket_since": "2026-10-07T17:01:00Z", "operation": None}


class FakeReceipts:
    def __init__(self, state):
        self.state = state
        self.calls = []
        self.history = {}

    def inspect(self, ticket=""):
        self.calls.append(ticket)
        return deepcopy(self.history.get(ticket, self.state))


class FakeActions:
    def __init__(self):
        self.records = {}
        self.job_records = {}
        self.log_records = {}
        self.dispatches = []
        self.reruns = []
        self.reads = []
        self.verified = SOURCE
        self.lose_ack = False
        self.read_error = False

    def run(self, run_id):
        self.reads.append(("run", run_id))
        if self.read_error:
            raise controller.Blocked("unknown_api_result")
        return controller.validate_run(deepcopy(self.records[run_id]))

    def active(self, workflow, exclude=0):
        self.reads.append(("active", workflow))
        return [deepcopy(item) for item in self.records.values()
                if item["path"] == ".github/workflows/" + workflow and item["status"] in controller.ACTIVE and item["id"] != exclude]

    def runs(self, workflow, **filters):
        self.reads.append(("runs", workflow))
        return [deepcopy(item) for item in self.records.values() if item["path"] == ".github/workflows/" + workflow
                and (filters.get("status") != "failure" or item.get("conclusion") == "failure")]

    def jobs(self, item):
        return deepcopy(self.job_records.get(item["id"], []))

    def job_log(self, job_id):
        self.reads.append(("job_log", job_id))
        return self.log_records[job_id]

    def matching(self, workflow, ticket, since):
        return [deepcopy(item) for item in self.records.values()
                if item["path"] == ".github/workflows/" + workflow and item["display_title"] == controller.title(workflow, ticket)]

    def verified_main(self):
        return self.verified

    def dispatch(self, workflow, ticket):
        self.dispatches.append((workflow, ticket))
        new_id = max(self.records, default=100) + 1
        self.records[new_id] = run(new_id, workflow, "queued", ticket=ticket)
        if self.lose_ack:
            self.lose_ack = False
            raise controller.Blocked("dispatch_response_lost")

    def rerun(self, run_id):
        self.reruns.append(run_id)
        self.records[run_id]["run_attempt"] += 1
        self.records[run_id]["status"] = "queued"
        self.records[run_id]["conclusion"] = None


class HeartbeatSchedulerTests(unittest.TestCase):
    def scheduler(self, state):
        self.actions = FakeActions()
        self.receipts = FakeReceipts(state)
        return controller.Scheduler(self.actions, self.receipts, now=lambda: NOW, sleep=lambda _: None)

    def assert_no_mutation(self):
        self.assertEqual(self.actions.dispatches, [])
        self.assertEqual(self.actions.reruns, [])

    def test_healthy_pending_watchdog_only_reads_recorded_run(self):
        scheduler = self.scheduler(pending())
        self.actions.records[42] = run(status="in_progress")
        self.assertEqual(scheduler.tick("watchdog")["status"], "healthy")
        self.assertEqual(self.actions.reads, [("run", 42)])
        self.assert_no_mutation()

    def test_unknown_api_or_status_fails_closed(self):
        for unknown in ("api", "status"):
            with self.subTest(unknown=unknown):
                scheduler = self.scheduler(pending())
                self.actions.records[42] = run(status="mystery" if unknown == "status" else "completed")
                self.actions.read_error = unknown == "api"
                with self.assertRaises(controller.Blocked):
                    scheduler.tick("watchdog")
                self.assert_no_mutation()

    def test_terminal_pending_resumes_exact_original_source_even_with_new_main(self):
        scheduler = self.scheduler(pending())
        self.actions.records[42] = run()
        original = deepcopy(self.actions.records[42])
        self.actions.verified = "d" * 40
        result = scheduler.tick("watchdog")
        self.assertEqual(result["status"], "resumed")
        self.assertEqual(self.actions.reruns, [42])
        self.assertEqual(self.actions.dispatches, [])
        for key in ("head_sha", "head_branch", "event", "display_title"):
            self.assertEqual(self.actions.records[42][key], original[key])

    def test_pending_source_conflict_never_dispatches_fresh_main(self):
        scheduler = self.scheduler(pending())
        self.actions.records[42] = run(head_sha="d" * 40)
        with self.assertRaisesRegex(controller.Blocked, "identity_conflict"):
            scheduler.tick("watchdog")
        self.assert_no_mutation()

    def test_github_recovery_limits_are_explicitly_blocked(self):
        for overrides, reason in [
            ({"created_at": (NOW - timedelta(days=30)).isoformat()}, "30_day"),
            ({"run_attempt": 50}, "50_attempt"),
        ]:
            with self.subTest(reason=reason):
                scheduler = self.scheduler(pending())
                self.actions.records[42] = run(**overrides)
                with self.assertRaisesRegex(controller.Blocked, reason):
                    scheduler.tick("watchdog")
                self.assert_no_mutation()

    def test_lost_dispatch_ack_is_rediscovered_by_exact_ticket(self):
        scheduler = self.scheduler(ready())
        self.actions.lose_ack = True
        # An unrelated newer run is never evidence that our POST was accepted.
        self.actions.records[90] = run(90, ticket=NEXT)
        result = scheduler.tick("watchdog")
        self.assertEqual(result["status"], "rediscovered")
        self.assertEqual(self.actions.dispatches, [("heartbeat-controller.yml", TICKET)])
        self.assertEqual(scheduler.tick("watchdog")["status"], "healthy")
        self.assertEqual(len(self.actions.dispatches), 1)

    def test_uncertain_dispatch_retry_keeps_one_logical_ticket(self):
        scheduler = self.scheduler(ready())
        calls = []
        def unavailable(workflow, ticket):
            calls.append((workflow, ticket))
            raise controller.Blocked("uncertain_post")
        self.actions.dispatch = unavailable
        with self.assertRaisesRegex(controller.Blocked, "same_ticket_only"):
            scheduler.tick("watchdog")
        self.assertEqual(calls, [("heartbeat-controller.yml", TICKET)] * 2)

    def test_unrelated_old_success_cannot_complete_dispatched_ticket(self):
        scheduler = self.scheduler(ready())
        phases = []
        def advance(_):
            phases.append(len(phases) + 1)
            if len(phases) == 1:
                self.actions.records[999] = run(999, ticket=NEXT, conclusion="success",
                                               created_at="2026-10-06T17:00:00Z")
            elif len(phases) == 2:
                state = pending()
                state["operation"]["original_run_id"] = 101
                self.receipts.state = state
            elif len(phases) == 3:
                self.actions.records[101].update(status="completed", conclusion="success")
                state = pending()
                state["status"] = "ready"
                state["operation"].update(status="completed", original_run_id=101)
                state.update(request_status="completed", next_request_id=NEXT)
                self.receipts.state = state
            else:
                self.fail("Controller did not finish after its own preserved receipt")
        scheduler.sleep = advance
        result = scheduler.controller(TICKET, 500)
        self.assertEqual(phases, [1, 2, 3])
        self.assertEqual(result["completed_request_id"], TICKET)
        self.assertEqual(self.actions.dispatches, [("growth.yml", TICKET), ("heartbeat-controller.yml", NEXT)])
        self.assertIn(("run", 101), self.actions.reads)
        self.assertNotIn(("run", 999), self.actions.reads)

    def test_stale_completed_controller_does_not_spawn_successor(self):
        state = ready()
        state.update(next_request_id=NEXT, request_status="completed")
        scheduler = self.scheduler(state)
        self.assertEqual(scheduler.controller(TICKET, 500)["status"], "already_terminal")
        self.assertEqual(self.actions.reads, [])
        self.assert_no_mutation()

    def test_unknown_controller_ticket_fails_closed(self):
        scheduler = self.scheduler(ready())
        with self.assertRaisesRegex(controller.Blocked, "stale_or_unknown"):
            scheduler.tick("controller", NEXT)
        self.assert_no_mutation()

    def test_deferred_writer_replay_preserves_original_event_identity(self):
        scheduler = self.scheduler(ready())
        original = run(17, "interact.yml", event="issue_comment", head_sha="d" * 40)
        self.actions.records[17] = deepcopy(original)
        self.actions.job_records[17] = [{"steps": [{"name": controller.DEFERRED_STEP, "conclusion": "failure"}]}]
        result = scheduler.tick("watchdog")
        self.assertEqual(result["status"], "replayed_writer")
        self.assertEqual(self.actions.reruns, [17])
        self.assertEqual(self.actions.dispatches, [])
        for key in ("head_sha", "head_branch", "event", "display_title"):
            self.assertEqual(self.actions.records[17][key], original[key])

    def test_ordinary_writer_failure_is_not_deferral_proof(self):
        scheduler = self.scheduler(ready())
        self.actions.records[17] = run(17, "reconcile.yml", event="workflow_run")
        self.actions.job_records[17] = [{"steps": [{"name": controller.LEGACY_DEFERRED_STEP, "conclusion": "failure"}]}]
        self.assertEqual(scheduler.tick("watchdog")["status"], "dispatched")
        self.assertEqual(self.actions.reruns, [])

    def test_pending_blocks_deferred_writer_replay(self):
        scheduler = self.scheduler(pending())
        self.actions.records[42] = run(status="in_progress")
        self.actions.records[17] = run(17, "interact.yml")
        self.actions.job_records[17] = [{"steps": [{"name": controller.DEFERRED_STEP, "conclusion": "failure"}]}]
        self.assertEqual(scheduler.tick("watchdog")["status"], "healthy")
        self.assert_no_mutation()

    def test_ci_pending_does_not_dispatch_guard_failures(self):
        scheduler = self.scheduler(ready())
        self.actions.verified = None
        self.assertEqual(scheduler.tick("controller", TICKET)["status"], "waiting_for_verified_source")
        self.assert_no_mutation()

    def test_queued_reconciliation_does_not_block_shared_writer_dispatch(self):
        scheduler = self.scheduler(ready())
        self.actions.records[17] = run(17, "reconcile.yml", status="queued", event="workflow_run")
        self.assertEqual(scheduler.tick("controller", TICKET)["status"], "dispatched")
        self.assertEqual(self.actions.dispatches, [("growth.yml", TICKET)])

    def test_executing_reconciliation_still_blocks_dispatch(self):
        scheduler = self.scheduler(ready())
        self.actions.records[17] = run(17, "reconcile.yml", status="in_progress", event="workflow_run")
        self.assertEqual(scheduler.tick("controller", TICKET)["status"], "healthy")
        self.assert_no_mutation()

    def legacy_failure(self, *, receipt=True, marker=True, exit_75=True, original_run_id=42):
        state = ready()
        if receipt:
            state["operation"] = dict(pending()["operation"], status="completed")
            state["next_request_id"] = NEXT
        scheduler = self.scheduler(state)
        self.actions.records[LEGACY_RUN] = run(LEGACY_RUN, "reconcile.yml", event="workflow_run", head_sha=LEGACY_SOURCE)
        self.actions.job_records[LEGACY_RUN] = [{"id": 170, "steps": [{
            "name": controller.LEGACY_DEFERRED_STEP, "conclusion": "failure",
            "started_at": "2026-10-07T17:00:01Z", "completed_at": "2026-10-07T17:00:03Z",
        }]}]
        lines = []
        if marker:
            lines.append("2026-10-07T17:00:02.1234567Z " + json.dumps({
                "status": "deferred", "reason": "heartbeat_pending", "request_id": TICKET,
                "original_run_id": original_run_id,
            }))
        if exit_75:
            lines.append("2026-10-07T17:00:03.1234567Z ##[error]Process completed with exit code 75.")
        self.actions.log_records[170] = "\n".join(lines)
        return scheduler

    def test_legacy_deferral_requires_exact_log_marker_and_terminal_receipt(self):
        scheduler = self.legacy_failure()
        self.assertEqual(scheduler.tick("watchdog")["status"], "replayed_writer")
        self.assertEqual(self.actions.reruns, [LEGACY_RUN])
        self.assertEqual(self.actions.dispatches, [])
        self.assertIn(("job_log", 170), self.actions.reads)

    def test_legacy_deferral_without_marker_or_exit_75_is_not_replayed(self):
        for missing in ("marker", "exit_75"):
            with self.subTest(missing=missing):
                scheduler = self.legacy_failure(**{missing: False})
                self.assertEqual(scheduler.tick("watchdog")["status"], "dispatched")
                self.assertEqual(self.actions.reruns, [])

    def test_legacy_marker_outside_failed_step_is_not_proof(self):
        scheduler = self.legacy_failure()
        self.actions.log_records[170] = self.actions.log_records[170].replace("17:00:02.1234567", "16:59:00.1234567")
        self.assertEqual(scheduler.tick("watchdog")["status"], "dispatched")
        self.assertEqual(self.actions.reruns, [])

    def test_legacy_original_run_conflict_fails_closed(self):
        scheduler = self.legacy_failure(original_run_id=999)
        with self.assertRaisesRegex(controller.Blocked, "original_run_conflict"):
            scheduler.tick("watchdog")
        self.assert_no_mutation()

    def test_legacy_deferred_ticket_uses_terminal_history_after_pointer_moves(self):
        scheduler = self.legacy_failure(receipt=False)
        self.receipts.history[TICKET] = dict(ready(), request_status="completed")
        self.assertEqual(scheduler.tick("watchdog")["status"], "replayed_writer")
        self.assertIn(TICKET, self.receipts.calls)
        self.assertEqual(self.actions.reruns, [LEGACY_RUN])

    def test_legacy_unseen_ticket_cannot_authorize_replay(self):
        scheduler = self.legacy_failure(receipt=False)
        with self.assertRaisesRegex(controller.Blocked, "not_terminal"):
            scheduler.tick("watchdog")
        self.assert_no_mutation()

    def test_legacy_active_growth_drains_before_new_generation(self):
        scheduler = self.scheduler(ready())
        self.actions.records[42] = run(status="in_progress", display_title="autonomous-growth-cycle")
        self.assertEqual(scheduler.tick("controller", TICKET)["status"], "healthy")
        self.assert_no_mutation()


class ActionsReadStabilizationTests(unittest.TestCase):
    def test_incomplete_snapshot_restarts_identical_read_and_accepts_complete_snapshot(self):
        actions = controller.Actions("JeremyHennessy/AgentTest")
        complete = [run(42, status="queued"), run(43, status="queued")]
        responses = [
            {"total_count": 2, "workflow_runs": [run(17, status="queued")]},
            {"total_count": 2, "workflow_runs": complete},
        ]
        with patch.object(actions, "api", side_effect=responses) as api, patch.object(controller.time, "sleep") as sleep:
            self.assertEqual(actions.runs("growth.yml", status="queued"), complete)
        self.assertEqual(api.call_count, 2)
        self.assertEqual(api.call_args_list[0], api.call_args_list[1])
        self.assertIn("page=1", api.call_args.args[0])
        sleep.assert_called_once_with(1)

    def test_persistently_incomplete_snapshot_remains_blocked_after_three_reads(self):
        actions = controller.Actions("JeremyHennessy/AgentTest")
        with patch.object(actions, "api", return_value={"total_count": 1, "workflow_runs": []}) as api, patch.object(controller.time, "sleep") as sleep:
            with self.assertRaisesRegex(controller.Blocked, "workflow_run_search_incomplete"):
                actions.runs("growth.yml", status="queued")
        self.assertEqual(api.call_count, 3)
        self.assertTrue(all(call == api.call_args_list[0] for call in api.call_args_list))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])


class BoundedLegacyLogTests(unittest.TestCase):
    def test_job_log_reads_text_and_rejects_oversized_stream(self):
        real_popen = subprocess.Popen
        actions = controller.Actions("JeremyHennessy/AgentTest")
        for size in (32, 1025):
            with self.subTest(size=size):
                def local_process(_command, **kwargs):
                    return real_popen([sys.executable, "-c", f"import sys; sys.stdout.write('x' * {size})"], **kwargs)
                with patch.object(controller.subprocess, "Popen", side_effect=local_process), patch.object(controller, "LOG_LIMIT", 1024):
                    if size <= 1024:
                        self.assertEqual(actions.job_log(170), "x" * size)
                    else:
                        with self.assertRaisesRegex(controller.Blocked, "too_large"):
                            actions.job_log(170)


class HeartbeatWorkflowTests(unittest.TestCase):
    def test_generation_and_ticket_replace_latest_run_delta(self):
        workflow = (ROOT / ".github/workflows/heartbeat-controller.yml").read_text()
        self.assertIn('"controller-v4"', workflow)
        self.assertIn("request_id:", workflow)
        self.assertIn("run-name: heartbeat controller", workflow)
        self.assertIn("group: agenttest-heartbeat-controller-v2", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertNotIn("controller-v3", workflow)
        self.assertNotIn("--limit 1", workflow)
        self.assertNotIn("always()", workflow)

    def test_watchdog_is_bounded_and_has_no_writer_or_core_work(self):
        workflow = (ROOT / ".github/workflows/heartbeat-watchdog.yml").read_text()
        self.assertIn('cron: "7,17,27,37,47,57 * * * *"', workflow)
        self.assertIn("timeout-minutes: 3", workflow)
        self.assertIn("actions: write", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("agenttest-autonomous-growth-v2", workflow)
        self.assertNotIn("unittest", workflow)
        self.assertNotIn("agenttest cycle", workflow)
        self.assertNotIn("upload-artifact", workflow)


if __name__ == "__main__":
    unittest.main()
