"""Single-use copied-state capability gate for challenge-world actions.

Research only. The executor persists both the shadow world and capability
consumption atomically. It never touches live Ora state and accepts only a
command recomputed from the verified epistemic selector and persisted public
recorder summaries.
"""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.state import StateStore
from challenge_shadow_epistemic_selector import (
    POLICY,
    select_epistemic_command,
)
from challenge_shadow_recorder import (
    ChallengeShadowRecorder,
    SOURCE_DESCRIPTOR_HASH,
    SOURCE_ID,
    STATE_KEY as RECORDER_STATE_KEY,
)
from open_object_world_challenge import (
    WORLD_VERSION,
    observe_world,
    transition,
)
from open_object_world_challenge_explorer import candidate_commands, command_key

VERSION = "challenge-action-authority-v2"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _canonical_command(command: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(command, dict):
        raise ValueError("challenge command must be an object")
    allowed = {"action", "target", "direction"}
    if "action" not in command or set(command) - allowed:
        raise ValueError("challenge command fields do not match public contract")
    result = {"action": str(command["action"])}
    if command.get("target") is not None:
        result["target"] = str(command["target"])
    if command.get("direction") is not None:
        result["direction"] = str(command["direction"])
    return result


def _observation_hash(observation: dict[str, Any]) -> str:
    return _digest(observation)


def _current_source_hash() -> str:
    root = Path(__file__).resolve().parent
    names = (
        "challenge_action_authority.py",
        "challenge_shadow_recorder.py",
        "challenge_shadow_epistemic_selector.py",
        "open_object_world_challenge.py",
        "open_object_world_challenge_explorer.py",
        "native_observe_inquire_integration.py",
        "normalized_inquiry_objectives.py",
    )
    return _digest({
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in names
    })


def _seal(state: dict[str, Any]) -> dict[str, Any]:
    state["checksum"] = _digest(
        {key: value for key, value in state.items() if key != "checksum"}
    )
    return state


def _save_atomic(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            _seal(deepcopy(state)),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def _load_executor(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError("challenge action executor is not initialized")
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("version") != VERSION:
        raise ValueError("challenge action executor version mismatch")
    expected = _digest(
        {key: value for key, value in state.items() if key != "checksum"}
    )
    if state.get("checksum") != expected:
        raise ValueError("challenge action executor checksum mismatch")
    if state.get("source_id") != SOURCE_ID:
        raise ValueError("challenge action executor source mismatch")
    if state.get("source_descriptor_hash") != SOURCE_DESCRIPTOR_HASH:
        raise ValueError("challenge source descriptor mismatch")
    if state.get("world_version") != WORLD_VERSION:
        raise ValueError("challenge world version mismatch")
    if type(state.get("max_actions")) is not int or state["max_actions"] < 1:
        raise ValueError("invalid challenge action budget")
    if type(state.get("actions_consumed")) is not int or not (
        0 <= state["actions_consumed"] <= state["max_actions"]
    ):
        raise ValueError("invalid consumed action count")
    if not isinstance(state.get("capabilities"), list):
        raise ValueError("invalid challenge capability ledger")
    # Public observation validates world structure as a side effect.
    observe_world(state["world"])
    return state


def _find_experiment(
    ora_state: dict[str, Any],
    experiment_id: str,
) -> dict[str, Any]:
    experiment = next(
        (
            row
            for row in ora_state.get("experiments", [])
            if isinstance(row, dict) and str(row.get("id")) == str(experiment_id)
        ),
        None,
    )
    if experiment is None:
        raise ValueError("native experiment was not found in copied Ora state")
    if experiment.get("status") != "proposed":
        raise ValueError("native experiment is not proposed")
    if experiment.get("readiness") != "awaiting_native_evidence":
        raise ValueError("native experiment is not awaiting native evidence")
    native = experiment.get("native_inquiry")
    if not isinstance(native, dict):
        raise ValueError("experiment is not a native inquiry")
    relation = native.get("relation")
    if not isinstance(relation, dict):
        raise ValueError("native inquiry relation is unavailable")
    if relation.get("kind") not in {
        "same_next_observation",
        "changes_next_observation",
    }:
        raise ValueError("bounded challenge action requires temporal native inquiry")
    return experiment


class ChallengeActionExecutor:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @classmethod
    def create(
        cls,
        path: Path | str,
        *,
        world: dict[str, Any],
        max_actions: int,
    ) -> "ChallengeActionExecutor":
        target = Path(path)
        if target.exists():
            raise ValueError("challenge action executor already exists")
        if type(max_actions) is not int or max_actions < 1:
            raise ValueError("max_actions must be a positive integer")
        observation = observe_world(world)
        state = {
            "version": VERSION,
            "source_id": SOURCE_ID,
            "source_descriptor_hash": SOURCE_DESCRIPTOR_HASH,
            "world_version": WORLD_VERSION,
            "world": deepcopy(world),
            "max_actions": max_actions,
            "actions_consumed": 0,
            "next_capability_index": 1,
            "capabilities": [],
            "created_observation_id": observation["observation_id"],
        }
        _save_atomic(target, state)
        return cls(target)

    def load(self) -> dict[str, Any]:
        return deepcopy(_load_executor(self.path))

    def observation(self) -> dict[str, Any]:
        return observe_world(_load_executor(self.path)["world"])

    def issue(
        self,
        *,
        ora_store: StateStore,
        recorder: ChallengeShadowRecorder,
        experiment_id: str,
    ) -> dict[str, Any]:
        executor = _load_executor(self.path)
        if executor["actions_consumed"] >= executor["max_actions"]:
            raise RuntimeError("challenge action budget is exhausted")
        if any(row.get("status") == "issued" for row in executor["capabilities"]):
            raise RuntimeError("an unconsumed challenge capability already exists")
        if any(
            isinstance(row.get("token"), dict)
            and str(row["token"].get("experiment_id")) == str(experiment_id)
            for row in executor["capabilities"]
        ):
            raise RuntimeError(
                "native experiment already received a challenge capability"
            )

        ora_state = ora_store.load()
        if not ora_store.path.is_file():
            raise ValueError("copied Ora state is unavailable")
        experiment = _find_experiment(ora_state, experiment_id)
        native = experiment["native_inquiry"]
        relation = native["relation"]
        feature = str(relation["feature"])
        relation_kind = str(relation["kind"])

        current_observation = observe_world(executor["world"])
        recorder_observation = recorder.latest_observation()
        if recorder_observation != current_observation:
            raise ValueError(
                "executor world is not aligned to the persisted recorder observation"
            )

        recorder_state = recorder.store.load()
        cursor = recorder_state.get(RECORDER_STATE_KEY)
        if not isinstance(cursor, dict):
            raise ValueError("challenge recorder checkpoint is unavailable")
        if cursor.get("source_id") != SOURCE_ID:
            raise ValueError("challenge recorder source mismatch")
        if cursor.get("source_descriptor_hash") != SOURCE_DESCRIPTOR_HASH:
            raise ValueError("challenge recorder descriptor mismatch")

        associations = recorder.action_associations()
        selection = select_epistemic_command(
            current_observation,
            feature=feature,
            relation=relation_kind,
            associations=associations,
        )
        if selection.get("policy") != POLICY:
            raise ValueError("unexpected epistemic selector policy")
        command = _canonical_command(selection["command"])
        public_commands = [
            _canonical_command(row)
            for row in candidate_commands(current_observation)
        ]
        if command not in public_commands:
            raise ValueError("selected command is not publicly available")

        question_id = str(experiment.get("question_id") or "")
        candidate_id = str(native.get("candidate_id") or "")
        if not question_id or not candidate_id:
            raise ValueError("native inquiry identity is incomplete")

        index = int(executor["next_capability_index"])
        capability_id = f"CAC{index:06d}"
        token_core = {
            "version": VERSION,
            "id": capability_id,
            "source_id": SOURCE_ID,
            "source_descriptor_hash": SOURCE_DESCRIPTOR_HASH,
            "world_version": WORLD_VERSION,
            "experiment_id": str(experiment_id),
            "question_id": question_id,
            "native_candidate_id": candidate_id,
            "ora_state_hash": _digest(ora_state),
            "source_content_hash": _current_source_hash(),
            "ora_cycle": ora_state["cycles"],
            "experiment_hash": _digest(experiment),
            "ora_store_path": str(ora_store.path.resolve()),
            "recorder_store_path": str(recorder.store.path.resolve()),
            "feature": feature,
            "relation": relation_kind,
            "observation_id": current_observation["observation_id"],
            "observation_cycle": int(current_observation["cycle"]),
            "observation_hash": _observation_hash(current_observation),
            "recorder_chain_hash": str(cursor.get("chain") or ""),
            "recorder_checkpoint_hash": _digest(cursor),
            "association_hash": _digest(associations),
            "world_hash": _digest(executor["world"]),
            "max_actions": executor["max_actions"],
            "selector_policy": POLICY,
            "selection_hash": _digest(selection),
            "command": command,
            "command_hash": _digest(command),
            "budget_ordinal": int(executor["actions_consumed"]) + 1,
        }
        token = {**token_core, "token_hash": _digest(token_core)}
        executor["capabilities"].append(
            {
                "id": capability_id,
                "status": "issued",
                "token": deepcopy(token),
                "issued_at_observation": current_observation["observation_id"],
            }
        )
        executor["next_capability_index"] = index + 1
        _save_atomic(self.path, executor)
        return {
            "token": deepcopy(token),
            "selection": deepcopy(selection),
            "association_count": len(associations),
        }

    def execute(
        self,
        token: dict[str, Any],
        *,
        ora_store: StateStore,
        recorder: ChallengeShadowRecorder,
    ) -> dict[str, Any]:
        executor = _load_executor(self.path)
        if not isinstance(token, dict):
            raise ValueError("challenge capability token must be an object")

        if token.get("source_id") != SOURCE_ID:
            raise ValueError("challenge capability source mismatch")
        if token.get("source_descriptor_hash") != SOURCE_DESCRIPTOR_HASH:
            raise ValueError("challenge capability descriptor mismatch")
        if token.get("world_version") != WORLD_VERSION:
            raise ValueError("challenge capability world mismatch")

        capability_id = str(token.get("id") or "")
        record = next(
            (
                row
                for row in executor["capabilities"]
                if str(row.get("id")) == capability_id
            ),
            None,
        )
        if record is None:
            raise ValueError("challenge capability is unknown")
        if record.get("status") != "issued":
            raise RuntimeError("challenge capability is already consumed")
        if token != record.get("token"):
            raise ValueError("challenge capability token was modified")
        token_core = {key: value for key, value in token.items() if key != "token_hash"}
        if token.get("token_hash") != _digest(token_core):
            raise ValueError("challenge capability token checksum mismatch")
        if executor["actions_consumed"] >= executor["max_actions"]:
            raise RuntimeError("challenge action budget is exhausted")
        if token.get("budget_ordinal") != executor["actions_consumed"] + 1:
            raise ValueError("challenge capability budget ordinal is stale")
        if token.get("max_actions") != executor["max_actions"]:
            raise ValueError("challenge capability action budget is stale")
        if token.get("world_hash") != _digest(executor["world"]):
            raise ValueError("challenge capability world is stale")
        if token.get("source_content_hash") != _current_source_hash():
            raise ValueError("challenge capability source content is stale")

        # Reload the explicit copied stores after restart. A capability reviews
        # one exact state, not just inquiry IDs or issuance-time metadata.
        if not ora_store.path.is_file() or not recorder.store.path.is_file():
            raise ValueError("reviewed copied state is unavailable")
        if token.get("ora_store_path") != str(ora_store.path.resolve()):
            raise ValueError("challenge capability copied Ora store mismatch")
        if token.get("recorder_store_path") != str(recorder.store.path.resolve()):
            raise ValueError("challenge capability recorder store mismatch")
        ora_state = ora_store.load()
        experiment = _find_experiment(ora_state, token["experiment_id"])
        if (
            token.get("ora_state_hash") != _digest(ora_state)
            or token.get("ora_cycle") != ora_state["cycles"]
            or token.get("experiment_hash") != _digest(experiment)
        ):
            raise ValueError("challenge capability copied Ora inquiry is stale")

        observation = observe_world(executor["world"])
        if token.get("observation_id") != observation["observation_id"]:
            raise ValueError("challenge capability observation is stale")
        if token.get("observation_cycle") != observation["cycle"]:
            raise ValueError("challenge capability cycle is stale")
        if token.get("observation_hash") != _observation_hash(observation):
            raise ValueError("challenge capability observation hash is stale")

        # Recorder methods validate the persisted checkpoint checksum. Check its
        # complete contents as well as recomputing the unchanged selector.
        if recorder.latest_observation() != observation:
            raise ValueError("challenge capability recorder observation is stale")
        cursor = recorder.store.load().get(RECORDER_STATE_KEY)
        if not isinstance(cursor, dict):
            raise ValueError("challenge recorder checkpoint is unavailable")
        if (
            cursor.get("source_id") != SOURCE_ID
            or cursor.get("source_descriptor_hash") != SOURCE_DESCRIPTOR_HASH
            or token.get("recorder_chain_hash") != str(cursor.get("chain") or "")
            or token.get("recorder_checkpoint_hash") != _digest(cursor)
        ):
            raise ValueError("challenge capability recorder checkpoint is stale")
        associations = recorder.action_associations()
        relation = experiment["native_inquiry"]["relation"]
        selection = select_epistemic_command(
            observation,
            feature=str(relation["feature"]),
            relation=str(relation["kind"]),
            associations=associations,
        )
        if (
            selection.get("policy") != POLICY
            or token.get("selector_policy") != POLICY
            or token.get("association_hash") != _digest(associations)
            or token.get("selection_hash") != _digest(selection)
            or token.get("command") != _canonical_command(selection["command"])
        ):
            raise ValueError("challenge capability selector or command is stale")

        command = _canonical_command(token["command"])
        if token.get("command_hash") != _digest(command):
            raise ValueError("challenge capability command checksum mismatch")
        available = [
            _canonical_command(row)
            for row in candidate_commands(observation)
        ]
        if command not in available:
            raise ValueError("challenge capability command is no longer public")

        next_cycle = int(observation["cycle"]) + 1
        next_world, receipt = transition(
            executor["world"],
            command,
            cycle=next_cycle,
        )
        next_observation = observe_world(next_world)

        # World transition and capability consumption share one atomic file save.
        executor["world"] = deepcopy(next_world)
        executor["actions_consumed"] += 1
        record["status"] = "consumed"
        record["consumed_cycle"] = next_cycle
        record["receipt_hash"] = _digest(receipt)
        record["result_observation_id"] = next_observation["observation_id"]
        record["result_observation_hash"] = _observation_hash(next_observation)
        _save_atomic(self.path, executor)

        return {
            "capability_id": capability_id,
            "command": command,
            "receipt": deepcopy(receipt),
            "observation": deepcopy(next_observation),
            "actions_consumed": executor["actions_consumed"],
            "remaining_budget": executor["max_actions"] - executor["actions_consumed"],
        }


def _unsafe_replace_world_for_adversarial_test(
    path: Path | str,
    world: dict[str, Any],
) -> None:
    """Research-test helper: simulate an out-of-band world advance.

    This is deliberately private and used only by adversarial tests/studies.
    Production/live code never calls it.
    """
    target = Path(path)
    state = _load_executor(target)
    observe_world(world)
    state["world"] = deepcopy(world)
    _save_atomic(target, state)
