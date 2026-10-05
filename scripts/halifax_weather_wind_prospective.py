from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "halifax-wind-prospective-v1"

# Frozen before any post-selection outcome review.
CLIMATE_IDENTIFIER = "8202251"
STATION_NAME = "HALIFAX STANFIELD INT'L A"
FEATURE = "wind_speed_kmh"
THRESHOLD_KMH = 5.0
FROZEN_RELATION = "same_next_observation"

# Historical source-selection evidence. Run #8 completed before the freeze.
BASELINE_RUN_ID = 37246649788
BASELINE_ARTIFACT_ID = 11319297170
BASELINE_ARTIFACT_SHA256 = "395898d938d947a0ab894dee42c3e310d9632742a16b6b56fd4c95aa3385e2bf"
BASELINE_HEAD_SHA = "a52c70dad9cffd8b7fea707e7496858c84063012"
BASELINE_LATEST_OBSERVATION_UTC = "2026-10-04T03:00:00Z"

# The selected source/feature/threshold were frozen by the first isolated wind
# compatibility commit immediately after the historical study.
SELECTION_FREEZE_COMMIT = "0413dd2843d4177eb7e9c162c253452c6d9ec11e"
SELECTION_FREEZE_UTC = "2026-10-05T00:14:42Z"

# Exact prospective clock windows are predeclared. They start at the first
# station hour absent from the frozen historical artifact. No later hour may be
# substituted for a missing target observation.
WINDOW_HOURS = 24
WINDOW_COUNT = 4
TARGET_START_UTC = "2026-10-04T04:00:00Z"
TARGET_OBSERVATION_COUNT = WINDOW_HOURS * WINDOW_COUNT


def parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def target_times() -> list[datetime]:
    start = parse_utc(TARGET_START_UTC)
    return [start + timedelta(hours=index) for index in range(TARGET_OBSERVATION_COUNT)]


def _frozen_metadata() -> dict[str, Any]:
    targets = target_times()
    return {
        "source": "environment_canada_climate_hourly_observations",
        "climate_identifier": CLIMATE_IDENTIFIER,
        "station_name": STATION_NAME,
        "feature": FEATURE,
        "threshold_kmh": THRESHOLD_KMH,
        "frozen_relation": FROZEN_RELATION,
        "window_hours": WINDOW_HOURS,
        "window_count": WINDOW_COUNT,
        "target_observation_count": TARGET_OBSERVATION_COUNT,
        "target_start_utc": iso_z(targets[0]),
        "target_end_utc": iso_z(targets[-1]),
        "baseline_run_id": BASELINE_RUN_ID,
        "baseline_artifact_id": BASELINE_ARTIFACT_ID,
        "baseline_artifact_sha256": BASELINE_ARTIFACT_SHA256,
        "baseline_head_sha": BASELINE_HEAD_SHA,
        "baseline_latest_observation_utc": BASELINE_LATEST_OBSERVATION_UTC,
        "selection_freeze_commit": SELECTION_FREEZE_COMMIT,
        "selection_freeze_utc": SELECTION_FREEZE_UTC,
        "feature_selected_after_historical_review": True,
        "results_blinded_until_all_target_observations_present": True,
    }


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("source") != "environment_canada_climate_hourly_observations":
        raise ValueError("unexpected observation source")
    if report.get("fed_to_ora") is not False:
        raise ValueError("prospective source must remain shadow-only")
    if report.get("station_names") != [STATION_NAME]:
        raise ValueError("station provenance does not match frozen protocol")

    targets = target_times()
    target_set = set(targets)
    by_time: dict[datetime, dict[str, Any]] = {}
    newest_source: datetime | None = None

    for item in report.get("observations", []):
        if str(item.get("climate_identifier") or "") != CLIMATE_IDENTIFIER:
            raise ValueError("climate identifier does not match frozen protocol")
        if str(item.get("station_name") or "") != STATION_NAME:
            raise ValueError("station name does not match frozen protocol")
        observed_at = parse_utc(str(item.get("utc_date") or ""))
        if newest_source is None or observed_at > newest_source:
            newest_source = observed_at
        if observed_at not in target_set:
            continue
        if observed_at in by_time:
            raise ValueError(f"duplicate target observation at {iso_z(observed_at)}")
        by_time[observed_at] = item

    missing = [moment for moment in targets if moment not in by_time]
    invalid = [
        moment
        for moment in targets
        if moment in by_time and not isinstance(by_time[moment].get(FEATURE), (int, float))
    ]

    base = {
        "study": SCHEMA_VERSION,
        "fed_to_ora": False,
        "authority": "read_only_shadow",
        "protocol": _frozen_metadata(),
        "available_target_observation_count": len(by_time),
        "missing_target_observation_count": len(missing),
        "invalid_target_observation_count": len(invalid),
        "newest_source_observation_utc": iso_z(newest_source) if newest_source else None,
        "results_released": False,
    }

    if invalid:
        base.update(
            {
                "status": "invalid_missing_wind_measurement",
                "invalid_target_times_utc": [iso_z(item) for item in invalid],
            }
        )
        return base

    if missing:
        target_end = targets[-1]
        source_has_passed_window = newest_source is not None and newest_source > target_end
        base.update(
            {
                "status": "incomplete_source_gap" if source_has_passed_window else "collecting",
                "missing_target_times_utc": [iso_z(item) for item in missing],
            }
        )
        return base

    values = [float(by_time[moment][FEATURE]) for moment in targets]
    window_results: list[dict[str, Any]] = []
    total_support = 0
    total_transitions = 0

    for window_index in range(WINDOW_COUNT):
        start_index = window_index * WINDOW_HOURS
        window_times = targets[start_index : start_index + WINDOW_HOURS]
        window_values = values[start_index : start_index + WINDOW_HOURS]
        support = sum(
            abs(right - left) <= THRESHOLD_KMH
            for left, right in zip(window_values, window_values[1:])
        )
        transitions = WINDOW_HOURS - 1
        contradictions = transitions - support
        total_support += support
        total_transitions += transitions
        window_results.append(
            {
                "window_index": window_index + 1,
                "start_utc": iso_z(window_times[0]),
                "end_utc": iso_z(window_times[-1]),
                "transition_count": transitions,
                "support_count": support,
                "contradiction_count": contradictions,
                "support_rate": round(support / transitions, 6),
            }
        )

    return {
        **base,
        "status": "complete",
        "results_released": True,
        "window_results": window_results,
        "aggregate_transition_count": total_transitions,
        "aggregate_support_count": total_support,
        "aggregate_contradiction_count": total_transitions - total_support,
        "aggregate_support_rate": round(total_support / total_transitions, 6),
        "interpretation_boundary": (
            "descriptive prospective evidence only; no automatic activation decision, "
            "Phase42 credit, or action authority"
        ),
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
