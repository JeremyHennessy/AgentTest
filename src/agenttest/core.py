from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .cognition import CognitionProvider, run_cognition
from .drives import choose_intention, compute_drives
from .evidence import known_evidence_ids
from .perception import COMPARABLE_FIELDS, changed_fields
from .semantic import consolidate_inquiry_families, consolidate_semantic_memory
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


def _recent_ids(
    items: list[dict[str, Any]],
    *,
    limit: int = 4,
    predicate=None,
) -> list[str]:
    refs: list[str] = []
    for item in reversed(items):
        if predicate is not None and not predicate(item):
            continue
        identifier = item.get("id")
        if identifier and str(identifier) not in refs:
            refs.append(str(identifier))
        if len(refs) >= limit:
            break
    refs.reverse()
    return refs


def _semantic_episode_refs(state: dict[str, Any], limit: int = 4) -> list[str]:
    refs: list[str] = []
    concepts = state.get("semantic_memory", {}).get("concepts", {})
    if not isinstance(concepts, dict):
        return refs
    ranked = sorted(
        concepts.values(),
        key=lambda item: (
            int(item.get("last_cycle", 0)),
            int(item.get("count", 0)),
            str(item.get("concept", "")),
        ),
        reverse=True,
    )
    for item in ranked:
        for ref in reversed(item.get("episode_refs", [])):
            if isinstance(ref, str) and ref not in refs:
                refs.append(ref)
            if len(refs) >= limit:
                return list(reversed(refs))
    return list(reversed(refs))


def _calibrate_self_model(state: dict[str, Any]) -> dict[str, Any]:
    self_model = state.setdefault("self_model", {})
    capabilities = list(
        dict.fromkeys(
            str(capability)
            for capability in self_model.get("capabilities", [])
            if str(capability).strip()
        )
    )

    episodes = state.get("episodes", [])
    questions = state.get("questions", [])
    experiments = state.get("experiments", [])
    predictions = state.get("predictions", [])
    intentions = state.get("intentions", [])
    cognition_events = state.get("cognition_events", [])
    cognition_candidates = state.get("cognition_candidates", [])
    reviews = state.get("proposal_reviews", [])
    world_claims = state.get("world_model", {}).get("claims", [])

    environment_refs = _recent_ids(
        episodes,
        predicate=lambda item: item.get("kind") == "environment",
    )
    semantic_refs = _semantic_episode_refs(state)
    current_world_refs = _recent_ids(
        [
            claim
            for claim in world_claims
            if claim.get("status") == "current"
        ]
    )

    registry: dict[str, dict[str, Any]] = {}

    def observed(refs: list[str], rationale: str) -> dict[str, Any]:
        return {
            "status": "observed",
            "evidence_refs": refs,
            "rationale": rationale,
            "calibrated_cycle": state.get("cycles", 0),
        }

    def unverified(reason: str) -> dict[str, Any]:
        return {
            "status": "unverified",
            "evidence_refs": [],
            "reason": reason,
            "calibrated_cycle": state.get("cycles", 0),
        }

    for capability in capabilities:
        if capability == "persistent structured state":
            refs = _recent_ids(episodes, limit=2)
            registry[capability] = (
                observed(
                    refs,
                    "Persistent episodes are present in the loaded state across the current history.",
                )
                if refs
                else unverified("No persistent episode evidence is present yet.")
            )
        elif capability == "append-only event journal":
            registry[capability] = unverified(
                "The live state does not currently expose a citable journal-write evidence ID."
            )
        elif capability == "question generation from accumulated concepts":
            refs = _recent_ids(questions)
            registry[capability] = (
                observed(refs, "Persisted generated questions are present.")
                if refs
                else unverified("No generated question has been persisted yet.")
            )
        elif capability == "selection of explicit falsifiable experiments":
            refs = _recent_ids(experiments)
            registry[capability] = (
                observed(refs, "Persisted experiments with falsification criteria are present.")
                if refs
                else unverified("No experiment evidence is present yet.")
            )
        elif capability == "narrow repository self-perception through auditable sensors":
            registry[capability] = (
                observed(environment_refs, "Environment episodes record repository sensor observations.")
                if environment_refs
                else unverified("No environment-sensor episode is present yet.")
            )
        elif capability == "one-step prediction of measured repository state":
            refs = _recent_ids(predictions)
            registry[capability] = (
                observed(refs, "Persisted repository predictions are present.")
                if refs
                else unverified("No prediction evidence is present yet.")
            )
        elif capability == "endogenous evidence-driven intention selection":
            refs = _recent_ids(intentions)
            registry[capability] = (
                observed(refs, "Persisted intention selections are present.")
                if refs
                else unverified("No intention-selection evidence is present yet.")
            )
        elif capability == "validated boundary for optional model-generated candidate thoughts":
            refs = _recent_ids(cognition_candidates)
            if refs:
                registry[capability] = observed(
                    refs,
                    "At least one model candidate passed the cognition grounding boundary.",
                )
            else:
                accepted_events = _recent_ids(
                    cognition_events,
                    predicate=lambda item: item.get("status") == "accepted",
                )
                registry[capability] = (
                    observed(
                        accepted_events,
                        "At least one cognition event passed the grounding boundary.",
                    )
                    if accepted_events
                    else unverified(
                        "No accepted live cognition candidate exists; provider-unavailable events do not verify grounding acceptance."
                    )
                )
        elif capability == "deterministic semantic consolidation with source episode references":
            registry[capability] = (
                observed(
                    semantic_refs,
                    "Semantic memory entries retain source episode references.",
                )
                if semantic_refs
                else unverified("Semantic memory has no citable source episodes yet.")
            )
        elif capability == "temporal world claims that preserve superseded observed values":
            registry[capability] = (
                observed(
                    current_world_refs,
                    "Current provenance-backed world claims are present.",
                )
                if current_world_refs
                else unverified("No provenance-backed world claim is present yet.")
            )
        elif capability == "evidence-backed self-authored change manifests without code execution":
            refs = _recent_ids(reviews)
            registry[capability] = (
                observed(
                    refs,
                    "Proposal review evidence demonstrates that a self-authored manifest reached governance review.",
                )
                if refs
                else unverified(
                    "No citable proposal-review evidence exists yet for a self-authored manifest."
                )
            )
        elif capability == "proposal review that distinguishes direct problem evidence from measurement gaps":
            refs = _recent_ids(reviews)
            registry[capability] = (
                observed(
                    refs,
                    "Persisted proposal reviews contain evidence-relevance verdicts.",
                )
                if refs
                else unverified("No proposal review has been persisted yet.")
            )
        elif capability == "persistent human interaction surface with evidence-linked responses":
            interaction_episode_refs = [
                str(item.get("input_episode_id"))
                for item in state.get("interactions", [])[-4:]
                if item.get("input_episode_id")
            ]
            registry[capability] = (
                observed(
                    interaction_episode_refs,
                    "Persisted human interaction records point to their source stimulus episodes.",
                )
                if interaction_episode_refs
                else unverified(
                    "No human interaction record with a citable stimulus episode exists yet."
                )
            )
        else:
            registry[capability] = unverified(
                "No explicit calibration rule has been defined for this capability claim."
            )

    counts = Counter(claim["status"] for claim in registry.values())
    total = len(capabilities)
    grounded = sum(
        1
        for claim in registry.values()
        if claim["status"] in {"verified", "observed", "unverified"}
    )
    summary = {
        "version": "self-model-calibration-v1",
        "total": total,
        "grounded": grounded,
        "coverage": 1.0 if total == 0 else grounded / total,
        "verified": counts.get("verified", 0),
        "observed": counts.get("observed", 0),
        "unverified": counts.get("unverified", 0),
        "calibrated_cycle": state.get("cycles", 0),
    }
    self_model["capability_claims"] = registry
    self_model["calibration"] = summary
    return summary


PREDICTION_CONTRACT_KIND = "prediction_status"
EXPERIMENT_STALE_AFTER_CYCLES = 3


def _valid_prediction_contract(experiment: dict[str, Any]) -> bool:
    contract = experiment.get("evidence_contract")
    if not isinstance(contract, dict):
        return False
    if contract.get("kind") != PREDICTION_CONTRACT_KIND:
        return False
    prediction_id = contract.get("prediction_id")
    expected_status = contract.get("expected_status")
    return (
        isinstance(prediction_id, str)
        and bool(prediction_id)
        and expected_status in {"confirmed", "violated"}
    )


def _later_prediction_evidence_refs(
    state: dict[str, Any],
    *,
    after_cycle: int,
    limit: int = 4,
) -> list[str]:
    refs: list[str] = []
    for reflection in reversed(state.get("reflections", [])):
        if reflection.get("source") != "prediction":
            continue
        if int(reflection.get("cycle", 0)) <= after_cycle:
            continue
        if reflection.get("outcome") not in {"confirmed", "violated"}:
            continue
        for identifier in (
            reflection.get("prediction_id"),
            reflection.get("id"),
        ):
            if identifier and str(identifier) not in refs:
                refs.append(str(identifier))
            if len(refs) >= limit:
                return list(reversed(refs))
    return list(reversed(refs))


def _reconcile_duplicate_experiments(state: dict[str, Any]) -> dict[str, Any]:
    """Preserve duplicate history while leaving one active canonical experiment."""

    cycle = int(state.get("cycles", 0))
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for experiment in state.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue
        if _valid_prediction_contract(experiment):
            continue
        question_id = str(experiment.get("question_id") or "")
        method = _norm(str(experiment.get("method") or ""))
        if not question_id or not method:
            continue
        groups.setdefault((question_id, method), []).append(experiment)

    superseded: list[str] = []
    canonical_groups: list[dict[str, Any]] = []
    for (question_id, method), experiments in sorted(groups.items()):
        if len(experiments) < 2:
            continue
        ordered = sorted(
            experiments,
            key=lambda item: (
                int(item.get("cycle", 0)),
                str(item.get("id", "")),
            ),
        )
        canonical = ordered[0]
        duplicate_ids: list[str] = []
        for duplicate in ordered[1:]:
            duplicate_id = str(duplicate.get("id", ""))
            duplicate["status"] = "superseded_duplicate"
            duplicate["duplicate_of"] = str(canonical.get("id", ""))
            duplicate["superseded_cycle"] = cycle
            duplicate.setdefault("status_history", []).append(
                {
                    "cycle": cycle,
                    "from": "proposed",
                    "to": "superseded_duplicate",
                    "reason": "exact_uncontracted_question_method_duplicate",
                    "canonical_experiment_id": str(canonical.get("id", "")),
                }
            )
            duplicate_ids.append(duplicate_id)
            superseded.append(duplicate_id)

        canonical_groups.append(
            {
                "question_id": question_id,
                "normalized_method": method,
                "canonical_experiment_id": str(canonical.get("id", "")),
                "superseded_experiment_ids": duplicate_ids,
            }
        )

    return {
        "cycle": cycle,
        "superseded_experiment_ids": superseded,
        "canonical_groups": canonical_groups,
    }


SPECIFICATION_VERSION = "experiment-specification-v1"
SPECIFICATION_REQUIRED_FIELDS = (
    "observable",
    "evidence_source",
    "resolution_rule",
)


def _trace_experiment_specifications(state: dict[str, Any]) -> dict[str, Any]:
    """Trace specification readiness without inventing observations or evidence."""

    cycle = int(state.get("cycles", 0))
    known_ids = known_evidence_ids(state)
    cognition_candidates = {
        str(item.get("id")): item
        for item in state.get("cognition_candidates", [])
        if item.get("id")
    }
    changed: list[str] = []
    blocked: list[str] = []
    actionable: list[str] = []
    ready: list[str] = []

    for experiment in state.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue

        experiment_id = str(experiment.get("id", ""))
        if _valid_prediction_contract(experiment):
            contract = experiment["evidence_contract"]
            traced = {
                "version": SPECIFICATION_VERSION,
                "actionability": "evidence_ready",
                "observable": {
                    "kind": "prediction_status",
                    "prediction_id": str(contract.get("prediction_id")),
                },
                "evidence_source": {
                    "kind": "prediction",
                    "refs": [str(contract.get("prediction_id"))],
                },
                "resolution_rule": {
                    "kind": "expected_prediction_status",
                    "expected_status": str(contract.get("expected_status")),
                },
                "available_fields": list(SPECIFICATION_REQUIRED_FIELDS),
                "missing_fields": [],
                "grounded_evidence_refs": [
                    str(contract.get("prediction_id"))
                ],
                "current_grounded_evidence_can_supply": True,
                "blocking_reason": None,
                "source_candidate_id": experiment.get("cognition_candidate_id"),
            }
            ready.append(experiment_id)
        else:
            candidate_id = experiment.get("cognition_candidate_id")
            candidate = (
                cognition_candidates.get(str(candidate_id))
                if candidate_id
                else None
            )

            observable_text = experiment.get("predicted_observation")
            if (
                (not isinstance(observable_text, str) or not observable_text.strip())
                and candidate is not None
                and isinstance(candidate.get("predicted_observation"), str)
                and candidate.get("predicted_observation", "").strip()
            ):
                observable_text = candidate["predicted_observation"]
            observable = (
                str(observable_text).strip()
                if isinstance(observable_text, str) and observable_text.strip()
                else None
            )

            candidate_refs = (
                [
                    str(ref)
                    for ref in candidate.get("evidence_refs", [])
                    if isinstance(ref, str) and ref in known_ids
                ]
                if candidate is not None
                else []
            )
            all_candidate_refs_grounded = (
                candidate is not None
                and bool(candidate.get("evidence_refs"))
                and len(candidate_refs) == len(candidate.get("evidence_refs", []))
            )
            evidence_source = (
                {
                    "kind": "grounded_candidate_evidence",
                    "refs": candidate_refs,
                }
                if all_candidate_refs_grounded
                else None
            )

            falsification = experiment.get("falsification")
            if (
                (not isinstance(falsification, str) or not falsification.strip())
                and candidate is not None
                and isinstance(candidate.get("falsification"), str)
            ):
                falsification = candidate.get("falsification")
            resolution_rule = (
                str(falsification).strip()
                if observable is not None
                and isinstance(falsification, str)
                and falsification.strip()
                else None
            )

            available_fields = []
            if observable is not None:
                available_fields.append("observable")
            if evidence_source is not None:
                available_fields.append("evidence_source")
            if resolution_rule is not None:
                available_fields.append("resolution_rule")
            missing_fields = [
                field
                for field in SPECIFICATION_REQUIRED_FIELDS
                if field not in available_fields
            ]

            can_supply = not missing_fields
            actionability = "actionable" if can_supply else "blocked"
            blocking_reason = (
                None
                if can_supply
                else (
                    "Current grounded state does not explicitly supply: "
                    + ", ".join(missing_fields)
                    + "."
                )
            )
            traced = {
                "version": SPECIFICATION_VERSION,
                "actionability": actionability,
                "observable": observable,
                "evidence_source": evidence_source,
                "resolution_rule": resolution_rule,
                "available_fields": available_fields,
                "missing_fields": missing_fields,
                "grounded_evidence_refs": candidate_refs,
                "current_grounded_evidence_can_supply": can_supply,
                "blocking_reason": blocking_reason,
                "source_candidate_id": str(candidate_id) if candidate_id else None,
            }
            (actionable if can_supply else blocked).append(experiment_id)

        previous = experiment.get("specification")
        previous_comparable = (
            {
                key: value
                for key, value in previous.items()
                if key != "evaluated_cycle"
            }
            if isinstance(previous, dict)
            else None
        )
        if previous_comparable != traced:
            traced["evaluated_cycle"] = cycle
            experiment["specification"] = traced
            experiment.setdefault("specification_history", []).append(
                {
                    "cycle": cycle,
                    "actionability": traced["actionability"],
                    "missing_fields": list(traced["missing_fields"]),
                    "grounded_evidence_refs": list(
                        traced["grounded_evidence_refs"]
                    ),
                }
            )
            changed.append(experiment_id)

    return {
        "cycle": cycle,
        "changed_experiment_ids": changed,
        "blocked_experiment_ids": blocked,
        "actionable_experiment_ids": actionable,
        "evidence_ready_experiment_ids": ready,
    }


def _review_experiment_readiness(state: dict[str, Any]) -> dict[str, Any]:
    cycle = int(state.get("cycles", 0))
    changed: list[str] = []
    ready: list[str] = []
    preserved_pending: list[str] = []

    for experiment in state.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue

        experiment_id = str(experiment.get("id", ""))
        if _valid_prediction_contract(experiment):
            experiment["readiness"] = "evidence_ready"
            experiment["readiness_reason"] = (
                "A structured prediction-status evidence contract is present."
            )
            ready.append(experiment_id)
            continue

        created_cycle = int(experiment.get("cycle", 0))
        age = cycle - created_cycle
        later_refs = _later_prediction_evidence_refs(
            state,
            after_cycle=created_cycle,
        )
        if age < EXPERIMENT_STALE_AFTER_CYCLES or not later_refs:
            experiment["readiness"] = "awaiting_specification_or_evidence"
            preserved_pending.append(experiment_id)
            continue

        previous_readiness = experiment.get("readiness")
        experiment["readiness"] = "needs_specification"
        experiment["readiness_reason"] = (
            "The experiment remained proposed for multiple cycles while later "
            "evaluated prediction evidence accumulated, but no structured evidence "
            "contract identifies what observation could resolve it."
        )
        experiment["readiness_review_cycle"] = cycle
        experiment["readiness_evidence_refs"] = later_refs
        if previous_readiness != "needs_specification":
            history = experiment.setdefault("readiness_history", [])
            history.append(
                {
                    "cycle": cycle,
                    "from": previous_readiness,
                    "to": "needs_specification",
                    "reason": "stale_without_structured_evidence_contract",
                    "evidence_refs": later_refs,
                }
            )
            changed.append(experiment_id)

    return {
        "reviewed_cycle": cycle,
        "stale_marked_needs_specification": changed,
        "evidence_ready": ready,
        "preserved_pending": preserved_pending,
    }


def _resolve_experiments_from_prediction(
    state: dict[str, Any],
    prediction: dict[str, Any],
    reflection: dict[str, Any],
    *,
    completed_at: str,
) -> list[str]:
    status = prediction.get("status")
    if status not in {"confirmed", "violated"}:
        return []

    prediction_id = str(prediction.get("id", ""))
    reflection_id = str(reflection.get("id", ""))
    resolved: list[str] = []

    for experiment in state.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue
        if not _valid_prediction_contract(experiment):
            continue

        contract = experiment["evidence_contract"]
        if contract.get("prediction_id") != prediction_id:
            continue

        expected = contract.get("expected_status")
        outcome = "supported" if status == expected else "falsified"
        evidence_refs = [
            identifier
            for identifier in (prediction_id, reflection_id)
            if identifier
        ]

        experiment["status"] = "completed"
        experiment["readiness"] = "resolved"
        experiment["outcome"] = outcome
        experiment["observed_prediction_status"] = status
        experiment["evidence_strength"] = 1.0
        experiment["evidence_refs"] = evidence_refs
        experiment["completion_source"] = "prediction_status_contract"
        experiment["completed_at"] = completed_at
        history = experiment.setdefault("status_history", [])
        history.append(
            {
                "cycle": state.get("cycles", 0),
                "from": "proposed",
                "to": "completed",
                "reason": "prediction_status_contract_resolved",
                "evidence_refs": evidence_refs,
                "outcome": outcome,
            }
        )
        resolved.append(str(experiment.get("id")))

    return resolved


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
        experiment_dedup_update = _reconcile_duplicate_experiments(state)
        experiment_readiness_update = _review_experiment_readiness(state)
        experiment_specification_update = _trace_experiment_specifications(state)

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
        inquiry_update = consolidate_inquiry_families(state)

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

        self_model_calibration = _calibrate_self_model(state)
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
            "experiment_dedup_update": experiment_dedup_update,
            "experiment_readiness_update": experiment_readiness_update,
            "experiment_specification_update": experiment_specification_update,
            "semantic_update": semantic_update,
            "inquiry_update": inquiry_update,
            "world_update": world_update,
            "self_model_calibration": self_model_calibration,
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
            "experiment_dedup_update": experiment_dedup_update,
            "experiment_readiness_update": experiment_readiness_update,
            "experiment_specification_update": experiment_specification_update,
            "semantic_update": semantic_update,
            "inquiry_update": inquiry_update,
            "world_update": world_update,
            "self_model_calibration": self_model_calibration,
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
        _calibrate_self_model(state)
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
            prediction["resolved_experiment_ids"] = []
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
        prediction["resolved_experiment_ids"] = _resolve_experiments_from_prediction(
            state,
            prediction,
            reflection,
            completed_at=now,
        )
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
        if intention["kind"] == "specify_experiment" and intention.get("target"):
            return (
                f"What observable, evidence source, and resolution rule would make "
                f"experiment {intention['target']} evidence-ready?"
            )

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
        if intention["kind"] == "specify_experiment" and intention.get("target"):
            match = next(
                (
                    item for item in state["experiments"]
                    if item["id"] == intention["target"]
                    and (
                        item.get("status") == "needs_specification"
                        or (
                            item.get("status") == "proposed"
                            and item.get("readiness") == "needs_specification"
                        )
                    )
                ),
                None,
            )
            if match is not None:
                match["last_selected_cycle"] = state["cycles"]
                match["specification_attempts"] = (
                    int(match.get("specification_attempts", 0)) + 1
                )
                return match

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

        existing = next(
            (
                item
                for item in state["experiments"]
                if item.get("status") == "proposed"
                and item.get("question_id") == question["id"]
                and _norm(str(item.get("method") or "")) == _norm(method)
            ),
            None,
        )
        if existing is not None:
            existing["last_selected_cycle"] = state["cycles"]
            existing["times_selected"] = int(existing.get("times_selected", 1)) + 1
            return existing

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
            "times_selected": 1,
            "last_selected_cycle": state["cycles"],
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
        inquiry_summary = state.get("semantic_memory", {}).get("inquiry_families", {})
        inquiry_family_count = int(inquiry_summary.get("family_count", unique_questions))

        state["metrics"].update(
            {
                "continuity": 1.0 if cycles >= 2 else (0.5 if cycles == 1 else 0.0),
                "memory": min(1.0, len(state["episodes"]) / 4.0),
                "semantic_memory": min(1.0, semantic_concepts / 8.0),
                "perception": min(1.0, len(state["environment_snapshots"]) / 3.0),
                "world_model": min(1.0, current_claims / 8.0),
                "cognition": min(1.0, len(accepted_cognition) / 3.0),
                "self_model": (
                    float(state.get("self_model", {}).get("calibration", {}).get("coverage"))
                    if state.get("self_model", {}).get("calibration", {}).get("coverage") is not None
                    else (
                        0.9 if evaluated_predictions else
                        (0.85 if state["environment_snapshots"] else (0.75 if cycles else 0.0))
                    )
                ),
                "curiosity": min(1.0, len(open_questions) / 5.0),
                "agency": min(1.0, len(state.get("intentions", [])) / 5.0),
                "learning": min(
                    1.0,
                    (len(completed) + len(evaluated_predictions)) / 5.0,
                ),
                "adaptation": min(1.0, len(state["accepted_changes"]) / 3.0),
                "reflection": min(1.0, len(state["reflections"]) / 5.0),
                "open_endedness": min(1.0, inquiry_family_count / max(1, cycles)),
                "reproducibility": (
                    1.0 if stable_replay else (0.8 if cycles else 0.0)
                ),
            }
        )
