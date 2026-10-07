"""Only authored native launcher stubs. No API/policy/world imports or calls."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from ora_study.launcher import (build_launcher, build_pending_scientific_launcher,
    read_reserved_status, run_launcher, MIB, MODES, SOURCE, SCIENTIFIC_PROTOCOL_SHA256)

RESULTS = Path(__file__).resolve().parents[2] / "policy-study-results"


class NativeLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=RESULTS, prefix="launcher-tests-")
        cls.root = Path(cls.tmp.name)
        cls.binary = build_launcher(cls.root / "build")
        cls.sequence = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_mode(self, mode="success", wall_ms=3000):
        type(self).sequence += 1
        root = self.root / (str(self.sequence)+"-"+mode)
        row = run_launcher(self.binary, root, mode=mode, wall_ms=wall_ms)
        self.assertEqual(row["science_transition_invocations"], 0)
        self.assertFalse(row["scientific_execution_allowed"])
        self.assertFalse(row["cpu_allowance_proved"])
        self.assertFalse(row["full_lifetime_hard_wall_proved"])
        self.assertFalse(row["scientific_output_inventory_proved"])
        self.assertEqual(row["restarts"], 0)
        self.assertFalse(row["observer"]["emergency_timeout"])
        self.assertLessEqual(sum(p.stat().st_size for p in root.iterdir()), row["stub_inventory_bound_bytes"])
        self.assertEqual((root / "launcher.status").stat().st_size, MIB)
        self.assertLessEqual(row["stdout_bytes"], 16384)
        self.assertLessEqual(row["stderr_bytes"], 16384)
        self.assertLessEqual(row["birth_ns"], row["entry_ns"])
        self.assertLess(row["entry_ns"], row["last_snapshot_ns"])
        self.assertLessEqual(row["last_snapshot_ns"], row["observer"]["reaped_boottime_ns"])
        return root, row

    def test_inherited_limits_and_lifetime_composition(self):
        _, row = self.run_mode()
        self.assertEqual(row["classification"], "fixture_complete")
        self.assertEqual(row["outer_as"], [32*MIB, 384*MIB])
        self.assertEqual(row["controller_as"], [96*MIB, 384*MIB])
        self.assertEqual(row["worker_as"], [384*MIB, 384*MIB])
        self.assertEqual(row["reporter_as"], [384*MIB, 384*MIB])
        self.assertEqual(row["window_start_ns"], row["birth_ns"])
        self.assertTrue(row["no_live_launcher_helper"])
        self.assertEqual(row["outer_pid"], row["observer"]["outer_pid"])
        self.assertTrue(row["aggregate_cpu_kernel_enforcement"])
        self.assertLessEqual(row["aggregate_cpu_observed_ns"], row["last_snapshot_ns"]-row["window_start_ns"])
        self.assertEqual(row["entry_route"], "direct-native")
        self.assertTrue(row["kernel_expiry_armed"])
        self.assertEqual(row["internal_wall_ceiling_ms"], 850000)
        for key in ("controller_affinity_cpu", "worker_affinity_cpu", "reporter_affinity_cpu"):
            self.assertEqual(row[key], row["selected_cpu"])
        self.assertEqual(row["controller_cpu"], [10, 10])
        self.assertEqual(row["worker_cpu"], [1, 1])
        self.assertEqual(row["reporter_cpu"], [10, 10])
        self.assertEqual(row["worker_nproc"], 1)
        self.assertEqual(sum((row[key][0] for key in ("outer_as", "controller_as", "worker_as"))), 512*MIB)
        self.assertEqual(row["stub_workers_observed_started"], 1)
        self.assertEqual(row["stub_reporters_observed_started"], 1)
        self.assertTrue(row["observer"]["exit_observed_after_finalization"])
        self.assertTrue(row["observer"]["exit_observed_within_deadline"])
        self.assertFalse(row["ambient_environment_forwarded"])

    def test_reserved_terminal_for_source_and_startup_failures(self):
        for mode in ("source_failure", "startup_failure"):
            with self.subTest(mode=mode):
                _, row = self.run_mode(mode)
                self.assertEqual(row["classification"], "invalid" if mode == "source_failure" else "incomplete")
                self.assertEqual(row["stub_workers_observed_started"], 0)
                self.assertEqual(row["controller_pid"], -1)

    def test_resource_failures_stop_without_restart(self):
        for mode in ("hang", "stdout_flood", "stderr_flood", "report_hang"):
            with self.subTest(mode=mode):
                _, row = self.run_mode(mode, wall_ms=700)
                self.assertEqual(row["classification"], "incomplete")
                self.assertTrue(row["whole_group_termination_attempted"])
                self.assertTrue(row["controller_reaped"])
                self.assertTrue(row["observer"]["exit_observed_within_deadline"])

    def test_child_controller_report_and_seal_failures(self):
        for mode in ("child_failure", "controller_failure", "controller_orphan", "report_failure", "seal_failure"):
            with self.subTest(mode=mode):
                _, row = self.run_mode(mode)
                self.assertEqual(row["classification"], "incomplete")
                self.assertTrue(row["whole_group_termination_attempted"])
                self.assertTrue(row["controller_reaped"])
                self.assertNotEqual(row["reason"], "cleanup_unverified")

    def test_early_parent_death_rejects_reparented_creator(self):
        _, row = self.run_mode("controller_early_death")
        self.assertEqual(row["classification"], "incomplete")
        self.assertTrue(row["early_parent_death_guard"])
        self.assertFalse(row["stub_counts_known"])
        self.assertTrue(row["controller_reaped"])
        self.assertEqual(row["stub_workers_observed_started"], 0)
        self.assertNotEqual(row["reason"], "cleanup_unverified")

    def test_hard_cpu_kills_authored_busy_stub(self):
        _, row = self.run_mode("cpu", wall_ms=4500)
        self.assertEqual(row["classification"], "incomplete")
        self.assertEqual(row["worker_code"], 137)
        self.assertGreater(row["child_cpu_observed_ns"], 500_000_000)
        self.assertLess(row["child_cpu_observed_ns"], 2_000_000_000)
        self.assertFalse(row["cpu_allowance_proved"])

    def test_address_space_and_descendant_refusal(self):
        for mode in ("allocation", "nproc"):
            with self.subTest(mode=mode):
                _, row = self.run_mode(mode)
                self.assertEqual(row["classification"], "fixture_complete")

    def test_existing_directory_and_arbitrary_payload_refused(self):
        root, row = self.run_mode()
        before = {p.name: p.read_bytes() for p in root.iterdir()}
        with self.assertRaises(FileExistsError):
            run_launcher(self.binary, root)
        self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
        with self.assertRaises(ValueError):
            run_launcher(self.binary, self.root / "no-science", mode="scientific")
        self.assertFalse((self.root / "no-science").exists())
        with self.assertRaises(ValueError):
            run_launcher(Path("/bin/true"), self.root / "arbitrary-program")
        self.assertFalse((self.root / "arbitrary-program").exists())

    def test_fixed_python_controller_and_source_mismatch(self):
        root, row = self.run_mode("python_controller")
        self.assertEqual(row["classification"], "fixture_complete")
        self.assertTrue(row["python_controller_bootstrap_verified"])
        self.assertEqual(row["authored_null_decisions"], 128)
        self.assertEqual(row["controller_as"], [96*MIB, 384*MIB])
        self.assertEqual(row["worker_as"], [384*MIB, 384*MIB])
        self.assertEqual(row["stub_workers_observed_started"], 1)
        self.assertEqual(row["stub_reporters_observed_started"], 0)
        summary = json.loads((root / "launcher.stdout").read_text())
        self.assertEqual(summary["actual_api_calls"], 0)
        self.assertEqual(summary["actual_world_calls"], 0)
        self.assertEqual(summary["null_decisions"], 128)
        negative_binary = build_launcher(self.root / "source-negative-build", fixture_source_mismatch=True)
        negative = run_launcher(negative_binary, self.root / "source-negative-run", mode="python_controller")
        self.assertEqual(negative["classification"], "invalid")
        self.assertEqual(negative["reason"], "python_source_validation_failed")
        self.assertFalse(negative["python_controller_bootstrap_verified"])
        self.assertEqual(negative["stub_workers_observed_started"], 0)
        self.assertEqual(negative["science_transition_invocations"], 0)

    def test_kernel_expiry_covers_blocked_finalization(self):
        for mode in ("finalize_hang", "finalize_blocked_write", "supervisor_hang"):
            with self.subTest(mode=mode):
                type(self).sequence += 1
                root = self.root / (str(self.sequence)+"-"+mode)
                row = run_launcher(self.binary, root, mode=mode, wall_ms=500)
                self.assertEqual(row["classification"], "incomplete")
                self.assertEqual(row["reason"], "kernel_expiry_observed")
                self.assertTrue(row["observer"]["kernel_expiry_observed"])
                self.assertEqual(row["observer"]["returncode"], 124)
                self.assertFalse(row["observer"]["emergency_timeout"])
                self.assertFalse(row["stub_counts_known"])
                self.assertEqual(row["science_transition_invocations"], 0)
                self.assertLess(row["observer"]["reaped_boottime_ns"] - row["observer"]["before_popen_boottime_ns"], 1_500_000_000)

    def test_torn_terminal_falls_back_to_reserved_initial(self):
        root, _ = self.run_mode()
        with (root / "launcher.status").open("r+b") as stream:
            stream.seek(65536)
            stream.write(b"{" + b"\0" * 8191)
        row = read_reserved_status(root)
        self.assertEqual(row["classification"], "incomplete")
        self.assertFalse(row["stub_counts_known"])
        self.assertEqual(row["science_transition_invocations"], 0)

    def test_scientific_binding_builds_but_never_executes(self):
        output = self.root / "never-executed-scientific-output"
        marker = SOURCE.parent.resolve().parents[1] / "policy-study-results" / "ONE_SCIENTIFIC_COMPARISON_STARTED.json"
        marker_before = marker.read_bytes() if marker.exists() else None
        python_hash = hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        profile = {"schema": "ora.scientific.launch.v1", "profile": "prospective_study_v4",
            "run_id": "ora-two-decision-v4-first-comparison", "output_root": str(output),
            "api_root": str(self.root), "api_manifest": {"authored_never_loaded.py": "0"*64},
            "python_sha256": python_hash, "api_runtime_manifest": {"executable_hash": python_hash},
            "admission_receipt_path": str(self.root / "uncreated-go-receipt.json"),
            "started_marker_path": str(marker), "protocol_sha256": SCIENTIFIC_PROTOCOL_SHA256}
        path = self.root / "launcher-authored-build-profile.json"
        path.write_text(json.dumps(profile))
        binary = build_pending_scientific_launcher(self.root / "scientific-build-only", path)
        self.assertTrue(binary.is_file())
        receipt = json.loads((binary.parent / "launcher-build.json").read_text())
        self.assertEqual(receipt["controller_role"], "pending_scientific")
        self.assertFalse(receipt["scientific_admission_reviewed"])
        self.assertEqual(receipt["scientific_limits"]["children"], 422)
        self.assertEqual(receipt["scientific_limits"]["transitions"], 512)
        self.assertFalse(output.exists())
        self.assertFalse(Path(profile["admission_receipt_path"]).exists())
        self.assertEqual(marker.read_bytes() if marker.exists() else None, marker_before)
        self.assertNotIn("scientific_controller", MODES)
        with self.assertRaises(ValueError):
            run_launcher(binary, output, mode="scientific_controller")
        profile["protocol_sha256"] = "0"*64
        path.write_text(json.dumps(profile))
        with self.assertRaises(ValueError):
            build_pending_scientific_launcher(self.root / "bad-protocol-build", path)
        self.assertFalse((self.root / "bad-protocol-build").exists())

    def test_scientific_receipt_rules_with_authored_scalar_harness(self):
        # Include source but replace its entry point. This executable calls
        # only pure receipt helpers; neither launch CLI/controller is invoked.
        source = self.root / "launcher-receipt-check.c"
        source.write_text("#define main unused_launcher_entry\n#include " + json.dumps(str(SOURCE.resolve())) + "\n#undef main\n" + r'''
int main(void) {
    const char *classification="invalid",*reason="known_integrity_failure";
    late_incomplete(&classification,&reason,"late_log_failure");
    if(strcmp(classification,"invalid") || strcmp(reason,"known_integrity_failure"))return 1;
    if(strcmp(scientific_state(1,0,2,100,0,0),"invalid"))return 2;
    if(strcmp(scientific_state(0,0,1,30,1,0),"invalid"))return 3;
    if(strcmp(scientific_state(1,0,1,30,1,0),"incomplete"))return 4;
    if(strcmp(scientific_state(1,0,0,128,6,1),"complete"))return 5;
    if(strcmp(scientific_state(1,0,0,128,6,0),"incomplete"))return 6;
    if(strcmp(scientific_state(1,0,0,128,1,1),"incomplete"))return 11;
    if(!scientific_complete_counts(384,128,128,64,165) ||
       !scientific_complete_counts(512,384,128,64,421) ||
       scientific_complete_counts(400,128,128,64,165) ||
       scientific_complete_counts(512,384,128,64,422))return 12;
    struct event event;
    const char *line="{\"phase\":10,\"pid\":1,\"value\":513,\"code\":384,\"as_soft\":1,\"as_hard\":1,\"cpu_soft\":1,\"cpu_hard\":1,\"nproc_soft\":1,\"affinity_cpu\":0,\"user_ns\":0,\"system_ns\":0}\n";
    if(parse_json_event(line,&event) || event.value!=513)return 7;
    if(!scientific_count_overrun(event.value,event.code,128,64,128))return 8;
    if(strcmp(scientific_state(1,1,0,128,6,1),"invalid") || event.value!=513)return 9;
    scientific_mode=1;
    if(child_cap()!=422 || event_cap()!=1280 || scientific_admission_reviewed || *reviewed_scientific_profile_sha256)return 10;
    return 0;
}
''')
        binary = self.root / "launcher-receipt-check"
        compiled = subprocess.run([shutil.which("cc"), "-static", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                                   "-o", str(binary), str(source)], capture_output=True, timeout=30)
        self.assertEqual(compiled.returncode, 0, compiled.stderr.decode())
        checked = subprocess.run([str(binary)], capture_output=True, timeout=3)
        self.assertEqual(checked.returncode, 0, checked.stderr.decode())


if __name__ == "__main__":
    unittest.main()
