"""Portable differential proofs for transaction-local JSON copy elimination."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CopyElisionProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary=tempfile.TemporaryDirectory(prefix="ora-copy-elision-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root=Path(temporary.name)
        bootstrap=ROOT/'experiments/grounded_policy_v2/__init__.py'
        assignment=next(node for node in ast.parse(bootstrap.read_text()).body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='_ADAPTERS' for target in node.targets))
        adapters=ast.literal_eval(assignment.value)
        files=sorted(list((ROOT/'src/agenttest').rglob('*.py'))+
            list((ROOT/'experiments/grounded_policy_v2').rglob('*.py'))+
            [ROOT/'experiments'/(name+'.py') for name in adapters])
        for variant in ('baseline','candidate'):
            for source in files:
                target=cls.root/variant/source.relative_to(ROOT)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,target)
        executive=cls.root/'baseline/experiments/grounded_policy_v2/executive.py'
        text=executive.read_text()
        assert text.count('        prefix=dict(state)\n')==1
        executive.write_text(text.replace('        prefix=dict(state)\n','        prefix=deepcopy(state)\n'))
        primitives=cls.root/'baseline/experiments/grounded_policy_v2/primitives.py'
        text=primitives.read_text()
        optimized='def encoded(value):\n    envelope = {k: v for k, v in value.items() if k != "seal"}\n    envelope["seal"] = digest(envelope)\n    return canonical(envelope) + b"\\n"\n'
        assert text.count(optimized)==1
        text=text.replace(optimized,'def encoded(value):\n    return canonical(seal(value)) + b"\\n"\n')
        optimized='value.get("seal") != digest({k: v for k, v in value.items() if k != "seal"})'
        assert text.count(optimized)==1
        primitives.write_text(text.replace(optimized,'value.get("seal") != seal(value)["seal"]'))
        cls.runs={}
        cases=ROOT/'tests/grounded_policy_v2_cases'
        for index,variant in enumerate(('baseline','candidate')):
            result=subprocess.run([sys.executable,'-I','-S','-B',str(cases/'copy_elision_probe.py'),
                str(cls.root/variant),str(cls.root/('variant'+str(index))),str(cases/'authored_d2_validation_recipe.json')],
                env={'LANG':'C','LC_ALL':'C'},capture_output=True,text=True,timeout=90)
            if result.returncode:
                raise AssertionError(result.stderr or result.stdout)
            cls.runs[variant]=json.loads(result.stdout)
        print('COPY_ELISION_COUNTS '+json.dumps({name:run['counts'] for name,run in cls.runs.items()},sort_keys=True))

    def test_only_three_sites_and_owned_copies_unchanged(self):
        changed=[]
        for path in (self.root/'baseline').rglob('*.py'):
            relative=path.relative_to(self.root/'baseline')
            if path.read_bytes()!=(self.root/'candidate'/relative).read_bytes():changed.append(str(relative))
        self.assertEqual(sorted(changed),['experiments/grounded_policy_v2/executive.py','experiments/grounded_policy_v2/primitives.py'])
        def function(variant,file,name):
            module=ast.parse((self.root/variant/'experiments/grounded_policy_v2'/file).read_text())
            return ast.dump(next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name==name))
        for file,name in (('primitives.py','seal'),('executive.py','_stage_selection')):
            self.assertEqual(function('baseline',file,name),function('candidate',file,name))

    def test_primitive_bytes_errors_nonmutation_and_isolation(self):
        self.assertEqual(self.runs['baseline']['results']['primitives'],self.runs['candidate']['results']['primitives'])
        self.assertEqual(len(self.runs['candidate']['results']['primitives']),18)

    def test_real_lifecycle_null_capacity_and_cancellation_acceptance(self):
        for variant,run in self.runs.items():
            self.assertEqual(run['transition_calls'],0)
            self.assertEqual(run['producer_calls'],0)
            self.assertEqual(run['selector_calls'],0)
            for mode in ('retain_first','withhold_first'):
                self.assertEqual([row['revision'] for row in run['results'][mode]],list(range(7)))
            for key in ('stage_isolation','policy_null','action_capacity_null','cancelled'):
                self.assertTrue(run['results'][key])
            self.assertEqual(run['results']['byte_capacity'],[{'offset':0,'status':'selected'},{'offset':-1,'status':'capacity_null'}])
        self.assertEqual(self.runs['baseline']['results'],self.runs['candidate']['results'])

    def test_tampering_and_direct_default_rejections_match(self):
        self.assertEqual(self.runs['baseline']['results']['tampering'],self.runs['candidate']['results']['tampering'])
        self.assertEqual(len(self.runs['candidate']['results']['tampering']),7)
        self.assertEqual(self.runs['baseline']['counts'],self.runs['candidate']['counts'])


if __name__=='__main__':
    result=unittest.main(verbosity=2,exit=False).result
    if hasattr(CopyElisionProof,'runs'):
        print(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun,'runs':CopyElisionProof.runs},sort_keys=True))
    sys.exit(0 if result.wasSuccessful() else 1)
