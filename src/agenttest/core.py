from __future__ import annotations

import json
import re
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from .action_lab import step_action_lab
from .agenda import update_agenda
from .cognition import CognitionProvider, run_cognition
from .drives import choose_intention, compute_drives
from .evidence import known_evidence_ids
from .episode_identity import allocate_episode_id, episode_sequence
from .learning import (
    REPOSITORY_STABILITY_FAMILY,
    consolidate_empirical_learning,
    empirical_family,
    expected_prediction_status,
)
from .native_evidence import validate_native_evidence_payload
from .native_inquiry import (
    NATIVE_INQUIRY_SOURCE,
    native_inquiry_metadata,
    validate_native_inquiry_candidate,
)
from .perception import COMPARABLE_FIELDS, changed_fields
from .planning_lab import step_planning_lab
from .public_observation import (
    SOURCE as PUBLIC_OBSERVATION_SOURCE,
    admit as admit_public_observation,
    allocate_selected as allocate_public_observation,
    bind_evidence as bind_public_evidence,
    ingest as ingest_public_observation,
    load_bundle as load_public_bundle,
    obtainable_contract as obtainable_public_contract,
    require_capacity_proofs as require_public_capacity_proofs,
    registry_eligible as public_registry_eligible,
)
from .semantic import (
    actionable_open_questions,
    consolidate_inquiry_families,
    consolidate_semantic_memory,
    question_has_active_experiment_path,
)
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
PREDICTION_EXPERIMENT_QUESTION = (
    "Will measured repository fields remain unchanged until the next "
    "self-observation unless an intervening code change alters the baseline?"
)
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
        if experiment.get("status") not in {"proposed", "parked_blocked"}:
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
            native_candidate = experiment.get("native_inquiry")
            if not isinstance(native_candidate, dict):
                native_candidate = None

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

            source_refs = (
                candidate.get("evidence_refs", [])
                if candidate is not None
                else (
                    native_candidate.get("evidence_refs", [])
                    if native_candidate is not None
                    else []
                )
            )
            candidate_refs = [
                str(ref)
                for ref in source_refs
                if isinstance(ref, str) and ref in known_ids
            ]
            all_candidate_refs_grounded = (
                bool(source_refs)
                and len(candidate_refs) == len(source_refs)
            )
            evidence_source = (
                {
                    "kind": (
                        "native_inquiry_evidence"
                        if native_candidate is not None
                        else "grounded_candidate_evidence"
                    ),
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
                "source_candidate_id": (
                    str(native_candidate.get("candidate_id"))
                    if native_candidate is not None
                    else (str(candidate_id) if candidate_id else None)
                ),
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


def _reconcile_blocked_experiment_parking(
    state: dict[str, Any],
    *,
    allow_parking: bool,
) -> dict[str, Any]:
    """Park mature blocked work while preserving automatic evidence-based re-entry."""

    cycle = int(state.get("cycles", 0))
    parked: list[str] = []
    reactivated: list[str] = []

    for experiment in state.get("experiments", []):
        experiment_id = str(experiment.get("id", ""))
        status = experiment.get("status")
        specification = experiment.get("specification", {})
        actionability = (
            specification.get("actionability")
            if isinstance(specification, dict)
            else None
        )

        if status == "parked_blocked":
            if actionability in {"actionable", "evidence_ready"}:
                experiment["status"] = "proposed"
                experiment["reactivated_cycle"] = cycle
                experiment["reactivation_reason"] = (
                    "Grounded specification evidence became available after parking."
                )
                experiment.setdefault("status_history", []).append(
                    {
                        "cycle": cycle,
                        "from": "parked_blocked",
                        "to": "proposed",
                        "reason": "grounded_specification_became_actionable",
                    }
                )
                reactivated.append(experiment_id)
            continue

        if not allow_parking or status != "proposed":
            continue
        if experiment.get("readiness") != "needs_specification":
            continue
        if actionability != "blocked":
            continue

        experiment["status"] = "parked_blocked"
        experiment["parked_cycle"] = cycle
        experiment["parked_reason"] = "grounded_specification_unavailable"
        experiment.setdefault("status_history", []).append(
            {
                "cycle": cycle,
                "from": "proposed",
                "to": "parked_blocked",
                "reason": "grounded_specification_unavailable",
                "missing_fields": list(specification.get("missing_fields", [])),
                "grounded_evidence_refs": list(
                    specification.get("grounded_evidence_refs", [])
                ),
            }
        )
        parked.append(experiment_id)

    return {
        "cycle": cycle,
        "parking_enabled": allow_parking,
        "parked_experiment_ids": parked,
        "reactivated_experiment_ids": reactivated,
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
        native_inquiry = experiment.get("native_inquiry")
        if isinstance(native_inquiry, dict):
            experiment["readiness"] = "awaiting_native_evidence"
            experiment["readiness_reason"] = (
                "A native inquiry owns a dedicated fresh native-evidence "
                "resolution contract."
            )
            preserved_pending.append(experiment_id)
            continue

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
    if status not in {
        "confirmed",
        "violated",
        "invalidated_by_intervention",
    }:
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
        if status == "invalidated_by_intervention":
            outcome = "inconclusive"
            completion_source = "prediction_contract_invalidated_by_intervention"
            completion_reason = "prediction_invalidated_by_intervention"
        else:
            outcome = "supported" if status == expected else "falsified"
            completion_source = "prediction_status_contract"
            completion_reason = "prediction_status_contract_resolved"

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
        experiment["completion_source"] = completion_source
        experiment["completed_at"] = completed_at
        history = experiment.setdefault("status_history", [])
        history.append(
            {
                "cycle": state.get("cycles", 0),
                "from": "proposed",
                "to": "completed",
                "reason": completion_reason,
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

    def record_native_evidence(
        self,
        evidence: dict[str, Any],
        *,
        enabled: bool = False,
        persist: bool = False,
        _now_override: str | None = None,
    ) -> dict[str, Any]:
        """Record one normalized native evidence episode without running a cycle."""
        if enabled is not True:
            raise RuntimeError("native evidence interface is disabled by default")

        loaded = self.store.load()
        normalized = validate_native_evidence_payload(evidence)
        state = loaded if persist else deepcopy(loaded)
        cycle = int(state.get("cycles", 0) or 0)
        now = _now_override or utc_now()
        before_count = len(state.get("episodes", []))
        self._remember(
            state,
            cycle,
            now,
            "native_inquiry_evidence",
            json.dumps(normalized, sort_keys=True),
            [
                "native_evidence",
                str(normalized["relation"]["kind"]),
                str(normalized["relation"]["feature"]),
            ],
        )
        episode = deepcopy(state["episodes"][before_count])
        if persist:
            self.store.save(state)
        return {
            "enabled": True,
            "persisted": bool(persist),
            "evidence": normalized,
            "evidence_ref": str(episode["id"]),
            "episode": episode,
            "state": deepcopy(state),
        }

    def resolve_native_inquiry(
        self,
        experiment_id: str,
        evidence_ref: str,
        *,
        enabled: bool = False,
        persist: bool = False,
        _now_override: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one temporal native inquiry from one matching outcome transition.

        The interface is disabled and non-persisting by default. It does not
        increment the organism cycle or grant action authority.
        """
        if enabled is not True:
            raise RuntimeError("native inquiry outcome resolver is disabled by default")

        loaded = self.store.load()
        experiment = next(
            (
                item
                for item in loaded.get("experiments", [])
                if str(item.get("id")) == str(experiment_id)
            ),
            None,
        )
        if experiment is None:
            raise ValueError("native inquiry experiment was not found")
        if experiment.get("status") != "proposed":
            raise ValueError("native inquiry experiment is not proposed")
        if experiment.get("readiness") != "awaiting_native_evidence":
            raise ValueError("native inquiry experiment is not awaiting native evidence")

        native = experiment.get("native_inquiry")
        if not isinstance(native, dict):
            raise ValueError("experiment is not a native inquiry experiment")
        expected_relation = native.get("relation")
        if not isinstance(expected_relation, dict):
            raise ValueError("native inquiry relation is unavailable")
        sequence_floor = native.get(
            "resolution_evidence_floor_episode_sequence"
        )
        legacy_floor = native.get("resolution_evidence_floor_episode_count")
        if sequence_floor is not None:
            if type(sequence_floor) is not int or sequence_floor < 0:
                raise ValueError(
                    "native inquiry resolution evidence sequence floor is unavailable"
                )
        elif type(legacy_floor) is not int or legacy_floor < 0:
            raise ValueError("native inquiry resolution evidence floor is unavailable")

        episodes = loaded.get("episodes", [])
        episode_index = next(
            (
                index
                for index, item in enumerate(episodes)
                if str(item.get("id")) == str(evidence_ref)
            ),
            None,
        )
        episode = episodes[episode_index] if episode_index is not None else None
        if episode is None or episode.get("kind") != "native_inquiry_evidence":
            raise ValueError("native inquiry outcome evidence was not found")

        if sequence_floor is not None:
            evidence_sequence = episode_sequence(episode.get("id"))
            if evidence_sequence is None:
                raise ValueError(
                    "native inquiry outcome evidence has no monotonic episode sequence"
                )
            if evidence_sequence <= sequence_floor:
                raise ValueError("native inquiry outcome evidence predates the inquiry")
        else:
            next_episode_index = loaded.get("next_episode_index")
            if (
                type(next_episode_index) is int
                and next_episode_index != len(episodes) + 1
            ):
                raise ValueError(
                    "legacy native inquiry evidence floor cannot be used after "
                    "episode archival"
                )
            if episode_index < legacy_floor:
                raise ValueError("native inquiry outcome evidence predates the inquiry")
        try:
            payload = json.loads(str(episode.get("content") or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("native inquiry outcome evidence is not valid JSON") from exc
        evidence = validate_native_evidence_payload(payload)
        relation = evidence.get("relation")
        if relation != expected_relation:
            raise ValueError("native inquiry outcome relation does not match experiment")

        grounding_observation_refs: set[str] = set()
        episodes_by_id = {
            str(item.get("id")): item
            for item in episodes
            if item.get("id")
        }
        for grounding_ref in native.get("evidence_refs", []):
            grounding_episode = episodes_by_id.get(str(grounding_ref))
            if (
                not isinstance(grounding_episode, dict)
                or grounding_episode.get("kind") != "native_inquiry_evidence"
            ):
                continue
            try:
                grounding_payload = json.loads(
                    str(grounding_episode.get("content") or "")
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    "native inquiry grounding evidence is not valid JSON"
                ) from exc
            grounding_evidence = validate_native_evidence_payload(grounding_payload)
            if grounding_evidence.get("relation") != expected_relation:
                continue
            grounding_observation_refs.update(
                str(ref) for ref in grounding_evidence.get("observation_refs", [])
            )

        outcome_observation_refs = {
            str(ref) for ref in evidence.get("observation_refs", [])
        }
        if not outcome_observation_refs - grounding_observation_refs:
            raise ValueError(
                "native inquiry outcome evidence contains no post-inquiry observation"
            )

        if evidence.get("measurement_kind") != "binary_transition_outcomes":
            raise ValueError(
                "native inquiry resolver currently supports temporal binary outcomes only"
            )
        if relation.get("kind") not in {
            "same_next_observation",
            "changes_next_observation",
        }:
            raise ValueError("native inquiry resolver requires a temporal relation")

        measurement = evidence.get("measurement")
        if not isinstance(measurement, dict):
            raise ValueError("native inquiry outcome measurement is unavailable")
        evaluable = int(measurement.get("evaluable", 0) or 0)
        confirmations = int(measurement.get("confirmations", 0) or 0)
        refutations = int(measurement.get("refutations", 0) or 0)
        if evaluable != 1 or confirmations + refutations != 1:
            raise ValueError(
                "native inquiry resolution requires exactly one evaluable transition"
            )
        if confirmations not in {0, 1} or refutations not in {0, 1}:
            raise ValueError("native inquiry outcome must be unambiguous")
        outcome = "supported" if confirmations == 1 else "falsified"

        state = loaded if persist else deepcopy(loaded)
        resolved_experiment = next(
            item
            for item in state["experiments"]
            if str(item.get("id")) == str(experiment_id)
        )
        now = _now_override or utc_now()
        cycle = int(state.get("cycles", 0) or 0)

        resolved_experiment["status"] = "completed"
        resolved_experiment["readiness"] = "resolved"
        resolved_experiment["outcome"] = outcome
        resolved_experiment["evidence_strength"] = 1.0
        resolved_experiment["evidence_refs"] = [str(evidence_ref)]
        resolved_experiment["completion_source"] = "native_evidence_contract"
        resolved_experiment["completed_at"] = now
        resolved_experiment["native_resolution"] = {
            "version": "native-inquiry-resolution-v1",
            "evidence_ref": str(evidence_ref),
            "relation": deepcopy(relation),
            "measurement_kind": evidence["measurement_kind"],
            "outcome": outcome,
        }
        resolved_experiment.setdefault("status_history", []).append(
            {
                "cycle": cycle,
                "from": "proposed",
                "to": "completed",
                "reason": "native_evidence_contract_resolved",
                "evidence_refs": [str(evidence_ref)],
                "outcome": outcome,
            }
        )

        reflection = {
            "id": f"R{len(state.get('reflections', [])) + 1:06d}",
            "source": "native_inquiry",
            "experiment_id": str(experiment_id),
            "evidence_ref": str(evidence_ref),
            "cycle": cycle,
            "outcome": outcome,
            "evidence_strength": 1.0,
            "lesson": (
                "One matching evaluable native transition "
                f"{outcome} the bounded temporal inquiry. Treat this as an "
                "experiment outcome, not as a general causal fact."
            ),
        }
        state.setdefault("reflections", []).append(reflection)

        if persist:
            self.store.save(state)

        return {
            "enabled": True,
            "persisted": bool(persist),
            "resolved": True,
            "experiment": deepcopy(resolved_experiment),
            "reflection": deepcopy(reflection),
            "evidence": deepcopy(evidence),
            "state": deepcopy(state),
        }

    def propose_native_inquiry(
        self,
        candidate: dict[str, Any],
        *,
        enabled: bool = False,
        persist: bool = False,
    ) -> dict[str, Any]:
        """Validate and stage one bounded native inquiry without running a cycle.

        The interface is intentionally disabled by default. Enabling it does not
        grant action authority, increment the organism cycle, or execute an
        environment transition. With persist=False it operates on a deep copy.
        """
        if enabled is not True:
            raise RuntimeError("native inquiry interface is disabled by default")

        loaded = self.store.load()
        validated = validate_native_inquiry_candidate(candidate, loaded)
        state = loaded if persist else deepcopy(loaded)
        cycle = int(state.get("cycles", 0) or 0)

        intention = {
            "id": f"I{len(state.get('intentions', [])) + 1:06d}",
            "cycle": cycle,
            "kind": "reduce_uncertainty",
            "dominant_drive": "uncertainty",
            "strength": float(validated["objective_score"]),
            "target": None,
            "rationale": (
                "Explicit opt-in native inquiry staged from persisted grounded "
                f"evidence using {validated['objective']}."
            ),
            "evidence_refs": list(validated["evidence_refs"]),
            "native_inquiry_candidate_id": validated["id"],
        }
        state.setdefault("intentions", []).append(intention)

        question = self._upsert_question(state, validated["question"])
        question["source"] = NATIVE_INQUIRY_SOURCE
        question["source_evidence_refs"] = list(validated["evidence_refs"])
        question["native_inquiry_candidate_id"] = validated["id"]
        question["native_relation"] = deepcopy(validated["relation"])

        thought = {
            "id": validated["id"],
            "question": validated["question"],
            "hypothesis": validated["hypothesis"],
            "experiment": validated["method"],
            "falsification": validated["falsification"],
            "predicted_observation": validated["predicted_observation"],
        }
        experiment = self._select_or_propose_experiment(
            state,
            question,
            intention,
            thought,
            require_grounded=True,
        )
        if experiment is None:
            raise RuntimeError("grounded native inquiry did not produce an experiment")

        experiment["cognition_candidate_id"] = None
        experiment["native_inquiry_candidate_id"] = validated["id"]
        experiment["native_inquiry"] = native_inquiry_metadata(validated)
        experiment["native_inquiry"]["resolution_evidence_floor_episode_count"] = len(
            state.get("episodes", [])
        )
        next_episode_index = int(state.get("next_episode_index", 1) or 1)
        if next_episode_index < 1:
            raise RuntimeError("native inquiry episode sequence is unavailable")
        experiment["native_inquiry"][
            "resolution_evidence_floor_episode_sequence"
        ] = next_episode_index - 1
        experiment["predicted_observation"] = validated["predicted_observation"]
        experiment["readiness"] = "awaiting_native_evidence"
        specification_update = _trace_experiment_specifications(state)
        specification = experiment.get("specification", {})
        if specification.get("actionability") != "actionable":
            raise RuntimeError("native inquiry failed grounded actionability tracing")

        inquiry_update = consolidate_inquiry_families(state)
        if persist:
            self.store.save(state)

        return {
            "enabled": True,
            "persisted": bool(persist),
            "candidate": validated,
            "intention": deepcopy(intention),
            "question": deepcopy(question),
            "experiment": deepcopy(experiment),
            "specification_update": deepcopy(specification_update),
            "inquiry_update": deepcopy(inquiry_update),
            "state": deepcopy(state),
        }

    def cycle(
        self,
        stimulus: str | None = None,
        observation: dict[str, Any] | None = None,
        cognition: bool = False,
        cognition_provider: CognitionProvider | None = None,
        strict_experiment_admission: bool = False,
        action_lab: bool = False,
        planning_lab: bool = False,
        _phase42_counterfactual: bool = False,
        _withhold_current_prediction_evidence: bool = False,
        _now_override: str | None = None,
        copy_public_observations: str | Path | None = None,
        copy_early_public_admission: bool = False,
        copy_frontier_grounded_handoff: bool = False,
        copy_public_capacity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if action_lab and planning_lab:
            raise ValueError("action_lab and planning_lab are mutually exclusive")
        state = self.store.load()
        if (copy_early_public_admission or copy_frontier_grounded_handoff) and self.store.path.resolve() == Path("state/organism.json").resolve():
            raise ValueError("frontier preparation requires an explicit copied store")
        if copy_frontier_grounded_handoff and not copy_early_public_admission:
            raise ValueError("frontier handoff requires common early public admission")
        public_trace = None
        if copy_public_observations is not None:
            if self.store.path.resolve() == Path("state/organism.json").resolve():
                raise ValueError("public observation inlet requires an explicit copied store")
            public_trace = ingest_public_observation(
                state, load_public_bundle(copy_public_observations),
            )
        state["cycles"] += 1
        state["generation"] = state["cycles"]
        cycle = state["cycles"]
        now = _now_override or utc_now()
        surprise = None
        prediction_result = None
        prediction_experiment = None
        experiment_dedup_update = _reconcile_duplicate_experiments(state)
        experiment_readiness_update = _review_experiment_readiness(state)
        experiment_specification_update = _trace_experiment_specifications(state)
        experiment_parking_update = _reconcile_blocked_experiment_parking(
            state,
            allow_parking=strict_experiment_admission,
        )

        if observation is not None:
            if not _withhold_current_prediction_evidence:
                prediction_result = self._evaluate_prediction(
                    state,
                    observation,
                    now,
                )
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

        action_lab_result = None
        if action_lab:
            action_lab_result = step_action_lab(state)
            self._remember(
                state,
                cycle,
                now,
                "action_lab",
                json.dumps(
                    {
                        "action": action_lab_result["action"],
                        "before": action_lab_result["before"],
                        "after": action_lab_result["after"],
                        "delta": action_lab_result["delta"],
                        "blocked": action_lab_result["blocked"],
                        "decision": action_lab_result["decision"],
                    },
                    sort_keys=True,
                ),
                [
                    "action_lab",
                    str(action_lab_result["action"]),
                    "causal_action",
                    "movement",
                ],
            )

        planning_lab_result = None
        if planning_lab:
            planning_lab_result = step_planning_lab(state)
            self._remember(
                state,
                cycle,
                now,
                "planning_lab",
                json.dumps(
                    {
                        "action": planning_lab_result.get("action"),
                        "before": planning_lab_result.get("before"),
                        "predicted_after": planning_lab_result.get("predicted_after"),
                        "after": planning_lab_result.get("after"),
                        "goal": planning_lab_result.get("goal"),
                        "goal_reached": planning_lab_result.get("goal_reached"),
                        "matched_prediction": planning_lab_result.get(
                            "matched_prediction"
                        ),
                        "plan_id": planning_lab_result.get("plan_id"),
                    },
                    sort_keys=True,
                ),
                [
                    "planning_lab",
                    "goal_directed_action",
                    "persistent_plan",
                    "model_based_planning",
                ],
            )

        if public_trace is not None:
            for pair in public_trace["pairs"]:
                self._remember(
                    state, cycle, now, "native_inquiry_evidence",
                    json.dumps(pair["evidence"], sort_keys=True),
                    ["native_evidence", pair["relation"], pair["evidence"]["relation"]["feature"]],
                )
                bind_public_evidence(
                    state, public_trace["source"], pair["pair_id"],
                    pair["relation"], state["episodes"][-1]["id"],
                )
        semantic_update = consolidate_semantic_memory(state)
        world_update = consolidate_world(state)
        empirical_learning_update = consolidate_empirical_learning(state)

        self._update_metrics(state)
        strict_question_attention = (
            strict_experiment_admission and observation is not None
        )
        drives = compute_drives(
            state,
            surprise,
            prediction_result,
            strict_question_attention=strict_question_attention,
        )
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

        if public_trace is not None and copy_early_public_admission:
            contracts = admit_public_observation(
                state, public_trace["source"], self._upsert_question,
            )
        if copy_early_public_admission:
            require_public_capacity_proofs(state, copy_public_capacity or {})
        frontier_pool = self._frontier_obtainable_pool(state, copy_public_capacity or {}) if copy_early_public_admission else []
        public_allocations_before_generation = [item["id"] for item in state.get("experiments", [])
                                                if item.get("public_observation_family")] if copy_early_public_admission else []
        legacy_question_text = self._generate_question(
            state,
            surprise,
            intention,
            thought,
            strict_question_attention=strict_question_attention,
            copy_frontier_grounded_handoff=copy_frontier_grounded_handoff,
            copy_public_capacity=copy_public_capacity,
        )
        legacy_question = self._upsert_question(state, legacy_question_text)
        if public_trace is not None:
            if not copy_early_public_admission:
                contracts = admit_public_observation(
                    state, public_trace["source"], self._upsert_question,
                )
            public_trace["contracts"] = contracts
            public_trace["eligible_families"] = [
                q["public_observation_family"] for q in state["questions"]
                if q.get("source") == PUBLIC_OBSERVATION_SOURCE
                and public_registry_eligible(state, q)
            ]
        self._annotate_frontier_question(legacy_question, legacy_question_text, intention,
                                         policy_enabled=copy_frontier_grounded_handoff)

        # Build the next repository prediction path after the cycle's drive and
        # intention are already chosen, but before agenda scoring. This preserves
        # the current-cycle drive decision while ensuring Phase 42 does not score
        # a stale gap between resolving the prior prediction experiment and
        # creating its evidence-ready successor.
        prediction = None
        if observation is not None:
            prediction = self._make_prediction(state, observation, now)
            state["predictions"].append(prediction)
            prediction_experiment = self._create_prediction_experiment(
                state,
                prediction,
                now,
            )

        agenda_decision = update_agenda(
            state,
            legacy_question=legacy_question,
            cycle=cycle,
        )
        if (
            agenda_decision is not None
            and not _phase42_counterfactual
            and agenda_decision.get(
                "priority_change_supported_by_new_evidence"
            ) is True
        ):
            selected = agenda_decision.get("selected") or {}
            counterfactual_record = {
                "method": "same-prior-state-full-cycle-v1",
                "withheld_source": (
                    "current_prediction_evaluation"
                    if prediction_result is not None
                    else None
                ),
                "evidence_refs": list(
                    selected.get("new_evidence_refs", [])
                    if isinstance(selected, dict)
                    else []
                ),
                "actual_selected_thread_id": agenda_decision.get(
                    "selected_thread_id"
                ),
                "actual_selected_question_id": (
                    selected.get("question_id")
                    if isinstance(selected, dict)
                    else None
                ),
                "counterfactual_selected_thread_id": None,
                "counterfactual_selected_question_id": None,
                "counterfactual_intention_kind": None,
                "counterfactual_legacy_question_id": None,
                "causal": False,
                "evaluated": False,
                "reason": None,
            }
            causal = False
            if prediction_result is None:
                counterfactual_record["reason"] = (
                    "no_current_prediction_evidence_to_withhold"
                )
            elif cognition:
                # Never replay a model/provider call merely to satisfy a
                # scientific diagnostic. Normal autonomous operation is
                # cognition-free; an unprovable provider-backed event remains
                # non-genuine rather than being replayed externally.
                counterfactual_record["reason"] = (
                    "cognition_enabled_counterfactual_not_replayed"
                )
            else:
                prior_state = self.store.load()
                with tempfile.TemporaryDirectory() as temp:
                    counterfactual_store = StateStore(
                        Path(temp) / "organism.json"
                    )
                    counterfactual_store.save(deepcopy(prior_state))
                    counterfactual_result = AgentCore(
                        counterfactual_store
                    ).cycle(
                        stimulus=stimulus,
                        observation=observation,
                        cognition=False,
                        strict_experiment_admission=strict_experiment_admission,
                        action_lab=action_lab,
                        planning_lab=planning_lab,
                        _phase42_counterfactual=True,
                        _withhold_current_prediction_evidence=True,
                        _now_override=now,
                        copy_public_observations=copy_public_observations,
                        copy_early_public_admission=copy_early_public_admission,
                        copy_frontier_grounded_handoff=copy_frontier_grounded_handoff,
                        copy_public_capacity=copy_public_capacity,
                    )
                counterfactual_decision = counterfactual_result.get(
                    "agenda_decision"
                )
                counterfactual_record["evaluated"] = True
                counterfactual_record["counterfactual_intention_kind"] = (
                    (counterfactual_result.get("intention") or {}).get("kind")
                )
                counterfactual_record["counterfactual_legacy_question_id"] = (
                    (counterfactual_result.get("question") or {}).get("id")
                )
                if isinstance(counterfactual_decision, dict):
                    counterfactual_selected = (
                        counterfactual_decision.get("selected") or {}
                    )
                    counterfactual_record[
                        "counterfactual_selected_thread_id"
                    ] = counterfactual_decision.get("selected_thread_id")
                    counterfactual_record[
                        "counterfactual_selected_question_id"
                    ] = (
                        counterfactual_selected.get("question_id")
                        if isinstance(counterfactual_selected, dict)
                        else None
                    )
                    causal = (
                        counterfactual_decision.get("selected_thread_id")
                        != agenda_decision.get("selected_thread_id")
                    )
                    counterfactual_record["reason"] = (
                        "withholding_current_prediction_evidence_changed_selection"
                        if causal
                        else "same_thread_resumed_without_current_prediction_evidence"
                    )
                else:
                    counterfactual_record["reason"] = (
                        "counterfactual_agenda_decision_unavailable"
                    )
            counterfactual_record["causal"] = causal
            agenda_decision[
                "priority_change_supported_by_new_evidence"
            ] = causal
            agenda_decision["resumption_causal_counterfactual"] = (
                counterfactual_record
            )
            agenda_decision["resumption_causal_evidence_refs"] = list(
                counterfactual_record["evidence_refs"]
            )

            if causal:
                last_resumption = state.get("agenda", {}).get(
                    "last_genuine_resumption"
                )
                if isinstance(last_resumption, dict):
                    last_resumption["causal_method"] = (
                        counterfactual_record["method"]
                    )
                    last_resumption["causal_evidence_refs"] = list(
                        counterfactual_record["evidence_refs"]
                    )
                    last_resumption["counterfactual_selected_thread_id"] = (
                        counterfactual_record[
                            "counterfactual_selected_thread_id"
                        ]
                    )
                    last_resumption[
                        "counterfactual_selected_question_id"
                    ] = counterfactual_record[
                        "counterfactual_selected_question_id"
                    ]
            else:
                # update_agenda provisionally increments the durable counter
                # from evidence coexistence alone. Restore the exact persisted
                # pre-cycle accounting unless the full-cycle counterfactual
                # proves the new evidence changed which thread won.
                prior_agenda = self.store.load().get("agenda", {})
                state["agenda"]["genuine_resumption_count"] = int(
                    prior_agenda.get("genuine_resumption_count", 0) or 0
                )
                state["agenda"]["last_genuine_resumption"] = deepcopy(
                    prior_agenda.get("last_genuine_resumption")
                )
        question = legacy_question
        if agenda_decision is not None:
            selected_question_id = str(
                agenda_decision.get("selected", {}).get("question_id") or ""
            )
            agenda_question = next(
                (
                    item
                    for item in state.get("questions", [])
                    if str(item.get("id") or "") == selected_question_id
                ),
                None,
            )
            if agenda_question is not None:
                question = agenda_question

        question["times_selected"] += 1
        question["last_selected_cycle"] = cycle
        inquiry_update = consolidate_inquiry_families(state)

        if question.get("source") == PUBLIC_OBSERVATION_SOURCE:
            # Never allow a generic intention's target to substitute an
            # unrelated experiment for the actually selected native question.
            experiment = allocate_public_observation(state, question, agenda_decision, now)
        else:
            experiment = self._select_or_propose_experiment(
                state,
                question,
                intention,
                thought,
                require_grounded=(
                    strict_experiment_admission and observation is not None
                ),
            )
        if public_trace is not None:
            public_trace["selected_question_id"] = question["id"]
            public_trace["native_selected"] = question.get("source") == PUBLIC_OBSERVATION_SOURCE
            public_trace["allocation_id"] = experiment["id"] if public_trace["native_selected"] and experiment else None
            public_trace["selection_status"] = (
                "selected" if public_trace["native_selected"] else
                "ordinary_defer" if public_trace["eligible_families"] else
                "exhausted" if public_trace["contracts"] else "zero_pairs_stop"
            )

        if copy_early_public_admission:
            # Origin is separate from the selected question's source provenance.
            frontier_trace = {
                "policy_enabled": copy_frontier_grounded_handoff,
                "intention_origin": {
                    "id": intention.get("id"), "kind": intention.get("kind"),
                    "target": intention.get("target"),
                    "evidence_refs": list(intention.get("evidence_refs", [])),
                },
                "eligible_pool": [{"question_id": item["question"]["id"],
                                   "selection_order": list(item["order"]),
                                   "source_evidence_refs": list(item["question"].get("source_evidence_refs", [])),
                                   "availability": item["proof"]["availability"]}
                                  for item in frontier_pool],
                "generated_legacy_question_id": legacy_question["id"],
                "passive_allocation_ids_before_generation": public_allocations_before_generation,
                "agenda_selected_question_id": question["id"],
                "returned_experiment_id": experiment.get("id") if experiment else None,
            }

        target_experiment = next(
            (item for item in state["experiments"]
             if item.get("id") == intention.get("target")), None,
        )
        experiment_routing = {
            "selected_question_id": question["id"],
            "returned_experiment_id": experiment.get("id") if experiment else None,
            "experiment_question_id": experiment.get("question_id") if experiment else None,
            "relationship": self._experiment_question_relationship(question, experiment, intention),
            "intention_kind": intention["kind"],
            "intention_target": intention.get("target"),
            "target_relationship": (
                self._experiment_question_relationship(question, target_experiment, intention)
                if target_experiment is not None else "unchecked"
            ),
        }
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
            "experiment_parking_update": experiment_parking_update,
            "action_lab_result": action_lab_result,
            "planning_lab_result": planning_lab_result,
            "semantic_update": semantic_update,
            "inquiry_update": inquiry_update,
            "agenda_decision": agenda_decision,
            "world_update": world_update,
            "empirical_learning_update": empirical_learning_update,
            "self_model_calibration": self_model_calibration,
            "intention_id": intention["id"],
            "cognition_event_id": cognition_event["id"] if cognition_event else None,
            "cognition_candidate_id": thought["id"] if thought else None,
            "selected_question_id": question["id"],
            "experiment_id": experiment["id"] if experiment else None,
            "experiment_routing": experiment_routing,
            "new_prediction_id": prediction["id"] if prediction else None,
            "prediction_experiment_id": (
                prediction_experiment["id"] if prediction_experiment else None
            ),
            "drives": drives,
            "strict_actionable_question_ids": (
                [
                    str(item.get("id"))
                    for item in actionable_open_questions(state)
                ]
                if strict_question_attention
                else None
            ),
            "metrics": state["metrics"],
        }
        if copy_early_public_admission:
            event["copy_frontier_handoff_trace"] = frontier_trace
        self.store.append_journal(event)
        result = {
            "cycle": cycle,
            "surprise": surprise,
            "prediction_result": prediction_result,
            "experiment_dedup_update": experiment_dedup_update,
            "experiment_readiness_update": experiment_readiness_update,
            "experiment_specification_update": experiment_specification_update,
            "experiment_parking_update": experiment_parking_update,
            "action_lab_result": action_lab_result,
            "planning_lab_result": planning_lab_result,
            "semantic_update": semantic_update,
            "inquiry_update": inquiry_update,
            "agenda_decision": agenda_decision,
            "world_update": world_update,
            "empirical_learning_update": empirical_learning_update,
            "self_model_calibration": self_model_calibration,
            "drives": drives,
            "strict_actionable_questions": (
                actionable_open_questions(state)
                if strict_question_attention
                else None
            ),
            "intention": intention,
            "cognition_event": cognition_event,
            "thought": thought,
            "question": question,
            "experiment": experiment,
            "experiment_routing": experiment_routing,
            "prediction": prediction,
            "prediction_experiment": prediction_experiment,
            "metrics": state["metrics"],
        }
        if copy_early_public_admission:
            result["copy_frontier_handoff_trace"] = frontier_trace
        if public_trace is not None:
            result["public_observation_trace"] = public_trace
        return result

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
            prediction["resolved_experiment_ids"] = _resolve_experiments_from_prediction(
                state,
                prediction,
                reflection,
                completed_at=now,
            )
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
        expected_status = expected_prediction_status(
            state,
            REPOSITORY_STABILITY_FAMILY,
        )
        family = empirical_family(state, REPOSITORY_STABILITY_FAMILY)
        if expected_status == "violated":
            statement = (
                "At least one measured repository field will change before the next "
                "self-observation unless an intervening code change alters the baseline."
            )
            falsification = (
                "If every measured comparable field remains unchanged on the next "
                "same-baseline observation, this change expectation is falsified."
            )
        else:
            statement = (
                "Measured repository fields will remain unchanged until the next "
                "self-observation unless an intervening code change alters the baseline."
            )
            falsification = (
                "Any change in a measured comparable field violates this prediction."
            )

        empirical_basis = None
        if family is not None:
            empirical_basis = {
                "version": state.get("empirical_learning", {}).get("version"),
                "evaluable_trials": int(family.get("evaluable_trials", 0) or 0),
                "stable_observations": int(
                    family.get("stable_observations", 0) or 0
                ),
                "change_observations": int(
                    family.get("change_observations", 0) or 0
                ),
                "inconclusive_trials": int(
                    family.get("inconclusive_trials", 0) or 0
                ),
                "stability_rate": family.get("stability_rate"),
                "evidence_refs": list(family.get("evidence_refs", []))[-16:],
            }

        return {
            "id": f"P{len(state['predictions']) + 1:06d}",
            "cycle": state["cycles"],
            "created_at": now,
            "status": "pending",
            "statement": statement,
            "expected": expected,
            "expected_status": expected_status,
            "learning_family": REPOSITORY_STABILITY_FAMILY,
            "empirical_basis": empirical_basis,
            "falsification": falsification,
        }

    def _create_prediction_experiment(
        self,
        state: dict[str, Any],
        prediction: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        """Bind the next repository self-observation to a falsifiable experiment."""

        question = self._upsert_question(state, PREDICTION_EXPERIMENT_QUESTION)
        question["times_selected"] = int(question.get("times_selected", 0) or 0) + 1
        question["last_selected_cycle"] = state["cycles"]
        question.setdefault("source", "repository_stability_prediction")

        experiment = {
            "id": f"X{len(state['experiments']) + 1:06d}",
            "cycle": state["cycles"],
            "question_id": question["id"],
            "status": "proposed",
            "readiness": "evidence_ready",
            "readiness_reason": (
                "A pending repository-state prediction supplies a structured "
                "prediction-status evidence contract."
            ),
            "source": "repository_stability_prediction",
            "intention_id": None,
            "cognition_candidate_id": None,
            "hypothesis": prediction["statement"],
            "method": (
                "Compare the next repository self-observation with the pending "
                "prediction. A changed baseline invalidates the test rather than "
                "counting as support or falsification."
            ),
            "falsification": prediction["falsification"],
            "predicted_observation": (
                "The next comparable repository self-observation differs in at least "
                "one measured field."
                if prediction.get("expected_status") == "violated"
                else (
                    "The next comparable repository self-observation matches the "
                    "prediction's measured fields."
                )
            ),
            "learning_family": prediction.get(
                "learning_family",
                REPOSITORY_STABILITY_FAMILY,
            ),
            "empirical_basis": prediction.get("empirical_basis"),
            "evidence_contract": {
                "kind": PREDICTION_CONTRACT_KIND,
                "prediction_id": prediction["id"],
                "expected_status": prediction.get(
                    "expected_status",
                    "confirmed",
                ),
            },
            "created_at": now,
            "times_selected": 1,
            "last_selected_cycle": state["cycles"],
        }
        state["experiments"].append(experiment)
        return experiment


    def _remember(
        self,
        state: dict[str, Any],
        cycle: int,
        now: str,
        kind: str,
        content: str,
        concepts: list[str],
    ) -> None:
        episode_id = allocate_episode_id(state)
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
        *,
        strict_question_attention: bool = False,
        copy_frontier_grounded_handoff: bool = False,
        copy_public_capacity: dict[str, Any] | None = None,
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

        if (
            intention["kind"] == "explore_empirical_frontier"
            and intention.get("target")
        ):
            if copy_frontier_grounded_handoff:
                pool = self._frontier_obtainable_pool(state, copy_public_capacity or {})
                if pool:
                    return str(min(pool, key=lambda item: item["order"])["question"]["text"])
            return self._frontier_template(intention["target"])

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

        fallback = (
            "Which assumption in my current decision process has gone longest "
            "without an attempt to falsify it?"
        )
        blocked_question_ids = self._blocked_question_ids(state)
        fallback_match = next(
            (
                item
                for item in state.get("questions", [])
                if _norm(str(item.get("text", ""))) == _norm(fallback)
            ),
            None,
        )
        if (
            intention.get("kind") == "reduce_uncertainty"
            and fallback_match is not None
            and str(fallback_match.get("id")) in blocked_question_ids
        ):
            eligible = self._least_selected_eligible_open_question(
                state,
                blocked_question_ids,
                strict_question_attention=strict_question_attention,
            )
            if eligible is not None:
                return str(eligible["text"])
            if strict_question_attention:
                return PREDICTION_EXPERIMENT_QUESTION
        return fallback

    def _blocked_question_ids(self, state: dict[str, Any]) -> set[str]:
        return {
            str(experiment.get("question_id"))
            for experiment in state.get("experiments", [])
            if (
                experiment.get("status") in {"proposed", "parked_blocked"}
                and experiment.get("question_id")
                and experiment.get("specification", {}).get("actionability")
                == "blocked"
            )
        }

    @staticmethod
    def _frontier_template(target: Any) -> str:
        return ("Which distinct measurable relationship should be tested next to "
                f"challenge or extend the learned {target} pattern?")

    def _annotate_frontier_question(self, question: dict[str, Any], text: str,
                                    intention: dict[str, Any], *, policy_enabled: bool) -> None:
        if (intention.get("kind") == "explore_empirical_frontier"
                and (not policy_enabled or (
                    text == self._frontier_template(intention.get("target"))
                    and question.get("source") in {None, "empirical_frontier_transfer"}))):
            question.setdefault("source", "empirical_frontier_transfer")
            question["source_learning_family"] = intention.get("target")
            question["source_evidence_refs"] = list(intention.get("evidence_refs", []))

    @staticmethod
    def _question_order(question: dict[str, Any]) -> tuple:
        return (int(question.get("times_selected", 0) or 0),
                int(question.get("last_selected_cycle", -1) or -1),
                int(question.get("created_cycle", 0) or 0),
                str(question.get("id", "")))

    def _frontier_obtainable_pool(self, state: dict[str, Any], capacity_receipts: dict[str, Any]) -> list[dict[str, Any]]:
        # All provable passive contracts across every registered source/feature.
        # No experiment status alone, preferred world/name or objective score.
        pool = []
        for question in state.get("questions", []):
            proof = obtainable_public_contract(state, question, capacity_receipts)
            if proof is not None:
                pool.append({"question": question, "proof": proof,
                             "order": self._question_order(question)})
        return pool

    def _least_selected_eligible_open_question(
        self,
        state: dict[str, Any],
        blocked_question_ids: set[str],
        *,
        strict_question_attention: bool = False,
    ) -> dict[str, Any] | None:
        eligible = [
            question
            for question in state.get("questions", [])
            if (
                question.get("status") == "open"
                and str(question.get("id")) not in blocked_question_ids
                and (
                    not strict_question_attention
                    or question_has_active_experiment_path(state, question)
                )
            )
        ]
        if not eligible:
            return None
        return min(
            eligible,
            key=self._question_order,
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

    @staticmethod
    def _experiment_question_relationship(
        question: dict[str, Any],
        experiment: dict[str, Any] | None,
        intention: dict[str, Any],
    ) -> str:
        """Describe the route without treating an intention target as ownership."""
        if experiment is None:
            return "no_experiment"
        if not question.get("id") or not experiment.get("question_id"):
            return "unknown"
        if question["id"] == experiment["question_id"]:
            return "owned"
        target = experiment.get("id")
        followups = {
            "specify_experiment": (
                "What observable, evidence source, and resolution rule would make "
                f"experiment {target} evidence-ready?"
            ),
            "resolve_pending_evidence": (
                "What obtainable evidence would resolve pending experiment "
                f"{target} with the least additional assumption?"
            ),
        }
        expected = followups.get(str(intention.get("kind")))
        if (target and intention.get("target") == target and expected
                and _norm(str(question.get("text") or "")) == _norm(expected)):
            return "explicit_followup"
        return "unrelated"

    def _select_or_propose_experiment(
        self,
        state: dict[str, Any],
        question: dict[str, Any],
        intention: dict[str, Any],
        thought: dict[str, Any] | None,
        *,
        require_grounded: bool = False,
    ) -> dict[str, Any] | None:
        if question.get("source") == PUBLIC_OBSERVATION_SOURCE:
            # Native allocation belongs exclusively to the actual post-agenda
            # hook. A generic intention or thought cannot authorize it here.
            return None
        if intention["kind"] == "specify_experiment" and intention.get("target"):
            match = next(
                (
                    item for item in state["experiments"]
                    if item["id"] == intention["target"]
                    and self._experiment_question_relationship(question, item, intention)
                    in {"owned", "explicit_followup"}
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
                    and self._experiment_question_relationship(question, item, intention)
                    in {"owned", "explicit_followup"}
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
            if require_grounded:
                return None
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
