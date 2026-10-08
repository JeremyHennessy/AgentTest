"""Timing Study 001: fixed copied full-lifecycle comparison; no live writer.

Nine independently stored sessions, fixed budgets, no result-dependent extension.
The evaluator never sends its world answers to any controller or learner.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback

from ora2.baseline import ACTIONS, WORLD, actuator, blob_id, public_observation, read_origin, strict_json
from ora2.learner import canonical
from ora2.lifecycle_store import LifecycleSession
from ora2.timing import context

BASE = 'b3d154175384db50c2634bb1f1949d95b550aac0'
PROTOCOL = 6049529990
CYCLES = 32
ARMS = tuple((policy, seed) for policy in ('progress', 'random') for seed in range(4)) + (('planner', 0),)
CELLS = tuple((x, y) for x in range(-2, 3) for y in range(-2, 3))
SYMBOLS = tuple(canonical(public_observation(list(p))) for p in CELLS)
ALLOWED_ADDITIONS = {'studies/timing001/run.py', 'studies/timing001/test_study.py',
                     'studies/timing001/PROTOCOL.md', '.github/workflows/ora2-timing001.yml'}
VERSION = 'ora2-timing-study-001'


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], timeout=30)


def verify_source(root):
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    changes = git(root, 'diff', '--name-status', BASE, 'HEAD').decode().splitlines()
    changed = set()
    for line in changes:
        kind, name = line.split('\t', 1)
        if kind != 'A' or name not in ALLOWED_ADDITIONS:
            raise ValueError('not an additions-only frozen-source study: ' + line)
        changed.add(name)
    if changed != ALLOWED_ADDITIONS:
        raise ValueError('study source membership differs from registration')
    original = {}
    for entry in git(root, 'ls-tree', '-rz', BASE).split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, expected = metadata.decode().split()
        name = name.decode(); path = root / name
        if kind != 'blob' or mode not in ('100644', '100755') or path.is_symlink():
            raise ValueError('unsupported baseline member')
        if blob_id(path.read_bytes()) != expected:
            raise ValueError('frozen baseline file changed: ' + name)
        original[name] = expected
    if git(root, 'status', '--porcelain', '--untracked-files=all').strip():
        raise ValueError('source checkout changed')
    return {'head': head, 'base': BASE, 'baseline_blobs': original,
            'study_sha256': {p: digest((root/p).read_bytes()) for p in sorted(ALLOWED_ADDITIONS)},
            'python': sys.version, 'protocol_comment': PROTOCOL}


def evaluate(agent, truths):
    """Same fixed 26-bucket scoring convention as Decision Study 001.

    Reset recent context in independent copies, never teach oracle results. These
    cases measure the retained position-conditioned model, not temporal transfer.
    """
    prior = copy.deepcopy(agent.__dict__)
    rng = agent._random.getstate()
    cases = []
    for point in CELLS:
        probe = copy.deepcopy(agent)
        probe.reorient(public_observation(list(point)))
        for action in ACTIONS:
            forecast = probe.predict(action)
            known = dict(forecast.known)
            if set(known) - set(SYMBOLS):
                raise ValueError('non-world prediction symbol')
            share = forecast.unseen / (len(SYMBOLS) - len(known) + 1)
            probabilities = {key: known.get(key, share) for key in SYMBOLS}
            if not math.isclose(math.fsum(probabilities.values()) + share, 1.0, abs_tol=1e-10):
                raise ValueError('invalid evaluator probability normalization')
            actual = canonical(public_observation(truths[(point, action)]['after']))
            probability = probabilities[actual]
            if not math.isfinite(probability) or probability <= 0:
                raise ValueError('invalid probability in evaluator')
            best = sorted(forecast.known, key=lambda item: (-item[1], item[0]))[0][0]
            cases.append({'position': list(point), 'action': action, 'after': truths[(point, action)]['after'],
                          'loss_bits': -math.log2(probability), 'p': probability,
                          'top1_correct': best == actual})
    # Compare every learner field, including private model tables, excluding the
    # copied Random object itself; compare its state rather than object identity.
    after = dict(agent.__dict__); previous = dict(prior)
    after.pop('_random'); previous.pop('_random')
    if after != previous or agent._random.getstate() != rng or agent._pending is not None:
        raise ValueError('evaluation mutated the acting learner')
    return {'loss_bits': math.fsum(c['loss_bits'] for c in cases)/100,
            'top1_accuracy': sum(c['top1_correct'] for c in cases)/100, 'cases': cases}


def evaluate_saved(session, truths):
    session.db.execute('BEGIN')
    try:
        agent = session._restore()[0]
        result = evaluate(agent, truths)
        session.db.execute('COMMIT')
        return result
    except BaseException:
        session.db.execute('ROLLBACK')
        raise


def goal_map(state):
    goals = state['planning_lab']['goals']
    result = {g['id']: g for g in goals}
    if len(result) != len(goals):
        raise ValueError('goal identities are not unique')
    return result


def audit_cycle(before, after, result, previous_owner, seen):
    """Independent bookkeeping assertions; no world action and no learner update."""
    lab, new = before['planning_lab'], after['planning_lab']
    timing = result['timing']; owner = timing['owner']
    if (timing['context'] != context(before) or result['timing_context_after'] != context(after) or
            timing['previous_owner'] != previous_owner or owner != result.get('owner', 'phase41') or
            result['cycle'] != after['cycles'] or after['cycles'] != before['cycles'] + 1):
        raise ValueError('ownership, cycle or commitment context mismatch')
    if before['identity'] != after['identity'] or after['episodes'][:len(before['episodes'])] != before['episodes']:
        raise ValueError('identity or historical memory was rewritten')
    prior = lab['transition_observations']; rows = new['transition_observations'][len(prior):]
    if new['transition_observations'][:len(prior)] != prior or len(rows) > 1:
        raise ValueError('transition prefix/accounting error')
    if rows != result['temporal']['transition_records']:
        raise ValueError('saved report differs from actual observations')
    for row in rows:
        key = row['source'], row['source_id']
        if key in seen:
            raise ValueError('duplicate completed world action')
        seen.add(key)
    if not rows and lab['position'] != new['position']:
        raise ValueError('unrecorded position change')
    old_goals, new_goals = goal_map(before), goal_map(after)
    if not old_goals.keys() <= new_goals.keys():
        raise ValueError('goal history was erased')
    for identifier, original in old_goals.items():
        current = new_goals[identifier]
        if original['target'] != current['target']:
            raise ValueError('goal target silently changed')
        if original['status'] == 'completed' and current != original:
            raise ValueError('completed goal history rewritten')
    completed = [g['id'] for g in new_goals.values() if g['status'] == 'completed' and
                 old_goals.get(g['id'], {}).get('status') != 'completed']
    for identifier in completed:
        if new_goals[identifier]['target'] != new['position']:
            raise ValueError('goal completion does not match observed position')
    if owner == 'ora2':
        if (lab.get('active_plan_id') is not None or lab.get('active_objective_realization_id') is not None or
                previous_owner == 'ora2' or not timing['eligible'] or len(rows) != 1):
            raise ValueError('protected commitment or return-to-planner rule violated')
        control = result['control']; choice = result['temporal']['learning_event']['choice']
        if (control['plan_interruption'] is not None or control['precommit_cancellation'] is not None or
                control['choice'] != choice or control['action'] != rows[0]['action'] or
                control['before'] != lab['position'] or control['after'] != new['position']):
            raise ValueError('learner-owned action attribution error')
        for identifier in completed:
            g = new_goals[identifier]
            if (lab['position'] == g['target'] or g.get('completion_source') != 'ora2_control' or
                    g.get('completed_execution_id') != control['id'] or 'completed_plan_id' in g):
                raise ValueError('false learner goal-arrival credit')
    return {'cycle': after['cycles'], 'owner': owner, 'reason': timing['reason'],
            'eligible': timing['eligible'], 'action': rows[0]['action'] if rows else None,
            'row': rows[0] if rows else None, 'completed_goals': completed,
            'created_goals': sorted(new_goals.keys()-old_goals.keys()),
            'active_goal_id': new.get('active_goal_id'), 'active_plan_id': new.get('active_plan_id'),
            'new_objective_realizations': len(new.get('objective_realizations',[]))-len(lab.get('objective_realizations',[])),
            'new_self_experiments': len(new.get('self_experiments',[]))-len(lab.get('self_experiments',[])),
            'new_route_memories': len(new.get('episodic_route_memories',[]))-len(lab.get('episodic_route_memories',[])),
            'goal_changes': [{'id': key, 'before': old_goals.get(key), 'after': value}
                            for key,value in new_goals.items() if old_goals.get(key) != value]}


def cold_status(database, root):
    env = os.environ.copy()
    env.update(PYTHONPATH=str(root/'src')+os.pathsep+str(root), PYTHONDONTWRITEBYTECODE='1')
    env.pop('OPENAI_API_KEY',None); env.pop('AGENTTEST_MODEL',None)
    run = subprocess.run([sys.executable,'-B','-s','-m','ora2.lifecycle_store','status',
            '--database',str(database),'--root',str(root)],cwd=root,env=env,capture_output=True,timeout=90)
    if run.returncode:
        raise ValueError('separate-process status failed: '+run.stderr.decode(errors='replace')[-2000:])
    return strict_json(run.stdout)


def execute_arm(policy, seed, root, output):
    if (policy, seed) not in ARMS:
        raise ValueError('unregistered arm')
    identity = verify_source(root)
    raw, history, origin = read_origin(root/'state/organism.json',root/'state/journal.jsonl')
    initial = strict_json(raw)
    execute = actuator()
    truths = {(point,action):execute(list(point),action,bounds=2,world_version=WORLD)
              for point in CELLS for action in ACTIONS}
    # These independent oracle calls are read-only evaluations, not learner experience.
    (output/'evaluation-truths.json').write_text(dump([
        {'position':list(point),'action':action,'receipt':truths[(point,action)]}
        for point in CELLS for action in ACTIONS])+'\n')
    seen = {(r['source'],r['source_id']) for r in initial['planning_lab']['transition_observations']}
    known_blocks = {(tuple(r['before']),r['action']) for r in initial['planning_lab']['transition_observations']
                    if r.get('world_version')==WORLD and r.get('blocked') is True}
    cohort = [g for g in initial['planning_lab']['goals'] if g['status']=='active']
    records = []; previous_owner = None; blocked_repeats = 0; resume_checked = False
    database = output/'session.sqlite'
    session = LifecycleSession.create(database,root,root/'state/organism.json',root/'state/journal.jsonl',
        enabled=True,seed=seed,cycle_limit=CYCLES,allow_ora2=policy!='planner',timing_policy=policy)
    try:
        start_eval = evaluate_saved(session,truths)
        (output/'evaluation-start.json').write_text(dump(start_eval)+'\n')
        with gzip.open(output/'trace.jsonl.gz','wt',encoding='utf-8') as trace:
            for sequence in range(1,CYCLES+1):
                before = strict_json(session.db.execute('SELECT snapshot FROM current').fetchone()[0])
                delivered = session.tick('timing001-'+str(sequence),enabled=True,owner='auto')
                if delivered['replayed']:
                    raise ValueError('fresh study request unexpectedly replayed')
                result=delivered['result']
                after=strict_json(session.db.execute('SELECT snapshot FROM current').fetchone()[0])
                audit=audit_cycle(before,after,result,previous_owner,seen)
                row=audit['row']
                if row and row['world_version']==WORLD:
                    key=(tuple(row['before']),row['action'])
                    if key in known_blocks: blocked_repeats+=1
                    if row['blocked']: known_blocks.add(key)
                trace.write(dump({'sequence':sequence,'audit':audit,'record':result})+'\n')
                trace.flush();records.append(audit);previous_owner=audit['owner']
                print('TIMING001_CYCLE '+dump({'policy':policy,'seed':seed,'sequence':sequence,
                    'cycle':after['cycles'],'owner':audit['owner'],'reason':audit['reason'],
                    'action':audit['action'],'completed_goals':audit['completed_goals']}),flush=True)
                if sequence==CYCLES//2:
                    status=session.status();session.close();session=None
                    if cold_status(database,root)!=status:
                        raise ValueError('mid-run cold reconstruction differs')
                    session=LifecycleSession(database,root)
                    if not session.tick('timing001-1',enabled=True,owner='auto')['replayed'] or session.status()!=status:
                        raise ValueError('mid-run old-request retry changed state')
                    resume_checked=True
            endpoint=evaluate_saved(session,truths)
            (output/'evaluation-end.json').write_text(dump(endpoint)+'\n')
            final=session.status()
            state=strict_json(session.db.execute('SELECT snapshot FROM current').fetchone()[0])
            if final['completed_cycles']!=CYCLES or final['cycle']!=initial['cycles']+CYCLES:
                raise ValueError('registered budget accounting differs')
            if session.db.execute('SELECT snapshot,journal FROM origin').fetchone()!=(raw,history):
                raise ValueError('original archive was changed')
            if not session.tick('timing001-1',enabled=True,owner='auto')['replayed'] or session.status()!=final:
                raise ValueError('final request retry changed state')
    finally:
        if session is not None: session.close()
    if cold_status(database,root)!=final:
        raise ValueError('final cold reconstruction differs')
    if verify_source(root)!=identity:
        raise ValueError('study source changed during execution')
    goals=goal_map(state)
    def completion(item):
        now=goals[item['id']]
        return {'id':item['id'],'target':item['target'],'completed':now['status']=='completed',
                'completed_at_step':now.get('completed_cycle',initial['cycles'])-initial['cycles'] if now['status']=='completed' else None}
    report={'version':VERSION,'status':'valid','policy':policy,'seed':seed,'cycles':CYCLES,
        'source':identity,'origin_sha256':{'snapshot':digest(raw),'journal':digest(history)},
        'origin_cycle':initial['cycles'],'initial_active_goals':[{'id':g['id'],'target':g['target']} for g in cohort],
        'initial_goal_results':[completion(g) for g in cohort], 'initial_cohort_empty':not cohort,
        'initial_loss_bits':start_eval['loss_bits'],'endpoint_loss_bits':endpoint['loss_bits'],
        'endpoint_top1_accuracy':endpoint['top1_accuracy'],
        'learner_actions':sum(r['owner']=='ora2' for r in records),
        'planner_actions':sum(r['owner']=='phase41' and r['row'] is not None for r in records),
        'idle_cycles':sum(r['row'] is None for r in records),
        'other_world_actions':sum(r['row'] is not None and r['row']['world_version']!=WORLD for r in records),
        'previously_observed_blocked_actions':blocked_repeats,
        'self_selected_goals_completed':sum(len(r['completed_goals']) for r in records),
        'new_objective_realizations':sum(r['new_objective_realizations'] for r in records),
        'learner_then_planner':any(a['owner']=='ora2' and b['owner']=='phase41' for a,b in zip(records,records[1:])),
        'protected_interruptions':0,'precommit_cancellations':0,'false_goal_credit':0,'duplicate_actions':0,
        'midrun_cold_resume':resume_checked,'final_cold_restart':True,'old_request_noop':True,
        'oracle_calls':100,'live_actions':0,'records':records,
        'scope':'fixed copied six-stage lifecycle; authored boundary rule; goal counts do not measure equal goal utility'}
    # Preserve the actual stored session for evidence, not an activated persistent pilot.
    with database.open('rb') as source,gzip.open(output/'session.sqlite.gz','wb') as target:
        shutil.copyfileobj(source,target)
    database.unlink()
    (output/'report.json').write_text(dump(report)+'\n')
    manifest={p.name:{'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())}
              for p in sorted(output.iterdir()) if p.is_file() and p.name!='manifest.json'}
    (output/'manifest.json').write_text(dump(manifest)+'\n')
    small={k:v for k,v in report.items() if k not in ('records','source')}
    print('TIMING001_ARM '+dump(small),flush=True)
    print('TIMING001_REPORT_SHA256 '+digest((output/'report.json').read_bytes()),flush=True)
    return report


def summarize(reports):
    if len(reports)!=len(ARMS): raise ValueError('not all nine registered sessions completed')
    by_key={(r.get('policy'),r.get('seed')):r for r in reports}
    if len(by_key)!=len(ARMS) or set(by_key)!=set(ARMS): raise ValueError('missing or duplicate arm identity')
    ref=by_key[('planner',0)]
    for key,r in by_key.items():
        if (r.get('version')!=VERSION or r.get('status')!='valid' or r.get('cycles')!=CYCLES or
            r.get('live_actions')!=0 or r.get('oracle_calls')!=100 or
            r.get('source')!=ref.get('source') or r.get('origin_sha256')!=ref.get('origin_sha256') or
            r.get('initial_active_goals')!=ref.get('initial_active_goals') or
            r.get('initial_loss_bits')!=ref.get('initial_loss_bits') or
            r.get('learner_actions',-1)+r.get('planner_actions',-1)+r.get('idle_cycles',-1)!=CYCLES):
            raise ValueError('invalid or incomparable session report: '+str(key))
        for field in ('protected_interruptions','precommit_cancellations','false_goal_credit','duplicate_actions'):
            if r.get(field)!=0: raise ValueError('failed bookkeeping gate: '+field)
        for field in ('midrun_cold_resume','final_cold_restart','old_request_noop'):
            if r.get(field) is not True: raise ValueError('failed continuity gate: '+field)
        for field in ('endpoint_loss_bits','initial_loss_bits','endpoint_top1_accuracy'):
            if type(r.get(field)) not in (float,int) or not math.isfinite(r[field]): raise ValueError('nonfinite measure')
    pairs=[]
    for seed in range(4):
        p,q=by_key[('progress',seed)],by_key[('random',seed)]
        pairs.append({'seed':seed,'progress_loss':p['endpoint_loss_bits'],'random_loss':q['endpoint_loss_bits'],
                      'advantage_bits':q['endpoint_loss_bits']-p['endpoint_loss_bits'],
                      'progress_actions':p['learner_actions'],'random_actions':q['learner_actions']})
    wins=sum(p['advantage_bits']>0 for p in pairs);losses=sum(p['advantage_bits']<0 for p in pairs)
    mean=math.fsum(p['advantage_bits'] for p in pairs)/4
    required={g['id'] for g in ref['initial_goal_results'] if g['completed']}
    initial_goals_preserved=all(required <= {g['id'] for g in by_key[('progress',seed)]['initial_goal_results'] if g['completed']}
                                for seed in range(4))
    control_observed=any(by_key[('progress',s)]['learner_actions']>0 and by_key[('progress',s)]['learner_then_planner'] for s in range(4))
    keep=mean>0 and wins>=3 and initial_goals_preserved and control_observed
    return {'version':VERSION,'status':'valid','decision':'eligible_for_separate_pilot_review' if keep else 'do_not_activate_pilot',
            'keep_screen_met':keep,'pairs':pairs,'wins':wins,'losses':losses,'ties':4-wins-losses,
            'mean_advantage_bits':mean,'source_head':ref['source']['head'],'frozen_base':BASE,
            'sessions':len(reports),'copied_cycles':CYCLES*len(reports),
            'copied_actions':sum(r['learner_actions']+r['planner_actions'] for r in reports),
            'oracle_calls':sum(r['oracle_calls'] for r in reports),'live_actions':0,
            'initial_cohort_empty':ref['initial_cohort_empty'],'initial_commitments_preserved':initial_goals_preserved,
            'learner_and_planner_continuation_observed':control_observed,
            'arms':[{k:r[k] for k in ('policy','seed','endpoint_loss_bits','endpoint_top1_accuracy',
                       'learner_actions','planner_actions','idle_cycles','previously_observed_blocked_actions',
                       'self_selected_goals_completed','new_objective_realizations','initial_goal_results')}
                    for r in sorted(reports,key=lambda r:(r['policy'],r['seed']))],
            'limits':['Four seeds are not independent worlds.','Timing rule is authored, not learned meta-control.',
                      'Self-selected goal counts do not establish equal difficulty or utility.',
                      'Evaluation resets recent context; no temporal-transfer conclusion.',
                      'No result-dependent extension, no live pilot, no Phase 42 completion.']}


def collect(root, output):
    reports=[]
    for policy,seed in ARMS:
        directory=root/(policy+'-'+str(seed))
        manifest=strict_json((directory/'manifest.json').read_bytes())
        for name,expected in manifest.items():
            if Path(name).name!=name: raise ValueError('invalid artifact member')
            raw=(directory/name).read_bytes()
            if digest(raw)!=expected['sha256'] or len(raw)!=expected['bytes']:
                raise ValueError('artifact content mismatch: '+str(directory/name))
        reports.append(strict_json((directory/'report.json').read_bytes()))
    summary=summarize(reports)
    output.write_text(dump(summary)+'\n')
    print('TIMING001_SUMMARY '+dump(summary),flush=True)
    print('TIMING001_SUMMARY_SHA256 '+digest(output.read_bytes()),flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    arm=sub.add_parser('arm');arm.add_argument('--policy',choices=('progress','random','planner'),required=True)
    arm.add_argument('--seed',type=int,required=True);arm.add_argument('--output',type=Path,required=True)
    total=sub.add_parser('summarize');total.add_argument('--artifacts',type=Path,required=True);total.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    if args.command=='arm':
        if os.getenv('GITHUB_RUN_ATTEMPT','1')!='1': raise ValueError('repeat study attempts are not registered')
        output=args.output.resolve()
        if output.is_relative_to(root): raise ValueError('study output must be outside the source checkout')
        output.mkdir(parents=True,exist_ok=False)
        try: execute_arm(args.policy,args.seed,root,output)
        except BaseException as error:
            (output/'failure.json').write_text(dump({'status':'invalid','policy':args.policy,'seed':args.seed,
                'exception':str(error),'traceback':traceback.format_exc()})+'\n')
            raise
    else:
        collect(args.artifacts.resolve(),args.output.resolve())


if __name__=='__main__':main()
