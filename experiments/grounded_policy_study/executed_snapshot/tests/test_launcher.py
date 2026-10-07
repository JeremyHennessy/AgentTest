"""Only authored native launcher stubs. No API/policy/world imports or calls."""
import json
from pathlib import Path
import tempfile
import unittest

from ora_study.launcher import build_launcher, read_reserved_status, run_launcher, MIB, MODES

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


if __name__ == "__main__":
    unittest.main()
