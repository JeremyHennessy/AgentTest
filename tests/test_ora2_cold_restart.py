from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from ora2.learner import Agent
from ora2.storage import ExperienceLog

ROOT = Path(__file__).parents[1]


class ColdRestartTests(unittest.TestCase):
    def child(self, code, *args):
        environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([sys.executable, '-c', code, *map(str,args)], env=environment,
                              text=True, capture_output=True, timeout=10)

    def test_separate_process_reconstructs_next_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'memory.sqlite'
            agent = Agent({'sensor': 0}, seed=17)
            with ExperienceLog(path, create=agent) as log:
                for i in range(40):
                    log.append(agent.observe(agent.choose(['a','b']), {'sensor':i%3}))
            expected = agent.choose(['a','b']).record()
            child = self.child("from ora2.storage import ExperienceLog; import sys,json; s=ExperienceLog(sys.argv[1]); print(json.dumps(s.restore().choose(['a','b']).record())); s.close()", path)
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertEqual(json.loads(child.stdout), expected)

    def crash_case(self, location):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'memory.sqlite'
            event_path = Path(temp)/'event.json'
            agent = Agent(0, seed=3)
            with ExperienceLog(path, create=agent):
                pass
            event = agent.observe(agent.choose(['a']), 1)
            event_path.write_text(json.dumps(event))
            code = '''
import json,os,sys
from ora2.storage import ExperienceLog
log=ExperienceLog(sys.argv[1])
real=log._db
class Crash:
    def __getattr__(self,name): return getattr(real,name)
    def execute(self,query,*args):
        result=real.execute(query,*args)
        if (sys.argv[3]=='before_commit' and query.startswith('INSERT INTO experience')) or (sys.argv[3]=='after_commit' and query=='COMMIT'):
            os._exit(17)
        return result
log._db=Crash()
log.append(json.load(open(sys.argv[2])))
'''
            child=self.child(code,path,event_path,location)
            self.assertEqual(child.returncode,17,child.stderr)
            with ExperienceLog(path) as log:
                expected_steps = int(location=='after_commit')
                self.assertEqual(log.restore().steps,expected_steps)
                self.assertEqual(log.append(event),location=='before_commit')
                self.assertEqual(log.restore().steps,1)

    def test_process_exit_before_commit_retains_previous_history(self):
        self.crash_case('before_commit')

    def test_process_exit_after_commit_lost_ack_does_not_duplicate(self):
        self.crash_case('after_commit')

if __name__=='__main__': unittest.main()
