from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from open_object_world_native_bridge import (
    collect_trace,
    choose_information_gain_candidate,
    held_out_evaluation,
    stage_in_copied_core,
)


def main() -> None:
    rows = []
    for seed in range(1, 5):
        trace = collect_trace(seed=seed, steps=240)
        observations = trace["observations"]
        split = len(observations) // 2
        prefix = observations[:split]
        held = observations[split - 1 :]
        selected = choose_information_gain_candidate(prefix)
        held_out = held_out_evaluation(
            selected["candidate"],
            held,
        )

        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = initial_state()
            state["cycles"] = 10
            state["generation"] = 10
            state["agenda"]["started_cycle"] = 1
            store.save(state)
            core = AgentCore(store)
            staged = stage_in_copied_core(core, selected, prefix)
            question_id = staged["inquiry_result"]["question"]["id"]
            cycle = core.cycle(
                stimulus="continue ordinary operation",
                _now_override=f"2026-10-05T00:0{seed}:00+00:00",
            )
            agenda_summary = next(
                item
                for item in cycle["agenda_decision"]["candidate_summaries"]
                if item["question_id"] == question_id
            )

        rows.append(
            {
                "seed": seed,
                "selected_feature": selected["candidate"]["feature"],
                "selected_relation": selected["candidate"]["relation"],
                "prefix_score": selected["score"],
                "prefix_evaluable": selected["candidate"]["evaluable"],
                "prefix_confirmations": selected["candidate"]["confirmations"],
                "prefix_refutations": selected["candidate"]["refutations"],
                "held_out": held_out,
                "copied_core_question_source": staged["inquiry_result"]["question"]["source"],
                "copied_core_actionability": staged["inquiry_result"][
                    "experiment"
                ]["specification"]["actionability"],
                "agenda_active_experiment_path": agenda_summary[
                    "active_experiment_path"
                ],
                "action_lab_result": cycle["action_lab_result"],
                "planning_lab_result": cycle["planning_lab_result"],
            }
        )

    report = {
        "study": "open-object-world-native-bridge-v1",
        "world": "open-object-world-v0",
        "objective": "information_gain",
        "selection": "prefix_only",
        "held_out_scoring": True,
        "world_action_authority": False,
        "rows": rows,
        "summary": {
            "all_copied_core_actionable": all(
                row["copied_core_actionability"] == "actionable"
                for row in rows
            ),
            "all_agenda_paths_active": all(
                row["agenda_active_experiment_path"]
                for row in rows
            ),
            "all_action_labs_off": all(
                row["action_lab_result"] is None
                and row["planning_lab_result"] is None
                for row in rows
            ),
            "distinct_selected_features": sorted(
                {row["selected_feature"] for row in rows}
            ),
            "mean_held_out_support_rate": round(
                sum(row["held_out"]["support_rate"] for row in rows) / len(rows),
                6,
            ),
            "minimum_held_out_support_rate": min(
                row["held_out"]["support_rate"] for row in rows
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
