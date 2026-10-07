"""Frozen v4 source-only profile. No caller can authorize scientific execution."""
from types import MappingProxyType
from .artifact_inventory import ALLOCATIONS, SOURCE_BOUNDS
from .profiles import SCIENTIFIC_PROFILE
from .protocol import CALL_CEILINGS, MIB, registry, worker_slots, worker_allowances

SCIENTIFIC_ADMISSION_REVIEWED = False
PROFILE = SCIENTIFIC_PROFILE
CALL_CAPS = MappingProxyType(dict(CALL_CEILINGS))
SLOTS = tuple(worker_slots())
NORMAL_SLOTS = tuple(slot for slot in SLOTS if ".stage" in slot)
LEDGER_CAP = 17 * MIB
LEDGER_SEGMENT_CAPS = (2 * MIB,) * 8 + (MIB,)
LEDGER_NAMES = ("ledger.jsonl",) + tuple(f"ledger.part{index:04d}.jsonl" for index in range(1, 9))
LOG_CAP = MIB - 32768
PIPE_CAP = 4 * MIB
WORKER_PROTOCOL_CAP = 12 * MIB
RUN_PROTOCOL_CAP = len(SLOTS) * WORKER_PROTOCOL_CAP
ABSOLUTE_LIFETIME_SECONDS = 850
# Prospective reallocation only: existing fixture evidence/profile is immutable.
# Native capsules remain the raw authority, so exporters need not duplicate them.
ALLOCATION = MappingProxyType({**ALLOCATIONS, "ledger_and_logs": 18 * MIB, "saved_exports": 8 * MIB})

assert len(registry()["anchors"]) == 32
assert len(PROFILE["case_ids"]) == 64
assert len(registry()["decision_ids"]) == 128
assert len(NORMAL_SLOTS) == 384
assert sum(ALLOCATION.values()) == 192 * MIB
assert LEDGER_CAP + LOG_CAP + 32768 == ALLOCATION["ledger_and_logs"]
assert 64 * sum(SOURCE_BOUNDS.values()) <= ALLOCATION["source_inputs"]
assert {category: sum(worker_allowances(slot)[category] for slot in SLOTS)
        for category in CALL_CAPS} == dict(CALL_CAPS)


def require_scientific_admission():
    if SCIENTIFIC_ADMISSION_REVIEWED is not True:
        raise RuntimeError("Scientific execution disabled pending separate exact-source admission")
