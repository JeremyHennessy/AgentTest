"""Isolated copied-world challenge substrate; no runtime/controller integration.

The evaluator supplies seeds. Learners receive only public_view() and the
realized action evidence, not barriers, rules, switch times or rewards.
This is a candidate test environment, not Ora's existing world or live organism.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random
from typing import Iterable

VERSION = "ora2-blind-context-copied-world-v1"
ACTIONS = ("token-a", "token-b", "token-c", "token-d")
BOUNDS = 2
MAX_BUDGET = 64
GENESIS = "0" * 64
_MOVES = ((1, 0), (-1, 0), (0, 1), (0, -1))


class InvalidWorldEvidence(ValueError):
    """Reject invalid provenance, illegal actions and counterfeit replays."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class StepReceipt:
    """Only realized action consequences, with an auditable predecessor link."""
    version: str
    stream_id: str
    index: int
    before: tuple[int, int]
    action: str
    after: tuple[int, int]
    blocked: bool
    predecessor: str
    digest: str

    def evidence(self) -> dict:
        """Provenance for a future forecaster; contains no hidden parameters."""
        return {
            "world_version": self.version,
            "cycle": self.index,
            "source": "blind_context_copied_world:" + self.stream_id,
            "source_id": self.digest,
            "before": list(self.before),
            "action": self.action,
            "after": list(self.after),
            "blocked": self.blocked,
        }


class BlindContextWorld:
    """Seed-varied world with hidden barriers and one hidden rule change.

    There are no goals, puzzles, authored solutions or reward labels. Actions
    are opaque names whose physical effects vary by copied world and regime.
    A future study must hold this *world object* in its evaluator, not hand it
    to the learning policy (which could introspect private Python attributes).
    """

    def __init__(self, *, seed: int, stream_id: str, budget: int = MAX_BUDGET):
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise InvalidWorldEvidence("bounded integer evaluator seed required")
        if (type(stream_id) is not str or len(stream_id) != 32 or
                any(c not in "0123456789abcdef" for c in stream_id)):
            raise InvalidWorldEvidence("opaque evaluator stream id must be 128-bit lowercase hex")
        if type(budget) is not int or not 1 <= budget <= MAX_BUDGET:
            raise InvalidWorldEvidence("bounded finite action budget required")
        self._budget = budget
        self._seed = seed
        self._stream_id = stream_id
        rng = random.Random(seed)
        first = list(_MOVES)
        rng.shuffle(first)
        second = first.copy()
        a, b = rng.sample(range(len(ACTIONS)), 2)
        second[a], second[b] = second[b], second[a]
        self._rules = (dict(zip(ACTIONS, first)), dict(zip(ACTIONS, second)))
        candidates = [(x, y) for x in range(-BOUNDS, BOUNDS + 1)
                      for y in range(-BOUNDS, BOUNDS + 1)
                      if (x, y) != (0, 0)]
        early = set(rng.sample(candidates, rng.randint(2, 4)))
        late = early.copy()
        outgoing = rng.choice(sorted(late))
        incoming = rng.choice(sorted(set(candidates) - late))
        late.remove(outgoing)
        late.add(incoming)
        self._barriers = (frozenset(early), frozenset(late))
        self._change_at = rng.randint(24, 40)
        self._where = (0, 0)
        self._receipts: list[StepReceipt] = []

    def public_view(self) -> dict:
        """Only these fields may reach an autonomous decision-maker."""
        return {
            "world_version": VERSION,
            "position": list(self._where),
            "available_actions": list(ACTIONS),
            "steps_completed": len(self._receipts),
            "remaining_budget": self._budget - len(self._receipts),
        }

    def step(self, action: str) -> StepReceipt:
        if type(action) is not str or action not in ACTIONS:
            raise InvalidWorldEvidence("action not in public opaque menu")
        index = len(self._receipts) + 1
        if index > self._budget:
            raise InvalidWorldEvidence("finite copied-world budget exhausted")
        regime = int(index >= self._change_at)
        delta = self._rules[regime][action]
        before = self._where
        target = (before[0] + delta[0], before[1] + delta[1])
        blocked = (any(not -BOUNDS <= c <= BOUNDS for c in target)
                   or target in self._barriers[regime])
        after = before if blocked else target
        predecessor = self._receipts[-1].digest if self._receipts else GENESIS
        fields = {"version": VERSION, "stream_id": self._stream_id,
                  "index": index, "before": list(before),
                  "action": action, "after": list(after), "blocked": blocked,
                  "predecessor": predecessor}
        digest = hashlib.sha256(_canonical(fields)).hexdigest()
        receipt = StepReceipt(VERSION, self._stream_id, index, before, action, after, blocked,
                              predecessor, digest)
        self._where = after
        self._receipts.append(receipt)
        return receipt

    def recorded(self) -> tuple[StepReceipt, ...]:
        return tuple(self._receipts)

    @classmethod
    def reconstruct(cls, *, seed: int, stream_id: str, receipts: Iterable[StepReceipt],
                    budget: int = MAX_BUDGET) -> "BlindContextWorld":
        """Independently replay and validate each source-linked consequence."""
        world = cls(seed=seed, stream_id=stream_id, budget=budget)
        for recorded in receipts:
            if type(recorded) is not StepReceipt:
                raise InvalidWorldEvidence("unsupported external receipt shape")
            if world.step(recorded.action) != recorded:
                raise InvalidWorldEvidence("copied-world replay mismatch")
        return world
