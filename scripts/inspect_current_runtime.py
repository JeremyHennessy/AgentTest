"""Export bounded, unmodified evidence from a pinned runtime; stdlib only."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOURCE_COMMIT = "3449926e336cda1194a98a509990b03bfea2151b"
SOURCE_TREE = "2fee231601b027ce00ef73dfab4b969e4f852ad0"
SOURCE_BLOB = "f91515038ddf5b7479152147457af6e21828da92"
SOURCE_BYTES = 69081867
STATE_PATH = "state/organism.json"
MAX_OUTPUT_BYTES = 1024 * 1024


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0"},
    )


def object_hash(kind, data):
    return hashlib.sha1(
        f"{kind} {len(data)}\0".encode() + data, usedforsecurity=False
    ).hexdigest()


def verify_source(repo):
    if git(repo, "rev-parse", "HEAD").decode().strip() != SOURCE_COMMIT:
        raise ValueError("source HEAD does not match pinned commit")
    commit = git(repo, "cat-file", "commit", SOURCE_COMMIT)
    if object_hash("commit", commit) != SOURCE_COMMIT:
        raise ValueError("source commit content hash mismatch")
    if commit.splitlines()[0] != f"tree {SOURCE_TREE}".encode():
        raise ValueError("source root tree mismatch")
    if object_hash("tree", git(repo, "cat-file", "tree", SOURCE_TREE)) != SOURCE_TREE:
        raise ValueError("source root tree content hash mismatch")
    entry = git(repo, "ls-tree", "-r", SOURCE_TREE, "--", STATE_PATH).decode().strip()
    if entry != f"100644 blob {SOURCE_BLOB}\t{STATE_PATH}":
        raise ValueError("source path/blob binding mismatch")
    path = repo / STATE_PATH
    if path.is_symlink() or not path.is_file():
        raise ValueError("source must be a regular file")
    raw = path.read_bytes()
    if len(raw) != SOURCE_BYTES or object_hash("blob", raw) != SOURCE_BLOB:
        raise ValueError("source blob hash or byte length mismatch")
    return raw


def pick(obj, fields):
    return {key: obj[key] for key in fields if key in obj}


def rows(obj, key):
    value = obj[key]
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{key} must be an array of objects")
    return value


def tags(records, key):
    counts = Counter(
        json.dumps(row[key], sort_keys=True, allow_nan=False)
        for row in records if key in row
    )
    return {
        "missing_count": sum(key not in row for row in records),
        "values": [{"value": json.loads(value), "count": count}
                   for value, count in sorted(counts.items())],
    }


def project(state):
    if not isinstance(state, dict):
        raise ValueError("runtime root must be an object")
    result = {"state_fields": sorted(state), "state": pick(
        state, ("schema_version", "cycles", "generation", "created_at", "updated_at")
    )}
    if "planning_lab" in state:
        lab = state["planning_lab"]
        if not isinstance(lab, dict):
            raise ValueError("planning_lab must be an object")
        view = pick(lab, ("version", "status", "world_version", "bounds", "position",
                          "active_goal_id", "active_plan_id", "active_objective_realization_id"))
        view["field_names"] = sorted(lab)
        for key in ("transition_observations", "executions", "goals", "plans"):
            if key not in lab:
                continue
            records = rows(lab, key)
            view[key + "_count"] = len(records)
            if key in ("transition_observations", "executions"):
                view[key + "_tag_counts"] = {
                    tag: tags(records, tag) for tag in ("world_version", "source")
                }
            if key == "transition_observations":
                indexes = sorted(set(range(min(32, len(records)))) |
                                 set(range(max(0, len(records) - 64), len(records))))
                view[key + "_sample_indexes"] = indexes
                view[key] = [records[index] for index in indexes]
                if "world_version" in lab:
                    matching = [index for index, record in enumerate(records)
                                if "world_version" in record
                                and record["world_version"] == lab["world_version"]]
                    same_world_indexes = sorted(set(matching[:32] + matching[-64:]))
                    view["same_world_transition_observations_count"] = len(matching)
                    view["same_world_transition_observations_sample_indexes"] = same_world_indexes
                    view["same_world_transition_observations"] = [
                        records[index] for index in same_world_indexes
                    ]
            if key in ("goals", "plans"):
                active_key = "active_goal_id" if key == "goals" else "active_plan_id"
                if active_key in lab and lab[active_key] is not None:
                    view["current_" + key] = [pick(record, (
                        "id", "goal_id", "status", "world_version", "created_cycle",
                        "next_step_index", "target", "start", "goal",
                    )) for record in records if record.get("id") == lab[active_key]]
        result["planning_lab"] = view
    question_ids = set()
    if "agenda" in state:
        agenda = state["agenda"]
        if not isinstance(agenda, dict):
            raise ValueError("agenda must be an object")
        view = pick(agenda, ("version", "foreground_thread_id", "last_decision_cycle"))
        foreground = agenda.get("foreground_thread_id")
        matched = []
        if "threads" in agenda:
            threads = rows(agenda, "threads")
            view["thread_count"] = len(threads)
            if isinstance(foreground, str) and foreground:
                matched = [row for row in threads if row.get("id") == foreground]
            view["threads"] = [pick(row, ("id", "question_id", "status", "source",
                                          "source_learning_family", "active_experiment_path"))
                               for row in matched]
            question_ids = {row["question_id"] for row in view["threads"]
                            if isinstance(row.get("question_id"), str)}
        view["foreground_match_status"] = (
            "identifier_absent" if "foreground_thread_id" not in agenda else
            "identifier_null" if foreground is None else
            "identifier_invalid" if not isinstance(foreground, str) or not foreground else
            "threads_absent" if "threads" not in agenda else
            "not_found" if not matched else
            "unique" if len(matched) == 1 else "ambiguous"
        )
        result["agenda"] = view
    for key in ("questions", "experiments"):
        if key in state:
            result["agenda_" + key] = [pick(row, (
                "id", "question_id", "native_inquiry_candidate_id", "intention_id",
            )) for row in rows(state, key)
                if (row.get("id") if key == "questions" else row.get("question_id"))
                in question_ids]
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"non-JSON numeric constant: {value}")


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       allow_nan=False, separators=(",", ":")) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output == source or source in output.parents:
        raise ValueError("artifact directory must be outside source checkout")
    raw = verify_source(source)
    provenance = {
        "repository": "JeremyHennessy/AgentTest", "commit": SOURCE_COMMIT,
        "root_tree": SOURCE_TREE, "path": STATE_PATH, "git_blob": SOURCE_BLOB,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "inspector_commit": os.environ.get("GITHUB_SHA"),
        "inspector_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    state = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    projection = encode({"format": "current-runtime-projection-v1",
                         "provenance": provenance, **project(state)})
    if verify_source(source) != raw:
        raise ValueError("source content changed during inspection")
    receipt = encode({"provenance": provenance, "source_unchanged": True,
                      "projection_bytes": len(projection),
                      "projection_sha256": hashlib.sha256(projection).hexdigest()})
    if len(projection) + len(receipt) > MAX_OUTPUT_BYTES:
        raise ValueError("projection and receipt exceed 1 MiB; no evidence was truncated")
    output.mkdir(parents=True, exist_ok=False)
    (output / "current-runtime-projection.json").write_bytes(projection)
    (output / "provenance-receipt.json").write_bytes(receipt)
    print(f"Verified unchanged source; exported {len(projection) + len(receipt)} bytes.")


if __name__ == "__main__":
    main()
