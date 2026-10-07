"""Bounded contracts and complete-capsule consistency checks.

Hashes detect accidental/conflicting mutation, not hostile writers who replace
all hashes. The supported world is the existing fixed Challenge schema.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

from challenge_shadow_recorder import (SOURCE_ID, SOURCE_DESCRIPTOR_HASH,
    validate_observation, validate_receipt, public_features)
from open_object_world_challenge import WORLD_VERSION, initial_world, observe_world
from . import IMPORT_MANIFEST

VERSION = "inquiry-executive-v1"
RULE = "case-local-declarative-v1"
MIB = 1_048_576
RECORD_CAP = 65_536
COMPLETION_RESERVE = MIB
INTERPRETATION_RESERVE = 131_072
# T2 additions: full outcome (<= 3 frames/receipts + 16 KiB metadata), new
# frame (<=64 KiB), two recorder replacements (each <=128 KiB), world history receipt
# (<=64 KiB), world bounded structural changes (<=8 KiB), event/attempt
# changes (<=16 KiB), seal/counters/newline (<=4 KiB). T3 <=64 KiB belief +
# <=16 KiB metadata/event. Reserialization does not duplicate old history.
T2_GROWTH_BOUND = 3 * RECORD_CAP + 16_384 + RECORD_CAP + 2 * 131_072 + RECORD_CAP + 8_192 + 16_384 + 4_096
T3_GROWTH_BOUND = RECORD_CAP + 16_384
assert T2_GROWTH_BOUND + INTERPRETATION_RESERVE < COMPLETION_RESERVE
assert T3_GROWTH_BOUND < INTERPRETATION_RESERVE
ROOT = Path(__file__).resolve().parents[2]
LABEL = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")

class Conflict(ValueError):
    pass

class Capacity(Conflict):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def bounded(value, cap=RECORD_CAP, what="record"):
    if len(canonical(value)) > cap:
        raise Capacity(f"{what} exceeds schema byte bound")
    return value


def exact(value, fields, what):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise Conflict(f"{what} fields violate contract")


def integer(value, low, high, what):
    if type(value) is not int or not low <= value <= high:
        raise Conflict(f"invalid {what}")


def label(value, what="identifier"):
    if not isinstance(value, str) or not LABEL.fullmatch(value):
        raise Conflict(f"invalid {what}")
    return value


def strict_json(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Conflict("duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(value):
        raise Conflict("nonfinite JSON value")
    try:
        return json.loads(payload, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Conflict("invalid JSON") from error


def seal(value):
    value = deepcopy(value)
    value["seal"] = digest({k: v for k, v in value.items() if k != "seal"})
    return value


def encoded(value):
    return canonical(seal(value)) + b"\n"


def verify_seal(value):
    if not isinstance(value, dict) or value.get("seal") != seal(value)["seal"]:
        raise Conflict("capsule checksum mismatch")


def code_manifest():
    """Conservative closure: every production module plus all adapter dependencies."""
    bootstrap = ROOT / "experiments/inquiry_executive"
    if not sys.dont_write_bytecode or (bootstrap / "__init__.pyc").exists() or any((bootstrap / "__pycache__").glob("__init__.*.pyc")):
        raise Conflict("source proof requires fresh -B interpreter and no executive bootstrap bytecode cache")
    names = [p for p in (ROOT / "src/agenttest").rglob("*.py")]
    names += list((ROOT / "experiments/inquiry_executive").glob("*.py"))
    names += [ROOT / "experiments" / (name + ".py") for name in (
        "challenge_action_authority", "challenge_shadow_recorder",
        "challenge_shadow_epistemic_selector", "native_observe_inquire_integration",
        "normalized_inquiry_objectives", "open_object_world_challenge",
        "open_object_world_challenge_explorer")]
    for name, module in tuple(sys.modules.items()):
        if name == "agenttest" or name.startswith("agenttest.") or name in {
            p.stem for p in names if p.parent == ROOT / "experiments"
        } or name.startswith("inquiry_executive"):
            path = getattr(module, "__file__", None)
            if path and not Path(path).resolve().is_relative_to(ROOT):
                raise Conflict(f"execution dependency outside pinned tree: {name}")
    current = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(names)}
    if current != IMPORT_MANIFEST:
        raise Conflict("execution source changed since package import")
    return current


def profile(name="synthetic_contract", *, max_bytes=None, max_decisions=None,
            max_actions=None, input_hash=None):
    if name == "synthetic_contract":
        result = {"name": name, "max_bytes": 2*MIB if max_bytes is None else max_bytes,
                  "max_decisions": 8 if max_decisions is None else max_decisions,
                  "max_actions": 4 if max_actions is None else max_actions,
                  "input_hash": None}
        integer(result["max_bytes"], 1, 16*MIB, "byte cap")
        integer(result["max_decisions"], 1, 16, "decision cap")
        integer(result["max_actions"], 0, 8, "action cap")
        if input_hash is not None:
            raise Conflict("synthetic profile cannot declare preserved input")
    elif name == "preserved_input_smoke":
        if max_bytes is None or max_decisions not in (None, 1) or max_actions not in (None, 1):
            raise Conflict("smoke requires explicit bytes and one decision/action")
        if not isinstance(input_hash, str) or not re.fullmatch("[a-f0-9]{64}", input_hash):
            raise Conflict("smoke requires immutable input hash")
        integer(max_bytes, 1, 256*MIB, "smoke byte cap")
        result = dict(name=name, max_bytes=max_bytes, max_decisions=1, max_actions=1,
                      input_hash=input_hash)
    else:
        raise Conflict("unknown capacity profile")
    if result["max_actions"] > result["max_decisions"]:
        raise Conflict("actions exceed decisions")
    return result


def validate_profile(value):
    exact(value, "name max_bytes max_decisions max_actions input_hash", "profile")
    if value != profile(value["name"], **{k: v for k, v in value.items() if k != "name"}):
        raise Conflict("noncanonical profile")


def validate_world(world):
    exact(world, "world_version layout_id cycle position inventory entities history", "world")
    integer(world["layout_id"], 1, 4, "layout")
    integer(world["cycle"], 0, 1_000_000, "world cycle")
    base = initial_world(world["layout_id"])
    if set(world["entities"]) != set(base["entities"]):
        raise Conflict("fixed Challenge entities required")
    for key, entity in world["entities"].items():
        original = base["entities"][key]
        if set(entity) != set(original):
            raise Conflict("unknown Challenge entity fields")
        for field, value in original.items():
            if field not in {"position", "_latched"} and entity[field] != value:
                raise Conflict("fixed Challenge entity schema changed")
        if "_latched" in entity and type(entity["_latched"]) is not bool:
            raise Conflict("invalid latch")
        if entity["position"] is not None:
            _position(entity["position"])
    _position(world["position"])
    if len(world["history"]) != world["cycle"]:
        raise Conflict("Challenge history/cycle mismatch")
    if not isinstance(world["history"], list):
        raise Conflict("invalid world history")
    for record in world["history"]:
        bounded(record, what="history receipt")
    bounded({k: v for k, v in world.items() if k != "history"}, 8_192, "world structure")
    bounded(validate_observation(observe_world(world)), what="public observation")


def _position(position):
    if not isinstance(position, list) or len(position) != 2:
        raise Conflict("invalid position")
    for item in position:
        integer(item, -2, 2, "position")


def hypotheses(value):
    if not isinstance(value, list) or not 2 <= len(value) <= 8:
        raise Conflict("inquiry needs 2–8 explanations")
    seen = set()
    for row in value:
        exact(row, "id explanation scope prediction", "hypothesis")
        label(row["id"])
        if row["id"] in seen:
            raise Conflict("duplicate hypothesis ID")
        seen.add(row["id"])
        for field in ("explanation", "scope"):
            if not isinstance(row[field], str) or not 1 <= len(row[field]) <= 512:
                raise Conflict("bounded explanation/scope required")
        prediction = row["prediction"]
        exact(prediction, "kind values", "prediction")
        if prediction["kind"] not in {"equal", "different", "categorical", "unavailable"}:
            raise Conflict("unsupported prediction")
        if not isinstance(prediction["values"], list) or len(prediction["values"]) > 8:
            raise Conflict("invalid categorical prediction")
        if prediction["kind"] != "categorical" and prediction["values"]:
            raise Conflict("unexpected prediction values")
        if prediction["kind"] == "categorical" and not prediction["values"]:
            raise Conflict("empty categorical prediction")
        for item in prediction["values"]:
            if not isinstance(item, (str, int, bool, list)):
                raise Conflict("invalid categorical value")
            bounded(item, 1_024, "categorical value")
    bounded(value, 16_384, "hypotheses")
    return deepcopy(value)


def unique(rows, what):
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise Conflict(f"invalid {what}")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(item, str) for item in ids) or len(ids) != len(set(ids)):
        raise Conflict(f"duplicate/invalid {what} identity")
    return {row["id"]: row for row in rows}


def ensure_capacity(state):
    size = len(encoded(state))
    if size + state["reserve"] > state["identity"]["profile"]["max_bytes"]:
        raise Capacity("capacity_exhausted: full capsule plus completion reserve")
    return size


def strict_receipt(value, before, after):
    """Legacy structural validation plus exact integral receipt coordinates."""
    result = validate_receipt(value, before, after)
    for field in ("before", "after"):
        _position(value[field])
    if "inspection" in value:
        _position(value["inspection"]["position"])
    return result


def integral_metadata(value):
    """Reject bool/equal-float encodings for retained integral metadata.

    Public feature values and scientific scores are deliberately not coerced.
    Optional absent counts/cycles stay null. Version strings remain strings;
    the executive's numeric hypothesis versions are checked separately.
    """
    names = {"revision", "sequence", "cycles", "cycle", "generation", "times_selected",
             "expected_revision", "budget_ordinal", "present_evaluable", "present_changed",
             "evaluable", "confirmations", "refutations",
             "next_episode_index"}
    if isinstance(value, dict):
        if {"evaluable", "changed", "same"} <= set(value):
            for key in ("evaluable", "changed", "same"):
                integer(value[key], 0, 2**53-1, "integral observation counter " + key)
        for key, child in value.items():
            if child is not None and (key in names or key.endswith("_cycle") or key.endswith("_count") or key.endswith("_episode_sequence")):
                integer(child, 0, 2**53-1, "integral metadata " + key)
            integral_metadata(child)
    elif isinstance(value, list):
        for child in value:
            integral_metadata(child)
