"""Review-only external controller with an explicit zero-simulator stub runner.

There is deliberately no scientific worker dispatch path. Changing a command
line switch cannot admit science. run_scientific() fails before creating files.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
from .ledger import Ledger, IntegrityError, CapacityError
from .protocol import canonical, registry
from .resources import BudgetedFiles, Window, environment_evidence

STUB_MODES = {"success", "fail_before_start", "fail_after_start", "fail_after_compute", "lost_response", "hang", "bad_json", "stderr_flood"}

def run_scientific(*args, **kwargs):
    raise IntegrityError("SCIENTIFIC RUN NO-GO: reviewed resource enforcement, adapter and combined approval required")

def _kill_group(process):
    if process is not None and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_stub(root, *, mode="success", wall_ns=5_000_000_000, inject_phase=None):
    """Bounded integration fixture. All child work is authored JSON arithmetic.

    Never calls GroundedExecutive, initial_world, Core, selector or transition.
    Existing directories are never reused. Returned metrics are fixture metrics.
    """
    window = Window()  # before source validation, output creation or child startup
    process = None
    ledger = None
    files = None
    selector = None
    root = Path(root)
    phase = "startup"
    result = {"schema": "ora.controller.fixture-result.v1", "data_kind": "synthetic_fixture",
              "scientific_execution": "NOT_RUN", "science_transition_invocations": 0,
              "classification": "incomplete", "phase": phase, "reason": "Startup not completed",
              "known_counters": {"scheduled_arm_cases": 0, "scheduled_decisions": 0, "actual_invocations": 0, "science_transition_invocations": 0, "reason": "No child dispatched before registration"}, "resource_guarantee": "observational only", "last_validated_state": None}
    try:
        if mode not in STUB_MODES:
            raise IntegrityError("Only explicit zero-simulator fixture modes are accepted")
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
        files = BudgetedFiles(root)
        # Usable reserved status exists before all validations/child startup.
        files.write("initial-status.json", result)
        ledger = Ledger(root/"ledger.jsonl", create=True)
        result["last_validated_state"] = "all64arm-cases-and128decisions-registered"
        for check_phase in ("source_validation", "locking", "restart"):
            phase = check_phase
            if inject_phase == phase:
                raise IntegrityError("Injected " + phase + " failure")
        phase = "worker_startup"
        if inject_phase == phase:
            raise OSError("Injected child startup failure")
        worker = Path(__file__).with_name("stub_worker.py")
        # Pin exact script bytes in fixture ledger before spawning an isolated interpreter.
        ledger.append("fixture_worker_source", {"path": str(worker), "sha256": hashlib.sha256(worker.read_bytes()).hexdigest()})
        decision = registry()["decision_ids"][0]
        ledger.decision_start(decision)
        ticket = ledger.charge("owned", "owned."+decision)
        child_env = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
        process = subprocess.Popen([sys.executable, "-I", "-S", "-B", str(worker), mode],
            cwd=root, env=child_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, bufsize=0, close_fds=True)
        ledger.append("worker_spawned", {"pid": process.pid, "mode": mode, "ticket": ticket,
                                          "credential_environment_passed": False, "isolated_interpreter": True})
        process.stdin.write(b"go\n")
        process.stdin.close()
        selector = selectors.DefaultSelector()
        for pipe in (process.stdout, process.stderr):
            selector.register(pipe, selectors.EVENT_READ)
        buffers = {process.stdout: b"", process.stderr: b""}
        completed = False
        phase = "worker"
        while selector.get_map():
            window.check(wall_ns=wall_ns)
            for key, _ in selector.select(timeout=0.01):
                block = os.read(key.fileobj.fileno(), 8192)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                buffers[key.fileobj] += block
                if len(buffers[key.fileobj]) > 16384:
                    raise CapacityError("Bounded worker pipe exceeded; output retained only as bounded prefix")
                if key.fileobj is process.stderr:
                    continue
                while b"\n" in buffers[key.fileobj]:
                    line, buffers[key.fileobj] = buffers[key.fileobj].split(b"\n", 1)
                    row = json.loads(line)
                    event = row["event"]
                    if event == "started":
                        ledger.advance(ticket, "started")
                    elif event == "computed":
                        ledger.advance(ticket, "computed", result_hash=row["result_hash"])
                    elif event == "durable":
                        # Saved authored stub proof, never a capsule or scientific outcome.
                        files.write("stub-proof.json", row)
                        ledger.advance(ticket, "durably_consumed", result_hash=row["result_hash"], authority_hash=row["authority_hash"])
                    elif event == "done":
                        if completed:
                            raise IntegrityError("Duplicate done")
                        completed = True
                    else:
                        raise IntegrityError("Unknown child event")
            if process.poll() is not None and not selector.get_map():
                break
        returncode = process.wait()
        if buffers[process.stdout]:
            raise IntegrityError("Incomplete child JSON record")
        if returncode != 0 or not completed:
            raise OSError(f"Child ended without complete response (exit {returncode}); never replay")
        if ledger.counters()["durably_consumed_verified"] != 1:
            raise IntegrityError("Success lacks durable evidence")
        ledger.decision_commit(decision, receipt_hash="a"*64, is_null=False)
        phase = "report"
        if inject_phase == phase:
            raise OSError("Injected report interruption")
        # Efficacy is intentionally absent; this reports only the fixture lifecycle.
        files.write("fixture-records.json", {"ledger_head": ledger.records[-1]["hash"], "mode": mode})
        phase = "seal"
        if inject_phase == phase:
            raise OSError("Injected sealing interruption")
        files.write("fixture-seal.json", {"ledger_head": ledger.records[-1]["hash"], "not_scientific": True})
        phase = "cleanup"
        if inject_phase == phase:
            raise OSError("Injected cleanup interruption")
        result.update(classification="fixture_complete", reason="Zero-simulator child fixture completed", last_validated_state="fixture-sealed")
    except (IntegrityError, ValueError, KeyError, TypeError) as error:
        result.update(classification="invalid", reason=str(error))
    except BaseException as error:
        result.update(classification="incomplete", reason=type(error).__name__+": "+str(error))
    finally:
        _kill_group(process)
        if selector is not None:
            selector.close()
        if process is not None:
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
        result["phase"] = phase
        if ledger is not None:
            result["known_counters"] = ledger.counters()
            if ledger.broken:
                result.update(classification="invalid", reason="Ledger evidence uncertain: "+result["reason"])
            elif result["known_counters"]["actual_invocations"] is None:
                result.update(classification="invalid", reason="Exact invocation count unverifiable; known bounds preserved: "+result["reason"])
            ledger.close()
        result["resources"] = window.sample()
        if files is not None:
            try:
                result["persisted_bytes_before_terminal"] = files.used()
                files.write("terminal.json", result, final=True)
                # This snapshot includes terminal write/lock/fsync, but the persisted
                # terminal cannot contain a measurement of its own future close.
                result["resources_after_terminal_write"] = window.sample()
                result["persisted_bytes_after_terminal"] = files.used()
            except BaseException as error:
                result.update(classification="invalid" if isinstance(error, IntegrityError) else "incomplete",
                              terminal_persistence_error=type(error).__name__+": "+str(error))
        # Caller/stdout is fallback evidence when no writable result directory exists.
    return result
