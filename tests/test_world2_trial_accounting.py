from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import StateStore

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in ("world2_ecology", "world2_ora_isolated", "world2_ora_compare"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module

adapter = sys.modules["world2_ora_isolated"]
compare = sys.modules["world2_ora_compare"]
world = sys.modules["world2_ecology"]


class World2TrialAccountingTests(unittest.TestCase):
    def test_first_observation_is_matched_in_both_arms(self):
        initial = world.initial_world2_state(seed=3)
        moved, _ = world.transition_world2(initial, "north", cycle=1)
        self.assertEqual(
            compare.stable_control_observation(seed=3, first_action="north"),
            adapter.world2_repository_shaped_observation(world.observe_world2(moved), world_seed=3),
        )

    def test_changed_sensor_reading_reaches_prediction_error_without_intervention(self):
        observation = world.observe_world2(world.initial_world2_state(seed=1))
        observation["local_resource"] = 1
        first = adapter.world2_repository_shaped_observation(observation)
        observation["local_resource"] = 2
        observation["cycle"] = 1
        second = adapter.world2_repository_shaped_observation(observation)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "organism.json"
            AgentCore(StateStore(path)).cycle(observation=first, cognition=False, strict_experiment_admission=True)
            result = AgentCore(StateStore(path)).cycle(observation=second, cognition=False, strict_experiment_admission=True)
        self.assertEqual(result["prediction_result"]["status"], "violated")
        self.assertIn("test_files", result["prediction_result"]["errors"])
        self.assertGreater(result["drives"]["prediction_error"], 0)

    def test_summary_excludes_pre_trial_history(self):
        start = {
            "cycle": 10, "question_ids": ["Q_OLD"], "question_texts": ["Old"],
            "counts": {"surprises": 1, "predictions": 1, "experiments": 1, "reflections": 1},
            "empirical_family_count": 1, "genuine_resumption_count": 5,
        }
        final = {
            "cycles": 11, "questions": [{"id": "Q_OLD", "text": "Old"}, {"id": "Q_NEW", "text": "New"}],
            "surprises": [{"cycle": 1, "changes": {"old": 1}}, {"cycle": 11, "changes": {"test_files": 2}}],
            "predictions": [{}, {}], "experiments": [{}, {}], "reflections": [{}, {}],
            "empirical_learning": {"families": {"old": {}}},
            "agenda": {"threads": [], "decisions": [{"cycle": 1, "foreground_changed": True}], "genuine_resumption_count": 5},
        }
        cycles = [{"cycle": 11, "question": {"text": "New"}, "intention": {"kind": "explain_change"},
                   "prediction_result": {"status": "violated"},
                   "agenda_decision": {"selected": {"question_id": "Q_NEW"}, "foreground_changed": False}}]
        summary = compare.summarize_trial({"trial_start": start, "ora_final": final, "cycles": cycles})
        self.assertEqual(summary["new_question_count"], 1)
        self.assertEqual(summary["distinct_question_text_count"], 1)
        self.assertEqual(summary["surprise_count"], 1)
        self.assertEqual(summary["foreground_change_count"], 0)
        self.assertEqual(summary["genuine_resumption_count"], 0)
        self.assertEqual(summary["prediction_count"], 1)
        self.assertEqual(summary["surprise_field_counts"], {"test_files": 1})


if __name__ == "__main__":
    unittest.main()
