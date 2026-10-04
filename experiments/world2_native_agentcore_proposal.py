from __future__ import annotations

from copy import deepcopy
from typing import Any

from world2_native_endogenous import choose_native_intention

PROPOSAL_VERSION = "world2-native-agentcore-proposal-v0"


def propose_native_question_candidate(state: dict[str, Any]) -> dict[str, Any] | None:
    """Translate native endogenous focus into the same grounded candidate shape Core consumes."""
    intention = choose_native_intention(state)
    target = intention.get("target")
    if not isinstance(target, dict):
        return None

    kind = str(target.get("prediction_kind") or "")
    position = target.get("target_position")
    object_id = target.get("object_id")
    evidence_refs = list(target.get("evidence_refs", []))

    if kind == "object_visible_at_position" and object_id and position is not None:
        subject = f"whether object {object_id} persists when position {position} is observed again"
        experiment = f"Return to observed position {position} and record whether object {object_id} is visible."
        falsification = f"A valid observation at {position} where object {object_id} is absent counts against persistence."
    elif kind == "resource_value_at_position" and position is not None:
        subject = f"whether the measured resource at position {position} is stable across observations"
        experiment = f"Observe position {position} again and compare the measured local resource with the prior value."
        falsification = f"A later measured resource value at {position} that differs from the prior value counts against stability."
    elif kind == "slow_signal_value":
        subject = "whether the broadcast slow signal is stable across observations"
        experiment = "Take another observation and compare the measured broadcast slow signal with its prior value."
        falsification = "A later measured broadcast slow-signal value that differs from the prior value counts against stability."
    else:
        return None

    question = f"What observation would most directly test {subject}?"
    hypothesis = f"The native observation represented by this inquiry will remain stable when it is legitimately measured again."
    return {
        "version": PROPOSAL_VERSION,
        "question": question,
        "hypothesis": hypothesis,
        "experiment": experiment,
        "falsification": falsification,
        "predicted_observation": None,
        "native_intention": deepcopy(intention),
        "evidence_refs": evidence_refs,
        "grounded": True,
        "source": "world2_native_endogenous",
    }
