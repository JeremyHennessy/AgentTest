from __future__ import annotations

import argparse
import json
from pathlib import Path

from agenttest.agenda import agenda_contract_errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the persisted Phase 42 agenda contract."
    )
    parser.add_argument("--state", required=True)
    parser.add_argument("--output")
    parser.add_argument(
        "--require-repository-prediction-path",
        action="store_true",
        help=(
            "Require the observed-cycle repository prediction question to retain "
            "an active evidence-ready experiment path visible to the agenda."
        ),
    )
    args = parser.parse_args()

    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    errors = agenda_contract_errors(
        state,
        require_repository_prediction_path=(
            args.require_repository_prediction_path
        ),
    )
    result = {
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "agenda_version": state.get("agenda", {}).get("version"),
        "cycle": state.get("cycles"),
    }

    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
