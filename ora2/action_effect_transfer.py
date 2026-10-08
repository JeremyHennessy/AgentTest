"""Pre-registered read-only action-effect transfer; no actuator or model API.

An engineer supplied translation/clamp representation learns command effects
from training transitions. A positive result is not autonomous discovery.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

VERSION = "ora2-action-effect-transfer-study001-v1"
WORLD = "bounded-stateful-world-v1"
SNAPSHOT = "f37c788cee851622823a848a7e3b8b32f67c06bec4b94eb5b709922e7a7aa6ec"
JOURNAL = "717b7380101ff7656b13cc5d9f8ac14ade862a6bdd1b9363ad3029d29d8e35e9"
BOUNDS, SMOOTHING, MAX_ROWS = 2, 0.10, 8192
EXPECTED_FOLDS, EXPECTED_CONTEXTS, EXPECTED_ROWS = 25, 95, 1637


class StudyInvalid(ValueError):
    """Invalid evidence produces no admitted scientific result."""


def point(value):
    if (type(value) not in (tuple, list) or len(value) != 2 or
            any(type(x) is not int or not -BOUNDS <= x <= BOUNDS for x in value)):
        raise StudyInvalid("invalid public coordinates")
    return tuple(value)


def domain():
    return tuple((x, y) for x in range(-BOUNDS, BOUNDS + 1)
                 for y in range(-BOUNDS, BOUNDS + 1))


def validate_rows(rows):
    if type(rows) is not list or not 0 < len(rows) <= MAX_ROWS:
        raise StudyInvalid("missing or above-limit same-world rows")
    normalized, seen, prior_cycle = [], set(), -1
    for item in rows:
        if type(item) is not dict or item.get("world_version") != WORLD:
            raise StudyInvalid("nonmatching world not admitted")
        before, after = point(item.get("before")), point(item.get("after"))
        action, blocked = item.get("action"), item.get("blocked")
        if type(action) is not str or not 0 < len(action) <= 128:
            raise StudyInvalid("invalid opaque command")
        if type(blocked) is not bool or blocked and before != after:
            raise StudyInvalid("invalid blocked observation")
        cycle, source_id, source = item.get("cycle"), item.get("source_id"), item.get("source")
        if (type(cycle) is not int or cycle < prior_cycle or
                type(source_id) is not str or not source_id or
                type(source) is not str or not source):
            raise StudyInvalid("invalid chronology or provenance")
        prior_cycle = cycle
        identity = (source, source_id)
        if identity in seen:
            raise StudyInvalid("duplicate identity must be deduplicated upstream")
        seen.add(identity)
        normalized.append(dict(before=before, after=after, action=action,
                               blocked=blocked, cycle=cycle, source_id=source_id,
                               source=source))
    return normalized


def predict(training, before, action, *, model):
    """Only training rows, public source coordinate and opaque action enter."""
    if model not in ("shared_effect", "nonspatial"):
        raise StudyInvalid("unknown registered predictor")
    before = point(before)
    counts = Counter()
    for row in training:
        if row["action"] != action:
            continue
        if model == "shared_effect":
            if row["blocked"]:
                continue
            delta = tuple(row["after"][i] - row["before"][i] for i in (0, 1))
            target = tuple(max(-BOUNDS, min(BOUNDS, before[i] + delta[i]))
                           for i in (0, 1))
        else:
            target = row["after"]
        counts[target] += 1
    targets = domain()
    if not counts:
        return {p: 1 / len(targets) for p in targets}
    total = sum(counts.values())
    distribution = {p: SMOOTHING / len(targets) +
                    (1 - SMOOTHING) * counts[p] / total for p in targets}
    if not math.isclose(math.fsum(distribution.values()), 1, abs_tol=1e-12, rel_tol=0):
        raise StudyInvalid("prediction is not normalized")
    return distribution


def top_one(distribution):
    # Stable ties use the public lexicographic coordinate order.
    return max(sorted(distribution), key=lambda pos: distribution[pos])


def evaluate(observations):
    rows = validate_rows(observations)
    locations = sorted({row["before"] for row in rows})
    # Earliest genuine record per source-position/action, never reweighted by
    # the number of repeated visits to the held-out source location.
    cases_by_context = {}
    for row in rows:
        cases_by_context.setdefault((row["before"], row["action"]), row)
    cases, folds = [], []
    for before in locations:
        training = [r for r in rows if r["before"] != before]
        if any(row["before"] == before for row in training):
            raise StudyInvalid("held-out source leaked into training")
        tests = sorted((r for (source, _), r in cases_by_context.items()
                        if source == before), key=lambda r: r["action"])
        if not tests:
            raise StudyInvalid("empty held-out fold")
        fold_cases = []
        for row in tests:
            # BOTH forecasts are completed before the evaluator reads after.
            shared = predict(training, before, row["action"], model="shared_effect")
            baseline = predict(training, before, row["action"], model="nonspatial")
            actual = row["after"]
            p_shared, p_baseline = shared[actual], baseline[actual]
            if not (0 < p_shared <= 1 and 0 < p_baseline <= 1):
                raise StudyInvalid("actual outcome likelihood invalid")
            loss_shared, loss_baseline = -math.log2(p_shared), -math.log2(p_baseline)
            receipt = {
                "before": list(before), "action": row["action"],
                "actual_after": list(actual), "source_id": row["source_id"],
                "blocked": row["blocked"], "train_rows": len(training),
                "train_action_nonblocked": sum(x["action"] == row["action"] and not x["blocked"]
                                                for x in training),
                "shared_effect_probability": p_shared, "nonspatial_probability": p_baseline,
                "shared_effect_top_one": list(top_one(shared)),
                "nonspatial_top_one": list(top_one(baseline)),
                "shared_effect_loss_bits": loss_shared,
                "nonspatial_loss_bits": loss_baseline,
                "advantage_bits": loss_baseline - loss_shared,
            }
            fold_cases.append(receipt)
            cases.append(receipt)
        folds.append({
            "position": list(before), "cases": len(fold_cases),
            "mean_advantage_bits": math.fsum(r["advantage_bits"] for r in fold_cases) / len(fold_cases),
            "mean_shared_loss_bits": math.fsum(r["shared_effect_loss_bits"] for r in fold_cases) / len(fold_cases),
            "mean_nonspatial_loss_bits": math.fsum(r["nonspatial_loss_bits"] for r in fold_cases) / len(fold_cases),
        })
    advantage = math.fsum(r["advantage_bits"] for r in cases) / len(cases)
    wins = sum(f["mean_advantage_bits"] > 0 for f in folds)
    return {
        "version": VERSION, "world": WORLD, "smoothing": SMOOTHING,
        "same_world_records": len(rows), "positions": len(locations),
        "unique_observed_position_actions": len(cases_by_context),
        "never_observed_position_actions": len(domain()) *
            len({row["action"] for row in rows}) - len(cases_by_context),
        "evaluated_cases": len(cases),
        "mean_shared_effect_loss_bits":
            math.fsum(r["shared_effect_loss_bits"] for r in cases) / len(cases),
        "mean_nonspatial_loss_bits":
            math.fsum(r["nonspatial_loss_bits"] for r in cases) / len(cases),
        "mean_advantage_bits_per_case": advantage,
        "mean_advantage_bits_per_fold":
            math.fsum(f["mean_advantage_bits"] for f in folds) / len(folds),
        "fold_wins": wins, "folds": folds, "cases": cases,
        "validity_screen": (len(locations) == EXPECTED_FOLDS and
                            len(cases_by_context) == EXPECTED_CONTEXTS and
                            len(cases) == EXPECTED_CONTEXTS and len(rows) == EXPECTED_ROWS),
        "transfer_screen_met": bool(advantage >= 0.25 and wins >= 20),
        "original_live_ora_actions": 0, "copied_world_actions": 0,
        "persistent_pilot_enabled": False,
        "limitations": "Retrospective one-world holdout; translation/clamping is authored, not autonomously discovered. Does not establish useful exploration, persistent learning, or subjective experience."
    }


def read_evidence(snapshot_path, journal_path):
    from .inherited_origin import read
    from .baseline import strict_json
    raw, journal, projection = read(snapshot_path, journal_path)
    if (hashlib.sha256(raw).hexdigest() != SNAPSHOT or
            hashlib.sha256(journal).hexdigest() != JOURNAL or
            projection["origin_cycle"] != 1803):
        raise StudyInvalid("immutable copied source changed")
    state = strict_json(raw)
    if state["planning_lab"]["bounds"] != BOUNDS:
        raise StudyInvalid("public bounds differ")
    identities = {}
    for row in state["planning_lab"]["transition_observations"]:
        key = (row.get("source"), row.get("source_id"))
        if key in identities and identities[key] != row:
            raise StudyInvalid("contradictory duplicate provenance")
        identities[key] = row
    retained = []
    for row in projection["rows"]:
        source = identities[(row["source"], row["source_id"])]
        if source.get("world_version") != WORLD:
            raise StudyInvalid("cross-world projection")
        retained.append(source)
    return retained


def run(snapshot_path, journal_path):
    result = evaluate(read_evidence(snapshot_path, journal_path))
    if not result["validity_screen"]:
        raise StudyInvalid("registered historical coverage differs; no score admitted")
    result.update({
        "status": "VALID_RECORDED_HELDOUT_RESULT",
        "snapshot_sha256": SNAPSHOT, "journal_sha256": JOURNAL,
        "predeclared_screen": "mean advantage >=0.25 bits/case and >=20/25 positive folds",
        "interpretation": "STRUCTURAL_TRANSFER_SCREEN_MET_ONLY" if
            result["transfer_screen_met"] else "VALID_NEGATIVE_STRUCTURAL_TRANSFER",
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for label in ("snapshot", "journal", "output"):
        parser.add_argument("--" + label, type=Path, required=True)
    args = parser.parse_args()
    for input_path in (args.snapshot, args.journal):
        if not input_path.is_file() or input_path.is_symlink():
            raise StudyInvalid("bounded independent historical input required")
    if (args.output.exists() or args.output.is_symlink() or
            args.output.resolve().is_relative_to(args.snapshot.resolve().parent) or
            args.output.resolve().is_relative_to(args.journal.resolve().parent)):
        raise StudyInvalid("new independent report outside the evidence directory required")
    receipt = run(args.snapshot, args.journal)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: receipt[k] for k in (
        "status", "same_world_records", "evaluated_cases",
        "mean_advantage_bits_per_case", "fold_wins", "transfer_screen_met")}, sort_keys=True))


if __name__ == "__main__":
    main()
