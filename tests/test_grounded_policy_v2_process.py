"""Fresh-process crash/CAS controls using tiny authored synthetic worlds.

Every child imports grounded_policy_v2 before any Ora/Challenge dependency in a
fresh source-only -B interpreter. Two north setup moves create the only cohort;
no historical input, scientific 64-step stream, paired corpus, scorer, runner or
publication is used. Append-only logs count actual setup and owned transition
invocations, including crash recomputation, separately from durable outcomes.
Every hand fixture is capped at 16 calls. POSIX lock/fsync checks establish the
observed process/filesystem behavior, not universal power-loss durability.
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
ERROR_EXIT = 3
BOUNDARIES = (
    "before_temp_write", "before_temp_fsync", "after_temp_fsync", "before_replace",
    "after_replace", "before_directory_fsync", "after_directory_fsync",
)
REPLACED = {"after_replace", "before_directory_fsync", "after_directory_fsync"}


def _wait_for(path, seconds=40):
    deadline = time.monotonic() + seconds
    while not Path(path).exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("test process rendezvous did not arrive: " + str(path))
        time.sleep(0.01)


def _child(options):
    # Keep project imports here, never in the unittest discovery interpreter.
    import grounded_policy_v2
    from grounded_policy_v2 import executive as executive_module
    from grounded_policy_v2 import store as store_module
    from grounded_policy_v2.contracts import canonical
    from grounded_policy_v2.executive import GroundedExecutive
    from open_object_world_challenge import initial_world, observe_world

    assert sys.dont_write_bytecode
    assert not any(n == "inquiry_executive" or n.startswith("inquiry_executive.")
                   for n in sys.modules)
    root = Path(options["root"])
    research = root / "research"
    path = research / "capsule.json"
    fault = options.get("fault")
    original_open = store_module.os.open
    original_replace = store_module.os.replace
    original_fsync = store_module.os.fsync
    original_flock = store_module.fcntl.flock
    original_transition = executive_module.transition

    def capture_staged():
        candidates = list(research.glob(".capsule.json.*.tmp"))
        if candidates:
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
        elif fault == "directory_fsync_error":
            raise OSError("injected directory fsync failure")
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
            Path(options["holding"]).write_text("replacement committed; lock held")
            _wait_for(options["release"])
            os._exit(CRASH_EXIT)
        return result

    def counted_transition(phase, *args, **kwargs):
        if phase == "owned" and options.get("forbid_transition"):
            raise AssertionError("read/replay called the private world transition")
        # A single O_APPEND write is process-safe for these short test records.
        # Persist the invocation before the injected post-transition crash.
        fd = original_open(root / "transition_calls.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            record = json.dumps({"phase": phase, "pid": os.getpid()}) + "\n"
            data = record.encode()
            assert os.write(fd, data) == len(data)
            original_fsync(fd)
        finally:
            os.close(fd)
        result = original_transition(*args, **kwargs)
        if phase == "owned" and fault == "after_transition":
            os._exit(CRASH_EXIT)
        return result

    def transition(*args, **kwargs):
        return counted_transition("owned", *args, **kwargs)

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
        source = root / "sources"
        source.mkdir()
        research.mkdir()
        world = initial_world(1)
        frames = [dict(observation=observe_world(world), receipt=None)]
        for _ in range(2):
            world, receipt = counted_transition("setup", world, {"action": "north"}, cycle=world["cycle"] + 1)
            frames.append(dict(observation=observe_world(world), receipt=receipt))
        values = dict(ora={}, world=world, observations=frames)
        paths = {key: source / (key + ".json") for key in values}
        for key, value in values.items():
            paths[key].write_bytes(canonical(value))
        executive = GroundedExecutive.create(path, research_dir=research,
            source_paths=paths, discovery_count=2, enabled=True)
        phase = options.get("phase", "initial")
        if phase != "initial":
            decision = executive.select_next(0)
            assert decision["status"] == "selected", decision
            assert decision["command"] == {"action": "north"}, decision
        if phase in {"committed", "interpreted"}:
            state = executive.read()
            outcome = executive.execute(state["attempts"][0]["id"], 1)
        if phase == "interpreted":
            executive.interpret(outcome["id"], 2)
        return {"state": executive.read()}

    executive = GroundedExecutive(path, research_dir=research, enabled=True)
    if options.get("ready"):
        Path(options["ready"]).write_text("opened in a fresh source-only interpreter")
        _wait_for(options["go"])
    if action == "read":
        return {"state": executive.read()}
    if action == "select":
        result = executive.select_next(options.get("revision", 0))
    elif action == "execute":
        attempt_id = options.get("attempt_id") or executive.read()["attempts"][-1]["id"]
        result = executive.execute(attempt_id, options.get("revision", 1))
    elif action == "interpret":
        outcome_id = options.get("outcome_id") or executive.read()["outcomes"][-1]["id"]
        result = executive.interpret(outcome_id, options.get("revision", 2))
    else:
        raise AssertionError("unknown child action: " + action)
    if options.get("fail_export"):
        (root / "missing-export-directory" / "result.json").write_text(json.dumps(result))
    return {"result": result, "state": executive.read()}


@unittest.skipUnless(os.name == "posix", "process lock and crash controls require POSIX")
class GroundedPolicyProcessTests(unittest.TestCase):
    totals = dict(fixtures=0, setup_transitions=0, owned_transition_invocations=0,
                  durable_outcomes=0, maximum_fixture_calls=0)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="grounded-v2-process-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture_roots = []
        self.sources = {}
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT / "experiments"))))

    def tearDown(self):
        for path, original in self.sources.items():
            self.assertEqual(path.read_bytes(), original, "protected synthetic source changed")
        for root in self.fixture_roots:
            rows = self.call_rows(root)
            setup = sum(row["phase"] == "setup" for row in rows)
            owned = sum(row["phase"] == "owned" for row in rows)
            self.assertEqual(setup, 2)
            self.assertLessEqual(len(rows), 16, "hand-fixture world-call limit exceeded")
            self.totals["fixtures"] += 1
            self.totals["setup_transitions"] += setup
            self.totals["owned_transition_invocations"] += owned
            self.totals["maximum_fixture_calls"] = max(self.totals["maximum_fixture_calls"], len(rows))
            # A separate log-derived invocation count is never called an outcome.
            # Corrupt-file controls preserve their last verified durable count.
            marker = root / "durable_outcomes.json"
            self.totals["durable_outcomes"] += json.loads(marker.read_text()) if marker.exists() else 0

    @classmethod
    def tearDownClass(cls):
        print("grounded_policy_v2 process accounting: " + json.dumps(cls.totals, sort_keys=True), flush=True)

    def command(self, root, action, **options):
        return [sys.executable, "-B", str(Path(__file__).resolve()), "--capsule-child",
                json.dumps({"root": str(root), "action": action, **options})]

    def call(self, root, action, *, expected=0, **options):
        result = subprocess.run(self.command(root, action, **options), cwd=ROOT,
            env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        if expected == CRASH_EXIT:
            self.assertEqual(result.stdout, "", "interrupted call unexpectedly returned")
            return None
        output = json.loads(result.stdout)
        if "state" in output:
            (root / "durable_outcomes.json").write_text(json.dumps(len(output["state"]["outcomes"])))
        return output

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

    def new_fixture(self, phase="initial"):
        root = self.root / str(len(self.fixture_roots) + 1)
        root.mkdir()
        self.fixture_roots.append(root)
        result = self.call(root, "bootstrap", phase=phase)
        for path in (root / "sources").glob("*.json"):
            self.sources[path] = path.read_bytes()
        self.assertEqual(len(result["state"]["frames"]), 3)
        self.assertEqual(result["state"]["identity"]["discovery_count"], 2)
        return root, result["state"]

    @staticmethod
    def capsule(root):
        return root / "research" / "capsule.json"

    @staticmethod
    def call_rows(root):
        path = root / "transition_calls.log"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def assert_calls(self, root, owned):
        rows = self.call_rows(root)
        self.assertEqual(sum(row["phase"] == "setup" for row in rows), 2)
        self.assertEqual(sum(row["phase"] == "owned" for row in rows), owned)
        self.assertEqual(len(rows), owned + 2)

    def read(self, root):
        return self.call(root, "read", forbid_transition=True)["state"]

    def assert_stage(self, state, phase):
        revision = {"initial": 0, "prepared": 1, "committed": 2, "interpreted": 3}[phase]
        actions = int(revision >= 2)
        self.assertEqual(state["revision"], revision)
        self.assertEqual(len(state["events"]), revision)
        self.assertEqual(len(state["decisions"]), int(revision >= 1))
        self.assertEqual(len(state["attempts"]), int(revision >= 1))
        self.assertEqual(len(state["outcomes"]), actions)
        self.assertEqual(len(state["beliefs"]), int(revision >= 3))
        self.assertEqual(len(state["frames"]), 3)
        self.assertEqual(state["world"]["cycle"], 2 + actions)
        self.assertEqual(len(state["world"]["history"]), 2 + actions)
        self.assertEqual(state["reserve"], {"initial": 0, "prepared": 524288,
            "committed": 65536, "interpreted": 0}[phase])
        self.assertEqual([a["status"] for a in state["attempts"]], [phase] if revision else [])
        if actions:
            outcome = state["outcomes"][0]
            attempt = state["attempts"][0]
            decision = state["decisions"][0]
            self.assertEqual(outcome["attempt_id"], attempt["id"])
            self.assertEqual(outcome["decision_id"], decision["id"])
            self.assertEqual(outcome["owner_id"], decision["owner_id"])
            self.assertEqual(outcome["selection_hash"], decision["hash"])
            self.assertEqual(outcome["receipt"], state["world"]["history"][-1])
            self.assertTrue(outcome["receipt"]["blocked"])
        if revision == 3:
            self.assertEqual(state["beliefs"][0]["outcome_id"], state["outcomes"][0]["id"])
            self.assertEqual(state["beliefs"][0]["owner_id"], state["decisions"][0]["owner_id"])

    def finish(self, root, *, forbid_transition=False):
        state = self.read(root)
        if not state["decisions"]:
            state = self.call(root, "select", revision=0, forbid_transition=True)["state"]
        state = self.call(root, "execute", revision=state["revision"],
                          forbid_transition=forbid_transition)["state"]
        state = self.call(root, "interpret", revision=state["revision"], forbid_transition=True)["state"]
        self.assert_stage(state, "interpreted")
        before = self.capsule(root).read_bytes()
        self.assertEqual(self.call(root, "execute", revision=3, forbid_transition=True)["result"], state["outcomes"][0])
        self.assertEqual(self.call(root, "interpret", revision=3, forbid_transition=True)["result"], state["beliefs"][0])
        self.assertEqual(self.capsule(root).read_bytes(), before)
        return state

    def test_fresh_process_t1_t2_t3_and_reopen_are_explicit(self):
        root, initial = self.new_fixture()
        prepared = self.call(root, "select", forbid_transition=True)["state"]
        self.assert_stage(prepared, "prepared")
        self.assertEqual(prepared["world"], initial["world"])
        before = self.capsule(root).read_bytes()
        self.assertEqual(self.read(root), prepared)
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.assert_calls(root, 0)
        self.finish(root)
        self.assert_calls(root, 1)

    def test_t1_atomic_boundaries_are_wholly_old_or_new(self):
        for fault in BOUNDARIES:
            with self.subTest(boundary=fault):
                root, initial = self.new_fixture()
                before = self.capsule(root).read_bytes()
                self.call(root, "select", fault=fault, expected=CRASH_EXIT, forbid_transition=True)
                self.assertEqual(self.capsule(root).read_bytes(),
                    (root / "staged.json").read_bytes() if fault in REPLACED else before)
                state = self.read(root)
                self.assert_stage(state, "prepared" if fault in REPLACED else "initial")
                self.assertEqual(state["world"], initial["world"])
                self.assertEqual(state["frames"], initial["frames"])
                self.assert_calls(root, 0)
                self.finish(root)
                self.assert_calls(root, 1)

    def test_t2_atomic_boundaries_and_uncommitted_recomputation(self):
        for fault in ("after_transition",) + BOUNDARIES:
            with self.subTest(boundary=fault):
                root, prepared = self.new_fixture("prepared")
                before = self.capsule(root).read_bytes()
                self.call(root, "execute", fault=fault, expected=CRASH_EXIT)
                replaced = fault in REPLACED
                self.assertEqual(self.capsule(root).read_bytes(),
                    (root / "staged.json").read_bytes() if replaced else before)
                state = self.read(root)
                self.assert_stage(state, "committed" if replaced else "prepared")
                if not replaced:
                    self.assertEqual(state, prepared)
                self.assert_calls(root, 1)
                final = self.finish(root, forbid_transition=replaced)
                self.assertEqual(len(final["outcomes"]), 1)
                self.assert_calls(root, 1 if replaced else 2)

    def test_t3_atomic_boundaries_and_lost_response_interpret_once(self):
        for fault in BOUNDARIES:
            with self.subTest(boundary=fault):
                root, committed = self.new_fixture("committed")
                before = self.capsule(root).read_bytes()
                self.call(root, "interpret", fault=fault, expected=CRASH_EXIT, forbid_transition=True)
                self.assertEqual(self.capsule(root).read_bytes(),
                    (root / "staged.json").read_bytes() if fault in REPLACED else before)
                state = self.read(root)
                self.assert_stage(state, "interpreted" if fault in REPLACED else "committed")
                self.assertEqual(state["world"], committed["world"])
                self.assertEqual(state["outcomes"], committed["outcomes"])
                self.finish(root, forbid_transition=True)
                self.assert_calls(root, 1)

    def race(self, root, action, revision):
        go = root / "go"
        processes = [self.start(root, action, revision=revision,
            ready=str(root / ("ready" + str(i))), go=str(go),
            forbid_transition=action != "execute") for i in range(2)]
        for i in range(2):
            _wait_for(root / ("ready" + str(i)))
        go.write_text("race")
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=60)
            self.assertIn(process.returncode, (0, ERROR_EXIT), stdout + stderr)
            results.append((process.returncode, json.loads(stdout)))
        self.assertEqual(sorted(code for code, _ in results), [0, ERROR_EXIT])
        conflict = next(row for code, row in results if code == ERROR_EXIT)
        self.assertEqual(conflict["error_type"], "Conflict")
        self.assertEqual(conflict["error"], "stale revision")
        return next(row for code, row in results if code == 0)

    def test_concurrent_t1_cas_retains_one_selected_capability(self):
        root, initial = self.new_fixture()
        result = self.race(root, "select", 0)
        state = self.read(root)
        self.assert_stage(state, "prepared")
        self.assertEqual(state["decisions"], [result["result"]])
        self.assertEqual(state["world"], initial["world"])
        self.assert_calls(root, 0)
        self.finish(root)
        self.assert_calls(root, 1)

    def test_concurrent_t2_cas_then_current_revision_replays_retained_outcome(self):
        root, _ = self.new_fixture("prepared")
        result = self.race(root, "execute", 1)
        state = self.read(root)
        self.assert_stage(state, "committed")
        before = self.capsule(root).read_bytes()
        self.assertEqual(self.call(root, "execute", revision=state["revision"], forbid_transition=True)["result"], result["result"])
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.assert_calls(root, 1)
        self.finish(root, forbid_transition=True)

    def test_concurrent_t3_cas_then_current_revision_replays_retained_belief(self):
        root, committed = self.new_fixture("committed")
        result = self.race(root, "interpret", 2)
        state = self.read(root)
        self.assert_stage(state, "interpreted")
        before = self.capsule(root).read_bytes()
        self.assertEqual(self.call(root, "interpret", revision=state["revision"], forbid_transition=True)["result"], result["result"])
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.assertEqual(state["world"], committed["world"])
        self.assert_calls(root, 1)

    def test_crashed_holder_releases_stable_lock_and_waiter_gets_stale_cas(self):
        root, _ = self.new_fixture("prepared")
        lock = root / "research" / "capsule.json.lock"
        identity = (lock.stat().st_dev, lock.stat().st_ino)
        holding, release, contending = (root / name for name in ("holding", "release", "contending"))
        owner = self.start(root, "execute", fault="hold_after_replace", holding=str(holding), release=str(release))
        _wait_for(holding)
        waiter = self.start(root, "execute", contending=str(contending), forbid_transition=True)
        _wait_for(contending)
        time.sleep(0.1)
        self.assertIsNone(waiter.poll(), "waiter bypassed the held process lock")
        self.assertIsNone(owner.poll())
        release.write_text("interrupt lock holder")
        self.collect(owner, CRASH_EXIT)
        rejection = self.collect(waiter, ERROR_EXIT)
        self.assertEqual(rejection, {"error_type": "Conflict", "error": "stale revision"})
        self.assertEqual((lock.stat().st_dev, lock.stat().st_ino), identity)
        self.assert_stage(self.read(root), "committed")
        self.finish(root, forbid_transition=True)
        self.assertEqual((lock.stat().st_dev, lock.stat().st_ino), identity)
        self.assert_calls(root, 1)

    def test_directory_fsync_uncertainty_requires_reread_before_retry(self):
        root, _ = self.new_fixture("prepared")
        failure = self.call(root, "execute", fault="directory_fsync_error", expected=ERROR_EXIT)
        self.assertEqual(failure["error_type"], "CommitUncertain")
        self.assertIn("reread", failure["error"])
        self.assert_stage(self.read(root), "committed")
        stale = self.call(root, "execute", revision=1, forbid_transition=True, expected=ERROR_EXIT)
        self.assertEqual(stale["error"], "stale revision")
        self.finish(root, forbid_transition=True)
        self.assert_calls(root, 1)

    def test_export_failure_after_t2_does_not_replay_action(self):
        root, _ = self.new_fixture("prepared")
        failure = self.call(root, "execute", fail_export=True, expected=ERROR_EXIT)
        self.assertEqual(failure["error_type"], "FileNotFoundError")
        self.assert_stage(self.read(root), "committed")
        self.finish(root, forbid_transition=True)
        self.assert_calls(root, 1)

    def test_corrupt_truncated_empty_missing_capsules_refuse_stray_recovery(self):
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
                for action in ("read", "select", "execute", "interpret"):
                    rejected = self.call(root, action, expected=ERROR_EXIT, forbid_transition=True)
                    self.assertIn(rejected["error_type"], ("Conflict", "FileNotFoundError"))
                    self.assertEqual(path.read_bytes() if path.exists() else None, bad)
                    self.assertEqual(stray.read_bytes(), old)
                self.assert_calls(root, 0)

    def test_staged_t1_file_never_overrides_authoritative_state(self):
        root, initial = self.new_fixture()
        before = self.capsule(root).read_bytes()
        self.call(root, "select", fault="before_replace", expected=CRASH_EXIT, forbid_transition=True)
        strays = list((root / "research").glob(".capsule.json.*.tmp"))
        self.assertEqual(len(strays), 1)
        self.assert_stage(json.loads(strays[0].read_bytes()), "prepared")
        self.assertEqual(self.read(root), initial)
        self.assertEqual(self.capsule(root).read_bytes(), before)
        self.capsule(root).unlink()
        rejected = self.call(root, "read", expected=ERROR_EXIT, forbid_transition=True)
        self.assertEqual(rejected["error_type"], "FileNotFoundError")
        self.assertFalse(self.capsule(root).exists())
        self.assertTrue(strays[0].exists())
        self.assert_calls(root, 0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--capsule-child":
        try:
            output = _child(json.loads(sys.argv[2]))
        except Exception as error:
            print(json.dumps({"error_type": type(error).__name__, "error": str(error)}))
            raise SystemExit(ERROR_EXIT)
        print(json.dumps(output, sort_keys=True))
    else:
        unittest.main()
