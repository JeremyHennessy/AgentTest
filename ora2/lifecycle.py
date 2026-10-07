"""Copy-only Phase 41 lifecycle with passive, prospective Ora 2 predictions.

The unchanged planner alone selects and executes actions. The temporal learner
observes their consequences; it never chooses, vetoes, or receives goal credit.
Every original writer runs against one disposable directory, not live state.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .baseline import ACTIONS, WORLD, blob_id, project, public_observation, strict_json
from .learner import ProtocolError, CapacityError, canonical

PHASE41_SOURCE_TREE = '9b0f880af84a0b1b69fd6aa9009ab738acd7dfad'
MODE = 'ora2-phase41-shadow-cycle-v1'
MAX_SNAPSHOT = 32 * 1024 * 1024
MAX_JOURNAL_TAIL = 4 * 1024 * 1024
STIMULUS = 'ora2 isolated Phase 41 continuity check'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_identity(root: Path) -> dict:
    """Verify each tracked Phase 41 source byte; do not certify a commit label alone."""
    root = root.resolve()
    tree = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD:src'], timeout=10).decode().strip()
    if tree != PHASE41_SOURCE_TREE:
        raise ProtocolError('unchanged Phase 41 source tree required')
    listing = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-rz', 'HEAD', 'src'], timeout=10)
    files = {}
    for entry in listing.split(b'\0'):
        if not entry:
            continue
        metadata, encoded_path = entry.split(b'\t', 1)
        mode, kind, expected = metadata.decode().split()
        name = encoded_path.decode()
        path = root / name
        if kind != 'blob' or mode not in ('100644', '100755') or path.is_symlink() or not path.is_file():
            raise ProtocolError('unsupported Phase 41 source member')
        raw = path.read_bytes()
        if blob_id(raw) != expected:
            raise ProtocolError('Phase 41 source bytes changed')
        files[name] = sha(raw)
    actual = {p.relative_to(root).as_posix() for p in (root / 'src').rglob('*.py')}
    if actual != {p for p in files if p.endswith('.py')}:
        raise ProtocolError('unexpected or missing Python source')
    own = {p.name: sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}
    return {'phase41_tree': tree, 'source_files': files, 'ora2_files': own,
            'python': list(sys.version_info[:3])}


def command_plan(work: Path, root: Path) -> list[tuple[str, list[str]]]:
    """Original six CLI stages; cognition, writes to source, and dispatch are absent."""
    prefix = [sys.executable, '-B', '-s', '-m', 'agenttest', '--state', str(work / 'organism.json')]
    return [
        ('cycle', prefix + ['cycle', '--planning-lab', '--grounded-experiments-only',
                            '--self-observe', '--root', str(root), '--stimulus', STIMULUS]),
        ('propose', prefix + ['propose', '--output', str(work / 'next_experiment.json')]),
        ('propose-change', prefix + ['propose-change', '--output', str(work / 'next_change.json')]),
        ('review-before', prefix + ['review-change', '--output', str(work / 'next_change_review.json')]),
        ('diagnose-change', prefix + ['diagnose-change', '--output', str(work / 'next_change_diagnostic.json')]),
        ('review-after', prefix + ['review-change', '--output', str(work / 'next_change_review.json')]),
    ]


def execute_phase41(raw: bytes, root: Path) -> dict:
    """Return staged results. Nothing is published and no caller input is written."""
    if not isinstance(raw, bytes) or len(raw) > MAX_SNAPSHOT:
        raise CapacityError('bounded snapshot bytes required')
    with tempfile.TemporaryDirectory(prefix='ora2-phase41-cycle-') as directory:
        work = Path(directory)
        (work / 'organism.json').write_bytes(raw)
        env = os.environ.copy()
        env.update(PYTHONPATH=str(root.resolve() / 'src'), PYTHONNOUSERSITE='1',
                   PYTHONDONTWRITEBYTECODE='1', PYTHONPYCACHEPREFIX=str(work / 'unused-cache'))
        env.pop('OPENAI_API_KEY', None)
        env.pop('AGENTTEST_MODEL', None)
        outputs = {}
        for name, command in command_plan(work, root.resolve()):
            completed = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                       check=False, timeout=90)
            if completed.returncode:
                raise ProtocolError('isolated Phase 41 stage failed: ' + name + ': ' + completed.stderr.decode(errors='replace')[-2000:])
            outputs[name] = strict_json(completed.stdout)
        snapshot_path, journal_path = work / 'organism.json', work / 'journal.jsonl'
        if snapshot_path.stat().st_size > MAX_SNAPSHOT or journal_path.stat().st_size > MAX_JOURNAL_TAIL:
            raise CapacityError('staged lifecycle output limit')
        snapshot, journal = snapshot_path.read_bytes(), journal_path.read_bytes()
        events = [strict_json(line) for line in journal.splitlines()]
        if not journal.endswith(b'\n') or not events:
            raise ProtocolError('complete staged journal required')
        sidecars = {p.name: p.read_text() for p in sorted(work.glob('next_*.json'))}
        return {'snapshot': snapshot, 'journal': journal, 'outputs': outputs, 'sidecars': sidecars}


def forecast_menu(agent) -> dict:
    return {a: agent.predict(a).public() for a in ACTIONS}


def learn_cycle(agent, before: dict, after: dict, predictions: dict) -> dict:
    """Learn only the actual new same-world row, never claim planner choices as ours."""
    start, end = before['planning_lab'], after['planning_lab']
    prior = start['transition_observations']
    rows = end['transition_observations']
    if rows[:len(prior)] != prior or len(rows) < len(prior):
        raise ProtocolError('historical transition prefix changed')
    added = rows[len(prior):]
    existing_ids = {(row.get('source'), row.get('source_id')) for row in prior}
    if any((row.get('source'), row.get('source_id')) in existing_ids for row in added):
        raise ProtocolError('a new cycle cannot reuse a historical transition identity')
    if len(added) > 1:
        raise ProtocolError('more than one planner transition in one ordinary cycle')
    report = {'action_owner': 'unchanged_phase41_planner', 'ora2_choices': 0,
              'transition_records': added, 'position_before': list(start['position']),
              'position_after': list(end['position']),
              'new_planner_transitions': len(added), 'prospectively_scored': False,
              'learning_event': None, 'reason': 'no_world_transition'}
    if added:
        row = added[0]
        # Full public record validation, using the unchanged historical adapter.
        project(after)
        if row.get('world_version') != WORLD:
            report['reason'] = 'other_world_not_trained'
        else:
            expected_before = public_observation(row['before'])
            expected_after = public_observation(row['after'])
            contiguous = agent.observation == canonical(expected_before)
            event = agent.inherit(expected_before, row['action'], expected_after,
                                  sequence_break=not contiguous)
            report['learning_event'] = event
            if row['before'] == start['position'] and contiguous:
                saved = predictions[row['action']]
                if event['choice']['forecast_sha256'] != sha(json.dumps(saved, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()):
                    raise ProtocolError('forecast was not the prediction made before Core')
                report['prospectively_scored'] = True
                report['reason'] = 'actual_planner_outcome_scored_then_learned'
            else:
                report['reason'] = 'different_start_exposure_only_not_prospective'
    current = public_observation(end['position'])
    if canonical(current) != agent.observation or (added and added[0].get('world_version') != WORLD):
        agent.reorient(current)
    return report


def run_cycle(raw: bytes, agent, root: Path, *, enabled: bool = False) -> dict:
    """Stage one full old lifecycle plus passive learning, with rollback on failure."""
    if enabled is not True:
        raise ProtocolError('explicit isolated-copy enablement required')
    import copy
    candidate = copy.deepcopy(agent)
    before = strict_json(raw)
    project(before)
    if candidate.observation != canonical(public_observation(before['planning_lab']['position'])):
        raise ProtocolError('learner is not at the current public location')
    source = source_identity(root)
    predictions = forecast_menu(candidate)  # before any Core or actuator call
    staged = execute_phase41(raw, root)
    after = strict_json(staged['snapshot'])
    project(after)
    if after.get('cycles') != before['cycles'] + 1 or after.get('identity') != before['identity']:
        raise ProtocolError('one cycle and unchanged identity required')
    if after.get('schema_version') != 24:
        raise ProtocolError('Phase 41 schema changed')
    events = [strict_json(line) for line in staged['journal'].splitlines()]
    cycles = [e for e in events if e.get('event') == 'cycle']
    if len(cycles) != 1 or cycles[0].get('cycle') != after['cycles']:
        raise ProtocolError('one matching completed cycle journal event required')
    report = learn_cycle(candidate, before, after, predictions)
    if source_identity(root) != source:
        raise ProtocolError('source changed during the cycle')
    staged.update(mode=MODE, temporal=report, forecasts=predictions,
                  learner=candidate, source=source, cycle=after['cycles'])
    return staged
