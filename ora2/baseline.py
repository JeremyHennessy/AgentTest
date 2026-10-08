"""Read-only Phase 41 inheritance. No former Phase 42 imports or inferred memories."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

from .learner import Agent, Config, ProtocolError, canonical

SOURCE_COMMIT = '6493c20940b4d1cadf9887b76c4a9ad73d149331'
STATE_COMMIT = '76cc1f73fae48c774070d7a166abfdfbe9260083'
STATE_BLOB = 'e675f36184f1cee8775fb0b4a7cbdea3362d7beb'
JOURNAL_BLOB = 'd54304b27f887623f441b20a050940a0cc8af298'
ACTUATOR_BLOB = 'd6ed911b8fd9e4bd7e50f5a9290974f8cc6f0f39'
WORLD = 'bounded-stateful-world-v1'
ACTIONS = ('north', 'east', 'south', 'west')


def blob_id(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def strict_json(raw: str | bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError('duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise ProtocolError('nonfinite JSON value')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


def position(value: Any) -> list[int]:
    if (type(value) is not list or len(value) != 2 or
            any(type(x) is not int or not -2 <= x <= 2 for x in value)):
        raise ProtocolError('invalid bounded public position')
    return list(value)


def project(snapshot: dict) -> dict:
    """Validate all delivered rows; never blend observations from different worlds."""
    if type(snapshot) is not dict or snapshot.get('schema_version') != 24:
        raise ProtocolError('Phase 41 schema 24 required')
    if type(snapshot.get('cycles')) is not int or snapshot['cycles'] <= 0:
        raise ProtocolError('experienced snapshot required, not cycle-zero starter')
    identity = snapshot.get('identity')
    if (type(identity) is not dict or type(identity.get('designation')) is not str or
            not identity['designation'] or 'chosen_name' not in identity or
            (identity['chosen_name'] is not None and type(identity['chosen_name']) is not str)):
        raise ProtocolError('historical identity does not match the Phase 41 schema')
    lab = snapshot.get('planning_lab', {})
    if lab.get('world_version') != WORLD or lab.get('bounds') != 2:
        raise ProtocolError('only the unchanged Phase 41 stateful world is admitted')
    current = position(lab.get('position'))
    rows = lab.get('transition_observations')
    if type(rows) is not list or len(rows) > 8192:
        raise ProtocolError('missing or above-limit historical observations')
    seen, retained = {}, []
    duplicates = other = 0
    unlocated = []
    last_cycle = -1
    separated = True
    for row in rows:
        if type(row) is not dict:
            raise ProtocolError('invalid transition record')
        source, sid = row.get('source'), row.get('source_id')
        if type(source) is not str or not source or type(sid) is not str or not sid:
            raise ProtocolError('missing historical transition identity')
        key = (source, sid)
        raw = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if key in seen:
            if seen[key] != raw:
                raise ProtocolError('changed duplicate historical observation')
            duplicates += 1
            continue
        seen[key] = raw
        cycle = row.get('cycle')
        if type(cycle) is not int or not last_cycle <= cycle <= snapshot['cycles']:
            raise ProtocolError('historical observation time conflict')
        last_cycle = cycle
        action = row.get('action')
        if action not in ACTIONS or type(row.get('blocked')) is not bool:
            raise ProtocolError('invalid observed control or blocked flag')
        delta = row.get('delta')
        if (type(delta) is not list or len(delta) != 2 or
                any(type(x) is not int or not -4 <= x <= 4 for x in delta)):
            raise ProtocolError('invalid observed displacement')
        if row['blocked'] and delta != [0, 0]:
            raise ProtocolError('blocked record has a nonzero displacement')
        # The pinned snapshot contains 54 early records with exactly this older
        # shape. Retain their identities/bytes, but do not invent positions or
        # assign a world. They cannot train a position-conditioned transition.
        legacy_keys = {'source', 'source_id', 'cycle', 'action', 'delta', 'blocked'}
        if set(row) == legacy_keys and source in {'action_lab', 'planning_lab'}:
            unlocated.append({'source': source, 'source_id': sid, 'cycle': cycle,
                              'record_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                              'reason': 'legacy_world_and_positions_not_recorded'})
            separated = True
            continue
        if row.get('world_version') not in {WORLD, 'bounded-world-v1', 'bounded-transfer-world-v1'}:
            raise ProtocolError('unidentified historical world')
        before, after = position(row.get('before')), position(row.get('after'))
        if delta != [after[i] - before[i] for i in (0, 1)]:
            raise ProtocolError('observed delta mismatch')
        if row['blocked'] and before != after:
            raise ProtocolError('blocked record changed position')
        if row.get('world_version') != WORLD:
            other += 1
            separated = True
            continue
        gap = separated or bool(retained and retained[-1]['after'] != before)
        retained.append({'source': source, 'source_id': sid, 'cycle': cycle,
                         'before': before, 'action': action, 'after': after,
                         'sequence_break': gap})
        separated = False
    if not retained:
        raise ProtocolError('no genuine same-world experience')
    return {'identity': identity, 'origin_cycle': snapshot['cycles'], 'position': current,
            'world': WORLD, 'rows': retained, 'delivered_rows': len(rows),
            'duplicate_rows': duplicates, 'other_world_rows': other,
            'unlocated_legacy_rows': len(unlocated), 'unlocated_legacy_refs': unlocated}


def public_observation(where: list[int]) -> dict:
    # Full existing public position is retained: no manufactured partial observability.
    return {'position': position(where)}


def seeded_agent(origin: dict, *, seed: int, config: Config) -> Agent:
    rows = origin['rows']
    agent = Agent(public_observation(rows[0]['before']), seed=seed, config=config)
    for row in rows:
        agent.inherit(public_observation(row['before']), row['action'],
                      public_observation(row['after']), sequence_break=row['sequence_break'])
    # Current location is an observation, not a fabricated connecting action.
    current = public_observation(origin['position'])
    if canonical(current) != agent.observation:
        agent.reorient(current)
    return agent


def read_origin(snapshot_path: Path, journal_path: Path) -> tuple[bytes, bytes, dict]:
    for path, maximum in ((snapshot_path, 32 * 1024 * 1024), (journal_path, 20 * 1024 * 1024)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
            raise ProtocolError('expected bounded regular historical source file')
    raw, journal = snapshot_path.read_bytes(), journal_path.read_bytes()
    if blob_id(raw) != STATE_BLOB or blob_id(journal) != JOURNAL_BLOB:
        raise ProtocolError('source is not the exact preserved Phase 41 checkpoint')
    origin = project(strict_json(raw))
    # Hash identity preserves every original byte; no journal rewrite or backfill.
    origin['journal_rows'] = sum(1 for line in journal.splitlines() if line)
    return raw, journal, origin


def actuator():
    """Load only the original protected world actuator, never its planning policy."""
    import agenttest.action_lab as module
    path = Path(module.__file__).resolve()
    if blob_id(path.read_bytes()) != ACTUATOR_BLOB:
        raise ProtocolError('actuator is not the reviewed Phase 41 source')
    return module.apply_bounded_action
