"""Bounded copied-world action policy. Receives ONLY public JSON on stdin.

Authored curiosity heuristic plus empirical action-effect predictions; this is NOT
learned meta-control, an LLM, or proof of autonomous intelligence.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import sys

DOMAIN = [(x, y) for x in range(-2, 3) for y in range(-2, 3)]


def forecast(view: dict, history: list, action: str) -> list[float]:
    pos = tuple(view['position'])
    local, global_delta = Counter(), Counter()
    for row in history:
        if row['action'] != action:
            continue
        before, after = tuple(row['before']), tuple(row['after'])
        if before == pos:
            local[after] += 1
        if not row['blocked']:
            global_delta[(after[0]-before[0], after[1]-before[1])] += 1
    global_counts = Counter()
    for delta, count in global_delta.items():
        target = (pos[0] + delta[0], pos[1] + delta[1])
        target = (max(-2, min(2, target[0])), max(-2, min(2, target[1])))
        global_counts[target] += count
    def distribution(counts):
        total = sum(counts.values())
        if not total:
            return [1 / 25] * 25
        return [0.1 / 25 + 0.9 * counts[p] / total for p in DOMAIN]
    g = distribution(global_counts)
    if not local:
        return g
    l = distribution(local)
    weight = min(0.65, sum(local.values()) / (sum(local.values()) + 4))
    return [(1 - weight) * a + weight * b for a, b in zip(g, l)]


def decide(message: dict) -> dict:
    if set(message) != {'public_view', 'history'}:
        raise ValueError('private data or missing public inputs')
    view, history = message['public_view'], message['history']
    if (set(view) != {'world_version', 'position', 'available_actions',
                     'steps_completed', 'remaining_budget'} or
            type(history) is not list or len(history) != view['steps_completed'] or
            view['remaining_budget'] < 1):
        raise ValueError('invalid public view or chronology')
    actions = view['available_actions']
    if not actions or len(actions) != len(set(actions)):
        raise ValueError('invalid public menu')
    proposals = []
    for action in actions:
        probs = forecast(view, history, action)
        if not math.isclose(sum(probs), 1.0, rel_tol=0, abs_tol=1e-12):
            raise ValueError('non-normalized forecast')
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        n = sum(r['action'] == action and r['before'] == view['position'] for r in history)
        proposals.append((entropy + 0.1 / (1 + n), action, probs))
    # Stable deterministic tie-breaking; no simulator seed or hidden rule access.
    _, action, probs = sorted(proposals, key=lambda x: (-x[0], x[1]))[0]
    return {'action': action, 'forecast': probs,
            'policy': 'public-empirical-curiosity-v1'}


if __name__ == '__main__':
    try:
        request = json.loads(sys.stdin.read(1_000_000))
        print(json.dumps(decide(request), sort_keys=True, allow_nan=False))
    except (ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
