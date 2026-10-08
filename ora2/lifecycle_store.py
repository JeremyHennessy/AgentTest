"""Transactional, bounded copy of the complete Phase 41 lifecycle.

Original archive bytes are kept once. New event bodies and their exact journal
suffixes are append-only; only the latest complete working snapshot is replaced.
No production state, network, scheduler, or former Phase 42 module is used.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import sqlite3

from .baseline import (STATE_BLOB, JOURNAL_BLOB, WORLD, blob_id, read_origin,
                       seeded_agent, strict_json, project, public_observation)
from .learner import Config, ProtocolError, CapacityError, canonical
from .lifecycle import MODE, source_identity, forecast_menu, run_cycle, learn_cycle, sha, MAX_SNAPSHOT
from .storage import encode

OWNED_MODE = 'ora2-phase41-owned-cycle-v1'
TIMED_MODE = 'ora2-phase41-timed-cycle-v1'

MAX_LOGICAL_BYTES = 128 * 1024 * 1024
REQUEST = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')


def seal(previous: str, body: str) -> str:
    return sha((previous + '\n' + body).encode())


class LifecycleSession:
    def __init__(self, path: str | Path, root: str | Path):
        self.path, self.root = Path(path).resolve(), Path(root).resolve()
        p = Path(path)
        if p.is_symlink() or not p.is_file() or p.stat().st_nlink != 1:
            raise ProtocolError('existing independent lifecycle database required')
        self.db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True,
                                  isolation_level=None, timeout=10)
        self.db.execute('PRAGMA synchronous=FULL')
        if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            self.close()
            raise ProtocolError('lifecycle database is corrupt')

    @classmethod
    def create(cls, path, root, snapshot, journal, *, enabled=False, seed=0, cycle_limit=8, allow_ora2=False, timing_policy='manual'):
        if enabled is not True or type(cycle_limit) is not int or not 1 <= cycle_limit <= 64:
            raise ProtocolError('explicit isolated-copy enablement and 1..64 cycles required')
        if type(allow_ora2) is not bool:
            raise ProtocolError('allow_ora2 must be an explicit boolean')
        from .timing import POLICIES
        if timing_policy not in POLICIES or (timing_policy != 'manual' and
                allow_ora2 != (timing_policy in ('progress', 'random'))):
            raise ProtocolError('timing policy requires matching explicit action authority')
        if Path(path).is_symlink():
            raise ProtocolError('symbolic link destination')
        target, root = Path(path).resolve(), Path(root).resolve()
        # No database anywhere inside the source checkout, including its live state.
        if target.is_relative_to(root) or target in {Path(snapshot).resolve(), Path(journal).resolve()}:
            raise ProtocolError('lifecycle database must be outside the source checkout and inputs')
        raw, history, origin = read_origin(Path(snapshot), Path(journal))
        code = source_identity(root)
        config = Config(max_steps=len(origin['rows']) + cycle_limit)
        seeded_agent(origin, seed=seed, config=config)
        meta = {'mode': MODE, 'code': code, 'seed': seed, 'config': asdict(config),
                'cycle_limit': cycle_limit, 'state_blob': STATE_BLOB, 'journal_blob': JOURNAL_BLOB}
        if allow_ora2:
            meta['allow_ora2'] = True
            meta['mode'] = OWNED_MODE
        if timing_policy != 'manual':
            meta.update(mode=TIMED_MODE, timing_policy=timing_policy)
        text = encode(meta)
        first = sha((text + '\n' + sha(raw) + '\n' + sha(history)).encode())
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        db = sqlite3.connect(target, isolation_level=None)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE origin(id INTEGER PRIMARY KEY CHECK(id=1), meta TEXT, snapshot BLOB, journal BLOB)')
            db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY, request TEXT UNIQUE, body TEXT, prior TEXT, seal TEXT)')
            db.execute('CREATE TABLE current(id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER, seal TEXT, snapshot BLOB)')
            for table in ('origin', 'events'):
                for operation in ('UPDATE', 'DELETE'):
                    db.execute(f"CREATE TRIGGER {table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable history'); END")
            db.execute('INSERT INTO origin VALUES(1,?,?,?)', (text, raw, history))
            db.execute('INSERT INTO current VALUES(1,0,?,?)', (first, raw))
            db.execute('COMMIT')
        finally:
            db.close()
        return cls(target, root)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _restore(self):
        saved = self.db.execute('SELECT meta,snapshot,journal FROM origin WHERE id=1').fetchone()
        if not saved:
            raise ProtocolError('missing original archive')
        text, raw, journal = saved
        meta = strict_json(text)
        if (meta.get('mode') not in (MODE, OWNED_MODE, TIMED_MODE) or meta.get('code') != source_identity(self.root) or
                meta.get('state_blob') != STATE_BLOB or meta.get('journal_blob') != JOURNAL_BLOB or
                blob_id(raw) != STATE_BLOB or blob_id(journal) != JOURNAL_BLOB):
            raise ProtocolError('lifecycle origin or source mismatch')
        if type(meta.get('allow_ora2', False)) is not bool:
            raise ProtocolError('invalid action ownership authority')
        from .timing import POLICIES, context, decide, validate_context
        timing_policy = meta.get('timing_policy', 'manual')
        timed = meta['mode'] == TIMED_MODE
        if timing_policy not in POLICIES or timed != (timing_policy != 'manual'):
            raise ProtocolError('mode and timing authority differ')
        required_authority = (timing_policy in ('progress', 'random')) if timed else meta['mode'] == OWNED_MODE
        if required_authority != meta.get('allow_ora2', False):
            raise ProtocolError('mode and action ownership authority differ')
        limit = meta.get('cycle_limit')
        if type(limit) is not int or not 1 <= limit <= 64:
            raise ProtocolError('invalid retained cycle budget')
        origin_state = strict_json(raw)
        origin = project(origin_state)
        config = Config(**meta['config'])
        if config != Config(max_steps=len(origin['rows']) + limit):
            raise ProtocolError('configuration changed')
        agent = seeded_agent(origin, seed=meta['seed'], config=config)
        previous = sha((text + '\n' + sha(raw) + '\n' + sha(journal)).encode())
        state_hash = sha(raw)
        count = 0
        appended = []
        controls = []
        previous_owner = None
        retained_context = context(origin_state) if timed else None
        logical = len(text.encode()) + len(raw) + len(journal)
        for seq, request, body, prior, checksum in self.db.execute('SELECT seq,request,body,prior,seal FROM events ORDER BY seq'):
            if seq != count + 1 or prior != previous or seal(prior, body) != checksum:
                raise ProtocolError('lifecycle event-chain mismatch')
            record = strict_json(body)
            if (record.get('request') != request or record.get('sequence') != seq or record.get('mode') != meta['mode'] or
                    not REQUEST.fullmatch(request) or record.get('before_snapshot_sha256') != state_hash or
                    record.get('cycle') != origin['origin_cycle'] + seq):
                raise ProtocolError('lifecycle event identity mismatch')
            if record['forecasts'] != forecast_menu(agent):
                raise ProtocolError('saved prospective forecast does not reproduce')
            owner = record.get('owner', 'phase41')
            if timed:
                expected_timing = decide(agent, retained_context, previous_owner=previous_owner,
                                         policy=timing_policy, seed=meta['seed'], sequence=seq)
                if record.get('timing') != expected_timing or owner != expected_timing['owner']:
                    raise ProtocolError('saved timing decision does not reproduce')
                next_context = record.get('timing_context_after')
                validate_context(next_context)
                if next_context['position'] != record['temporal']['position_after']:
                    raise ProtocolError('timing context differs from action outcome')
                retained_context = next_context
            elif 'timing' in record or 'timing_context_after' in record:
                raise ProtocolError('manual session cannot acquire timed authority')
            previous_owner = owner
            report = record['temporal']
            prior_rows = origin_state['planning_lab']['transition_observations'] + appended
            before = {'schema_version': 24, 'cycles': record['cycle'] - 1, 'identity': origin['identity'],
                      'planning_lab': {'bounds': 2, 'world_version': WORLD,
                                       'position': strict_json(agent.observation)['position'],
                                       'transition_observations': prior_rows}}
            after = {'schema_version': 24, 'cycles': record['cycle'], 'identity': origin['identity'],
                     'planning_lab': {'bounds': 2, 'world_version': WORLD,
                                      'position': report['position_after'],
                                      'transition_observations': prior_rows + report['transition_records']}}
            if owner == 'ora2' and meta.get('allow_ora2') is True:
                from .control import learn_selected
                choice = agent.choose(('north', 'east', 'south', 'west'))
                expected_report = learn_selected(agent, before, after, record['forecasts'], choice)
                if record.get('control', {}).get('choice') != choice.record():
                    raise ProtocolError('retained control choice changed')
                controls.append(record['control'])
            elif owner == 'phase41':
                expected_report = learn_cycle(agent, before, after, record['forecasts'])
            else:
                raise ProtocolError('unauthorized retained action owner')
            if encode(expected_report) != encode(report):
                raise ProtocolError('saved passive learning or attribution does not reproduce')
            rows = report['transition_records']
            suffix = record['journal_suffix'].encode()
            if not suffix.endswith(b'\n'):
                raise ProtocolError('truncated lifecycle journal')
            cycle_events = [strict_json(line) for line in suffix.splitlines()]
            cycle_events = [e for e in cycle_events if e.get('event') == 'cycle']
            if len(cycle_events) != 1 or cycle_events[0].get('cycle') != record['cycle']:
                raise ProtocolError('missing or duplicated cycle journal event')
            appended.extend(rows)
            logical += len(body.encode())
            count, previous, state_hash = seq, checksum, record['after_snapshot_sha256']
        current = self.db.execute('SELECT seq,seal,snapshot FROM current WHERE id=1').fetchone()
        if not current or current[:2] != (count, previous) or sha(current[2]) != state_hash or count > limit:
            raise ProtocolError('current snapshot or durable head mismatch')
        working = strict_json(current[2])
        project(working)
        if (working['cycles'] != origin['origin_cycle'] + count or working['identity'] != origin['identity'] or
                working['planning_lab']['transition_observations'] != origin_state['planning_lab']['transition_observations'] + appended or
                public_observation(working['planning_lab']['position']) != strict_json(agent.observation)):
            raise ProtocolError('current Phase 41 history is inconsistent')
        if working['planning_lab'].get('ora2_executions', []) != origin_state['planning_lab'].get('ora2_executions', []) + controls:
            raise ProtocolError('retained control attribution differs from journal')
        if timed and context(working) != retained_context:
            raise ProtocolError('current timing commitments differ from recorded context')
        if len(current[2]) > MAX_SNAPSHOT or logical + len(current[2]) > MAX_LOGICAL_BYTES:
            raise CapacityError('lifecycle logical storage budget exhausted')
        return agent, meta, origin, count, previous, current[2], logical

    def status(self):
        self.db.execute('BEGIN')
        try:
            agent, meta, origin, count, previous, raw, logical = self._restore()
            state = strict_json(raw)
            report = {'mode': meta['mode'], 'cycle': state['cycles'], 'completed_cycles': count,
                      'cycle_limit': meta['cycle_limit'], 'identity': origin['identity'],
                      'position': state['planning_lab']['position'], 'learner': agent.summary(),
                      'action_owner': ('explicit_per_cycle' if meta.get('allow_ora2') else 'unchanged_phase41_planner'),
                      'ora2_choices': len(state['planning_lab'].get('ora2_executions', [])),
                      'allow_ora2': meta.get('allow_ora2', False),
                      'logical_bytes': logical + len(raw), 'head': previous, 'live_actions': 0}
            if meta['mode'] == TIMED_MODE:
                report.update(action_owner='state_based_boundary_rule', timing_policy=meta['timing_policy'])
            self.db.execute('COMMIT')
            return report
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def tick(self, request: str, *, enabled=False, owner='phase41'):
        if enabled is not True or owner not in ('phase41', 'ora2', 'auto') or type(request) is not str or not REQUEST.fullmatch(request):
            raise ProtocolError('explicit isolated-copy request required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            agent, meta, origin, count, previous, raw, logical = self._restore()
            timed = meta['mode'] == TIMED_MODE
            if timed != (owner == 'auto'):
                raise ProtocolError('timed and manual ownership requests cannot be mixed')
            old = self.db.execute('SELECT body FROM events WHERE request=?', (request,)).fetchone()
            if old:
                if not timed and strict_json(old[0]).get('owner', 'phase41') != owner:
                    raise ProtocolError('same request cannot change action owner')
                self.db.execute('COMMIT')
                return {'replayed': True, 'result': strict_json(old[0])}
            if count >= meta['cycle_limit']:
                raise CapacityError('cycle budget exhausted; no automatic reset')
            timing = None
            if timed:
                from .timing import context, decide
                last = self.db.execute('SELECT body FROM events ORDER BY seq DESC LIMIT 1').fetchone()
                previous_owner = strict_json(last[0]).get('owner', 'phase41') if last else None
                timing = decide(agent, context(strict_json(raw)), previous_owner=previous_owner,
                                policy=meta['timing_policy'], seed=meta['seed'], sequence=count + 1)
                owner = timing['owner']
            if owner == 'ora2' and meta.get('allow_ora2') is not True:
                raise ProtocolError('this copied session was not enabled for learner control')
            staged = run_cycle(raw, agent, self.root, enabled=True, owner=owner)
            if staged['source'] != meta['code']:
                raise ProtocolError('source changed before staging')
            record = {'mode': meta['mode'], 'sequence': count + 1, 'request': request, 'cycle': staged['cycle'],
                      'before_snapshot_sha256': sha(raw), 'after_snapshot_sha256': sha(staged['snapshot']),
                      'forecasts': staged['forecasts'], 'temporal': staged['temporal'],
                      'journal_suffix': staged['journal'].decode(), 'outputs': staged['outputs'],
                      'sidecars': staged['sidecars']}
            if owner == 'ora2':
                record.update(owner=owner, control=staged['control'])
            if timing is not None:
                record.update(timing=timing, timing_context_after=context(strict_json(staged['snapshot'])))
            body = encode(record)
            if logical + len(body.encode()) + len(staged['snapshot']) > MAX_LOGICAL_BYTES:
                raise CapacityError('new lifecycle result exceeds logical storage budget')
            checksum = seal(previous, body)
            self.db.execute('INSERT INTO events VALUES(?,?,?,?,?)', (count + 1, request, body, previous, checksum))
            self.db.execute('UPDATE current SET seq=?,seal=?,snapshot=? WHERE id=1', (count + 1, checksum, staged['snapshot']))
            self.db.execute('COMMIT')
            return {'replayed': False, 'result': record}
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ora 2 full isolated Phase 41 lifecycle with explicit action ownership')
    parser.add_argument('command', choices=('init', 'step', 'status'))
    parser.add_argument('--database', required=True)
    parser.add_argument('--root', default='.')
    parser.add_argument('--isolated-copy', action='store_true')
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--cycle-limit', type=int, default=8)
    parser.add_argument('--request')
    parser.add_argument('--allow-ora2', action='store_true')
    parser.add_argument('--owner', choices=('phase41', 'ora2', 'auto'), default='phase41')
    parser.add_argument('--timing-policy', choices=('manual', 'progress', 'random', 'planner'), default='manual')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.command == 'init':
        with LifecycleSession.create(args.database, root, root / 'state/organism.json', root / 'state/journal.jsonl',
                                     enabled=args.isolated_copy, seed=args.seed, cycle_limit=args.cycle_limit, allow_ora2=args.allow_ora2, timing_policy=args.timing_policy) as session:
            print(json.dumps(session.status(), sort_keys=True))
    else:
        with LifecycleSession(args.database, root) as session:
            report = session.status() if args.command == 'status' else session.tick(args.request, enabled=args.isolated_copy, owner=args.owner)
            print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
