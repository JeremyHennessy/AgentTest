"""Conservative copied-cycle ownership, not a learned priority/agenda system.

No world execution, state mutation, clock, network, or old Phase 42 machinery.
The tested learner still selects the action; this rule only selects its opportunity.
"""
from __future__ import annotations

import hashlib
import math

from .baseline import ACTIONS, position
from .control import active
from .learner import ProtocolError, canonical

VERSION = 'ora2-boundary-timing-v1'
POLICIES = ('manual', 'progress', 'random', 'planner')


def context(state: dict) -> dict:
    """Small pre-action projection of current commitments, not retrospective credit."""
    lab = state['planning_lab']
    result = {'position': position(lab['position'])}
    for label, reference, collection, fields in (
        ('plan', 'active_plan_id', 'plans', ('id', 'status', 'goal_id', 'next_step_index')),
        ('goal', 'active_goal_id', 'goals', ('id', 'status', 'target')),
        ('precommit', 'active_objective_realization_id', 'objective_realization_decisions', ('id', 'status')),
    ):
        item = active(lab, reference, collection)
        result[label] = None if item is None else {key: item.get(key) for key in fields}
    validate_context(result)
    return result


def validate_context(value: dict) -> None:
    if type(value) is not dict or set(value) != {'position', 'plan', 'goal', 'precommit'}:
        raise ProtocolError('invalid timing context')
    position(value['position'])
    for name, keys in (('plan', {'id', 'status', 'goal_id', 'next_step_index'}),
                       ('goal', {'id', 'status', 'target'}), ('precommit', {'id', 'status'})):
        item = value[name]
        if item is None:
            continue
        if (type(item) is not dict or set(item) != keys or
                any(type(item[k]) is not str or not item[k] for k in ('id', 'status'))):
            raise ProtocolError('invalid referenced timing commitment')
        if name == 'goal':
            position(item['target'])
        if name == 'plan' and (type(item['goal_id']) is not str or not item['goal_id'] or
                               type(item['next_step_index']) is not int or item['next_step_index'] < 0):
            raise ProtocolError('invalid referenced plan progress')
    canonical(value)


def decide(agent, current: dict, *, previous_owner: str | None,
           policy: str, seed: int, sequence: int) -> dict:
    """Return a reproducible receipt. Does not draw the learner's action RNG."""
    validate_context(current)
    if (policy not in POLICIES[1:] or previous_owner not in (None, 'phase41', 'ora2') or
            type(seed) is not int or type(sequence) is not int or sequence < 1):
        raise ProtocolError('invalid timing policy or sequence')
    if agent.summary()['pending'] is not None:
        raise ProtocolError('timing cannot replace an outstanding action choice')
    progress = [agent.progress(action) for action in ACTIONS]
    if any(type(p) not in (float, int) or not math.isfinite(p) or p < 0 for p in progress):
        raise ProtocolError('invalid retained prediction progress')
    reason = None
    if current['precommit'] is not None:
        reason = 'preserve_pending_commitment'
    elif current['plan'] is not None:
        reason = 'preserve_referenced_plan'
    elif current['goal'] is not None and (current['goal']['status'] != 'active' or
                                          current['goal']['target'] == current['position']):
        reason = 'planner_goal_bookkeeping_due'
    elif previous_owner == 'ora2':
        reason = 'return_to_planner_after_exploration'
    eligible = reason is None
    owner, draw = 'phase41', None
    if eligible:
        if policy == 'progress':
            if math.fsum(progress) > 0:
                owner, reason = 'ora2', 'positive_retained_prediction_progress'
            else:
                reason = 'no_positive_prediction_progress'
        elif policy == 'random':
            # Separate reproducible control draw; never advances action-selection RNG.
            raw = canonical({'domain': VERSION, 'seed': seed, 'sequence': sequence}).encode()
            draw = int.from_bytes(hashlib.sha256(raw).digest()[:8], 'big') / 2**64
            owner = 'ora2' if draw < 0.5 else 'phase41'
            reason = 'random_timing_control'
        else:
            reason = 'planner_reference'
    return {'version': VERSION, 'policy': policy, 'sequence': sequence,
            'context': current, 'previous_owner': previous_owner,
            'eligible': eligible, 'owner': owner, 'reason': reason,
            'actions': list(ACTIONS), 'retained_progress': progress,
            'random_draw': draw}
