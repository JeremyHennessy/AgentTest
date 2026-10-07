"""Inactive, authored ownership checks for one existing public take command.

The copied Ora input supplies the explicit request; this module neither chooses
an object nor claims natural inquiry or learning. Authority-only snapshots stay
outside the public selection view. Restart checks never invoke the actuator.
"""
from copy import deepcopy

from open_object_world_challenge import observe_world
from open_object_world_challenge_explorer import candidate_commands
from .contracts import Conflict, bounded, canonical, digest, exact, strict_receipt, validate_world

BACKEND = "authored_object_ownership_v1"
RULE = "authored-object-outcome-record-v1"
INPUT_KEY = "owned_object_selection"
SNAPSHOT_CAP = 8192


def configuration():
    return dict(version=BACKEND, provenance="authored_ownership_check",
                command_scope="take", learning_evidence="not_established")


def request(ora):
    value = ora.get(INPUT_KEY)
    exact(value, "provenance command source_observation_hash", "authored object selection")
    if value["provenance"] != "authored_ownership_check":
        raise Conflict("object slice requires explicit authored ownership provenance")
    exact(value["command"], "action target", "public take command")
    if value["command"]["action"] != "take" or not isinstance(value["command"]["target"], str):
        raise Conflict("object slice supports only a supplied public take command")
    source_hash = value["source_observation_hash"]
    if not isinstance(source_hash, str) or len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
        raise Conflict("object selection requires an exact public observation hash")
    bounded(value, 4096, "authored object selection")
    return deepcopy(value)


def select(ora, observation):
    supplied = request(ora)
    command = supplied["command"]
    reason = None
    if supplied["source_observation_hash"] != digest(observation):
        reason = "stale_public_context"
    elif command not in candidate_commands(observation):
        reason = "command_not_publicly_available"
    return dict(schema=BACKEND, provenance="authored_ownership_check",
                request_hash=digest(supplied), source_observation_hash=digest(observation),
                selected_action=None if reason else command["action"],
                command=None if reason else deepcopy(command), reason=reason)


def snapshot(world):
    result = {key: deepcopy(value) for key, value in world.items() if key != "history"}
    bounded(result, SNAPSHOT_CAP, "object world snapshot")
    return result


def restore(before, outcome):
    """Check the exact permitted take mutation, receipt and durable snapshot."""
    command = outcome["command"]
    exact(command, "action target", "owned public take command")
    observation = observe_world(before)
    if command["action"] != "take" or command not in candidate_commands(observation):
        raise Conflict("owned take command unavailable in saved public context")
    receipt = outcome["receipt"]
    strict_receipt(receipt, outcome["before_observation"], outcome["after_observation"])
    if (receipt["action"] != command["action"] or receipt["target"] != command["target"]
            or receipt["direction"] is not None):
        raise Conflict("object receipt differs from owned command")
    bounded(outcome["world_snapshot"], SNAPSHOT_CAP, "object world snapshot")
    expected = deepcopy(before)
    target = command["target"]
    entity = expected["entities"][target]
    # Eligibility is public. These immutable private properties are consulted
    # only by authority's outcome validator, never by selection.
    success = entity.get("_kind") == "object" and bool(entity.get("_carryable"))
    effects = ["inventory_changed"] if success else ["target_unavailable"]
    if success:
        entity["position"] = None
        expected["inventory"].append(target)
    expected["cycle"] += 1
    expected["history"].append(deepcopy(receipt))
    after = observe_world(expected)
    states = {row["id"]: row["observable_state"] for row in after["visible_entities"]
              if "observable_state" in row}
    prior_states = {row["id"]: row["observable_state"] for row in observation["visible_entities"]
                    if "observable_state" in row}
    if any(prior_states[key] != value for key, value in states.items() if key in prior_states):
        effects.append("public_state_changed")
    expected_receipt = dict(id=f"OWC-A{expected['cycle']:06d}", cycle=expected["cycle"],
        action="take", target=target, direction=None, before=before["position"],
        after=before["position"], success=success, blocked=False,
        observed_effects=effects, visible_entity_states=states)
    if canonical(receipt) != canonical(expected_receipt):
        raise Conflict("take receipt does not match permitted object outcome")
    if canonical(outcome["world_snapshot"]) != canonical(snapshot(expected)):
        raise Conflict("object snapshot changes state outside owned take outcome")
    if canonical(outcome["before_observation"]) != canonical(observation) or canonical(outcome["after_observation"]) != canonical(after):
        raise Conflict("object outcome public observations differ from saved world")
    validate_world(expected)
    return expected
