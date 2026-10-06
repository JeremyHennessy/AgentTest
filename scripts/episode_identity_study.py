"""Compare unchanged Core behavior with the ID candidate on disposable state.

Separate processes import baseline/candidate packages. Full normalized state
and cycle results are compared; only the new top-level allocator field is
excluded. Original evidence and source files are never overwritten.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

FIELD = 'next_episode_index'
PRODUCTION = 'eb906904d4a30d7427075987f928e0b97699cfe3'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def semantic_state(state):
    result=deepcopy(state)
    result.pop(FIELD,None)
    return result


def worker(state_file, steps):
    from agenttest.core import AgentCore
    from agenttest.state import StateStore
    from agenttest.evidence import known_evidence_ids
    store=StateStore(state_file)
    clock=['2026-10-05T13:00:00+00:00']
    with ExitStack() as patches:
        for name,module in list(sys.modules.items()):
            if name.startswith('agenttest.') and hasattr(module,'utc_now'):
                patches.enter_context(patch.object(module,'utc_now',side_effect=lambda:clock[0]))
        state=store.load()
        source=deepcopy(state['environment_snapshots'][-1])
        initial=semantic_state(state)
        baseline_episodes=deepcopy(state['episodes'])
        report={'initial_semantic_hash':digest(initial),'initial_known_ids_hash':digest(sorted(known_evidence_ids(state))),'initial_cycle':state['cycles'],'initial_episode_count':len(baseline_episodes),'initial_next_episode_index':state.get(FIELD),'rows':[]}
        for step in range(steps):
            clock[0]=f'2026-10-05T13:{step+1:02d}:00+00:00'
            start=time.perf_counter()
            result=AgentCore(StateStore(state_file)).cycle(stimulus='autonomous heartbeat',observation=deepcopy(source),strict_experiment_admission=True,planning_lab=True,_now_override=clock[0])
            state=store.load()
            ids=[e['id'] for e in state['episodes']]
            if len(ids)!=len(set(ids)): raise AssertionError('duplicate episode identity')
            if state['episodes'][:len(baseline_episodes)]!=baseline_episodes: raise AssertionError('historical episode content changed')
            report['rows'].append({'step':step+1,'cycle':state['cycles'],'state_hash':digest(semantic_state(state)),'result_hash':digest(result),'known_ids_hash':digest(sorted(known_evidence_ids(state))),'episode_count':len(ids),'last_episode_id':ids[-1],'next_episode_index':state.get(FIELD),'agenda_hash':digest(state['agenda']),'planning_hash':digest(state['planning_lab']),'action_hash':digest(state['action_lab']),'seconds':round(time.perf_counter()-start,6)})
        report['historical_episodes_preserved']=True
        return report


def run(args):
    source=Path(args.state).resolve()
    original_hash=file_hash(source)
    reports={}
    with tempfile.TemporaryDirectory() as tmp:
        for name,src in (('baseline',args.baseline_src),('candidate',args.candidate_src)):
            target=Path(tmp)/name/'organism.json'; target.parent.mkdir(); target.write_bytes(source.read_bytes())
            env=dict(os.environ,PYTHONPATH=str(Path(src).resolve()),PYTHONDONTWRITEBYTECODE='1')
            completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker','--state',str(target),'--steps',str(args.steps)],capture_output=True,text=True,env=env,timeout=300,check=False)
            if completed.returncode: raise RuntimeError(f'{name} failed: {completed.stderr[-4000:]}')
            reports[name]=json.loads(completed.stdout)
    base,new=reports['baseline'],reports['candidate']
    if base['initial_semantic_hash']!=new['initial_semantic_hash']: raise AssertionError('migration changed semantic state')
    if base['initial_known_ids_hash']!=new['initial_known_ids_hash']: raise AssertionError('migration changed evidence authority')
    if new['initial_next_episode_index']!=base['initial_episode_count']+1: raise AssertionError('dense live history numbering changed')
    compared=('state_hash','result_hash','known_ids_hash','episode_count','last_episode_id','agenda_hash','planning_hash','action_hash')
    matches=[]
    for left,right in zip(base['rows'],new['rows']):
        checks={field:left[field]==right[field] for field in compared}
        checks['watermark_correct']=right['next_episode_index']==right['episode_count']+1
        matches.append({'cycle':right['cycle'],'checks':checks})
    if len(matches)!=args.steps or not all(all(row['checks'].values()) for row in matches): raise AssertionError('baseline/candidate behavior mismatch: '+json.dumps(matches))
    if file_hash(source)!=original_hash: raise AssertionError('pinned source file was changed')
    return {'study':'monotonic-episode-identity-copied-live-parity-v1','passed':True,'production_base':PRODUCTION,'source_sha':args.source_sha,'source_sha256':original_hash,'source_unchanged':True,'migration_only_adds_allocator_metadata':True,'matched_cycles':len(matches),'comparison':matches,'baseline':base,'candidate':new,'live_modified':False,'retention_enabled':False,'external_model_api_used':False,'limitations':['Single-writer state snapshots; no stale-writer fencing or distributed allocator.','No episode deletion, archive loading, tombstone authority, resolver floor changes, or retention enabled.','A missing legacy watermark cannot recover a deleted maximum ID; migrate and persist before future compaction.','A restored old snapshot replays its old history; global IDs across independent forks are not promised.']}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state',required=True); p.add_argument('--steps',type=int,default=5)
    p.add_argument('--worker',action='store_true'); p.add_argument('--baseline-src'); p.add_argument('--candidate-src')
    p.add_argument('--source-sha'); p.add_argument('--output')
    a=p.parse_args()
    if a.worker: print(json.dumps(worker(a.state,a.steps),sort_keys=True)); return
    report=run(a)
    if a.output: Path(a.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':report['passed'],'matched_cycles':report['matched_cycles'],'source_unchanged':report['source_unchanged'],'migration_only_adds_allocator_metadata':True,'initial_cycle':report['baseline']['initial_cycle'],'last_cycle':report['candidate']['rows'][-1]['cycle']},sort_keys=True))

if __name__=='__main__': main()
