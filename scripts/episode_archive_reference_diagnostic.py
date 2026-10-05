from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EPISODE_ID = re.compile(r"^E([0-9]+)$")


def _category(path: tuple[str, ...]) -> str:
    if not path:
        return "root"
    top = path[0]
    leaf = next((part for part in reversed(path) if not part.isdigit()), top)
    return f"{top}.{leaf}"


def collect_external_episode_refs(state: dict[str, Any]) -> dict[str, Any]:
    occurrences: list[tuple[str, str]] = []

    def walk(value: Any, path: tuple[str, ...]) -> None:
        if path == ("episodes",):
            return
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, (*path, str(key)))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, (*path, str(index)))
        elif isinstance(value, str) and EPISODE_ID.fullmatch(value):
            occurrences.append((_category(path), value))

    for key, value in state.items():
        if key == "episodes":
            continue
        walk(value, (str(key),))

    by_category: dict[str, set[str]] = defaultdict(set)
    occurrence_counts = Counter()
    for category, identifier in occurrences:
        by_category[category].add(identifier)
        occurrence_counts[category] += 1
    return {
        "ids": sorted({identifier for _, identifier in occurrences}),
        "occurrence_count": len(occurrences),
        "by_category": {
            key: {
                "unique_ids": sorted(values),
                "unique_count": len(values),
                "occurrence_count": occurrence_counts[key],
            }
            for key, values in sorted(by_category.items())
        },
    }


def _numeric(identifier: str) -> int | None:
    match = EPISODE_ID.fullmatch(identifier)
    return int(match.group(1)) if match else None


def analyze(state: dict[str, Any], *, state_bytes: int, prior_cycle: int | None = None, prior_bytes: int | None = None) -> dict[str, Any]:
    episodes = state.get("episodes", [])
    ids = [str(item.get("id") or "") for item in episodes]
    id_set = set(ids)
    refs = collect_external_episode_refs(state)
    ref_set = set(refs["ids"])
    missing = sorted(ref_set - id_set)
    present_refs = sorted(ref_set & id_set)
    ordinals = sorted(value for value in (_numeric(item) for item in present_refs) if value is not None)

    semantic = state.get("semantic_memory", {})
    last_index = int(semantic.get("last_episode_index", 0) or 0)
    native = [
        item for item in state.get("experiments", [])
        if isinstance(item, dict) and isinstance(item.get("native_inquiry"), dict)
    ]
    native_proposed = [item for item in native if item.get("status") == "proposed"]
    floors = [
        int(item["native_inquiry"].get("resolution_evidence_floor_episode_count", 0) or 0)
        for item in native
        if type(item["native_inquiry"].get("resolution_evidence_floor_episode_count")) is int
    ]

    deletion_sizes = sorted({
        size for size in (1, 100, 1000, max(1, len(episodes)//10))
        if 0 < size < len(episodes)
    })
    deletion_risks = []
    for removed in deletion_sizes:
        retained = len(episodes) - removed
        next_len_after_append = retained + 1
        semantic_start = min(last_index, next_len_after_append)
        semantic_would_process_new = semantic_start <= retained
        hypothetical_floor = len(episodes)
        next_outcome_index = retained
        hypothetical_fresh_outcome_rejected = next_outcome_index < hypothetical_floor
        deletion_risks.append({
            "removed_prefix_count": removed,
            "retained_episode_count": retained,
            "semantic_last_episode_index": last_index,
            "semantic_start_after_one_new_append": semantic_start,
            "semantic_would_process_new_episode": semantic_would_process_new,
            "hypothetical_native_floor": hypothetical_floor,
            "new_outcome_list_index_after_deletion": next_outcome_index,
            "hypothetical_fresh_outcome_rejected_as_predating_inquiry": hypothetical_fresh_outcome_rejected,
        })

    report = {
        "diagnostic_version": "episode-archive-reference-contract-v1",
        "cycle": int(state.get("cycles", 0) or 0),
        "state_bytes": state_bytes,
        "episode_count": len(episodes),
        "last_episode_id": ids[-1] if ids else None,
        "next_episode_index": state.get("next_episode_index"),
        "episode_ids_unique": len(ids) == len(id_set),
        "external_episode_reference_occurrences": refs["occurrence_count"],
        "external_unique_episode_references": len(ref_set),
        "external_reference_categories": refs["by_category"],
        "referenced_episode_ids_missing_from_hot_ledger": missing,
        "referenced_episode_ids_present_in_hot_ledger": len(present_refs),
        "unreferenced_hot_episode_count": len(id_set - ref_set),
        "oldest_referenced_numeric_episode": ordinals[0] if ordinals else None,
        "newest_referenced_numeric_episode": ordinals[-1] if ordinals else None,
        "semantic_memory": {
            "last_episode_index": last_index,
            "equals_current_episode_count": last_index == len(episodes),
            "concept_count": len(semantic.get("concepts", {})),
            "association_count": len(semantic.get("associations", {})),
        },
        "native_inquiry": {
            "experiment_count": len(native),
            "proposed_count": len(native_proposed),
            "episode_count_floors": floors,
        },
        "deletion_risk_simulation": deletion_risks,
        "measured_growth": None,
        "conclusion": {
            "physical_prefix_deletion_safe_now": False,
            "reasons": [
                "semantic consolidation uses a positional episode-list cursor",
                "native inquiry freshness uses a positional episode-list floor",
                "external state structures retain episode IDs that require explicit archive authority/retrieval semantics",
            ],
        },
    }
    if prior_cycle is not None and prior_bytes is not None and report["cycle"] > prior_cycle:
        delta_cycles = report["cycle"] - prior_cycle
        delta_bytes = state_bytes - prior_bytes
        report["measured_growth"] = {
            "prior_cycle": prior_cycle,
            "prior_state_bytes": prior_bytes,
            "delta_cycles": delta_cycles,
            "delta_bytes": delta_bytes,
            "bytes_per_cycle_over_sample": round(delta_bytes / delta_cycles, 2),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--output")
    parser.add_argument("--prior-cycle", type=int)
    parser.add_argument("--prior-bytes", type=int)
    args = parser.parse_args()

    path = Path(args.state)
    state = json.loads(path.read_text(encoding="utf-8"))
    report = analyze(
        state,
        state_bytes=path.stat().st_size,
        prior_cycle=args.prior_cycle,
        prior_bytes=args.prior_bytes,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(json.dumps({
        "cycle": report["cycle"],
        "state_bytes": report["state_bytes"],
        "episode_count": report["episode_count"],
        "external_unique_episode_references": report["external_unique_episode_references"],
        "missing_references": len(report["referenced_episode_ids_missing_from_hot_ledger"]),
        "semantic_last_episode_index": report["semantic_memory"]["last_episode_index"],
        "native_inquiry_count": report["native_inquiry"]["experiment_count"],
        "physical_prefix_deletion_safe_now": report["conclusion"]["physical_prefix_deletion_safe_now"],
        "bytes_per_cycle_over_sample": (
            report["measured_growth"]["bytes_per_cycle_over_sample"]
            if report["measured_growth"] else None
        ),
    }, sort_keys=True))
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
