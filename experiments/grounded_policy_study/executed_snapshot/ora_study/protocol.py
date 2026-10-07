"""Frozen scheduling metadata. No world, observation or outcome is constructed."""
from __future__ import annotations
import hashlib
import json

MIB = 1_048_576
MOVEMENTS = ("north", "east", "south", "west")
LAYOUTS = (1, 2, 3, 4)
ANCHORS = (32, 36, 40, 44, 48, 52, 56, 60)
ARMS = ("R", "W")
LIMITS = {
    "neutral_durable": 256, "owned_durable": 128, "probe_durable": 128,
    "transition_invocations": 512, "decisions": 128,
    "output_bytes": 192 * MIB, "finalization_reserve_bytes": MIB,
    "concurrent_tree_rss_bytes": 512 * MIB,
    "aggregate_cpu_ns": 900_000_000_000, "wall_ns": 1_500_000_000_000,
}
APPROVED_FILES = {
    "policy-implementation-review/PROTOCOL_V4_EXACT_BYTE_SIGNOFF.md": "d33be2c89ed7e1563f872574d4b7186d31e9507977284dac9c8eacc70471e0dd",
    "policy-study-protocol/FIRST_COMPARISON_V4.md": "0764aab03b99d59cc9eeb9c3aaeac481beda5c955c860e6c3db5f94fd08bda50",
    "policy-study-protocol/AMENDMENT_RECORD.md": "095db08770dcd89a358abcad80562b027abf58c09e23fb8aa9376141f966d80a",
    "policy-implementation-review/PROTOCOL_COHORT_CONSTRUCTION_AMENDMENT_REVIEW_V2.md": "7c0be59220df4b44d578c2a48c4859ba9db647712c768ff89e7701017d6e282f",
    "investigation-policy-design/FIRST_COMPARISON.md": "6f40f7bd8606a0e97f3f18eb4220347309e36892c0872bd4f5ff2721c6881241",
    "investigation-policy-design/POLICY_AND_API.md": "5d1d686afa22a269b5061031c5a75b77121241aee2aac84228473481da4e319d",
    "investigation-policy-review/FINAL_REVIEW.md": "1606e9e72680d9b92e33a6cd98e90302ec5b2a58fb0a66a37db684bf376a0014",
}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def registry():
    """Declare slots only; these are not generated scientific anchor records."""
    pairs = []
    for layout in LAYOUTS:
        for t in ANCHORS:
            anchor_id = f"layout{layout}.t{t}"
            pairs.append({"anchor_id": anchor_id, "layout": layout, "t": t,
                          "cases": {arm: f"{anchor_id}.{arm}" for arm in ARMS}})
    return {"anchors": pairs, "arm_case_ids": [a["cases"][arm] for a in pairs for arm in ARMS],
            "decision_ids": [f"{a['cases'][arm]}.stage{stage}" for a in pairs for arm in ARMS for stage in (1, 2)]}

def transition_slots():
    neutral = [f"neutral.layout{layout}.t{t}" for layout in LAYOUTS for t in range(1, 65)]
    owned = ["owned." + decision for decision in registry()["decision_ids"]]
    probes = [f"probe.{a['anchor_id']}.{move}" for a in registry()["anchors"] for move in MOVEMENTS]
    return {"neutral": neutral, "owned": owned, "probe": probes}

CALL_CEILINGS = {"producer":64,"capsule_validation":1986,"cohort_proof":1986,
                 "decision_proof":2500,"checker_reconstruction":4486,
                 "selecting_backend":128,"forbidden_core_cycle":0}

def worker_slots():
    slots=[f"neutral.layout{layout}" for layout in LAYOUTS]
    for case in registry()["arm_case_ids"]:
        slots += [f"{case}.create_select.stage1",f"{case}.execute.stage1",f"{case}.interpret.stage1",
                  f"{case}.select.stage2",f"{case}.execute.stage2",f"{case}.interpret.stage2"]
    slots += [f"probes.{anchor['anchor_id']}" for anchor in registry()["anchors"]]
    slots += ["terminal_reconciliation","reporter"]
    return slots

CALL_CEILINGS["transition"]=512

def worker_allowances(worker_id):
    out={name:0 for name in CALL_CEILINGS}
    if worker_id.startswith("neutral.layout"):
        out["transition"]=64
    elif worker_id.startswith("probes."):
        out["transition"]=4
    elif worker_id=="terminal_reconciliation":
        out.update(capsule_validation=2,cohort_proof=2,decision_proof=4,checker_reconstruction=6)
    elif worker_id=="reporter":
        pass
    else:
        phase,stage=worker_id.split(".")[-2:]
        if phase=="create_select":
            out.update(producer=1,capsule_validation=6,cohort_proof=6,decision_proof=2,checker_reconstruction=8,selecting_backend=1)
        else:
            decision_proofs=7 if phase=="select" else 5 if stage=="stage1" else 10
            out.update(capsule_validation=5,cohort_proof=5,decision_proof=decision_proofs,checker_reconstruction=5+decision_proofs)
            if phase=="select":
                out["selecting_backend"]=1
            if phase=="execute":
                out["transition"]=1
    return out
