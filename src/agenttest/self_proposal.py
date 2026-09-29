from __future__ import annotations

from typing import Any

from .change_control import make_change_manifest

TARGET_ORDER = (
    "learning",
    "reflection",
    "self_model",
    "agency",
    "curiosity",
    "reproducibility",
    "perception",
    "semantic_memory",
    "world_model",
    "memory",
    "continuity",
    "open_endedness",
    "cognition",
)

TARGETS: dict[str, dict[str, Any]] = {
    "learning": {
        "files": ["src/agenttest/core.py", "src/agenttest/drives.py", "tests/test_core.py"],
        "title": "Resolve stale experiment evidence debt",
        "hypothesis": (
            "Separating evidence-ready experiments from underspecified investigations can "
            "prevent stale unresolved work from dominating attention while preserving every "
            "historical experiment and its provenance."
        ),
        "expected_effect": (
            "An experiment with a concrete evidence contract can close only from matching later "
            "evidence; an underspecified stale experiment is retained but marked as needing "
            "specification and no longer contributes to resolvable evidence hunger."
        ),
        "test_plan": (
            "Construct evidence-ready and underspecified experiments, provide later evaluated "
            "prediction evidence, verify only a legitimate match closes, verify stale "
            "underspecified work remains preserved with an explicit non-ready status, and run "
            "the baseline-owned preservation gate."
        ),
        "falsification": (
            "Reject if unrelated evidence closes an experiment, history is deleted, evidence "
            "hunger still counts work that cannot be resolved, or any preserved behavior regresses."
        ),
    },
    "reflection": {
        "files": ["src/agenttest/core.py", "tests/test_core.py"],
        "title": "Structure repeated prediction-error lessons",
        "hypothesis": (
            "Grouping repeated evidence-backed prediction errors by measured field can make "
            "reflection more useful without converting correlations into causal claims."
        ),
        "expected_effect": (
            "Repeated prediction errors produce a structured pattern summary that retains all "
            "source reflection and prediction IDs."
        ),
        "test_plan": (
            "Create repeated controlled prediction errors on one field and verify a derived "
            "pattern appears with complete provenance and no causal assertion."
        ),
        "falsification": (
            "Reject if source evidence is lost, the summary asserts an unobserved cause, or "
            "preserved behavior regresses."
        ),
    },
    "self_model": {
        "files": ["src/agenttest/core.py", "tests/test_core.py"],
        "title": "Calibrate self-model claims against behavioral checks",
        "hypothesis": (
            "Connecting self-model capability claims to explicit passing behavioral evidence "
            "can reduce unsupported self-description."
        ),
        "expected_effect": (
            "Capability claims distinguish implemented, behaviorally verified, and unverified states."
        ),
        "test_plan": (
            "Attach evidence status to selected capability claims and verify a failed behavior "
            "cannot remain labeled verified."
        ),
        "falsification": (
            "Reject if capability labels can advance without evidence or if prior evidence is lost."
        ),
    },
    "agency": {
        "files": ["src/agenttest/drives.py", "tests/test_core.py"],
        "title": "Compare intention choice by expected evidence gain",
        "hypothesis": (
            "Adding evidence-gain information to intention selection can improve action choice "
            "without weakening deterministic reproducibility."
        ),
        "expected_effect": (
            "When two drives are close, the selected intention favors the option with a concrete "
            "resolvable evidence target while retaining deterministic tie behavior."
        ),
        "test_plan": (
            "Construct controlled equal-pressure states with and without resolvable evidence "
            "targets and compare selected intentions under the preservation gate."
        ),
        "falsification": (
            "Reject if intention choice becomes nondeterministic, ignores prediction error, or "
            "regresses a preserved behavior."
        ),
    },
    "curiosity": {
        "files": ["src/agenttest/core.py", "src/agenttest/semantic.py", "tests/test_core.py"],
        "title": "Reduce semantically repetitive questions",
        "hypothesis": (
            "Using semantic-memory overlap when selecting questions can reduce repeated inquiry "
            "while preserving evidence relevance."
        ),
        "expected_effect": (
            "Repeated equivalent stimuli yield fewer near-duplicate questions and more distinct "
            "evidence-grounded inquiry."
        ),
        "test_plan": (
            "Feed repeated and slightly varied concepts, measure question-family duplication, "
            "and run preservation checks."
        ),
        "falsification": (
            "Reject if question diversity does not improve, relevance declines, or preserved behavior regresses."
        ),
    },
    "reproducibility": {
        "files": ["src/agenttest/replay.py", "tests/test_core.py"],
        "title": "Add deterministic cycle replay checks",
        "hypothesis": (
            "Replaying recorded deterministic inputs against an isolated state can reveal "
            "unintended behavioral drift."
        ),
        "expected_effect": (
            "A recorded deterministic cycle can be replayed to an equivalent structured result "
            "after volatile timestamps and identifiers are normalized."
        ),
        "test_plan": (
            "Record a controlled cycle fixture, replay it twice, compare normalized outputs, "
            "and run the baseline-owned preservation gate."
        ),
        "falsification": (
            "Reject if identical controlled inputs produce materially different normalized behavior "
            "or if replay mutates the source state."
        ),
    },
    "perception": {
        "files": ["src/agenttest/perception.py", "tests/test_core.py"],
        "title": "Add evidence about test-result state to self-perception",
        "hypothesis": (
            "A narrow test-result sensor can distinguish code growth from verified behavioral health."
        ),
        "expected_effect": (
            "Repository observations can include a provenance-backed test-status signal without "
            "changing existing structural sensor semantics."
        ),
        "test_plan": (
            "Feed controlled passing and failing test-result fixtures and verify precise change detection."
        ),
        "falsification": (
            "Reject if test status cannot be traced to evidence, creates nondeterministic observations, "
            "or regresses existing perception."
        ),
    },
    "semantic_memory": {
        "files": ["src/agenttest/semantic.py", "tests/test_core.py"],
        "title": "Measure recency and recurrence separately in semantic retrieval",
        "hypothesis": (
            "Separating recurrence from recency can improve retrieval relevance without changing raw memory."
        ),
        "expected_effect": (
            "Retrieval reports distinct recurrence and recency contributions with source episode provenance."
        ),
        "test_plan": (
            "Construct old-frequent and new-rare concepts, verify deterministic ranking components, "
            "and preserve raw episodes."
        ),
        "falsification": (
            "Reject if ranking is not reproducible, provenance is lost, or raw evidence changes."
        ),
    },
    "world_model": {
        "files": ["src/agenttest/world.py", "tests/test_core.py"],
        "title": "Represent unresolved contradictions explicitly",
        "hypothesis": (
            "An explicit contradiction state can preserve incompatible evidence without prematurely superseding it."
        ),
        "expected_effect": (
            "Conflicting non-authoritative claims remain simultaneously inspectable until stronger evidence resolves them."
        ),
        "test_plan": (
            "Create controlled equal-strength conflicting claims and verify neither is silently erased."
        ),
        "falsification": (
            "Reject if conflict evidence is discarded, one claim wins without stronger evidence, or history is rewritten."
        ),
    },
    "memory": {
        "files": ["src/agenttest/core.py", "tests/test_core.py"],
        "title": "Measure whether remembered evidence changes later choices",
        "hypothesis": (
            "Explicit memory-use tracing can distinguish stored history from history that actually affects selection."
        ),
        "expected_effect": (
            "Selected questions or intentions record which prior evidence materially affected the choice."
        ),
        "test_plan": (
            "Compare otherwise identical states with and without one prior evidence item and verify the recorded dependency."
        ),
        "falsification": (
            "Reject if traces cite unused evidence, omit material evidence, or alter preserved behavior."
        ),
    },
    "continuity": {
        "files": ["src/agenttest/state.py", "tests/test_core.py"],
        "title": "Detect interrupted state writes explicitly",
        "hypothesis": (
            "A recoverable transaction marker can make interrupted persistence observable without corrupting last good state."
        ),
        "expected_effect": (
            "An interrupted save leaves the prior committed state readable and records recovery evidence on restart."
        ),
        "test_plan": (
            "Simulate interruption before atomic replacement and verify prior state survives unchanged."
        ),
        "falsification": (
            "Reject if interruption corrupts committed state, loses history, or cannot be detected."
        ),
    },
    "open_endedness": {
        "files": ["src/agenttest/core.py", "src/agenttest/semantic.py", "tests/test_core.py"],
        "title": "Track inquiry families across cycles",
        "hypothesis": (
            "Explicit question-family tracking can distinguish genuine branching from paraphrase churn."
        ),
        "expected_effect": (
            "Open-endedness is supported by distinct evidence-grounded inquiry families rather than raw question count."
        ),
        "test_plan": (
            "Generate paraphrases and distinct evidence-driven questions, then verify family counts distinguish them."
        ),
        "falsification": (
            "Reject if paraphrases inflate open-endedness or distinct evidence-grounded questions collapse incorrectly."
        ),
    },
    "cognition": {
        "files": ["src/agenttest/cognition.py", "tests/test_core.py"],
        "title": "Compare model-backed candidates with deterministic inquiry",
        "hypothesis": (
            "When a cognition provider is actually available, paired evaluation can determine whether "
            "model-backed candidates add falsifiable information rather than only variety."
        ),
        "expected_effect": (
            "Candidate provenance records a paired deterministic comparator and later resolution outcome."
        ),
        "test_plan": (
            "Run paired controlled candidate generation only when a provider is configured and compare "
            "falsifiability and resolution without granting tool authority."
        ),
        "falsification": (
            "Reject if model-backed candidates cannot be compared to a deterministic baseline or increase unsupported claims."
        ),
    },
}

SYSTEM_DIAGNOSTIC_TARGETS: dict[str, dict[str, Any]] = {
    "attention_control_blocked_attention_loop": {
        "dimension": "agency",
        "files": ["src/agenttest/core.py", "tests/test_core.py"],
        "title": "Redirect inquiry away from blocked experiments",
        "hypothesis": (
            "If uncertainty-driven inquiry stops reselecting questions whose active experiment "
            "is explicitly blocked, attention can move to other unresolved evidence without "
            "deleting blocked history."
        ),
        "expected_effect": (
            "A blocked experiment and its question remain preserved, but uncertainty-driven "
            "selection does not return to them until grounded evidence changes their actionability."
        ),
        "test_plan": (
            "Construct blocked and non-blocked inquiry states, verify blocked questions are skipped "
            "while eligible questions remain selectable, verify blocked history is preserved, and "
            "run the baseline-owned preservation gate."
        ),
        "falsification": (
            "Reject if blocked work is deleted, attention still loops on the blocked question, "
            "eligible inquiry is suppressed, or preserved behavior regresses."
        ),
    },
    "experiment_design_specification_churn": {
        "dimension": "learning",
        "files": ["src/agenttest/core.py", "tests/test_core.py"],
        "title": "Prevent duplicate experiment proliferation",
        "hypothesis": (
            "Reusing one canonical unresolved question/method experiment can stop "
            "specification churn without deleting historical attempts."
        ),
        "expected_effect": (
            "Exact uncontracted duplicate experiments remain preserved as history while "
            "only one canonical copy remains active and future equivalent selections reuse it."
        ),
        "test_plan": (
            "Construct repeated question/method experiments, verify history is preserved, "
            "duplicate active copies are superseded with provenance, and run preservation checks."
        ),
        "falsification": (
            "Reject if experiment history is deleted, evidence-contracted work is collapsed, "
            "duplicates remain active, or preserved behavior regresses."
        ),
    },
    "experiment_design_specification_backlog": {
        "dimension": "learning",
        "files": ["src/agenttest/core.py", "src/agenttest/drives.py", "tests/test_core.py"],
        "title": "Triage experiment specification backlog",
        "hypothesis": (
            "Explicitly tracing each missing observable, evidence source, and resolution rule "
            "can distinguish internally resolvable experiment specifications from work blocked "
            "on unavailable evidence without inventing facts."
        ),
        "expected_effect": (
            "Underspecified experiments retain their history while recording what contract fields "
            "are missing and whether current grounded evidence can supply them; blocked work does "
            "not masquerade as executable experimentation."
        ),
        "test_plan": (
            "Construct experiments with and without grounded resolvable evidence, verify missing "
            "contract fields and resolution paths are explicit, verify no evidence reference or "
            "executable contract is fabricated, and run the baseline-owned preservation gate."
        ),
        "falsification": (
            "Reject if the candidate invents observables or evidence references, hides unresolved "
            "backlog, promotes blocked work to evidence-ready, or regresses preserved behavior."
        ),
    },
}


def _active_proposal(state: dict[str, Any]) -> dict[str, Any] | None:
    unresolved = {
        "proposed",
        "reviewed_measurement_gap",
        "reviewed_needs_evidence",
        "reviewed_supported_problem",
    }
    for proposal in state.get("change_proposals", []):
        if proposal.get("status") in unresolved:
            return proposal
    return None


def _latest_experiment_design_signal(
    state: dict[str, Any],
) -> dict[str, Any] | None:
    latest = next(
        (
            diagnostic
            for diagnostic in reversed(state.get("system_diagnostics", []))
            if diagnostic.get("kind") == "experiment_design"
            and diagnostic.get("status") == "completed"
        ),
        None,
    )
    if latest is None:
        return None

    outcome = str(latest.get("outcome") or "")
    signal_by_outcome = {
        "specification_churn": "experiment_design_specification_churn",
        "specification_backlog": "experiment_design_specification_backlog",
    }
    signal = signal_by_outcome.get(outcome)
    if signal is None:
        return None

    identifier = latest.get("id")
    if not identifier:
        return None
    return {
        "dimension": SYSTEM_DIAGNOSTIC_TARGETS[signal]["dimension"],
        "baseline_metric": float(
            state.get("metrics", {}).get(
                SYSTEM_DIAGNOSTIC_TARGETS[signal]["dimension"],
                0.0,
            )
        ),
        "deficit": float(
            state.get("drives", {}).get("specification_pressure", 0.0)
        ),
        "priority": -2,
        "evidence_refs": [str(identifier)],
        "selection_signal": signal,
        "source_diagnostic_id": str(identifier),
        "diagnostic_outcome": outcome,
    }


def _latest_attention_control_signal(
    state: dict[str, Any],
) -> dict[str, Any] | None:
    latest = next(
        (
            diagnostic
            for diagnostic in reversed(state.get("system_diagnostics", []))
            if diagnostic.get("kind") == "attention_control"
            and diagnostic.get("status") == "completed"
        ),
        None,
    )
    if latest is None or latest.get("outcome") != "blocked_attention_loop":
        return None

    identifier = latest.get("id")
    if not identifier:
        return None
    signal = "attention_control_blocked_attention_loop"
    spec = SYSTEM_DIAGNOSTIC_TARGETS[signal]
    return {
        "dimension": spec["dimension"],
        "baseline_metric": float(
            state.get("metrics", {}).get(spec["dimension"], 0.0)
        ),
        "deficit": float(state.get("drives", {}).get("uncertainty", 0.0)),
        "priority": -3,
        "evidence_refs": [str(identifier)],
        "selection_signal": signal,
        "source_diagnostic_id": str(identifier),
        "diagnostic_outcome": "blocked_attention_loop",
    }


def _cognition_is_externally_blocked(state: dict[str, Any]) -> bool:
    if state.get("cognition_candidates"):
        return False
    events = state.get("cognition_events", [])
    if any(event.get("status") == "accepted" for event in events):
        return False
    # With no successful cognition evidence, a zero cognition metric is not
    # evidence that code is defective. It may simply mean no provider exists.
    return True


def _learning_evidence_debt(
    state: dict[str, Any],
    *,
    min_age_cycles: int = 3,
) -> dict[str, Any] | None:
    current_cycle = int(state.get("cycles", 0))
    prediction_reflections = [
        reflection
        for reflection in state.get("reflections", [])
        if reflection.get("source") == "prediction"
        and reflection.get("prediction_id")
    ]

    for experiment in state.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue
        if experiment.get("readiness") in {
            "awaiting_specification_or_evidence",
            "needs_specification",
        }:
            continue
        created_cycle = int(experiment.get("cycle", 0))
        age = current_cycle - created_cycle
        if age < min_age_cycles:
            continue

        later = [
            reflection
            for reflection in prediction_reflections
            if int(reflection.get("cycle", 0)) > created_cycle
        ]
        if not later:
            continue

        refs = [str(experiment["id"])]
        for reflection in later[-2:]:
            prediction_id = reflection.get("prediction_id")
            reflection_id = reflection.get("id")
            for identifier in (prediction_id, reflection_id):
                if identifier and str(identifier) not in refs:
                    refs.append(str(identifier))
        return {
            "experiment_id": str(experiment["id"]),
            "age_cycles": age,
            "evidence_refs": refs,
        }
    return None


def _open_endedness_metric_is_aligned(
    state: dict[str, Any],
    *,
    tolerance: float = 0.05,
) -> bool:
    summary = state.get("semantic_memory", {}).get("inquiry_families", {})
    if not isinstance(summary, dict):
        return False
    expected = summary.get("open_endedness")
    reported = state.get("metrics", {}).get("open_endedness")
    if not isinstance(expected, (int, float)) or not isinstance(reported, (int, float)):
        return False
    return abs(float(reported) - float(expected)) <= tolerance


def _recent_evidence_refs(
    state: dict[str, Any],
    target: str,
    limit: int = 6,
) -> list[str]:
    refs: list[str] = []

    def add(items: list[dict[str, Any]], predicate=None) -> None:
        for item in reversed(items):
            if predicate is not None and not predicate(item):
                continue
            identifier = item.get("id")
            if identifier and identifier not in refs:
                refs.append(str(identifier))
            if len(refs) >= limit:
                return

    if target in {"learning", "reflection", "self_model", "reproducibility"}:
        add(state.get("reflections", []))
        add(
            state.get("predictions", []),
            lambda item: item.get("status") in {"confirmed", "violated"},
        )
        add(state.get("experiments", []), lambda item: item.get("status") == "proposed")
    elif target in {"agency"}:
        add(state.get("intentions", []))
        add(state.get("surprises", []))
        add(state.get("experiments", []), lambda item: item.get("status") == "proposed")
    elif target in {"curiosity", "open_endedness", "memory", "semantic_memory"}:
        add(state.get("questions", []))
        add(state.get("episodes", []))
    elif target == "world_model":
        claims = state.get("world_model", {}).get("claims", [])
        add(claims)
        add(state.get("reflections", []))
    elif target == "perception":
        add(state.get("surprises", []))
        add(state.get("episodes", []), lambda item: item.get("kind") == "environment")
    elif target == "continuity":
        add(state.get("episodes", []))
        add(state.get("predictions", []))
    elif target == "cognition":
        add(state.get("cognition_candidates", []))
        add(state.get("cognition_events", []))
        add(state.get("reflections", []))

    if len(refs) < limit:
        add(state.get("reflections", []))
        add(state.get("surprises", []))
        add(state.get("episodes", []))

    return refs[:limit]


def select_change_target(state: dict[str, Any]) -> dict[str, Any] | None:
    metrics = state.get("metrics", {})
    ranked: list[tuple[float, int, str, list[str]]] = []

    attention_signal = _latest_attention_control_signal(state)
    if attention_signal is not None:
        return attention_signal

    diagnostic_signal = _latest_experiment_design_signal(state)
    if diagnostic_signal is not None:
        return diagnostic_signal

    evidence_debt = _learning_evidence_debt(state)
    if evidence_debt is not None:
        return {
            "dimension": "learning",
            "baseline_metric": float(metrics.get("learning", 0.0)),
            "deficit": float(state.get("drives", {}).get("evidence_hunger", 0.8)),
            "priority": -1,
            "evidence_refs": evidence_debt["evidence_refs"],
            "selection_signal": "stale_evidence_debt",
            "experiment_id": evidence_debt["experiment_id"],
            "age_cycles": evidence_debt["age_cycles"],
        }

    for priority, dimension in enumerate(TARGET_ORDER):
        metric = float(metrics.get(dimension, 0.0))
        if metric >= 0.999:
            continue
        if dimension == "cognition" and _cognition_is_externally_blocked(state):
            continue
        if dimension == "open_endedness" and _open_endedness_metric_is_aligned(state):
            continue

        refs = _recent_evidence_refs(state, dimension)
        if not refs:
            continue

        deficit = 1.0 - metric
        ranked.append((deficit, -priority, dimension, refs))

    if not ranked:
        return None

    deficit, neg_priority, dimension, refs = max(ranked)
    return {
        "dimension": dimension,
        "baseline_metric": float(metrics.get(dimension, 0.0)),
        "deficit": deficit,
        "priority": -neg_priority,
        "evidence_refs": refs,
    }


def propose_self_change(
    state: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
    existing = _active_proposal(state)
    if existing is not None:
        return existing, False

    selected = select_change_target(state)
    if selected is None:
        return None, False

    target = selected["dimension"]
    selection_signal = selected.get("selection_signal")
    spec = (
        SYSTEM_DIAGNOSTIC_TARGETS[selection_signal]
        if selection_signal in SYSTEM_DIAGNOSTIC_TARGETS
        else TARGETS[target]
    )
    manifest = make_change_manifest(
        state,
        title=spec["title"],
        target_dimension=target,
        files=spec["files"],
        hypothesis=spec["hypothesis"],
        expected_effect=spec["expected_effect"],
        test_plan=spec["test_plan"],
        falsification=spec["falsification"],
        rollback="Revert the candidate change and restore the previous verified baseline.",
        evidence_refs=selected["evidence_refs"],
    )
    manifest.update(
        {
            "id": f"M{len(state.get('change_proposals', [])) + 1:06d}",
            "source": "self-proposal-v1",
            "created_cycle": state.get("cycles", 0),
            "selection_signal": selection_signal,
            "source_diagnostic_id": selected.get("source_diagnostic_id"),
            "selection_rationale": (
                (
                    f"Stale evidence debt was detected in experiment "
                    f"{selected.get('experiment_id')} after "
                    f"{selected.get('age_cycles')} cycles despite later evaluated evidence; "
                    "this overrides the saturated aggregate learning metric."
                )
                if selection_signal == "stale_evidence_debt"
                else (
                    (
                        f"Protected system diagnostic {selected.get('source_diagnostic_id')} "
                        f"reported {selected.get('diagnostic_outcome')}; this direct diagnostic "
                        "signal takes priority over aggregate metric saturation."
                    )
                    if selection_signal in SYSTEM_DIAGNOSTIC_TARGETS
                    else (
                    f"{target} was the highest eligible evidence-backed deficit "
                    f"({selected['deficit']:.3f}) after excluding saturated dimensions, "
                    "process-only adaptation, externally blocked cognition, and metrics "
                    "already aligned with their verified derived measurement."
                    )
                )
            ),
        }
    )
    state.setdefault("change_proposals", []).append(manifest)
    return manifest, True
