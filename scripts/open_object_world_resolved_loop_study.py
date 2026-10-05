from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "scripts"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from open_object_world_copied_loop import run_mature_copied_loop


CHECKPOINTS = tuple(range(200, 951, 50))


def make_core(path: str) -> AgentCore:
    store = StateStore(Path(path) / "organism.json")
    state = initial_state()
    state["cycles"] = 20
    state["generation"] = 20
    state["agenda"]["started_cycle"] = 1
    store.save(state)
    return AgentCore(store)


def main() -> None:
    rows = []
    for seed in range(1, 5):
        for checkpoint in CHECKPOINTS:
            with tempfile.TemporaryDirectory() as temp:
                core = make_core(temp)
                loop = run_mature_copied_loop(
                    core,
                    seed=seed,
                    checkpoint=checkpoint,
                )
                if loop["status"] != "completed":
                    rows.append(
                        {
                            "seed": seed,
                            "checkpoint": checkpoint,
                            "status": "not_mature",
                        }
                    )
                    continue
                resolved = core.resolve_native_inquiry_outcome(
                    loop["experiment_id"],
                    loop["outcome_evidence_ref"],
                    enabled=True,
                    persist=True,
                    _now_override="2026-10-05T01:15:00+00:00",
                )
                expected = (
                    "falsified"
                    if loop["falsified_hypothesis"]
                    else "supported"
                )
                experiment = next(
                    item
                    for item in core.store.load()["experiments"]
                    if item["id"] == loop["experiment_id"]
                )
                rows.append(
                    {
                        "seed": seed,
                        "checkpoint": checkpoint,
                        "status": "resolved",
                        "expected_outcome": expected,
                        "resolved_outcome": resolved["resolution"]["outcome"],
                        "matches_world_evidence": (
                            resolved["resolution"]["outcome"] == expected
                        ),
                        "experiment_status": experiment["status"],
                        "experiment_readiness": experiment["readiness"],
                        "completion_source": experiment["completion_source"],
                        "evidence_ref_preserved": (
                            loop["outcome_evidence_ref"]
                            in experiment["evidence_refs"]
                        ),
                    }
                )

    resolved_rows = [row for row in rows if row["status"] == "resolved"]
    report = {
        "study": "open-object-world-resolved-copied-loop-v1",
        "live_ora_modified": False,
        "core_action_authority_used": False,
        "resolver_enabled_only_in_copied_state": True,
        "rows": rows,
        "summary": {
            "case_count": len(rows),
            "resolved_case_count": len(resolved_rows),
            "all_outcomes_match_world_evidence": all(
                row["matches_world_evidence"] for row in resolved_rows
            ),
            "all_completed_and_resolved": all(
                row["experiment_status"] == "completed"
                and row["experiment_readiness"] == "resolved"
                for row in resolved_rows
            ),
            "all_completion_sources_strict_native_contract": all(
                row["completion_source"]
                == "native_inquiry_evidence_contract"
                for row in resolved_rows
            ),
            "all_outcome_evidence_refs_preserved": all(
                row["evidence_ref_preserved"] for row in resolved_rows
            ),
            "supported_count": sum(
                row["resolved_outcome"] == "supported"
                for row in resolved_rows
            ),
            "falsified_count": sum(
                row["resolved_outcome"] == "falsified"
                for row in resolved_rows
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
