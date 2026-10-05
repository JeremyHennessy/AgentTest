from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.evidence import known_evidence_ids
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.state import StateStore, initial_state


def evidence(feature: str) -> dict:
    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": "same_next_observation",
            "feature": feature,
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": [
            f"retention.report:{feature}:before",
            f"retention.report:{feature}:after",
        ],
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": 1,
            "confirmations": 1,
            "refutations": 0,
        },
    }


def record(store: StateStore, feature: str) -> str:
    return AgentCore(store).record_native_evidence(
        evidence(feature),
        enabled=True,
        persist=True,
    )["evidence_ref"]


def run() -> dict:
    with tempfile.TemporaryDirectory() as temp:
        store = StateStore(Path(temp) / "organism.json")
        state = initial_state()
        state["cycles"] = 4
        state["generation"] = 4
        state["agenda"]["started_cycle"] = 1
        store.save(state)

        original_refs = [record(store, feature) for feature in ("a", "b", "c")]
        pruned = store.load()
        pruned["episodes"] = [
            item for item in pruned["episodes"]
            if item["id"] != "E000002"
        ]
        store.save(pruned)
        new_ref = record(store, "after-prune")
        ids_after_prune = [item["id"] for item in store.load()["episodes"]]

    with tempfile.TemporaryDirectory() as temp:
        store = StateStore(Path(temp) / "organism.json")
        store.save(initial_state())
        ref = record(store, "tombstone")
        state = store.load()
        item = next(item for item in state["episodes"] if item["id"] == ref)
        item["kind"] = "native_evidence_tombstone"
        item["content"] = json.dumps({"status": "compacted"})
        store.save(state)
        tombstone_known = ref in known_evidence_ids(store.load())

    return {
        "diagnostic": "native-evidence-retention-hazards-v1",
        "production_behavior_changed": False,
        "physical_deletion": {
            "original_refs": original_refs,
            "deleted_ref": "E000002",
            "next_allocated_ref": new_ref,
            "episode_ids_after_new_record": ids_after_prune,
            "duplicate_id_created": (
                len(ids_after_prune) != len(set(ids_after_prune))
            ),
        },
        "tombstone": {
            "ref": ref,
            "still_in_known_evidence_ids": tombstone_known,
        },
        "conclusion": (
            "Current episode retention cannot safely delete or naively tombstone "
            "native evidence. A retention design needs monotonic identity allocation "
            "independent of list length plus explicit archive/evidence-universe and "
            "referential-integrity semantics."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run()
    if not result["physical_deletion"]["duplicate_id_created"]:
        raise SystemExit("expected deletion/ID-collision hazard was not reproduced")
    if not result["tombstone"]["still_in_known_evidence_ids"]:
        raise SystemExit("expected tombstone evidence-universe hazard was not reproduced")
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
