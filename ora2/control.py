"""Learner-owned action at the Phase 41 core's existing action boundary.

No old Phase 42 policy is used. The selector's immutable Choice is made by the
parent before this action. Original goals and plans are retained, with explicit
interruptions instead of false old-plan progress. All effects are pure copied
world/state effects; the enclosing lifecycle transaction is authoritative.
"""
from __future__ import annotations

import copy
import json
from typing import Callable

from .baseline import ACTIONS, WORLD, position, project, public_observation
from .learner import ProtocolError, canonical

OWNER = 'ora2'
SOURCE = 'ora2_control'


def active(lab: dict, field: str, collection: str) -> dict | None:
    identifier = lab.get(field)
    if identifier is None:
        return None
    matches = [v for v in lab.get(collection, []) if v.get('id') == identifier]
    if len(matches) != 1:
        raise ProtocolError('unresolved or duplicate active reference: ' + field)
    return matches[0]


def apply_selected(state: dict, payload: dict, execute: Callable, rebuild: Callable) -> dict:
    """Apply one already selected control, stage changes, and then install the lab."""
    project(state)
    if type(payload) is not dict or set(payload) != {'before', 'choice', 'choice_record'}:
        raise ProtocolError('explicit pre-action decision payload required')
    decision, record = payload['choice'], payload['choice_record']
    lab = copy.deepcopy(state['planning_lab'])
    before = position(lab['position'])
    if payload['before'] != public_observation(before):
        raise ProtocolError('decision is not for this position')
    action = decision.get('action')
    if action not in ACTIONS or decision.get('menu') != list(ACTIONS) or record.get('action') != action:
        raise ProtocolError('decision must expose all four approved commands')
    from .lifecycle import sha
    if record.get('forecast_sha256') != sha(json.dumps(decision['forecast'], sort_keys=True,
                                                       separators=(',', ':'), ensure_ascii=False).encode()):
        raise ProtocolError('decision forecast identity mismatch')
    plan = active(lab, 'active_plan_id', 'plans')
    goal = active(lab, 'active_goal_id', 'goals')
    precommit = active(lab, 'active_objective_realization_id', 'objective_realization_decisions')
    if plan is not None and (goal is None or plan.get('goal_id') != goal['id'] or plan.get('status') != 'active'):
        raise ProtocolError('active plan and goal are inconsistent')
    if goal is not None and goal.get('status') != 'active':
        raise ProtocolError('active goal reference is not active')
    if precommit is not None and precommit.get('status') != 'precommitted':
        raise ProtocolError('active realization is not pending')
    cycle = state['cycles']
    eid = f'O2C{cycle:06d}'
    if any(row.get('source_id') == eid for row in lab['transition_observations']):
        raise ProtocolError('cycle already has a learner action')
    # Validate references BEFORE invoking even the pure copied-world actuator.
    outcome = execute(before, action, bounds=2, world_version=WORLD)
    after = position(outcome.get('after'))
    if (outcome.get('action') != action or outcome.get('before') != before or
            outcome.get('delta') != [after[i]-before[i] for i in (0, 1)] or
            type(outcome.get('blocked')) is not bool or (outcome['blocked'] and before != after)):
        raise ProtocolError('invalid actuator receipt')
    interruption = None
    if plan is not None:
        interruption = {'plan_id': plan['id'], 'goal_id': goal['id'],
                        'step_before': plan.get('next_step_index'), 'step_after': plan.get('next_step_index'),
                        'reason': 'ora2_selected_action', 'execution_id': eid}
        plan.update(status='invalidated', invalidated_cycle=cycle,
                    invalidation_reason='ora2_selected_action', ora2_interruption=interruption)
        lab['active_plan_id'] = None
    cancellation = None
    if precommit is not None:
        cancellation = {'decision_id': precommit['id'], 'reason': 'ora2_selected_action'}
        precommit.update(status='cancelled_ora2_action', cancelled_cycle=cycle,
                         cancellation_reason='ora2_selected_action', ora2_execution_id=eid)
        lab['active_objective_realization_id'] = None
    arrival = goal is not None and before != list(goal.get('target', [])) and after == list(goal.get('target', []))
    if arrival:
        # Actual arrival is retained, but it is NOT an executed/completed old plan.
        goal.update(status='completed', completed_cycle=cycle,
                    completion_source=SOURCE, completed_execution_id=eid)
        lab['active_goal_id'] = None
    row = {'source': SOURCE, 'source_id': eid, 'cycle': cycle, 'world_version': WORLD,
           'action': action, 'before': before, 'after': after,
           'delta': list(outcome['delta']), 'blocked': outcome['blocked']}
    lab['transition_observations'].append(row)
    lab['position'], lab['last_action_cycle'] = after, cycle
    key = f'{after[0]},{after[1]}'
    lab.setdefault('visit_counts', {})[key] = lab.get('visit_counts', {}).get(key, 0) + 1
    lab['status'] = 'goal_reached' if arrival else ('needs_replan' if goal else 'ready')
    event = {'id': eid, 'action_owner': OWNER, 'choice': copy.deepcopy(record),
             'action': action, 'before': before, 'after': after, 'world_version': WORLD,
             'delta': list(outcome['delta']), 'blocked': outcome['blocked'],
             'cycle': cycle, 'goal_id': goal['id'] if goal else None,
             'goal_reached': arrival, 'plan_id': None,
             'plan_interruption': interruption, 'precommit_cancellation': cancellation,
             'status': lab['status'], 'replan_required': bool(goal and not arrival)}
    lab.setdefault('ora2_executions', []).append(event)
    rebuild(lab)  # Phase 41's evidence consolidation, not its action-selection policy.
    state['planning_lab'] = lab
    return event


def learn_selected(agent, before: dict, after: dict, predictions: dict, choice) -> dict:
    """Replay/scoring uses the original selected Choice, not an inherited exposure."""
    project(after)
    prior = before['planning_lab']['transition_observations']
    rows = after['planning_lab']['transition_observations']
    if rows[:len(prior)] != prior or len(rows) != len(prior) + 1:
        raise ProtocolError('owned cycle must add exactly one transition')
    row = rows[-1]
    if (row['source'] != SOURCE or row['source_id'] != f"O2C{after['cycles']:06d}" or
            row['cycle'] != after['cycles'] or row['world_version'] != WORLD or
            row['action'] != choice.action or row['before'] != before['planning_lab']['position'] or
            row['after'] != after['planning_lab']['position'] or
            canonical(public_observation(row['before'])) != agent.observation or
            choice.forecast.public() != predictions[choice.action]):
        raise ProtocolError('owned transition does not match the selected action and forecast')
    event = agent.observe(choice, public_observation(row['after']))
    return {'action_owner': OWNER, 'ora2_choices': 1, 'transition_records': [row],
            'position_before': row['before'], 'position_after': row['after'],
            'new_planner_transitions': 0, 'new_ora2_transitions': 1,
            'prospectively_scored': True, 'learning_event': event,
            'reason': 'selected_action_scored_then_learned'}


def validate_effects(before: dict, after: dict, payload: dict, event: dict) -> None:
    """Independently derive plan/goal changes from the saved outcome, no actuation."""
    start, end = before['planning_lab'], after['planning_lab']
    original = copy.deepcopy(before)
    original['cycles'] = after['cycles']
    receipt = {k: event[k] for k in ('action', 'before', 'after', 'delta', 'blocked')}
    expected = apply_selected(original, payload, lambda *a, **k: receipt, lambda lab: None)
    expected['episode_id'] = event.get('episode_id')
    if expected != event:
        raise ProtocolError('action attribution or plan/goal receipt differs')
    wanted = original['planning_lab']
    for key in ('plans', 'goals', 'active_plan_id', 'active_goal_id',
                'objective_realization_decisions', 'active_objective_realization_id',
                'executions', 'objective_realizations', 'position', 'visit_counts',
                'transition_observations', 'last_action_cycle', 'status', 'ora2_executions'):
        if end.get(key) != wanted.get(key):
            raise ProtocolError('unexpected owned-cycle planning change: ' + key)
    added = after.get('episodes', [])[len(before.get('episodes', [])):]
    owned = [e for e in added if e.get('kind') == 'ora2_action']
    if (len(owned) != 1 or owned[0].get('id') != event['episode_id'] or
            json.loads(owned[0]['content']) != event or
            any(e.get('kind') == 'planning_lab' for e in added)):
        raise ProtocolError('owned action is missing or misattributed in memory')
