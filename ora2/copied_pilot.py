"""Explicit, bounded, restartable copied-world Ora 2 engineering pilot.

Never reads/writes original Ora state. The evaluator keeps hidden mechanics;
worker receives only public observations and prior realized evidence. This is
not a registered benefit study or authorization to migrate original Ora.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .blind_context_world import BlindContextWorld, StepReceipt

VERSION = 'ora2-copied-pilot-v1'
MAX_CYCLES = 32


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files():
    root = Path(__file__).resolve().parent
    return root / 'blind_context_world.py', root / 'pilot_worker.py'


def check_path(path):
    path = Path(path).absolute()
    repo = Path(__file__).resolve().parents[1]
    resolved = path.parent.resolve() / path.name
    if resolved.is_relative_to(repo) or path.is_symlink() or (path.exists() and path.stat().st_nlink != 1):
        raise ValueError('pilot ledger must be independent of repo, live state and symlinks')
    if not path.parent.is_dir():
        raise ValueError('pilot ledger parent must exist')
    return path


def atomic_save(path, data, *, new=False):
    raw = canonical(data) + b'\n'
    if new:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        return
    if not path.is_file() or path.is_symlink() or path.stat().st_nlink != 1:
        raise ValueError('pilot ledger was replaced')
    fd, temp_name = tempfile.mkstemp(prefix='.ora2-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def make(seed: int, stream_id: str, budget: int = 16):
    if type(budget) is not int or not 1 <= budget <= MAX_CYCLES:
        raise ValueError('bounded copied-pilot budget required')
    BlindContextWorld(seed=seed, stream_id=stream_id, budget=budget)
    return {'version': VERSION, 'world_sha256': digest(files()[0]),
            'worker_sha256': digest(files()[1]), 'runner_sha256': digest(__file__), 'seed': seed,
            'stream_id': stream_id, 'budget': budget, 'records': [],
            'live_original_actions': 0, 'original_state_changed': False}


def worker(view, history):
    # No evaluator seed, hidden map, change-point or simulator object crosses
    # this process boundary. No external model provider or inherited secrets.
    payload = {'public_view': view, 'history': history}
    with tempfile.TemporaryDirectory(prefix='ora2-worker-') as directory:
        done = subprocess.run([sys.executable, '-I', '-B', str(files()[1])],
                              input=canonical(payload), capture_output=True,
                              timeout=15, cwd=directory,
                              env={'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
    if done.returncode:
        raise ValueError('isolated policy worker rejected public input: ' + done.stderr.decode()[-400:])
    answer = json.loads(done.stdout)
    if (set(answer) != {'action', 'forecast', 'policy'} or
            answer['action'] not in view['available_actions'] or
            answer['policy'] != 'public-empirical-curiosity-v1' or
            type(answer['forecast']) is not list or len(answer['forecast']) != 25 or
            any(type(p) not in (int, float) or not math.isfinite(p) or p <= 0
                for p in answer['forecast']) or
            not math.isclose(math.fsum(answer['forecast']), 1, abs_tol=1e-12, rel_tol=0)):
        raise ValueError('invalid policy forecast or action')
    return answer


def restore(data):
    if (set(data) != {'version', 'world_sha256', 'worker_sha256', 'runner_sha256', 'seed', 'stream_id',
                     'budget', 'records', 'live_original_actions', 'original_state_changed'} or
            data['version'] != VERSION or data['world_sha256'] != digest(files()[0]) or
            data['worker_sha256'] != digest(files()[1]) or data['runner_sha256'] != digest(__file__) or
            data['live_original_actions'] != 0 or data['original_state_changed'] is not False or
            type(data['records']) is not list or len(data['records']) > data['budget']):
        raise ValueError('pilot source/identity mismatch or unsafe ledger')
    world = BlindContextWorld(seed=data['seed'], stream_id=data['stream_id'], budget=data['budget'])
    history, previous = [], '0' * 64
    for i, row in enumerate(data['records'], 1):
        if set(row) != {'index', 'choice', 'before_view', 'receipt', 'evidence', 'log_loss_bits', 'prior', 'head'}:
            raise ValueError('unsupported copied-pilot record shape')
        view = world.public_view()
        answer = worker(view, history)
        if row['choice'] != answer or row['before_view'] != view or row['index'] != i:
            raise ValueError('saved decision differs from cold independent policy reconstruction')
        receipt = world.step(answer['action'])
        if canonical(row['receipt']) != canonical(asdict(receipt)) or row['evidence'] != receipt.evidence():
            raise ValueError('saved action evidence does not replay')
        p = answer['forecast'][(receipt.after[0]+2)*5 + receipt.after[1]+2]
        if not math.isclose(row['log_loss_bits'], -math.log2(p), abs_tol=1e-12):
            raise ValueError('forecast score differs on replay')
        body = {key: row[key] for key in ('index', 'choice', 'before_view', 'receipt', 'evidence', 'log_loss_bits')}
        chain = hashlib.sha256(previous.encode() + b'\n' + canonical(body)).hexdigest()
        if row['prior'] != previous or row['head'] != chain:
            raise ValueError('copied-pilot ledger chain broken')
        history.append(receipt.evidence())
        previous = chain
    return world, history, previous


def advance(path, *, enabled=False, resume=False, seed=0, stream_id=None,
            budget=16, steps=1):
    if enabled is not True or type(steps) is not int or not 1 <= steps <= MAX_CYCLES:
        raise ValueError('explicit bounded copied-world enablement required')
    path = check_path(path)
    lock = path.with_name(path.name + '.lock')
    if lock.is_symlink():
        raise ValueError('pilot lock cannot be a symlink')
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return _advance_locked(path, resume=resume, seed=seed, stream_id=stream_id, budget=budget, steps=steps)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _advance_locked(path, *, resume, seed, stream_id, budget, steps):
    if resume:
        data = json.loads(path.read_bytes())
    else:
        if stream_id is None:
            raise ValueError('new copied world requires a distinct stream ID')
        data = make(seed, stream_id, budget)
        atomic_save(path, data, new=True)
    world, history, prior = restore(data)
    if len(history) + steps > data['budget']:
        raise ValueError('pilot budget exhausted: no implicit extension')
    for _ in range(steps):
        view = world.public_view()
        choice = worker(view, history)
        receipt = world.step(choice['action'])
        p = choice['forecast'][(receipt.after[0]+2)*5 + receipt.after[1]+2]
        body = {'index': len(history) + 1, 'before_view': view, 'choice': choice,
                'receipt': asdict(receipt), 'evidence': receipt.evidence(),
                'log_loss_bits': -math.log2(p)}
        head = hashlib.sha256(prior.encode() + b'\n' + canonical(body)).hexdigest()
        data['records'].append({**body, 'prior': prior, 'head': head})
        atomic_save(path, data)
        history.append(receipt.evidence())
        prior = head
    restored, _, head = restore(json.loads(path.read_bytes()))
    if restored.public_view() != world.public_view() or head != prior:
        raise ValueError('post-save cold replay failed')
    return {'status': 'BOUNDED_COPIED_ENGINEERING_PILOT',
            'completed_actions': len(history), 'action_limit': data['budget'],
            'position': world.public_view()['position'], 'head': head,
            'mean_forecast_log_loss_bits': sum(r['log_loss_bits'] for r in data['records']) / len(history),
            'authored_policy_actions': len(history), 'original_live_ora_actions': 0,
            'persistent_original_ora2_enabled': False,
            'scientific_benefit_gate': 'NOT_TESTED'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--enable-copied', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--stream-id', default=None)
    parser.add_argument('--budget', type=int, default=16)
    parser.add_argument('--steps', type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(advance(args.ledger, enabled=args.enable_copied, resume=args.resume,
                             seed=args.seed, stream_id=args.stream_id, budget=args.budget,
                             steps=args.steps), sort_keys=True))


if __name__ == '__main__':
    main()
