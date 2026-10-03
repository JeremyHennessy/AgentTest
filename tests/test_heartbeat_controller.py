from pathlib import Path
import os
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HeartbeatControllerWorkflowTests(unittest.TestCase):
    def _dispatch_script(self) -> str:
        workflow = (ROOT / ".github/workflows/heartbeat-controller.yml").read_text(
            encoding="utf-8"
        )
        step = "      - name: Dispatch and verify autonomous growth\n"
        start = workflow.index(step)
        run_marker = "        run: |\n"
        script_start = workflow.index(run_marker, start) + len(run_marker)
        script_end = workflow.index(
            "\n      - name: Queue successor controller", script_start
        )
        return textwrap.dedent(workflow[script_start:script_end])

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

    def test_growth_dispatch_does_not_attach_to_newer_unrelated_run(self) -> None:
        """Execute the real workflow step against a stale/out-of-order run listing.

        Run 100 exists before this controller dispatches. Its own dispatch creates
        run 200, but another growth dispatch becomes the newest visible run (300)
        before the controller polls. A correct correlation mechanism must watch
        run 200, never merely the newest ID different from the pre-dispatch ID.
        """
        script = self._dispatch_script()
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_gh = temp_path / "gh"
            watched = temp_path / "watched"
            state = temp_path / "state"
            state.write_text("before", encoding="utf-8")
            fake_gh.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
if [ "$1 $2" = "run list" ]; then
  phase="$(cat "$GH_FAKE_STATE")"
  if [ "$phase" = "before" ]; then
    printf '100\\n'
  elif printf '%s\\n' "$*" | grep -q 'displayTitle'; then
    # A correlation-aware query can find the controller's own run even when
    # a newer unrelated growth run is visible.
    printf '200\\n'
  else
    # GitHub's newest visible run belongs to a different dispatcher.
    printf '300\\n'
  fi
elif [ "$1 $2" = "workflow run" ]; then
  printf 'after' > "$GH_FAKE_STATE"
elif [ "$1 $2" = "run watch" ]; then
  printf '%s\\n' "$3" > "$GH_FAKE_WATCHED"
else
  echo "unexpected gh invocation: $*" >&2
  exit 2
fi
""",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{temp}{os.pathsep}{env['PATH']}",
                    "GITHUB_REPOSITORY": "JeremyHennessy/AgentTest",
                    "GH_FAKE_STATE": str(state),
                    "GH_FAKE_WATCHED": str(watched),
                }
            )
            subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", script],
                cwd=ROOT,
                env=env,
                check=True,
                timeout=10,
            )

            self.assertEqual(
                watched.read_text(encoding="utf-8").strip(),
                "200",
                "controller watched a newer unrelated growth run instead of its own dispatch",
            )


if __name__ == "__main__":
    unittest.main()
