"""Hosted finite Ora 2 lifecycle smoke using an actual copied Phase 41 world.

This is not the prospectively registered scientific study, a persistent pilot,
or original live Ora. No external model provider or live-state write exists.
Each owned choice must equal its exact read-only pre-action learner preview.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .baseline import strict_json
from .lifecycle_store import LifecycleSession
from .opportunity import VERSION, propose


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root: Path, database: Path, limit: int, seed: int) -> dict:
    if not 1 <= limit <= 8 or not database.is_absolute() or database.is_relative_to(root):
        raise ValueError('bounded independent database required')
    snapshot, journal = root/'state/organism.json', root/'state/journal.jsonl'
    source_hashes = {'snapshot': digest(snapshot), 'journal': digest(journal)}
    with LifecycleSession.create(database, root, snapshot, journal,
                                 enabled=True, seed=seed, cycle_limit=limit,
                                 allow_ora2=True, timing_policy='manual') as session:
        original = session.status()
        if original['completed_cycles'] != 0:
            raise AssertionError('not a fresh independent origin')
    actions = []
    previous_owner = None
    for number in range(limit):
        with LifecycleSession(database, root) as session:
            agent, meta, _, count, _, raw, _ = session._restore()
            if count != number:
                raise AssertionError('retained sequence changed')
            state = strict_json(raw)
            lab = state['planning_lab']
            active_goal = lab.get('active_goal_id')
            active_plan = lab.get('active_plan_id')
            active_precommit = lab.get('active_objective_realization_id')
            proposal = propose(agent, state, previous_owner=previous_owner)
            request = f'ora2-clean-smoke-{number+1}'
            response = session.tick(request, enabled=True, owner=proposal['owner'])
            if response['replayed']:
                raise AssertionError('fresh request was replayed')
            result = response['result']
            if proposal['owner'] == 'ora2':
                if result.get('control',{}).get('choice') != proposal['choice_record']:
                    raise AssertionError('prospective chosen action differs from executed action')
                if any(x is not None for x in (active_goal,active_plan,active_precommit)):
                    raise AssertionError('learner interrupted an inherited commitment')
            elif result.get('control'):
                raise AssertionError('planner cycle misattributed to Ora 2')
            duplicate = session.tick(request, enabled=True, owner=proposal['owner'])
            if duplicate != {'replayed':True,'result':result}:
                raise AssertionError('idempotent replay failed')
            actions.append({'cycle':result['cycle'],'owner':proposal['owner'],
                            'action':(result.get('control') or {}).get('choice',{}).get('action'),
                            'reason':proposal['reason'],'proposal_sha256':proposal['proposal_sha256'],
                            'active_goal_before':active_goal,'active_plan_before':active_plan,
                            'active_precommit_before':active_precommit,
                            'saved_snapshot_sha256':result['after_snapshot_sha256']})
            previous_owner = proposal['owner']
        # Every subsequent cycle enters a separate process for cold replay.
        env = os.environ.copy()
        env.pop('OPENAI_API_KEY',None)
        env.pop('AGENTTEST_MODEL',None)
        cold = subprocess.run([sys.executable,'-B','-m','ora2.lifecycle_store','status',
                               '--database',str(database),'--root',str(root)],
                              cwd=root,env=env,capture_output=True,text=True,check=True,timeout=120)
        if json.loads(cold.stdout)['completed_cycles'] != number+1:
            raise AssertionError('cold committed-cycle replay failed')
    if {'snapshot':digest(snapshot), 'journal':digest(journal)} != source_hashes:
        raise AssertionError('historical Phase 41 checkpoint changed')
    with LifecycleSession(database,root) as session:
        final=session.status()
    return {'status':'HOSTED_ENGINEERING_SMOKE_ONLY','policy':VERSION,
            'world':'unchanged_phase41_world_on_copied_state',
            'original_live_ora_actions':0,'input_sha256':source_hashes,
            'completed_cycles':limit,'learner_owned_cycles':sum(a['owner']=='ora2' for a in actions),
            'actions':actions,'final':final,'benefit_and_continuity_gate':'NOT_EVALUATED',
            'persistent_pilot_enabled':False}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--cycles',type=int,default=4)
    parser.add_argument('--seed',type=int,default=5)
    args=parser.parse_args()
    result=run(args.root.resolve(),args.database.resolve(),args.cycles,args.seed)
    args.report.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'cycles':result['completed_cycles'],
                      'owned':result['learner_owned_cycles'],'source':result['input_sha256']}))


if __name__=='__main__':
    main()
