"""Decision Study 001: frozen policies, independently scored copied worlds.

No runtime modification, network access, live writer, or old Phase 42 imports.
This is a policy experiment, not the full Core lifecycle or a live rollout.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import traceback

from ora2.baseline import (ACTIONS, WORLD, STATE_COMMIT, STATE_BLOB, JOURNAL_BLOB,
                           actuator, blob_id, project, public_observation,
                           read_origin, seeded_agent, strict_json)
from ora2.learner import Config, canonical

BASE = '0ed728dff32e5b4d9ff6aea767710fb7ddb8e836'
PROTOCOL_COMMENT = 6047734476
SEEDS = tuple(range(16))
BUDGET = 128
MAX_PLANNER_CALLS = 512
CHECKPOINTS = (0, 32, 64, 96, 128)
CELLS = tuple((x, y) for x in range(-2, 3) for y in range(-2, 3))
CELL_SYMBOLS = tuple(canonical(public_observation(list(p))) for p in CELLS)
ALLOWED_ADDITIONS = {
    'studies/decision001/run.py', 'studies/decision001/test_study.py',
    'studies/decision001/PROTOCOL.md', '.github/workflows/ora2-decision001.yml',
}


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], timeout=30)


def verify_source(root):
    """Every baseline-owned tracked byte, not merely a source-commit label."""
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    changed = git(root, 'diff', '--name-only', BASE, 'HEAD').decode().splitlines()
    if set(changed) - ALLOWED_ADDITIONS:
        raise ValueError('study modifies files outside its declared additions')
    original = {}
    for item in git(root, 'ls-tree', '-rz', BASE).split(b'\0'):
        if not item:
            continue
        meta, name = item.split(b'\t', 1)
        mode, kind, expected = meta.decode().split()
        name = name.decode()
        path = root / name
        if kind != 'blob' or mode not in ('100644', '100755') or path.is_symlink():
            raise ValueError('unsupported baseline member: ' + name)
        if blob_id(path.read_bytes()) != expected:
            raise ValueError('baseline bytes changed: ' + name)
        original[name] = expected
    # Reject tracked/untracked local drift except ignored interpreter caches.
    if git(root, 'status', '--porcelain', '--untracked-files=all').strip():
        raise ValueError('study checkout is not clean')
    added = {name: digest((root / name).read_bytes()) for name in sorted(ALLOWED_ADDITIONS)}
    return {'head': head, 'base': BASE, 'baseline_blob_ids': original,
            'study_sha256': added, 'python': sys.version,
            'protocol_comment': PROTOCOL_COMMENT}


def lifted_probabilities(forecast):
    """Evaluator-only fixed 26-class convention; nothing returned to the learner."""
    known = dict(forecast.known)
    if set(known) - set(CELL_SYMBOLS):
        raise ValueError('predictor exposed non-world symbols')
    remaining = len(CELL_SYMBOLS) - len(known) + 1  # extra invalid/outside bucket
    share = forecast.unseen / remaining
    lifted = {key: known.get(key, share) for key in CELL_SYMBOLS}
    if not math.isclose(math.fsum(lifted.values()) + share, 1.0, abs_tol=1e-10):
        raise ValueError('fixed evaluation alphabet is not normalized')
    if any(p <= 0 or not math.isfinite(p) for p in lifted.values()):
        raise ValueError('invalid forecast probability')
    return lifted


def fixed_evaluation(agent, truths, underobserved):
    """Never train or mutate the acting learner; reset context in each copy."""
    cases = []
    for position in CELLS:
        probe = copy.deepcopy(agent)
        probe.reorient(public_observation(list(position)))
        for action in ACTIONS:
            forecast = probe.predict(action)
            distribution = lifted_probabilities(forecast)
            key = (position, action)
            actual = canonical(public_observation(truths[key]['after']))
            best_known = sorted(forecast.known, key=lambda pair: (-pair[1], pair[0]))[0][0]
            probability = distribution[actual]
            cases.append({'position': list(position), 'action': action,
                          'after': truths[key]['after'], 'p': probability,
                          'loss_bits': -math.log2(probability),
                          'top1_correct': best_known == actual,
                          'initially_underobserved': key in underobserved})
    subset = [c['loss_bits'] for c in cases if c['initially_underobserved']]
    return {'loss_bits': math.fsum(c['loss_bits'] for c in cases) / len(cases),
            'top1_accuracy': sum(c['top1_correct'] for c in cases) / len(cases),
            'initially_underobserved_loss': math.fsum(subset) / len(subset) if subset else None,
            'cases': cases}


def assess_without_mutation(agent, truths, underobserved):
    # Cheap complete public-state comparison plus RNG check; evaluator only touches copies.
    before = dump(agent.summary()), agent.observation, tuple(agent._history), agent._random.getstate()
    result = fixed_evaluation(agent, truths, underobserved)
    after = dump(agent.summary()), agent.observation, tuple(agent._history), agent._random.getstate()
    if before != after or agent._pending is not None:
        raise ValueError('evaluation altered acting learner')
    return result


def make_predictors(origin, seed):
    maximum = len(origin['rows']) + BUDGET
    return (seeded_agent(origin, seed=seed, config=Config(max_steps=maximum)),
            seeded_agent(origin, seed=seed, config=Config(max_depth=0, max_steps=maximum)))


def mean(values):
    return math.fsum(values) / len(values) if values else None


def run_arm(name, seed, origin, snapshot, truths, underobserved, output, execute, planner=None):
    """Only actual chosen/recorded transitions teach either predictor."""
    agent, depth0 = make_predictors(origin, seed or 0)
    rng = random.Random(seed or 0)
    state = copy.deepcopy(snapshot) if name == 'phase41' else None
    inherited_counts = {}
    known_blocked = set()
    for row in origin['rows']:
        key = (tuple(row['before']), row['action'])
        inherited_counts[key] = inherited_counts.get(key, 0) + 1
        if row['before'] == row['after']:
            known_blocked.add(key)
    visited, new_cases = set(), set()
    calls = actions = same_world = other_world = idle = repeat_blocked = 0
    longest_streak = streak = 0
    last_blocked = None
    losses, depth0_losses, checkpoints = [], [], []
    label = name + ('-' + str(seed) if seed is not None else '')
    trace_path = output / (label + '.jsonl.gz')

    def evaluate():
        value = assess_without_mutation(agent, truths, underobserved)
        checkpoints.append({'actions': actions, 'loss_bits': value['loss_bits'],
                            'top1_accuracy': value['top1_accuracy'],
                            'initially_underobserved_loss': value['initially_underobserved_loss']})
        with gzip.open(output / (label + '-eval-' + str(actions) + '.json.gz'), 'wt') as handle:
            handle.write(dump(value) + '\n')

    evaluate()
    with gzip.open(trace_path, 'wt') as trace:
        while actions < BUDGET:
            calls += 1
            if name == 'phase41' and calls > MAX_PLANNER_CALLS:
                raise ValueError('planner did not complete the registered action budget')
            before = strict_json(agent.observation)['position']
            if name == 'phase41':
                assert planner is not None
                forecasts = {a: agent.predict(a) for a in ACTIONS}  # before old planner runs
                zero_forecasts = {a: depth0.predict(a) for a in ACTIONS}
                lab = state['planning_lab']
                count = len(lab['transition_observations'])
                previous = copy.deepcopy(lab['transition_observations'][-1])
                state['cycles'] += 1
                result = planner(state)
                lab = state['planning_lab']
                rows = lab['transition_observations'][count:]
                if lab['transition_observations'][count-1] != previous or len(rows) > 1:
                    raise ValueError('planner transition history/accounting changed unexpectedly')
                if not rows:
                    idle += 1
                    if lab['position'] != before:
                        raise ValueError('planner changed position without a transition')
                    trace.write(dump({'type': 'idle', 'call': calls, 'cycle': state['cycles'],
                                      'position': before, 'result': result}) + '\n')
                    continue
                row = rows[0]
                receipt = {k: row[k] for k in ('action', 'before', 'after', 'delta', 'blocked')}
                world = row['world_version']
                if world not in (WORLD, 'bounded-transfer-world-v1'):
                    raise ValueError('unregistered planner world')
                actions += 1
                if world != WORLD:
                    other_world += 1
                    agent.reorient(public_observation(lab['position']))
                    depth0.reorient(public_observation(lab['position']))
                    trace.write(dump({'type': 'other_world_action', 'number': actions,
                                      'call': calls, 'world': world, 'receipt': receipt}) + '\n')
                    if actions in CHECKPOINTS:
                        evaluate()
                    continue
                if row['before'] != before or row['after'] != lab['position']:
                    raise ValueError('planner action does not match public current context')
                forecast, zero_forecast = forecasts[row['action']], zero_forecasts[row['action']]
                event = agent.inherit(public_observation(before), row['action'], public_observation(row['after']))
                owner = 'unchanged_phase41_planner'
            else:
                if name == 'ora2':
                    choice = agent.choose(ACTIONS)
                    action, forecast, owner = choice.action, choice.forecast, 'ora2'
                elif name == 'uniform':
                    # Same one-uniform-draw sequence as the matching Ora 2 seed.
                    action = ACTIONS[min(int(rng.random() * len(ACTIONS)), len(ACTIONS)-1)]
                    forecast, owner = agent.predict(action), 'uniform_random_controller'
                else:
                    raise ValueError('unknown registered arm')
                zero_forecast = depth0.predict(action)
                receipt = execute(before, action, bounds=2, world_version=WORLD)
                after = public_observation(receipt['after'])
                event = agent.observe(choice, after) if name == 'ora2' else agent.inherit(public_observation(before), action, after)
                actions += 1
            if receipt != truths[(tuple(receipt['before']), receipt['action'])]:
                raise ValueError('recorded action outcome disagrees with the fixed world')
            same_world += 1
            action = receipt['action']
            after = public_observation(receipt['after'])
            if event['choice']['forecast_sha256'] != digest(dump(forecast.public()).encode()):
                raise ValueError('outcome was not scored against the prior forecast')
            zero_event = depth0.inherit(public_observation(receipt['before']), action, after)
            if zero_event['choice']['forecast_sha256'] != digest(dump(zero_forecast.public()).encode()):
                raise ValueError('depth-zero observer forecast ordering mismatch')
            losses.append(event['predictive_loss_bits'])
            depth0_losses.append(zero_event['predictive_loss_bits'])
            key = (tuple(receipt['before']), action)
            visited.add(key)
            if key not in inherited_counts:
                new_cases.add(key)
            if receipt['blocked']:
                repeat_blocked += int(key in known_blocked)
                known_blocked.add(key)
                streak = streak + 1 if key == last_blocked else 1
                longest_streak = max(longest_streak, streak)
                last_blocked = key
            else:
                streak, last_blocked = 0, None
            trace.write(dump({'type': 'action', 'number': actions, 'call': calls,
                              'owner': owner, 'receipt': receipt, 'experience': event,
                              'depth0_predictive_loss_bits': zero_event['predictive_loss_bits']}) + '\n')
            if actions in CHECKPOINTS:
                evaluate()
    if actions != BUDGET or same_world + other_world != BUDGET or idle + actions != calls:
        raise ValueError('incomplete action accounting')
    rng_state = agent._random.getstate() if name == 'ora2' else rng.getstate()
    area = math.fsum((b['actions']-a['actions']) * (a['loss_bits']+b['loss_bits']) / 2
                     for a, b in zip(checkpoints, checkpoints[1:])) / BUDGET
    return {'arm': name, 'seed': seed, 'calls': calls, 'actions': actions,
            'same_world_actions': same_world, 'other_world_actions': other_world, 'idle_calls': idle,
            'ora2_owned_actions': BUDGET if name == 'ora2' else 0,
            'checkpoints': checkpoints, 'mean_curve_loss': area,
            'final_position': strict_json(agent.observation)['position'],
            'unique_selected_state_actions': len(visited), 'newly_sampled_state_actions': len(new_cases),
            'previously_observed_blocked_actions': repeat_blocked, 'max_identical_blocked_streak': longest_streak,
            'on_route_loss': mean(losses), 'on_route_depth0_loss': mean(depth0_losses),
            'last64_on_route_loss': mean(losses[-64:]), 'last64_depth0_loss': mean(depth0_losses[-64:]),
            'rng_sha256': digest(repr(rng_state).encode()), 'trace_file': trace_path.name,
            'trace_sha256': digest(trace_path.read_bytes()), 'model': agent.summary()}


def comparison(arms):
    ours = {a['seed']: a for a in arms if a['arm'] == 'ora2'}
    randoms = {a['seed']: a for a in arms if a['arm'] == 'uniform'}
    old = [a for a in arms if a['arm'] == 'phase41']
    if len(arms) != 33 or set(ours) != set(SEEDS) or set(randoms) != set(SEEDS) or len(old) != 1:
        raise ValueError('missing registered arm or seed')
    pairs = []
    for seed in SEEDS:
        a, b = ours[seed], randoms[seed]
        if a['rng_sha256'] != b['rng_sha256'] or a['actions'] != BUDGET or b['actions'] != BUDGET:
            raise ValueError('paired random draws or action budgets differ')
        delta = b['checkpoints'][-1]['loss_bits'] - a['checkpoints'][-1]['loss_bits']
        pairs.append({'seed': seed, 'ora2_loss': a['checkpoints'][-1]['loss_bits'],
                      'uniform_loss': b['checkpoints'][-1]['loss_bits'], 'ora2_advantage_bits': delta})
    gain = mean([p['ora2_advantage_bits'] for p in pairs])
    wins = sum(p['ora2_advantage_bits'] > 0 for p in pairs)
    losses = sum(p['ora2_advantage_bits'] < 0 for p in pairs)
    return {'paired_mean_advantage_bits': gain, 'ora2_wins': wins, 'ora2_losses': losses,
            'ties': len(SEEDS)-wins-losses, 'pairs': pairs,
            'engineering_threshold_met': gain >= 0.02 and wins >= 12,
            'decision': 'keep_for_further_integration' if gain >= 0.02 and wins >= 12 else 'do_not_promote_current_selector',
            'phase41_reference_endpoint': old[0]['checkpoints'][-1],
            'scope': 'one fixed world and inherited snapshot; seeds are not independent worlds; no live learning claim'}


def run(root, output):
    source = verify_source(root)
    raw, history, origin = read_origin(root / 'state/organism.json', root / 'state/journal.jsonl')
    snapshot = strict_json(raw)
    execute = actuator()
    from agenttest.planning_lab import step_planning_lab
    truths = {(p, a): execute(list(p), a, bounds=2, world_version=WORLD) for p in CELLS for a in ACTIONS}
    counts = {}
    for row in origin['rows']:
        key = (tuple(row['before']), row['action'])
        counts[key] = counts.get(key, 0) + 1
    under = {key for key in truths if counts.get(key, 0) < 2}
    initial, _ = make_predictors(origin, 0)
    baseline = assess_without_mutation(initial, truths, under)
    provenance = {'source': source, 'state_commit': STATE_COMMIT, 'state_blob': STATE_BLOB,
                  'journal_blob': JOURNAL_BLOB, 'snapshot_sha256': digest(raw), 'journal_sha256': digest(history),
                  'origin_cycle': origin['origin_cycle'], 'initial_symbols': initial.summary()['observed_symbols'],
                  'inherited_observations': len(origin['rows']), 'unlocated_legacy_rows': origin['unlocated_legacy_rows'],
                  'initially_underobserved_cases': len(under), 'initially_never_observed_cases': 100-len(counts),
                  'evaluator_oracle_calls': len(truths), 'seeds': list(SEEDS), 'action_budget': BUDGET}
    (output / 'provenance.json').write_text(dump(provenance) + '\n')
    (output / 'evaluation_truths.json').write_text(dump(list(truths.values())) + '\n')
    (output / 'baseline.json').write_text(dump(baseline) + '\n')
    arms = []
    for name, seed in [('phase41', None)] + [(name, seed) for seed in SEEDS for name in ('ora2', 'uniform')]:
        value = run_arm(name, seed, origin, snapshot, truths, under, output, execute, step_planning_lab)
        arms.append(value)
        (output / 'completed_arms.json').write_text(dump(arms) + '\n')
        print('ORA2_D001_ARM ' + dump({k: value[k] for k in ('arm', 'seed', 'calls', 'actions', 'idle_calls', 'checkpoints')}), flush=True)
    if verify_source(root) != source:
        raise ValueError('source changed during experiment')
    result = comparison(arms)
    aggregates = {}
    for name in ('ora2', 'uniform', 'phase41'):
        group = [a for a in arms if a['arm'] == name]
        aggregates[name] = {'runs': len(group),
            'endpoint_loss_bits': mean([a['checkpoints'][-1]['loss_bits'] for a in group]),
            'endpoint_top1_accuracy': mean([a['checkpoints'][-1]['top1_accuracy'] for a in group]),
            'mean_curve_loss': mean([a['mean_curve_loss'] for a in group]),
            'mean_unique_selected_cases': mean([a['unique_selected_state_actions'] for a in group]),
            'mean_newly_sampled_cases': mean([a['newly_sampled_state_actions'] for a in group]),
            'mean_previously_observed_blocked_actions': mean([a['previously_observed_blocked_actions'] for a in group]),
            'mean_on_route_loss': mean([a['on_route_loss'] for a in group]),
            'mean_on_route_depth0_loss': mean([a['on_route_depth0_loss'] for a in group])}
    compact = [{k: v for k, v in a.items() if k != 'model'} for a in arms]
    report = {'valid': True, 'study': 'Ora2 Decision Study 001', 'provenance': provenance,
              'baseline': {k: v for k, v in baseline.items() if k != 'cases'},
              'result': result, 'aggregates': aggregates, 'arms': compact,
              'total_agent_world_actions': sum(a['actions'] for a in arms),
              'total_planner_calls': arms[0]['calls'], 'live_actions': 0, 'source_bytes_preserved': True}
    (output / 'report.json').write_text(dump(report) + '\n')
    manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                for p in sorted(output.iterdir()) if p.is_file()}
    (output / 'manifest.json').write_text(dump(manifest) + '\n')
    print('ORA2_D001_RESULT ' + dump({'valid': True, 'base': BASE, 'head': source['head'],
          'baseline': report['baseline'], 'initial_symbols': provenance['initial_symbols'],
          'initially_underobserved_cases': len(under), 'initially_never_observed_cases': 100-len(counts),
          'result': result, 'aggregates': aggregates, 'total_agent_world_actions': report['total_agent_world_actions'],
          'live_actions': 0, 'report_sha256': manifest['report.json']['sha256'],
          'manifest_sha256': digest((output / 'manifest.json').read_bytes())}), flush=True)


def main():
    root = Path(__file__).resolve().parents[2]
    output = Path(sys.argv[1]).resolve()
    if output.is_relative_to(root):
        raise ValueError('study output must be outside the repository')
    output.mkdir(parents=True, exist_ok=False)
    try:
        run(root, output)
    except BaseException as error:
        (output / 'INVALID.json').write_text(dump({'valid': False, 'error': str(error),
            'traceback': traceback.format_exc(), 'no_positive_conclusion': True}) + '\n')
        raise


if __name__ == '__main__':
    main()
