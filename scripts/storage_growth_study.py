"""Read-only inventory and isolated, cold-process diagnostic-writer comparison.

This never migrates, rewrites, prunes, or executes a cycle against input files.
The optional comparison runs only in a newly created temporary directory.
Historical inputs must be labelled as historical; no natural-progress claim is made.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Any

NOW = "2026-10-07T00:00:00+00:00"
SCRIPTS = ("experiment_design_eval", "blocked_attention_eval")


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_output(output: Path, inputs: list[Path]) -> None:
    for source in inputs:
        if output.resolve() == source.resolve() or (
            output.exists() and source.exists() and output.samefile(source)
        ):
            raise ValueError("output must not alias an input file")


def collection_sizes(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, value in state.items():
        row = {"field": key, "compact_value_bytes": len(encoded(value))}
        if isinstance(value, (dict, list)):
            row["count"] = len(value)
        if isinstance(value, dict):
            row["children"] = sorted(
                [{"field": child, "compact_value_bytes": len(encoded(item)),
                  "count": len(item) if isinstance(item, (dict, list)) else None}
                 for child, item in value.items()],
                key=lambda item: item["compact_value_bytes"], reverse=True,
            )[:8]
        rows.append(row)
    return sorted(rows, key=lambda item: item["compact_value_bytes"], reverse=True)


def journal_inventory(path: Path) -> dict[str, Any]:
    source = path.resolve()
    if source.name == "journal.jsonl" and ((source.parent / "journal-archives.json").exists() or (source.parent / "journal-archives.json").is_symlink()):
        raise ValueError("active journal tail is not full history; use a verified logical export")
    events = Counter()
    raw_by_event = Counter()
    cycle_field_bytes = Counter()
    compact_bytes = 0
    count = 0
    last_cycle = None
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError(f"invalid journal line {number}") from error
            if not isinstance(event, dict):
                raise ValueError(f"journal line {number} is not an object")
            kind = str(event.get("event", "<missing>"))
            events[kind] += 1
            raw_by_event[kind] += len(line)
            compact_bytes += len(encoded(event)) + 1
            count += 1
            last_cycle = event.get("cycle", last_cycle)
            if kind == "cycle":
                for key, value in event.items():
                    cycle_field_bytes[key] += len(encoded(value))
    return {
        "raw_bytes": path.stat().st_size, "sha256": file_sha(path),
        "events": count, "last_event_cycle": last_cycle,
        "events_by_kind": dict(events), "raw_bytes_by_kind": dict(raw_by_event),
        "hypothetical_compact_bytes": compact_bytes,
        "cycle_field_value_bytes": dict(cycle_field_bytes.most_common()),
        "rewritten": False,
    }


def inventory(state_path: Path, journal_path: Path | None, provenance: str) -> dict[str, Any]:
    original = state_path.read_bytes()
    state = json.loads(original)
    compact = encoded(state) + b"\n"
    compressed = gzip.compress(original, mtime=0)
    restored = gzip.decompress(compressed)
    if restored != original:
        raise AssertionError("gzip did not preserve exact source bytes")
    result = {
        "provenance": provenance,
        "classification": "inventory only; no live changes or natural-progress evidence",
        "state": {
            "cycle": state.get("cycles"), "raw_bytes": len(original),
            "sha256": sha(original), "compact_bytes": len(compact),
            "whitespace_saving_bytes": len(original) - len(compact),
            "compact_canonical_sha256": sha(encoded(json.loads(compact))),
            "gzip_original_bytes": len(compressed), "gzip_byte_roundtrip": True,
            "fields": collection_sizes(state),
        },
    }
    if journal_path is not None:
        result["journal"] = journal_inventory(journal_path)
    if file_sha(state_path) != sha(original):
        raise AssertionError("source changed during inventory")
    return result


def load_script(root: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ValueError("cannot load diagnostic script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(root: Path, case: Path, operation: str) -> dict[str, Any]:
    """One fresh-process save, diagnostic, cache hit, or copied planning cycle."""
    def deny_network(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("storage comparison cannot access the network")
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    from agenttest.core import AgentCore
    from agenttest.state import StateStore

    for name, module in list(sys.modules.items()):
        if name.startswith("agenttest.") and hasattr(module, "utc_now"):
            module.utc_now = lambda: NOW
    store = StateStore(case / "organism.json")
    output = None
    if operation == "save":
        store.save(store.load())
    elif operation == "cycle":
        state = store.load()
        observation = deepcopy((state.get("environment_snapshots") or [{
            "sensor": "storage-copy-test", "branch": "isolated",
            "tracked_files": 10, "python_files": 4,
            "python_source_lines": 100, "test_files": 1,
            "working_tree_clean": True,
        }])[-1])
        output = AgentCore(store).cycle(
            "autonomous heartbeat", observation=observation,
            strict_experiment_admission=True, planning_lab=True,
            cognition=False, _now_override=NOW,
        )
    else:
        module = load_script(root, operation)
        module._now = lambda: NOW
        report_path = case / f"{operation}.json"
        sys.argv = [operation, "--state", str(store.path), "--output", str(report_path)]
        with redirect_stdout(io.StringIO()):
            module.main()
        output = json.loads(report_path.read_bytes())

    state_bytes = store.path.read_bytes()
    journal = store.journal_path.read_bytes() if store.journal_path.exists() else b""
    return {
        "operation": operation, "cycle": json.loads(state_bytes).get("cycles"),
        "state_bytes": len(state_bytes), "state_sha256": sha(state_bytes),
        "state_canonical_sha256": sha(encoded(json.loads(state_bytes))),
        "reloaded_state_canonical_sha256": sha(encoded(store.load())),
        "journal_bytes": len(journal), "journal_sha256": sha(journal),
        "output_canonical_sha256": sha(encoded(output)),
        "created": output.get("created") if isinstance(output, dict) else None,
    }


def compare_writers(state_path: Path, journal_path: Path | None,
                    baseline_root: Path, candidate_root: Path, cycles: int = 1) -> dict[str, Any]:
    originals = {path: file_sha(path) for path in (state_path, journal_path) if path is not None}
    prefix = journal_path.read_bytes() if journal_path is not None else b""
    stages = []
    this_script = Path(__file__).resolve()
    with tempfile.TemporaryDirectory(prefix="ora-storage-copy-") as directory:
        cases = {}
        for label, root in (("baseline", baseline_root), ("candidate", candidate_root)):
            case = Path(directory) / label
            case.mkdir()
            shutil.copyfile(state_path, case / "organism.json")
            (case / "journal.jsonl").write_bytes(prefix)
            cases[label] = (root.resolve(), case)

        operations = ["save", *SCRIPTS, *SCRIPTS]
        for _ in range(cycles):
            operations += ["cycle", *SCRIPTS, *SCRIPTS]
        for operation in operations:
            step = {"operation": operation}
            for label, (root, case) in cases.items():
                # Explicit clean environment: no API credentials or provider calls.
                env = {"PATH": os.defpath, "PYTHONPATH": str(root / "src"),
                       "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
                command = [sys.executable, str(this_script), "--worker-root", str(root),
                           "--worker-case", str(case), "--worker-operation", operation]
                completed = subprocess.run(command, env=env, cwd=case,
                                           capture_output=True, text=True, check=True)
                step[label] = json.loads(completed.stdout)
                actual = (case / "journal.jsonl").read_bytes()
                if not actual.startswith(prefix):
                    raise AssertionError("historical journal prefix changed")
            for key in ("state_canonical_sha256", "reloaded_state_canonical_sha256",
                        "journal_sha256", "output_canonical_sha256", "created"):
                if step["baseline"][key] != step["candidate"][key]:
                    raise AssertionError(f"{operation}: {key} differs")
            step["full_decoded_state_and_output_equal"] = True
            step["journal_bytes_and_historical_prefix_equal"] = True
            stages.append(step)
        final_journal = (cases["candidate"][1] / "journal.jsonl").read_bytes()
        new_events = [json.loads(line) for line in final_journal[len(prefix):].splitlines()]
    if any(file_sha(path) != before for path, before in originals.items()):
        raise AssertionError("input files changed during comparison")
    return {"classification": "synthetic isolated copied-state evidence; no natural milestone credit",
            "fixed_clock": NOW, "cold_process_each_operation": True,
            "baseline_root": str(baseline_root.resolve()),
            "candidate_root": str(candidate_root.resolve()), "stages": stages,
            "input_bytes_unchanged": True, "new_journal_events": len(new_events),
            "new_event_kinds": dict(Counter(event.get("event") for event in new_events)),
            "original_journal_prefix_bytes": len(prefix)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--provenance")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--candidate-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cycles", type=int, choices=range(4), default=1)
    parser.add_argument("--worker-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-case", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-operation", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_root:
        print(json.dumps(worker(args.worker_root, args.worker_case, args.worker_operation)))
        return
    if args.state is None or not args.provenance:
        parser.error("--state and --provenance are required")
    sources = [path for path in (args.state, args.journal) if path is not None]
    if args.output:
        safe_output(args.output, sources)
    result = inventory(args.state, args.journal, args.provenance)
    if args.baseline_root:
        result["writer_comparison"] = compare_writers(
            args.state, args.journal, args.baseline_root, args.candidate_root, args.cycles,
        )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
