"""Predeclared eight-cycle owned-action integration; not a policy-benefit study."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ora2.baseline import STATE_BLOB, JOURNAL_BLOB, blob_id, strict_json
from ora2.lifecycle_store import LifecycleSession

ROOT = Path(__file__).resolve().parents[1]
OWNERS = ('phase41', 'phase41', 'phase41', 'phase41', 'ora2', 'phase41', 'phase41', 'ora2')


class OwnedPinnedTests(unittest.TestCase):
    def test_eight_declared_cycles_with_real_learner_choices_and_return_to_planner(self):
        snapshot, journal = ROOT/'state/organism.json', ROOT/'state/journal.jsonl'
        available = snapshot.is_file() and journal.is_file()
        if not available and os.getenv('GITHUB_ACTIONS') != 'true':
            self.skipTest('complete checkpoint absent locally; hosted CI must execute')
        self.assertTrue(available)
        from test_ora2_lifecycle_pinned import baseline_tick, normalized
        raw, history = snapshot.read_bytes(), journal.read_bytes()
        self.assertEqual(blob_id(raw), STATE_BLOB)
        self.assertEqual(blob_id(history), JOURNAL_BLOB)
        initial = strict_json(raw)
        reports=[]
        with tempfile.TemporaryDirectory(prefix='ora2-owned-pinned-') as td:
            base=Path(td)/'comparator';base.mkdir()
            (base/'organism.json').write_bytes(raw);(base/'journal.jsonl').write_bytes(history)
            path=Path(td)/'candidate.sqlite'
            with LifecycleSession.create(path, ROOT, snapshot, journal, enabled=True,
                                         seed=17, cycle_limit=8, allow_ora2=True) as session:
                for index,owner in enumerate(OWNERS):
                    before=strict_json(session.db.execute('SELECT snapshot FROM current').fetchone()[0])
                    if index<4:ordinary=baseline_tick(base,ROOT)
                    result=session.tick(f'owned-integration-{index}', enabled=True, owner=owner)['result']
                    after=strict_json(session.db.execute('SELECT snapshot FROM current').fetchone()[0])
                    self.assertEqual(after['cycles'], initial['cycles']+index+1)
                    self.assertEqual(after['identity'], initial['identity'])
                    self.assertEqual(after['planning_lab']['transition_observations'][:len(initial['planning_lab']['transition_observations'])],
                                     initial['planning_lab']['transition_observations'])
                    self.assertEqual(after['episodes'][:len(initial['episodes'])],initial['episodes'])
                    self.assertGreater(len(after['episodes']),len(before['episodes']))
                    row={'cycle':after['cycles'],'owner':owner,'position':after['planning_lab']['position'],
                         'new_transitions':len(result['temporal']['transition_records']),
                         'ora2_choices':result['temporal']['ora2_choices'],
                         'episodes_added':len(after['episodes'])-len(before['episodes'])}
                    if index<4:
                        self.assertEqual(normalized(strict_json((base/'organism.json').read_bytes())),normalized(after))
                        self.assertEqual(normalized(ordinary),normalized(result['outputs']))
                        row['prefix_full_state_parity']=True
                    if owner=='ora2':
                        self.assertEqual(result['temporal']['ora2_choices'],1)
                        control=result['control']
                        self.assertEqual(control['choice'],result['temporal']['learning_event']['choice'])
                        self.assertEqual(after['planning_lab']['executions'],before['planning_lab']['executions'])
                        self.assertEqual(after['planning_lab']['objective_realizations'],before['planning_lab']['objective_realizations'])
                        old_plan_id=before['planning_lab'].get('active_plan_id')
                        if old_plan_id:
                            old_plan=next(p for p in before['planning_lab']['plans'] if p['id']==old_plan_id)
                            new_plan=next(p for p in after['planning_lab']['plans'] if p['id']==old_plan_id)
                            self.assertEqual(old_plan['next_step_index'],new_plan['next_step_index'])
                            self.assertEqual(new_plan['status'],'invalidated')
                        row.update(action=control['action'], plan_interruption=control['plan_interruption'],
                                   precommit_cancellation=control['precommit_cancellation'],
                                   goal_reached=control['goal_reached'], episode_id=control['episode_id'])
                    elif index>4:
                        self.assertEqual(result['temporal']['ora2_choices'],0)
                        self.assertEqual(len(after['planning_lab'].get('ora2_executions',[])),
                                         len(before['planning_lab'].get('ora2_executions',[])))
                    reports.append(row)
                status=session.status()
                self.assertEqual(status['completed_cycles'],8)
                self.assertEqual(status['ora2_choices'],2)
                # Fixed intermediate steps must actually exercise a plan interruption
                # and at least one subsequent planner action, not merely an idle loop.
                self.assertTrue(reports[4]['plan_interruption'])
                self.assertGreater(sum(r['new_transitions'] for r in reports[5:7]),0)
                with patch('ora2.lifecycle_store.run_cycle', side_effect=AssertionError('must not run')):
                    self.assertTrue(session.tick('owned-integration-4',enabled=True,owner='ora2')['replayed'])
                    self.assertEqual(session.status(),status)
                self.assertEqual(session.db.execute('SELECT snapshot,journal FROM origin').fetchone(),(raw,history))
            with LifecycleSession(path, ROOT) as reopened:
                self.assertEqual(reopened.status(),status)
            env=os.environ.copy();env.update(PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT),PYTHONDONTWRITEBYTECODE='1')
            cold=subprocess.run([sys.executable,'-B','-s','-m','ora2.lifecycle_store','status',
                                 '--database',str(path),'--root',str(ROOT)],
                                env=env,cwd=ROOT,capture_output=True,timeout=90)
            self.assertEqual(cold.returncode,0,cold.stderr.decode())
            self.assertEqual(strict_json(cold.stdout),status)
        self.assertEqual(snapshot.read_bytes(),raw);self.assertEqual(journal.read_bytes(),history)
        print('ORA2_OWNED_CYCLE_INTEGRATION '+json.dumps(dict(
            origin_cycle=initial['cycles'], declared_owners=list(OWNERS), cycles=8,
            learner_selected_actions=2, live_actions=0, records=reports,
            separate_process_restart=True, source_archive_unchanged=True,
            scope='developer-scheduled control opportunities; no autonomous timing or new benefit claim'
        ),sort_keys=True),flush=True)


if __name__=='__main__':unittest.main()
