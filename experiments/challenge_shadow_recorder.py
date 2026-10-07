"""Durable public-stream adapter for the reviewed challenge world.

Research only. This module consumes public observations/receipts and persists
only aggregate evidence plus the latest public observation in a copied
StateStore. It does not execute AgentCore cycles or grant environment authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.state import StateStore
from native_observe_inquire_integration import (
    PUBLICATION_VERSION,
    SOURCE_MANIFEST_VERSION,
    source_manifest_hash,
)
from normalized_inquiry_objectives import rank_normalized_candidates

WORLD_VERSION = "open-object-world-challenge-v1"
RECORDER_VERSION = "challenge-public-stream-recorder-v1"
STATE_KEY = "challenge_shadow_recorder_v1"
ACTIONS = {"north","east","south","west","inspect","interact","take","drop","push"}
LABEL = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")

REVIEWED_SOURCE = {
    "version": "reviewed-shadow-source-v1",
    "commit": "80c0f63163d08aa2efc04ca60e1c41032ba2e839",
    "world_blob": "49683553596400e8c7b49b5ed5fdec5f937b7a22",
    "explorer_blob": "db5415b17077fdad65bf1671700f79979ff92be1",
    "objective_blob": "e25fbd9f75ec642971c372a08a476d4fe6bd1641",
    "integration_blob": "57452a114e972408aafd1f97a0c4970298ec5bbe",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


SOURCE_DESCRIPTOR_HASH = _digest(REVIEWED_SOURCE)
SOURCE_ID = f"research.challenge-v1.{SOURCE_DESCRIPTOR_HASH[:16]}"


def reviewed_source_descriptor() -> dict[str, Any]:
    return deepcopy(REVIEWED_SOURCE)


def source_manifest() -> dict[str, Any]:
    return {
        "version": SOURCE_MANIFEST_VERSION,
        "source_id": SOURCE_ID,
        "source_kind": "public_observation_stream",
        "observation_schema": WORLD_VERSION,
        "recorder_version": RECORDER_VERSION,
        "provenance_mode": "hash_chained_unsigned",
        "cumulative_publications": True,
        "max_recent_observation_refs": 64,
        "signed_source": False,
        "allow_environment_actions": False,
    }


def _label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not LABEL.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def _position(value: Any) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int or item < -2 or item > 2 for item in value)
    ):
        raise ValueError("invalid public position")
    return [int(value[0]), int(value[1])]


def validate_observation(value: Any) -> dict[str, Any]:
    required = {
        "world_version","observation_id","cycle","position",
        "inventory_ids","visible_entities",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("observation fields do not match public contract")
    if value["world_version"] != WORLD_VERSION:
        raise ValueError("unexpected challenge world version")
    cycle = value["cycle"]
    if type(cycle) is not int or cycle < 0:
        raise ValueError("invalid observation cycle")
    if value["observation_id"] != f"owc-{cycle:06d}":
        raise ValueError("observation ID/cycle mismatch")
    position = _position(value["position"])
    inventory = value["inventory_ids"]
    if (
        not isinstance(inventory, list)
        or any(not isinstance(item, str) for item in inventory)
        or len(inventory) != len(set(inventory))
    ):
        raise ValueError("invalid public inventory")
    for item in inventory:
        _label(item, "inventory ID")
    visible = value["visible_entities"]
    if not isinstance(visible, list):
        raise ValueError("visible_entities must be a list")
    seen = set()
    for entity in visible:
        if not isinstance(entity, dict):
            raise ValueError("invalid visible entity")
        allowed = {"id","position","appearance","observable_state"}
        required_entity = {"id","position","appearance"}
        if not required_entity <= set(entity) or set(entity) - allowed:
            raise ValueError("visible entity fields violate public contract")
        entity_id = _label(entity["id"], "entity ID")
        if entity_id in seen or entity_id in inventory:
            raise ValueError("duplicate public entity identity")
        seen.add(entity_id)
        entity_position = _position(entity["position"])
        if sum(abs(a-b) for a,b in zip(position, entity_position)) > 1:
            raise ValueError("nonlocal entity leaked into public observation")
        if not isinstance(entity["appearance"], str):
            raise ValueError("appearance must be public text")
        if "observable_state" in entity and not isinstance(entity["observable_state"], str):
            raise ValueError("observable_state must be public text")
    return deepcopy(value)


def validate_receipt(value: Any, before: dict, after: dict) -> dict[str, Any]:
    required = {
        "id","cycle","action","target","direction","before","after",
        "success","blocked","observed_effects","visible_entity_states",
    }
    allowed = required | {"inspection"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - allowed:
        raise ValueError("receipt fields violate public contract")
    cycle = value["cycle"]
    if type(cycle) is not int or cycle != after["cycle"]:
        raise ValueError("receipt cycle mismatch")
    if value["id"] != f"OWC-A{cycle:06d}":
        raise ValueError("receipt ID/cycle mismatch")
    if value["action"] not in ACTIONS:
        raise ValueError("unsupported public action")
    if value["before"] != before["position"] or value["after"] != after["position"]:
        raise ValueError("receipt position does not align with observations")
    if any(type(value[field]) is not bool for field in ("success","blocked")):
        raise ValueError("invalid receipt flags")
    for field in ("target","direction"):
        if value[field] is not None:
            _label(value[field], field)
    effects = value["observed_effects"]
    if not isinstance(effects, list) or any(not isinstance(item, str) for item in effects):
        raise ValueError("invalid public effects")
    states = value["visible_entity_states"]
    if (
        not isinstance(states, dict)
        or any(not isinstance(k,str) or not isinstance(v,str) for k,v in states.items())
    ):
        raise ValueError("invalid visible state map")
    if "inspection" in value:
        inspection = value["inspection"]
        if not isinstance(inspection, dict):
            raise ValueError("invalid inspection")
        allowed_inspection = {"id","position","appearance","observable_state"}
        required_inspection = {"id","position","appearance"}
        if not required_inspection <= set(inspection) or set(inspection) - allowed_inspection:
            raise ValueError("inspection fields violate public contract")
        _label(inspection["id"], "inspection ID")
        _position(inspection["position"])
        if not isinstance(inspection["appearance"], str):
            raise ValueError("invalid inspection appearance")
        if (
            "observable_state" in inspection
            and not isinstance(inspection["observable_state"], str)
        ):
            raise ValueError("invalid inspection state")
    return deepcopy(value)


def public_features(observation: dict[str, Any]) -> dict[str, Any]:
    checked = validate_observation(observation)
    features: dict[str, Any] = {
        "position": tuple(checked["position"]),
        "inventory_ids": tuple(sorted(checked["inventory_ids"])),
        "visible_ids": tuple(
            sorted(str(item["id"]) for item in checked["visible_entities"])
        ),
    }
    for item in checked["visible_entities"]:
        entity_id = str(item["id"])
        features[f"entity.{entity_id}.position"] = tuple(item["position"])
        if item.get("observable_state") is not None:
            features[f"entity.{entity_id}.state"] = str(item["observable_state"])
    return features


def action_label(receipt: dict[str, Any]) -> str:
    parts = [str(receipt.get("action") or "")]
    if receipt.get("target"):
        parts.append(str(receipt["target"]))
    if receipt.get("direction"):
        parts.append(str(receipt["direction"]))
    return ":".join(parts)


def _seal(cursor: dict[str, Any]) -> dict[str, Any]:
    cursor["checksum"] = _digest(
        {key:value for key,value in cursor.items() if key != "checksum"}
    )
    return cursor


class ChallengeShadowRecorder:
    def __init__(
        self,
        store: StateStore,
        *,
        enabled: bool = False,
        source_id: str = SOURCE_ID,
    ) -> None:
        if enabled is not True:
            raise RuntimeError("challenge shadow recorder is disabled by default")
        if source_id != SOURCE_ID:
            raise ValueError("challenge source identity does not match reviewed source")
        self.store = store
        self.source_id = source_id
        root = Path(__file__).resolve().parents[1]
        if store.path.resolve().is_relative_to(root / "state"):
            raise ValueError("shadow recorder refuses repository live-state directory")
        if not store.path.exists():
            raise ValueError("explicit copied StateStore must already exist")

    def _load(self) -> tuple[dict[str, Any], dict[str, Any] | None]:
        state = self.store.load()
        cursor = state.get(STATE_KEY)
        if cursor is not None:
            if not isinstance(cursor, dict):
                raise ValueError("invalid recorder checkpoint")
            if cursor.get("version") != RECORDER_VERSION:
                raise ValueError("recorder version mismatch")
            if cursor.get("source_id") != self.source_id:
                raise ValueError("recorder source mismatch")
            expected = _digest(
                {key:value for key,value in cursor.items() if key != "checksum"}
            )
            if cursor.get("checksum") != expected:
                raise ValueError("recorder checkpoint checksum mismatch")
        return state, cursor

    def ingest(
        self,
        observation: dict[str, Any],
        receipt: dict[str, Any] | None = None,
    ) -> bool:
        current = validate_observation(observation)
        state, cursor = self._load()
        delivery = _digest(
            {
                "source_id": self.source_id,
                "observation": current,
                "receipt": receipt,
            }
        )
        if cursor is None:
            if current["cycle"] != 0 or receipt is not None:
                raise ValueError("new challenge stream must start at cycle zero")
            cursor = {
                "version": RECORDER_VERSION,
                "source_id": self.source_id,
                "source_descriptor_hash": SOURCE_DESCRIPTOR_HASH,
                "latest": current,
                "totals": {},
                "by_action": {},
                "seen_actions": [],
                "recent_refs": [],
                "chain": "",
                "delivery": delivery,
            }
        else:
            previous = cursor["latest"]
            if current["cycle"] == previous["cycle"]:
                if delivery == cursor["delivery"]:
                    return False
                raise ValueError("conflicting duplicate challenge delivery")
            if current["cycle"] != previous["cycle"] + 1:
                raise ValueError("missing or out-of-order challenge observation")
            valid_receipt = validate_receipt(receipt, previous, current)
            label = action_label(valid_receipt)
            cursor["seen_actions"] = sorted(
                set(cursor["seen_actions"]) | {label}
            )
            left, right = public_features(previous), public_features(current)
            for feature in sorted(left.keys() & right.keys()):
                changed = int(left[feature] != right[feature])
                total = cursor["totals"].setdefault(
                    feature,
                    {"evaluable":0,"changed":0,"same":0},
                )
                exposure = cursor["by_action"].setdefault(feature, {}).setdefault(
                    label,
                    {"evaluable":0,"changed":0,"same":0},
                )
                for row in (total, exposure):
                    row["evaluable"] += 1
                    row["changed"] += changed
                    row["same"] += 1 - changed
            cursor["latest"] = current
            cursor["delivery"] = delivery

        cursor["chain"] = _digest([cursor["chain"], delivery])
        cursor["recent_refs"] = (
            cursor["recent_refs"]
            + [f"{self.source_id}:{current['observation_id']}"]
        )[-64:]
        state[STATE_KEY] = _seal(cursor)
        self.store.save(state)
        return True

    def temporal_candidates(self) -> list[dict[str, Any]]:
        _, cursor = self._load()
        if cursor is None:
            return []
        candidates = []
        for index, (feature,total) in enumerate(
            sorted(cursor["totals"].items()), start=1
        ):
            evaluable = int(total["evaluable"])
            if evaluable < 3:
                continue
            stable = int(total["same"]) >= int(total["changed"])
            candidates.append(
                {
                    "id": f"CSC{index:04d}",
                    "relation": (
                        "same_next_observation"
                        if stable else "changes_next_observation"
                    ),
                    "feature": feature,
                    "action": None,
                    "status": "evaluated",
                    "evaluable": evaluable,
                    "confirmations": int(
                        total["same"] if stable else total["changed"]
                    ),
                    "refutations": int(
                        total["changed"] if stable else total["same"]
                    ),
                }
            )
        return candidates

    def action_associations(self) -> list[dict[str, Any]]:
        _, cursor = self._load()
        if cursor is None:
            return []
        rows = []
        index = 1
        for feature,total in sorted(cursor["totals"].items()):
            for label in cursor["seen_actions"]:
                present = cursor["by_action"].get(feature, {}).get(label)
                if not present or not int(present["evaluable"]):
                    continue
                absent = {
                    key:int(total[key]) - int(present[key])
                    for key in ("evaluable","changed","same")
                }
                if absent["evaluable"] <= 0:
                    continue
                p1 = int(present["changed"]) / int(present["evaluable"])
                p0 = absent["changed"] / absent["evaluable"]
                difference = round(p1-p0, 6)
                rows.append(
                    {
                        "id": f"CSA{index:05d}",
                        "relation": "action_associated_with_change",
                        "feature": feature,
                        "action": label,
                        "status": (
                            "association_observed"
                            if difference != 0
                            else "no_observed_association"
                        ),
                        "effect_difference": difference,
                        "action_present": deepcopy(present),
                        "action_absent": absent,
                        "evaluable": int(total["evaluable"]),
                    }
                )
                index += 1
        return rows

    def publication(self) -> dict[str, Any]:
        state, cursor = self._load()
        if cursor is None:
            raise ValueError("challenge recorder has no observations")
        ranked = rank_normalized_candidates(
            self.temporal_candidates(),
            "information_gain",
        )
        selected = next((row for row in ranked if row["eligible"]), None)
        if selected is None:
            raise ValueError("challenge recorder has no eligible temporal inquiry")
        candidate = selected["candidate"]
        manifest = source_manifest()
        return {
            "version": PUBLICATION_VERSION,
            "source_id": self.source_id,
            "source_manifest_hash": source_manifest_hash(manifest),
            "chain_hash": str(cursor["chain"]),
            "coverage": {
                "start_cycle": 0,
                "end_cycle": int(cursor["latest"]["cycle"]),
            },
            "observation_refs": list(cursor["recent_refs"]),
            "selected_temporal_candidate": {
                "relation": candidate["relation"],
                "feature": candidate["feature"],
                "objective": "information_gain",
                "objective_score": float(selected["score"]),
                "evaluable": int(candidate["evaluable"]),
                "confirmations": int(candidate["confirmations"]),
                "refutations": int(candidate["refutations"]),
            },
        }

    def latest_observation(self) -> dict[str, Any]:
        _, cursor = self._load()
        if cursor is None:
            raise ValueError("challenge recorder has no observations")
        return deepcopy(cursor["latest"])


def single_transition_outcome(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    candidate: dict[str, Any],
    source_id: str = SOURCE_ID,
) -> dict[str, Any] | None:
    left, right = public_features(before), public_features(after)
    feature = str(candidate["feature"])
    if feature not in left or feature not in right:
        return None
    relation = str(candidate["relation"])
    if relation not in {"same_next_observation","changes_next_observation"}:
        raise ValueError("challenge outcome requires temporal relation")
    same = left[feature] == right[feature]
    supported = same if relation == "same_next_observation" else not same
    return {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": {
            "kind": relation,
            "feature": feature,
            "action": None,
            "comparison_status": "not_applicable",
        },
        "observation_refs": [
            f"{source_id}:{before['observation_id']}",
            f"{source_id}:{after['observation_id']}",
        ],
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": 1,
            "confirmations": 1 if supported else 0,
            "refutations": 0 if supported else 1,
        },
    }
