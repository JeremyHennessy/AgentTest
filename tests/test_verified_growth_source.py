"""Focused fail-closed checks for the growth workflow's source gate."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verified_growth_source.py"
SPEC = importlib.util.spec_from_file_location("verified_growth_source", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)
SOURCE_SHA = "a" * 40


def success_payload():
    return {"workflow_runs": [{
        "id": 37637795724, "head_sha": SOURCE_SHA, "head_branch": "main",
        "event": "push", "path": guard.VERIFY_WORKFLOW_PATH,
        "workflow_id": guard.VERIFY_WORKFLOW_ID, "status": "completed",
        "conclusion": "success", "repository": {"full_name": guard.REPOSITORY},
        "head_repository": {"full_name": guard.REPOSITORY}}]}


class VerifiedCITests(unittest.TestCase):
    def test_exact_success_is_accepted(self):
        result = guard.verified_run(success_payload(), SOURCE_SHA)
        self.assertEqual(result["run_id"], 37637795724)
        self.assertEqual(result["source_sha"], SOURCE_SHA)

    def test_wrong_identity_or_unfinished_evidence_is_rejected(self):
        changes = {"head_sha": "b" * 40, "head_branch": "autonomous/growth",
                   "event": "pull_request", "path": ".github/workflows/impostor.yml",
                   "workflow_id": 123, "status": "in_progress", "conclusion": "failure",
                   "id": None, "repository": {"full_name": "other/repo"},
                   "head_repository": {"full_name": "other/repo"}}
        for field, value in changes.items():
            with self.subTest(field=field):
                payload = success_payload()
                payload["workflow_runs"][0][field] = value
                with self.assertRaises(guard.GateFailure):
                    guard.verified_run(payload, SOURCE_SHA)
        for conclusion in (None, "cancelled", "skipped", "neutral", "timed_out"):
            payload = success_payload()
            payload["workflow_runs"][0]["conclusion"] = conclusion
            with self.subTest(conclusion=conclusion), self.assertRaises(guard.GateFailure):
                guard.verified_run(payload, SOURCE_SHA)

    def test_missing_or_malformed_evidence_is_rejected(self):
        for payload in (None, [], {}, {"workflow_runs": []}, {"workflow_runs": [None]},
                        {"workflow_runs": success_payload()["workflow_runs"] * 2}):
            with self.subTest(payload=payload), self.assertRaises(guard.GateFailure):
                guard.verified_run(payload, SOURCE_SHA)
        with self.assertRaises(guard.GateFailure):
            guard.verified_run(success_payload(), "main")

    def test_existing_token_request_is_exact_and_has_no_success_filter(self):
        with patch.dict(os.environ, {"GH_TOKEN": "test-token"}), patch.object(guard.urllib.request, "build_opener") as builder:
            response = builder.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = json.dumps(success_payload()).encode()
            result = guard.verify_ci(SOURCE_SHA, guard.REPOSITORY)
            request = builder.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
            self.assertIn("actions/workflows/verify.yml/runs?", request.full_url)
            self.assertIn("head_sha=" + SOURCE_SHA, request.full_url)
            self.assertNotIn("status=success", request.full_url)
            self.assertEqual(result["run_id"], 37637795724)

    def test_access_failure_never_falls_back_or_retries(self):
        with patch.dict(os.environ, {"GH_TOKEN": "test-token"}), patch.object(guard.urllib.request, "build_opener") as builder:
            builder.return_value.open.side_effect = urllib.error.HTTPError("https://api.github.com/", 403, "Forbidden", {}, None)
            with self.assertRaises(guard.GateFailure):
                guard.verify_ci(SOURCE_SHA, guard.REPOSITORY)
            self.assertEqual(builder.return_value.open.call_count, 1)

    def test_missing_token_stops_before_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(guard.urllib.request, "build_opener") as builder:
            with self.assertRaises(guard.GateFailure):
                guard.verify_ci(SOURCE_SHA, guard.REPOSITORY)
            builder.assert_not_called()


class ExactSourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.run_git("init", "-q")
        self.run_git("config", "user.name", "Source gate fixture")
        self.run_git("config", "user.email", "fixture@example.invalid")
        self.write("src/runtime.py", "value = 1\n")
        self.write(".github/workflows/growth.yml", "name: fixture\n")
        self.write("pyproject.toml", "name = 'fixture'\n")
        self.write("state/organism.json", "{}\n")
        self.write(".gitignore", "ignored/\n*.tmp\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "Verified fixture")
        self.source_sha = self.run_git("rev-parse", "HEAD").strip().decode()

    def run_git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, path, body):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    def verify(self, require_clean=False):
        return guard.verify_source(self.root, self.source_sha, require_clean)

    def test_unchanged_and_committed_claim_state_allow_exact_retry(self):
        self.verify(require_clean=True)
        self.write("state/organism.json", '{"pending": "same-request"}\n')
        self.run_git("add", "state/organism.json")
        self.run_git("commit", "-qm", "Claim same request")
        self.verify(require_clean=True)

    def test_state_changes_only_are_allowed_at_publication(self):
        self.write("state/organism.json", '{"cycle": 1}\n')
        self.write("state/new-diagnostic.json", "{}\n")
        self.verify()
        with self.assertRaises(guard.GateFailure):
            self.verify(require_clean=True)
        self.run_git("add", "state/")
        self.verify()
        with self.assertRaises(guard.GateFailure):
            self.verify(require_clean=True)

    def test_committed_non_state_drift_is_rejected(self):
        self.write("src/runtime.py", "value = 2\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "Unverified source")
        with self.assertRaisesRegex(guard.GateFailure, "HEAD drift"):
            self.verify()

    def test_staged_drift_cannot_hide_behind_restored_worktree(self):
        self.write("src/runtime.py", "value = 2\n")
        self.run_git("add", "src/runtime.py")
        self.write("src/runtime.py", "value = 1\n")
        with self.assertRaisesRegex(guard.GateFailure, "index drift"):
            self.verify()

    def test_unstaged_workflow_and_config_changes_are_rejected(self):
        for path in (".github/workflows/growth.yml", "pyproject.toml"):
            original = (self.root / path).read_text()
            self.write(path, original + "# unverified\n")
            with self.subTest(path=path), self.assertRaisesRegex(guard.GateFailure, "worktree drift"):
                self.verify()
            self.write(path, original)

    def test_deleted_and_executable_mode_changes_are_rejected(self):
        target = self.root / "src/runtime.py"
        target.chmod(0o755)
        with self.assertRaisesRegex(guard.GateFailure, "worktree drift"):
            self.verify()
        target.unlink()
        with self.assertRaisesRegex(guard.GateFailure, "worktree drift"):
            self.verify()

    def test_untracked_including_ignored_code_is_rejected(self):
        for path in ("extra.py", "ignored/runtime.py", "runtime.tmp"):
            self.write(path, "value = 2\n")
            with self.subTest(path=path), self.assertRaisesRegex(guard.GateFailure, "untracked"):
                self.verify()
            (self.root / path).unlink()

    def test_assume_unchanged_flag_cannot_hide_modified_bytes(self):
        self.run_git("update-index", "--assume-unchanged", "src/runtime.py")
        self.write("src/runtime.py", "value = 2\n")
        with self.assertRaisesRegex(guard.GateFailure, "worktree drift"):
            self.verify()

    def test_drift_after_execution_blocks_publication(self):
        self.verify(require_clean=True)
        self.write("state/organism.json", '{"cycle": 1}\n')
        self.write("src/runtime.py", "value = 2\n")
        with self.assertRaisesRegex(guard.GateFailure, "worktree drift"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
