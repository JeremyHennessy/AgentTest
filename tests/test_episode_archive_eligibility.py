from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "episode_archive_eligibility_eval.py"
spec = importlib.util.spec_from_file_location(
    "episode_archive_eligibility_eval",
    SCRIPT,
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules["episode_archive_eligibility_eval"] = module
spec.loader.exec_module(module)


def episode(
    identifier: str,
    cycle: int,
    kind: str = "stimulus",
    content: str = "x",
):
    return {
        "id": identifier,
        "cycle": cycle,
        "time": "2026-10-05T00:00:00+00:00",
        "kind": kind,
        "content": content,
        "concepts": [],
    }


class EpisodeArchiveEligibilityTests(unittest.TestCase):
    def test_explicit_external_episode_refs_are_protected(self):
        state = initial_state()
        state["cycles"] = 10
        state["episodes"] = [
            episode(f"E{index:06d}", index)
            for index in range(1, 7)
        ]
        state["next_episode_index"] = 7
        state["reflections"] = [
            {
                "id": "R000001",
                "evidence_refs": ["E000002"],
            }
        ]
        result = module.derive_protection(state, hot_suffix=1)
        self.assertIn("E000002", result["protected_ids"])
        self.assertNotIn("E000002", result["eligible_ids"])
        self.assertIn("E000001", result["eligible_ids"])

    def test_hot_suffix_and_current_cycles_are_never_eligible(self):
        state = initial_state()
        state["cycles"] = 20
        state["episodes"] = [
            episode(f"E{index:06d}", index)
            for index in range(1, 21)
        ]
        state["next_episode_index"] = 21
        result = module.derive_protection(state, hot_suffix=4)
        for identifier in (
            "E000017",
            "E000018",
            "E000019",
            "E000020",
        ):
            self.assertIn(identifier, result["protected_ids"])
        self.assertNotIn("E000001", result["protected_ids"])

    def test_pending_world_snapshot_environment_episode_is_protected(self):
        state = initial_state()
        state["cycles"] = 5
        state["episodes"] = [
            episode("E000001", 1),
            episode("E000002", 2, "environment"),
            episode("E000003", 3),
        ]
        state["next_episode_index"] = 4
        state["environment_snapshots"] = [
            {"cycle": 1},
            {"cycle": 2},
        ]
        state["world_model"]["last_snapshot_index"] = 1
        result = module.derive_protection(state, hot_suffix=0)
        self.assertIn("E000002", result["protected_ids"])
        self.assertIn("E000001", result["eligible_ids"])

    def test_pending_planning_memory_source_episode_is_protected(self):
        state = initial_state()
        state["cycles"] = 20
        state["episodes"] = [
            episode("E000001", 1),
            episode(
                "E000002",
                10,
                "planning_lab",
                json.dumps({"plan_id": "PP000001"}),
            ),
            episode(
                "E000003",
                11,
                "planning_lab",
                json.dumps({"plan_id": "PP000001"}),
            ),
        ]
        state["next_episode_index"] = 4
        lab = state["planning_lab"]
        lab["episodic_memory_started_cycle"] = 1
        lab["plans"] = [
            {
                "id": "PP000001",
                "status": "completed",
                "completed_cycle": 11,
                "world_version": lab["world_version"],
            }
        ]
        lab["executions"] = [
            {
                "plan_id": "PP000001",
                "cycle": 10,
                "step_index": 0,
                "matched_prediction": True,
            },
            {
                "plan_id": "PP000001",
                "cycle": 11,
                "step_index": 1,
                "matched_prediction": True,
            },
        ]
        lab["episodic_route_memories"] = []
        result = module.derive_protection(state, hot_suffix=0)
        self.assertIn("E000002", result["protected_ids"])
        self.assertIn("E000003", result["protected_ids"])
        self.assertIn("E000001", result["eligible_ids"])

    def test_existing_route_memory_turns_raw_planning_episode_back_into_normal_eligibility(self):
        state = initial_state()
        state["cycles"] = 20
        state["episodes"] = [
            episode(
                "E000001",
                10,
                "planning_lab",
                json.dumps({"plan_id": "PP000001"}),
            )
        ]
        state["next_episode_index"] = 2
        lab = state["planning_lab"]
        lab["episodic_memory_started_cycle"] = 1
        lab["plans"] = [
            {
                "id": "PP000001",
                "status": "completed",
                "completed_cycle": 10,
                "world_version": lab["world_version"],
            }
        ]
        lab["executions"] = [
            {
                "plan_id": "PP000001",
                "cycle": 10,
                "step_index": 0,
                "matched_prediction": True,
            }
        ]
        lab["episodic_route_memories"] = [
            {
                "id": "EM000001",
                "source_plan_id": "PP000001",
                "source_episode_ids": [],
            }
        ]
        result = module.derive_protection(state, hot_suffix=0)
        self.assertIn("E000001", result["eligible_ids"])

    def test_opaque_episode_identity_fails_closed(self):
        state = initial_state()
        state["episodes"] = [episode("legacy-opaque", 1)]
        with self.assertRaisesRegex(ValueError, "opaque episode"):
            module.derive_protection(state, hot_suffix=0)


if __name__ == "__main__":
    unittest.main()
