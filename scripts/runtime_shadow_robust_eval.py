from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Any

FIELDS = (
    "checkout_duration_s",
    "cycle_duration_s",
    "preserve_duration_s",
    "total_duration_s",
)
BASELINE_WINDOW = 7
RELATIVE_BAND = 0.20
MIN_ABSOLUTE_BAND_S = 1.0
WINDOW_SIZE = 12


def classify(value: float, history: list[float]) -> str | None:
    if len(history) < BASELINE_WINDOW:
        return None
    baseline = median(history[-BASELINE_WINDOW:])
    tolerance = max(MIN_ABSOLUTE_BAND_S, abs(baseline) * RELATIVE_BAND)
    if value < baseline - tolerance:
        return "faster"
    if value > baseline + tolerance:
        return "slower"
    return "normal"


def labels(observations: list[dict[str, Any]], field: str) -> list[str | None]:
    values: list[float] = []
    result: list[str | None] = []
    for item in observations:
        value = item.get(field)
        if not isinstance(value, (int, float)):
            result.append(None)
            continue
        numeric = float(value)
        result.append(classify(numeric, values))
        values.append(numeric)
    return result


def relation(left: str, right: str) -> str:
    return "same_next_observation" if left == right else "changes_next_observation"


def evaluate_window(window: list[dict[str, Any]], field: str) -> dict[str, Any]:
    field_labels = labels(window, field)
    usable = [item for item in field_labels if item is not None]
    if len(usable) < 4:
        return {"status": "insufficient"}

    split = len(usable) // 2
    prefix = usable[:split]
    held = usable[split - 1 :]
    prefix_relations = [
        relation(left, right) for left, right in zip(prefix, prefix[1:])
    ]
    held_relations = [
        relation(left, right) for left, right in zip(held, held[1:])
    ]
    same = prefix_relations.count("same_next_observation")
    changed = prefix_relations.count("changes_next_observation")
    selected = (
        "same_next_observation"
        if same > changed
        else "changes_next_observation"
    )
    support = sum(item == selected for item in held_relations)
    return {
        "status": "evaluated",
        "selected_relation": selected,
        "held_out_support_count": support,
        "held_out_count": len(held_relations),
        "held_out_support_rate": round(support / len(held_relations), 6),
        "prefix_labels": prefix,
        "held_out_labels": held[1:],
    }


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    observations = sorted(
        report.get("observations", []),
        key=lambda item: int(item.get("run_number", 0)),
    )
    windows = []
    start = 0
    while start + WINDOW_SIZE <= len(observations):
        windows.append(observations[start : start + WINDOW_SIZE])
        start += WINDOW_SIZE

    fields: dict[str, Any] = {}
    for field in FIELDS:
        results = [evaluate_window(window, field) for window in windows]
        evaluated = [item for item in results if item["status"] == "evaluated"]
        rates = [item["held_out_support_rate"] for item in evaluated]
        selected = [item["selected_relation"] for item in evaluated]
        fields[field] = {
            "windows": results,
            "evaluated_window_count": len(evaluated),
            "minimum_support_rate": min(rates) if rates else None,
            "mean_support_rate": (
                round(sum(rates) / len(rates), 6) if rates else None
            ),
            "relation_consistent_across_windows": (
                len(set(selected)) == 1 if selected else None
            ),
            "selected_relations": selected,
        }

    return {
        "study": "runtime-shadow-robust-prospective-v1",
        "fed_to_ora": False,
        "representation": {
            "baseline": f"median_previous_{BASELINE_WINDOW}",
            "relative_band": RELATIVE_BAND,
            "minimum_absolute_band_s": MIN_ABSOLUTE_BAND_S,
            "labels": ["faster", "normal", "slower"],
            "window_size": WINDOW_SIZE,
            "non_overlapping_windows": True,
        },
        "observation_count": len(observations),
        "complete_window_count": len(windows),
        "fields": fields,
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
