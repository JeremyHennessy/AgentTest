from __future__ import annotations

from typing import Any

from .learning import (
    REPOSITORY_STABILITY_FAMILY,
    empirical_family,
    empirical_family_saturation,
)
from .semantic import question_has_active_experiment_path

AGENDA_VERSION = "persistent-multithread-agenda-v1"
AGENDA_MAX_THREADS = 4
AGENDA_MAX_ARCHIVED_THREADS = 16
AGENDA_MAX_DECISIONS = 128
AGENDA_MAX_THREAD_HISTORY = 32
AGENDA_EVIDENCE_REF_LIMIT = 16
AGENDA_CURRENT_EVIDENCE_FOCUS_VALUE = 1.0


def initial_agenda_state() -> dict[str, Any]:
    return {
        "version": AGENDA_VERSION,
        "started_cycle": None,
        "foreground_thread_id": None,
        "threads": [],
        "archived_threads": [],
        "decisions": [],
        "last_decision_cycle": None,
        "next_thread_index": 1,
        "next_decision_index": 1,
    }


def ensure_agenda_state(state: dict[str, Any]) -> dict[str, Any]:
    agenda = state.setdefault("agenda", initial_agenda_state())
    for key, value in initial_agenda_state().items():
        agenda.setdefault(key, value)
    agenda["version"] = AGENDA_VERSION
    return agenda


def _linked_experiments(
    state: dict[str, Any],
    question_id: str,
) -> list[dict[str, Any]]:
    return [
        item
        for item in state.get("experiments", [])
        if str(item.get("question_id") or "") == question_id
    ]


def _question_family(
    state: dict[str, Any],
    question: dict[str, Any],
) -> str | None:
    explicit = question.get("source_learning_family")
    if isinstance(explicit, str) and explicit:
        return explicit

    if question.get("source") == "repository_stability_prediction":
        return REPOSITORY_STABILITY_FAMILY

    question_id = str(question.get("id") or "")
    for experiment in reversed(_linked_experiments(state, question_id)):
        family = experiment.get("learning_family")
        if isinstance(family, str) and family:
            return family
    return None


def _evidence_refs(
    state: dict[str, Any],
    question: dict[str, Any],
) -> list[str]:
    refs: list[str] = []

    def add(values: Any) -> None:
        if not isinstance(values, list):
            return
        for value in values:
            if isinstance(value, str) and value and value not in refs:
                refs.append(value)

    add(question.get("source_evidence_refs"))
    question_id = str(question.get("id") or "")
    for experiment in _linked_experiments(state, question_id):
        add(experiment.get("evidence_refs"))
        empirical_basis = experiment.get("empirical_basis")
        if isinstance(empirical_basis, dict):
            add(empirical_basis.get("evidence_refs"))
        contract = experiment.get("evidence_contract")
        if isinstance(contract, dict):
            prediction_id = contract.get("prediction_id")
            if (
                isinstance(prediction_id, str)
                and prediction_id
                and prediction_id not in refs
            ):
                refs.append(prediction_id)

    return refs[-AGENDA_EVIDENCE_REF_LIMIT:]


def _candidate_metrics(
    state: dict[str, Any],
    question: dict[str, Any],
    *,
    legacy_question_id: str,
    prior_thread: dict[str, Any] | None,
) -> dict[str, Any]:
    question_id = str(question.get("id") or "")
    source = str(question.get("source") or "")
    family = _question_family(state, question)
    family_record = empirical_family(state, family) if family else None
    saturation = (
        empirical_family_saturation(family_record)
        if isinstance(family_record, dict)
        else 0.0
    )
    active_path = question_has_active_experiment_path(state, question)
    refs = _evidence_refs(state, question)
    prior_refs = set(
        str(ref)
        for ref in (prior_thread or {}).get("evidence_refs", [])
        if isinstance(ref, str)
    )
    new_refs = [ref for ref in refs if ref not in prior_refs]

    legacy_focus_value = AGENDA_CURRENT_EVIDENCE_FOCUS_VALUE if question_id == legacy_question_id else 0.0
    actionability_value = 0.35 if active_path else 0.0
    frontier_value = (
        round(0.8 * saturation, 6)
        if source == "empirical_frontier_transfer"
        else 0.0
    )
    evidence_change_value = min(0.3, 0.05 * len(new_refs))
    replication_saturation_cost = (
        round(0.7 * saturation, 6)
        if source == "repository_stability_prediction"
        else 0.0
    )
    priority_score = round(
        legacy_focus_value
        + actionability_value
        + frontier_value
        + evidence_change_value
        - replication_saturation_cost,
        6,
    )

    return {
        "question_id": question_id,
        "question_text": str(question.get("text") or ""),
        "source": source or None,
        "source_learning_family": family,
        "active_experiment_path": active_path,
        "family_saturation": round(float(saturation), 6),
        "legacy_focus_value": legacy_focus_value,
        "actionability_value": actionability_value,
        "frontier_value": frontier_value,
        "evidence_change_value": round(evidence_change_value, 6),
        "replication_saturation_cost": replication_saturation_cost,
        "priority_score": priority_score,
        "evidence_refs": refs,
        "new_evidence_refs": new_refs,
        "times_selected": int(question.get("times_selected", 0) or 0),
        "last_selected_cycle": question.get("last_selected_cycle"),
    }


def _eligible_questions(
    state: dict[str, Any],
    *,
    legacy_question_id: str,
    existing_question_ids: set[str],
) -> list[dict[str, Any]]:
    eligible = []
    for question in state.get("questions", []):
        if (
            not isinstance(question, dict)
            or question.get("status") != "open"
            or not question.get("id")
        ):
            continue
        question_id = str(question["id"])
        source = str(question.get("source") or "")
        if (
            question_id == legacy_question_id
            or question_id in existing_question_ids
            or source
            in {
                "repository_stability_prediction",
                "empirical_frontier_transfer",
            }
            or question_has_active_experiment_path(state, question)
        ):
            eligible.append(question)
    return eligible


def _append_history(
    thread: dict[str, Any],
    *,
    cycle: int,
    previous_status: str | None,
    status: str,
    reason: str,
    evidence_refs: list[str],
) -> None:
    if previous_status == status:
        return
    history = thread.setdefault("history", [])
    history.append(
        {
            "cycle": cycle,
            "from": previous_status,
            "to": status,
            "reason": reason,
            "evidence_refs": list(evidence_refs),
        }
    )
    if len(history) > AGENDA_MAX_THREAD_HISTORY:
        del history[:-AGENDA_MAX_THREAD_HISTORY]


def _new_thread(
    agenda: dict[str, Any],
    *,
    question_id: str,
    cycle: int,
) -> dict[str, Any]:
    index = int(agenda.get("next_thread_index", 1) or 1)
    agenda["next_thread_index"] = index + 1
    return {
        "id": f"AT{index:06d}",
        "question_id": question_id,
        "created_cycle": cycle,
        "status": None,
        "priority_score": 0.0,
        "evidence_refs": [],
        "last_foreground_cycle": None,
        "last_updated_cycle": cycle,
        "history": [],
    }


def update_agenda(
    state: dict[str, Any],
    *,
    legacy_question: dict[str, Any],
    cycle: int,
) -> dict[str, Any] | None:
    """Maintain a bounded persistent inquiry agenda over existing questions only."""

    agenda = ensure_agenda_state(state)
    started = agenda.get("started_cycle")
    if started is None or cycle <= int(started or 0):
        return None

    legacy_question_id = str(legacy_question.get("id") or "")
    if not legacy_question_id:
        return None

    existing_by_question = {
        str(thread.get("question_id") or ""): thread
        for thread in agenda.get("threads", [])
        if thread.get("question_id")
    }
    eligible = _eligible_questions(
        state,
        legacy_question_id=legacy_question_id,
        existing_question_ids=set(existing_by_question),
    )
    if len(eligible) < 2:
        return None

    metrics = [
        _candidate_metrics(
            state,
            question,
            legacy_question_id=legacy_question_id,
            prior_thread=existing_by_question.get(str(question.get("id") or "")),
        )
        for question in eligible
    ]
    metrics.sort(
        key=lambda item: (
            -float(item["priority_score"]),
            int(item.get("times_selected", 0) or 0),
            int(item.get("last_selected_cycle") or -1),
            str(item["question_id"]),
        )
    )
    selected_metrics = metrics[0]
    bounded_metrics = metrics[:AGENDA_MAX_THREADS]
    if selected_metrics["question_id"] not in {
        item["question_id"] for item in bounded_metrics
    }:
        bounded_metrics[-1] = selected_metrics

    previous_foreground_thread_id = agenda.get("foreground_thread_id")
    previous_foreground_question_id = None
    if previous_foreground_thread_id:
        previous = next(
            (
                thread
                for thread in agenda.get("threads", [])
                if thread.get("id") == previous_foreground_thread_id
            ),
            None,
        )
        if previous is not None:
            previous_foreground_question_id = previous.get("question_id")

    next_threads: list[dict[str, Any]] = []
    resumed_thread_id = None
    suspended_thread_ids: list[str] = []
    selected_thread: dict[str, Any] | None = None

    for candidate in bounded_metrics:
        question_id = str(candidate["question_id"])
        thread = existing_by_question.get(question_id)
        if thread is None:
            thread = _new_thread(
                agenda,
                question_id=question_id,
                cycle=cycle,
            )

        previous_status = str(thread.get("status") or "") or None
        selected = question_id == selected_metrics["question_id"]
        status = "foreground" if selected else "suspended"
        source = str(candidate.get("source") or "")
        if selected:
            reason = "highest_evidence_linked_priority"
        elif (
            candidate.get("active_experiment_path")
            and source == "repository_stability_prediction"
            and float(candidate.get("family_saturation", 0.0) or 0.0) > 0.0
        ):
            reason = "mature_replication_can_continue_without_foreground_attention"
        elif candidate.get("active_experiment_path"):
            reason = "lower_priority_but_executable"
        else:
            reason = "waiting_for_executable_path_or_new_evidence"

        _append_history(
            thread,
            cycle=cycle,
            previous_status=previous_status,
            status=status,
            reason=reason,
            evidence_refs=list(candidate.get("evidence_refs", [])),
        )
        if previous_status == "suspended" and status == "foreground":
            resumed_thread_id = str(thread["id"])
        if previous_status == "foreground" and status == "suspended":
            suspended_thread_ids.append(str(thread["id"]))

        thread.update(
            {
                "status": status,
                "priority_score": candidate["priority_score"],
                "question_text": candidate["question_text"],
                "source": candidate.get("source"),
                "source_learning_family": candidate.get(
                    "source_learning_family"
                ),
                "active_experiment_path": candidate["active_experiment_path"],
                "family_saturation": candidate["family_saturation"],
                "evidence_refs": list(candidate.get("evidence_refs", [])),
                "new_evidence_refs": list(
                    candidate.get("new_evidence_refs", [])
                ),
                "suspension_reason": None if selected else reason,
                "resume_condition": (
                    None
                    if selected
                    else (
                        "new evidence or an executable path raises this thread "
                        "above the current foreground priority"
                    )
                ),
                "last_updated_cycle": cycle,
            }
        )
        if selected:
            thread["last_foreground_cycle"] = cycle
            selected_thread = thread
        next_threads.append(thread)

    retained_ids = {str(thread["id"]) for thread in next_threads}
    for thread in agenda.get("threads", []):
        if str(thread.get("id") or "") in retained_ids:
            continue
        archived = dict(thread)
        archived["status"] = "abandoned"
        archived["abandoned_cycle"] = cycle
        archived["abandon_reason"] = "outside_current_bounded_agenda"
        agenda.setdefault("archived_threads", []).append(archived)

    agenda["archived_threads"] = agenda.get("archived_threads", [])[
        -AGENDA_MAX_ARCHIVED_THREADS:
    ]
    agenda["threads"] = next_threads
    agenda["foreground_thread_id"] = (
        str(selected_thread["id"]) if selected_thread is not None else None
    )
    agenda["last_decision_cycle"] = cycle

    second_score = (
        float(metrics[1]["priority_score"])
        if len(metrics) > 1
        else float(selected_metrics["priority_score"])
    )
    decision_index = int(agenda.get("next_decision_index", 1) or 1)
    agenda["next_decision_index"] = decision_index + 1
    decision = {
        "id": f"AD{decision_index:06d}",
        "cycle": cycle,
        "policy_version": AGENDA_VERSION,
        "candidate_count": len(metrics),
        "legacy_counterfactual": {
            "question_id": legacy_question_id,
            "question_text": str(legacy_question.get("text") or ""),
        },
        "selected": dict(selected_metrics),
        "selected_thread_id": (
            str(selected_thread["id"]) if selected_thread is not None else None
        ),
        "changed_choice": (
            selected_metrics["question_id"] != legacy_question_id
        ),
        "previous_foreground_thread_id": previous_foreground_thread_id,
        "previous_foreground_question_id": previous_foreground_question_id,
        "foreground_changed": (
            previous_foreground_thread_id is not None
            and selected_thread is not None
            and str(selected_thread["id"]) != previous_foreground_thread_id
        ),
        "resumed_thread_id": resumed_thread_id,
        "suspended_thread_ids": suspended_thread_ids,
        "priority_change_supported_by_new_evidence": bool(
            resumed_thread_id
            and selected_metrics.get("new_evidence_refs")
        ),
        "decision_margin": round(
            float(selected_metrics["priority_score"]) - second_score,
            6,
        ),
        "evidence_refs": list(selected_metrics.get("evidence_refs", [])),
        "candidate_summaries": [dict(item) for item in bounded_metrics],
        "rationale": (
            "Maintain several persisted inquiry threads, preserve the legacy "
            "question choice as a counterfactual, and foreground the existing "
            "thread with the strongest current evidence-linked priority."
        ),
    }
    agenda.setdefault("decisions", []).append(decision)
    if len(agenda["decisions"]) > AGENDA_MAX_DECISIONS:
        del agenda["decisions"][:-AGENDA_MAX_DECISIONS]
    return decision
