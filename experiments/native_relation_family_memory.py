from __future__ import annotations

from copy import deepcopy
from typing import Any

FAMILY_MEMORY_VERSION = "native-relation-family-memory-v0"
FAMILY_MEMORY_KEY = "native_relation_family_memory"


def update_family_memory(
    state: dict[str, Any], ledger: list[dict[str, Any]]
) -> dict[str, Any]:
    memory = state.setdefault(
        FAMILY_MEMORY_KEY,
        {"version": FAMILY_MEMORY_VERSION, "families": {}, "updates": 0},
    )
    for item in ledger:
        if not item.get("evaluable"):
            continue
        proposal = item["proposal"]
        family = proposal["relation"]
        record = memory["families"].setdefault(
            family,
            {
                "relation": family,
                "evaluable": 0,
                "confirmations": 0,
                "refutations": 0,
                "feature_refs": [],
                "action_refs": [],
            },
        )
        record["evaluable"] += int(item["evaluable"])
        record["confirmations"] += int(item["confirmations"])
        record["refutations"] += int(item["refutations"])
        feature = str(proposal["feature"])
        if feature not in record["feature_refs"]:
            record["feature_refs"].append(feature)
        action = proposal.get("action")
        if action and action not in record["action_refs"]:
            record["action_refs"].append(action)
    memory["updates"] += 1
    return deepcopy(memory)


def rank_held_out_proposals(
    state: dict[str, Any], proposals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rank unseen combinations using relation-family history, never target truth."""
    memory = state.get(FAMILY_MEMORY_KEY, {"families": {}})
    ranked = []
    for proposal in proposals:
        record = memory.get("families", {}).get(proposal["relation"], {})
        evaluable = int(record.get("evaluable", 0) or 0)
        confirmations = int(record.get("confirmations", 0) or 0)
        refutations = int(record.get("refutations", 0) or 0)
        conflict = min(confirmations, refutations)
        conflict_ratio = conflict / evaluable if evaluable else 0.0
        evidence_weight = min(0.4, evaluable / 20.0)
        score = round(0.3 + evidence_weight + min(0.3, conflict_ratio), 6)
        ranked.append(
            {
                "proposal": deepcopy(proposal),
                "family_evidence": {
                    "evaluable": evaluable,
                    "confirmations": confirmations,
                    "refutations": refutations,
                },
                "score": score,
                "selection_basis": "persisted_relation_family_evidence",
            }
        )
    return sorted(
        ranked,
        key=lambda item: (-item["score"], item["proposal"]["id"]),
    )
