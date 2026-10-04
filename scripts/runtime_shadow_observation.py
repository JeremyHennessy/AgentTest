from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


SCHEMA_VERSION = "runtime-shadow-observation-v1"


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def seconds_between(start: str | None, end: str | None) -> float | None:
    left = parse_time(start)
    right = parse_time(end)
    if left is None or right is None:
        return None
    return round((right - left).total_seconds(), 3)


def normalize_run(run: dict[str, Any], job: dict[str, Any] | None) -> dict[str, Any]:
    steps = {
        str(item.get("name") or ""): item
        for item in (job or {}).get("steps", [])
        if isinstance(item, dict)
    }

    def step_seconds(name: str) -> float | None:
        item = steps.get(name)
        if not item:
            return None
        return seconds_between(item.get("started_at"), item.get("completed_at"))

    created = run.get("created_at") or run.get("createdAt")
    started = run.get("run_started_at") or run.get("started_at") or run.get("startedAt")
    updated = run.get("updated_at") or run.get("updatedAt")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": int(run.get("id") or run.get("databaseId") or 0),
        "run_number": int(run.get("run_number") or run.get("runNumber") or 0),
        "head_sha": str(run.get("head_sha") or run.get("headSha") or ""),
        "conclusion": run.get("conclusion"),
        "queue_delay_s": seconds_between(created, started),
        "total_duration_s": seconds_between(started, updated),
        "checkout_duration_s": step_seconds("Run actions/checkout@v4"),
        "cycle_duration_s": step_seconds("Observe and run one autonomous cycle"),
        "preserve_duration_s": step_seconds("Preserve cycle"),
        "experiment_health_duration_s": step_seconds("Measure experiment design health"),
        "attention_health_duration_s": step_seconds("Measure blocked attention health"),
        "phase42_integrity_duration_s": step_seconds("Verify Phase 42 live-state integrity"),
        "phase42_opportunity_duration_s": step_seconds("Measure Phase 42 resumption opportunities"),
    }


def summarize(observations: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(observations, key=lambda item: item["run_number"])
    fields = [
        "queue_delay_s",
        "total_duration_s",
        "checkout_duration_s",
        "cycle_duration_s",
        "preserve_duration_s",
    ]
    stats: dict[str, Any] = {}
    for field in fields:
        values = [
            float(item[field])
            for item in ordered
            if isinstance(item.get(field), (int, float))
        ]
        changes = sum(
            1
            for left, right in zip(values, values[1:])
            if left != right
        )
        stats[field] = {
            "observed_count": len(values),
            "distinct_values": sorted(set(values)),
            "distinct_count": len(set(values)),
            "change_count": changes,
            "change_rate": round(changes / max(1, len(values) - 1), 6)
            if values
            else None,
            "mean": round(mean(values), 6) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
        }

    ids = [item["run_id"] for item in ordered]
    return {
        "schema_version": SCHEMA_VERSION,
        "observation_count": len(ordered),
        "unique_run_count": len(set(ids)),
        "deduplicated": len(ids) == len(set(ids)),
        "first_run_number": ordered[0]["run_number"] if ordered else None,
        "last_run_number": ordered[-1]["run_number"] if ordered else None,
        "all_successful": all(item.get("conclusion") == "success" for item in ordered),
        "fields": stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    parser.add_argument("--jobs-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    runs = json.loads(Path(args.runs).read_text())
    jobs_dir = Path(args.jobs_dir)
    observations = []
    for run in runs:
        run_id = int(run.get("id") or run.get("databaseId") or 0)
        job_path = jobs_dir / f"{run_id}.json"
        job = None
        if job_path.exists():
            payload = json.loads(job_path.read_text())
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            job = jobs[0] if jobs else None
        observations.append(normalize_run(run, job))

    report = {
        "study": "runtime-shadow-observation-v1",
        "source": "github_actions_autonomous_growth",
        "fed_to_ora": False,
        "authority": "read_only_shadow",
        "observations": observations,
        "summary": summarize(observations),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    Path(args.output).write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
