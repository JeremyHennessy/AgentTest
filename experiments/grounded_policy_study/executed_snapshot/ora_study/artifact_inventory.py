"""Fixed logical-byte allocations for prospective reviewed scientific artifacts.

Every parent write is reserved before it starts. The frozen API's only external
writes are one capsule, its zero-byte stable lock and at most one same-directory
replacement; these receive a separate per-dispatch reservation. This is a
trusted-source composition, not a filesystem security boundary or disk quota.
"""
from pathlib import Path
import os
from .ledger import IntegrityError,CapacityError
from .protocol import MIB,canonical,registry

ALLOCATIONS={"capsules":128*MIB,"source_inputs":24*MIB,"D_references":2*MIB,
             "saved_exports":24*MIB,"ledger_and_logs":2*MIB,"temporary_peak":3*MIB,
             "reports":6*MIB,"manifests":2*MIB,"finalization":MIB}
assert sum(ALLOCATIONS.values())==192*MIB
SOURCE_BOUNDS={"ora":8*1024,"world":96*1024,"observations":208*1024}
# 64 distinct three-file source sets consume19.5MiB, leaving4.5MiB in the source
# allocation for common neutral source snapshots. Oversize inputs fail before a
# worker is dispatched; these are fixed resource slots, not scientific exclusions.
assert 64*sum(SOURCE_BOUNDS.values())<=ALLOCATIONS["source_inputs"]

class ArtifactInventory:
    def __init__(self,root,*,allocations=None):
        self.root=Path(root)
        self.allocations=dict(ALLOCATIONS if allocations is None else allocations)
        self.records={}
        self.external_active=None
        self.capsules=set()
        self.halted=False
    def _safe(self,name):
        value=Path(name)
        if value.is_absolute() or ".." in value.parts or not value.parts:
            raise IntegrityError("Artifact path escapes run root")
        path=self.root/value
        if any(p.is_symlink() for p in (path,*path.parents) if p.is_relative_to(self.root)):
            raise IntegrityError("Artifact symlink")
        return path
    def used(self,category):
        return sum(record["reserved_bytes"] for record in self.records.values() if record["category"]==category)
    def reserve(self,name,category,size):
        if self.halted or type(size) is not int or size<0 or category not in self.allocations or name in self.records:
            raise IntegrityError("Invalid/duplicate artifact reservation")
        self._safe(name)
        if self.used(category)+size>self.allocations[category]:
            raise CapacityError("Fixed artifact allocation exhausted: "+category)
        self.records[name]={"category":category,"reserved_bytes":size,"actual_bytes":None}
    def put_new(self,name,category,value):
        raw=value if isinstance(value,bytes) else canonical(value)+b"\n"
        self.reserve(name,category,len(raw))
        path=self._safe(name)
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            try:
                view=memoryview(raw)
                while view:
                    count=os.write(fd,view)
                    if count<=0:
                        raise OSError("Short artifact write")
                    view=view[count:]
                os.fsync(fd)
            finally:
                os.close(fd)
            directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            self.records[name]["actual_bytes"]=len(raw)
        except BaseException:
            # A partial write/reservation is retained; never automatically free
            # it or open a different output directory to continue.
            self.halted=True
            raise
    def register_capsule(self,case_id):
        if case_id not in registry()["arm_case_ids"] or case_id in self.capsules:
            raise IntegrityError("Unregistered/recreated capsule artifact")
        self.reserve(f"capsules/{case_id}.json","capsules",2*MIB)
        self.reserve(f"capsules/{case_id}.json.lock","capsules",0)
        self.capsules.add(case_id)
    def begin_api_write(self,case_id):
        if self.halted or self.external_active is not None or case_id not in self.capsules:
            raise IntegrityError("Only one registered native capsule writer may run")
        self.external_active=case_id
    def finish_api_write(self,case_id):
        if self.external_active!=case_id:
            raise IntegrityError("Unexpected native writer completion")
        folder=self.root/"capsules"
        if any(folder.glob(f".{case_id}.json.*.tmp")):
            self.halted=True
            raise IntegrityError("Stranded capsule temporary ends run; reservation retained")
        path=folder/f"{case_id}.json"
        try:
            size=path.stat().st_size
            if path.is_symlink() or path.stat().st_nlink!=1 or size>2*MIB:
                raise IntegrityError("Native capsule exceeds registered allocation or aliases")
            self.records[f"capsules/{case_id}.json"]["actual_bytes"]=size
        except BaseException:
            self.halted=True
            raise
        self.external_active=None
    def summary(self):
        return {"allocations":dict(self.allocations),"total_allocation":sum(self.allocations.values()),
                "reserved_by_category":{k:self.used(k) for k in self.allocations},
                "external_writer":self.external_active,"halted":self.halted,
                "one_capsule_temp_max_bytes":2*MIB,"other_atomic_temp_reserve_bytes":MIB,
                "integration_status":"Source-audited writer integration still required"}
