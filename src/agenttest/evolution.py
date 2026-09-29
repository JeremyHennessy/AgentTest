from __future__ import annotations

from typing import Any

from .state import DIMENSIONS, utc_now

_TEMPLATES = {
    "continuity": (
        "Test recovery from an interrupted run.",
        "Interrupt a cycle before persistence, restart, and verify no committed event is lost.",
    ),
    "memory": (
        "Test whether prior experience changes a later choice.",
        "Present two otherwise equal choices where only one has supporting prior evidence.",
    ),
    "perception": (
        "Test whether self-observation detects a real environmental change.",
        "Change one measured repository property and verify the next observation records exactly that surprise.",
    ),
    "self_model": (
        "Test calibration of a claimed capability.",
        "Make a one-step prediction before observation, then compare expected and observed fields.",
    ),
    "curiosity": (
        "Test internally generated novelty.",
        "Run without a user question and measure whether a non-duplicate testable question appears.",
    ),
    "agency": (
        "Test endogenous choice among competing pressures.",
        "Record current drives and verify the selected intention follows the reproducible priority rule.",
    ),
    "learning": (
        "Test behavioral update after prediction error.",
        "Violate one measured prediction and verify the next intention prioritizes explaining that change.",
    ),
    "adaptation": (
        "Test a reversible self-change.",
        "Propose one code or policy change on a branch and compare it to the current baseline.",
    ),
    "reflection": (
        "Test prediction/outcome comparison.",
        "Make a prediction before an observation and require a post-observation error analysis.",
    ),
    "open_endedness": (
        "Test whether inquiry branches rather than loops.",
        "Measure whether unresolved observations create genuinely new question families.",
    ),
    "reproducibility": (
        "Test replayability.",
        "Replay a recorded cycle from the same inputs and compare the structured outputs.",
    ),
}


def propose_growth_experiment(state: dict[str, Any]) -> dict[str, Any]:
    metrics = state.get("metrics", {})
    target = min(DIMENSIONS, key=lambda name: metrics.get(name, 0.0))
    title, method = _TEMPLATES[target]
    return {
        "proposal_version": 1,
        "created_at": utc_now(),
        "target_dimension": target,
        "baseline": metrics.get(target, 0.0),
        "title": title,
        "hypothesis": f"A focused reversible test can produce evidence about {target}.",
        "method": method,
        "measurement": (
            "Compare the target dimension and its raw evidence before and after the test. "
            "Do not treat code changes alone as improvement."
        ),
        "falsification": (
            "Reject the change if the target evidence does not improve, cannot be reproduced, "
            "or causes a verified regression in another dimension."
        ),
        "status": "proposed",
    }
