"""Source-only package loader for a future cold controller/reporter launcher.

The launcher must execute this .py file directly using an exact checked path.
It captures and hashes all package .py files before installation, rejects warm
package modules, and compiles captured bytes. Existing bytecode is preserved and
never consulted. This loader supplies no scientific admission or resource proof.
"""
import hashlib
import importlib.abc
import importlib.util
from pathlib import Path
import sys

class PinnedSources(importlib.abc.MetaPathFinder):
    def __init__(self, root, expected, *, package="ora_study"):
        if any(name==package or name.startswith(package+".") for name in sys.modules):
            raise RuntimeError("Warm study package imports forbidden")
        root_path=Path(root).absolute()
        if ".." in root_path.parts or any(p.is_symlink() for p in (root_path,*root_path.parents)):
            raise RuntimeError("Symlinked or noncanonical package ancestry")
        self.root=root_path.resolve()
        self.package=package
        self.modules={}
        discovered={str(p.relative_to(self.root)) for p in self.root.rglob("*.py")}
        if discovered != set(expected):
            raise RuntimeError("Study source closure membership differs")
        for relative, wanted in sorted(expected.items()):
            path=self.root/relative
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise RuntimeError("Source alias or escape")
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=wanted:
                raise RuntimeError("Study source digest differs")
            parts=list(Path(relative).with_suffix("").parts)
            is_package=parts[-1]=="__init__"
            if is_package:
                parts.pop()
            name=".".join([package]+parts)
            self.modules[name]=(path,raw,is_package)
    def find_spec(self, fullname, path=None, target=None):
        item=self.modules.get(fullname)
        if item is None:
            if fullname==self.package or fullname.startswith(self.package+"."):
                raise ModuleNotFoundError("Unmanifested package module refused: "+fullname)
            return None
        source,raw,is_package=item
        loader=CapturedBytes(source,raw)
        spec=importlib.util.spec_from_loader(fullname,loader,origin=str(source),is_package=is_package)
        if is_package:
            spec.submodule_search_locations=[str(source.parent)]
        return spec
    def install(self):
        sys.meta_path.insert(0,self)

class CapturedBytes(importlib.abc.Loader):
    def __init__(self,path,payload):
        self.path,self.payload=path,payload
    def create_module(self,spec):
        return None
    def exec_module(self,module):
        module.__file__=str(self.path)
        exec(compile(self.payload,str(self.path),"exec"),module.__dict__)

if __name__ == "__main__":
    raise SystemExit("Source-loader primitive only; scientific launch remains disabled")
