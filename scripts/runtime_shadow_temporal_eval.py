from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FIELDS = (
    "checkout_duration_s",
    "cycle_duration_s",
    "preserve_duration_s",
    "total_duration_s",
)


def transition(left: float, right: float) -> str:
    return "same_next_observation" if left == right else "changes_next_observation"


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    observations = sorted(
        report.get("observations", []),
        key=lambda item: int(item.get("run_number", 0)),
    )
    split = len(observations) // 2
    if split < 2 or len(observations) - split < 2:
        raise ValueError("runtime shadow temporal study needs at least four observations")

    results: dict[str, Any] = {}
    for field in FIELDS:
        values = [
            float(item[field])
            for item in observations
            if isinstance(item.get(field), (int, float))
        ]
        if len(values) != len(observations):
            results[field] = {"status": "incomplete"}
            continue

        prefix = values[:split]
        suffix = values[split - 1 :]
        prefix_transitions = [
            transition(left, right)
            for left, right in zip(prefix, prefix[1:])
        ]
        same_count = prefix_transitions.count("same_next_observation")
        change_count = prefix_transitions.count("changes_next_observation")
        selected = (
            "same_next_observation"
            if same_count > change_count
            else "changes_next_observation"
        )

        held_transitions = [
            transition(left, right)
            for left, right in zip(suffix, suffix[1:])
        ]
        supported = sum(item == selected for item in held_transitions)
        results[field] = {
            "status": "evaluated",
            "prefix_count": len(prefix),
            "held_out_transition_count": len(held_transitions),
            "prefix_same_count": same_count,
            "prefix_change_count": change_count,
            "selected_relation": selected,
            "held_out_support_count": supported,
            "held_out_support_rate": round(
                supported / len(held_transitions),
                6,
            ),
            "held_out_same_count": held_transitions.count(
                "same_next_observation"
            ),
            "held_out_change_count": held_transitions.count(
                "changes_next_observation"
            ),
            "prefix_mean": round(sum(prefix) / len(prefix), 6),
            "held_out_mean": round(
                sum(values[split:]) / len(values[split:]),
                6,
            ),
        }

    return {
        "study": "runtime-shadow-temporal-prospective-v1",
        "fed_to_ora": False,
        "split_protocol": "first_half_select_second_half_evaluate",
        "observation_count": len(observations),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.input).read_text())
    result = evaluate(report)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    Path(args.output).write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
