#!/usr/bin/env python3
"""Schedule durable heartbeat tickets; never write state or execute a Core cycle.

The growth branch is the authority. Actions metadata is only evidence of delivery,
activity, or the original event to rerun. POST errors never allocate another ticket.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time
from urllib.parse import urlencode

GENERATION = "controller-v4"
DEFERRED_STEP = "Heartbeat pending: deferred writer"
LEGACY_DEFERRED_STEP = "Resolve verified merged change"
# Closed migration exception: this pre-guard workflow was already queued during
# rollout. Never add runs automatically; remove after this original event clears.
LEGACY_RECONCILIATION = {37642389633: "7948bdf33f11c5f98bdbdbcb718c04118c7354a4"}
LOG_LIMIT = 256 * 1024
ACTIVE = {"queued", "in_progress", "waiting", "pending", "requested"}
CONCLUSIONS = {"success", "failure", "cancelled", "timed_out", "skipped", "neutral", "action_required", "stale", "startup_failure"}
WRITERS = ("interact.yml", "reconcile.yml")
SHA = re.compile(r"[0-9a-f]{40}\Z")
TICKET = re.compile(r"heartbeat:v1:[0-9a-f]{64}\Z")


class Blocked(RuntimeError):
    """Incomplete or conflicting evidence: make no speculative dispatch."""


def validate_run(run: dict) -> dict:
    if not isinstance(run, dict) or not isinstance(run.get("id"), int):
        raise Blocked("invalid_actions_run")
    status = run.get("status")
    if status not in ACTIVE | {"completed"}:
        raise Blocked("unknown_actions_run_status")
    if status == "completed" and run.get("conclusion") not in CONCLUSIONS:
        raise Blocked("unknown_actions_run_conclusion")
    return run


def title(workflow: str, ticket: str) -> str:
    return ("heartbeat " if workflow == "growth.yml" else "heartbeat controller ") + ticket


class Actions:
    def __init__(self, repository: str):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
            raise Blocked("invalid_repository")
        self.prefix = f"repos/{repository}"

    def api(self, path: str, payload: dict | None = None):
        command = ["gh", "api", "-H", "Accept: application/vnd.github+json", f"{self.prefix}/{path}"]
        if payload is not None:
            command += ["--method", "POST", "--input", "-"]
        result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                                text=True, capture_output=True, timeout=45)
        if result.returncode:
            raise Blocked(f"actions_api_unavailable:{path.split('?')[0]}")
        try:
            return json.loads(result.stdout) if result.stdout.strip() else None
        except ValueError as exc:
            raise Blocked("invalid_actions_json") from exc

    def runs(self, workflow: str, **filters) -> list[dict]:
        # GitHub caps filtered run searches at 1,000 results. Do not interpret a
        # truncated search as absence. Current tickets normally span minutes.
        for snapshot_attempt in range(3):
            rows = []
            for page in range(1, 11):
                query = urlencode({"per_page": 100, "page": page, **filters})
                data = self.api(f"actions/workflows/{workflow}/runs?{query}")
                if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
                    raise Blocked("invalid_workflow_run_listing")
                total = data.get("total_count")
                if not isinstance(total, int) or total < 0 or total > 1000:
                    raise Blocked("workflow_run_search_truncated_or_unknown")
                batch = [validate_run(run) for run in data["workflow_runs"]]
                rows.extend(batch)
                if len(batch) < 100:
                    if len(rows) < total:
                        break
                    return rows
            else:
                raise Blocked("workflow_run_search_truncated")
            # Counts and pages can briefly reflect different Actions snapshots.
            # Discard the incomplete snapshot and repeat the same read from page
            # one; never infer absence from it or retry a malformed response.
            if snapshot_attempt < 2:
                time.sleep(snapshot_attempt + 1)
        raise Blocked("workflow_run_search_incomplete")

    def active(self, workflow: str, exclude: int = 0) -> list[dict]:
        rows = []
        for status in sorted(ACTIVE):
            rows.extend(run for run in self.runs(workflow, status=status) if run["id"] != exclude)
        return rows

    def matching(self, workflow: str, ticket: str, since: str | None) -> list[dict]:
        filters = {"event": "workflow_dispatch", "branch": "main"}
        if since:
            filters["created"] = ">=" + since
        return [run for run in self.runs(workflow, **filters) if run.get("display_title") == title(workflow, ticket)]

    def run(self, run_id: int) -> dict:
        return validate_run(self.api(f"actions/runs/{run_id}"))

    def jobs(self, run: dict) -> list[dict]:
        # Attempt-scoped metadata prevents an old deferred attempt from causing
        # a replay after a later attempt has already processed the original event.
        attempt = run.get("run_attempt")
        if not isinstance(attempt, int) or attempt < 1:
            raise Blocked("unknown_run_attempt")
        data = self.api(f"actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100")
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise Blocked("invalid_jobs_response")
        if data.get("total_count") != len(data["jobs"]):
            raise Blocked("jobs_response_truncated")
        return data["jobs"]

    def job_log(self, job_id: int) -> str:
        if type(job_id) is not int or job_id <= 0:
            raise Blocked("invalid_deferred_job_identity")
        command = ["gh", "api", f"{self.prefix}/actions/jobs/{job_id}/logs"]
        chunks = bytearray()
        deadline = time.monotonic() + 20
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0 or not selector.select(remaining):
                            raise Blocked("deferred_job_log_timeout")
                        chunk = os.read(process.stdout.fileno(), min(8192, LOG_LIMIT + 1 - len(chunks)))
                        if not chunk:
                            break
                        chunks.extend(chunk)
                        if len(chunks) > LOG_LIMIT:
                            raise Blocked("deferred_job_log_too_large")
                if process.wait(timeout=max(0.01, deadline - time.monotonic())):
                    raise Blocked("deferred_job_log_unavailable")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        try:
            return chunks.decode("utf-8")
        except UnicodeError as exc:
            raise Blocked("invalid_deferred_job_log") from exc

    def dispatch(self, workflow: str, ticket: str):
        inputs = {"request_id": ticket}
        if workflow == "heartbeat-controller.yml":
            inputs["controller_token"] = GENERATION
        return self.api(f"actions/workflows/{workflow}/dispatches", {"ref": "main", "inputs": inputs})

    def rerun(self, run_id: int):
        # GitHub preserves the original event, GITHUB_SHA and GITHUB_REF.
        return self.api(f"actions/runs/{run_id}/rerun", {})

    def verified_main(self) -> str | None:
        ref = self.api("git/ref/heads/main")
        sha = (ref.get("object") or {}).get("sha") if isinstance(ref, dict) else None
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise Blocked("unknown_main_source")
        runs = self.runs("verify.yml", event="push", branch="main", head_sha=sha)
        if not runs:
            return None
        run = max(runs, key=lambda row: row["id"])
        if run.get("head_sha") != sha or run.get("head_branch") != "main" or run.get("event") != "push":
            raise Blocked("source_ci_identity_conflict")
        if run["status"] in ACTIVE:
            return None
        if run["conclusion"] != "success":
            raise Blocked("exact_main_source_ci_not_successful")
        jobs = {job.get("name"): job.get("conclusion") for job in self.jobs(run)}
        for name in ("unit-tests", "behavioral-preservation", "capability-handoff-sanity"):
            if jobs.get(name) != "success":
                raise Blocked("exact_main_required_check_not_successful")
        return sha


class Receipts:
    def __init__(self, root: Path, *, shallow: bool = False):
        self.root = root
        self.shallow = shallow

    def inspect(self, ticket: str = "") -> dict:
        if ticket and self.shallow:
            # Only the rare legacy log fallback needs historical proof in the
            # watchdog. Its normal current-pointer path remains depth one.
            result = subprocess.run(["git", "-C", str(self.root), "rev-parse", "--is-shallow-repository"],
                                    text=True, capture_output=True, timeout=10)
            if result.returncode or result.stdout.strip() not in {"true", "false"}:
                raise Blocked("unknown_receipt_history_depth")
            if result.stdout.strip() == "true":
                fetched = subprocess.run(["git", "-C", str(self.root), "fetch", "--unshallow", "--no-tags",
                                          "--filter=blob:none", "origin", "refs/heads/autonomous/growth:refs/remotes/origin/autonomous/growth"],
                                         text=True, capture_output=True, timeout=90)
                if fetched.returncode:
                    raise Blocked("historical_deferred_receipt_unavailable")
            self.shallow = False
        command = [sys.executable, "-B", str(Path(__file__).with_name("heartbeat_transport.py")),
                   "inspect", "--remote", "--root", str(self.root)]
        if ticket:
            command += ["--request-id", ticket]
        elif self.shallow:
            command += ["--shallow"]
        result = subprocess.run(command, text=True, capture_output=True, timeout=90)
        if result.returncode:
            raise Blocked("growth_branch_receipt_unavailable_or_conflicting")
        try:
            data = json.loads(result.stdout)
        except ValueError as exc:
            raise Blocked("invalid_growth_branch_receipt") from exc
        if not isinstance(data, dict) or data.get("status") not in {"pending", "ready"}:
            raise Blocked("unknown_growth_branch_receipt_status")
        if not isinstance(data.get("next_request_id"), str) or not TICKET.fullmatch(data["next_request_id"]):
            raise Blocked("invalid_next_heartbeat_ticket")
        if not isinstance(data.get("ticket_since"), str) or not data["ticket_since"]:
            raise Blocked("unknown_ticket_time_anchor")
        if ticket and data.get("request_status") not in {"unseen", "pending", "completed", "abandoned"}:
            raise Blocked("unknown_requested_receipt_status")
        return data


class Scheduler:
    def __init__(self, actions, receipts, *, now=None, sleep=time.sleep):
        self.actions = actions
        self.receipts = receipts
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep

    def dispatch_same_ticket(self, workflow: str, ticket: str, since: str | None) -> dict:
        before = self.actions.matching(workflow, ticket, since)
        if any(run["status"] in ACTIVE for run in before):
            return {"status": "already_active", "request_id": ticket}
        known = {run["id"] for run in before}
        # A lost acknowledgement may create a second delivery, never a second
        # logical request. Both deliveries retain the exact same durable ticket.
        for attempt in range(2):
            try:
                self.actions.dispatch(workflow, ticket)
                return {"status": "dispatched", "request_id": ticket}
            except (Blocked, subprocess.TimeoutExpired):
                self.sleep(2)
                matches = self.actions.matching(workflow, ticket, since)
                if any(run["id"] not in known or run["status"] in ACTIVE for run in matches):
                    return {"status": "rediscovered", "request_id": ticket}
                if attempt:
                    raise Blocked("dispatch_outcome_unknown_same_ticket_only")
        raise AssertionError("unreachable")

    def resume_original(self, run: dict, *, operation: dict | None = None) -> dict:
        run = validate_run(run)
        if operation is not None:
            if (run["id"] != operation["original_run_id"] or run.get("head_sha") != operation["source_sha"]
                    or run.get("head_branch") != "main" or run.get("event") != "workflow_dispatch"
                    or run.get("display_title") != title("growth.yml", operation["request_id"])
                    or str(run.get("path", "")).split("@")[0] != ".github/workflows/growth.yml"):
                raise Blocked("pending_original_run_identity_conflict")
        if run["status"] in ACTIVE:
            return {"status": "healthy", "run_id": run["id"]}
        try:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            if created.tzinfo is None:
                raise ValueError("missing timezone")
        except (KeyError, TypeError, ValueError) as exc:
            raise Blocked("unknown_original_run_age") from exc
        if self.now() - created >= timedelta(days=30):
            raise Blocked("original_run_exceeds_github_30_day_rerun_window")
        attempt = run.get("run_attempt")
        # Deliberately stop at 50 total attempts, within GitHub's 50-rerun limit.
        if not isinstance(attempt, int) or attempt < 1 or attempt >= 50:
            raise Blocked("original_run_reached_50_attempt_recovery_limit")
        try:
            self.actions.rerun(run["id"])
        except (Blocked, subprocess.TimeoutExpired):
            observed = self.actions.run(run["id"])
            if observed["status"] not in ACTIVE and observed.get("run_attempt", 0) <= attempt:
                raise Blocked("original_rerun_outcome_unknown")
        return {"status": "resumed", "run_id": run["id"], "run_attempt": attempt}

    def legacy_deferred(self, run: dict, job: dict, state: dict) -> bool:
        if run["id"] not in LEGACY_RECONCILIATION:
            return False
        if (run.get("head_sha") != LEGACY_RECONCILIATION[run["id"]]
                or run.get("event") != "workflow_run" or run.get("head_branch") != "main"
                or str(run.get("path", "")).split("@")[0] != ".github/workflows/reconcile.yml"):
            raise Blocked("legacy_reconciliation_migration_identity_conflict")
        steps = [step for step in job["steps"] if step.get("name") == LEGACY_DEFERRED_STEP
                 and step.get("conclusion") == "failure"]
        if not steps:
            return False
        if len(steps) != 1 or run.get("event") != "workflow_run":
            raise Blocked("ambiguous_legacy_reconciliation_failure")
        step = steps[0]
        try:
            start = datetime.fromisoformat(step["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(step["completed_at"].replace("Z", "+00:00")) + timedelta(seconds=1)
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError("invalid step time")
        except (KeyError, TypeError, ValueError) as exc:
            raise Blocked("unknown_legacy_deferred_step_window") from exc
        markers, exited_75 = [], False
        for line in self.actions.job_log(job.get("id")).splitlines():
            timestamp, separator, message = line.partition(" ")
            if not separator:
                continue
            try:
                stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if stamp.tzinfo is None or not start <= stamp < end:
                    continue
            except ValueError:
                continue
            if message == "##[error]Process completed with exit code 75.":
                exited_75 = True
            if not message.startswith("{"):
                continue
            try:
                marker = json.loads(message)
            except ValueError:
                continue
            if (isinstance(marker, dict) and set(marker) == {"status", "reason", "request_id", "original_run_id"}
                    and marker.get("status") == "deferred" and marker.get("reason") == "heartbeat_pending"
                    and isinstance(marker.get("request_id"), str) and TICKET.fullmatch(marker["request_id"])
                    and type(marker.get("original_run_id")) is int and marker["original_run_id"] > 0):
                markers.append(marker)
        if not markers or not exited_75:
            return False
        if len(markers) != 1:
            raise Blocked("ambiguous_legacy_deferred_request")
        marker = markers[0]
        ticket = marker["request_id"]
        operation = state.get("operation") or {}
        if operation.get("request_id") == ticket:
            if operation.get("original_run_id") != marker["original_run_id"]:
                raise Blocked("legacy_deferred_original_run_conflict")
            status = operation.get("status")
        else:
            history = self.receipts.inspect(ticket)
            if history["status"] == "pending":
                raise Blocked("heartbeat_pending_during_deferred_replay")
            status = history["request_status"]
        if status not in {"completed", "abandoned"}:
            raise Blocked("legacy_deferred_request_not_terminal")
        return True

    def replay_deferred(self, state: dict) -> dict | None:
        deferred = []
        for workflow in WRITERS:
            for run in self.actions.runs(workflow, status="failure"):
                if run["status"] != "completed" or run.get("conclusion") != "failure":
                    raise Blocked("failed_writer_listing_conflict")
                for job in self.actions.jobs(run):
                    if not isinstance(job.get("steps"), list):
                        raise Blocked("unknown_writer_steps")
                    marked = any(step.get("name") == DEFERRED_STEP and step.get("conclusion") == "failure"
                                 for step in job["steps"])
                    if not marked and workflow == "reconcile.yml" and run["id"] in LEGACY_RECONCILIATION:
                        marked = self.legacy_deferred(run, job, state)
                    if marked:
                        if str(run.get("path", "")).split("@")[0] != f".github/workflows/{workflow}":
                            raise Blocked("deferred_writer_workflow_conflict")
                        deferred.append(run)
                        break
        if not deferred:
            return None
        # Preserve each original event's identity and FIFO order. No redispatch
        # with a copied message or a newly selected verify event is permitted.
        result = self.resume_original(min(deferred, key=lambda run: run["id"]))
        result["status"] = "replayed_writer"
        return result

    def tick(self, mode: str, ticket: str = "", own_run_id: int = 0) -> dict:
        state = self.receipts.inspect(ticket)
        operation = state.get("operation")
        if ticket and state.get("request_status") in {"completed", "abandoned"}:
            return {"status": "already_terminal", "request_id": ticket}
        if state["status"] == "pending":
            if not isinstance(operation, dict) or operation.get("status") != "pending":
                raise Blocked("pending_receipt_missing")
            if ticket and ticket != operation.get("request_id"):
                raise Blocked("different_heartbeat_request_pending")
            result = self.resume_original(self.actions.run(operation["original_run_id"]), operation=operation)
            result["request_id"] = operation["request_id"]
            return result
        next_ticket = state["next_request_id"]
        if ticket and ticket != next_ticket:
            raise Blocked("stale_or_unknown_controller_ticket")
        if mode == "watchdog" and self.actions.active("heartbeat-controller.yml", exclude=own_run_id):
            return {"status": "healthy", "reason": "controller_active"}
        # Also drain a prior-generation growth run during the rollout. Unknown
        # in-flight work never authorizes a fresh cycle over it.
        for workflow in ("growth.yml", *WRITERS):
            active = [validate_run(run) for run in self.actions.active(workflow)]
            if workflow == "reconcile.yml":
                # Queued reconciliation shares the writer lane with growth.
                # Only executing reconciliation blocks a fresh dispatch (#236).
                active = [run for run in active if run["status"] == "in_progress"]
            if active:
                return {"status": "healthy", "reason": f"{workflow}_active", "request_id": next_ticket}
        replay = self.replay_deferred(state)
        if replay:
            return replay
        if self.actions.verified_main() is None:
            return {"status": "waiting_for_verified_source", "request_id": next_ticket}
        workflow = "growth.yml" if mode == "controller" else "heartbeat-controller.yml"
        since = state["ticket_since"]
        result = self.dispatch_same_ticket(workflow, next_ticket, since)
        result["workflow"] = workflow
        return result

    def controller(self, ticket: str, own_run_id: int, timeout: float = 2400) -> dict:
        initial = self.receipts.inspect(ticket)
        if ticket and initial.get("request_status") in {"completed", "abandoned"}:
            return {"status": "already_terminal", "request_id": ticket}
        ticket = ticket or initial["next_request_id"]
        deadline = time.monotonic() + timeout
        managed = False
        dispatched = False
        resumed = False
        while time.monotonic() < deadline:
            state = self.receipts.inspect(ticket)
            if state.get("request_status") in {"completed", "abandoned"}:
                if not managed:
                    return {"status": "already_terminal", "request_id": ticket}
                # Only a controller that actually observed/managed this request
                # queues its deterministic successor. A stale duplicate is inert.
                if state["status"] == "pending":
                    return {"status": "healthy", "reason": "successor_already_pending"}
                result = self.dispatch_same_ticket("heartbeat-controller.yml", state["next_request_id"], state["ticket_since"])
                result["completed_request_id"] = ticket
                return result
            if dispatched and state["status"] == "ready":
                matches = self.actions.matching("growth.yml", ticket, state["ticket_since"])
                if matches and all(run["status"] == "completed" for run in matches):
                    raise Blocked("growth_finished_without_durable_receipt")
                self.sleep(10)
                continue
            if resumed and state["status"] == "pending":
                run = self.actions.run(state["operation"]["original_run_id"])
                if run["status"] == "completed":
                    raise Blocked("pending_growth_still_terminal_after_recovery")
                self.sleep(10)
                continue
            result = self.tick("controller", ticket, own_run_id)
            print(json.dumps(result, sort_keys=True), flush=True)
            status = result["status"]
            if status == "already_terminal":
                return result
            if status == "resumed":
                managed = resumed = True
            elif status in {"dispatched", "rediscovered", "already_active"}:
                managed = dispatched = True
            elif state["status"] == "pending":
                managed = True
            self.sleep(10)
        raise Blocked("controller_observation_window_exhausted_watchdog_will_recheck")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("controller", "watchdog"))
    parser.add_argument("--request-id", default="")
    parser.add_argument("--run-id", type=int, default=0)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.request_id and not TICKET.fullmatch(args.request_id):
            raise Blocked("invalid_controller_ticket")
        scheduler = Scheduler(Actions(os.environ.get("GITHUB_REPOSITORY", "")), Receipts(args.root, shallow=args.mode == "watchdog"))
        result = scheduler.controller(args.request_id, args.run_id) if args.mode == "controller" else scheduler.tick("watchdog", own_run_id=args.run_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Blocked, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
