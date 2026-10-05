from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


shadow = load("halifax_weather_shadow")
evaluation = load("halifax_weather_shadow_eval")


class HalifaxWeatherShadowTests(unittest.TestCase):
    def test_normalizer_uses_observations_not_forecasts(self):
        row = {
            "ID": "x",
            "STATION_NAME": "HALIFAX STANFIELD INT'L A",
            "CLIMATE_IDENTIFIER": "8202250",
            "UTC_DATE": "2026-10-04T20:00:00",
            "LOCAL_DATE": "2026-10-04 17:00:00",
            "TEMP": "12.3",
            "RELATIVE_HUMIDITY": "75",
            "STATION_PRESSURE": "101.2",
            "VISIBILITY": "24.1",
            "WIND_SPEED": "15",
            "WIND_DIRECTION": "28",
            "DEW_POINT_TEMP": "8.0",
            "PRECIP_AMOUNT": "",
            "WEATHER_ENG_DESC": "Cloudy",
        }
        item = shadow.normalize(row)
        self.assertEqual(item["temperature_c"], 12.3)
        self.assertEqual(item["conditions"], "Cloudy")
        self.assertNotIn("forecast", item)
        self.assertNotIn("prediction", item)

    def test_thresholds_are_frozen(self):
        self.assertEqual(evaluation.THRESHOLDS["temperature_c"], 1.0)
        self.assertEqual(evaluation.THRESHOLDS["relative_humidity_pct"], 5.0)
        self.assertEqual(evaluation.THRESHOLDS["station_pressure_kpa"], 0.3)
        self.assertEqual(evaluation.WINDOW, 24)

    def test_no_agent_state_or_action_access(self):
        source = (ROOT / "scripts" / "halifax_weather_shadow.py").read_text()
        source += (ROOT / "scripts" / "halifax_weather_shadow_eval.py").read_text()
        for forbidden in (
            "AgentCore",
            "StateStore",
            "state/organism.json",
            "propose_native_inquiry",
            "record_native_evidence",
            "transition_world",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
