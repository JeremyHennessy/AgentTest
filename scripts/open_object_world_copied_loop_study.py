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


def core_in_temp(temp: str) -> AgentCore:
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
                result = run_mature_copied_loop(
                    core_in_temp(temp),
                    seed=seed,
                    checkpoint=checkpoint,
                )
            rows.append(result)

    mature = [row for row in rows if row["status"] == "completed"]
    evaluable = [row for row in mature if row["evaluable"]]
    falsified = [
        row for row in evaluable
        if row["falsified_hypothesis"] is True
    ]
    report = {
        "study": "open-object-world-copied-loop-v1",
        "live_ora_modified": False,
        "core_action_authority_used": False,
        "reward_signal": False,
        "rows": rows,
        "summary": {
            "case_count": len(rows),
            "mature_case_count": len(mature),
            "evaluable_outcome_count": len(evaluable),
            "outcome_evidence_recorded_count": sum(
                row.get("outcome_evidence_ref") is not None
                for row in mature
            ),
            "falsification_count": len(falsified),
            "falsification_rate": (
                round(len(falsified) / len(evaluable), 6)
                if evaluable
                else None
            ),
            "all_questions_native": all(
                row.get("question_source") == "native_inquiry"
                for row in mature
            ),
            "auto_resolved_count": sum(
                row.get("native_outcome_auto_resolved") is True
                for row in mature
            ),
            "all_experiments_remain_awaiting_native_evidence": all(
                row.get("experiment_status_after_outcome") == "proposed"
                and row.get("experiment_readiness_after_outcome")
                == "awaiting_native_evidence"
                for row in mature
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
