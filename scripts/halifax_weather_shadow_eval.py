from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

NUMERIC_FIELDS = (
    "temperature_c",
    "relative_humidity_pct",
    "station_pressure_kpa",
    "visibility_km",
    "wind_speed_kmh",
)
WINDOW = 24
THRESHOLDS = {
    "temperature_c": 1.0,
    "relative_humidity_pct": 5.0,
    "station_pressure_kpa": 0.3,
    "visibility_km": 2.0,
    "wind_speed_kmh": 5.0,
}


def relation(left: float, right: float, threshold: float) -> str:
    return (
        "same_next_observation"
        if abs(right - left) <= threshold
        else "changes_next_observation"
    )


def evaluate_window(values: list[float], threshold: float) -> dict[str, Any]:
    split = len(values) // 2
    prefix = values[:split]
    held = values[split - 1 :]
    prefix_relations = [
        relation(a, b, threshold) for a, b in zip(prefix, prefix[1:])
    ]
    held_relations = [
        relation(a, b, threshold) for a, b in zip(held, held[1:])
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
        "selected_relation": selected,
        "held_out_support_count": support,
        "held_out_count": len(held_relations),
        "held_out_support_rate": round(support / len(held_relations), 6),
    }


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    observations = report["observations"]
    fields: dict[str, Any] = {}
    for field in NUMERIC_FIELDS:
        values = [
            float(item[field])
            for item in observations
            if isinstance(item.get(field), (int, float))
        ]
        windows = [
            values[index : index + WINDOW]
            for index in range(0, len(values) - WINDOW + 1, WINDOW)
        ]
        results = [
            evaluate_window(window, THRESHOLDS[field])
            for window in windows
        ]
        rates = [item["held_out_support_rate"] for item in results]
        selected = [item["selected_relation"] for item in results]
        fields[field] = {
            "threshold": THRESHOLDS[field],
            "complete_window_count": len(results),
            "mean_support_rate": round(sum(rates) / len(rates), 6) if rates else None,
            "minimum_support_rate": min(rates) if rates else None,
            "relation_consistent_across_windows": len(set(selected)) == 1 if selected else None,
            "selected_relations": selected,
            "windows": results,
        }
    return {
        "study": "halifax-weather-shadow-prospective-v1",
        "fed_to_ora": False,
        "window_size": WINDOW,
        "non_overlapping_windows": True,
        "thresholds_predeclared": True,
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
