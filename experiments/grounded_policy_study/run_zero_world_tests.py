"""Run the reviewed authored-data suite without loading Ora or a real world.

The executed snapshot is immutable. Its historical sibling paths are reproduced
inside a disposable directory; no existing results, API sources, launch profiles,
approval receipts, or native fixture binaries are staged there.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest


SNAPSHOT = Path(__file__).resolve().parent / "executed_snapshot"
MANIFEST_NAME = "EXECUTED_SOURCE_MANIFEST.json"
MANIFEST_SHA256 = "44501db2a928139f0131956f492818d92854c70a7b068eb19169ef795e09f956"
FORBIDDEN_IMPORTS = frozenset((
    "agenttest", "grounded_policy_v2", "inquiry_executive",
    "open_object_world_challenge", "open_object_world_challenge_explorer",
    "challenge_action_authority", "challenge_shadow_epistemic_selector",
    "challenge_shadow_recorder", "native_observe_inquire_integration",
    "normalized_inquiry_objectives",
))


class NoWorldImports:
    """Defense in depth for the test process; child programs are authored stubs."""

    def __init__(self):
        self.attempts = []

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in FORBIDDEN_IMPORTS:
            self.attempts.append(fullname)
            raise ImportError("Real Ora/API/world imports are outside this suite: " + fullname)
        return None


def captured_snapshot():
    manifest_bytes = (SNAPSHOT / MANIFEST_NAME).read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise RuntimeError("Executed source manifest differs from the reviewed snapshot")
    expected = json.loads(manifest_bytes)
    present = {
        str(path.relative_to(SNAPSHOT))
        for path in SNAPSHOT.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if present != set(expected) | {MANIFEST_NAME}:
        raise RuntimeError("Executed snapshot file membership changed")
    captured = {}
    for name, wanted in expected.items():
        relative = Path(name)
        path = SNAPSHOT / relative
        if relative.is_absolute() or ".." in relative.parts or path.is_symlink():
            raise RuntimeError("Noncanonical snapshot source: " + name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != wanted:
            raise RuntimeError("Executed snapshot bytes changed: " + name)
        captured[name] = raw
    captured[MANIFEST_NAME] = manifest_bytes
    return captured


def main():
    if len(sys.argv) != 1:
        raise RuntimeError("This entry point accepts no activation or fixture arguments")
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("Use python -I -S -B to run this isolated authored-data suite")
    if sys.platform != "linux":
        raise RuntimeError("The native resource tests require Linux and an installed C compiler")
    captured = captured_snapshot()
    guard = NoWorldImports()
    sys.meta_path.insert(0, guard)
    start = time.monotonic_ns()
    original_cwd = Path.cwd()
    original_path = sys.path[:]
    try:
        with tempfile.TemporaryDirectory(prefix="ora-study-authored-") as temporary:
            root = Path(temporary).resolve()
            study = root / "policy-study-work"
            for name, raw in captured.items():
                target = study / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            (root / "policy-study-results").mkdir()
            os.chdir(root)
            sys.path.insert(0, str(study))
            suite = unittest.TestLoader().discover(str(study / "tests"), pattern="test_*.py")
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            forbidden_loaded = sorted(
                name for name in sys.modules if name.split(".", 1)[0] in FORBIDDEN_IMPORTS
            )
            snapshot_unchanged = all(
                (study / name).read_bytes() == raw for name, raw in captured.items()
            )
            passed = (result.wasSuccessful() and not guard.attempts
                      and not forbidden_loaded and snapshot_unchanged)
            summary = {
                "schema": "ora.study.publication-test.v1",
                "scope": "authored-data and zero-world resource tests only",
                "passed": passed,
                "tests_run": result.testsRun,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
                "elapsed_ns": time.monotonic_ns() - start,
                "snapshot_manifest_sha256": MANIFEST_SHA256,
                "snapshot_files_unchanged": snapshot_unchanged,
                "forbidden_import_attempts": guard.attempts,
                "forbidden_modules_loaded": forbidden_loaded,
                "real_fixture_run": False,
                "scientific_study_run": False,
                "scope_basis": "reviewed tests; exact frozen source; API sources absent from staged workspace",
            }
            print(json.dumps(summary, sort_keys=True))
            return 0 if passed else 1
    finally:
        os.chdir(original_cwd)
        sys.path[:] = original_path
        sys.meta_path.remove(guard)


if __name__ == "__main__":
    raise SystemExit(main())
