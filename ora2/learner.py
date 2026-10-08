"""An original implementation of sequence-conditioned predictive learning.

No existing Ora module, question catalogue, movement grammar, simulator, network,
or filesystem is imported. Public JSON observations and an allowed action menu
are the complete interface. This module recommends actions; it cannot execute one.

A bank of suffix predictors learns from chronologically observed transitions.
Their weights change by their own prospective prediction errors. Action choice
uses measured improvement in prediction, with a declared exploration reserve.
Neither a phase number nor a resumption count exists in the decision procedure.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from typing import Any

VERSION = 'ora2-temporal-0.1'


class ProtocolError(ValueError):
    """Input is ambiguous or does not match the one outstanding decision."""


class CapacityError(RuntimeError):
    """A declared bound was reached; existing experience is not deleted."""


@dataclass(frozen=True)
class Config:
    max_depth: int = 4
    progress_window: int = 12
    exploration: float = 0.15
    max_steps: int = 10000
    max_symbols: int = 2048
    max_contexts: int = 100000
    max_actions: int = 32
    max_observation_bytes: int = 2048

    def __post_init__(self) -> None:
        ranges = {
            'max_depth': (0, 8), 'progress_window': (2, 128),
            'max_steps': (1, 100000), 'max_symbols': (2, 8192),
            'max_contexts': (1, 1000000), 'max_actions': (1, 64),
            'max_observation_bytes': (16, 16384),
        }
        for field, (low, high) in ranges.items():
            value = getattr(self, field)
            if type(value) is not int or not low <= value <= high:
                raise ProtocolError(f'invalid {field}')
        if type(self.exploration) not in (int, float) or not 0 < self.exploration <= 1:
            raise ProtocolError('exploration must be finite and in (0, 1]')


def canonical(value: Any, byte_limit: int = 16384) -> str:
    """Lossless for supported JSON; missing keys and explicit null stay distinct."""
    def check(v: Any, depth: int = 0) -> None:
        if depth > 12:
            raise ProtocolError('observation nesting limit')
        if v is None or type(v) in (bool, int, str):
            return
        if type(v) is float and math.isfinite(v):
            return
        if type(v) is list:
            for x in v:
                check(x, depth + 1)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for x in v.values():
                check(x, depth + 1)
            return
        raise ProtocolError('observation is not finite materialized JSON')
    check(value)
    try:
        text = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        size = len(text.encode('utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ProtocolError('invalid JSON encoding') from exc
    if size > byte_limit:
        raise CapacityError('observation byte limit')
    return text


@dataclass(frozen=True)
class Forecast:
    # JSON-encoded observed symbols cannot collide with the separate unseen mass.
    known: tuple[tuple[str, float], ...]
    unseen: float
    depth_weights: tuple[float, ...]

    def probability(self, encoded_observation: str) -> float:
        return dict(self.known).get(encoded_observation, self.unseen)

    def public(self) -> dict[str, Any]:
        return {'known': [{'observation': json.loads(k), 'probability': v} for k, v in self.known],
                'unseen_probability': self.unseen, 'depth_weights': list(self.depth_weights)}


@dataclass(frozen=True)
class Choice:
    step: int
    action: str
    menu: tuple[str, ...]
    probabilities: tuple[float, ...]
    learning_progress: tuple[float, ...]
    reason: str
    forecast: Forecast

    def public(self) -> dict[str, Any]:
        return {'step': self.step, 'action': self.action, 'menu': list(self.menu),
                'action_probabilities': list(self.probabilities),
                'learning_progress': list(self.learning_progress), 'reason': self.reason,
                'forecast': self.forecast.public()}

    def record(self) -> dict[str, Any]:
        """Compact audit receipt; full forecasts are reconstructible from history."""
        result = self.public()
        forecast = result.pop('forecast')
        raw = json.dumps(forecast, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        result['forecast_sha256'] = hashlib.sha256(raw).hexdigest()
        result['depth_weights'] = list(self.forecast.depth_weights)
        result['unseen_probability'] = self.forecast.unseen
        return result


class Agent:
    """Bounded research learner. No import of legacy cognition or any actuator."""

    def __init__(self, observation: Any, *, config: Config | None = None, seed: int = 0):
        if type(seed) is not int:
            raise ProtocolError('seed must be an integer')
        if config is not None and type(config) is not Config:
            raise ProtocolError('configuration must be a Config')
        self.config = config or Config()
        self.initial_observation = canonical(observation, self.config.max_observation_bytes)
        self.observation = self.initial_observation
        self.seed = seed
        self.steps = 0
        self._random = random.Random(seed)
        self._history: deque[tuple[str, str]] = deque(maxlen=self.config.max_depth)
        self._symbols = {self.observation}
        self._tables: list[dict[tuple, Counter]] = [dict() for _ in range(self.config.max_depth + 1)]
        self._totals: list[dict[tuple, int]] = [dict() for _ in self._tables]
        self._log_weights: dict[str, list[float]] = {}
        self._action_counts: Counter = Counter()
        self._losses: dict[str, deque[float]] = {}
        self._pending: Choice | None = None

    def _contexts(self) -> tuple[tuple, ...]:
        past = tuple(self._history)
        # Start-of-life is represented by a shorter suffix, not invented events.
        return tuple((self.observation, past[-d:] if d else ())
                     for d in range(self.config.max_depth + 1))

    def _weights(self, action: str) -> tuple[float, ...]:
        logs = self._log_weights.get(action, [-d * math.log(2) for d in range(self.config.max_depth + 1)])
        top = max(logs)
        terms = [math.exp(v - top) for v in logs]
        total = math.fsum(terms)
        return tuple(v / total for v in terms)

    def _expert_probabilities(self, action: str, symbol: str | None) -> tuple[float, ...]:
        k = len(self._symbols) + 1  # one open-vocabulary mass, never future labels
        result = []
        for table, totals, context in zip(self._tables, self._totals, self._contexts()):
            counts = table.get((context, action), Counter())
            n = totals.get((context, action), 0)
            result.append((counts.get(symbol, 0) + 0.5) / (n + 0.5 * k))
        return tuple(result)

    def predict(self, action: str) -> Forecast:
        self._validate_action(action)
        weights = self._weights(action)
        def mix(symbol: str | None) -> float:
            return math.fsum(w * p for w, p in zip(weights, self._expert_probabilities(action, symbol)))
        return Forecast(tuple((s, mix(s)) for s in sorted(self._symbols)), mix(None), weights)

    def progress(self, action: str) -> float:
        losses = tuple(self._losses.get(action, ()))
        w = self.config.progress_window
        if len(losses) < 2 * w:
            return 0.0
        return max(0.0, math.fsum(losses[:w]) / w - math.fsum(losses[w:]) / w)

    @staticmethod
    def _validate_action(action: str) -> None:
        if type(action) is not str or not action or len(action.encode('utf-8')) > 128:
            raise ProtocolError('action must be a nonempty bounded opaque string')

    def choose(self, allowed_actions: list[str] | tuple[str, ...]) -> Choice:
        """Make exactly one proposal; a second requires its observed outcome."""
        if self._pending is not None:
            raise ProtocolError('a decision is already outstanding')
        if self.steps >= self.config.max_steps:
            raise CapacityError('step limit')
        if type(allowed_actions) not in (list, tuple) or not allowed_actions:
            raise ProtocolError('a nonempty explicit action menu is required')
        menu = tuple(allowed_actions)
        for action in menu:
            self._validate_action(action)
        if len(menu) != len(set(menu)):
            raise ProtocolError('duplicate actions')
        if len(set(self._action_counts) | set(menu)) > self.config.max_actions:
            raise CapacityError('action vocabulary limit')
        gains = tuple(self.progress(a) for a in menu)
        new = tuple(a for a in menu if self._action_counts[a] == 0)
        total_gain = math.fsum(gains)
        if new:
            probabilities = tuple(1 / len(new) if a in new else 0.0 for a in menu)
            reason = 'untried_control'
        elif total_gain > 0:
            e = self.config.exploration
            probabilities = tuple(e / len(menu) + (1 - e) * g / total_gain for g in gains)
            reason = 'measured_learning_progress'
        else:
            probabilities = tuple(1 / len(menu) for _ in menu)
            reason = 'no_measured_progress_exploration'
        # Draw state belongs to the experience history; no clock or phase input.
        draw = self._random.random()
        cumulative = 0.0
        selected = len(menu) - 1
        for i, probability in enumerate(probabilities):
            cumulative += probability
            if draw < cumulative:
                selected = i
                break
        choice = Choice(self.steps + 1, menu[selected], menu, probabilities, gains, reason, self.predict(menu[selected]))
        self._pending = choice
        return choice

    def observe(self, choice: Choice, observation: Any) -> dict[str, Any]:
        """Score the pre-action forecast, then update. No future-outcome leakage."""
        if choice != self._pending or choice.step != self.steps + 1:
            raise ProtocolError('outcome does not match the outstanding decision')
        symbol = canonical(observation, self.config.max_observation_bytes)
        if symbol not in self._symbols and len(self._symbols) >= self.config.max_symbols:
            raise CapacityError('observation vocabulary limit')
        contexts = self._contexts()
        keys = tuple((c, choice.action) for c in contexts)
        growth = sum(key not in table for table, key in zip(self._tables, keys))
        if sum(len(t) for t in self._tables) + growth > self.config.max_contexts:
            raise CapacityError('predictive context limit')
        # All checks and scores precede mutation.
        experts = self._expert_probabilities(choice.action, symbol if symbol in self._symbols else None)
        probability = choice.forecast.probability(symbol)
        loss = -math.log2(probability)
        prior = self._log_weights.get(choice.action, [-d * math.log(2) for d in range(self.config.max_depth + 1)])
        posterior = [old + math.log(p) for old, p in zip(prior, experts)]
        top = max(posterior)
        posterior = [x - top for x in posterior]
        event = {'version': VERSION, 'step': choice.step,
                 'before': json.loads(self.observation), 'choice': choice.record(),
                 'after': json.loads(symbol), 'predictive_loss_bits': loss,
                 'probability_assigned_before_outcome': probability}
        for table, totals, key in zip(self._tables, self._totals, keys):
            table.setdefault(key, Counter())[symbol] += 1
            totals[key] = totals.get(key, 0) + 1
        self._log_weights[choice.action] = posterior
        self._losses.setdefault(choice.action, deque(maxlen=2 * self.config.progress_window)).append(loss)
        self._action_counts[choice.action] += 1
        self._history.append((self.observation, choice.action))
        self._symbols.add(symbol)
        self.observation = symbol
        self.steps += 1
        self._pending = None
        return event

    def reorient(self, observation: Any) -> None:
        """Start a new observed sequence without inventing a connecting action."""
        if self._pending is not None:
            raise ProtocolError('cannot reorient an outstanding decision')
        symbol = canonical(observation, self.config.max_observation_bytes)
        if symbol not in self._symbols and len(self._symbols) >= self.config.max_symbols:
            raise CapacityError('observation vocabulary limit')
        self.observation = symbol
        self._symbols.add(symbol)
        self._history.clear()

    def inherit(self, before: Any, action: str, after: Any, *, sequence_break: bool = False) -> dict[str, Any]:
        """Learn a recorded action, without claiming to have selected it or drawing RNG."""
        if type(sequence_break) is not bool or self._pending is not None:
            raise ProtocolError('invalid inherited sequence boundary')
        self._validate_action(action)
        start = canonical(before, self.config.max_observation_bytes)
        end = canonical(after, self.config.max_observation_bytes)
        if not sequence_break and start != self.observation:
            raise ProtocolError('discontinuous inherited transition')
        if self.steps >= self.config.max_steps:
            raise CapacityError('step limit')
        if len(set(self._action_counts) | {action}) > self.config.max_actions:
            raise CapacityError('action vocabulary limit')
        if len(self._symbols | {start, end}) > self.config.max_symbols:
            raise CapacityError('observation vocabulary limit')
        previous_observation, previous_history = self.observation, tuple(self._history)
        previous_symbols = set(self._symbols)
        try:
            if sequence_break:
                self.reorient(before)
            forecast = self.predict(action)
            choice = Choice(self.steps + 1, action, (action,), (1.0,), (0.0,),
                            'inherited_observation_not_agent_choice', forecast)
            self._pending = choice
            return self.observe(choice, after)
        except (ProtocolError, CapacityError):
            self.observation = previous_observation
            self._history.clear()
            self._history.extend(previous_history)
            self._symbols = previous_symbols
            self._pending = None
            raise

    def metadata(self) -> dict[str, Any]:
        return {'version': VERSION, 'config': asdict(self.config), 'seed': self.seed,
                'initial_observation': json.loads(self.initial_observation)}

    def summary(self) -> dict[str, Any]:
        return {'steps': self.steps, 'observed_symbols': len(self._symbols),
                'predictive_contexts': sum(len(t) for t in self._tables),
                'action_counts': dict(self._action_counts),
                'depth_weights': {a: list(self._weights(a)) for a in self._action_counts},
                'learning_progress': {a: self.progress(a) for a in self._action_counts},
                'pending': self._pending.public() if self._pending else None}
