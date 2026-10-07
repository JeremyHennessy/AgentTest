"""Authored rejection-path proof; never constructs or transitions a world."""
import sys
from pathlib import Path

api_root = Path(sys.argv[1]).resolve()
forbidden_entries = []
forbidden = {
    (str(api_root / "experiments/open_object_world_challenge.py"), name)
    for name in ("initial_world", "observe_world", "transition")
} | {
    (str(api_root / "src/agenttest/grounded_policy/policy.py"), name)
    for name in ("build_cohort", "evaluate", "_reconstruct_cohort", "verify_cohort", "verify_evaluation")
}


def import_guard(frame, event, arg):
    key = (frame.f_code.co_filename, frame.f_code.co_name)
    if event == "call" and key in forbidden:
        forbidden_entries.append(list(key))
        raise AssertionError("Forbidden scientific/world function entry during import")


sys.setprofile(import_guard)
sys.path.insert(0, str(api_root / "experiments"))
import grounded_policy_v2  # Required first, before any numerical dependencies.
from grounded_policy_v2 import contracts, executive, primitives, store
sys.setprofile(None)

import collections
import json
import os
import resource
import tempfile
import time

resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024,) * 2)
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024,) * 2)
results = []


def run_one(name, capsule_store, identities, authored, *, direct=False):
    counts = collections.Counter()
    boundaries = []
    snapshots = []
    verified_object = []
    validator_object = []
    tracked = {
        primitives.strict_json.__code__: "strict_json",
        primitives.verify_seal.__code__: "verify_seal",
        executive.validate_capsule.__code__: "validate_capsule",
        contracts.code_manifest.__code__: "code_manifest",
        contracts.runtime_manifest.__code__: "runtime_manifest",
    }

    def observe(frame, event, arg):
        key = (frame.f_code.co_filename, frame.f_code.co_name)
        if event == "call" and key in forbidden:
            forbidden_entries.append(list(key))
            raise AssertionError("Forbidden scientific/world function entry")
        if event != "call" or frame.f_code not in tracked:
            return
        kind = tracked[frame.f_code]
        counts[kind] += 1
        if kind in ("verify_seal", "validate_capsule"):
            value = frame.f_locals["value" if kind == "verify_seal" else "state"]
            boundaries.append(kind)
            snapshots.append(primitives.canonical(value))
            (verified_object if kind == "verify_seal" else validator_object).append(value)

    if not direct:
        capsule_store.path.write_bytes(primitives.canonical(authored) + b"\n")
    started = time.process_time_ns()
    sys.setprofile(observe)
    try:
        if direct:
            executive.validate_capsule(authored)
        else:
            fd = os.open(capsule_store.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                capsule_store._read_locked(fd, identities)
            finally:
                os.close(fd)
    except contracts.Conflict as error:
        outcome = {"type": type(error).__name__, "message": str(error)}
    else:
        raise AssertionError("Authored invalid input unexpectedly accepted")
    finally:
        sys.setprofile(None)
    elapsed = time.process_time_ns() - started
    if validator_object and verified_object and not direct:
        assert all(value is verified_object[0] for value in validator_object + verified_object)
        assert len(set(snapshots)) == 1, "State changed between seal and validation"
    # Retain the parsed references until the next test, preventing id reuse.
    item = {"name": name, "outcome": outcome, "counts": dict(counts),
            "boundary_order": boundaries, "same_private_object_and_bytes": bool(validator_object and verified_object),
            "cpu_ns_not_a_full_validation_benchmark": elapsed}
    results.append(item)
    return verified_object[0] if verified_object else None


with tempfile.TemporaryDirectory(prefix="checksum-proof-", dir=sys.argv[2]) as temporary:
    root = Path(temporary)
    path = root / "authored.json"
    lock = root / "authored.json.lock"
    lock.touch()
    capsule_store = store.CapsuleStore(path, root, enabled=True)
    stat_root, stat_lock = root.stat(), lock.stat()
    identities = {"directory": [stat_root.st_dev, stat_root.st_ino],
                  "lock": [stat_lock.st_dev, stat_lock.st_ino]}
    identity = dict(run_id="a" * 32, path=str(path), research_dir=str(root), filesystem=identities,
        source_inputs={}, code_manifest=contracts.code_manifest(), runtime_manifest=contracts.runtime_manifest(),
        profile={"name": "synthetic_two_decision_v2", "max_bytes": 2097152, "max_decisions": 3, "max_actions": 2},
        selection_backend=contracts.BACKEND, science_configuration=contracts.science_configuration(),
        evidence_mode="retain_first", discovery_count=32, adapter={}, initial_ora_hash="0" * 64,
        initial_world_hash="0" * 64, initial_frames_hash="0" * 64)
    base = dict(version=contracts.VERSION, identity=identity, identity_hash=primitives.digest(identity),
        revision=0, frames=[], cohort={}, ora={}, world={}, decisions=[], attempts=[], outcomes=[], beliefs=[], events=[], reserve=0, seal=None)

    def authored(mutate=lambda value: None, *, seal=True):
        value = primitives.strict_json(primitives.canonical(base))
        mutate(value)
        return primitives.seal(value) if seal else value

    bad_seal = authored()
    bad_seal["reserve"] = 1
    run_one("tampered_seal", capsule_store, identities, bad_seal)
    run_one("wrong_path_resealed", capsule_store, identities,
        authored(lambda value: value["identity"].update(path=str(root / "another.json"))))
    run_one("wrong_directory_resealed", capsule_store, identities,
        authored(lambda value: value["identity"].update(research_dir=str(root.parent))))
    run_one("wrong_filesystem_resealed", capsule_store, identities,
        authored(lambda value: value["identity"].update(filesystem={"directory": [0, 0], "lock": [0, 0]})))
    capsule_store._pinned = "f" * 64
    run_one("wrong_pinned_identity_resealed", capsule_store, identities, authored())
    capsule_store._pinned = None
    run_one("unknown_capsule_field_resealed", capsule_store, identities,
        authored(lambda value: value.update(unexpected=True)))
    run_one("unsupported_version_resealed", capsule_store, identities,
        authored(lambda value: value.update(version="unrecognized")))
    run_one("invalid_evidence_mode_resealed", capsule_store, identities,
        authored(lambda value: value["identity"].update(evidence_mode="unreviewed")))
    first = run_one("invalid_profile_resealed", capsule_store, identities, authored())
    second = run_one("fresh_second_read", capsule_store, identities, authored())
    assert first is not second, "Parsed state escaped or was reused across reads"
    run_one("changed_second_read_requires_new_seal", capsule_store, identities, bad_seal)
    run_one("direct_validator_default_rejects_bad_seal", capsule_store, identities, bad_seal, direct=True)
    assert executive.validate_capsule.__kwdefaults__ == {"verify_checksum": True}
    assert not forbidden_entries

print(json.dumps({"schema": "ora.checksum-local-reuse-proof.v1", "api_root": str(api_root),
    "results": results, "case_count": len(results), "forbidden_entries": forbidden_entries,
    "direct_validator_default": executive.validate_capsule.__kwdefaults__,
    "accepted_capsule_coverage": False, "full_budget_benchmark": False,
    "scientific_transitions": 0, "scientific_decisions": 0}, sort_keys=True))
