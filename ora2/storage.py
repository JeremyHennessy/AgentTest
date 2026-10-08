"""Local completed-experience log, not a live-world or GitHub transaction layer.

Append-only SQLite records retain public experience, not repeated full model
snapshots. A fresh learner replays them and verifies its original decisions.
The caller must not use an in-memory learner after a failed append; reload it.
There is no claim of exactly-once physical action or remote-runner durability.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from .learner import Agent, Config, ProtocolError, VERSION


def encode(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


class ExperienceLog:
    def __init__(self, path: str | Path, *, create: Agent | None = None):
        self.path = Path(path)
        self._db: sqlite3.Connection | None = None
        if create is not None:
            if create.steps or create.summary()['pending']:
                raise ProtocolError('new log requires a fresh learner')
            # Never overwrite a legacy memory file, including an existing symlink.
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            try:
                self._db = sqlite3.connect(self.path, isolation_level=None)
                self._db.executescript('''
                    PRAGMA synchronous=FULL;
                    CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                    CREATE TABLE head (id INTEGER PRIMARY KEY CHECK(id=1), step INTEGER NOT NULL, seal TEXT NOT NULL);
                    CREATE TABLE experience (step INTEGER PRIMARY KEY, body TEXT NOT NULL,
                                             predecessor TEXT NOT NULL, seal TEXT NOT NULL);
                    CREATE TRIGGER no_update BEFORE UPDATE ON experience BEGIN SELECT RAISE(ABORT,'append only'); END;
                    CREATE TRIGGER no_delete BEFORE DELETE ON experience BEGIN SELECT RAISE(ABORT,'append only'); END;
                ''')
                self._db.execute('BEGIN IMMEDIATE')
                self._db.execute('INSERT INTO metadata VALUES (1, ?)', (encode(create.metadata()),))
                self._db.execute('INSERT INTO head VALUES (1,0,?)', (hashlib.sha256(encode(create.metadata()).encode()).hexdigest(),))
                self._db.execute('COMMIT')
            except BaseException:
                self.close()
                # Do not silently repair or reuse an incompletely initialized log.
                raise
        else:
            if not self.path.is_file() or self.path.is_symlink():
                raise ProtocolError('existing regular log required; no automatic bootstrap')
            uri = self.path.resolve().as_uri() + '?mode=rw'
            self._db = sqlite3.connect(uri, uri=True, isolation_level=None)
            self._db.execute('PRAGMA synchronous=FULL')
        if self._db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            self.close()
            raise ProtocolError('SQLite integrity check failed')

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self) -> 'ExperienceLog':
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _metadata(self) -> dict[str, Any]:
        if self._db is None:
            raise ProtocolError('log is closed')
        row = self._db.execute('SELECT value FROM metadata WHERE id=1').fetchone()
        if row is None:
            raise ProtocolError('missing metadata')
        value = json.loads(row[0])
        if set(value) != {'version', 'config', 'seed', 'initial_observation'} or value['version'] != VERSION:
            raise ProtocolError('unsupported log identity')
        return value

    def append(self, event: dict[str, Any]) -> bool:
        """Exactly identical completed deliveries are no-ops, not new learning."""
        self._metadata()
        if event.get('version') != VERSION or type(event.get('step')) is not int or event['step'] < 1:
            raise ProtocolError('invalid event identity')
        body = encode(event)
        self._db.execute('BEGIN IMMEDIATE')
        try:
            old = self._db.execute('SELECT body FROM experience WHERE step=?', (event['step'],)).fetchone()
            if old:
                if old[0] != body:
                    raise ProtocolError('conflicting delivery')
                self._db.execute('COMMIT')
                return False
            tail = self._db.execute('SELECT step,seal FROM experience ORDER BY step DESC LIMIT 1').fetchone()
            last, previous = tail if tail else (0, hashlib.sha256(encode(self._metadata()).encode()).hexdigest())
            if self._db.execute('SELECT step,seal FROM head WHERE id=1').fetchone() != (last, previous):
                raise ProtocolError('stored head does not match history')
            if event['step'] != last + 1:
                raise ProtocolError('noncontiguous experience')
            seal = hashlib.sha256((previous + '\n' + body).encode()).hexdigest()
            self._db.execute('INSERT INTO experience VALUES (?,?,?,?)', (event['step'], body, previous, seal))
            self._db.execute('UPDATE head SET step=?,seal=? WHERE id=1', (event['step'], seal))
            self._db.execute('COMMIT')
            return True
        except BaseException:
            if self._db.in_transaction:
                self._db.execute('ROLLBACK')
            raise

    def restore(self) -> Agent:
        """Read-only replay with decision/outcome parity, including seeded draws."""
        meta = self._metadata()
        agent = Agent(meta['initial_observation'], config=Config(**meta['config']), seed=meta['seed'])
        previous = hashlib.sha256(encode(meta).encode()).hexdigest()
        for step, body, predecessor, seal in self._db.execute('SELECT step,body,predecessor,seal FROM experience ORDER BY step'):
            if step != agent.steps + 1 or predecessor != previous:
                raise ProtocolError('experience order or predecessor conflict')
            if hashlib.sha256((previous + '\n' + body).encode()).hexdigest() != seal:
                raise ProtocolError('experience content conflict')
            event = json.loads(body)
            choice = agent.choose(event['choice']['menu'])
            if choice.record() != event['choice']:
                raise ProtocolError('recorded decision does not reproduce')
            actual = agent.observe(choice, event['after'])
            if encode(actual) != body:
                raise ProtocolError('recorded outcome does not reproduce')
            previous = seal
        if self._db.execute('SELECT step,seal FROM head WHERE id=1').fetchone() != (agent.steps, previous):
            raise ProtocolError('stored head does not match replay')
        return agent
