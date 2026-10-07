"""Read-only source/protocol/runtime capture. Does not import the policy API."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
from .ledger import IntegrityError
from .protocol import APPROVED_FILES, canonical, digest, LIMITS, registry


def file_hash(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise IntegrityError("Manifest input is not an non-symlink regular file: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(root, expected):
    root = Path(root).resolve()
    for relative, wanted in expected.items():
        path = root / relative
        if not path.resolve().is_relative_to(root) or path.is_symlink() or file_hash(path) != wanted:
            raise IntegrityError("Frozen source mismatch: " + relative)
    return digest(expected)


def capture(root):
    root = Path(root).resolve()
    validate_manifest(root, APPROVED_FILES)
    api_snapshot_path = root / "policy-results/final-loaded-source-closure.json"
    saved = json.loads(api_snapshot_path.read_bytes())
    actual_api_digest = validate_manifest(root/"policy-work", saved["code_manifest"])
    if actual_api_digest != saved["code_manifest_digest"]:
        raise IntegrityError("API closure digest mismatch")
    for value in saved["runtime_manifest"]["modules"].values():
        if file_hash(value["path"]) != value["sha256"]:
            raise IntegrityError("Pinned numerical source changed")
    if file_hash(Path(sys.executable).resolve()) != saved["runtime_manifest"]["executable_hash"]:
        raise IntegrityError("Interpreter differs from API freeze")
    # Compiled Decimal is built-in in this environment; an external binary is
    # hashed if a future reviewed runtime snapshot uses one.
    extension = saved["runtime_manifest"]["compiled_decimal"]
    if extension["origin"] not in ("built-in", "frozen") and file_hash(extension["origin"]) != extension["sha256"]:
        raise IntegrityError("Compiled decimal changed")
    files = {str(path.relative_to(root/"policy-study-work")): file_hash(path)
             for path in sorted((root/"policy-study-work").rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts}
    loaded_runtime = {}
    for name, module in sorted(tuple(sys.modules.items())):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_file() and not Path(path).resolve().is_relative_to(root):
            loaded_runtime[name] = {"path": str(Path(path).resolve()), "sha256": file_hash(Path(path).resolve())}
    return {"schema": "ora.study.preexecution-freeze.v1", "status": "NO-GO", "scientific_run": "NOT_RUN",
            "protocol_manifest": APPROVED_FILES, "study_source_manifest": files,
            "study_source_digest": digest(files), "api_source_manifest": saved["code_manifest"],
            "api_code_digest": actual_api_digest, "api_runtime_manifest": saved["runtime_manifest"],
            "api_runtime_digest": saved["runtime_manifest_digest"],
            "inspected_api_snapshot_hash": file_hash(api_snapshot_path),
            "observer_loaded_runtime": loaded_runtime,
            "observer_runtime_scope": "Read-only manifest observer; not a claimed future scientific loaded closure",
            "registry": registry(), "limits": LIMITS,
            "independent_combined_review": None, "scientific_execution_authorized": False}


def capture_execution_root(api_root, study_root):
    """Portable publication contract: unchanged API repo plus this study folder.

    No local sibling policy-work/policy-results directory is required. Exact
    reviewed document/API manifest copies live in reviewed-inputs. Runtime paths
    deliberately remain pinned to the approved execution environment; a different
    interpreter/numeric installation requires a prospective new runtime review.
    """
    api_root,study_root=Path(api_root).resolve(),Path(study_root).resolve()
    inputs=study_root/"reviewed-inputs"
    provenance=json.loads((inputs/"manifest.json").read_bytes())
    for origin,wanted in APPROVED_FILES.items():
        name=Path(origin).name
        if provenance.get(name)!={"origin_relative_path":origin,"sha256":wanted} or file_hash(inputs/name)!=wanted:
            raise IntegrityError("Bundled reviewed input differs: "+name)
    saved=json.loads((inputs/"final-loaded-source-closure.json").read_bytes())
    if file_hash(inputs/"final-loaded-source-closure.json")!=provenance["final-loaded-source-closure.json"]["sha256"]:
        raise IntegrityError("Bundled API snapshot changed")
    api_digest=validate_manifest(api_root,saved["code_manifest"])
    if api_digest!=saved["code_manifest_digest"]:
        raise IntegrityError("Portable API closure differs")
    for value in saved["runtime_manifest"]["modules"].values():
        if file_hash(value["path"])!=value["sha256"]:
            raise IntegrityError("Runtime requires prospective refreeze")
    if file_hash(Path(sys.executable).resolve())!=saved["runtime_manifest"]["executable_hash"]:
        raise IntegrityError("Interpreter requires prospective refreeze")
    sources={str(p.relative_to(study_root)):file_hash(p) for p in sorted(study_root.rglob("*"))
             if p.is_file() and "__pycache__" not in p.parts}
    return {"schema":"ora.portable-execution-freeze.v1","status":"NO-GO",
            "scientific_execution_authorized":False,"api_root_contract":"Repository root with unchanged experiments/grounded_policy_v2 and src/agenttest",
            "study_root_contract":"This deliverable directory containing ora_study and reviewed-inputs",
            "protocol_provenance":provenance,"api_source_manifest":saved["code_manifest"],
            "api_code_digest":api_digest,"api_runtime_manifest":saved["runtime_manifest"],
            "study_source_manifest":sources,"study_source_digest":digest(sources),
            "requirements":["Source-only bootstrap before imports","Native loaded binary/source/runtime freeze","Combined independent pre-execution review","Explicit execution instruction"]}
