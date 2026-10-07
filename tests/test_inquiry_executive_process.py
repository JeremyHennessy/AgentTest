"""Fresh-process crash/concurrency controls for the copied inquiry executive.

Only tiny authored synthetic inputs are used. These tests exercise POSIX flock,
atomic replacement and fsync on the filesystem running the suite; they do not
claim universal filesystem or power-loss durability, natural selection,
learning, or live activation. No selector output is injected or mocked. Faults
and transition spies are test-local only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CRASH_EXIT = 73
INPUTS = {"planning_lab_requested": False, "provenance": "synthetic_control"}


def _wait_for(path, seconds=40):
    deadline = time.monotonic() + seconds
    while not Path(path).exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("test process rendezvous did not arrive: " + str(path))
        time.sleep(0.01)


def _child(options):
    """Called only in a newly exec'd interpreter, never in the test runner."""
    import inquiry_executive.executive as executive_module
    import inquiry_executive.store as store_module
    from inquiry_executive.executive import InquiryExecutive
    from inquiry_executive.synthetic import create_sources

    root = Path(options["root"])
    research = root / "research"
    path = research / "capsule.json"
    metadata = root / "fixture.json"
    fault = options.get("fault")
    original_replace = store_module.os.replace
    original_fsync = store_module.os.fsync
    original_transition = executive_module.transition
    original_flock = store_module.fcntl.flock
    original_open = store_module.os.open

    def capture_staged():
        candidates = list(research.glob(".capsule.json.*.tmp"))
        if candidates:
            # Each crash fixture has exactly one attempted transaction.
            newest = max(candidates, key=lambda item: item.stat().st_mtime_ns)
            (root / "staged.json").write_bytes(newest.read_bytes())

    def open_file(name, flags, *args, **kwargs):
        if (fault == "before_temp_write" and isinstance(name, str)
                and name.startswith(".capsule.json.") and name.endswith(".tmp")
                and flags & os.O_CREAT and flags & os.O_EXCL):
            os._exit(CRASH_EXIT)
        return original_open(name, flags, *args, **kwargs)

    def fsync(fd):
        regular = stat.S_ISREG(os.fstat(fd).st_mode)
        if regular:
            capture_staged()
            if fault == "before_temp_fsync":
                os._exit(CRASH_EXIT)
        elif fault == "before_directory_fsync":
            os._exit(CRASH_EXIT)
        result = original_fsync(fd)
        if regular and fault == "after_temp_fsync":
            os._exit(CRASH_EXIT)
        if not regular and fault == "after_directory_fsync":
            os._exit(CRASH_EXIT)
        return result

    def replace(source, destination, **kwargs):
        capture_staged()
        if fault == "before_replace":
            os._exit(CRASH_EXIT)
        result = original_replace(source, destination, **kwargs)
        if fault == "after_replace":
            os._exit(CRASH_EXIT)
        if fault == "hold_after_replace":
            Path(options["holding"]).write_text("replacement committed, lock held")
            _wait_for(options["release"])
            os._exit(CRASH_EXIT)
        return result

    def transition(*args, **kwargs):
        # One short append is atomic across the test's two processes. The log
        # records calls to the actual private transition, not validation reads.
        with (root / "transition_calls.log").open("a") as handle:
            handle.write(str(os.getpid()) + "\n")
        if options.get("forbid_transition"):
            raise AssertionError("recovery/replay called the private world transition")
        result = original_transition(*args, **kwargs)
        if fault == "after_transition":
            os._exit(CRASH_EXIT)
        return result

    def flock(fd, operation):
        if options.get("contending"):
            Path(options["contending"]).write_text("about to acquire process lock")
        return original_flock(fd, operation)

    store_module.os.open = open_file
    store_module.os.fsync = fsync
    store_module.os.replace = replace
    store_module.fcntl.flock = flock
    executive_module.transition = transition

    action = options["action"]
    if action == "bootstrap":
        fixture = create_sources(root / "sources")
        research.mkdir()
        metadata.write_text(json.dumps({
            "source_paths": {key: str(fixture[key]) for key in ("ora", "world", "observations")},
            "proposal": fixture["proposal"], "provenance": fixture["provenance"],
        }))
        executive = InquiryExecutive.create(path, research_dir=research,
            source_paths={key: fixture[key] for key in ("ora", "world", "observations")}, enabled=True)
        phase = options.get("phase", "admitted")
        if phase != "initial":
            executive.admit(fixture["proposal"], 0)
        if phase in {"prepared", "committed"}:
            decision = executive.select_next(INPUTS, 1)
            assert decision["attempt_id"] is not None, decision
        if phase == "committed":
            executive.execute(decision["attempt_id"], 2)
        return {"state": executive.read()}

    if action == "create_retry":
        fixture = json.loads(metadata.read_text())
        executive = InquiryExecutive.create(path, research_dir=research,
            source_paths=fixture["source_paths"], enabled=True)
        return {"state": executive.read()}

    executive = InquiryExecutive(path, research_dir=research, enabled=True)
    if options.get("ready"):
        Path(options["ready"]).write_text("opened in a fresh process")
        _wait_for(options["go"])
    if action == "read":
        return {"state": executive.read()}
    if action == "select":
        return {"result": executive.select_next(INPUTS, options.get("revision", 1)),
                "state": executive.read()}
    if action == "execute":
        attempt_id = options.get("attempt_id") or executive.read()["attempts"][-1]["id"]
        outcome = executive.execute(attempt_id, options.get("revision", 2))
        if options.get("fail_export"):
            # Export is downstream of the durable transaction. Its failure must
            # not make a retry execute the world again.
            (root / "missing-export-directory" / "outcome.json").write_text(json.dumps(outcome))
        return {"result": outcome, "state": executive.read()}
    if action == "recover":
        return {"result": executive.recover_or_interpret(), "state": executive.read()}
    if action == "finish":
        attempt_id = options.get("attempt_id") or executive.read()["attempts"][-1]["id"]
        outcome = executive.execute(attempt_id, 2)
        belief = executive.recover_or_interpret()
        again_outcome = executive.execute(attempt_id, 2)
        again_belief = executive.recover_or_interpret()
        return {"result": outcome, "belief": belief, "again_outcome": again_outcome,
                "again_belief": again_belief, "state": executive.read()}
    raise AssertionError("unknown child operation: " + action)


@unittest.skipUnless(os.name == "posix", "process lock and crash controls require POSIX")
class InquiryExecutiveProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture_number = 0
        self.sources = {}
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                        PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT / "experiments"))))

    def tearDown(self):
        for path, original in self.sources.items():
            self.assertEqual(path.read_bytes(), original, "a protected copied source changed")

    def command(self, root, action, **options):
        return [sys.executable, str(Path(__file__).resolve()), "--capsule-child",
                json.dumps({"root": str(root), "action": action, **options})]

    def call(self, root, action, *, expected=0, **options):
        completed = subprocess.run(self.command(root, action, **options), cwd=ROOT,
            env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
        if expected == CRASH_EXIT:
            self.assertEqual(completed.stdout, "", "an interrupted call unexpectedly returned")
            return None
        return json.loads(completed.stdout)

    def start(self, root, action, **options):
        process = subprocess.Popen(self.command(root, action, **options), cwd=ROOT,
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, process)
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    def collect(self, process, expected=0):
        stdout, stderr = process.communicate(timeout=60)
        self.assertEqual(process.returncode, expected, stdout + stderr)
        return json.loads(stdout) if stdout else None

    def new_fixture(self, phase="admitted", *, fault=None):
        self.fixture_number += 1
        root = self.root / str(self.fixture_number)
        root.mkdir()
        result = self.call(root, "bootstrap", phase=phase, fault=fault,
                           expected=CRASH_EXIT if fault else 0)
        for path in (root / "sources").glob("*.json"):
            self.sources[path] = path.read_bytes()
        if result is not None:
            self.assertEqual(json.loads((root / "fixture.json").read_text())["provenance"]["label"],
                             "synthetic_control")
        return root, result["state"] if result else None

    @staticmethod
    def capsule(root):
        return root / "research" / "capsule.json"

    @staticmethod
    def calls(root):
        path = root / "transition_calls.log"
        return len(path.read_text().splitlines()) if path.exists() else 0

    def read(self, root):
        return self.call(root, "read", forbid_transition=True)["state"]

    def assert_stage(self, state, phase):
        actions = int(phase in {"committed", "interpreted"})
        beliefs = int(phase == "interpreted")
        decisions = int(phase in {"prepared", "committed", "interpreted"})
        self.assertEqual(state["revision"], 1 + decisions + actions + beliefs)
        self.assertEqual(state["counters"], dict(inquiries=1, decisions=decisions,
            attempts=decisions, outcomes=actions, beliefs=beliefs, actions=actions))
        self.assertEqual(len(state["frames"]), state["identity"]["initial_frame_count"] + actions)
        self.assertEqual(state["world"]["cycle"], 3 + actions)
        self.assertEqual(len(state["world"]["history"]), 3 + actions)
        self.assertEqual(len(state["events"]), state["revision"])
        self.assertEqual(state["reserve"], {"admitted": 0, "prepared": 1_048_576,
            "committed": 131_072, "interpreted": 0}[phase])
        self.assertEqual([row["status"] for row in state["attempts"]], [phase] if decisions else [])
        self.assertEqual(sum(row["status"] in {"prepared", "committed"} for row in state["attempts"]),
                         int(phase in {"prepared", "committed"}))

    def finish(self, root, prepared, *, forbid_transition=False):
        result = self.call(root, "finish", forbid_transition=forbid_transition)
        self.assertEqual(result["result"], result["again_outcome"])
        self.assertEqual(result["belief"], result["again_belief"])
        state = result["state"]
        self.assert_stage(state, "interpreted")
        self.assertEqual(state["attempts"][0]["contract"], prepared["attempts"][0]["contract"])
        self.assertEqual(state["outcomes"][0], result["result"])
        self.assertEqual(state["beliefs"][0], result["belief"])
        self.assertEqual(state["outcomes"][0]["attempt_id"], state["attempts"][0]["id"])
        self.assertEqual(state["outcomes"][0]["receipt"], state["frames"][-1]["receipt"])
        self.assertEqual(state["outcomes"][0]["receipt"], state["world"]["history"][-1])
        self.assertEqual(state["beliefs"][0]["outcome_id"], state["outcomes"][0]["id"])
        before_replay = self.capsule(root).read_bytes()
        replay = self.call(root, "finish", forbid_transition=True)
        self.assertEqual(replay, result)
        self.assertEqual(self.capsule(root).read_bytes(), before_replay)
        return state

    def test_t1_temp_write_fsync_and_replace_crashes_are_wholly_old_or_new(self):
        boundaries = ("before_temp_write", "before_temp_fsync", "after_temp_fsync", "before_replace",
                      "after_replace", "before_directory_fsync", "after_directory_fsync")
        for fault in boundaries:
            with self.subTest(boundary=fault):
                root, admitted = self.new_fixture()
                old = self.capsule(root).read_bytes()
                self.call(root, "select", fault=fault, expected=CRASH_EXIT)
                replaced = fault in {"after_replace", "before_directory_fsync", "after_directory_fsync"}
                self.assertEqual(self.capsule(root).read_bytes(),
                                 (root / "staged.json").read_bytes() if replaced else old)
                state = self.read(root)
                self.assert_stage(state, "prepared" if replaced else "admitted")
                self.assertEqual(state["world"], admitted["world"])
                self.assertEqual(state["frames"], admitted["frames"])
                self.assertEqual(self.calls(root), 0)
                if not replaced:
                    state = self.call(root, "select")["state"]
                self.finish(root, state)
                self.assertEqual(self.calls(root), 1)

    def test_restart_after_t1_does_not_select_or_execute_without_request(self):
        root, prepared = self.new_fixture("prepared")
        before = self.capsule(root).read_bytes()
        recovered = self.call(root, "recover", forbid_transition=True)
        self.assertIsNone(recovered["result"])
        self.assertEqual(recovered["state"], prepared)
        self.assertEqual(self.read(root), prepared)
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.assertEqual(self.calls(root), 0)
        self.finish(root, prepared)
        self.assertEqual(self.calls(root), 1)

    def test_crash_after_pure_transition_before_t2_leaves_exact_prepared_state(self):
        root, prepared = self.new_fixture("prepared")
        before = self.capsule(root).read_bytes()
        self.call(root, "execute", fault="after_transition", expected=CRASH_EXIT)
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.assertEqual(self.read(root), prepared)
        self.assertEqual(self.calls(root), 1)
        self.finish(root, prepared)
        # Recomputing an uncommitted pure transition is allowed; only one world
        # revision, action, receipt, outcome and belief can be committed.
        self.assertEqual(self.calls(root), 2)

    def test_t2_before_replace_crash_cannot_commit_or_recover_staged_outcome(self):
        root, prepared = self.new_fixture("prepared")
        before = self.capsule(root).read_bytes()
        self.call(root, "execute", fault="before_replace", expected=CRASH_EXIT)
        self.assertTrue(list((root / "research").glob(".capsule.json.*.tmp")))
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.assertEqual(self.read(root), prepared)
        self.assertIsNone(self.call(root, "recover", forbid_transition=True)["result"])
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.finish(root, prepared)
        self.assertEqual(self.calls(root), 2)

    def test_t2_after_replace_lost_response_recovers_full_outcome_without_replay(self):
        for fault in ("after_replace", "before_directory_fsync", "after_directory_fsync"):
            with self.subTest(boundary=fault):
                root, prepared = self.new_fixture("prepared")
                self.call(root, "execute", fault=fault, expected=CRASH_EXIT)
                self.assertEqual(self.capsule(root).read_bytes(), (root / "staged.json").read_bytes())
                committed = self.read(root)
                self.assert_stage(committed, "committed")
                self.assertEqual(self.calls(root), 1)
                final = self.finish(root, prepared, forbid_transition=True)
                self.assertEqual(final["world"], committed["world"])
                self.assertEqual(final["frames"], committed["frames"])
                self.assertEqual(final["outcomes"], committed["outcomes"])
                self.assertEqual(self.calls(root), 1)

    def test_t3_before_and_after_replace_interpret_at_most_once(self):
        for fault in ("before_replace", "after_replace", "before_directory_fsync", "after_directory_fsync"):
            with self.subTest(boundary=fault):
                root, committed = self.new_fixture("committed")
                before = self.capsule(root).read_bytes()
                self.call(root, "recover", fault=fault, forbid_transition=True, expected=CRASH_EXIT)
                replaced = fault != "before_replace"
                self.assertEqual(self.capsule(root).read_bytes(),
                    (root / "staged.json").read_bytes() if replaced else before)
                recovered = self.read(root)
                self.assert_stage(recovered, "interpreted" if replaced else "committed")
                self.assertEqual(recovered["world"], committed["world"])
                self.assertEqual(recovered["outcomes"], committed["outcomes"])
                self.finish(root, committed, forbid_transition=True)
                self.assertEqual(self.calls(root), 1)

    def test_two_processes_execute_one_prepared_attempt_exactly_once(self):
        root, prepared = self.new_fixture("prepared")
        go = root / "go"
        processes = [self.start(root, "execute", ready=str(root / ("ready" + str(i))), go=str(go))
                     for i in range(2)]
        for i in range(2):
            _wait_for(root / ("ready" + str(i)))
        go.write_text("race")
        results = [self.collect(process) for process in processes]
        self.assertEqual(results[0]["result"], results[1]["result"])
        self.assert_stage(self.read(root), "committed")
        self.assertEqual(self.calls(root), 1)
        self.finish(root, prepared, forbid_transition=True)
        self.assertEqual(self.calls(root), 1)

    def test_two_processes_recover_one_committed_outcome_into_one_belief(self):
        root, committed = self.new_fixture("committed")
        go = root / "go"
        processes = [self.start(root, "recover", ready=str(root / ("ready" + str(i))),
                                go=str(go), forbid_transition=True) for i in range(2)]
        for i in range(2):
            _wait_for(root / ("ready" + str(i)))
        go.write_text("race")
        results = [self.collect(process) for process in processes]
        self.assertEqual(results[0]["result"], results[1]["result"])
        state = self.read(root)
        self.assert_stage(state, "interpreted")
        self.assertEqual(state["world"], committed["world"])
        self.assertEqual(state["outcomes"], committed["outcomes"])
        self.assertEqual(self.calls(root), 1)
        self.finish(root, committed, forbid_transition=True)
        self.assertEqual(self.calls(root), 1)

    def test_two_process_selection_cas_has_one_conflict_and_one_capability(self):
        root, admitted = self.new_fixture()
        go = root / "go"
        processes = [self.start(root, "select", ready=str(root / ("ready" + str(i))), go=str(go))
                     for i in range(2)]
        for i in range(2):
            _wait_for(root / ("ready" + str(i)))
        go.write_text("race")
        completed = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=60)
            self.assertIn(process.returncode, (0, 3), stdout + stderr)
            completed.append((process.returncode, json.loads(stdout)))
        self.assertEqual(sorted(code for code, _ in completed), [0, 3])
        conflict = next(result for code, result in completed if code == 3)
        self.assertEqual(conflict["error_type"], "Conflict")
        self.assertIn("revision", conflict["error"])
        prepared = self.read(root)
        self.assert_stage(prepared, "prepared")
        self.assertEqual(prepared["world"], admitted["world"])
        self.assertEqual(self.calls(root), 0)
        self.finish(root, prepared)
        self.assertEqual(self.calls(root), 1)

    def test_crashed_lock_holder_releases_waiter_to_existing_committed_outcome(self):
        root, prepared = self.new_fixture("prepared")
        lock = root / "research" / "capsule.json.lock"
        identity = (lock.stat().st_dev, lock.stat().st_ino)
        holding, release, contending = (root / name for name in ("holding", "release", "contending"))
        owner = self.start(root, "execute", fault="hold_after_replace",
                           holding=str(holding), release=str(release))
        _wait_for(holding)
        waiter = self.start(root, "execute", contending=str(contending), forbid_transition=True)
        _wait_for(contending)
        # Owner still holds an exclusive kernel lock after atomic replacement.
        time.sleep(0.1)
        self.assertIsNone(waiter.poll(), "second interpreter bypassed the process lock")
        self.assertIsNone(owner.poll())
        release.write_text("interrupt owner")
        self.collect(owner, CRASH_EXIT)
        result = self.collect(waiter)
        self.assert_stage(result["state"], "committed")
        self.assertEqual(result["result"], result["state"]["outcomes"][0])
        self.assertEqual((lock.stat().st_dev, lock.stat().st_ino), identity)
        self.finish(root, prepared, forbid_transition=True)
        self.assertEqual(self.calls(root), 1)

    def test_corrupt_truncated_empty_and_missing_authoritative_capsules_reject(self):
        for kind in ("corrupt", "truncated", "empty", "missing"):
            with self.subTest(kind=kind):
                root, _ = self.new_fixture("prepared")
                path = self.capsule(root)
                old = path.read_bytes()
                stray = path.parent / ".capsule.json.valid-but-uncommitted.tmp"
                stray.write_bytes(old)
                if kind == "missing":
                    path.unlink()
                elif kind == "truncated":
                    path.write_bytes(old[:len(old) // 2])
                elif kind == "empty":
                    path.write_bytes(b"")
                else:
                    damaged = json.loads(old)
                    damaged["revision"] += 1
                    path.write_text(json.dumps(damaged))
                bad = path.read_bytes() if path.exists() else None
                for action in ("read", "execute", "recover"):
                    rejected = self.call(root, action, expected=3, forbid_transition=True)
                    self.assertIn(rejected["error_type"], ("Conflict", "FileNotFoundError"))
                    self.assertEqual(path.read_bytes() if path.exists() else None, bad)
                    self.assertEqual(stray.read_bytes(), old)
                self.assertEqual(self.calls(root), 0)

    def test_stray_prepared_temporary_file_never_overrides_authoritative_state(self):
        root, admitted = self.new_fixture()
        before = self.capsule(root).read_bytes()
        self.call(root, "select", fault="before_replace", expected=CRASH_EXIT)
        strays = list((root / "research").glob(".capsule.json.*.tmp"))
        self.assertEqual(len(strays), 1)
        staged = json.loads(strays[0].read_bytes())
        self.assert_stage(staged, "prepared")
        self.assertEqual(self.read(root), admitted)
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.capsule(root).unlink()
        self.assertEqual(self.call(root, "read", expected=3)["error_type"], "FileNotFoundError")
        self.assertFalse(self.capsule(root).exists())
        self.assertTrue(strays[0].exists())

    def test_failed_creation_retries_with_same_orphan_lock_without_temp_recovery(self):
        for fault in ("before_temp_fsync", "after_temp_fsync", "before_replace"):
            with self.subTest(boundary=fault):
                root, _ = self.new_fixture("initial", fault=fault)
                self.assertFalse(self.capsule(root).exists())
                lock = root / "research" / "capsule.json.lock"
                identity = (lock.stat().st_dev, lock.stat().st_ino)
                strays = list((root / "research").glob(".capsule.json.*.tmp"))
                self.assertEqual(len(strays), 1)
                orphan = strays[0].read_bytes()
                self.assertEqual(self.call(root, "read", expected=3)["error_type"], "FileNotFoundError")
                created = self.call(root, "create_retry")["state"]
                self.assertEqual(created["revision"], 0)
                self.assertTrue(all(value == 0 for value in created["counters"].values()))
                self.assertEqual((lock.stat().st_dev, lock.stat().st_ino), identity)
                self.assertEqual(strays[0].read_bytes(), orphan)
                self.assertNotEqual(created["identity"]["run_id"], json.loads(orphan)["identity"]["run_id"])
                self.assertEqual(self.read(root), created)
                self.assertEqual(self.calls(root), 0)

    def test_creation_lost_response_reopens_existing_run_and_rejects_recreation(self):
        root, _ = self.new_fixture("initial", fault="after_replace")
        before = self.capsule(root).read_bytes()
        initial = self.read(root)
        self.assertEqual(initial["revision"], 0)
        failure = self.call(root, "create_retry", expected=3)
        self.assertEqual(failure["error_type"], "Conflict")
        self.assertIn("already exists", failure["error"])
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.assertEqual(self.read(root), initial)

    def test_export_failure_after_t2_does_not_replay_action(self):
        root, prepared = self.new_fixture("prepared")
        failure = self.call(root, "execute", fail_export=True, expected=3)
        self.assertEqual(failure["error_type"], "FileNotFoundError")
        self.assert_stage(self.read(root), "committed")
        self.finish(root, prepared, forbid_transition=True)
        self.assertEqual(self.calls(root), 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--capsule-child":
        try:
            output = _child(json.loads(sys.argv[2]))
        except Exception as error:
            print(json.dumps({"error_type": type(error).__name__, "error": str(error)}))
            raise SystemExit(3)
        print(json.dumps(output, sort_keys=True))
    else:
        unittest.main()
