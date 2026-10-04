from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.state import initial_state
from native_relation_family_memory import FAMILY_MEMORY_KEY, rank_held_out_proposals
from native_relation_discovery import RELATION_VERSION
from native_relation_transfer_core import run_held_out_relation_core_path
from trajectory_relation_profiles import (
    world2_stability_trajectory,
    world3_action_trajectory,
    world3_change_trajectory,
)

HELD_OUT = [
    {"id": "H1", "version": RELATION_VERSION, "relation": "action_precedes_change", "feature": "novel_signal", "action": "interact"},
    {"id": "H2", "version": RELATION_VERSION, "relation": "same_next_observation", "feature": "novel_signal", "action": None},
    {"id": "H3", "version": RELATION_VERSION, "relation": "changes_next_observation", "feature": "novel_signal", "action": None},
]


def main() -> None:
    profiles = {}
    for name, fn in (
        ("stability", world2_stability_trajectory),
        ("change", world3_change_trajectory),
        ("action", world3_action_trajectory),
    ):
        state = initial_state()
        output = fn(state)
        ranked = rank_held_out_proposals(state, HELD_OUT)
        core = run_held_out_relation_core_path(state, HELD_OUT)
        profiles[name] = {
            "sample_count": len(output["samples"]),
            "family_memory": state[FAMILY_MEMORY_KEY],
            "ranked": ranked,
            "selected_relation": core["selected"]["proposal"]["relation"],
            "selected_id": core["selected"]["proposal"]["id"],
            "selected_score": core["selected"]["score"],
        }
    report = {
        "study": "actual-trajectory-relation-transfer-v1",
        "scoring_rule": "frozen-native-relation-family-memory-v0",
        "held_out_feature": "novel_signal",
        "profiles": profiles,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
