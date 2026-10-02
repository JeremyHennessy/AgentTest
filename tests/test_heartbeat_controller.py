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
        self.assertNotIn("cancel-in-progress: true", workflow)

    def test_growth_dispatch_is_correlated_to_the_exact_controller_run(self) -> None:
        controller = (ROOT / ".github/workflows/heartbeat-controller.yml").read_text(
            encoding="utf-8"
        )
        growth = (ROOT / ".github/workflows/growth.yml").read_text(encoding="utf-8")

        self.assertIn("controller_dispatch_token:", growth)
        self.assertIn(
            "run-name: autonomous-growth-cycle [${{ inputs.controller_dispatch_token || 'manual' }}]",
            growth,
        )
        self.assertIn(
            'correlation_token="controller-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"',
            controller,
        )
        self.assertIn('-f controller_dispatch_token="$correlation_token"', controller)
        self.assertIn("--json databaseId,displayTitle", controller)
        self.assertIn("displayTitle", controller)
        self.assertNotIn('before="$(', controller)
        self.assertNotIn('[ "$candidate" != "$before" ]', controller)


if __name__ == "__main__":
    unittest.main()
