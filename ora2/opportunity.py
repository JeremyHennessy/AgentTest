"""Joint opportunity policy for Ora 2's new behavioral design.

This is an authored safety/novelty gate, not a learned executive or proof of
increased intelligence. It reads public experience and makes no world actions,
API requests, file writes, or changes to the actual learner's RNG.
"""
from __future__ import annotations

import copy
import hashlib
import math

from .baseline import ACTIONS, WORLD, position, public_observation
from .learner import ProtocolError, canonical

VERSION = 'ora2-joint-opportunity-prototype-v1'


def _reference(lab: dict, key: str, collection: str) -> dict | None:
    ident = lab.get(key)
    if ident is None:
        return None
    found = [x for x in lab.get(collection, ()) if isinstance(x, dict) and x.get('id') == ident]
    if len(found) != 1:
        raise ProtocolError('ambiguous or missing inherited commitment: ' + key)
    return found[0]


def propose(agent, snapshot: dict, *, previous_owner: str | None) -> dict:
    """Preview an exact learner action without consuming learner RNG.

    This replaces the failed global-progress timing premise: the admitted
    opportunity and the executed command must be the SAME action in the
    SAME observed context, with exact prospective attribution.
    """
    if type(snapshot) is not dict or type(snapshot.get('planning_lab')) is not dict:
        raise ProtocolError('missing planning evidence')
    if previous_owner not in (None, 'phase41', 'ora2'):
        raise ProtocolError('invalid previous owner')
    lab = snapshot['planning_lab']
    if lab.get('world_version') != WORLD:
        raise ProtocolError('unapproved world')
    where = position(lab.get('position'))
    if canonical(public_observation(where)) != agent.observation:
        raise ProtocolError('learner and world are not at the same public state')
    if agent.summary().get('pending') is not None:
        raise ProtocolError('cannot preview an outstanding choice')
    precommit = _reference(lab, 'active_objective_realization_id', 'objective_realization_decisions')
    plan = _reference(lab, 'active_plan_id', 'plans')
    goal = _reference(lab, 'active_goal_id', 'goals')
    preview = copy.deepcopy(agent).choose(ACTIONS)
    if preview.action not in ACTIONS or tuple(preview.menu) != tuple(ACTIONS):
        raise ProtocolError('unapproved learner action menu')
    matching = []
    for row in lab.get('transition_observations', []):
        if (type(row) is dict and row.get('world_version') == WORLD and
                row.get('before') == where and row.get('action') == preview.action):
            if type(row.get('blocked')) is not bool:
                raise ProtocolError('ambiguous observed action outcome')
            matching.append(row)
    blocked = sum(row['blocked'] for row in matching)
    forecast = preview.forecast.public()
    probabilities = [x['probability'] for x in forecast['known']] + [forecast['unseen_probability']]
    if not probabilities or any(type(x) not in (float,int) or not math.isfinite(x) or x < 0 or x > 1
                                for x in probabilities):
        raise ProtocolError('invalid prospective forecast')
    residual_uncertainty = 1.0 - max(probabilities)
    if precommit is not None:
        reason = 'protect_inherited_precommit'
    elif plan is not None:
        reason = 'protect_inherited_plan'
    elif goal is not None:
        reason = 'protect_inherited_goal'
    elif previous_owner == 'ora2':
        reason = 'yield_full_cycle_to_original_planner'
    elif len(matching) >= 2 and blocked == len(matching):
        reason = 'observed_repeated_block_for_exact_action'
    elif len(matching) >= 2 and residual_uncertainty < 0.20:
        reason = 'little_unresolved_evidence_for_exact_action'
    else:
        reason = 'exact_action_context_has_unresolved_evidence'
    admitted = reason == 'exact_action_context_has_unresolved_evidence'
    envelope = {'version':VERSION, 'observation':public_observation(where),
                'action':preview.action, 'choice_record':preview.record(),
                'same_context_action_observations':len(matching),
                'same_context_action_blocks':blocked,
                'residual_predictive_uncertainty':residual_uncertainty,
                'previous_owner':previous_owner, 'reason':reason,
                'owner':'ora2' if admitted else 'phase41'}
    envelope['proposal_sha256'] = hashlib.sha256(canonical(envelope).encode()).hexdigest()
    return envelope
