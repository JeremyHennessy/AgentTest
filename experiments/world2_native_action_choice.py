from __future__ import annotations

from copy import deepcopy
from typing import Any

from world2_native_opportunity import select_native_inquiry

ACTION_CHOICE_VERSION = "world2-native-action-choice-v0"
_MOVE_FOR_DELTA = {
    (1, 0): "north",
    (0, -1): "east",
    (-1, 0): "south",
    (0, 1): "west",
}


def propose_action_for_inquiry(
    state: dict[str, Any], current_position: list[int]
) -> dict[str, Any]:
    """Propose one bounded test action from an inquiry target; never execute it."""
    selected = select_native_inquiry(state)
    if selected is None:
        return {
            "version": ACTION_CHOICE_VERSION,
            "status": "no_inquiry",
            "action": "observe",
            "inquiry": None,
            "reason": "No persisted native inquiry currently has test value.",
        }

    target = selected.get("target_position")
    if target is None:
        action = "observe"
        reason = "The selected broadcast hypothesis can be tested by another observation."
    elif current_position == target:
        action = "observe"
        reason = "The selected local hypothesis is testable at the current position."
    else:
        dx = int(target[0]) - int(current_position[0])
        dy = int(target[1]) - int(current_position[1])
        if dx:
            delta = (1 if dx > 0 else -1, 0)
        else:
            delta = (0, 1 if dy > 0 else -1)
        action = _MOVE_FOR_DELTA[delta]
        reason = "Move one bounded step toward the selected inquiry's observed target."

    return {
        "version": ACTION_CHOICE_VERSION,
        "status": "proposed",
        "action": action,
        "inquiry": deepcopy(selected),
        "reason": reason,
    }
