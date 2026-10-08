"""Single-use child interpreter: explicit action hook in unchanged Phase 41 Core.

This process-local hook is never installed in a live process. The parent runs it
only in a disposable directory and commits its outputs transactionally. The five
remaining lifecycle commands continue to use the unchanged original CLI.
"""
from __future__ import annotations

import json
from pathlib import Path

from .baseline import actuator, strict_json
from .control import apply_selected
from .learner import ProtocolError
from .lifecycle import STIMULUS, sha, source_identity


def run(snapshot: Path, decision_path: Path, receipt_path: Path, root: Path) -> dict:
    root = root.resolve()
    for path in (snapshot, decision_path, receipt_path):
        if path.is_symlink() or path.resolve().is_relative_to(root):
            raise ProtocolError('owned worker requires disposable out-of-checkout paths')
    source = source_identity(root)
    payload = strict_json(decision_path.read_bytes())
    if sha(snapshot.read_bytes()) != payload.pop('snapshot_sha256', None):
        raise ProtocolError('decision snapshot mismatch')
    from agenttest import core as module
    from agenttest.planning_lab import _rebuild_model
    from agenttest.perception import repository_snapshot
    from agenttest.state import StateStore
    execute = actuator()
    events = []

    def selected_step(state):
        if events:
            raise ProtocolError('second action dispatch in one owned cycle')
        result = apply_selected(state, payload, execute, _rebuild_model)
        events.append(result)
        return result

    class OwnedCore(module.AgentCore):
        def _remember(self, state, cycle, now, kind, content, concepts):
            if kind == 'planning_lab':
                if len(events) != 1:
                    raise ProtocolError('owned memory before owned action')
                event = events[0]
                event['episode_id'] = f"E{len(state['episodes']) + 1:06d}"
                kind, content = 'ora2_action', json.dumps(event, sort_keys=True)
                concepts = ['ora2', 'evidence_selected_action', 'movement']
            return super()._remember(state, cycle, now, kind, content, concepts)

    prior = module.step_planning_lab
    module.step_planning_lab = selected_step
    try:
        result = OwnedCore(StateStore(snapshot)).cycle(
            stimulus=STIMULUS, observation=repository_snapshot(root),
            cognition=False, strict_experiment_admission=True, planning_lab=True)
    finally:
        module.step_planning_lab = prior
    if len(events) != 1 or source_identity(root) != source:
        raise ProtocolError('owned dispatch or source identity failure')
    receipt_path.write_text(json.dumps(events[0], sort_keys=True) + '\n')
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Internal disposable Ora 2 action worker')
    for name in ('snapshot', 'decision', 'receipt', 'root'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.snapshot, args.decision, args.receipt, args.root), sort_keys=True))


if __name__ == '__main__':
    main()
