"""Isolated, opt-in streaming recorder; not wired into live AgentCore.cycle.

Only the latest public observation and sufficient counts are retained. Native
summaries are cumulative snapshots, NOT disjoint batches: read only the current
publication manifest and never add overlapping snapshot counts together.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from types import FunctionType
from typing import Any

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION, validate_native_evidence_payload
from agenttest.state import StateStore
from normalized_inquiry_objectives import rank_normalized_candidates
from open_object_world_action_association import action_label
from open_object_world_epistemic_actions import select_epistemic_command
from open_object_world_native_bridge import public_features

KEY = "isolated_native_stream_recorder_v1"
VERSION = "public-stream-recorder-v1"
WORLD = "open-object-world-v0"
ACTIONS = {"north", "east", "south", "west", "inspect", "interact", "take", "drop", "push"}
LABEL = re.compile(r"[A-Za-z0-9_.-]{1,96}\Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _label(value: Any) -> str:
    if not isinstance(value, str) or not LABEL.fullmatch(value):
        raise ValueError("invalid public identifier")
    return value


def _position(value: Any) -> None:
    if not isinstance(value, list) or len(value) != 2 or any(type(x) is not int or not -2 <= x <= 2 for x in value):
        raise ValueError("invalid public position")


def _observation(value: Any) -> dict:
    fields = {"world_version", "observation_id", "cycle", "position", "inventory_ids", "visible_entities"}
    if not isinstance(value, dict) or set(value) != fields or value["world_version"] != WORLD:
        raise ValueError("observation contract mismatch or hidden field")
    cycle = value["cycle"]
    if type(cycle) is not int or cycle < 0 or value["observation_id"] != f"ow-{cycle:06d}":
        raise ValueError("observation sequence/id mismatch")
    _position(value["position"])
    inventory = value["inventory_ids"]
    if not isinstance(inventory, list) or len(inventory) != len(set(map(str, inventory))):
        raise ValueError("invalid inventory")
    for item in inventory:
        _label(item)
    if not isinstance(value["visible_entities"], list):
        raise ValueError("invalid visible entities")
    ids = set()
    for entity in value["visible_entities"]:
        required = {"id", "position", "appearance"}
        if not isinstance(entity, dict) or not required <= set(entity) or set(entity) - (required | {"observable_state"}):
            raise ValueError("entity contract mismatch or hidden field")
        _label(entity["id"])
        if entity["id"] in ids or entity["id"] in inventory:
            raise ValueError("duplicate visible/inventory identity")
        ids.add(entity["id"])
        _position(entity["position"])
        if sum(abs(a-b) for a,b in zip(value["position"], entity["position"])) > 1:
            raise ValueError("nonlocal entity")
        if not isinstance(entity["appearance"], str) or ("observable_state" in entity and not isinstance(entity["observable_state"], str)):
            raise ValueError("invalid public entity value")
    return deepcopy(value)


def _receipt(value: Any, before: dict, after: dict) -> dict:
    required = {"id", "cycle", "action", "target", "direction", "before", "after", "success", "blocked", "observed_effects", "mechanism_observed_state", "barrier_observed_state"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - (required | {"inspection"}):
        raise ValueError("receipt contract mismatch or hidden field")
    if type(value["cycle"]) is not int or value["cycle"] != after["cycle"] or value["id"] != f"OWA{after['cycle']:06d}":
        raise ValueError("receipt sequence/id mismatch")
    if value["before"] != before["position"] or value["after"] != after["position"]:
        raise ValueError("receipt is not aligned to the observations")
    if value["action"] not in ACTIONS:
        raise ValueError("unknown public action")
    for key in ("target", "direction"):
        if value[key] is not None:
            _label(value[key])
    if any(type(value[k]) is not bool for k in ("success", "blocked")):
        raise ValueError("invalid receipt flags")
    if not isinstance(value["observed_effects"], list) or any(not isinstance(x, str) for x in value["observed_effects"]):
        raise ValueError("invalid receipt effects")
    for key in ("mechanism_observed_state", "barrier_observed_state"):
        if value[key] is not None and not isinstance(value[key], str):
            raise ValueError("invalid receipt state")
    if "inspection" in value:
        inspection = value["inspection"]
        if not isinstance(inspection, dict) or set(inspection) != {"id", "position", "appearance", "observable_state"}:
            raise ValueError("inspection contract mismatch or hidden field")
        _label(inspection["id"])
        _position(inspection["position"])
        if not isinstance(inspection["appearance"], str) or (inspection["observable_state"] is not None and not isinstance(inspection["observable_state"], str)):
            raise ValueError("invalid inspection")
    return deepcopy(value)


def _seal(cursor: dict) -> dict:
    cursor["checksum"] = _digest({k: v for k, v in cursor.items() if k != "checksum"})
    return cursor


class _CopyStore:
    """In-memory transaction target for unchanged, nonpersisting native APIs."""
    def __init__(self, state: dict):
        self.state = deepcopy(state)

    def load(self) -> dict:
        return deepcopy(self.state)


class NativeStreamRecorder:
    def __init__(self, store: StateStore, source_id: str, *, enabled: bool = False):
        if enabled is not True:
            raise RuntimeError("isolated stream recorder is disabled by default")
        self.store = store
        self.source_id = _label(source_id)
        root = Path(__file__).resolve().parents[1]
        if store.path.resolve().is_relative_to(root / "state"):
            raise ValueError("research recorder refuses repository live-state directory")
        if not store.path.exists():
            raise ValueError("explicit pre-created isolated StateStore required")

    def _load(self) -> tuple[dict, dict | None]:
        state = self.store.load()
        cursor = state.get(KEY)
        if cursor is not None:
            if not isinstance(cursor, dict) or cursor.get("version") != VERSION or cursor.get("source_id") != self.source_id:
                raise ValueError("recorder version/source mismatch")
            if cursor.get("checksum") != _digest({k: v for k, v in cursor.items() if k != "checksum"}):
                raise ValueError("recorder checkpoint checksum mismatch")
        return state, cursor

    def ingest(self, observation: dict, receipt: dict | None = None, *, source_id: str) -> bool:
        """Commit one contiguous sample. Return False only for an identical retry.

        Receipt labels/flags are never treated as outcome truth; change counts
        come exclusively from adjacent publicly observable feature values.
        """
        if source_id != self.source_id:
            raise ValueError("source mismatch")
        current = _observation(observation)
        state, cursor = self._load()
        delivery = _digest({"source": source_id, "observation": current, "receipt": receipt})
        if cursor is None:
            if current["cycle"] != 0 or receipt is not None:
                raise ValueError("a new source must start at observation zero without a receipt")
            cursor = {"version": VERSION, "source_id": source_id, "latest": current, "totals": {}, "by_action": {}, "seen_actions": [], "recent_refs": [], "chain": "", "delivery": delivery, "published": None}
        else:
            previous = cursor["latest"]
            if current["cycle"] == previous["cycle"]:
                if delivery == cursor["delivery"]:
                    return False
                raise ValueError("conflicting duplicate delivery")
            if current["cycle"] != previous["cycle"] + 1:
                raise ValueError("missing or out-of-order sample")
            valid_receipt = _receipt(receipt, previous, current)
            label = action_label(valid_receipt)
            cursor["seen_actions"] = sorted(set(cursor["seen_actions"]) | {label})
            left, right = public_features(previous), public_features(current)
            for feature in sorted(left.keys() & right.keys()):
                changed = int(left[feature] != right[feature])
                total = cursor["totals"].setdefault(feature, {"evaluable": 0, "changed": 0, "same": 0})
                exposure = cursor["by_action"].setdefault(feature, {}).setdefault(label, {"evaluable": 0, "changed": 0, "same": 0})
                for count in (total, exposure):
                    count["evaluable"] += 1
                    count["changed"] += changed
                    count["same"] += 1 - changed
            cursor["latest"] = current
            cursor["delivery"] = delivery
        cursor["chain"] = _digest([cursor["chain"], delivery])
        cursor["recent_refs"] = (cursor["recent_refs"] + [f"{source_id}:{current['observation_id']}"])[-64:]
        state[KEY] = _seal(cursor)
        self.store.save(state)
        return True

    def publish(self) -> dict:
        """Atomically publish all eligible summaries, not just the winning one.

        Evidence counts cover the whole stream prefix. Up to 64 recent sample
        refs are retained under the existing v2 schema, with a prefix digest in
        the recorder manifest. This is not a signed observation-source registry
        and does not make complete raw provenance independently replayable.
        """
        state, cursor = self._load()
        if cursor is None:
            raise ValueError("no public observations recorded")
        previous = cursor["published"]
        if previous and previous["chain"] == cursor["chain"]:
            self._published_payloads(state, cursor)
            return deepcopy(previous)
        staged = _CopyStore(state)
        core = AgentCore(staged)
        refs: list[str] = []
        def record(relation: dict, kind: str, measurement: dict) -> None:
            result = core.record_native_evidence({"version": NATIVE_EVIDENCE_V2_VERSION, "relation": relation, "observation_refs": cursor["recent_refs"], "measurement_kind": kind, "measurement": measurement}, enabled=True, persist=False)
            staged.state = result["state"]
            refs.append(result["evidence_ref"])
        for feature, total in sorted(cursor["totals"].items()):
            if total["evaluable"] >= 3:
                stable = total["same"] >= total["changed"]
                record({"kind": "same_next_observation" if stable else "changes_next_observation", "feature": feature, "action": None, "comparison_status": "not_applicable"}, "binary_transition_outcomes", {"evaluable": total["evaluable"], "confirmations": total["same"] if stable else total["changed"], "refutations": total["changed"] if stable else total["same"]})
            for label in cursor["seen_actions"]:
                present = cursor["by_action"].get(feature, {}).get(label)
                if not present or not present["evaluable"]:
                    continue
                absent = {k: total[k] - present[k] for k in total}
                if not absent["evaluable"]:
                    continue
                p1 = present["changed"] / present["evaluable"]
                p0 = absent["changed"] / absent["evaluable"]
                record({"kind": "action_associated_with_change", "feature": feature, "action": label, "comparison_status": "comparable"}, "comparative_action_exposure", {"action_present": present, "action_absent": absent, "observed_change_rate_action_present": round(p1, 6), "observed_change_rate_action_absent": round(p0, 6), "observed_change_rate_difference": round(p1-p0, 6)})
        payloads = [e["content"] for e in staged.state["episodes"] if e["id"] in set(refs)]
        cursor["published"] = {"cycle": cursor["latest"]["cycle"], "chain": cursor["chain"], "evidence_refs": refs, "payload_checksum": _digest(payloads)}
        staged.state[KEY] = _seal(cursor)
        self.store.save(staged.state)  # One existing StateStore atomic replacement.
        return deepcopy(cursor["published"])

    def _published_payloads(self, state: dict, cursor: dict) -> list[dict]:
        publication = cursor["published"]
        if not publication or publication["chain"] != cursor["chain"]:
            raise ValueError("publish the current sample before requesting a decision")
        by_id = {e["id"]: e for e in state["episodes"]}
        contents = []
        for ref in publication["evidence_refs"]:
            episode = by_id.get(ref)
            if not episode or episode.get("kind") != "native_inquiry_evidence":
                raise ValueError("published native evidence is missing")
            contents.append(episode["content"])
        if _digest(contents) != publication["payload_checksum"]:
            raise ValueError("published evidence checksum mismatch")
        return [validate_native_evidence_payload(json.loads(content)) for content in contents]

    def candidates(self) -> tuple[list[dict], list[dict]]:
        state, cursor = self._load()
        if cursor is None:
            raise ValueError("no recorder checkpoint")
        temporal, actions = [], []
        for payload in self._published_payloads(state, cursor):
            relation, m = payload["relation"], payload["measurement"]
            if payload["measurement_kind"] == "binary_transition_outcomes":
                temporal.append({"relation": relation["kind"], "feature": relation["feature"], "action": None, "status": "evaluated", **m})
            else:
                difference = m["observed_change_rate_difference"]
                actions.append({"relation": relation["kind"], "feature": relation["feature"], "action": relation["action"], "status": "association_observed" if difference != 0 else "no_observed_association", "effect_difference": difference, "action_present": m["action_present"], "action_absent": m["action_absent"], "evaluable": m["action_present"]["evaluable"] + m["action_absent"]["evaluable"]})
        temporal.sort(key=lambda c: c["feature"])
        actions.sort(key=lambda c: (c["feature"], c["action"]))
        for i, candidate in enumerate(temporal, 1):
            candidate["id"] = f"OWC{i:04d}"
        for i, candidate in enumerate(actions, 1):
            candidate["id"] = f"OWA{i:05d}"
        return temporal, actions

    def decision(self) -> dict:
        """Read only. The research adapter changes the selector's data source,
        never its code, parameters, command generator or tie-breaking rules.
        """
        temporal, associations = self.candidates()
        ranked = rank_normalized_candidates(temporal, "information_gain")
        if not ranked:
            raise ValueError("no eligible temporal inquiry yet")
        candidate = ranked[0]["candidate"]
        _, cursor = self._load()
        namespace = dict(select_epistemic_command.__globals__)
        namespace["association_candidates"] = lambda *_a, **_k: deepcopy(associations)
        selector = FunctionType(select_epistemic_command.__code__, namespace)
        selection = selector(cursor["latest"], feature=candidate["feature"], relation=candidate["relation"], prefix_observations=[], prefix_receipts=[])
        return {"ranked": ranked, "associations": associations, "selection": selection}
