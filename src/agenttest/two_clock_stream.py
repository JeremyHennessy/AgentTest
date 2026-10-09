"""Full-history, multiple-reversal two-clock observation memory.

All logic is derived from earlier public before/action/after receipts.
This module must not import world physics, private goals or phase test labels.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from typing import Any

from .two_clock_memory import ACTIONS, DELTAS, _normalize, _context

VERSION = "original-ora-two-clock-stream-v2"
WORLD = "bounded-stateful-world-v1"
MAX_EVENTS = 32768
MAX_CAPSULE_BYTES = 16 * 1024 * 1024
ALPHA = 0.5
LIFETIME_STRENGTH = 3.0
RECENT_STRENGTH = 1.5
MIN_PRIOR_LOCAL = 4
MIN_CONTRADICTIONS = 2
MIN_DOMINANCE = 0.80


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _prob(count: Counter, size: int) -> dict[str, float]:
    return {d: (count[d] + ALPHA) / (size + len(DELTAS) * ALPHA)
            for d in DELTAS}


def _mode(count: Counter) -> str:
    return max(DELTAS, key=lambda d: (count[d], -DELTAS.index(d)))


class TwoClockStream:
    """Append-only indexed predictions; no self-directed action execution."""

    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        self.events: list[dict[str, Any]] = []
        self.known: set[str] = set()
        self.action_totals: dict[str, int] = defaultdict(int)
        self.action_counts: dict[str, Counter] = defaultdict(Counter)
        self.context_totals: dict[str, int] = defaultdict(int)
        self.context_counts: dict[str, Counter] = defaultdict(Counter)
        self.active_totals: dict[str, int] = defaultdict(int)
        self.active_counts: dict[str, Counter] = defaultdict(Counter)
        self.active_recent: dict[str, list[dict]] = defaultdict(list)
        self.markers: dict[str, list[dict]] = defaultdict(list)
        for event in events or []:
            self.observe(event)

    def observe(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        if len(self.events) >= MAX_EVENTS:
            raise ValueError("indexed memory capacity exceeded; refusing evidence loss")
        row = _normalize(raw)
        if row["index"] != len(self.events) + 1:
            raise ValueError("invalid source observation sequence")
        if row["id"] in self.known:
            raise ValueError("replayed duplicate original source observation")
        if not isinstance(row["delta"], str) or row["delta"] not in DELTAS:
            raise ValueError("unsupported public effect")
        context = _context(row["before"], row["action"])
        action, delta = row["action"], row["delta"]
        # Counters and indexes always derive from an already validated event.
        self.events.append(row)
        self.known.add(row["id"])
        self.action_totals[action] += 1
        self.action_counts[action][delta] += 1
        self.context_totals[context] += 1
        self.context_counts[context][delta] += 1
        self.active_totals[context] += 1
        self.active_counts[context][delta] += 1

        # Only the last two of the active segment are needed to identify a new
        # pair of agreeing, disagreeing outcomes; all records stay in events.
        tail = self.active_recent[context]
        tail.append(row)
        if len(tail) > MIN_CONTRADICTIONS:
            del tail[0]
        if self.active_totals[context] < MIN_PRIOR_LOCAL + MIN_CONTRADICTIONS:
            return []
        if tail[0]["delta"] != tail[1]["delta"]:
            return []
        old = self.active_counts[context].copy()
        for recent in tail:
            old[recent["delta"]] -= 1
        older_n = self.active_totals[context] - MIN_CONTRADICTIONS
        dominant = _mode(old)
        new_kind = tail[0]["delta"]
        if old[dominant] / older_n < MIN_DOMINANCE or new_kind == dominant:
            return []
        marker = {
            "context": context,
            "start_index": tail[0]["index"],
            "confirmation_index": tail[1]["index"],
            "prior_modal": dominant,
            "recent_modal": new_kind,
            "prior_count": older_n,
            "evidence_ids": [tail[0]["id"], tail[1]["id"]],
            "marker_number": len(self.markers[context]) + 1,
        }
        if len(self.markers[context]) >= MAX_EVENTS // 6:
            raise ValueError("unbounded local-marker history")
        self.markers[context].append(marker)
        # Crucial difference from v1: this active segment now has its OWN
        # counters. Another genuine reversal can be detected in this SAME
        # continuously inherited memory only after enough subsequent evidence.
        self.active_counts[context] = Counter(r["delta"] for r in tail)
        self.active_totals[context] = len(tail)
        return [deepcopy(marker)]

    def predict(self, before: list[int], action: str, *, arm: str) -> dict[str, Any]:
        from .two_clock_memory import _position
        location = _position(before)
        if action not in ACTIONS or arm not in {
            "two_clock", "lifetime", "action", "uniform"
        }:
            raise ValueError("unknown public prediction arm")
        context = _context(location, action)
        family = _prob(self.action_counts[action], self.action_totals[action])
        markers = self.markers.get(context, [])
        if arm == "uniform":
            probabilities = {d: 1.0 / len(DELTAS) for d in DELTAS}
            basis = "uniform"
        elif arm == "action":
            probabilities = family
            basis = "action"
        elif arm == "two_clock" and markers:
            local_n = self.active_totals[context]
            local_counts = self.active_counts[context]
            probabilities = {
                d: (local_counts[d] + RECENT_STRENGTH * family[d])
                / (local_n + RECENT_STRENGTH)
                for d in DELTAS
            }
            basis = "confirmed_local_reversal"
        else:
            local_n = self.context_totals[context]
            local_counts = self.context_counts[context]
            probabilities = {
                d: (local_counts[d] + LIFETIME_STRENGTH * family[d])
                / (local_n + LIFETIME_STRENGTH)
                for d in DELTAS
            }
            basis = "full_lifetime_local"
        if (any(not math.isfinite(p) or p <= 0 or p > 1
                for p in probabilities.values())
                or abs(sum(probabilities.values()) - 1.0) > 1e-10):
            raise ValueError("unverifiable indexed-memory forecast")
        dominant = max(DELTAS, key=lambda d: (probabilities[d], -DELTAS.index(d)))
        return {
            "version": VERSION, "arm": arm, "before": location, "action": action,
            "distribution": probabilities, "predicted_delta": dominant,
            "lifetime_rows": len(self.events),
            "action_rows": self.action_totals[action],
            "local_rows": self.context_totals[context],
            "active_rows": self.active_totals[context],
            "basis": basis,
            "change_marker_count": len(markers),
            "latest_change_marker": deepcopy(markers[-1]) if markers else None,
        }

    def capsule(self) -> bytes:
        body = {"version": VERSION, "world": WORLD, "events": self.events}
        payload = _json({"body": body, "sha256": digest(body)})
        if len(payload) > MAX_CAPSULE_BYTES:
            raise ValueError("bounded lossless memory capsule is too large")
        return payload

    @classmethod
    def from_capsule(cls, raw: bytes) -> "TwoClockStream":
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_CAPSULE_BYTES:
            raise ValueError("invalid original evidence memory capsule size")
        try:
            document = json.loads(raw)
        except (TypeError, UnicodeError, ValueError) as exc:
            raise ValueError("corrupt encoded original evidence memory") from exc
        if (not isinstance(document, dict) or set(document) != {"body", "sha256"}
                or not isinstance(document["body"], dict)
                or set(document["body"]) != {"version", "world", "events"}):
            raise ValueError("invalid original evidence memory envelope")
        body = document["body"]
        if (body["version"] != VERSION or body["world"] != WORLD
                or type(document["sha256"]) is not str
                or document["sha256"] != digest(body)
                or not isinstance(body["events"], list)):
            raise ValueError("original memory envelope does not match its source")
        rebuilt = cls(body["events"])
        if rebuilt.capsule() != raw:
            raise ValueError("noncanonical original memory evidence serialization")
        return rebuilt


def brier(prediction: dict[str, Any], actual: str) -> dict[str, Any]:
    if actual not in DELTAS or not isinstance(prediction, dict):
        raise ValueError("unsupported measured public movement")
    probabilities = prediction.get("distribution")
    if not isinstance(probabilities, dict) or set(probabilities) != set(DELTAS):
        raise ValueError("unknown prior predictive distribution")
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
           for x in probabilities.values()):
        raise ValueError("invalid prior forecast probabilities")
    if abs(sum(probabilities.values()) - 1) > 1e-10:
        raise ValueError("incorrect prior probability sum")
    return {
        "brier": sum((probabilities[d] - (1.0 if d == actual else 0.0)) ** 2
                     for d in DELTAS),
        "logloss": -math.log(probabilities[actual]),
        "hit": prediction["predicted_delta"] == actual,
        "actual_probability": probabilities[actual],
    }
