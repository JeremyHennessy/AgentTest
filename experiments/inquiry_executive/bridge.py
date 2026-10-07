"""Copied-only, single-call bridge to the unchanged ordinary AgentCore cycle.

This module deliberately has no selector injection or world transition hook.
Public evidence must already have been admitted to the copied Ora state. The
caller commits this staged result into the executive capsule, or discards it.
"""
from __future__ import annotations

import json
import stat
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.agenda import AGENDA_MAX_THREADS
from agenttest.core import AgentCore
from agenttest.state import SCHEMA_VERSION

BRIDGE_VERSION = "inquiry-executive-ordinary-bridge-v1"
_INPUT_FIELDS = {"planning_lab_requested", "provenance"}
_PROVENANCE = {"synthetic_control", "preserved_input_smoke"}


def _copy_json(value: Any) -> Any:
    """Reject executable objects and non-JSON values before any Core call."""
    def check(item: Any) -> None:
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("bridge JSON keys must be strings")
            for child in item.values():
                check(child)
        elif type(item) is list:
            for child in item:
                check(child)
        elif item is not None and type(item) not in {str, int, float, bool}:
            raise ValueError("bridge inputs must contain JSON values only")
    check(value)
    # allow_nan=False rejects infinity as well as NaN. No serialization coercion.
    json.dumps(value, allow_nan=False)
    return deepcopy(value)


def _copied_path(path: str | Path) -> Path:
    if not isinstance(path, (str, Path)) or not str(path):
        raise ValueError("ordinary bridge requires an explicit copied path")
    if not Path(path).is_absolute():
        raise ValueError("ordinary bridge requires an absolute copied path")
    target = Path(path).absolute()
    if target != target.resolve():
        raise ValueError("ordinary bridge rejects path aliases and symlinks")
    for component in (target, *target.parents):
        if component.is_symlink():
            raise ValueError("ordinary bridge rejects symlinks")
    root = Path(__file__).resolve().parents[2]
    protected = {Path("state/organism.json").absolute(), root / "state/organism.json"}
    live_directories = {Path("state").absolute(), root / "state"}
    if target in protected or any(target.is_relative_to(directory) for directory in live_directories) or ".git" in target.parts:
        raise ValueError("ordinary bridge requires a non-live copied path")
    if target.exists():
        info = target.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("ordinary bridge rejects nonregular files and hardlinks")
        for source in protected:
            if source.exists() and target.samefile(source):
                raise ValueError("ordinary bridge path aliases live state")
    return target


class MemoryStore:
    """Deep-copy Core load/save/journal contract with no filesystem writes.

    Repeated load calls see exactly the committed snapshot until save. In
    particular Core's provisional-resumption correction cannot read its own
    partially mutated working state. The explicit path exists only for existing
    read-only guards; this class never constructs a StateStore or opens it.
    """

    def __init__(self, state: dict[str, Any], path: str | Path) -> None:
        self.path = _copied_path(path)
        if type(state) is not dict:
            raise ValueError("ordinary bridge state must be an object")
        self._state = _copy_json(state)
        self._events: list[dict[str, Any]] = []
        self.save_count = 0

    def load(self) -> dict[str, Any]:
        return deepcopy(self._state)

    def save(self, state: dict[str, Any]) -> None:
        if type(state) is not dict:
            raise ValueError("ordinary bridge state must be an object")
        self._state = _copy_json(state)
        self.save_count += 1

    def append_journal(self, event: dict[str, Any]) -> None:
        if type(event) is not dict:
            raise ValueError("ordinary bridge journal event must be an object")
        self._events.append(_copy_json(event))

    @property
    def events(self) -> list[dict[str, Any]]:
        return deepcopy(self._events)


def validate_public_inputs(public_inputs: dict[str, Any]) -> dict[str, Any]:
    if type(public_inputs) is not dict or set(public_inputs) != _INPUT_FIELDS:
        raise ValueError("ordinary bridge public_inputs fields do not match envelope")
    if type(public_inputs["planning_lab_requested"]) is not bool:
        raise ValueError("planning_lab_requested must be boolean")
    if type(public_inputs["provenance"]) is not str or public_inputs["provenance"] not in _PROVENANCE:
        raise ValueError("ordinary bridge provenance is not declared")
    return deepcopy(public_inputs)


def _unique(rows: Any, key: str, value: Any, name: str) -> dict[str, Any]:
    if type(rows) is not list or value is None:
        raise ValueError(f"ordinary bridge {name} identity is unavailable")
    found = [row for row in rows if type(row) is dict and row.get(key) == value]
    if len(found) != 1:
        raise ValueError(f"ordinary bridge requires unique {name} identity")
    return found[0]


def _unique_ids(rows: Any, name: str) -> None:
    if type(rows) is not list or any(type(row) is not dict for row in rows):
        raise ValueError(f"ordinary bridge {name} must be an object list")
    ids = [row.get("id") for row in rows]
    if any(type(value) is not str or not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"ordinary bridge requires unique {name} IDs")


def _selection(post: dict[str, Any], result: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    cycle = result["cycle"]
    agenda = post["agenda"]
    decision = result.get("agenda_decision")
    if event.get("agenda_decision") != decision:
        raise ValueError("ordinary result/event agenda mismatch")
    cycle_decisions = [item for item in agenda["decisions"] if item.get("cycle") == cycle]
    if decision is None:
        if cycle_decisions or agenda.get("last_decision_cycle") == cycle:
            raise ValueError("ordinary null result contradicts saved agenda decision")
        return None
    if type(decision) is not dict or decision.get("cycle") != cycle:
        raise ValueError("ordinary decision cycle mismatch")
    if len(cycle_decisions) != 1 or cycle_decisions[0] != decision:
        raise ValueError("ordinary cycle requires exactly one actual agenda decision")
    if not agenda["decisions"] or agenda["decisions"][-1] != decision or agenda.get("last_decision_cycle") != cycle:
        raise ValueError("ordinary decision is not the latest saved decision")
    if _unique(agenda["decisions"], "id", decision.get("id"), "decision") != decision:
        raise ValueError("ordinary decision identity mismatch")
    selected = decision.get("selected")
    if type(selected) is not dict:
        raise ValueError("ordinary decision has no selected candidate")
    question_id = selected.get("question_id")
    question = _unique(post["questions"], "id", question_id, "selected question")
    if result.get("question") != question or event.get("selected_question_id") != question_id:
        raise ValueError("ordinary selected and returned question mismatch")
    thread_id = decision.get("selected_thread_id")
    thread = _unique(agenda["threads"], "id", thread_id, "selected thread")
    foreground = [item for item in agenda["threads"] if item.get("status") == "foreground"]
    if (foreground != [thread] or thread.get("question_id") != question_id
            or agenda.get("foreground_thread_id") != thread_id
            or thread.get("last_updated_cycle") != cycle):
        raise ValueError("ordinary selected foreground thread mismatch")
    if question.get("status") != "open":
        raise ValueError("ordinary agenda selected a non-open question")
    experiment = result.get("experiment")
    experiment_id = None
    if experiment is not None:
        if type(experiment) is not dict:
            raise ValueError("ordinary returned experiment is malformed")
        experiment_id = experiment.get("id")
        if _unique(post["experiments"], "id", experiment_id, "returned experiment") != experiment:
            raise ValueError("ordinary returned experiment body mismatch")
    routing = result.get("experiment_routing")
    if type(routing) is not dict or routing != event.get("experiment_routing"):
        raise ValueError("ordinary experiment routing proof mismatch")
    if (routing.get("selected_question_id") != question_id
            or routing.get("returned_experiment_id") != experiment_id
            or routing.get("experiment_question_id") != (experiment.get("question_id") if experiment else None)
            or event.get("experiment_id") != experiment_id):
        raise ValueError("ordinary experiment routing identity mismatch")
    intention = result.get("intention")
    if type(intention) is not dict or routing.get("intention_kind") != intention.get("kind") or routing.get("intention_target") != intention.get("target"):
        raise ValueError("ordinary experiment routing intention mismatch")
    owned = bool(experiment is not None and experiment.get("question_id") == question_id)
    if (routing.get("relationship") == "owned") != owned:
        raise ValueError("ordinary experiment routing ownership mismatch")
    if experiment is None and routing.get("relationship") != "no_experiment":
        raise ValueError("ordinary null experiment routing mismatch")
    return deepcopy({
        "decision_id": decision["id"], "cycle": cycle,
        "question_id": question_id, "thread_id": thread_id,
        "experiment_id": experiment_id, "question": question,
        "experiment": experiment, "thread": thread,
        "experiment_routing": routing, "owned": owned,
        "deferral_reason": None if owned else "no_owned_returned_experiment",
    })


def run_cycle(ora_state: dict[str, Any], public_inputs: dict[str, Any], path: str | Path) -> dict[str, Any]:
    """Run exactly one unchanged ordinary cycle, without actuation or providers.

    Only original planning-mode metadata and the evidence provenance label are
    accepted. No input can select an owner or expand the execution envelope.
    A truthful unbound or unowned winner is retained for the executive to defer.
    """
    inputs = validate_public_inputs(public_inputs)
    memory = MemoryStore(ora_state, path)
    pre = memory.load()
    if pre.get("schema_version") != SCHEMA_VERSION or type(pre.get("cycles")) is not int or pre["cycles"] < 0:
        raise ValueError("ordinary bridge requires current copied Ora schema")
    for name in ("questions", "experiments"):
        _unique_ids(pre.get(name), name)
    if type(pre.get("agenda")) is not dict:
        raise ValueError("ordinary bridge requires copied agenda state")
    for name in ("decisions", "threads", "archived_threads"):
        _unique_ids(pre["agenda"].get(name), f"agenda {name}")
    cycle_inputs = {
        "stimulus": None, "observation": None, "cognition": False,
        "cognition_provider": None, "strict_experiment_admission": False,
        "action_lab": False, "planning_lab": False,
        "_phase42_counterfactual": False,
        "_withhold_current_prediction_evidence": False,
        "_now_override": None, "copy_public_observations": None,
        "copy_early_public_admission": False,
        "copy_frontier_grounded_handoff": False,
        "copy_public_capacity": None,
        "copy_public_resolution_dispatch": False,
    }
    # Intentionally the only cycle invocation. No callback, monkeypatch, second
    # agenda pass, reconstructed ranking, sensor, or real StateStore is used.
    result = _copy_json(AgentCore(memory).cycle(**cycle_inputs))
    post, events = memory.load(), memory.events
    if memory.save_count != 1 or len(events) != 1:
        raise ValueError("ordinary bridge requires one staged save and one cycle event")
    event = events[0]
    cycle = pre["cycles"] + 1
    if (type(result) is not dict or result.get("cycle") != cycle
            or post.get("cycles") != cycle or post.get("generation") != cycle
            or event.get("event") != "cycle" or event.get("cycle") != cycle):
        raise ValueError("ordinary bridge cycle/result/event mismatch")
    if (event.get("observation_supplied") is not False
            or event.get("stimulus_supplied") is not False
            or result.get("prediction_result") is not None
            or result.get("prediction") is not None
            or result.get("cognition_event") is not None
            or result.get("thought") is not None
            or result.get("action_lab_result") is not None
            or result.get("planning_lab_result") is not None):
        raise ValueError("ordinary bridge envelope was expanded")
    for name in ("questions", "experiments"):
        _unique_ids(post.get(name), name)
    selection = _selection(post, result, event)
    decision = result.get("agenda_decision")
    summaries = decision.get("candidate_summaries", []) if decision else []
    count = decision.get("candidate_count") if decision else None
    if decision and (type(count) is not int or type(summaries) is not list
                     or not 2 <= count or not 1 <= len(summaries) <= min(count, AGENDA_MAX_THREADS)):
        raise ValueError("ordinary bounded candidate summary is malformed")
    diagnostic = decision.get("resumption_causal_counterfactual") if decision else None
    if diagnostic is not None and (diagnostic.get("evaluated") is not False
            or diagnostic.get("causal") is not False
            or diagnostic.get("reason") != "no_current_prediction_evidence_to_withhold"):
        raise ValueError("ordinary bridge entered an unavailable resumption diagnostic")
    return deepcopy({
        "version": BRIDGE_VERSION,
        "pre_state": pre, "post_state": post, "result": result,
        "events": events, "selection": selection,
        "pre_inputs": {"public_inputs": inputs, "cycle_kwargs": cycle_inputs, "store_path": str(memory.path)},
        "treatments": {
            "planning_lab_actuation": "deferred_by_inquiry_executive",
            "original_requested_planning_mode": "enabled" if inputs["planning_lab_requested"] else "disabled",
            "action_lab_actuation": "disabled",
            "repository_observation": "omitted_by_first_slice",
            "legacy_resumption_diagnostic": "no_current_prediction_evidence",
            "provenance": inputs["provenance"],
        },
        "candidate_summary": {
            "candidate_count": count, "retained_count": len(summaries),
            "summaries": summaries, "truncated": count is not None and count > len(summaries),
            "complete_preselection_manifest": False,
            "disclosure": "Ordinary agenda retains at most four candidate summaries; a full preselection candidate manifest is not instrumented. A no-decision result has no reported candidate count.",
        },
    })
