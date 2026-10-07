"""Default-off research v2; import first in a fresh -B source-only interpreter.

A trusted local source-integrity boundary, not a hostile-Python sandbox. The
legacy inquiry_executive namespace is deliberately outside this closure.
"""
from __future__ import annotations
import hashlib
import importlib.abc
import importlib.util
import sys
import sysconfig
import importlib.machinery
from pathlib import Path

_NUMERICAL_NAMES=('fractions','decimal','numbers','_decimal','_pydecimal')
if any(name in sys.modules for name in _NUMERICAL_NAMES):
    raise RuntimeError('grounded policy v2 requires a fresh interpreter: import before numerical dependencies')
_STDLIB=Path(sysconfig.get_path('stdlib')).resolve()
_NUMERICAL_SOURCES={name:(_STDLIB/(name+'.py')).read_bytes() for name in ('fractions','decimal','numbers')}
_NUMERICAL_EXTENSION=importlib.machinery.BuiltinImporter.find_spec('_decimal')
if _NUMERICAL_EXTENSION is None:
    _NUMERICAL_EXTENSION=importlib.machinery.PathFinder.find_spec('_decimal',[str(_STDLIB/'lib-dynload')])
if _NUMERICAL_EXTENSION is None or _NUMERICAL_EXTENSION.origin not in ('built-in','frozen') and not Path(_NUMERICAL_EXTENSION.origin).resolve().is_relative_to(_STDLIB):
    raise RuntimeError('compiled decimal standard-library runtime required')
_NUMERICAL_EXTENSION_HASH=(None if _NUMERICAL_EXTENSION.origin in ('built-in','frozen') else hashlib.sha256(Path(_NUMERICAL_EXTENSION.origin).read_bytes()).hexdigest())
NUMERICAL_IMPORT_MANIFEST={name:{'path':str(_STDLIB/(name+'.py')),'sha256':hashlib.sha256(payload).hexdigest()} for name,payload in _NUMERICAL_SOURCES.items()}
_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = _ROOT / 'experiments/grounded_policy_v2'
_ADAPTERS = ('challenge_action_authority', 'challenge_shadow_recorder',
    'challenge_shadow_epistemic_selector', 'native_observe_inquire_integration',
    'normalized_inquiry_objectives', 'open_object_world_challenge',
    'open_object_world_challenge_explorer')
if not sys.dont_write_bytecode or (_PACKAGE/'__init__.pyc').exists() or any((_PACKAGE/'__pycache__').glob('__init__.*.pyc')):
    raise RuntimeError('v2 source proof requires fresh -B and no bootstrap bytecode cache')
if any(n == 'agenttest' or n.startswith('agenttest.') or n in _ADAPTERS or n == 'inquiry_executive' or n.startswith('inquiry_executive.') for n in sys.modules):
    raise RuntimeError('grounded policy v2 requires a fresh interpreter: import first')
_FILES = list((_ROOT/'src/agenttest').rglob('*.py')) + list(_PACKAGE.rglob('*.py')) + [_ROOT/'experiments'/(n+'.py') for n in _ADAPTERS]
_SOURCE_BYTES = {str(p.relative_to(_ROOT)):p.read_bytes() for p in sorted(_FILES)}
IMPORT_MANIFEST = {p:hashlib.sha256(b).hexdigest() for p,b in _SOURCE_BYTES.items()}
_MODULES = {}
for _relative,_payload in _SOURCE_BYTES.items():
    _parts = list(Path(_relative).with_suffix('').parts[1:])
    _package = _parts[-1] == '__init__'
    if _package: _parts.pop()
    _MODULES['.'.join(_parts)] = (_ROOT/_relative,_payload,_package)
for _name,_payload in _NUMERICAL_SOURCES.items():
    _MODULES[_name]=(_STDLIB/(_name+'.py'),_payload,False)
class _PinnedLoader(importlib.abc.Loader):
    def __init__(self,path,payload): self.path,self.payload=path,payload
    def create_module(self,spec): return None
    def exec_module(self,module):
        module.__file__=str(self.path)
        exec(compile(self.payload,str(self.path),'exec'),module.__dict__)
class _PinnedFinder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='_decimal': return _NUMERICAL_EXTENSION
        if fullname=='_pydecimal': raise RuntimeError('pure decimal fallback is outside the reviewed runtime')
        item=_MODULES.get(fullname)
        if item is None: return None
        source,payload,package=item
        spec=importlib.util.spec_from_loader(fullname,_PinnedLoader(source,payload),origin=str(source),is_package=package)
        if package: spec.submodule_search_locations=[str(source.parent)]
        return spec
sys.meta_path.insert(0,_PinnedFinder())
