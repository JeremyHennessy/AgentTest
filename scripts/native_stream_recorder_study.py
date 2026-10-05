"""Fixed, isolated restart study. Worker processes have no history/oracle input."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'experiments'))
from agenttest.state import StateStore, initial_state
from native_stream_recorder import KEY, NativeStreamRecorder

FROZEN_BASE = 'dcb03f13ad37bcc84543bfa9f42c5be04095feb3'
PRODUCTION_BASE = 'eb906904d4a30d7427075987f928e0b97699cfe3'
CHECKPOINTS = tuple(range(200, 951, 50))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def worker(mode, path, source, sample=None):
    recorder = NativeStreamRecorder(StateStore(path), source, enabled=True)
    if mode == 'ingest':
        payload = json.loads(Path(sample).read_text())
        recorder.ingest(payload['observation'], payload['receipt'], source_id=source)
        recorder.publish()
        before = file_hash(path)
        duplicate = recorder.ingest(payload['observation'], payload['receipt'], source_id=source)
        if duplicate or file_hash(path) != before:
            raise AssertionError('identical retry mutated persisted state')
        return {'pid': os.getpid(), 'retry_preserved_bytes': True}
    before = file_hash(path)
    result = recorder.decision()
    if file_hash(path) != before:
        raise AssertionError('reading a saved decision changed the state')
    return {'pid': os.getpid(), 'decision': result, 'read_preserved_bytes': True}


def cold(mode, path, source, sample=None, expect_rejection=False):
    command = [sys.executable, str(Path(__file__).resolve()), '--worker', mode, '--state', str(path), '--source', source]
    if sample:
        command.extend(['--sample', str(sample)])
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if expect_rejection:
        if result.returncode == 0 or 'ValueError' not in result.stderr:
            raise AssertionError('missing-evidence control was not rejected')
        return True
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def direct(observations, receipts):
    # Only the evaluator uses these history-based reference functions.
    from open_object_world_native_bridge import temporal_candidates
    from open_object_world_action_association import association_candidates
    from normalized_inquiry_objectives import rank_normalized_candidates
    from open_object_world_epistemic_actions import select_epistemic_command
    ranked = rank_normalized_candidates(temporal_candidates(observations), 'information_gain')
    candidate = ranked[0]['candidate']
    return {'ranked': ranked, 'associations': association_candidates(observations, receipts, min_present=1), 'selection': select_epistemic_command(observations[-1], feature=candidate['feature'], relation=candidate['relation'], prefix_observations=observations, prefix_receipts=receipts)}


def study(checkpoints=CHECKPOINTS):
    from open_object_world import initial_world, observe_world, transition
    from open_object_world_explorer import choose_command, observation_signature, command_key
    rows = []
    for seed in range(1, 5):
        source = f'object-world-{seed}'
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            prefix = StateStore(directory/'prefix'/'organism.json')
            state = initial_state(); state['cycles'] = 20; state['generation'] = 20; state['agenda']['started_cycle'] = 1
            prefix.save(state)
            recorder = NativeStreamRecorder(prefix, source, enabled=True)
            world = initial_world(seed)
            observations = [observe_world(world)]; receipts = []; attempts = Counter()
            recorder.ingest(observations[0], source_id=source)
            for cycle in range(1, max(checkpoints)+1):
                before = observations[-1]
                command = choose_command(before, attempts)
                attempts[(observation_signature(before), command_key(command))] += 1
                world, receipt = transition(world, command, cycle=cycle)
                observation = observe_world(world)
                recorder.ingest(observation, receipt, source_id=source)
                observations.append(observation); receipts.append(receipt)
                if cycle not in checkpoints:
                    continue
                case = StateStore(directory/f'case-{cycle}'/'organism.json')
                case.save(prefix.load())
                candidate = NativeStreamRecorder(case, source, enabled=True)
                candidate.publish()
                oracle_before = direct(observations, receipts)
                reloaded = cold('read', case.path, source)
                # Fault injection acts only on an expendable copy, never prefix/case.
                control = StateStore(directory/f'control-{cycle}'/'organism.json')
                broken = case.load(); broken['episodes'].pop(); control.save(broken)
                rejected = cold('read', control.path, source, expect_rejection=True)
                next_world, new_receipt = transition(deepcopy(world), reloaded['decision']['selection']['command'], cycle=cycle+1)
                new_observation = observe_world(next_world)
                sample = directory/f'sample-{cycle}.json'
                sample.write_text(json.dumps({'observation': new_observation, 'receipt': new_receipt}))
                ingest_result = cold('ingest', case.path, source, sample)
                after_reload = cold('read', case.path, source)
                oracle_after = direct([*observations, new_observation], [*receipts, new_receipt])
                final_state = case.load()
                fields = ('ranked', 'associations', 'selection')
                row = {'seed': seed, 'checkpoint': cycle, 'mature': oracle_before['selection']['mode']=='seek_disconfirming_observation', 'before': {k: reloaded['decision'][k] == oracle_before[k] for k in fields}, 'after_new_experience': {k: after_reload['decision'][k] == oracle_after[k] for k in fields}, 'distinct_fresh_processes': len({os.getpid(), reloaded['pid'], ingest_result['pid'], after_reload['pid']}) == 4, 'retry_preserved_bytes': ingest_result['retry_preserved_bytes'], 'missing_evidence_rejected': rejected, 'core_cycle_preserved': final_state['cycles']==20, 'raw_history_absent': all(k not in final_state[KEY] for k in ('history','observations','receipts')), 'temporal_candidates': len(oracle_before['ranked']), 'action_associations': len(oracle_before['associations']), 'state_bytes': case.path.stat().st_size, 'prefix_chain': final_state[KEY]['chain'], 'state_sha256': file_hash(case.path)}
                rows.append(row)
                print(f"checked layout={seed} checkpoint={cycle} parity={all(row['before'].values()) and all(row['after_new_experience'].values())}", file=sys.stderr, flush=True)
    summary = {'case_count': len(rows), 'mature_case_count': sum(r['mature'] for r in rows), 'before_full_parity_count': sum(all(r['before'].values()) for r in rows), 'after_new_experience_full_parity_count': sum(all(r['after_new_experience'].values()) for r in rows), 'fresh_process_proof_count': sum(r['distinct_fresh_processes'] for r in rows), 'identical_retry_preserved_count': sum(r['retry_preserved_bytes'] for r in rows), 'missing_evidence_rejection_count': sum(r['missing_evidence_rejected'] for r in rows), 'core_cycle_preserved_count': sum(r['core_cycle_preserved'] for r in rows), 'raw_history_absent_count': sum(r['raw_history_absent'] for r in rows), 'max_case_state_bytes': max(r['state_bytes'] for r in rows)}
    for group in ('before', 'after_new_experience'):
        for field in ('ranked','associations','selection'):
            summary[f'{group}_{field}_match_count'] = sum(r[group][field] for r in rows)
    paths = ['src/agenttest/core.py','src/agenttest/state.py','src/agenttest/native_evidence.py','experiments/open_object_world.py','experiments/open_object_world_explorer.py','experiments/open_object_world_native_bridge.py','experiments/open_object_world_action_association.py','experiments/open_object_world_epistemic_actions.py','experiments/normalized_inquiry_objectives.py','experiments/native_stream_recorder.py','tests/test_native_stream_recorder.py','scripts/native_stream_recorder_study.py']
    required_counts = [v for k,v in summary.items() if k.endswith('_count') and k not in ('case_count','mature_case_count')]
    passed = all(v==len(rows) for v in required_counts)
    if checkpoints == CHECKPOINTS:
        passed = passed and len(rows)==64 and summary['mature_case_count']==30
    return {'study':'native-stream-recorder-cold-restart-v1','passed':passed,'production_baseline':PRODUCTION_BASE,'research_dependency_base':FROZEN_BASE,'git_sha':os.environ.get('GITHUB_SHA'),'checkpoints':list(checkpoints),'source_hashes':{p:file_hash(ROOT/p) for p in paths},'authority':{'production_modified':False,'live_world_activated':False,'external_model_calls':False,'phase42_credit':False},'limitations':['Fixed four-layout parity study, not independent intelligence/generalization evidence.','Cumulative native snapshots use the existing maximum 64 recent observation refs; prefix digests do not replace a signed source registry or full raw provenance replay.','Research-only single-writer recorder and frozen-selector adapter; not wired to live AgentCore.cycle.','Publication is explicit and transactional; native evidence history grows and no production retention/scaling policy is established.'],'summary':summary,'rows':rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['read','ingest'])
    parser.add_argument('--state'); parser.add_argument('--source'); parser.add_argument('--sample')
    parser.add_argument('--output'); parser.add_argument('--smoke',action='store_true')
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker,args.state,args.source,args.sample),sort_keys=True)); return
    report = study((40,) if args.smoke else CHECKPOINTS)
    text = json.dumps(report,indent=2,sort_keys=True)
    if args.output: Path(args.output).write_text(text+'\n')
    print(json.dumps(report['summary'],sort_keys=True))
    if not report['passed']: raise SystemExit(1)

if __name__ == '__main__': main()
