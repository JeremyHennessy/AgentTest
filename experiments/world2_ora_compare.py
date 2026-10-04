from __future__ import annotations

import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.core import AgentCore
from agenttest.state import StateStore
from world2_ora_isolated import run_isolated_ora_world2_trial


def stable_control_observation() -> dict[str, Any]:
    return {
        "branch": "isolated/control",
        "baseline_fingerprint": "control:stable-v1",
        "tracked_files": 100,
        "python_files": 20,
        "python_source_lines": 5000,
        "test_files": 12,
        "working_tree_clean": True,
    }


def run_isolated_control_trial(
    source_state: dict[str, Any],
    *,
    cycles: int,
) -> dict[str, Any]:
    before = deepcopy(source_state)
    results = []
    with tempfile.TemporaryDirectory() as temp:
        store = StateStore(Path(temp) / "organism.json")
        store.save(deepcopy(source_state))
        core = AgentCore(store)
        for _ in range(cycles):
            result = core.cycle(
                stimulus="isolated stable control observation",
                observation=stable_control_observation(),
                cognition=False,
                strict_experiment_admission=True,
            )
            results.append(
                {
                    "cycle": result.get("cycle"),
                    "intention": deepcopy(result.get("intention")),
                    "question": deepcopy(result.get("question")),
                    "agenda_decision": deepcopy(result.get("agenda_decision")),
                }
            )
        final = store.load()
    if source_state != before:
        raise RuntimeError("control trial mutated caller source state")
    return {"cycles": results, "ora_final": final}


def summarize_trial(trial: dict[str, Any]) -> dict[str, Any]:
    final = trial["ora_final"]
    cycles = trial["cycles"]
    questions = [
        str(item.get("text") or "")
        for item in final.get("questions", [])
        if str(item.get("text") or "").strip()
    ]
    intentions = [
        str((item.get("intention") or {}).get("kind") or "")
        for item in cycles
        if (item.get("intention") or {}).get("kind")
    ]
    agenda = final.get("agenda") or {}
    decisions = agenda.get("decisions", [])
    foreground_changes = sum(
        bool(item.get("foreground_changed"))
        for item in decisions
        if isinstance(item, dict)
    )
    selected_questions = [
        str((item.get("selected") or {}).get("question_id") or "")
        for item in decisions
        if isinstance(item, dict) and (item.get("selected") or {}).get("question_id")
    ]
    return {
        "cycle_count": len(cycles),
        "distinct_question_text_count": len(set(questions)),
        "question_count": len(questions),
        "intention_counts": dict(sorted(Counter(intentions).items())),
        "distinct_intention_count": len(set(intentions)),
        "agenda_thread_count": len(agenda.get("threads", [])),
        "foreground_change_count": foreground_changes,
        "distinct_selected_question_count": len(set(selected_questions)),
        "surprise_count": len(final.get("surprises", [])),
        "prediction_count": len(final.get("predictions", [])),
        "experiment_count": len(final.get("experiments", [])),
        "reflection_count": len(final.get("reflections", [])),
        "empirical_family_count": len((final.get("empirical_learning") or {}).get("families", {})),
        "genuine_resumption_count": int(agenda.get("genuine_resumption_count", 0) or 0),
    }


def compare_world2_to_control(
    source_state: dict[str, Any],
    *,
    seed: int,
    actions: list[str],
) -> dict[str, Any]:
    control = run_isolated_control_trial(source_state, cycles=len(actions))
    world2 = run_isolated_ora_world2_trial(source_state, seed=seed, actions=actions)
    return {
        "seed": seed,
        "cycle_count": len(actions),
        "control": summarize_trial(control),
        "world2": summarize_trial(world2),
    }
