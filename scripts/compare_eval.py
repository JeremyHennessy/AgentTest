from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    baseline_checks = baseline.get("checks", {})
    candidate_checks = candidate.get("checks", {})
    regressions = []
    improvements = []

    for name, base in baseline_checks.items():
        candidate_check = candidate_checks.get(name)
        if base.get("passed"):
            if candidate_check is None or not candidate_check.get("passed"):
                regressions.append(
                    {
                        "check": name,
                        "baseline": base,
                        "candidate": candidate_check,
                    }
                )
        elif candidate_check is not None and candidate_check.get("passed"):
            improvements.append(name)

    return {
        "baseline_suite": baseline.get("suite"),
        "candidate_suite": candidate.get("suite"),
        "regressions": regressions,
        "improvements": improvements,
        "preserved": not regressions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = compare(load(args.baseline), load(args.candidate))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if not result["preserved"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
