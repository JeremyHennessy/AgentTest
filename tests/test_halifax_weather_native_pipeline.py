from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "halifax_weather_native_pipeline.py"
spec = importlib.util.spec_from_file_location("halifax_weather_native_pipeline", SCRIPT)
assert spec is not None and spec.loader is not None
pipeline = importlib.util.module_from_spec(spec)
sys.modules["halifax_weather_native_pipeline"] = pipeline
spec.loader.exec_module(pipeline)


class HalifaxWeatherNativePipelineTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 50
        state["generation"] = 50
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return store

    def observations(self):
        speeds = [10, 12, 11, 13, 18, 16, 15, 14]
        return [
            {
                "observation_id": f"weather-{index}",
                "station_name": "HALIFAX STANFIELD INT'L A",
                "climate_identifier": "8202251",
                "utc_date": f"2026-10-04T{index:02d}:00:00",
                "wind_speed_kmh": value,
            }
            for index, value in enumerate(speeds)
        ]

    def test_real_observations_become_public_v2_evidence_and_inquiry(self):
        store = self.make_store()
        result = pipeline.stage_isolated_inquiry(
            AgentCore(store),
            self.observations(),
        )
        evidence = result["evidence_result"]["evidence"]
        inquiry = result["inquiry_result"]
        self.assertEqual(evidence["version"], "native-inquiry-evidence-v2")
        self.assertEqual(evidence["measurement_kind"], "binary_transition_outcomes")
        self.assertEqual(
            evidence["relation"],
            inquiry["candidate"]["relation"],
        )
        self.assertEqual(
            inquiry["experiment"]["specification"]["actionability"],
            "actionable",
        )
        self.assertEqual(store.load()["cycles"], 50)

    def test_next_normal_cycle_sees_weather_inquiry_without_action_authority(self):
        store = self.make_store()
        core = AgentCore(store)
        staged = pipeline.stage_isolated_inquiry(core, self.observations())
        question_id = staged["inquiry_result"]["question"]["id"]
        cycle = core.cycle(
            stimulus="continue ordinary operation",
            _now_override="2026-10-05T00:00:00+00:00",
        )
        self.assertIsNone(cycle["action_lab_result"])
        self.assertIsNone(cycle["planning_lab_result"])
        summary = next(
            item for item in cycle["agenda_decision"]["candidate_summaries"]
            if item["question_id"] == question_id
        )
        self.assertTrue(summary["active_experiment_path"])

    def test_pipeline_has_no_network_or_environment_action(self):
        source = SCRIPT.read_text()
        for forbidden in (
            "requests",
            "urllib",
            "subprocess",
            "transition_world",
            "action_lab",
            "planning_lab",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
