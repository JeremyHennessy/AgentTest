"""Prospectively registered, one-time passive prediction comparison.

No original Ora actions or persistent pilot. The independent evaluator owns
actions and hidden mechanics. Both models see only the same public history.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import subprocess

from .blind_context_world import ACTIONS, BOUNDS, VERSION as WORLD, BlindContextWorld
from .pilot_worker import forecast as local_forecast

VERSION = "ora2-blind-context-prediction-study001-v1"
PROTOCOL_BLOB = "930a9956a62bba1a53af455afe2b07e2a0f13746"
DOMAIN = tuple((x, y) for x in range(-2, 3) for y in range(-2, 3))
SEEDS = tuple(range(12))
STEPS = 64
WARMUP = 16
MIN_ADVANTAGE = 0.03
MIN_WINS = 9
MIN_SENSITIVE = 24


class InvalidStudy(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def schedule(seed, index):
    if type(seed) is not int or type(index) is not int or index < 1:
        raise InvalidStudy("invalid evaluator action schedule input")
    key = f"ora2-blind-context-study001-action:{seed}:{index}".encode()
    return ACTIONS[hashlib.sha256(key).digest()[0] % len(ACTIONS)]


def stream(seed):
    if type(seed) is not int:
        raise InvalidStudy("invalid evaluator stream seed")
    return sha(f"ora2-blind-context-study001-stream:{seed}".encode())[:32]


def strong_spatial(view, history, action):
    """Independent strong baseline; only prior actual observations."""
    position = tuple(view["position"])
    delta = Counter()
    for row in history:
        if row["action"] != action or row["blocked"]:
            continue
        before, after = row["before"], row["after"]
        delta[(after[0] - before[0], after[1] - before[1])] += 1
    counts = Counter()
    for move, n in delta.items():
        target = tuple(max(-BOUNDS, min(BOUNDS, position[i] + move[i]))
                       for i in (0, 1))
        counts[target] += n
    total = sum(counts.values())
    if total == 0:
        return [1 / len(DOMAIN)] * len(DOMAIN)
    return [0.1 / len(DOMAIN) + 0.9 * counts[p] / total for p in DOMAIN]


def validate(probabilities):
    if (type(probabilities) is not list or len(probabilities) != 25 or
            any(type(p) not in (float, int) or not math.isfinite(p) or p <= 0 or p >= 1
                for p in probabilities) or
            not math.isclose(math.fsum(probabilities), 1.0, rel_tol=0, abs_tol=1e-12)):
        raise InvalidStudy("invalid forecast probabilities")


def top_one(probabilities):
    return list(DOMAIN[max(range(25), key=lambda i: probabilities[i])])


def evaluate_world(seed):
    if type(seed) is not int or not 0 <= seed < 2**63:
        raise InvalidStudy("invalid evaluator seed")
    world = BlindContextWorld(seed=seed, stream_id=stream(seed), budget=STEPS)
    history, cases, receipts = [], [], []
    for index in range(1, STEPS + 1):
        view = world.public_view()
        action = schedule(seed, index)
        # Never pass the world, seed, private map, or current outcome to models.
        baseline = strong_spatial(view, history, action)
        candidate = local_forecast(view, history, action)
        validate(baseline)
        validate(candidate)
        saved = {"view": view, "action": action, "baseline": baseline,
                 "candidate": candidate}
        forecast_sha256 = sha(canonical(saved))
        receipt = world.step(action)
        if receipt.before != tuple(view["position"]) or receipt.index != index:
            raise InvalidStudy("world action attribution differs")
        evidence = receipt.evidence()
        if evidence["source_id"] != receipt.digest or evidence["action"] != action:
            raise InvalidStudy("missing source provenance")
        receipts.append(receipt)
        actual = list(receipt.after)
        position_index = DOMAIN.index(tuple(actual))
        p_base, p_candidate = baseline[position_index], candidate[position_index]
        # Evaluator-only sensitivity classification, never exposed to either model.
        target = tuple(receipt.before[i] + world._rules[int(index >= world._change_at)][action][i]
                       for i in (0, 1))
        nonboundary_block = receipt.blocked and all(-BOUNDS <= x <= BOUNDS for x in target)
        changed_regime = index >= world._change_at
        if index > WARMUP:
            case = {
                "seed": seed, "index": index, "view": view, "action": action,
                "forecast_sha256": forecast_sha256, "baseline": baseline,
                "candidate": candidate, "receipt": asdict(receipt),
                "evidence": evidence, "actual_after": actual,
                "baseline_loss_bits": -math.log2(p_base),
                "candidate_loss_bits": -math.log2(p_candidate),
                "advantage_bits": math.log2(p_candidate / p_base),
                "baseline_top_one": top_one(baseline),
                "candidate_top_one": top_one(candidate),
                "sensitive_case": bool(nonboundary_block or changed_regime),
                "actual_baseline_probability": p_base,
                "actual_candidate_probability": p_candidate,
            }
            cases.append(case)
        history.append(evidence)
    reconstructed = BlindContextWorld.reconstruct(seed=seed, stream_id=stream(seed),
                                                   receipts=receipts, budget=STEPS)
    if reconstructed.recorded() != world.recorded() or len(cases) != STEPS - WARMUP:
        raise InvalidStudy("cold world reconstruction or fixed budget mismatch")
    mean = math.fsum(c["advantage_bits"] for c in cases) / len(cases)
    return {
        "seed": seed, "stream": stream(seed), "actions": STEPS,
        "warmup": WARMUP, "scored": len(cases), "mean_advantage_bits": mean,
        "sensitive_cases": sum(c["sensitive_case"] for c in cases),
        "last_receipt_digest": receipts[-1].digest,
        "cases": cases,
    }


def check_protocol(root):
    path = root / "docs/ORA2_BLIND_CONTEXT_STUDY001.md"
    blob = subprocess.check_output(["git", "-C", str(root), "hash-object", str(path)],
                                   text=True).strip()
    if blob != PROTOCOL_BLOB:
        raise InvalidStudy("prospective protocol changed or missing")
    if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD:src"],
                               text=True).strip() != "9b0f880af84a0b1b69fd6aa9009ab738acd7dfad":
        raise InvalidStudy("protected Phase41 source changed")
    return blob


def run(root):
    root = Path(root).resolve()
    protocol = check_protocol(root)
    source_hashes = {
        name: sha((root / name).read_bytes()) for name in
        ("ora2/blind_context_world.py", "ora2/pilot_worker.py",
         "ora2/blind_context_study001.py")
    }
    results = [evaluate_world(seed) for seed in SEEDS]
    cases = [c for world in results for c in world["cases"]]
    if (len(results) != 12 or len(cases) != 576 or
            any(world["actions"] != 64 or world["scored"] != 48 for world in results) or
            len({(c["seed"], c["index"]) for c in cases}) != 576):
        raise InvalidStudy("registered case budget or identity differs")
    mean = math.fsum(c["advantage_bits"] for c in cases) / len(cases)
    wins = sum(world["mean_advantage_bits"] > 0 for world in results)
    sensitivity = sum(c["sensitive_case"] for c in cases)
    if sensitivity < MIN_SENSITIVE:
        status = "INCONCLUSIVE_LOW_SENSITIVITY"
    elif mean >= MIN_ADVANTAGE and wins >= MIN_WINS:
        status = "VALID_POSITIVE"
    else:
        status = "VALID_NEGATIVE"
    summary = {
        "version": VERSION, "status": status,
        "protocol_blob": protocol, "source_sha256": source_hashes,
        "seeds": list(SEEDS), "actions": 768, "warmup": 192,
        "paired_scored_cases": 576,
        "mean_advantage_bits_per_case": mean, "paired_seed_wins": wins,
        "sensitive_cases": sensitivity, "required_sensitivity": MIN_SENSITIVE,
        "mean_baseline_loss_bits": math.fsum(c["baseline_loss_bits"] for c in cases) / len(cases),
        "mean_candidate_loss_bits": math.fsum(c["candidate_loss_bits"] for c in cases) / len(cases),
        "baseline_top_one_correct": sum(c["baseline_top_one"] == c["actual_after"] for c in cases),
        "candidate_top_one_correct": sum(c["candidate_top_one"] == c["actual_after"] for c in cases),
        "original_live_ora_actions": 0, "learner_owned_actions": 0,
        "persistent_pilot_enabled": False,
        "limitations": "Evaluator-scripted exposures in authored copied worlds; no learner-owned investigation or inherited-goal continuity.",
    }
    return {"summary": summary, "worlds": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-registered-study", action="store_true")
    args = parser.parse_args()
    if not args.enable_registered_study:
        raise SystemExit("explicit one-time registered-study enablement required")
    result = run(args.root)
    if args.output.exists() or args.output.is_relative_to(args.root.resolve()):
        raise SystemExit("new external report path required")
    args.output.write_bytes(canonical(result) + b"\n")
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
