from __future__ import annotations

import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.core import AgentCore
from agenttest.state import StateStore
from world2_ecology import initial_world2_state, observe_world2, transition_world2
from world2_ora_isolated import (
    TRIAL_STIMULUS, run_isolated_ora_world2_trial, trial_cycle_record,
    trial_start_metadata, trial_time, world2_repository_shaped_observation,
)


def stable_control_observation(*, seed: int = 1, first_action: str | None = None) -> dict[str, Any]:
    world = initial_world2_state(seed=seed)
    if first_action is not None:
        world, _ = transition_world2(world, first_action, cycle=1)
    return world2_repository_shaped_observation(observe_world2(world), world_seed=seed)


def run_isolated_control_trial(
    source_state: dict[str, Any], *, cycles: int,
    observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before = deepcopy(source_state)
    start = trial_start_metadata(source_state)
    frozen_observation = deepcopy(observation if observation is not None else stable_control_observation())
    results = []
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "organism.json"
        StateStore(path).save(deepcopy(source_state))
        for index in range(1, cycles + 1):
            result = AgentCore(StateStore(path)).cycle(
                stimulus=TRIAL_STIMULUS, observation=deepcopy(frozen_observation),
                cognition=False, strict_experiment_admission=True,
                _now_override=trial_time(source_state, index),
            )
            results.append(trial_cycle_record(result, frozen_observation))
        final = StateStore(path).load()
    if source_state != before:
        raise RuntimeError("control trial mutated caller source state")
    return {"cycles": results, "ora_final": final, "trial_start": start}


def summarize_trial(trial: dict[str, Any]) -> dict[str, Any]:
    """Trial-window outcomes only; historical totals are not trial discoveries."""
    final, cycles, start = trial["ora_final"], trial["cycles"], trial["trial_start"]
    start_cycle = int(start["cycle"])
    decisions = [item["agenda_decision"] for item in cycles if isinstance(item.get("agenda_decision"), dict)]
    new_questions = [item for item in final.get("questions", []) if item.get("id") not in set(start["question_ids"])]
    trial_questions = [item["question"]["text"] for item in cycles if item.get("question")]
    intentions = [item["intention"]["kind"] for item in cycles if item.get("intention")]
    prediction_statuses = Counter((item.get("prediction_result") or {}).get("status", "none") for item in cycles)
    new_surprises = [item for item in final.get("surprises", []) if int(item.get("cycle", -1)) > start_cycle]
    agenda = final.get("agenda") or {}
    genuine_delta = int(agenda.get("genuine_resumption_count", 0)) - int(start["genuine_resumption_count"])
    return {
        "cycle_count": len(cycles),
        "start_cycle": start_cycle,
        "end_cycle": int(final["cycles"]),
        "new_question_count": len(new_questions),
        "new_question_texts": sorted({item.get("text", "") for item in new_questions}),
        "distinct_question_text_count": len(set(trial_questions)),
        "intention_counts": dict(sorted(Counter(intentions).items())),
        "distinct_intention_count": len(set(intentions)),
        "agenda_thread_count": len(agenda.get("threads", [])),
        "foreground_change_count": sum(item.get("foreground_changed") is True for item in decisions),
        "distinct_selected_question_count": len({(item.get("selected") or {}).get("question_id") for item in decisions if (item.get("selected") or {}).get("question_id")}),
        "prediction_status_counts": dict(sorted(prediction_statuses.items())),
        "post_first_sample_intervention_invalidations": sum((item.get("prediction_result") or {}).get("status") == "invalidated_by_intervention" for item in cycles[1:]),
        "surprise_count": len(new_surprises),
        "surprise_field_counts": dict(sorted(Counter(field for item in new_surprises for field in item.get("changes", {})).items())),
        "prediction_count": len(final.get("predictions", [])) - start["counts"]["predictions"],
        "experiment_count": len(final.get("experiments", [])) - start["counts"]["experiments"],
        "reflection_count": len(final.get("reflections", [])) - start["counts"]["reflections"],
        "new_empirical_family_count": len((final.get("empirical_learning") or {}).get("families", {})) - start["empirical_family_count"],
        "genuine_resumption_count": genuine_delta,
        "new_retained_decision_count": len(decisions),
        "note": "Synthetic repository-shaped sensor pilot; scripted actions. Not native ecological learning or a natural capability demonstration.",
    }


def compare_world2_to_control(
    source_state: dict[str, Any], *, seed: int, actions: list[str],
) -> dict[str, Any]:
    frozen = stable_control_observation(seed=seed, first_action=actions[0] if actions else None)
    control = run_isolated_control_trial(source_state, cycles=len(actions), observation=frozen)
    control_summary = summarize_trial(control)
    control_first = control["cycles"][0]["observation"] if actions else None
    del control
    world2 = run_isolated_ora_world2_trial(source_state, seed=seed, actions=actions)
    if actions and control_first != world2["cycles"][0]["observation"]:
        raise RuntimeError("paired trials did not start with identical sensor observations")
    world_summary = summarize_trial(world2)
    if control_summary["post_first_sample_intervention_invalidations"] or world_summary["post_first_sample_intervention_invalidations"]:
        raise RuntimeError("ordinary trial data was misclassified as an intervention")
    trace = [{
        "cycle": item["cycle"],
        "prediction_status": (item.get("prediction_result") or {}).get("status"),
        "prediction_errors": (item.get("prediction_result") or {}).get("errors", {}),
        "drives": item.get("drives"),
        "intention": (item.get("intention") or {}).get("kind"),
        "question_id": (item.get("question") or {}).get("id"),
        "selected_thread_id": (item.get("agenda_decision") or {}).get("selected_thread_id"),
    } for item in world2["cycles"]]
    return {"seed": seed, "cycle_count": len(actions), "control": control_summary, "world2": world_summary, "world2_trace": trace}
