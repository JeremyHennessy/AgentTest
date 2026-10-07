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
import shlex
import shutil
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


def install_test_compiler(root):
    """Strip at link time, before the frozen builder hashes the native image.

    This wrapper is disposable test infrastructure, never a fixture compiler or
    an alteration of the captured launcher. The original 1 MiB check still runs.
    """
    compiler = shutil.which("cc")
    if compiler is None:
        raise RuntimeError("The native tests require an already installed C compiler")
    compiler = Path(compiler).resolve()
    directory = root / "test-compiler"
    directory.mkdir()
    wrapper = directory / "cc"
    source = "#!/bin/sh\nexec " + shlex.quote(str(compiler)) + ' -s "$@"\n'
    wrapper.write_text(source)
    wrapper.chmod(0o700)
    original_path = os.environ.get("PATH", os.defpath)
    os.environ["PATH"] = str(directory) + os.pathsep + original_path
    return {
        "scope": "disposable authored-test compiler only",
        "compiler": str(compiler),
        "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
        "wrapper": str(wrapper),
        "wrapper_source": source,
        "wrapper_sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        "added_link_flags": ["-s"],
    }, original_path


def verify_test_compiler(root, compiler_receipt, original_path):
    """Build, never execute, real authored launchers and check the unchanged cap."""
    from ora_study.launcher import MIB, _verify_build, build_launcher

    wrapped_path = os.environ["PATH"]
    try:
        os.environ["PATH"] = original_path
        unstripped = build_launcher(root / "unstripped-build")
    finally:
        os.environ["PATH"] = wrapped_path
    stripped = build_launcher(root / "stripped-build")
    unstripped_bytes = unstripped.read_bytes()
    stripped_bytes = stripped.read_bytes()
    receipt = json.loads((stripped.parent / "launcher-build.json").read_bytes())
    stripped_hash = hashlib.sha256(stripped_bytes).hexdigest()
    if receipt["compiler"] != compiler_receipt["wrapper"]:
        raise RuntimeError("Frozen builder did not use the test-only compiler wrapper")
    if receipt["binary_sha256"] != stripped_hash:
        raise RuntimeError("Frozen build receipt does not bind the compiled stripped bytes")
    if len(stripped_bytes) > len(unstripped_bytes):
        raise RuntimeError("Link-time stripping increased the authored binary size")
    _verify_build(stripped)  # Retains the original 1 MiB rejection without edits.

    # A hash-matched but oversized authored negative fixture must still fail.
    # It is never executed; this protects the cap independently of libc size.
    oversized_directory = root / "oversized-negative-build"
    oversized_directory.mkdir()
    oversized = oversized_directory / "launcher-native"
    oversized_bytes = stripped_bytes + b"\0" * (MIB + 1 - len(stripped_bytes))
    oversized.write_bytes(oversized_bytes)
    receipt["binary_sha256"] = hashlib.sha256(oversized_bytes).hexdigest()
    (oversized_directory / "launcher-build.json").write_text(json.dumps(receipt))
    try:
        _verify_build(oversized)
    except ValueError as error:
        if str(error) != "Native binary/source exceeds the frozen build bound":
            raise
    else:
        raise RuntimeError("Frozen launcher admitted the oversized negative fixture")
    return {
        "passed": True,
        "unstripped_binary_bytes": len(unstripped_bytes),
        "unstripped_binary_sha256": hashlib.sha256(unstripped_bytes).hexdigest(),
        "stripped_binary_bytes": len(stripped_bytes),
        "stripped_binary_sha256": stripped_hash,
        "bytes_removed": len(unstripped_bytes) - len(stripped_bytes),
        "frozen_binary_cap_bytes": MIB,
        "build_receipt_matches_compiled_binary": True,
        "oversized_negative_bytes": len(oversized_bytes),
        "oversized_negative_rejected": True,
        "launchers_executed_by_packaging_check": 0,
    }


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
    original_environment_path = os.environ.get("PATH")
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
            compiler_receipt, compiler_path = install_test_compiler(root)
            packaging_check = verify_test_compiler(root, compiler_receipt, compiler_path)
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
                "test_compiler": compiler_receipt,
                "compiler_packaging_check": packaging_check,
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
        if original_environment_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = original_environment_path


if __name__ == "__main__":
    raise SystemExit(main())
