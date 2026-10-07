import hashlib
import importlib
import py_compile
from pathlib import Path
import sys
import tempfile
import unittest
from ora_study.source_bootstrap import PinnedSources, CapturedBytes

RESULTS=Path(__file__).resolve().parents[2]/"policy-study-results"
class SourceOnlyLoading(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=RESULTS,prefix="source-")
        self.root=Path(self.tmp.name)
        self.package="authored_source_fixture"
        self.finder=None
        (self.root/"__init__.py").write_text('FIXTURE_ONLY = True\n')
        (self.root/"payload.py").write_text('VALUE = "old-bytecode"\n')
        py_compile.compile(str(self.root/"payload.py"),doraise=True)
        (self.root/"payload.py").write_text('VALUE = "captured-source"\n')
        self.expected={str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob("*.py")}
    def tearDown(self):
        if self.finder in sys.meta_path:
            sys.meta_path.remove(self.finder)
        for name in list(sys.modules):
            if name==self.package or name.startswith(self.package+"."):
                del sys.modules[name]
        self.tmp.cleanup()
    def test_stale_bytecode_is_preserved_but_never_used(self):
        caches=list((self.root/"__pycache__").iterdir())
        before={p.name:p.read_bytes() for p in caches}
        self.finder=PinnedSources(self.root,self.expected,package=self.package)
        self.finder.install()
        module=importlib.import_module(self.package+".payload")
        self.assertEqual(module.VALUE,"captured-source")
        self.assertIsInstance(module.__loader__,CapturedBytes)
        self.assertEqual(before,{p.name:p.read_bytes() for p in caches})
    def test_unknown_sourceless_module_cannot_fall_through(self):
        self.finder=PinnedSources(self.root,self.expected,package=self.package)
        self.finder.install()
        importlib.import_module(self.package)
        extra=self.root/"unreviewed.py"
        extra.write_text('UNREVIEWED = True\n')
        py_compile.compile(str(extra),cfile=str(self.root/"unreviewed.pyc"),doraise=True)
        extra.unlink()
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module(self.package+".unreviewed")
    def test_symlink_root_refuses_before_resolution(self):
        alias=self.root/"alias"
        alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(RuntimeError):
            PinnedSources(alias,self.expected,package=self.package)
    def test_changed_source_or_membership_rejects(self):
        (self.root/"payload.py").write_text('VALUE = "changed"\n')
        with self.assertRaises(RuntimeError):
            PinnedSources(self.root,self.expected,package=self.package)
        (self.root/"extra.py").write_text('VALUE = 1\n')
        with self.assertRaises(RuntimeError):
            PinnedSources(self.root,self.expected,package=self.package)
    def test_warm_module_refuses(self):
        sys.modules[self.package]=object()
        with self.assertRaises(RuntimeError):
            PinnedSources(self.root,self.expected,package=self.package)
    def test_loader_uses_captured_not_later_changed_bytes(self):
        self.finder=PinnedSources(self.root,self.expected,package=self.package)
        self.finder.install()
        (self.root/"payload.py").write_text('VALUE = "changed-after-capture"\n')
        module=importlib.import_module(self.package+".payload")
        self.assertEqual(module.VALUE,"captured-source")
if __name__ == "__main__":
    unittest.main()
