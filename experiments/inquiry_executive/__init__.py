"""Copied executive, requiring import-first use in a fresh interpreter.

Warm Ora/Challenge module state cannot be certified from files on disk. Reject
it instead of guessing which bytes ran. Repository dependencies are thereafter
compiled directly from the pinned bytes below, never from a bytecode cache.
This is a trusted local integrity boundary, not a hostile Python sandbox.
"""
from __future__ import annotations

import hashlib
import importlib.abc
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_ADAPTERS = (
    "challenge_action_authority", "challenge_shadow_recorder",
    "challenge_shadow_epistemic_selector", "native_observe_inquire_integration",
    "normalized_inquiry_objectives", "open_object_world_challenge",
    "open_object_world_challenge_explorer")
if any(name == "agenttest" or name.startswith("agenttest.") or name in _ADAPTERS
       for name in sys.modules):
    raise RuntimeError("inquiry executive requires a fresh interpreter: import it before Ora/Challenge dependencies")
_FILES = (list((_ROOT / "src/agenttest").rglob("*.py"))
          + list((_ROOT / "experiments/inquiry_executive").glob("*.py"))
          + [_ROOT / "experiments" / (name + ".py") for name in _ADAPTERS])
_SOURCE_BYTES = {str(p.relative_to(_ROOT)): p.read_bytes() for p in sorted(_FILES)}
IMPORT_MANIFEST = {name: hashlib.sha256(payload).hexdigest()
                   for name,payload in _SOURCE_BYTES.items()}
_MODULES = {}
for _relative, _payload in _SOURCE_BYTES.items():
    _path = Path(_relative)
    _parts = list(_path.with_suffix("").parts[1:])
    _package = _parts[-1] == "__init__"
    if _package:
        _parts.pop()
    _MODULES[".".join(_parts)] = (_ROOT / _relative, _payload, _package)


class _PinnedLoader(importlib.abc.Loader):
    def __init__(self, path, payload):
        self.path, self.payload = path, payload

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = str(self.path)
        exec(compile(self.payload, str(self.path), "exec"), module.__dict__)


class _PinnedFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        item = _MODULES.get(fullname)
        if item is None:
            return None
        source, payload, package = item
        spec = importlib.util.spec_from_loader(fullname, _PinnedLoader(source,payload),
                                              origin=str(source), is_package=package)
        if package:
            spec.submodule_search_locations = [str(source.parent)]
        return spec


sys.meta_path.insert(0, _PinnedFinder())
