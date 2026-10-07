"""Isolated exact-source loading probes; no executive world transitions."""
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class SourceLoadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='executive-source-proof-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'copy'
        shutil.copytree(ROOT/'src',self.root/'src',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'experiments',self.root/'experiments',ignore=shutil.ignore_patterns('__pycache__'))
        self.env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(self.root/'src')+os.pathsep+str(self.root/'experiments'))

    def run_probe(self,code):
        result=subprocess.run([sys.executable,'-B','-c',code],cwd=self.root,env=self.env,text=True,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_preloaded_dependency_refused_instead_of_certifying_disk(self):
        self.run_probe("""
import open_object_world_challenge as old
from pathlib import Path
p=Path(old.__file__);p.write_text(p.read_text().replace('BOUNDS = 2','BOUNDS = 3'))
try:
 import inquiry_executive.contracts
except RuntimeError as error:
 assert 'fresh interpreter' in str(error)
else:raise AssertionError('preloaded old dependency was certified')
""")

    def test_disk_mutation_after_package_import_refused(self):
        self.run_probe("""
import inquiry_executive
from pathlib import Path
p=Path('experiments/open_object_world_challenge.py')
p.write_text(p.read_text().replace('BOUNDS = 2','BOUNDS = 3'))
from inquiry_executive.contracts import code_manifest,Conflict
import open_object_world_challenge as loaded
assert loaded.BOUNDS == 2
try:code_manifest()
except Conflict:pass
else:raise AssertionError('disk change was certified')
""")

    def test_dependency_stale_bytecode_ignored_by_source_loader(self):
        p=self.root/'experiments/open_object_world_challenge.py'
        original=p.read_bytes();info=p.stat()
        py_compile.compile(str(p),doraise=True)
        changed=original.replace(b'BOUNDS = 2',b'BOUNDS = 3')
        self.assertEqual(len(changed),len(original));p.write_bytes(changed)
        os.utime(p,ns=(info.st_atime_ns,info.st_mtime_ns))
        self.run_probe("""
import inquiry_executive
import open_object_world_challenge as loaded
from inquiry_executive.contracts import code_manifest
assert loaded.BOUNDS == 3, 'stale dependency cache was used'
code_manifest()
""")

    def test_valid_stale_bootstrap_cache_fails_closed(self):
        p=self.root/'experiments/inquiry_executive/__init__.py'
        original=p.read_bytes();info=p.stat()
        py_compile.compile(str(p),doraise=True)
        changed=original.replace(b'Warm Ora/Challenge',b'Old. Ora/Challenge')
        self.assertNotEqual(changed,original);self.assertEqual(len(changed),len(original))
        p.write_bytes(changed);os.utime(p,ns=(info.st_atime_ns,info.st_mtime_ns))
        self.run_probe("""
import inquiry_executive
assert 'Warm Ora/Challenge' in inquiry_executive.__doc__, 'test did not load the valid stale bootstrap cache'
from inquiry_executive.contracts import code_manifest,Conflict
try:code_manifest()
except Conflict as error:assert 'bootstrap bytecode cache' in str(error)
else:raise AssertionError('cached bootstrap silently certified')
""")
