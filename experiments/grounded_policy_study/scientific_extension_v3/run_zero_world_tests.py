"""Verify and test the immutable, default-off scientific source overlay.

Only declared source bytes are staged. The existing foundation suite is not
invoked. No API source, real-world data, operational profile, GO receipt, started
marker, scientific result or historical native binary enters the test tree.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent
MANIFEST_SHA256 = "335fc45beee3117a6b55953b4ca5b33a95e6b167000080c4f42291c133a310bc"


def checked_bytes(path, wanted):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Expected a regular publication source file: " + str(path))
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != wanted:
        raise RuntimeError("Publication source digest changed: " + str(path))
    return raw


def capture_composition():
    manifest = json.loads(checked_bytes(ROOT / "SOURCE_MANIFEST.json", MANIFEST_SHA256))
    helper = ROOT.parent / "run_zero_world_tests.py"
    checked_bytes(helper, manifest["foundation_test_helper_sha256"])
    # Load definitions from the exact #224 helper without invoking its main or
    # its 150-test suite. This preserves the reviewed link-time strip wrapper.
    foundation = runpy.run_path(str(helper), run_name="foundation_publication_helper")
    sources = foundation["captured_snapshot"]()
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()}
    if hashes != manifest["foundation_snapshot_files"]:
        raise RuntimeError("Foundation composition differs from the pinned #224 snapshot")
    overlay = ROOT / "overlay"
    present = {str(path.relative_to(overlay)) for path in overlay.rglob("*")
               if path.is_file() or path.is_symlink()}
    if present != set(manifest["overlay_files"]):
        raise RuntimeError("Scientific overlay membership changed")
    for name, description in manifest["overlay_files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Invalid scientific overlay path")
        sources[name] = checked_bytes(overlay / name, description["sha256"])
    if {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()} != manifest["composed_files"]:
        raise RuntimeError("Composed source bytes differ from the reviewed v3 implementation closure")
    return manifest, foundation, sources


def main():
    if len(sys.argv) != 1 or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("Use python -I -S -B with no activation or fixture arguments")
    if sys.platform != "linux":
        raise RuntimeError("The authored native receipt checks require Linux and an installed C compiler")
    manifest, foundation, sources = capture_composition()
    guard = foundation["NoWorldImports"]()
    sys.meta_path.insert(0, guard)
    original_cwd, original_path = Path.cwd(), sys.path[:]
    original_environment_path = os.environ.get("PATH")
    start = time.monotonic_ns()
    try:
        with tempfile.TemporaryDirectory(prefix="ora-scientific-v3-authored-") as temporary:
            root = Path(temporary).resolve()
            study = root / "policy-study-work"
            for name, raw in sources.items():
                target = study / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            (root / "policy-study-results").mkdir()
            os.chdir(root)
            sys.path[:0] = [str(study), str(study / "tests")]
            compiler, _ = foundation["install_test_compiler"](root)
            suite = unittest.TestLoader().loadTestsFromNames(manifest["authored_test_targets"])
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            forbidden = sorted(name for name in sys.modules
                               if name.split(".", 1)[0] in foundation["FORBIDDEN_IMPORTS"])
            staged_unchanged = all((study / name).read_bytes() == raw for name, raw in sources.items())
            _, _, recaptured = capture_composition()
            unchanged = staged_unchanged and recaptured == sources
            passed = (result.wasSuccessful() and not result.skipped and not guard.attempts
                      and not forbidden and unchanged
                      and result.testsRun == manifest["expected_test_count"])
            summary = {
                "schema": "ora.scientific.publication-zero-world-checks.v3",
                "passed": passed,
                "tests_run": result.testsRun,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
                "authored_test_targets": manifest["authored_test_targets"],
                "composition_manifest_sha256": MANIFEST_SHA256,
                "reviewed_package_manifest_sha256": manifest["reviewed_package_manifest_sha256"],
                "reviewed_native_source_sha256": manifest["reviewed_native_source_sha256"],
                "composed_files_unchanged": unchanged,
                "forbidden_import_attempts": guard.attempts,
                "forbidden_modules_loaded": forbidden,
                "test_compiler": compiler,
                "foundation_150_test_suite_invoked": False,
                "C_test_scope": {
                    "disabled_binding_compiled_only": True,
                    "pure_receipt_harness_invoked": True,
                    "native_scientific_role_invoked": False,
                },
                "actual_api_calls": 0,
                "actual_world_calls": 0,
                "scientific_execution": False,
                "real_fixture_rerun": False,
                "elapsed_ns": time.monotonic_ns() - start,
            }
            print(json.dumps(summary, sort_keys=True))
            return 0 if passed else 1
    finally:
        os.chdir(original_cwd)
        sys.path[:] = original_path
        sys.meta_path.remove(guard)
        if original_environment_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = original_environment_path


if __name__ == "__main__":
    raise SystemExit(main())
