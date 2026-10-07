"""Require exact main CI and source equality before autonomous state writes.

Standalone stdlib only: growth executes a pinned copy outside its checkout.
This checks Git objects and actual bytes, without a cache or state receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "JeremyHennessy/AgentTest"
VERIFY_WORKFLOW_ID = 369754149
VERIFY_WORKFLOW_PATH = ".github/workflows/verify.yml"


class GateFailure(RuntimeError):
    """Evidence is missing or does not match the source that would run."""


def valid_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise GateFailure("Expected a full lowercase Git commit SHA")
    return value


def verified_run(data: dict, source_sha: str) -> dict:
    valid_sha(source_sha)
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if not isinstance(runs, list) or len(runs) != 1 or not isinstance(runs[0], dict):
        raise GateFailure("Exact main verify push evidence is unavailable")
    run = runs[0]
    expected = {"head_sha": source_sha, "head_branch": "main", "event": "push",
                "path": VERIFY_WORKFLOW_PATH, "workflow_id": VERIFY_WORKFLOW_ID,
                "status": "completed", "conclusion": "success"}
    for key, value in expected.items():
        if run.get(key) != value:
            raise GateFailure(f"Exact main verify push mismatch: {key}")
    for key in ("repository", "head_repository"):
        if not isinstance(run.get(key), dict) or run[key].get("full_name") != REPOSITORY:
            raise GateFailure(f"Exact main verify push mismatch: {key}")
    if type(run.get("id")) is not int or run["id"] <= 0:
        raise GateFailure("Invalid verify run identity")
    return {"run_id": run["id"], "source_sha": source_sha,
            "workflow_id": VERIFY_WORKFLOW_ID, "conclusion": "success"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def verify_ci(source_sha: str, repository: str) -> dict:
    valid_sha(source_sha)
    if repository != REPOSITORY:
        raise GateFailure("Unexpected repository")
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise GateFailure("Existing job token is required; no anonymous fallback")
    query = urllib.parse.urlencode({"branch": "main", "event": "push",
                                   "head_sha": source_sha, "per_page": 1})
    url = f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/verify.yml/runs?{query}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Ora-verified-growth-source"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            print(json.dumps({"ci_metadata_http_status": response.status}), flush=True)
            if response.status != 200:
                raise GateFailure("CI metadata did not return HTTP 200")
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise GateFailure("CI metadata response exceeds the expected size")
            data = json.loads(raw)
    except urllib.error.HTTPError as error:
        print(json.dumps({"ci_metadata_http_status": error.code}), flush=True)
        raise GateFailure("CI metadata access failed with existing permissions; no fallback") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise GateFailure("CI metadata is unavailable or malformed; stopping before claim") from error
    return verified_run(data, source_sha)


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise GateFailure("Git evidence failed: " + " ".join(args[:2]))
    return result.stdout


def is_state(path: bytes) -> bool:
    return path.startswith(b"state/")


def tree_sources(root: Path, revision: str) -> dict:
    result = {}
    for row in git(root, "ls-tree", "-rz", revision).split(b"\0"):
        if not row:
            continue
        header, path = row.split(b"\t", 1)
        mode, kind, oid = header.split()
        if is_state(path):
            continue
        if kind != b"blob" or mode not in (b"100644", b"100755", b"120000"):
            raise GateFailure("Unsupported non-state source type: " + os.fsdecode(path))
        result[path] = (mode, oid)
    return result


def index_sources(root: Path) -> dict:
    result = {}
    for row in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not row:
            continue
        header, path = row.split(b"\t", 1)
        mode, oid, stage = header.split()
        if stage != b"0":
            raise GateFailure("Unmerged index entry: " + os.fsdecode(path))
        if not is_state(path):
            result[path] = (mode, oid)
    return result


def file_identity(path: Path) -> tuple[bytes, bytes]:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        body = os.fsencode(os.readlink(path))
        return b"120000", hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest().encode()
    if not stat.S_ISREG(info.st_mode):
        raise GateFailure("Non-file source path: " + str(path))
    mode = b"100755" if info.st_mode & stat.S_IXUSR else b"100644"
    digest = hashlib.sha1(b"blob " + str(info.st_size).encode() + b"\0")
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return mode, digest.hexdigest().encode()


def compare_sources(expected: dict, actual: dict, label: str) -> None:
    differences = sorted(path for path in expected.keys() | actual.keys()
                         if expected.get(path) != actual.get(path))
    if differences:
        names = ", ".join(os.fsdecode(path) for path in differences[:10])
        raise GateFailure(f"Non-state {label} drift: {names}")


def verify_source(root: Path, source_sha: str, require_clean: bool = False) -> dict:
    valid_sha(source_sha)
    root = root.resolve()
    expected = tree_sources(root, source_sha)
    compare_sources(expected, tree_sources(root, "HEAD"), "HEAD")
    compare_sources(expected, index_sources(root), "index")
    actual = {}
    for path in expected:
        try:
            actual[path] = file_identity(root / os.fsdecode(path))
        except (FileNotFoundError, NotADirectoryError):
            pass
    compare_sources(expected, actual, "worktree")
    # Deliberately omit --exclude-standard: ignored code is still source drift.
    untracked = [path for path in git(root, "ls-files", "--others", "-z").split(b"\0")
                 if path and (require_clean or not is_state(path))]
    if untracked:
        raise GateFailure("Unexpected untracked paths: " + ", ".join(os.fsdecode(path) for path in untracked[:10]))
    if require_clean and git(root, "status", "--porcelain", "-z", "--untracked-files=all"):
        raise GateFailure("Pre-execution checkout must be clean, including state")
    return {"source_sha": source_sha, "source_files": len(expected), "source": "verified"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("verify-ci", "verify-source"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    try:
        result = (verify_ci(args.source_sha, args.repository) if args.operation == "verify-ci"
                  else verify_source(args.root, args.source_sha, args.require_clean))
    except (GateFailure, OSError, ValueError) as error:
        print(f"Verified source gate stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
