"""Two-timescale falsification candidate: retain lifetime evidence, revise local view.

This module is a pure, bounded statistical reader of public position/action and
past observed delta. No world physics, switch regime, planner, evaluator,
hidden map, or externally assigned goal is imported into its decisions.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from typing import Any

VERSION = "ora-two-clock-reversible-memory-v1"
ACTIONS = ("north", "east", "south", "west")
DELTAS = ("0,0", "1,0", "-1,0", "0,1", "0,-1")
ALPHA = 0.5
LIFETIME_LOCAL_STRENGTH = 3.0
RECENT_LOCAL_STRENGTH = 1.5
MAX_EVENTS = 4096


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _position(value: Any) -> list[int]:
    if (not isinstance(value, list) or len(value) != 2
            or any(type(x) is not int or not -2 <= x <= 2 for x in value)):
        raise ValueError("invalid public five-by-five position")
    return list(value)


def _normalize(value: dict) -> dict:
    fields = {"id", "index", "before", "action", "after"}
    if not isinstance(value, dict) or set(value) not in (fields, fields | {"delta"}):
        raise ValueError("invalid public transition row")
    identifier = value["id"]
    if (not isinstance(identifier, str) or not 0 < len(identifier) <= 96
            or any(c in identifier for c in "\r\n\t")):
        raise ValueError("invalid observation identity")
    index = value["index"]
    if type(index) is not int or index < 1:
        raise ValueError("invalid evidence index")
    if value["action"] not in ACTIONS:
        raise ValueError("invalid public action")
    before = _position(value["before"])
    after = _position(value["after"])
    delta = f"{after[0]-before[0]},{after[1]-before[1]}"
    if delta not in DELTAS:
        raise ValueError("invalid one-step-or-still displacement")
    if "delta" in value and value["delta"] != delta:
        raise ValueError("recorded delta contradicts its observed positions")
    return {
        "id": identifier, "index": index, "before": before,
        "action": value["action"], "after": after, "delta": delta,
    }


def _context(position: list[int], action: str) -> str:
    return f"{position[0]},{position[1]}|{action}"


def _mode(counts: Counter) -> str:
    return max(DELTAS, key=lambda d: (counts[d], -DELTAS.index(d)))


def _prob(counts: Counter, n: int) -> dict[str, float]:
    return {delta: (counts[delta] + ALPHA) / (n + ALPHA * len(DELTAS))
            for delta in DELTAS}


class TwoClockMemory:
    def __init__(self, events: list[dict] | None = None) -> None:
        self.events: list[dict] = []
        self.known_ids: set[str] = set()
        self.markers: dict[str, dict] = {}
        self.contexts: dict[str, list[dict]] = {}
        for event in events or []:
            self.observe(event)

    def observe(self, raw: dict) -> list[dict]:
        if len(self.events) >= MAX_EVENTS:
            raise ValueError("memory storage bound exhausted; no silent evidence deletion")
        event = _normalize(raw)
        if event["index"] != len(self.events) + 1:
            raise ValueError("non-monotonic evidence index")
        if event["id"] in self.known_ids:
            raise ValueError("duplicate source evidence")
        self.events.append(event)
        self.known_ids.add(event["id"])
        context = _context(event["before"], event["action"])
        observations = self.contexts.setdefault(context, [])
        observations.append(event)
        if context not in self.markers and len(observations) >= 6:
            earlier = observations[:-2]
            newest = observations[-2:]
            counts = Counter(item["delta"] for item in earlier)
            dominant = _mode(counts)
            if (counts[dominant] / len(earlier) >= 0.80
                    and newest[0]["delta"] == newest[1]["delta"]
                    and newest[0]["delta"] != dominant):
                self.markers[context] = {
                    "context": context,
                    "start_index": newest[0]["index"],
                    "confirmation_index": newest[1]["index"],
                    "prior_modal": dominant,
                    "recent_modal": newest[0]["delta"],
                    "prior_count": len(earlier),
                    "evidence_ids": [newest[0]["id"], newest[1]["id"]],
                }
        return [deepcopy(self.markers[context])] if (
            context in self.markers
            and self.markers[context]["confirmation_index"] == event["index"]
        ) else []

    def predict(self, before: list[int], action: str, *, arm: str) -> dict:
        position = _position(before)
        if action not in ACTIONS or arm not in {
            "lifetime", "two_clock", "action", "uniform",
        }:
            raise ValueError("unapproved public model arm")
        family = [r for r in self.events if r["action"] == action]
        fc = Counter(r["delta"] for r in family)
        family_prob = _prob(fc, len(family))
        context = _context(position, action)
        local = self.contexts.get(context, [])
        lc = Counter(r["delta"] for r in local)
        if arm == "uniform":
            probs = {d: 1.0 / len(DELTAS) for d in DELTAS}
            basis = "uniform"
        elif arm == "action":
            probs = family_prob
            basis = "historical_action"
        else:
            strength = LIFETIME_LOCAL_STRENGTH
            seen = local
            basis = "lifetime_local"
            if arm == "two_clock" and context in self.markers:
                marker = self.markers[context]
                seen = [r for r in local if r["index"] >= marker["start_index"]]
                lc = Counter(r["delta"] for r in seen)
                strength = RECENT_LOCAL_STRENGTH
                basis = "confirmed_local_change"
            probs = {
                d: (lc[d] + strength * family_prob[d]) / (len(seen) + strength)
                for d in DELTAS
            }
        if any(not 0 < p <= 1 or not math.isfinite(p) for p in probs.values()):
            raise ValueError("invalid predictive distribution")
        if abs(sum(probs.values()) - 1.0) > 1e-10:
            raise ValueError("non-normalized predictive distribution")
        best = max(DELTAS, key=lambda d: (probs[d], -DELTAS.index(d)))
        return {
            "version": VERSION,
            "arm": arm,
            "before": position,
            "action": action,
            "distribution": probs,
            "predicted_delta": best,
            "lifetime_count": len(self.events),
            "action_count": len(family),
            "local_count": len(local),
            "active_local_marker": deepcopy(self.markers.get(context)),
            "basis": basis,
        }

    def dump(self) -> bytes:
        body = {"version": VERSION, "events": self.events}
        return canonical({"body": body, "sha256": sha(body)})

    @classmethod
    def load(cls, data: bytes) -> "TwoClockMemory":
        if not isinstance(data, bytes) or len(data) > 2 * 1024 * 1024:
            raise ValueError("invalid bounded two-clock checkpoint")
        try:
            document = json.loads(data)
        except (TypeError, UnicodeError, ValueError) as exc:
            raise ValueError("unreadable two-clock checkpoint") from exc
        if (not isinstance(document, dict) or set(document) != {"body", "sha256"}
                or not isinstance(document["body"], dict)
                or set(document["body"]) != {"version", "events"}
                or document["body"]["version"] != VERSION
                or document["sha256"] != sha(document["body"])):
            raise ValueError("two-clock checkpoint integrity failure")
        if not isinstance(document["body"]["events"], list):
            raise ValueError("invalid checkpoint event list")
        result = cls(document["body"]["events"])
        if result.dump() != data:
            raise ValueError("noncanonical source checkpoint")
        return result


def scored(prediction: dict, observed: str) -> dict:
    if observed not in DELTAS:
        raise ValueError("unknown private scored outcome")
    probs = prediction["distribution"]
    if set(probs) != set(DELTAS) or abs(sum(probs.values()) - 1) > 1e-10:
        raise ValueError("invalid frozen predictor output")
    return {
        "brier": sum((probs[d] - (1 if d == observed else 0)) ** 2 for d in DELTAS),
        "logloss": -math.log(probs[observed]),
        "hit": prediction["predicted_delta"] == observed,
    }
