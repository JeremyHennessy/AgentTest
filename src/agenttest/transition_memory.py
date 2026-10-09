"""Source-grounded transition memory for Ora's existing bounded world.

This inference module knows no world transition rules, hidden action deltas,
planner goals, research labels, or artificial success criteria. Every prediction
is formed from *earlier* public observations and authored five-outcome support.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from typing import Any

VERSION = "original-ora-transition-memory-v1"
WORLD = "bounded-stateful-world-v1"
ACTIONS = ("north", "east", "south", "west")
DELTAS = ("0,0", "1,0", "-1,0", "0,1", "0,-1")
ALPHA = 0.5
LOCAL_STRENGTH = 3.0
MAX_ROWS = 4096
_MIN_PROB = 1e-300


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _position(value: Any) -> list[int]:
    if (not isinstance(value, list) or len(value) != 2
            or any(type(x) is not int or x < -2 or x > 2 for x in value)):
        raise ValueError("only a public 5x5 integer position is admitted")
    return list(value)


def delta_key(before: Any, after: Any) -> str:
    b = _position(before)
    a = _position(after)
    key = f"{a[0] - b[0]},{a[1] - b[1]}"
    if key not in DELTAS:
        raise ValueError("unrecognized one-step-or-blocked observed displacement")
    return key


def normalize(row: dict[str, Any]) -> dict[str, Any]:
    fields = {"id", "index", "before", "action", "after", "world_version"}
    if not isinstance(row, dict) or set(row) not in (fields, fields | {"delta"}):
        raise ValueError("transition-memory event fields do not match schema")
    identifier = row["id"]
    if (not isinstance(identifier, str) or not 0 < len(identifier) <= 160
            or any(c in identifier for c in "\n\r\t")):
        raise ValueError("invalid original event identity")
    if type(row["index"]) is not int or row["index"] < 1:
        raise ValueError("invalid observation index")
    if row["world_version"] != WORLD:
        raise ValueError("incompatible original world")
    if row["action"] not in ACTIONS:
        raise ValueError("action not in public original-world command grammar")
    before, after = _position(row["before"]), _position(row["after"])
    delta = delta_key(before, after)
    if "delta" in row and row["delta"] != delta:
        raise ValueError("stored delta contradicts public before/after evidence")
    return {
        "id": identifier,
        "index": row["index"],
        "before": before,
        "action": row["action"],
        "after": after,
        "delta": delta,
        "world_version": WORLD,
    }


def _prob(counts: Counter, n: int) -> dict[str, float]:
    return {label: (counts[label] + ALPHA) / (n + len(DELTAS) * ALPHA)
            for label in DELTAS}


def _context(position: list[int], action: str) -> tuple[int, int, str]:
    return position[0], position[1], action


class TransitionMemory:
    """Append-only, bounded, exact-index evidence with cold-reload checks."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows: list[dict[str, Any]] = []
        self._known: set[str] = set()
        for row in rows or []:
            self.add(row)

    @property
    def length(self) -> int:
        return len(self._rows)

    @property
    def rows(self) -> list[dict[str, Any]]:
        return deepcopy(self._rows)

    def add(self, row: dict[str, Any]) -> None:
        if len(self._rows) >= MAX_ROWS:
            raise ValueError("evidence memory budget exhausted; no automatic truncation")
        event = normalize(row)
        if event["index"] != len(self._rows) + 1:
            raise ValueError("out-of-order, skipped, or replayed evidence index")
        if event["id"] in self._known:
            raise ValueError("duplicate original evidence identity")
        self._rows.append(event)
        self._known.add(event["id"])

    def _counts(self, before: list[int], action: str) -> tuple[Counter, Counter, Counter, int, int]:
        overall, family, local = Counter(), Counter(), Counter()
        familyn = localn = 0
        context = _context(before, action)
        for item in self._rows:
            label = item["delta"]
            overall[label] += 1
            if item["action"] == action:
                family[label] += 1
                familyn += 1
                if _context(item["before"], item["action"]) == context:
                    local[label] += 1
                    localn += 1
        return overall, family, local, familyn, localn

    def forecast(
        self, before: list[int], action: str, *, arm: str = "hier",
    ) -> dict[str, Any]:
        position = _position(before)
        if action not in ACTIONS:
            raise ValueError("not a permitted original-world action")
        if arm not in {"hier", "family", "global", "uniform"}:
            raise ValueError("unknown predeclared model arm")
        overall, family, local, familyn, localn = self._counts(position, action)
        if arm == "uniform":
            probabilities = {outcome: 1.0 / len(DELTAS) for outcome in DELTAS}
        elif arm == "global":
            probabilities = _prob(overall, len(self._rows))
        else:
            family_probs = _prob(family, familyn)
            if arm == "family" or localn == 0:
                probabilities = family_probs
            else:
                probabilities = {
                    label: (local[label] + LOCAL_STRENGTH * family_probs[label])
                    / (localn + LOCAL_STRENGTH)
                    for label in DELTAS
                }
        if any(p <= 0 or not math.isfinite(p) for p in probabilities.values()):
            raise ValueError("invalid predicted probability")
        if abs(sum(probabilities.values()) - 1) > 1e-10:
            raise ValueError("forecast probabilities are not normalized")
        modal = max(DELTAS, key=lambda o: (probabilities[o], -DELTAS.index(o)))
        return {
            "version": VERSION,
            "arm": arm,
            "evidence_count": len(self._rows),
            "family_count": familyn,
            "local_count": localn,
            "before": position,
            "action": action,
            "distribution": probabilities,
            "predicted_delta": modal,
            "source_chain_hash": digest(self._rows),
        }

    def export(self) -> bytes:
        body = {"version": VERSION, "world_version": WORLD, "rows": self._rows}
        return _json({"body": body, "sha256": digest(body)})

    @classmethod
    def restore(cls, blob: bytes) -> "TransitionMemory":
        if not isinstance(blob, bytes) or len(blob) > 5 * 1024 * 1024:
            raise ValueError("invalid persisted evidence capsule size")
        try:
            value = json.loads(blob)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("invalid persisted evidence serialization") from exc
        if not isinstance(value, dict) or set(value) != {"body", "sha256"}:
            raise ValueError("invalid evidence envelope")
        body = value["body"]
        if (not isinstance(body, dict) or set(body) != {"version", "world_version", "rows"}
                or body.get("version") != VERSION or body.get("world_version") != WORLD
                or value["sha256"] != digest(body)):
            raise ValueError("evidence envelope source or hash mismatch")
        if not isinstance(body["rows"], list):
            raise ValueError("invalid evidence body rows")
        return cls(body["rows"])


def score(prediction: dict[str, Any], observed: str) -> dict[str, float | bool]:
    if observed not in DELTAS:
        raise ValueError("unsupported observed displacement")
    distribution = prediction.get("distribution")
    if not isinstance(distribution, dict) or set(distribution) != set(DELTAS):
        raise ValueError("unverifiable distribution")
    if any(type(v) not in (float, int) or v <= 0 or not math.isfinite(v)
           for v in distribution.values()):
        raise ValueError("invalid probability")
    if abs(sum(distribution.values()) - 1) > 1e-10:
        raise ValueError("probability mass mismatch")
    return {
        "brier": sum((distribution[v] - (1.0 if v == observed else 0)) ** 2
                     for v in DELTAS),
        "logloss": -math.log(max(distribution[observed], _MIN_PROB)),
        "hit": prediction["predicted_delta"] == observed,
        "blocked_brier": (distribution["0,0"] - (1.0 if observed == "0,0" else 0.0)) ** 2,
    }


def _rotated_row(item: dict[str, Any]) -> dict[str, Any]:
    """Negative control: intentionally misattribute a historical action label."""
    shifted = deepcopy(item)
    shifted.pop("delta", None)
    shift = (item["index"] % 3) + 1
    shifted["action"] = ACTIONS[(ACTIONS.index(item["action"]) + shift) % len(ACTIONS)]
    return shifted


def _base_row(item: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(item[key]) for key in (
        "id", "index", "before", "action", "after", "world_version",
    )}


def evaluate_history(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The predeclared chronological, non-causal matched natural-action study."""
    if not isinstance(rows, list):
        raise ValueError("study input must be complete chronological records")
    normalized = TransitionMemory(rows).rows
    count = len(normalized)
    if count < 80:
        return {
            "status": "INSUFFICIENT", "eligible_rows": count,
            "reason": "fewer_than_80_authentic_compatible_original_actions",
        }
    heldout = min(64, max(24, count // 5))
    train = count - heldout
    models = {
        "HIER-1": TransitionMemory(),
        "FAM-1": TransitionMemory(),
        "FROZEN-1": TransitionMemory(),
        "GLOBAL-1": TransitionMemory(),
        "UNIFORM-1": TransitionMemory(),
        "SHUFFLED-1": TransitionMemory(),
    }
    for item in normalized[:train]:
        for name, model in models.items():
            model.add(_rotated_row(item) if name == "SHUFFLED-1" else _base_row(item))
    arms = {
        "HIER-1": "hier", "FAM-1": "family", "FROZEN-1": "family",
        "GLOBAL-1": "global", "UNIFORM-1": "uniform", "SHUFFLED-1": "hier",
    }
    scores: dict[str, list[dict[str, float | bool]]] = {name: [] for name in arms}
    per_action: list[dict[str, Any]] = []
    local_evidence = 0
    for item in normalized[train:]:
        before, action, observed = item["before"], item["action"], item["delta"]
        forecasts = {
            name: models[name].forecast(before, action, arm=mode)
            for name, mode in arms.items()
        }
        local_evidence += int(forecasts["HIER-1"]["local_count"] > 0)
        record = {
            "id": item["id"],
            "index": item["index"],
            "action": action,
            "observed_delta": observed,
            "frozen_predictions": {},
        }
        for name, prediction in forecasts.items():
            row_score = score(prediction, observed)
            scores[name].append(row_score)
            record["frozen_predictions"][name] = {
                "predicted_delta": prediction["predicted_delta"],
                "actual_outcome_probability": prediction["distribution"][observed],
                "family_count": prediction["family_count"],
                "local_count": prediction["local_count"],
                "brier": row_score["brier"],
                "logloss": row_score["logloss"],
            }
        per_action.append(record)
        for name, model in models.items():
            if name != "FROZEN-1":
                model.add(_rotated_row(item) if name == "SHUFFLED-1" else _base_row(item))
    metrics = {}
    for name, recorded in scores.items():
        divisor = len(recorded)
        metrics[name] = {
            "mean_multiclass_brier": round(
                sum(float(r["brier"]) for r in recorded) / divisor, 9
            ),
            "mean_logloss": round(
                sum(float(r["logloss"]) for r in recorded) / divisor, 9
            ),
            "exact_delta_hit_rate": round(
                sum(bool(r["hit"]) for r in recorded) / divisor, 9
            ),
            "blocked_brier": round(
                sum(float(r["blocked_brier"]) for r in recorded) / divisor, 9
            ),
            "evaluated": divisor,
        }
    difference = metrics["FAM-1"]["mean_multiclass_brier"] - metrics["HIER-1"]["mean_multiclass_brier"]
    return {
        "version": VERSION,
        "study": "original-ora-chronological-transition-memory-001",
        "status": "candidate_improves_over_family" if difference > 0 else "candidate_no_gain",
        "status_scope": "descriptive_one_dependent_older_behavior_series",
        "total_compatible_rows": count,
        "training_rows": train,
        "evaluation_rows": heldout,
        "first_evaluation_id": normalized[train]["id"],
        "last_evaluation_id": normalized[-1]["id"],
        "original_input_digest": digest(normalized),
        "candidate_local_evidence_forecasts": local_evidence,
        "metrics": metrics,
        "family_minus_candidate_brier": round(difference, 9),
        "per_action": per_action,
        "limits": [
            "One dependent series of old naturally chosen actions is not independent validation or causal behavior improvement.",
            "Fixed five-delta support and 5x5 positions are authored premises, not evolved world understanding.",
            "The heldout suffix is retrospective; selection/history interventions cannot be randomized after the fact.",
            "Action-label shuffling is a negative sensitivity check, not a complete causal counterfactual.",
            "Source preservation and software integrity are not evidence of consciousness or autonomous life.",
        ],
    }
