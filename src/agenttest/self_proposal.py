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
        "files": ["src/agenttest/core.py", "tests/test_core.py"],
        "title": "Close measurable experiment loops from later evidence",
        "hypothesis": (
            "Linking eligible pending experiments to later measured outcomes can increase "
            "evidence-backed learning without manufacturing experiment results."
        ),
        "expected_effect": (
            "At least one eligible experiment can transition from proposed to completed "
            "only when a matching later observation or prediction result supplies evidence."
        ),
        "test_plan": (
            "Add a controlled experiment whose predicted observation is later confirmed or "
            "violated; verify only the matching experiment closes, then run the baseline-owned "
            "behavioral preservation gate."
        ),
        "falsification": (
            "Reject if no eligible experiment closes after matching evidence, if an unrelated "
            "experiment closes, if evidence provenance is missing, or if any preserved behavior regresses."
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


def _active_proposal(state: dict[str, Any]) -> dict[str, Any] | None:
    for proposal in state.get("change_proposals", []):
        if proposal.get("status") == "proposed":
            return proposal
    return None


def _cognition_is_externally_blocked(state: dict[str, Any]) -> bool:
    if state.get("cognition_candidates"):
        return False
    events = state.get("cognition_events", [])
    if any(event.get("status") == "accepted" for event in events):
        return False
    # With no successful cognition evidence, a zero cognition metric is not
    # evidence that code is defective. It may simply mean no provider exists.
    return True


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

    for priority, dimension in enumerate(TARGET_ORDER):
        metric = float(metrics.get(dimension, 0.0))
        if metric >= 0.999:
            continue
        if dimension == "cognition" and _cognition_is_externally_blocked(state):
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
    spec = TARGETS[target]
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
            "selection_rationale": (
                f"{target} was the highest eligible evidence-backed deficit "
                f"({selected['deficit']:.3f}) after excluding saturated dimensions, "
                "process-only adaptation, and externally blocked cognition."
            ),
        }
    )
    state.setdefault("change_proposals", []).append(manifest)
    return manifest, True
