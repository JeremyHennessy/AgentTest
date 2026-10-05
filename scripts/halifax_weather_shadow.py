from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "halifax-weather-shadow-v1"
FIELDS = {
    "TEMP": "temperature_c",
    "DEW_POINT_TEMP": "dew_point_c",
    "RELATIVE_HUMIDITY": "relative_humidity_pct",
    "STATION_PRESSURE": "station_pressure_kpa",
    "VISIBILITY": "visibility_km",
    "WIND_DIRECTION": "wind_direction_tens_deg",
    "WIND_SPEED": "wind_speed_kmh",
    "PRECIP_AMOUNT": "precip_amount_mm",
    "WEATHER_ENG_DESC": "conditions",
}


def number(value: Any) -> float | None:
    if value is None or str(value).strip() in {"", "None", "null"}:
        return None
    return float(value)


def normalize(row: dict[str, Any]) -> dict[str, Any]:
    item = {
        "schema_version": SCHEMA_VERSION,
        "observation_id": str(row.get("ID") or row.get("id") or ""),
        "station_name": str(row.get("STATION_NAME") or ""),
        "climate_identifier": str(row.get("CLIMATE_IDENTIFIER") or ""),
        "utc_date": str(row.get("UTC_DATE") or ""),
        "local_date": str(row.get("LOCAL_DATE") or ""),
    }
    for source, target in FIELDS.items():
        value = row.get(source)
        item[target] = (
            str(value).strip()
            if target == "conditions" and value not in (None, "")
            else number(value)
            if target != "conditions"
            else None
        )
    return item


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--climate-identifier", required=True)
    parser.add_argument("--station-name", required=True)
    args = parser.parse_args()

    with Path(args.input).open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows = [
        row for row in rows
        if str(row.get("CLIMATE_IDENTIFIER") or "") == args.climate_identifier
        and str(row.get("STATION_NAME") or "") == args.station_name
    ]
    if not rows:
        raise ValueError("no observations matched the pinned station provenance")
    observations = [normalize(row) for row in rows]
    observations.sort(key=lambda item: item["utc_date"])
    ids = [item["observation_id"] for item in observations]
    report = {
        "study": SCHEMA_VERSION,
        "source": "environment_canada_climate_hourly_observations",
        "fed_to_ora": False,
        "authority": "read_only_shadow",
        "observation_count": len(observations),
        "deduplicated": len(ids) == len(set(ids)),
        "station_names": sorted({item["station_name"] for item in observations}),
        "observations": observations,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    Path(args.output).write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
