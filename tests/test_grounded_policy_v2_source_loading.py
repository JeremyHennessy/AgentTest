"""Copied-tree source isolation controls with zero world/Core transitions.

Each control uses a fresh, bytecode-disabled interpreter. The only capsule
fixture is a v1 cycle-zero world, one initial observation, and empty Ora input;
no historical state, inquiry selection, experiment, or world action is run.
"""
from __future__ import annotations

import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = (
    "challenge_action_authority",
    "challenge_shadow_recorder",
    "challenge_shadow_epistemic_selector",
    "native_observe_inquire_integration",
    "normalized_inquiry_objectives",
    "open_object_world_challenge",
    "open_object_world_challenge_explorer",
)


class GroundedPolicySourceLoadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="grounded-policy-source-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "copy"
        for folder in ("src", "experiments"):
            shutil.copytree(
                ROOT / folder,
                self.root / folder,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        self.env = dict(
            os.environ,
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=os.pathsep.join(
                str(self.root / folder) for folder in ("src", "experiments")
            ),
        )

    def run_source_check(self, code):
        result = subprocess.run(
            [sys.executable, "-B", "-c", textwrap.dedent(code)],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def add_source(self, relative, payload=b"VALUE = 'captured'\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def stale_cache(self, relative, before, after):
        path = self.root / relative
        original = path.read_bytes()
        changed = original.replace(before, after)
        self.assertNotEqual(original, changed)
        self.assertEqual(len(original), len(changed))
        info = path.stat()
        py_compile.compile(str(path), doraise=True)
        path.write_bytes(changed)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))

    def test_manifest_is_exact_separate_recursive_source_closure(self):
        # Unused nested modules still belong to the package's source identity.
        self.add_source("experiments/grounded_policy_v2/nested/__init__.py")
        self.add_source("experiments/grounded_policy_v2/nested/unused.py")
        self.add_source("src/agenttest/nested_source_check/__init__.py")
        self.add_source("src/agenttest/nested_source_check/unused.py")
        output = self.run_source_check("""
            import grounded_policy_v2
            import json
            import sys
            from grounded_policy_v2.contracts import code_manifest
            manifest = code_manifest()
            assert type(manifest) is dict
            assert not any(name == 'inquiry_executive' or
                           name.startswith('inquiry_executive.')
                           for name in sys.modules)
            print(json.dumps(manifest, sort_keys=True))
        """)
        files = list((self.root / "src/agenttest").rglob("*.py"))
        files += list((self.root / "experiments/grounded_policy_v2").rglob("*.py"))
        files += [self.root / "experiments" / (name + ".py") for name in ADAPTERS]
        expected = {
            str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        }
        self.assertEqual(json.loads(output), expected)
        self.assertFalse(any("inquiry_executive" in name for name in expected))

    def numerical_copy(self):
        import sysconfig
        import importlib.util
        numerical=self.root/'numerical-runtime';numerical.mkdir()
        standard=Path(sysconfig.get_path('stdlib'))
        for name in ('fractions','decimal','numbers'):
            shutil.copyfile(standard/(name+'.py'),numerical/(name+'.py'))
        extension=importlib.util.find_spec('_decimal')
        if extension.origin not in ('built-in','frozen'):
            (numerical/'lib-dynload').mkdir()
            shutil.copyfile(extension.origin,numerical/'lib-dynload'/Path(extension.origin).name)
        bootstrap=self.root/'experiments/grounded_policy_v2/__init__.py'
        original=bootstrap.read_text()
        needle="_STDLIB=Path(sysconfig.get_path('stdlib')).resolve()"
        self.assertIn(needle,original)
        bootstrap.write_text(original.replace(needle,'_STDLIB=Path('+repr(str(numerical))+').resolve()'))
        return numerical

    def test_preloaded_numerical_dependencies_fail_closed(self):
        for module in ('fractions','decimal','numbers','_decimal','_pydecimal'):
            with self.subTest(module=module):
                self.run_source_check(f"""
                    import importlib
                    importlib.import_module({module!r})
                    try:import grounded_policy_v2
                    except RuntimeError as error:assert 'fresh interpreter' in str(error)
                    else:raise AssertionError('warm numerical module certified')
                """)

    def test_numeric_stale_bytecode_is_bypassed_by_captured_source(self):
        numerical=self.numerical_copy();p=numerical/'fractions.py'
        original=p.read_bytes();info=p.stat();py_compile.compile(str(p),doraise=True)
        changed=original.replace(b'na * db + da * nb',b'na * db - da * nb')
        self.assertNotEqual(changed,original);self.assertEqual(len(changed),len(original))
        p.write_bytes(changed);os.utime(p,ns=(info.st_atime_ns,info.st_mtime_ns))
        self.run_source_check("""
            import grounded_policy_v2
            from grounded_policy_v2.contracts import runtime_manifest
            from fractions import Fraction
            assert Fraction(1,2)+Fraction(1,3)==Fraction(1,6),'stale numerical pyc executed'
            runtime_manifest()
        """)

    def test_numeric_disk_mutation_after_capture_refused(self):
        numerical=self.numerical_copy()
        self.run_source_check(f"""
            import grounded_policy_v2
            from pathlib import Path
            p=Path({str(numerical/'fractions.py')!r})
            p.write_bytes(p.read_bytes().replace(b'na * db + da * nb',b'na * db - da * nb'))
            from fractions import Fraction
            assert Fraction(1,2)+Fraction(1,3)==Fraction(5,6),'captured numerical bytes replaced'
            try:
                from grounded_policy_v2.contracts import runtime_manifest
                runtime_manifest()
            except ValueError as error:assert 'numerical' in str(error)
            else:raise AssertionError('new disk code certified as old loaded code')
        """)

    def test_numeric_pythonpath_shadow_is_not_loaded(self):
        shadow=self.root/'fractions.py';shadow.write_text("raise AssertionError('unreviewed numerical shadow')\n")
        self.run_source_check("""
            import grounded_policy_v2
            from grounded_policy_v2.contracts import runtime_manifest
            import fractions
            from fractions import Fraction
            assert Fraction(1,2)+Fraction(1,3)==Fraction(5,6)
            assert fractions.__file__==runtime_manifest()['modules']['fractions']['path']
        """)

    def test_preloaded_agenttest_refused(self):
        self.run_source_check("""
            import agenttest
            try:
                import grounded_policy_v2
            except RuntimeError as error:
                assert 'fresh interpreter' in str(error)
            else:
                raise AssertionError('preloaded Ora dependency was certified')
        """)

    def test_preloaded_challenge_adapters_refused(self):
        for name in ADAPTERS:
            with self.subTest(module=name):
                self.run_source_check(f"""
                    import importlib
                    importlib.import_module({name!r})
                    try:
                        import grounded_policy_v2
                    except RuntimeError as error:
                        assert 'fresh interpreter' in str(error)
                    else:
                        raise AssertionError('preloaded Challenge dependency was certified')
                """)

    def test_preloaded_v1_package_refused_without_loading_dependencies(self):
        self.run_source_check("""
            import inquiry_executive
            import sys
            assert 'agenttest' not in sys.modules
            try:
                import grounded_policy_v2
            except RuntimeError as error:
                assert 'fresh interpreter' in str(error)
            else:
                raise AssertionError('preloaded v1 source loader was accepted')
        """)

    def test_lazy_modules_execute_captured_bytes_after_disk_mutation(self):
        # Both package and production sources are captured before their first
        # module import, so reopening their changed disk source is forbidden.
        self.add_source("src/agenttest/_source_loading_control.py")
        self.add_source("experiments/grounded_policy_v2/_source_loading_control.py")
        self.run_source_check("""
            import grounded_policy_v2
            import builtins
            import hashlib
            from pathlib import Path
            from grounded_policy_v2.contracts import code_manifest, Conflict
            captured = code_manifest()
            paths = (
                Path('src/agenttest/_source_loading_control.py'),
                Path('experiments/grounded_policy_v2/_source_loading_control.py'),
            )
            original = {str(path.resolve()): path.read_bytes() for path in paths}
            for path in paths:
                path.write_bytes(b"VALUE = 'mutated!'\\n")
            compiled = {}
            real_compile = builtins.compile
            def record_compile(source, filename, *args, **kwargs):
                if filename in original:
                    assert type(source) is bytes, 'pinned source was not compiled from bytes'
                    compiled[filename] = source
                return real_compile(source, filename, *args, **kwargs)
            builtins.compile = record_compile
            try:
                from agenttest import _source_loading_control as ora
                from grounded_policy_v2 import _source_loading_control as policy
            finally:
                builtins.compile = real_compile
            assert ora.VALUE == policy.VALUE == 'captured'
            assert compiled == original, 'loader did not compile captured source bytes'
            for path in paths:
                assert captured[str(path)] == hashlib.sha256(original[str(path.resolve())]).hexdigest()
            try:
                code_manifest()
            except Conflict:
                pass
            else:
                raise AssertionError('post-import source mutation was certified')
        """)

    def test_adapter_disk_mutation_after_package_import_refused(self):
        self.run_source_check("""
            import grounded_policy_v2
            from pathlib import Path
            path = Path('experiments/open_object_world_challenge.py')
            original = path.read_bytes()
            changed = original.replace(b'BOUNDS = 2', b'BOUNDS = 3')
            assert changed != original
            path.write_bytes(changed)
            from grounded_policy_v2.contracts import code_manifest, Conflict
            import open_object_world_challenge as loaded
            assert loaded.BOUNDS == 2, 'changed disk source was executed'
            try:
                code_manifest()
            except Conflict:
                pass
            else:
                raise AssertionError('disk change was certified')
        """)

    def test_added_source_members_refused(self):
        for relative in (
            "src/agenttest/_added_source.py",
            "experiments/grounded_policy_v2/_added_source.py",
            "experiments/grounded_policy_v2/nested/_added_source.py",
        ):
            with self.subTest(path=relative):
                try:
                    self.run_source_check(f"""
                        import grounded_policy_v2
                        from pathlib import Path
                        from grounded_policy_v2.contracts import code_manifest, Conflict
                        path = Path({relative!r})
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text('ADDED = True\\n')
                        try:
                            code_manifest()
                        except Conflict:
                            pass
                        else:
                            raise AssertionError('new source member was certified')
                    """)
                finally:
                    (self.root / relative).unlink(missing_ok=True)

    def test_deleted_source_members_refused(self):
        for relative in (
            "src/agenttest/_deleted_source.py",
            "experiments/grounded_policy_v2/_deleted_source.py",
            "experiments/grounded_policy_v2/nested/_deleted_source.py",
        ):
            with self.subTest(path=relative):
                self.add_source(relative)
                self.run_source_check(f"""
                    import grounded_policy_v2
                    from pathlib import Path
                    from grounded_policy_v2.contracts import code_manifest, Conflict
                    Path({relative!r}).unlink()
                    try:
                        code_manifest()
                    except Conflict:
                        pass
                    else:
                        raise AssertionError('deleted source member was certified')
                """)

    def test_dependency_stale_bytecode_ignored(self):
        self.stale_cache(
            "experiments/open_object_world_challenge.py", b"BOUNDS = 2", b"BOUNDS = 3"
        )
        self.run_source_check("""
            import grounded_policy_v2
            import open_object_world_challenge as loaded
            from grounded_policy_v2.contracts import code_manifest
            assert loaded.BOUNDS == 3, 'stale Challenge cache was executed'
            code_manifest()
        """)

    def test_agenttest_stale_bytecode_ignored(self):
        self.stale_cache("src/agenttest/__init__.py", b'"0.1.0"', b'"0.1.1"')
        self.run_source_check("""
            import grounded_policy_v2
            import agenttest
            from grounded_policy_v2.contracts import code_manifest
            assert agenttest.__version__ == '0.1.1', 'stale Ora cache was executed'
            code_manifest()
        """)

    def test_package_dependency_stale_bytecode_ignored(self):
        relative = "experiments/grounded_policy_v2/_source_loading_control.py"
        self.add_source(relative)
        self.stale_cache(relative, b"'captured'", b"'current!'")
        self.run_source_check("""
            import grounded_policy_v2
            from grounded_policy_v2 import _source_loading_control as loaded
            from grounded_policy_v2.contracts import code_manifest
            assert loaded.VALUE == 'current!', 'stale v2 dependency cache was executed'
            code_manifest()
        """)

    def test_valid_stale_bootstrap_bytecode_fails_closed(self):
        path = self.root / "experiments/grounded_policy_v2/__init__.py"
        path.write_bytes(path.read_bytes() + b"\n_SOURCE_TEST_MARKER = 'cache'\n")
        self.stale_cache(
            "experiments/grounded_policy_v2/__init__.py", b"'cache'", b"'fresh'"
        )
        self.run_source_check("""
            try:
                import grounded_policy_v2
            except RuntimeError as error:
                assert 'bytecode' in str(error)
            else:
                assert grounded_policy_v2._SOURCE_TEST_MARKER == 'cache', 'fixture did not load stale bootstrap'
                from grounded_policy_v2.contracts import code_manifest, Conflict
                try:
                    code_manifest()
                except Conflict as error:
                    assert 'bytecode' in str(error)
                else:
                    raise AssertionError('cached bootstrap was certified')
        """)

    def test_adjacent_bootstrap_bytecode_fails_closed(self):
        path = self.root / "experiments/grounded_policy_v2/__init__.py"
        py_compile.compile(str(path), cfile=str(path.with_suffix(".pyc")), doraise=True)
        self.run_source_check("""
            try:
                import grounded_policy_v2
            except RuntimeError as error:
                assert 'bytecode' in str(error)
            else:
                from grounded_policy_v2.contracts import code_manifest, Conflict
                try:
                    code_manifest()
                except Conflict as error:
                    assert 'bytecode' in str(error)
                else:
                    raise AssertionError('adjacent bootstrap cache was certified')
        """)

    def test_unrelated_v1_source_changes_do_not_change_v2_manifest(self):
        self.run_source_check("""
            import grounded_policy_v2
            import sys
            from pathlib import Path
            from grounded_policy_v2.contracts import code_manifest
            before = code_manifest()
            v1 = Path('experiments/inquiry_executive')
            (v1 / '__init__.py').write_text("raise AssertionError('v1 must not execute')\\n")
            (v1 / '_unrelated_added_source.py').write_text('UNRELATED = True\\n')
            (v1 / 'synthetic.py').unlink()
            assert code_manifest() == before
            assert not any(name == 'inquiry_executive' or
                           name.startswith('inquiry_executive.')
                           for name in sys.modules)
        """)

    def test_v1_manifest_and_frozen_capsule_survive_unrelated_v2_addition(self):
        # Establish the original v1 capsule with no v2 package present. Keep
        # all observations synthetic and at cycle zero; cap actions at zero.
        shutil.rmtree(self.root / "experiments/grounded_policy_v2")
        self.run_source_check("""
            import inquiry_executive
            import json
            from pathlib import Path
            import open_object_world_challenge as world_module
            def no_transition(*args, **kwargs):
                raise AssertionError('source isolation controls cannot run transitions')
            world_module.transition = no_transition
            from agenttest.core import AgentCore
            AgentCore.cycle = no_transition
            from inquiry_executive.contracts import code_manifest, profile
            from inquiry_executive.executive import InquiryExecutive
            root = Path.cwd()
            sources = root / 'synthetic-sources'
            research = root / 'source-only-research'
            sources.mkdir()
            research.mkdir()
            world = world_module.initial_world()
            values = dict(
                ora={}, world=world,
                observations=[dict(observation=world_module.observe_world(world), receipt=None)],
            )
            paths = {}
            for name, value in values.items():
                path = sources / (name + '.json')
                path.write_text(json.dumps(value))
                paths[name] = path
            executive = InquiryExecutive.create(
                research / 'frozen-v1.json', research_dir=research,
                source_paths=paths, enabled=True,
                limits=profile(max_decisions=1, max_actions=0),
            )
            state = executive.read()
            assert state['world']['cycle'] == 0
            assert state['world']['history'] == []
            assert state['revision'] == 0
            assert all(value == 0 for value in state['counters'].values())
            assert len(state['frames']) == 1
            manifest = code_manifest()
            assert state['identity']['code_manifest'] == manifest
            assert not any('grounded_policy_v2' in name for name in manifest)
            (root / 'v1-manifest-before.json').write_text(json.dumps(manifest, sort_keys=True))
        """)
        capsule = self.root / "source-only-research/frozen-v1.json"
        frozen_capsule = capsule.read_bytes()
        frozen_sources = {
            path: path.read_bytes() for path in (self.root / "synthetic-sources").glob("*.json")
        }
        frozen_v1 = {
            path: path.read_bytes()
            for path in (self.root / "experiments/inquiry_executive").rglob("*.py")
        }
        shutil.copytree(
            ROOT / "experiments/grounded_policy_v2",
            self.root / "experiments/grounded_policy_v2",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        self.add_source("experiments/grounded_policy_v2/_unrelated_added_source.py")
        self.run_source_check("""
            import inquiry_executive
            import json
            import sys
            from pathlib import Path
            import open_object_world_challenge as world_module
            def no_transition(*args, **kwargs):
                raise AssertionError('frozen v1 reopening cannot run transitions')
            world_module.transition = no_transition
            from agenttest.core import AgentCore
            AgentCore.cycle = no_transition
            from inquiry_executive.contracts import code_manifest
            from inquiry_executive.executive import InquiryExecutive
            root = Path.cwd()
            before = json.loads((root / 'v1-manifest-before.json').read_text())
            assert code_manifest() == before, 'unrelated v2 changed the v1 source closure'
            research = root / 'source-only-research'
            state = InquiryExecutive(
                research / 'frozen-v1.json', research_dir=research, enabled=True,
            ).read()
            assert state['identity']['code_manifest'] == before
            assert state['world']['cycle'] == 0
            assert state['revision'] == 0
            assert all(value == 0 for value in state['counters'].values())
            assert not any(name == 'grounded_policy_v2' or
                           name.startswith('grounded_policy_v2.')
                           for name in sys.modules)
        """)
        self.assertEqual(capsule.read_bytes(), frozen_capsule)
        for path, before in {**frozen_sources, **frozen_v1}.items():
            self.assertEqual(path.read_bytes(), before, str(path))


if __name__ == "__main__":
    unittest.main()
