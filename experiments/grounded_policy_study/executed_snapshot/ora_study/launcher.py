"""Build/run only the authored, zero-world-call native resource fixture.

This module has no scientific dispatch interface. The native source admits a
fixed mode list and cannot import or execute a selected external worker. Its
limits are a composition prototype, not permission to execute the study.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

SOURCE = Path(__file__).with_name("launcher_native.c")
MIB = 1024 * 1024
MODES = frozenset(("success", "source_failure", "startup_failure", "child_failure",
                  "controller_failure", "controller_orphan", "controller_early_death", "hang", "cpu",
                  "stdout_flood", "stderr_flood", "allocation", "nproc",
                  "report_failure", "seal_failure", "report_hang", "finalize_hang", "finalize_blocked_write", "supervisor_hang", "python_controller"))
ENVIRONMENT = {"LANG": "C", "LC_ALL": "C"}
REPORT_OFFSET = 65536
REPORT_CAP = 8192


def build_launcher(build_dir, *, fixture_source_mismatch=False):
    """Build the authored zero-world role; default tests never bind an API role."""
    return _build_launcher(build_dir, fixture_source_mismatch=fixture_source_mismatch)


def build_pending_native_fixture_launcher(build_dir, profile_path):
    """Bind one exact prospective software-fixture profile, without executing it.

    The native source guard and both controller admission guards remain False.
    No GO receipt is written or inferred. Public run_launcher does not admit
    this role. A separate source/profile review is required before activation.
    """
    path = Path(profile_path)
    if path.is_symlink():
        raise ValueError("Fixture profile must be a regular unaliased file")
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Fixture profile exceeds its fixed bound")
    profile = json.loads(raw)
    keys = {"schema", "profile", "fixture_id", "output_root", "api_root", "api_manifest",
            "api_runtime_manifest", "python_sha256", "admission_receipt_path", "started_marker_path"}
    if type(profile) is not dict or set(profile) != keys:
        raise ValueError("Unexpected native fixture profile schema")
    if (profile["schema"] != "ora.native-fixture.launch.v1" or
            profile["profile"] != "one_native_invariant_pair_v1" or
            profile["fixture_id"] != "ora-bounded-native-invariant-2026-10-07-v1"):
        raise ValueError("Only the fixed prospective two-case fixture may be bound")
    for key in ("output_root", "api_root", "admission_receipt_path", "started_marker_path"):
        value = profile[key]
        if not isinstance(value, str) or len(os.fsencode(value)) > 4095:
            raise ValueError("Profile path exceeds bound")
        target = Path(value)
        if not target.is_absolute() or str(target.resolve()) != value or target.is_symlink():
            raise ValueError("Profile paths must be absolute and canonical")
    fixed_marker = SOURCE.parent.resolve().parents[1] / "policy-study-results" / "ONE_NATIVE_INVARIANT_STARTED.json"
    if profile["started_marker_path"] != str(fixed_marker):
        raise ValueError("Fixture one-attempt marker cannot be relocated")
    if Path(profile["output_root"]).exists():
        raise FileExistsError("Prospective output root already exists")
    api_manifest = profile["api_manifest"]
    if not isinstance(api_manifest, dict) or not api_manifest:
        raise ValueError("Missing fixed API source manifest")
    for name, wanted in api_manifest.items():
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts or relative.suffix != ".py" or
                not isinstance(wanted, str) or len(wanted) != 64 or
                any(c not in "0123456789abcdef" for c in wanted)):
            raise ValueError("Invalid fixed API source entry")
    actual_python = hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
    runtime = profile["api_runtime_manifest"]
    if (profile["python_sha256"] != actual_python or not isinstance(runtime, dict) or
            runtime.get("executable_hash") != actual_python):
        raise ValueError("Prospective interpreter binding differs")
    return _build_launcher(build_dir, pending_profile=(profile, raw))


def _build_launcher(build_dir, *, fixture_source_mismatch=False, pending_profile=None):
    """Compile authored C using an already installed compiler, once per directory.

    Compilation and this build receipt are preparation, never a scientific run.
    No download, package installation, source import or simulator call occurs.
    """
    compiler = shutil.which("cc")
    if compiler is None:
        raise RuntimeError("No installed C compiler; nothing was installed")
    root = Path(build_dir)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    binary = root / "launcher-native"
    package_root = SOURCE.parent.resolve()
    controller_name = "native_fixture_controller.py" if pending_profile else "launcher_python_controller.py"
    controller_path = package_root / controller_name
    controller_bytes = controller_path.read_bytes() if controller_path.is_file() else b""
    if len(controller_bytes) > 64 * 1024:
        raise ValueError("Fixed controller source exceeds compile-time bound")
    source_manifest = {str(path.relative_to(package_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sorted(package_root.rglob("*.py"))}
    if controller_bytes and source_manifest.get(controller_name) != hashlib.sha256(controller_bytes).hexdigest():
        raise ValueError("Controller changed while capturing its build")
    if pending_profile and not controller_bytes:
        raise ValueError("Fixed prospective controller is missing")
    if fixture_source_mismatch:
        # Explicit negative software fixture. No actual source file changes.
        source_manifest["driver.py"] = "0" * 64
    manifest_path = root / "launcher-package-manifest.json"
    manifest_bytes = json.dumps(source_manifest, sort_keys=True, separators=(",", ":")).encode()
    if len(manifest_bytes) > 16384:
        raise ValueError("Package manifest exceeds frozen bound")
    manifest_path.write_bytes(manifest_bytes)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    bindings = {
        "ORA_PYTHON_PATH": sys.executable,
        "ORA_PY_CONTROLLER_SOURCE": controller_bytes.decode("utf-8"),
        "ORA_PACKAGE_ROOT": str(package_root),
        "ORA_MANIFEST_PATH": str(manifest_path.resolve()),
        "ORA_MANIFEST_SHA256": manifest_hash,
        "ORA_CHILD_EXE": str(binary.resolve()),
    }
    profile_hash = None
    if pending_profile:
        profile, profile_raw = pending_profile
        bound_profile_path = root / "launcher-native-fixture-profile.json"
        bound_profile_path.write_bytes(profile_raw)
        profile_hash = hashlib.sha256(profile_raw).hexdigest()
        bindings.update({"ORA_FIXTURE_PROFILE_PATH": str(bound_profile_path.resolve()),
                         "ORA_FIXTURE_PROFILE_SHA256": profile_hash,
                         "ORA_FIXTURE_OUTPUT_ROOT": profile["output_root"]})
    command = [compiler, "-static", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror"]
    if pending_profile:
        command.append("-DORA_NATIVE_FIXTURE_BINDING=1")
    command += ["-D" + key + "=" + json.dumps(value) for key, value in bindings.items()]
    command += ["-o", str(binary), str(SOURCE)]
    built = subprocess.run(command, env={**ENVIRONMENT, "PATH": "/usr/bin:/bin"},
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    if built.returncode:
        raise RuntimeError("Native build failed: " + built.stderr[:8192].decode("utf-8", "replace"))
    receipt = {"schema": "ora.launcher.build.v1", "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
               "compiler": compiler,
               "command": [arg if not arg.startswith("-DORA_PY_CONTROLLER_SOURCE=") else "-DORA_PY_CONTROLLER_SOURCE=<captured source SHA256 below>" for arg in command],
               "controller_source_sha256": hashlib.sha256(controller_bytes).hexdigest(),
               "package_manifest_sha256": manifest_hash,
               "fixed_python_executable": sys.executable,
               "fixed_package_root": str(package_root),
               "fixture_source_mismatch": fixture_source_mismatch,
               "controller_role": "pending_native_fixture" if pending_profile else "authored_zero_world",
               "native_fixture_profile_sha256": profile_hash,
               "native_fixture_admission_reviewed": False,
               "world_calls": 0, "scientific_execution_allowed": False,
               "scope": "Build provenance only, not a complete loaded-source freeze"}
    (root / "launcher-build.json").write_text(json.dumps(receipt, sort_keys=True, indent=2)+"\n")
    return binary


def _before_exec():
    """External software-test setup only, not a required live launcher helper.

    It ensures the native image inherits the declared limits at exec. The
    supported actual entry is the static native program, whose own bootstrap,
    source checks and child lifetime share its process-birth origin.
    """
    resource.setrlimit(resource.RLIMIT_AS, (32*MIB, 384*MIB))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MIB, MIB))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))


def read_reserved_status(output_dir, *, expired=False):
    """Recover the latest complete JSON slot; never invent missing stub counts."""
    path = Path(output_dir) / "launcher.status"
    with path.open("rb") as stream:
        initial = stream.read(REPORT_CAP)
        stream.seek(REPORT_OFFSET)
        terminal = stream.read(REPORT_CAP)
    for raw in ((initial,) if expired else (terminal, initial)):
        line, delimiter, _ = raw.partition(b"\n")
        if not delimiter:
            continue
        try:
            row = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if row.get("schema") == "ora.launcher.stub.v1":
            return row
    raise RuntimeError("No verified reserved status slot; stub counts unknown")


def _validate_request(output_dir, mode, wall_ms):
    if mode not in MODES:
        raise ValueError("Only authored zero-world-call modes are permitted")
    if type(wall_ms) is not int or not 250 <= wall_ms <= 850_000:
        raise ValueError("wall_ms must be a bounded integer in [250, 850000]")
    root = Path(output_dir)
    if root.exists() or root.is_symlink():
        raise FileExistsError(root)
    if not root.parent.is_dir():
        raise FileNotFoundError(root.parent)
    if len(os.fsencode(root)) > 4095:
        raise ValueError("Output path exceeds native argument bound")
    return root


def _verify_build(binary):
    binary = Path(binary)
    receipt_path = binary.parent / "launcher-build.json"
    if binary.name != "launcher-native" or not receipt_path.is_file() or receipt_path.stat().st_size > REPORT_CAP:
        raise ValueError("Only a launcher built by build_launcher is permitted")
    with receipt_path.open("rb") as stream:
        raw = stream.read(REPORT_CAP + 1)
    if len(raw) > REPORT_CAP:
        raise ValueError("Build receipt grew past its bound")
    receipt = json.loads(raw)
    with binary.open("rb") as stream:
        binary_bytes = stream.read(MIB + 1)
    with SOURCE.open("rb") as stream:
        source_bytes = stream.read(128 * 1024 + 1)
    if len(binary_bytes) > MIB or len(source_bytes) > 128 * 1024:
        raise ValueError("Native binary/source exceeds the frozen build bound")
    if receipt.get("source_sha256") != hashlib.sha256(source_bytes).hexdigest() or receipt.get("binary_sha256") != hashlib.sha256(binary_bytes).hexdigest():
        raise ValueError("Authored launcher source or binary changed after build")
    return binary


def run_launcher(binary, output_dir, *, mode="success", wall_ms=3000, route="direct"):
    """External test observer; actual entry is the static native executable.

    Invoke the binary directly with output_dir, authored mode and wall_ms.
    No Python helper or observer is required by that process tree. This
    function only observes software fixtures from outside their resource unit.
    Python cannot initialize under this environment's outer32 MiB AS bound,
    so there is deliberately no Python-prefix launcher route.
    """
    root = _validate_request(output_dir, mode, wall_ms)
    if route != "direct":
        raise ValueError("Unknown launcher route")
    binary = Path(binary)
    if binary.name != "launcher-native":
        raise ValueError("Only the authored launcher is permitted")
    started = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    # This is a software-test provenance check outside the native resource
    # unit. The actual direct entry performs its own source-identity checks
    # only after arming expiry and reserving its failure record.
    binary = _verify_build(binary)
    command = [str(binary), str(root), mode, str(wall_ms)]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=ENVIRONMENT, close_fds=True,
                               start_new_session=True, preexec_fn=_before_exec)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=wall_ms/1000+2)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=2)
    exited = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    if len(stdout) > REPORT_CAP or len(stderr) > REPORT_CAP:
        raise RuntimeError("Native launcher broke its source-audited stream cap")
    if not (root / "launcher.status").is_file():
        raise RuntimeError(f"Launcher stopped before reserved report: exit={process.returncode}")
    expired = process.returncode in (124, -signal.SIGALRM)
    result = read_reserved_status(root, expired=expired)
    if expired:
        result["classification"] = "incomplete"
        result["reason"] = "kernel_expiry_observed"
        result["phase"] = "terminal_exit"
    result["observer"] = {"before_popen_boottime_ns": started, "reaped_boottime_ns": exited,
                          "outer_pid": process.pid, "returncode": process.returncode,
                          "entry_route": route, "kernel_expiry_observed": expired,
                          "emergency_timeout": timed_out, "native_stdout_bytes": len(stdout),
                          "native_stderr_bytes": len(stderr),
                          "exit_observed_after_finalization": not timed_out and process.returncode in (0, 2),
                          "exit_observed_within_deadline": "deadline_ns" in result and exited <= result["deadline_ns"],
                          "world_calls": 0, "realtime_deadline_guarantee_claimed": False}
    return result
