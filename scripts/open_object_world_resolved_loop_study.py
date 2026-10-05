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
from open_object_world_resolved_loop import run_resolved_loop


CHECKPOINTS = tuple(range(200, 951, 50))


def make_core(temp: str) -> AgentCore:
    store = StateStore(Path(temp) / "organism.json")
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
                row = run_resolved_loop(
                    make_core(temp),
                    seed=seed,
                    checkpoint=checkpoint,
                )
            rows.append(row)

    mature = [row for row in rows if row["status"] == "completed"]
    resolved = [
        row for row in mature
        if row.get("resolution_status") == "resolved"
    ]
    report = {
        "study": "open-object-world-resolved-loop-v1",
        "live_ora_modified": False,
        "core_action_authority_used": False,
        "rows": rows,
        "summary": {
            "case_count": len(rows),
            "mature_case_count": len(mature),
            "resolved_case_count": len(resolved),
            "all_resolution_matches_observation": all(
                row.get("resolution_matches_observation") is True
                for row in resolved
            ),
            "falsified_count": sum(
                row.get("resolved_experiment_outcome") == "falsified"
                for row in resolved
            ),
            "supported_count": sum(
                row.get("resolved_experiment_outcome") == "supported"
                for row in resolved
            ),
            "all_completed": all(
                row.get("resolved_experiment_status") == "completed"
                and row.get("resolved_experiment_readiness") == "resolved"
                for row in resolved
            ),
            "all_resolution_refs_match_outcome_evidence": all(
                row.get("resolution_evidence_refs")
                == [row.get("outcome_evidence_ref")]
                for row in resolved
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
