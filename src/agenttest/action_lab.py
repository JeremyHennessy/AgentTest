from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

ACTION_LAB_VERSION = "bounded-action-lab-v1"
ACTION_ORDER = ("north", "east", "south", "west")
MIN_EFFECT_SAMPLES = 2
BOUNDS = 2

# The labels are intentionally not their ordinary spatial meanings. AgentTest is
# given only action outcomes and must learn the transition mapping empirically.
_HIDDEN_ACTION_DELTAS: dict[str, tuple[int, int]] = {
    "north": (1, 0),
    "east": (0, -1),
    "south": (-1, 0),
    "west": (0, 1),
}


def initial_action_lab_state() -> dict[str, Any]:
    return {
        "version": ACTION_LAB_VERSION,
        "bounds": BOUNDS,
        "position": [0, 0],
        "visit_counts": {"0,0": 1},
        "history": [],
        "learned_effects": {},
        "last_action_cycle": None,
    }


def ensure_action_lab_state(state: dict[str, Any]) -> dict[str, Any]:
    lab = state.setdefault("action_lab", initial_action_lab_state())
    lab.setdefault("version", ACTION_LAB_VERSION)
    lab.setdefault("bounds", BOUNDS)
    lab.setdefault("position", [0, 0])
    lab.setdefault("visit_counts", {"0,0": 1})
    lab.setdefault("history", [])
    lab.setdefault("learned_effects", {})
    lab.setdefault("last_action_cycle", None)
    return lab


def _position_key(position: list[int] | tuple[int, int]) -> str:
    return f"{int(position[0])},{int(position[1])}"


def _in_bounds(position: tuple[int, int], bounds: int) -> bool:
    return all(-bounds <= value <= bounds for value in position)


def _rebuild_learned_effects(lab: dict[str, Any]) -> dict[str, Any]:
    samples: dict[str, list[tuple[int, int]]] = defaultdict(list)
    blocked_counts: Counter[str] = Counter()

    for record in lab.get("history", []):
        action = str(record.get("action") or "")
        if action not in ACTION_ORDER:
            continue
        if record.get("blocked"):
            blocked_counts[action] += 1
            continue
        delta = record.get("delta")
        if (
            isinstance(delta, list)
            and len(delta) == 2
            and all(isinstance(value, int) for value in delta)
        ):
            samples[action].append((delta[0], delta[1]))

    learned: dict[str, Any] = {}
    for action in ACTION_ORDER:
        action_samples = samples[action]
        effect_counts = Counter(action_samples)
        if effect_counts:
            effect, count = sorted(
                effect_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0]
            confidence = count / len(action_samples)
            modal_delta = [int(effect[0]), int(effect[1])]
        else:
            confidence = 0.0
            modal_delta = None

        learned[action] = {
            "unblocked_samples": len(action_samples),
            "blocked_samples": int(blocked_counts[action]),
            "modal_delta": modal_delta,
            "confidence": round(confidence, 6),
        }

    lab["learned_effects"] = learned
    return learned


def choose_action(lab: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    learned = _rebuild_learned_effects(lab)

    undersampled = [
        action
        for action in ACTION_ORDER
        if int(learned[action]["unblocked_samples"]) < MIN_EFFECT_SAMPLES
    ]
    if undersampled:
        action = min(
            undersampled,
            key=lambda name: (
                int(learned[name]["unblocked_samples"]),
                ACTION_ORDER.index(name),
            ),
        )
        return action, {
            "kind": "learn_transition",
            "reason": "Choose the least-sampled permitted action to identify its effect.",
            "target_action": action,
        }

    position = tuple(int(value) for value in lab.get("position", [0, 0]))
    bounds = int(lab.get("bounds", BOUNDS))
    visits = lab.get("visit_counts", {})

    candidates: list[tuple[int, int, str, tuple[int, int]]] = []
    for action in ACTION_ORDER:
        delta = learned[action].get("modal_delta")
        if not isinstance(delta, list) or len(delta) != 2:
            continue
        target = (position[0] + int(delta[0]), position[1] + int(delta[1]))
        if not _in_bounds(target, bounds):
            continue
        visit_count = int(visits.get(_position_key(target), 0) or 0)
        candidates.append(
            (
                visit_count,
                ACTION_ORDER.index(action),
                action,
                target,
            )
        )

    if candidates:
        visit_count, _, action, target = min(candidates)
        return action, {
            "kind": "use_learned_transition",
            "reason": (
                "Use the learned action-effect model to move toward the least-visited "
                "reachable location."
            ),
            "predicted_target": [target[0], target[1]],
            "predicted_target_visits": visit_count,
            "source_samples": int(
                learned[action].get("unblocked_samples", 0) or 0
            ),
        }

    action = ACTION_ORDER[0]
    return action, {
        "kind": "bounded_fallback",
        "reason": "No learned in-bounds transition was available; use fixed safe fallback.",
        "target_action": action,
    }


def step_action_lab(state: dict[str, Any]) -> dict[str, Any]:
    """Execute exactly one whitelisted internal action with no external side effects."""

    lab = ensure_action_lab_state(state)
    before = [int(value) for value in lab.get("position", [0, 0])]
    action, decision = choose_action(lab)
    if action not in ACTION_ORDER:
        raise ValueError(f"action is not permitted: {action}")

    delta = _HIDDEN_ACTION_DELTAS[action]
    proposed = (before[0] + delta[0], before[1] + delta[1])
    bounds = int(lab.get("bounds", BOUNDS))
    blocked = not _in_bounds(proposed, bounds)
    after = before if blocked else [proposed[0], proposed[1]]
    observed_delta = [after[0] - before[0], after[1] - before[1]]

    record = {
        "id": f"LA{len(lab.get('history', [])) + 1:06d}",
        "cycle": int(state.get("cycles", 0) or 0),
        "action": action,
        "before": before,
        "after": after,
        "delta": observed_delta,
        "blocked": blocked,
        "decision": decision,
    }
    lab.setdefault("history", []).append(record)
    lab["position"] = list(after)
    key = _position_key(after)
    lab.setdefault("visit_counts", {})[key] = (
        int(lab["visit_counts"].get(key, 0) or 0) + 1
    )
    lab["last_action_cycle"] = int(state.get("cycles", 0) or 0)
    learned = _rebuild_learned_effects(lab)

    result = {
        **record,
        "lab_version": ACTION_LAB_VERSION,
        "learned_effects": json.loads(json.dumps(learned)),
        "visited_location_count": len(lab.get("visit_counts", {})),
    }
    return result
