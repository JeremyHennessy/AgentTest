"""Fixed sixteen-cycle timing integration. A null opportunity count is valid."""
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


class TimedPinnedTests(unittest.TestCase):
    def test_sixteen_state_selected_cycles_and_cold_restart(self):
        snapshot, journal = ROOT/'state/organism.json', ROOT/'state/journal.jsonl'
        available = snapshot.is_file() and journal.is_file()
        if not available and os.getenv('GITHUB_ACTIONS') != 'true':
            self.skipTest('complete checkpoint absent locally; hosted CI must execute')
        self.assertTrue(available)
        raw, history = snapshot.read_bytes(), journal.read_bytes()
        self.assertEqual(blob_id(raw), STATE_BLOB); self.assertEqual(blob_id(history), JOURNAL_BLOB)
        initial = strict_json(raw); records = []; previous_owner = None
        with tempfile.TemporaryDirectory(prefix='ora2-timed-integration-') as directory:
            database = Path(directory)/'session.sqlite'
            with LifecycleSession.create(database, ROOT, snapshot, journal, enabled=True,
                    seed=17, cycle_limit=16, allow_ora2=True, timing_policy='progress') as session:
                for i in range(16):
                    before = strict_json(session.db.execute('SELECT snapshot FROM current').fetchone()[0])
                    result = session.tick('timed-'+str(i), enabled=True, owner='auto')['result']
                    after = strict_json(session.db.execute('SELECT snapshot FROM current').fetchone()[0])
                    timing = result['timing']; owner = timing['owner']; lab = before['planning_lab']
                    if lab.get('active_plan_id') or lab.get('active_objective_realization_id') or previous_owner=='ora2':
                        self.assertEqual(owner, 'phase41')
                    if owner=='ora2':
                        control = result['control']
                        self.assertIsNone(control['plan_interruption'])
                        self.assertIsNone(control['precommit_cancellation'])
                        self.assertEqual(control['choice'], result['temporal']['learning_event']['choice'])
                        self.assertEqual(result['temporal']['ora2_choices'], 1)
                    self.assertEqual(after['identity'],initial['identity'])
                    self.assertEqual(after['episodes'][:len(initial['episodes'])],initial['episodes'])
                    self.assertEqual(after['planning_lab']['transition_observations'][:len(initial['planning_lab']['transition_observations'])],
                                     initial['planning_lab']['transition_observations'])
                    old_goals={g['id']:g for g in lab['goals']}
                    new_goals={g['id']:g for g in after['planning_lab']['goals']}
                    self.assertTrue(old_goals.keys()<=new_goals.keys())
                    for key in old_goals:
                        self.assertEqual(old_goals[key]['target'],new_goals[key]['target'])
                    records.append({'cycle':after['cycles'],'owner':owner,'reason':timing['reason'],
                        'eligible':timing['eligible'],'position':after['planning_lab']['position'],
                        'action':result.get('control',{}).get('action'),
                        'transitions':len(result['temporal']['transition_records'])})
                    previous_owner = owner
                status=session.status()
                self.assertEqual(status['completed_cycles'],16)
                with patch('ora2.lifecycle_store.run_cycle',side_effect=AssertionError('cannot execute on retry')):
                    self.assertTrue(session.tick('timed-0',enabled=True,owner='auto')['replayed'])
                    self.assertEqual(session.status(),status)
                self.assertEqual(session.db.execute('SELECT snapshot,journal FROM origin').fetchone(),(raw,history))
            with LifecycleSession(database,ROOT) as reopened:
                self.assertEqual(reopened.status(),status)
            env=os.environ.copy();env.update(PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT),PYTHONDONTWRITEBYTECODE='1')
            cold=subprocess.run([sys.executable,'-B','-s','-m','ora2.lifecycle_store','status',
                '--database',str(database),'--root',str(ROOT)],cwd=ROOT,env=env,capture_output=True,timeout=90)
            self.assertEqual(cold.returncode,0,cold.stderr.decode())
            self.assertEqual(strict_json(cold.stdout),status)
        self.assertEqual(snapshot.read_bytes(),raw);self.assertEqual(journal.read_bytes(),history)
        print('ORA2_TIMING_INTEGRATION '+json.dumps({'cycles':16,'seed':17,'records':records,
            'learner_selected_actions':sum(r['owner']=='ora2' for r in records),
            'live_actions':0,'caller_selected_turns':0,'rule':'authored conservative boundary timing',
            'source_archive_unchanged':True,'separate_process_restart':True,
            'learning_benefit_claim':False},sort_keys=True),flush=True)


if __name__=='__main__':unittest.main()
