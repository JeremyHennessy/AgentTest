from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .cognition import CognitionProvider, run_cognition
from .drives import choose_intention, compute_drives
from .perception import COMPARABLE_FIELDS, changed_fields
from .semantic import consolidate_semantic_memory
from .state import DIMENSIONS, StateStore, utc_now
from .world import consolidate_world

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
    """Persistent loop with memory, world model, prediction, drives and cognition."""

    def __init__(self, store: StateStore | None = None) -> None:
        self.store = store or StateStore()

    def cycle(
        self,
        stimulus: str | None = None,
        observation: dict[str, Any] | None = None,
        cognition: bool = False,
        cognition_provider: CognitionProvider | None = None,
    ) -> dict[str, Any]:
        state = self.store.load()
        state["cycles"] += 1
        state["generation"] = state["cycles"]
        cycle = state["cycles"]
        now = utc_now()
        surprise = None
        prediction_result = None

        if observation is not None:
            prediction_result = self._evaluate_prediction(state, observation, now)
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

        semantic_update = consolidate_semantic_memory(state)
        world_update = consolidate_world(state)

        self._update_metrics(state)
        drives = compute_drives(state, surprise, prediction_result)
        state["drives"] = drives
        intention = choose_intention(state, drives)
        state["intentions"].append(intention)

        cognition_event = None
        thought = None
        if cognition:
            cognition_event, thought = run_cognition(
                state,
                intention,
                cognition_provider,
            )

        question_text = self._generate_question(state, surprise, intention, thought)
        question = self._upsert_question(state, question_text)
        question["times_selected"] += 1
        question["last_selected_cycle"] = cycle

        experiment = self._select_or_propose_experiment(
            state,
            question,
            intention,
            thought,
        )

        prediction = None
        if observation is not None:
            prediction = self._make_prediction(state, observation, now)
            state["predictions"].append(prediction)

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
            "prediction_result_id": (
                prediction_result["id"] if prediction_result else None
            ),
            "semantic_update": semantic_update,
            "world_update": world_update,
            "intention_id": intention["id"],
            "cognition_event_id": cognition_event["id"] if cognition_event else None,
            "cognition_candidate_id": thought["id"] if thought else None,
            "selected_question_id": question["id"],
            "experiment_id": experiment["id"],
            "new_prediction_id": prediction["id"] if prediction else None,
            "drives": drives,
            "metrics": state["metrics"],
        }
        self.store.append_journal(event)
        return {
            "cycle": cycle,
            "surprise": surprise,
            "prediction_result": prediction_result,
            "semantic_update": semantic_update,
            "world_update": world_update,
            "drives": drives,
            "intention": intention,
            "cognition_event": cognition_event,
            "thought": thought,
            "question": question,
            "experiment": experiment,
            "prediction": prediction,
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
            "source": "experiment",
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
        consolidate_world(state)
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

    def _evaluate_prediction(
        self,
        state: dict[str, Any],
        observation: dict[str, Any],
        now: str,
    ) -> dict[str, Any] | None:
        pending = [
            item for item in state.get("predictions", [])
            if item.get("status") == "pending"
        ]
        if not pending:
            return None

        prediction = pending[-1]
        expected = prediction["expected"]

        expected_baseline = expected.get("baseline_fingerprint")
        observed_baseline = observation.get("baseline_fingerprint")
        baseline_changed = (
            observed_baseline is not None
            and expected_baseline != observed_baseline
        )

        if baseline_changed:
            prediction["status"] = "invalidated_by_intervention"
            prediction["evaluated_at"] = now
            prediction["errors"] = {
                "baseline_fingerprint": {
                    "expected": expected_baseline,
                    "observed": observed_baseline,
                }
            }
            prediction["evidence_strength"] = 1.0
            reflection = {
                "id": f"R{len(state['reflections']) + 1:06d}",
                "source": "prediction",
                "prediction_id": prediction["id"],
                "cycle": state["cycles"],
                "outcome": prediction["status"],
                "evidence_strength": 1.0,
                "lesson": (
                    "The prior repository-stability prediction was invalidated by a "
                    "non-state repository intervention. Do not score the intervention "
                    "as an environmental prediction error."
                ),
            }
            state["reflections"].append(reflection)
            return prediction

        changes = {}
        for field in COMPARABLE_FIELDS:
            before = expected.get(field)
            after = observation.get(field)
            if before != after:
                changes[field] = {"expected": before, "observed": after}

        prediction["status"] = "violated" if changes else "confirmed"
        prediction["evaluated_at"] = now
        prediction["errors"] = changes
        prediction["evidence_strength"] = 1.0

        reflection = {
            "id": f"R{len(state['reflections']) + 1:06d}",
            "source": "prediction",
            "prediction_id": prediction["id"],
            "cycle": state["cycles"],
            "outcome": prediction["status"],
            "evidence_strength": 1.0,
            "lesson": (
                "Measured repository stability prediction was "
                f"{prediction['status']}; use the observed error fields rather than "
                "inventing a cause."
            ),
        }
        state["reflections"].append(reflection)
        return prediction

    def _make_prediction(
        self,
        state: dict[str, Any],
        observation: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        expected = {field: observation.get(field) for field in COMPARABLE_FIELDS}
        return {
            "id": f"P{len(state['predictions']) + 1:06d}",
            "cycle": state["cycles"],
            "created_at": now,
            "status": "pending",
            "statement": (
                "Measured repository fields will remain unchanged until the next "
                "self-observation unless an intervening change occurs."
            ),
            "expected": expected,
            "falsification": "Any change in a measured comparable field violates this prediction.",
        }

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
        surprise: dict[str, Any] | None,
        intention: dict[str, Any],
        thought: dict[str, Any] | None,
    ) -> str:
        if intention["kind"] == "resolve_pending_evidence" and intention.get("target"):
            candidate = (
                f"What obtainable evidence would resolve pending experiment "
                f"{intention['target']} with the least additional assumption?"
            )
            if not self._question_exists(state, candidate):
                return candidate

        if thought is not None:
            candidate = thought["question"].strip()
            if not self._question_exists(state, candidate):
                return candidate

        if intention["kind"] == "explain_change" and surprise and surprise["changes"]:
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

    def _select_or_propose_experiment(
        self,
        state: dict[str, Any],
        question: dict[str, Any],
        intention: dict[str, Any],
        thought: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if intention["kind"] == "resolve_pending_evidence" and intention.get("target"):
            match = next(
                (
                    item for item in state["experiments"]
                    if item["id"] == intention["target"]
                    and item.get("status") == "proposed"
                ),
                None,
            )
            if match is not None:
                match["last_selected_cycle"] = state["cycles"]
                return match

        if thought is not None and _norm(question["text"]) == _norm(thought["question"]):
            hypothesis = thought["hypothesis"]
            method = thought["experiment"]
            falsification = thought["falsification"]
            predicted_observation = thought["predicted_observation"]
            cognition_candidate_id = thought["id"]
        else:
            hypothesis = (
                "A deliberately chosen disconfirming observation will reduce more "
                "uncertainty than collecting another confirming example."
            )
            method = (
                "Seek one observation that would make the current working idea less "
                "likely, and record the result before changing behavior."
            )
            falsification = (
                "The experiment fails if it cannot name a possible observation that "
                "would count against the hypothesis."
            )
            predicted_observation = None
            cognition_candidate_id = None

        experiment = {
            "id": f"X{len(state['experiments']) + 1:06d}",
            "cycle": state["cycles"],
            "question_id": question["id"],
            "status": "proposed",
            "intention_id": intention["id"],
            "cognition_candidate_id": cognition_candidate_id,
            "hypothesis": hypothesis,
            "method": method,
            "falsification": falsification,
            "predicted_observation": predicted_observation,
            "created_at": utc_now(),
        }
        state["experiments"].append(experiment)
        return experiment

    def _update_metrics(self, state: dict[str, Any]) -> None:
        cycles = state["cycles"]
        completed = [
            experiment
            for experiment in state["experiments"]
            if experiment.get("status") == "completed"
        ]
        evaluated_predictions = [
            prediction
            for prediction in state.get("predictions", [])
            if prediction.get("status") in {"confirmed", "violated"}
        ]
        accepted_cognition = [
            item
            for item in state.get("cognition_candidates", [])
            if item.get("status") == "proposed"
        ]
        stable_replay = any(
            diagnostic.get("kind") == "deterministic_replay"
            and diagnostic.get("status") == "completed"
            and diagnostic.get("outcome") == "stable"
            for diagnostic in state.get("proposal_diagnostics", [])
        )
        semantic = state.get("semantic_memory", {})
        semantic_concepts = len(semantic.get("concepts", {}))
        world = state.get("world_model", {})
        current_claims = len(world.get("current", {}))
        open_questions = [
            question for question in state["questions"] if question["status"] == "open"
        ]
        unique_questions = len({_norm(item["text"]) for item in state["questions"]})

        state["metrics"].update(
            {
                "continuity": 1.0 if cycles >= 2 else (0.5 if cycles == 1 else 0.0),
                "memory": min(1.0, len(state["episodes"]) / 4.0),
                "semantic_memory": min(1.0, semantic_concepts / 8.0),
                "perception": min(1.0, len(state["environment_snapshots"]) / 3.0),
                "world_model": min(1.0, current_claims / 8.0),
                "cognition": min(1.0, len(accepted_cognition) / 3.0),
                "self_model": (
                    0.9 if evaluated_predictions else
                    (0.85 if state["environment_snapshots"] else (0.75 if cycles else 0.0))
                ),
                "curiosity": min(1.0, len(open_questions) / 5.0),
                "agency": min(1.0, len(state.get("intentions", [])) / 5.0),
                "learning": min(
                    1.0,
                    (len(completed) + len(evaluated_predictions)) / 5.0,
                ),
                "adaptation": min(1.0, len(state["accepted_changes"]) / 3.0),
                "reflection": min(1.0, len(state["reflections"]) / 5.0),
                "open_endedness": min(1.0, unique_questions / max(1, cycles)),
                "reproducibility": (
                    1.0 if stable_replay else (0.8 if cycles else 0.0)
                ),
            }
        )
