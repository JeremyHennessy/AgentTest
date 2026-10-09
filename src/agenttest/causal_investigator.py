"""Evidence-owned investigation selection for a separate, bounded AgentTest study.

No world or transition import is permitted in this module. Decisions see only
public observations and earlier completed public outcomes; neither a hidden
map nor a designer-assigned goal, reward, success predicate, or answer.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from typing import Any

VERSION = "phase42-evidence-owned-v1"
OUTCOMES = (
    "blocked",
    "moved",
    "inventory_changed",
    "observable_state_changed",
    "visibility_changed",
    "reported_effect",
    "no_observed_effect",
)
MAX_HISTORY = 256
MAX_MENU = 128


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def project_public(observation: dict[str, Any]) -> dict[str, Any]:
    """Whitelisted observation projection, excluding cycle and private state."""
    if not isinstance(observation, dict):
        raise ValueError("public observation must be a mapping")
    position = observation.get("position")
    if (not isinstance(position, list) or len(position) != 2
            or any(type(x) is not int or not -128 <= x <= 128 for x in position)):
        raise ValueError("invalid public position")
    inventory = observation.get("inventory_ids")
    visible = observation.get("visible_entities")
    if (not isinstance(inventory, list) or not isinstance(visible, list)
            or len(inventory) > 64 or len(visible) > 64):
        raise ValueError("invalid public entities")
    if any(not isinstance(x, str) or not 0 < len(x) <= 128 for x in inventory):
        raise ValueError("invalid inventory id")
    if len(set(inventory)) != len(inventory):
        raise ValueError("duplicate inventory id")
    items = []
    seen = set()
    for item in visible:
        if not isinstance(item, dict):
            raise ValueError("invalid visible entity")
        identifier = item.get("id")
        loc = item.get("position")
        if (not isinstance(identifier, str) or not 0 < len(identifier) <= 128
                or identifier in seen or not isinstance(loc, list)
                or len(loc) != 2 or any(type(x) is not int for x in loc)):
            raise ValueError("invalid visible entity identity or position")
        seen.add(identifier)
        appearance = item.get("appearance", "")
        if not isinstance(appearance, str) or len(appearance) > 512:
            raise ValueError("invalid appearance")
        observed = item.get("observable_state")
        if observed is not None and (
            not isinstance(observed, str) or len(observed) > 128
        ):
            raise ValueError("invalid observable state")
        items.append({
            "id": identifier,
            "position": list(loc),
            "appearance": appearance,
            "observable_state": observed,
        })
    items.sort(key=lambda item: item["id"])
    return {
        "position": list(position),
        "inventory_ids": sorted(inventory),
        "visible_entities": items,
    }


def command_key(command: dict[str, Any]) -> tuple[str, str, str]:
    if not isinstance(command, dict):
        raise ValueError("command must be a mapping")
    if not set(command).issubset({"action", "target", "direction"}):
        raise ValueError("unrecognized command fields")
    action = command.get("action")
    if not isinstance(action, str) or not 0 < len(action) <= 64:
        raise ValueError("invalid command action")
    values = [action]
    for field in ("target", "direction"):
        value = command.get(field)
        if value is not None and (not isinstance(value, str) or not 0 < len(value) <= 128):
            raise ValueError("invalid command " + field)
        values.append(value or "")
    return tuple(values)


def _family(public: dict[str, Any], command: dict[str, Any]) -> str:
    action, target, direction = command_key(command)
    # Object labels are not baked into shared generalizations. Only what the
    # agent actually sees (appearance/state) is available to generalize from.
    kind = "no-target"
    if target:
        for item in public["visible_entities"]:
            if item["id"] == target:
                kind = "seen:" + item["appearance"] + ":" + str(item["observable_state"])
                break
        else:
            kind = "held" if target in public["inventory_ids"] else "not-visible"
    return _digest([action, direction, kind])


def _context(public: dict[str, Any], command: dict[str, Any]) -> str:
    return _digest([public, command_key(command)])


def classify_outcome(
    before: dict[str, Any], after: dict[str, Any], receipt: dict[str, Any]
) -> str:
    pre = project_public(before)
    post = project_public(after)
    if not isinstance(receipt, dict):
        raise ValueError("missing public action receipt")
    if receipt.get("blocked") is True:
        return "blocked"
    if pre["position"] != post["position"]:
        return "moved"
    if pre["inventory_ids"] != post["inventory_ids"]:
        return "inventory_changed"
    prior = {i["id"]: i["observable_state"] for i in pre["visible_entities"]}
    newer = {i["id"]: i["observable_state"] for i in post["visible_entities"]}
    if any(prior[k] != newer[k] for k in prior.keys() & newer.keys()):
        return "observable_state_changed"
    if pre["visible_entities"] != post["visible_entities"]:
        return "visibility_changed"
    if receipt.get("observed_effects"):
        return "reported_effect"
    return "no_observed_effect"


def _history_stats(
    public: dict[str, Any], command: dict[str, Any],
    history: list[dict[str, Any]],
) -> tuple[Counter, Counter, int, int, list[str]]:
    family = _family(public, command)
    context = _context(public, command)
    local = Counter()
    pooled = Counter()
    refs = []
    for event in history:
        kind = event["outcome_kind"]
        if kind not in OUTCOMES:
            raise ValueError("invalid prior event outcome")
        row_public = project_public(event["public_before"])
        row_command = event["command"]
        if _family(row_public, row_command) == family:
            pooled[kind] += 1
            refs.append(event["id"])
            if _context(row_public, row_command) == context:
                local[kind] += 1
    return local, pooled, sum(local.values()), sum(pooled.values()), refs


def forecast(
    public_observation: dict[str, Any],
    command: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(history) > MAX_HISTORY:
        raise ValueError("history budget exhausted")
    public = project_public(public_observation)
    local, pooled, local_n, family_n, refs = _history_stats(public, command, history)
    k = len(OUTCOMES)
    # Hierarchical, deliberately conservative smoothing. Empirical action
    # families supply a prior; current context can override that prior.
    family_prob = {o: (pooled[o] + 0.5) / (family_n + 0.5 * k) for o in OUTCOMES}
    probabilities = {
        o: (local[o] + 2.0 * family_prob[o]) / (local_n + 2.0)
        for o in OUTCOMES
    }
    assert abs(sum(probabilities.values()) - 1.0) < 1e-9
    return {
        "probabilities": {o: round(probabilities[o], 12) for o in OUTCOMES},
        "local_samples": local_n,
        "family_samples": family_n,
        "evidence_refs": refs,
        "predicted_outcome": max(OUTCOMES, key=lambda o: (probabilities[o], -OUTCOMES.index(o))),
        "local_blocked": local["blocked"],
        "local_no_effect": local["no_observed_effect"],
    }


def select_investigation(
    observation: dict[str, Any],
    prior_events: list[dict[str, Any]],
    menu: list[dict[str, Any]],
) -> dict[str, Any]:
    """Select an investigation *before* taking an action; no forced winner."""
    public = project_public(observation)
    if (not isinstance(prior_events, list) or len(prior_events) > MAX_HISTORY
            or not isinstance(menu, list) or not 0 < len(menu) <= MAX_MENU):
        raise ValueError("invalid investigation capacity")
    if len({command_key(c) for c in menu}) != len(menu):
        raise ValueError("duplicate public command")
    rankings = []
    for candidate in menu:
        expected = forecast(public, candidate, prior_events)
        prob = expected["probabilities"]
        entropy = -sum(p * math.log(p) for p in prob.values() if p > 0)
        entropy /= math.log(len(OUTCOMES))
        local_n = expected["local_samples"]
        family_n = expected["family_samples"]
        # The objective is *uncertainty about usable public effects*, not
        # reaching a specific object, direction, puzzle key or score.
        information_opportunity = (
            0.60 * entropy
            + 0.30 / math.sqrt(1 + local_n)
            + 0.10 / math.sqrt(1 + family_n)
        )
        # Repeated observed failures are counted, not suppressed or relabeled.
        redundant = (expected["local_blocked"] + expected["local_no_effect"])
        score = information_opportunity / (1 + 0.4 * redundant)
        tie = _digest([public, command_key(candidate)])
        rankings.append((score, tie, deepcopy(candidate), expected))
    # The digest breaks ties without favoring compass order or a known solution.
    score, _, command, expected = min(rankings, key=lambda r: (-r[0], r[1]))
    return {
        "version": VERSION,
        "owner_id": f"INV{len(prior_events) + 1:06d}",
        "question": "What observable effect follows this bounded public action?",
        "command": command,
        "forecast": expected,
        "selection_score": round(score, 12),
        "available_commands": len(menu),
        "history_length": len(prior_events),
        "public_hash": _digest(public),
        "policy": "empirical-uncertainty-with-repeat-cost-v1",
    }


def brier(prediction: dict[str, float], actual: str) -> float:
    if actual not in OUTCOMES:
        raise ValueError("unknown outcome")
    if set(prediction) != set(OUTCOMES) or abs(sum(prediction.values()) - 1) > 1e-8:
        raise ValueError("invalid frozen probability distribution")
    if any(not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0 or p > 1
           for p in prediction.values()):
        raise ValueError("invalid probability")
    return sum((prediction[o] - (1 if o == actual else 0)) ** 2 for o in OUTCOMES)


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(events)
    kinds = Counter(row["outcome_kind"] for row in events)
    predicted = [
        brier(row["selection"]["forecast"]["probabilities"], row["outcome_kind"])
        for row in events
    ]
    uniform = 1 - 1 / len(OUTCOMES)
    return {
        "events": total,
        "outcomes": {kind: kinds[kind] for kind in OUTCOMES},
        "owned_actions": total,
        "unique_public_contexts": len({_digest(project_public(e["public_before"])) for e in events}),
        "mean_prequential_brier": round(sum(predicted) / total, 8) if total else None,
        "uniform_brier": round(uniform, 8),
        "forecast_improves_on_uniform": bool(total and sum(predicted) / total < uniform),
        "interpretation": (
            "Forecast scores compare to an untrained uniform predictor only. "
            "They do not establish useful goal progress, open-ended learning, "
            "reproduction, consciousness, or an independent organism."
        ),
    }
