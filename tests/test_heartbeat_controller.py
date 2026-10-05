from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HeartbeatControllerWorkflowTests(unittest.TestCase):
    def test_successor_dispatch_retries_transient_failures_without_changing_generation(self) -> None:
        workflow = (ROOT / ".github/workflows/heartbeat-controller.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("for attempt in $(seq 1 5); do", workflow)
        self.assertIn("Successor dispatch attempt $attempt failed", workflow)
        self.assertIn("backoff=$((attempt * 3))", workflow)
        self.assertIn("Failed to queue successor controller after 5 attempts.", workflow)
        self.assertIn("-f controller_token=controller-v3", workflow)
        self.assertIn("-f delay_seconds=0", workflow)
        self.assertIn("for attempt in $(seq 1 10); do", workflow)
        self.assertIn("gh run view \"$run_id\"", workflow)
        self.assertIn('grep -q "HTTP 404"', workflow)
        self.assertIn("retrying in 2 seconds", workflow)
        self.assertIn(
            "Growth run $run_id did not become queryable after 10 attempts.",
            workflow,
        )
        self.assertNotIn("cancel-in-progress: true", workflow)


if __name__ == "__main__":
    unittest.main()
