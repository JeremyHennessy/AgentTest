"""Pure JSON and hash primitives; no authority, source path, or world imports."""
from __future__ import annotations
import hashlib,json,re
from copy import deepcopy
RECORD_CAP=65_536
LABEL=re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
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
    envelope = {k: v for k, v in value.items() if k != "seal"}
    envelope["seal"] = digest(envelope)
    return canonical(envelope) + b"\n"


def verify_seal(value):
    if not isinstance(value, dict) or value.get("seal") != digest({k: v for k, v in value.items() if k != "seal"}):
        raise Conflict("capsule checksum mismatch")



