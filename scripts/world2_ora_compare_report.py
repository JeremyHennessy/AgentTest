from __future__ import annotations

import json

from agenttest.state import initial_state
from world2_ora_compare import compare_world2_to_control


def main() -> int:
    source = initial_state()
    actions = [
        "north", "interact", "south", "observe", "west", "observe",
        "east", "observe", "north", "west", "observe", "south",
        "observe", "interact", "observe", "east", "observe", "west",
        "observe", "observe", "north", "observe", "south", "observe",
    ]
    reports = [
        compare_world2_to_control(source, seed=seed, actions=actions)
        for seed in (1, 2, 3, 4, 5)
    ]
    print(json.dumps(reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
