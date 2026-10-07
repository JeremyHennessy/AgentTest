"""Read sealed saved records only, with no policy/runtime imports or write access.

The final scorer executes in a fresh reporter interpreter. A report fix can use
unchanged sealed inputs with its own source hash; it cannot rerun any world step.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .ledger import IntegrityError
from .protocol import APPROVED_FILES, canonical, LIMITS

def _strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise IntegrityError("Duplicate saved JSON key")
            result[key] = value
        return result
    def no_float(value):
        raise IntegrityError("Use exact saved rationals, not float JSON")
    return json.loads(raw, object_pairs_hook=unique, parse_float=no_float, parse_constant=no_float)


def read_sealed(root, seal_name="records-seal.json"):
    root = Path(root).resolve()
    if Path(seal_name).name != seal_name:
        raise IntegrityError("Seal must be a root-relative simple name")
    seal_path = root/seal_name
    if seal_path.is_symlink() or not seal_path.is_file():
        raise IntegrityError("Missing immutable records seal: efficacy remains blinded")
    if seal_path.stat().st_size > 1_048_576:
        raise IntegrityError("Oversized seal")
    seal_raw = seal_path.read_bytes()
    seal = _strict_json(seal_raw)
    if set(seal) != {"schema", "protocol_manifest", "records", "saved_input", "records_complete"}:
        raise IntegrityError("Unknown records seal schema fields")
    if seal["schema"] != "ora.study.records-seal.v1" or seal["records_complete"] is not True or seal["protocol_manifest"] != APPROVED_FILES:
        raise IntegrityError("Records/protocol not sealed")
    if not isinstance(seal["records"], dict) or seal["saved_input"] not in seal["records"]:
        raise IntegrityError("Saved input missing from seal")
    total = len(seal_raw)
    payload = None
    for relative, wanted in seal["records"].items():
        path = root/relative
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise IntegrityError("Invalid sealed record path")
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file() or path.stat().st_nlink != 1:
            raise IntegrityError("Untrusted sealed record file")
        total += path.stat().st_size
        if total > LIMITS["output_bytes"]-LIMITS["finalization_reserve_bytes"]:
            raise IntegrityError("Sealed input exceeds scientific output allowance")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != wanted:
            raise IntegrityError("Sealed record changed: "+relative)
        if relative == seal["saved_input"]:
            payload = _strict_json(raw)
    return payload, hashlib.sha256(seal_raw).hexdigest()


def report_saved(root):
    payload, seal_hash = read_sealed(root)
    # Keep numerical imports in the independent reporter process only.
    from .scorer import score_saved_study
    result = score_saved_study(payload)
    result["saved_records_seal_hash"] = seal_hash
    result["reporter_source_hash"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def apply_outer_terminal(candidate, terminal):
    """Later report/write/seal failure always dominates provisional efficacy.

    The native controller must independently authenticate its own terminal and
    file bindings before calling this pure function. A caller-provided object is
    not an authority substitute. No extra API read is involved.
    """
    from copy import deepcopy
    from .protocol import digest
    result=deepcopy(candidate)
    result["provisional_computed_classification"]=candidate.get("classification")
    result["outer_terminal"]=deepcopy(terminal)
    status=terminal.get("classification") if isinstance(terminal,dict) else None
    if candidate.get("classification")=="invalid" or status=="invalid":
        result["classification"]="invalid"
    elif status=="incomplete":
        result["classification"]="incomplete"
    elif (status=="complete" and terminal.get("report_sha256")==digest(candidate)
          and terminal.get("records_seal_sha256")==candidate.get("saved_records_seal_hash")
          and terminal.get("finalization_complete") is True):
        result["classification"]=candidate.get("classification","invalid")
    else:
        result["classification"]="invalid"
        result.setdefault("errors",[]).append("Outer terminal/finalization/report binding is absent or inconsistent")
    if result.get("data_kind")=="synthetic_fixture":
        result["scientific_result"]=None
    else:
        result["scientific_result"]=result["classification"]
    return result
