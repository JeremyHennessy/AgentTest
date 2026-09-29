from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .perception import changed_fields
from .state import DIMENSIONS, StateStore, utc_now

_STOPWORDS = {
    "about", "after", "again", "agent", "could", "cycle", "from", "have",
    "into", "itself", "most", "that", "their", "there", "these", "this",
    "through", "what", "when", "where", "which", "with", "would",
}


def _concepts(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text.lower())
    return [word for word in words if word not in _STOPWORDS]


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


class AgentCore:
    """Persistent loop that can observe, remember, question, choose and reflect."""

    def __init__(self, store: StateStore | None = None) -> None:
        self.store = store or StateStore()

    def cycle(
        self,
        stimulus: str | None = None,
        observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.store.load()
        state["cycles"] += 1
        state["generation"] = state["cycles"]
        cycle = state["cycles"]
        now = utc_now()
        surprise = None

        if observation is not None:
            previous = (
                state["environment_snapshots"][-1]
                if state["environment_snapshots"]
                else None
            )
            snapshot = dict(observation)
            snapshot["cycle"] = cycle
            state["environment_snapshots"].append(snapshot)
            changes = changed_fields(previous, snapshot)
            if changes:
                surprise = {
                    "id": f"S{len(state['surprises']) + 1:06d}",
                    "cycle": cycle,
                    "time": now,
                    "changes": changes,
                }
                state["surprises"].append(surprise)

            self._remember(
                state,
                cycle,
                now,
                "environment",
                json.dumps(snapshot, sort_keys=True),
                list(changes.keys()) or ["repository", "observation"],
            )

        if stimulus:
            self._remember(
                state,
                cycle,
                now,
                "stimulus",
                stimulus,
                _concepts(stimulus),
            )

        question_text = self._generate_question(state, surprise)
        question = self._upsert_question(state, question_text)
        question["times_selected"] += 1
        question["last_selected_cycle"] = cycle

        experiment = self._propose_experiment(state, question)
        state["experiments"].append(experiment)

        state["self_model"]["last_updated_cycle"] = cycle
        self._update_metrics(state)
        self.store.save(state)

        event = {
            "event": "cycle",
            "cycle": cycle,
            "time": now,
            "stimulus_supplied": bool(stimulus),
            "observation_supplied": observation is not None,
            "surprise_id": surprise["id"] if surprise else None,
            "selected_question_id": question["id"],
            "proposed_experiment_id": experiment["id"],
            "metrics": state["metrics"],
        }
        self.store.append_journal(event)
        return {
            "cycle": cycle,
            "surprise": surprise,
            "question": question,
            "experiment": experiment,
            "metrics": state["metrics"],
        }

    def record_outcome(
        self,
        experiment_id: str,
        outcome: str,
        evidence_strength: float = 0.5,
    ) -> dict[str, Any]:
        if not 0.0 <= evidence_strength <= 1.0:
            raise ValueError("evidence_strength must be between 0 and 1")

        state = self.store.load()
        match = next(
            (item for item in state["experiments"] if item["id"] == experiment_id),
            None,
        )
        if match is None:
            raise KeyError(f"Unknown experiment: {experiment_id}")
        if match["status"] == "completed":
            raise ValueError(f"Experiment already completed: {experiment_id}")

        match["status"] = "completed"
        match["outcome"] = outcome
        match["evidence_strength"] = evidence_strength
        match["completed_at"] = utc_now()

        reflection = {
            "id": f"R{len(state['reflections']) + 1:06d}",
            "experiment_id": experiment_id,
            "cycle": state["cycles"],
            "outcome": outcome,
            "evidence_strength": evidence_strength,
            "lesson": (
                "Treat this outcome as provisional and weight future choices by its "
                "evidence strength; do not promote it to fact automatically."
            ),
        }
        state["reflections"].append(reflection)
        self._update_metrics(state)
        self.store.save(state)
        self.store.append_journal(
            {
                "event": "experiment_outcome",
                "time": utc_now(),
                "cycle": state["cycles"],
                "experiment_id": experiment_id,
                "evidence_strength": evidence_strength,
            }
        )
        return reflection

    def _remember(
        self,
        state: dict[str, Any],
        cycle: int,
        now: str,
        kind: str,
        content: str,
        concepts: list[str],
    ) -> None:
        episode_id = f"E{len(state['episodes']) + 1:06d}"
        state["episodes"].append(
            {
                "id": episode_id,
                "cycle": cycle,
                "time": now,
                "kind": kind,
                "content": content,
                "concepts": concepts,
            }
        )
        counts = Counter(state.get("concept_counts", {}))
        counts.update(concepts)
        state["concept_counts"] = dict(counts)

    def _generate_question(
        self,
        state: dict[str, Any],
        surprise: dict[str, Any] | None = None,
    ) -> str:
        if surprise and surprise["changes"]:
            field = sorted(surprise["changes"])[0]
            change = surprise["changes"][field]
            candidate = (
                f"What caused repository {field} to change from {change['before']!r} "
                f"to {change['after']!r}, and did that change alter a verified capability?"
            )
            if not self._question_exists(state, candidate):
                return candidate

        counts = state.get("concept_counts", {})
        ranked = sorted(counts.items(), key=lambda item: (item[1], item[0]))

        if len(ranked) >= 2:
            left, right = ranked[0][0], ranked[1][0]
            candidate = (
                f"What observation could distinguish whether {left} and {right} "
                "are meaningfully related rather than merely co-occurring?"
            )
            if not self._question_exists(state, candidate):
                return candidate

        metrics = state.get("metrics", {})
        weakest = min(DIMENSIONS, key=lambda name: metrics.get(name, 0.0))
        candidate = (
            f"What smallest reversible experiment could increase {weakest} "
            "without reducing reproducibility?"
        )
        if not self._question_exists(state, candidate):
            return candidate

        return (
            "Which assumption in my current decision process has gone longest "
            "without an attempt to falsify it?"
        )

    def _question_exists(self, state: dict[str, Any], text: str) -> bool:
        target = _norm(text)
        return any(_norm(item["text"]) == target for item in state["questions"])

    def _upsert_question(self, state: dict[str, Any], text: str) -> dict[str, Any]:
        target = _norm(text)
        for item in state["questions"]:
            if _norm(item["text"]) == target:
                return item

        question = {
            "id": f"Q{len(state['questions']) + 1:06d}",
            "text": text,
            "status": "open",
            "created_cycle": state["cycles"],
            "times_selected": 0,
            "last_selected_cycle": None,
        }
        state["questions"].append(question)
        return question

    def _propose_experiment(
        self, state: dict[str, Any], question: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": f"X{len(state['experiments']) + 1:06d}",
            "cycle": state["cycles"],
            "question_id": question["id"],
            "status": "proposed",
            "hypothesis": (
                "A deliberately chosen disconfirming observation will reduce more "
                "uncertainty than collecting another confirming example."
            ),
            "method": (
                "Seek one observation that would make the current working idea less "
                "likely, and record the result before changing behavior."
            ),
            "falsification": (
                "The experiment fails if it cannot name a possible observation that "
                "would count against the hypothesis."
            ),
            "created_at": utc_now(),
        }

    def _update_metrics(self, state: dict[str, Any]) -> None:
        cycles = state["cycles"]
        completed = [
            experiment
            for experiment in state["experiments"]
            if experiment.get("status") == "completed"
        ]
        open_questions = [
            question for question in state["questions"] if question["status"] == "open"
        ]
        unique_questions = len({_norm(item["text"]) for item in state["questions"]})

        state["metrics"].update(
            {
                "continuity": 1.0 if cycles >= 2 else (0.5 if cycles == 1 else 0.0),
                "memory": min(1.0, len(state["episodes"]) / 4.0),
                "perception": min(1.0, len(state["environment_snapshots"]) / 3.0),
                "self_model": (
                    0.85 if state["environment_snapshots"] else (0.75 if cycles else 0.0)
                ),
                "curiosity": min(1.0, len(open_questions) / 5.0),
                "agency": min(1.0, len(state["experiments"]) / 5.0),
                "learning": min(1.0, len(completed) / 3.0),
                "adaptation": min(1.0, len(state["accepted_changes"]) / 3.0),
                "reflection": min(1.0, len(state["reflections"]) / 3.0),
                "open_endedness": min(1.0, unique_questions / max(1, cycles)),
                "reproducibility": 0.8 if cycles else 0.0,
            }
        )
