"""Authored transport fault cases using real local Git refs and immutable commits."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("heartbeat_transport", ROOT / "scripts/heartbeat_transport.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class HeartbeatTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "work"
        self.remote = Path(self.temp.name) / "remote.git"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Transport fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        subprocess.run(["git", "init", "--bare", str(self.remote)], capture_output=True, check=True)
        (self.root / "app.py").write_text("# verified fixture source\n")
        (self.root / "state").mkdir()
        (self.root / "state/organism.json").write_text(json.dumps({"cycles": 3, "memory": ["preserve me"]}))
        (self.root / "state/journal.jsonl").write_text('{"event":"cycle","cycle":3}\n')
        self.git("add", ".")
        self.git("commit", "-m", "Verified fixture baseline")
        self.source = self.git("rev-parse", "HEAD")
        self.git("checkout", "-b", "autonomous/growth")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", "HEAD:refs/heads/autonomous/growth")
        self.request = t.inspect(self.root)["next_request_id"]
        self.sensor = patch.dict(sys.modules, {"agenttest.perception": SimpleNamespace(
            repository_snapshot=lambda root: {"sensor": "repository-v2", "head": t._head(root), "working_tree_clean": True})})
        self.sensor.start()
        self.addCleanup(self.sensor.stop)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=True).stdout.decode().strip()

    def commit(self, title, request=None):
        self.git("add", "state/")
        message = ["commit", "-m", title]
        if request:
            message.extend(["-m", "Heartbeat-Request: " + request])
        self.git(*message)
        return self.git("rev-parse", "HEAD")

    def claimed(self, request=None, run_id=101, mode="ordinary"):
        request = request or self.request
        remote_before = t._remote(self.root)
        result = t.claim(self.root, request, self.source, run_id, mode)
        self.assertEqual(result["status"], "created")
        commit = self.commit("Claim heartbeat", request)
        self.assertEqual(t.publish(self.root, commit, remote_before, sleeper=lambda _: None)["status"], "published")
        return commit

    def compute(self, request, claim_commit):
        seen = []
        root = self.root
        class FixtureCore:
            def __init__(self, store):
                pass
            def cycle(self, stimulus, **kwargs):
                seen.append((stimulus, kwargs))
                path = root / "state/organism.json"
                state = json.loads(path.read_text())
                state["cycles"] += 1
                path.write_text(json.dumps(state))
                with (root / "state/journal.jsonl").open("a") as stream:
                    stream.write(json.dumps({"event": "cycle", "cycle": state["cycles"], "time": kwargs["_now_override"]}) + "\n")
                return {"cycle": state["cycles"]}
        with patch.dict(sys.modules, {"agenttest.core": SimpleNamespace(AgentCore=FixtureCore),
                                     "agenttest.state": SimpleNamespace(StateStore=lambda path: path)}):
            result = t.cycle(self.root, request, self.source, claim_commit)
        self.assertEqual(result["status"], "computed_locally")
        self.assertEqual(len(seen), 1)
        return seen[0]

    def finished(self, request=None, run_id=101):
        request = request or self.request
        claim_commit = self.claimed(request, run_id)
        self.compute(request, claim_commit)
        t.complete(self.root, request, self.source, claim_commit)
        candidate = self.commit("Record heartbeat", request)
        return claim_commit, candidate

    def test_lost_push_acknowledgment_reconciles_exact_candidate(self):
        parent, candidate = self.finished()
        real_git = t._git
        pushes = []
        def lost_ack(root, *args, **kwargs):
            result = real_git(root, *args, **kwargs)
            if args[0] == "push":
                pushes.append(args)
                return subprocess.CompletedProcess(args, 1, b"", b"simulated lost acknowledgment")
            return result
        with patch.object(t, "_git", side_effect=lost_ack):
            result = t.publish(self.root, candidate, parent, sleeper=lambda _: None)
        self.assertEqual(result["status"], "published")
        self.assertEqual(len(pushes), 1)
        self.assertEqual(t._remote(self.root), candidate)
        self.assertEqual(t.claim(self.root, self.request, self.source, 101, "ordinary")["status"], "already_completed")

    def test_rejected_push_retries_same_commit_without_recomputing(self):
        parent, candidate = self.finished()
        real_git = t._git
        pushes = []
        def reject_first(root, *args, **kwargs):
            if args[0] == "push":
                pushes.append(args)
                if len(pushes) == 1:
                    return subprocess.CompletedProcess(args, 1, b"", b"simulated remote 500")
            return real_git(root, *args, **kwargs)
        with patch.object(t, "_git", side_effect=reject_first), patch.object(t, "cycle", side_effect=AssertionError("publisher must not compute")):
            result = t.publish(self.root, candidate, parent, sleeper=lambda _: None)
        self.assertEqual(result["status"], "published")
        self.assertEqual(len(pushes), 2)
        self.assertEqual(pushes[0], pushes[1])
        self.assertEqual(pushes[0][-1], candidate + ":refs/heads/autonomous/growth")

    def test_runner_loss_resumes_frozen_input_and_original_identity_only(self):
        claim_commit = self.claimed()
        original = t._read(self.root)
        self.assertEqual(t.claim(self.root, self.request, self.source, 101, "ordinary")["status"], "already_claimed")
        with self.assertRaisesRegex(t.TransportError, "original_run"):
            t.claim(self.root, self.request, self.source, 102, "ordinary")
        with self.assertRaisesRegex(t.TransportError, "source_mismatch"):
            t.claim(self.root, self.request, "f" * 40, 101, "ordinary")
        with patch.object(t, "_runtime", return_value={"implementation": "CPython", "python": "0.0.0"}):
            with self.assertRaisesRegex(t.TransportError, "runtime_mismatch"):
                t.claim(self.root, self.request, self.source, 101, "ordinary")
        _, arguments = self.compute(self.request, claim_commit)
        self.assertEqual(arguments["observation"], original["observation"])
        self.assertEqual(arguments["_now_override"], original["cycle_time"])
        self.assertFalse(arguments["cognition"])
        self.assertTrue(arguments["planning_lab"])
        self.assertEqual(json.loads((self.root / "state/organism.json").read_text())["memory"], ["preserve me"])

    def test_historical_completed_request_does_not_become_new_work(self):
        parent, first = self.finished()
        t.publish(self.root, first, parent, sleeper=lambda _: None)
        second_request = t.inspect(self.root)["next_request_id"]
        parent, second = self.finished(second_request, 102)
        t.publish(self.root, second, parent, sleeper=lambda _: None)
        before = (self.root / "state/organism.json").read_bytes()
        self.assertEqual(t.claim(self.root, self.request, self.source, 101, "ordinary")["status"], "already_completed")
        self.assertEqual(t.inspect(self.root, self.request)["request_status"], "completed")
        self.assertEqual((self.root / "state/organism.json").read_bytes(), before)
        self.assertNotIn("completed", t._read(self.root).get("history", {}))

    def test_shallow_watchdog_upgrades_history_only_for_requested_ticket(self):
        parent, first = self.finished()
        t.publish(self.root, first, parent, sleeper=lambda _: None)
        second_request = t.inspect(self.root)["next_request_id"]
        parent, second = self.finished(second_request, 102)
        t.publish(self.root, second, parent, sleeper=lambda _: None)
        watchdog = Path(self.temp.name) / "watchdog"
        subprocess.run(["git", "clone", "--depth=1", "--no-checkout", "--branch",
                        "autonomous/growth", self.remote.as_uri(), str(watchdog)],
                       capture_output=True, check=True)
        current = t.inspect(watchdog, remote=True, shallow=True)
        self.assertEqual(current["operation"]["request_id"], second_request)
        self.assertEqual(t._git(watchdog, "rev-parse", "--is-shallow-repository").stdout.strip(), b"true")
        self.assertEqual(t._git(watchdog, "rev-list", "--count", "HEAD").stdout.strip(), b"1")
        historical = t.inspect(watchdog, self.request, remote=True)
        self.assertEqual(historical["request_status"], "completed")
        self.assertEqual(t._git(watchdog, "rev-parse", "--is-shallow-repository").stdout.strip(), b"false")
        self.assertEqual(t._head(watchdog), second)
        self.assertEqual(t.inspect(watchdog, "heartbeat:v1:" + "f" * 64, remote=True)["request_status"], "unseen")

    def test_conflicting_remote_advance_does_not_rewrite_candidate(self):
        parent, candidate = self.finished()
        self.git("checkout", "--detach", parent)
        (self.root / "state/other.json").write_text('{"external":"unexpected"}')
        conflict = self.commit("Unexpected other writer")
        self.git("push", "origin", "HEAD:refs/heads/autonomous/growth")
        self.git("checkout", "--detach", candidate)
        with self.assertRaisesRegex(t.TransportError, "remote_advanced_incompatibly"):
            t.publish(self.root, candidate, parent, sleeper=lambda _: None)
        self.assertEqual(t._remote(self.root), conflict)
        self.assertEqual(t._head(self.root), candidate)

    def test_writer_defers_and_remote_inspection_does_not_checkout(self):
        claim_commit = self.claimed()
        result = t.writer_check(self.root)
        self.assertEqual(result, {"status": "deferred", "reason": "heartbeat_pending", "request_id": self.request, "original_run_id": 101})
        self.git("checkout", "--detach", self.source)
        before = t._head(self.root)
        result = t.inspect(self.root, remote=True)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["head"], claim_commit)
        self.assertEqual(t._head(self.root), before)
        self.assertEqual(result["next_request_id"], self.request)

    def test_legacy_reconciliation_entry_defers_before_any_state_write(self):
        self.claimed()
        paths = [self.root / "state/organism.json", self.root / "state/journal.jsonl",
                 self.root / "state/heartbeat_operation.json"]
        before = [path.read_bytes() for path in paths]
        output = self.root / "reconciliation.json"
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/reconcile_verified_change.py"),
            "--state", str(paths[0]), "--commit-sha", "a" * 40,
            "--changed-file", "src/agenttest/core.py", "--verify-run-id", "1",
            "--pr-number", "1", "--attribution-text", "authored pending transport fixture",
            "--output", str(output)], capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 75, result.stderr)
        marker = json.loads(result.stderr)
        self.assertEqual(marker["status"], "deferred")
        self.assertEqual(marker["reason"], "heartbeat_pending")
        self.assertEqual(marker["request_id"], self.request)
        self.assertEqual([path.read_bytes() for path in paths], before)
        self.assertFalse(output.exists())

    def test_wrong_or_stale_genesis_ticket_cannot_create_intent(self):
        original = (self.root / "state/organism.json").read_bytes()
        with self.assertRaisesRegex(t.TransportError, "stale_or_unrelated_heartbeat_ticket"):
            t.claim(self.root, "heartbeat:v1:" + "0" * 64, self.source, 101, "ordinary")
        self.assertFalse((self.root / t.OP_PATH).exists())
        (self.root / "state/other.json").write_text('{"revision":1}')
        self.commit("Advance remote input before first heartbeat")
        self.git("push", "origin", "HEAD:refs/heads/autonomous/growth")
        with self.assertRaisesRegex(t.TransportError, "stale_or_unrelated_heartbeat_ticket"):
            t.claim(self.root, self.request, self.source, 101, "ordinary")
        self.assertFalse((self.root / t.OP_PATH).exists())
        self.assertEqual((self.root / "state/organism.json").read_bytes(), original)

    def test_claim_can_publish_on_top_of_unpushed_source_merge(self):
        remote_before = t._remote(self.root)
        # A source-only fast-forward represents the local verified-source merge.
        (self.root / "app.py").write_text("# new verified fixture source\n")
        self.git("add", "app.py")
        self.git("commit", "-m", "New verified source")
        self.source = t._head(self.root)
        t.claim(self.root, self.request, self.source, 101, "ordinary")
        candidate = self.commit("Claim heartbeat", self.request)
        self.assertEqual(t.publish(self.root, candidate, remote_before, sleeper=lambda _: None)["status"], "published")
        self.assertEqual(t.claim(self.root, self.request, self.source, 101, "ordinary")["status"], "already_claimed")

    def test_changed_input_and_journal_history_fail_closed(self):
        claim_commit = self.claimed()
        path = self.root / "state/organism.json"
        path.write_text('{"cycles":3,"memory":["changed"]}')
        with self.assertRaisesRegex(t.TransportError, "clean_checkout"):
            t.cycle(self.root, self.request, self.source, claim_commit)
        self.git("restore", "state/organism.json")
        self.compute(self.request, claim_commit)
        journal = self.root / "state/journal.jsonl"
        journal.write_text(journal.read_text().replace('"cycle":3', '"cycle":2'))
        with self.assertRaisesRegex(t.TransportError, "journal_history_changed"):
            t.complete(self.root, self.request, self.source, claim_commit)

    def test_bounded_and_transport_claims_share_one_remote_commit(self):
        from agenttest.heartbeat_claim import DEFAULT_PAYLOAD, MAX_REQUESTS, validate_cycle_claim
        claim_commit = self.claimed(mode="current-world-investigation")
        state = json.loads((self.root / "state/organism.json").read_text())
        self.assertEqual(state["current_world_heartbeat"]["pending"]["request_id"], self.request)
        self.assertEqual(MAX_REQUESTS, 16)
        bounded = validate_cycle_claim(self.root / "state/organism.json", self.request, claim_commit, DEFAULT_PAYLOAD)
        self.assertEqual(bounded["request_id"], self.request)
        self.assertEqual(t.claim(self.root, self.request, self.source, 101, "current-world-investigation")["status"], "already_claimed")
        self.assertEqual(t._head(self.root), claim_commit)

    def test_unreadable_remote_never_uses_stale_ref_or_pushes(self):
        parent, candidate = self.finished()
        real_git = t._git
        pushed = []
        def unavailable(root, *args, **kwargs):
            if args[0] == "fetch":
                raise t.TransportError("simulated_unreadable_remote")
            if args[0] == "push":
                pushed.append(args)
            return real_git(root, *args, **kwargs)
        with patch.object(t, "_git", side_effect=unavailable):
            with self.assertRaisesRegex(t.TransportError, "publication_unconfirmed"):
                t.publish(self.root, candidate, parent, attempts=2, sleeper=lambda _: None)
        self.assertEqual(pushed, [])
        self.assertEqual(t._head(self.root), candidate)

    def test_missing_receipt_trailer_blocks_publication(self):
        parent = self.claimed()
        self.compute(self.request, parent)
        t.complete(self.root, self.request, self.source, parent)
        candidate = self.commit("Missing trailer")
        with self.assertRaisesRegex(t.TransportError, "trailer_missing"):
            t.publish(self.root, candidate, parent, sleeper=lambda _: None)


if __name__ == "__main__":
    unittest.main()
