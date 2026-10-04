from __future__ import annotations

from copy import deepcopy
from typing import Any

NATIVE_ACTIVATION_POLICY_VERSION = "native-activation-policy-v1"
DEFAULT_NATIVE_ACTIVATION_POLICY = {
    "version": NATIVE_ACTIVATION_POLICY_VERSION,
    "enabled": False,
    "mode": "off",
    "allowed_relations": [],
    "objective": None,
    "allow_persist_evidence": False,
    "allow_persist_inquiry": False,
    "allow_environment_actions": False,
    "allow_action_lab": False,
    "allow_planning_lab": False,
}

_ALLOWED_MODES = {"off", "observe_and_inquire"}
_ALLOWED_TEMPORAL_RELATIONS = {
    "same_next_observation",
    "changes_next_observation",
}


def validate_native_activation_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    if policy is None:
        return deepcopy(DEFAULT_NATIVE_ACTIVATION_POLICY)
    if not isinstance(policy, dict) or set(policy) != set(DEFAULT_NATIVE_ACTIVATION_POLICY):
        raise ValueError("native activation policy fields do not match contract")
    if policy["version"] != NATIVE_ACTIVATION_POLICY_VERSION:
        raise ValueError("unsupported native activation policy version")

    enabled = policy["enabled"]
    if type(enabled) is not bool:
        raise ValueError("native activation enabled must be boolean")
    mode = policy["mode"]
    if mode not in _ALLOWED_MODES:
        raise ValueError("unsupported native activation mode")

    relations = policy["allowed_relations"]
    if (
        not isinstance(relations, list)
        or len(relations) != len(set(relations))
        or any(item not in _ALLOWED_TEMPORAL_RELATIONS for item in relations)
    ):
        raise ValueError("native activation allows temporal relations only")

    objective = policy["objective"]
    persist_evidence = policy["allow_persist_evidence"]
    persist_inquiry = policy["allow_persist_inquiry"]
    environment_actions = policy["allow_environment_actions"]
    action_lab = policy["allow_action_lab"]
    planning_lab = policy["allow_planning_lab"]
    for name, value in (
        ("allow_persist_evidence", persist_evidence),
        ("allow_persist_inquiry", persist_inquiry),
        ("allow_environment_actions", environment_actions),
        ("allow_action_lab", action_lab),
        ("allow_planning_lab", planning_lab),
    ):
        if type(value) is not bool:
            raise ValueError(f"{name} must be boolean")

    if environment_actions or action_lab or planning_lab:
        raise ValueError("native activation v1 cannot grant action authority")

    if not enabled:
        if (
            mode != "off"
            or relations
            or objective is not None
            or persist_evidence
            or persist_inquiry
        ):
            raise ValueError("disabled native activation policy must be fully off")
    else:
        if mode != "observe_and_inquire":
            raise ValueError("enabled native activation v1 is observe_and_inquire only")
        if not relations:
            raise ValueError("enabled native activation requires temporal relation allowlist")
        if objective != "information_gain":
            raise ValueError("native activation v1 requires frozen information_gain objective")
        if not persist_evidence or not persist_inquiry:
            raise ValueError(
                "observe_and_inquire activation requires explicit evidence and inquiry persistence"
            )

    return {
        "version": NATIVE_ACTIVATION_POLICY_VERSION,
        "enabled": enabled,
        "mode": mode,
        "allowed_relations": list(relations),
        "objective": objective,
        "allow_persist_evidence": persist_evidence,
        "allow_persist_inquiry": persist_inquiry,
        "allow_environment_actions": False,
        "allow_action_lab": False,
        "allow_planning_lab": False,
    }


def temporal_activation_policy() -> dict[str, Any]:
    """Return the explicit opt-in policy used only by isolated activation tests."""
    return {
        "version": NATIVE_ACTIVATION_POLICY_VERSION,
        "enabled": True,
        "mode": "observe_and_inquire",
        "allowed_relations": [
            "same_next_observation",
            "changes_next_observation",
        ],
        "objective": "information_gain",
        "allow_persist_evidence": True,
        "allow_persist_inquiry": True,
        "allow_environment_actions": False,
        "allow_action_lab": False,
        "allow_planning_lab": False,
    }
