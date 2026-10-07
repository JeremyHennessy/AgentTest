"""Isolated Phase 41 copy runner; no live branch, workflow, or external action writes.

One SQLite transaction contains one pure bounded-world result. Original Ora's
full snapshot and journal remain immutable archive bytes. The old planner is
not called or assigned credit for choices made by the temporal controller.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from .baseline import (ACTIONS, WORLD, SOURCE_COMMIT, STATE_COMMIT, STATE_BLOB,
                       JOURNAL_BLOB, ACTUATOR_BLOB, actuator, blob_id, project,
                       public_observation, read_origin, seeded_agent, strict_json)
from .learner import Config, ProtocolError, CapacityError
from .storage import encode

MODE = 'ora2-isolated-phase41-v1'


def source_identity() -> dict:
    root = Path(__file__).parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.glob('*.py'))}


def seal(previous: str, body: str) -> str:
    return hashlib.sha256((previous + '\n' + body).encode()).hexdigest()


class Session:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if (not self.path.is_file() or self.path.is_symlink() or
                self.path.stat().st_nlink != 1):
            raise ProtocolError('existing independent regular session required')
        self.db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=rw',
                                  uri=True, isolation_level=None, timeout=10)
        self.db.execute('PRAGMA synchronous=FULL')
        if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            self.close()
            raise ProtocolError('session integrity failure')

    @classmethod
    def create(cls, path: str | Path, snapshot: str | Path, journal: str | Path,
               *, enabled: bool = False, seed: int = 0, action_limit: int = 64):
        if enabled is not True:
            raise ProtocolError('explicit isolated-copy enablement required')
        if type(action_limit) is not int or not 1 <= action_limit <= 64:
            raise ProtocolError('creation action limit must be 1..64')
        if Path(path).is_symlink():
            raise ProtocolError('session path cannot be a symbolic link')
        target = Path(path).resolve()
        root = Path(__file__).resolve().parents[1]
        if target.is_relative_to(root / 'state') or any(
                target == Path(p).resolve() for p in (snapshot, journal)):
            raise ProtocolError('cannot write historical or live state location')
        raw, history, origin = read_origin(Path(snapshot), Path(journal))
        config = Config(max_steps=len(origin['rows']) + action_limit)
        seeded_agent(origin, seed=seed, config=config)  # validate full inheritance before creating anything
        meta = {'mode': MODE, 'source_commit': SOURCE_COMMIT, 'state_commit': STATE_COMMIT,
                'state_blob': STATE_BLOB, 'journal_blob': JOURNAL_BLOB,
                'actuator_blob': ACTUATOR_BLOB, 'code': source_identity(),
                'seed': seed, 'action_limit': action_limit, 'config': asdict(config)}
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        db = sqlite3.connect(target, isolation_level=None)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE origin (id INTEGER PRIMARY KEY CHECK(id=1), metadata TEXT NOT NULL, snapshot BLOB NOT NULL, journal BLOB NOT NULL)')
            db.execute('CREATE TABLE events (seq INTEGER PRIMARY KEY, request TEXT UNIQUE NOT NULL, body TEXT NOT NULL, prior TEXT NOT NULL, seal TEXT NOT NULL)')
            db.execute('CREATE TABLE head (id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL, seal TEXT NOT NULL)')
            for table in ('origin', 'events'):
                for operation in ('UPDATE', 'DELETE'):
                    db.execute(f"CREATE TRIGGER {table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable history'); END")
            text = encode(meta)
            db.execute('INSERT INTO origin VALUES(1,?,?,?)', (text, raw, history))
            db.execute('INSERT INTO head VALUES(1,0,?)', (hashlib.sha256(text.encode()).hexdigest(),))
            db.execute('COMMIT')
        finally:
            db.close()  # failed initialization is left visible; never silently repaired
        return cls(target)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _restore(self):
        row = self.db.execute('SELECT metadata,snapshot,journal FROM origin WHERE id=1').fetchone()
        if row is None:
            raise ProtocolError('missing origin')
        text, raw, history = row
        meta = strict_json(text)
        if (meta.get('mode') != MODE or meta.get('code') != source_identity() or
                meta.get('source_commit') != SOURCE_COMMIT or meta.get('state_commit') != STATE_COMMIT or
                meta.get('state_blob') != STATE_BLOB or meta.get('journal_blob') != JOURNAL_BLOB or
                meta.get('actuator_blob') != ACTUATOR_BLOB or blob_id(raw) != STATE_BLOB or
                blob_id(history) != JOURNAL_BLOB):
            raise ProtocolError('origin or executable identity mismatch')
        if type(meta.get('action_limit')) is not int or not 1 <= meta['action_limit'] <= 64:
            raise ProtocolError('invalid retained action limit')
        origin = project(strict_json(raw))
        config = Config(**meta['config'])
        if config != Config(max_steps=len(origin['rows']) + meta['action_limit']):
            raise ProtocolError('retained configuration changed')
        agent = seeded_agent(origin, seed=meta['seed'], config=config)
        previous = hashlib.sha256(text.encode()).hexdigest()
        count = 0
        for seq, request, body, prior, checksum in self.db.execute('SELECT seq,request,body,prior,seal FROM events ORDER BY seq'):
            if seq != count + 1 or prior != previous or seal(prior, body) != checksum:
                raise ProtocolError('event order or content mismatch')
            value = strict_json(body)
            if value.get('request') != request or value.get('sequence') != seq or value.get('mode') != MODE:
                raise ProtocolError('event identity mismatch')
            choice = agent.choose(ACTIONS)
            expected = agent.observe(choice, value['experience']['after'])
            if encode(expected) != encode(value['experience']):
                raise ProtocolError('saved choice or evidence does not reproduce')
            receipt = value['world_receipt']
            before = expected['before']['position']
            after = expected['after']['position']
            if (receipt.get('action') != choice.action or receipt.get('before') != before or
                    receipt.get('after') != after or
                    receipt.get('delta') != [after[i]-before[i] for i in (0, 1)] or
                    type(receipt.get('blocked')) is not bool or
                    (receipt['blocked'] and after != before)):
                raise ProtocolError('world receipt is inconsistent')
            previous, count = checksum, seq
        if count > meta['action_limit'] or self.db.execute('SELECT seq,seal FROM head WHERE id=1').fetchone() != (count, previous):
            raise ProtocolError('retained head or action budget mismatch')
        return agent, meta, origin, count, previous

    def status(self):
        self.db.execute('BEGIN')
        try:
            agent, meta, origin, count, previous = self._restore()
            result = {'mode': MODE, 'identity': origin['identity'], 'origin_cycle': origin['origin_cycle'],
                      'inherited_observations': len(origin['rows']), 'new_actions': count,
                      'action_limit': meta['action_limit'], 'world': WORLD,
                      'position': strict_json(agent.observation)['position'], 'head': previous,
                      'model': agent.summary(), 'legacy_planner_active_in_this_lane': False,
                      'live_ora_changed': False}
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def tick(self, request: str, *, enabled: bool = False):
        if enabled is not True or type(request) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', request):
            raise ProtocolError('explicit isolated-copy request required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            agent, meta, origin, count, previous = self._restore()
            existing = self.db.execute('SELECT body FROM events WHERE request=?', (request,)).fetchone()
            if existing:
                self.db.execute('COMMIT')
                return {'replayed': True, 'result': strict_json(existing[0])}
            if count >= meta['action_limit']:
                raise CapacityError('isolated action budget exhausted; no automatic reset')
            execute = actuator()
            choice = agent.choose(ACTIONS)  # all four public commands remain available
            before = strict_json(agent.observation)['position']
            receipt = execute(before, choice.action, bounds=2, world_version=WORLD)
            experience = agent.observe(choice, public_observation(receipt['after']))
            value = {'mode': MODE, 'sequence': count + 1, 'request': request,
                     'experience': experience, 'world_receipt': receipt}
            body = encode(value)
            checksum = seal(previous, body)
            self.db.execute('INSERT INTO events VALUES(?,?,?,?,?)', (count + 1, request, body, previous, checksum))
            self.db.execute('UPDATE head SET seq=?,seal=? WHERE id=1', (count + 1, checksum))
            self.db.execute('COMMIT')
            return {'replayed': False, 'result': value}
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ora 2 isolated Phase 41 copy; never modifies live Ora')
    parser.add_argument('command', choices=('init', 'step', 'status'))
    parser.add_argument('--database', required=True)
    parser.add_argument('--isolated-copy', action='store_true')
    parser.add_argument('--snapshot', default='state/organism.json')
    parser.add_argument('--journal', default='state/journal.jsonl')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--action-limit', type=int, default=64)
    parser.add_argument('--request')
    args = parser.parse_args()
    if args.command == 'init':
        with Session.create(args.database, args.snapshot, args.journal, enabled=args.isolated_copy,
                            seed=args.seed, action_limit=args.action_limit) as session:
            print(json.dumps(session.status(), sort_keys=True))
    else:
        with Session(args.database) as session:
            result = session.status() if args.command == 'status' else session.tick(args.request, enabled=args.isolated_copy)
            print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
