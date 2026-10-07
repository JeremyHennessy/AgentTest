"""Honest resource diagnostics and budgeted parent writes.

Sampling is observational, never a hard process-tree guarantee. RLIMIT_CPU is
per-process and RLIMIT_AS is virtual memory; neither is represented as a global
CPU/RSS limit. Scientific admission remains blocked on this environment.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import resource
import sys
import time
from .ledger import CapacityError, IntegrityError
from .protocol import LIMITS, canonical

class Window:
    def __init__(self):
        self.start_ns = time.monotonic_ns()
        self.peak_rss_bytes = 0
        self.last = None

    def sample(self):
        processes = {}
        for path in Path("/proc").glob("[0-9]*/stat"):
            try:
                raw = path.read_text()
                rest = raw[raw.rfind(")")+2:].split()
                processes[int(path.parent.name)] = (int(rest[1]), int(rest[11])+int(rest[12]), int(rest[21]))
            except (OSError, ValueError, IndexError):
                continue
        ours = {os.getpid()}
        while True:
            expanded = ours | {pid for pid, row in processes.items() if row[0] in ours}
            if ours == expanded:
                break
            ours = expanded
        page_size = os.sysconf("SC_PAGE_SIZE")
        ticks = os.sysconf("SC_CLK_TCK")
        rss = sum(processes[pid][2] * page_size for pid in ours if pid in processes)
        live_child_ticks = sum(processes[pid][1] for pid in ours if pid != os.getpid() and pid in processes)
        current = resource.getrusage(resource.RUSAGE_SELF)
        waited = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_ns = int((current.ru_utime + current.ru_stime + waited.ru_utime + waited.ru_stime) * 1_000_000_000) + live_child_ticks * 1_000_000_000 // ticks
        self.peak_rss_bytes = max(self.peak_rss_bytes, rss)
        self.last = {"wall_ns": time.monotonic_ns()-self.start_ns,
                     "observed_tree_cpu_ns": cpu_ns, "observed_tree_rss_bytes": rss,
                     "sampled_peak_tree_rss_bytes": self.peak_rss_bytes,
                     "observed_pids": sorted(ours), "hard_enforcement": False,
                     "limitations": ["Short-lived processes and between-sample RSS can be missed",
                                      "Python supervisor bootstrap precedes monotonic initialization",
                                      "Post-finalization exit overhead is outside the final snapshot"]}
        return self.last

    def check(self, *, wall_ns=None):
        row = self.sample()
        if row["wall_ns"] > (LIMITS["wall_ns"] if wall_ns is None else wall_ns):
            raise CapacityError("Observed uninterrupted wall window exceeded")
        if row["observed_tree_cpu_ns"] > LIMITS["aggregate_cpu_ns"]:
            raise CapacityError("Observed aggregate CPU ceiling exceeded")
        if row["observed_tree_rss_bytes"] > LIMITS["concurrent_tree_rss_bytes"]:
            raise CapacityError("Observed concurrent RSS ceiling exceeded")
        return row

class BudgetedFiles:
    """Parent-owned bounded writes; cap includes old + temporary replacement.

    This protects this writer only. A hard quota for all child/kernel writes is
    not available and remains a separate scientific admission blocker.
    """
    def __init__(self, root, *, total=LIMITS["output_bytes"], reserve=LIMITS["finalization_reserve_bytes"]):
        self.root = Path(root)
        self.total, self.reserve = total, reserve
        if total <= reserve or reserve <= 0:
            raise ValueError("Invalid output/reserve limits")
        self.reserve_path = self.root / "finalization.reserve"
        fd = os.open(self.reserve_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            left = reserve
            chunk = b"\0" * min(reserve, 65536)
            while left:
                count = os.write(fd, chunk[:left])
                if count <= 0:
                    raise OSError("Short reserve write")
                left -= count
            os.fsync(fd)
        finally:
            os.close(fd)
        self.finalizing = False
        self._sync_dir()

    def used(self):
        size = 0
        for path in self.root.rglob("*"):
            if path.is_symlink():
                raise IntegrityError("Symlink in output tree")
            if path.is_file():
                info = path.stat()
                if info.st_nlink != 1:
                    raise IntegrityError("Aliased output")
                size += info.st_size
        return size

    def _sync_dir(self):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def write(self, name, content, *, final=False):
        if Path(name).name != name or name in (".", "..", "finalization.reserve"):
            raise IntegrityError("Output path must be a simple file name")
        if self.finalizing and not final:
            raise IntegrityError("Scientific output cannot use finalization reserve")
        if final and not self.finalizing:
            self.reserve_path.unlink()
            self._sync_dir()
            self.finalizing = True
        raw = content if isinstance(content, bytes) else canonical(content)+b"\n"
        if self.used() + len(raw) > self.total:
            raise CapacityError("New and temporary output exceed whole-run cap")
        path, temp = self.root/name, self.root/(name+".new")
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            data = memoryview(raw)
            while data:
                count = os.write(fd, data)
                if count <= 0:
                    raise OSError("Short output write")
                data = data[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, path)
        self._sync_dir()
        if self.used() > self.total:
            raise CapacityError("Concurrent output growth breached cap")


def environment_evidence():
    """Read capabilities only. Do not mount/create cgroups or change security."""
    try:
        mounts = Path("/proc/mounts").read_text().splitlines()
    except OSError:
        mounts = []
    workspace_mounts = [line for line in mounts if "/workspace" in line]
    delegated = Path("/sys/fs/cgroup").is_dir()
    return {"schema": "ora.resource-preflight.v1", "python": sys.version,
            "platform": sys.platform, "cgroup_visible": delegated,
            "cgroup_descriptor": Path("/proc/self/cgroup").read_text() if Path("/proc/self/cgroup").exists() else None,
            "workspace_mounts": workspace_mounts,
            "volatile_fsync_mount_observed": any("fsync=volatile" in line for line in workspace_mounts),
            "durability_scope": "Process-crash atomic replacement/fsync only; no machine-power-loss promise",
            "alternative_enforcement": "Sequential audited children with additive inherited RLIMIT_AS/CPU budgets and fixed artifact allocations is feasible in principle; proof and integrated tests remain required",
            "resource_mechanisms": {"procfs_sampling": Path("/proc/self/stat").exists(),
                                    "posix_flock": True, "posix_fsync": True,
                                    "rlimit_cpu_is_aggregate": False, "rlimit_as_is_rss": False},
            "scientific_execution_allowed": False,
            "blockers": [
                "No reviewed hard concurrent process-tree RSS/aggregate CPU/output enforcement",
                "No exact full-lifetime external supervisor including its own bootstrap/finalization",
                "No reviewed authoritative API adapter with per-invocation accounting",
                "Independent combined controller/scorer/mask/source review and execution instruction absent"]}
