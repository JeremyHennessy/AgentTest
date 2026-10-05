from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from open_object_world_explorer import run_unguided


def main() -> None:
    rows = [run_unguided(seed, steps=240) for seed in range(1, 5)]
    report = {
        "study": "open-object-world-unguided-discovery-v1",
        "world": "open-object-world-v0",
        "policy": "least-tried public observation-command pair",
        "guided_solution": False,
        "reward_signal": False,
        "rows": rows,
        "summary": {
            "all_layouts_explored_multiple_positions": all(
                row["unique_position_count"] > 4 for row in rows
            ),
            "all_layouts_changed_inventory": all(
                row["unique_inventory_state_count"] > 1 for row in rows
            ),
            "layouts_with_observed_state_change": sum(
                1
                for row in rows
                if row["entities_with_multiple_observed_states"]
            ),
            "layouts_with_target_state_change_effect": sum(
                1
                for row in rows
                if row["observed_effect_counts"].get(
                    "target_state_changed", 0
                ) > 0
            ),
            "layouts_with_target_position_change_effect": sum(
                1
                for row in rows
                if row["observed_effect_counts"].get(
                    "target_position_changed", 0
                ) > 0
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
