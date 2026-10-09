"""Frozen experimental comparison of local memory across hidden physical changes.

The PRIVATE evaluator varies the existing original/transfer world laws. The
PUBLIC learner is given only position, command and its own prior observations.
Every position/action pair is probed, not selected for a favorable response.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from agenttest import two_clock_memory as cognition
from agenttest.action_lab import (
    STATEFUL_WORLD_VERSION, TRANSFER_WORLD_VERSION, apply_bounded_action,
)

PROTOCOL = "ora-two-clock-changed-world-frozen-001"
SWEEP_COUNT_BEFORE = 6
SWEEP_COUNT_AFTER = 4
ACTIONS = cognition.ACTIONS
PANEL = [
    ([x, y], action)
    for x in range(-2, 3)
    for y in range(-2, 3)
    for action in ACTIONS
]
ARMS = {
    "TWOCLOCK-1": "two_clock",
    "LIFETIME-1": "lifetime",
    "ACTION-1": "action",
    "UNIFORM-1": "uniform",
}
SCENARIOS = {
    "no_change": (STATEFUL_WORLD_VERSION, STATEFUL_WORLD_VERSION),
    "forward_change": (STATEFUL_WORLD_VERSION, TRANSFER_WORLD_VERSION),
    "reverse_change": (TRANSFER_WORLD_VERSION, STATEFUL_WORLD_VERSION),
    "single_faulty_sensor": (STATEFUL_WORLD_VERSION, STATEFUL_WORLD_VERSION),
}


def _observed(before: list[int], action: str, law: str) -> tuple[list[int], str]:
    result = apply_bounded_action(
        before, action, bounds=2, world_version=law,
    )
    after = result["after"]
    key = f"{after[0]-before[0]},{after[1]-before[1]}"
    if key not in cognition.DELTAS:
        raise RuntimeError("unsupported world effect")
    return list(after), key


def _differential() -> set[tuple[int, int, str]]:
    diff = set()
    for position, action in PANEL:
        if _observed(position, action, STATEFUL_WORLD_VERSION) != (
            _observed(position, action, TRANSFER_WORLD_VERSION)
        ):
            diff.add((position[0], position[1], action))
    # The evaluator predeclares these two independently known source
    # differences. They are never supplied to the learner.
    expected = {(0, 2, "south"), (0, -2, "south")}
    if diff != expected:
        raise RuntimeError("authored world controls changed; invalid frozen experiment")
    return diff


def _record(identifier: str, index: int, before: list[int],
            action: str, after: list[int]) -> dict:
    return {
        "id": identifier, "index": index, "before": list(before),
        "action": action, "after": list(after),
    }


def _metric(values: list[dict[str, float | bool]]) -> dict[str, Any]:
    if not values:
        raise AssertionError("predeclared panel must retain every probe")
    return {
        "count": len(values),
        "mean_brier": round(
            sum(float(v["brier"]) for v in values) / len(values), 9,
        ),
        "mean_logloss": round(
            sum(float(v["logloss"]) for v in values) / len(values), 9,
        ),
        "exact_delta_hits": sum(bool(v["hit"]) for v in values),
    }


def _run_one(name: str, affected: set[tuple[int, int, str]]) -> dict:
    old_law, new_law = SCENARIOS[name]
    models = {arm: cognition.TwoClockMemory() for arm in ARMS}
    counter = 0
    for sweep in range(1, SWEEP_COUNT_BEFORE + 1):
        for before, action in PANEL:
            after, _ = _observed(before, action, old_law)
            counter += 1
            event = _record(f"{name}-E{counter:06d}", counter, before, action, after)
            for model in models.values():
                triggers = model.observe(event)
                if triggers:
                    raise AssertionError("prior stable environment fabricated a change")
    assert counter == 600
    # Exact serial/cold-reload parity before the new world intervention.
    for arm, model in list(models.items()):
        data = model.dump()
        restored = cognition.TwoClockMemory.load(data)
        if restored.dump() != data:
            raise AssertionError("first cold reload changed learned evidence")
        models[arm] = restored

    observations: dict[str, dict[str, list[dict]]] = {
        arm: {part: [] for part in ("all", "sensitive", "other", "late_sensitive")}
        for arm in ARMS
    }
    markers: list[dict] = []
    per_probe: list[dict] = []
    sensor_faults = 0

    for sweep in range(1, SWEEP_COUNT_AFTER + 1):
        for before, action in PANEL:
            after, actual_delta = _observed(before, action, new_law)
            sensitive = (before[0], before[1], action) in affected
            forecast = {
                arm: models[arm].predict(before, action, arm=mode)
                for arm, mode in ARMS.items()
            }
            entry = {
                "evaluation_sweep": sweep,
                "source_position": list(before),
                "public_action": action,
                "true_delta": actual_delta,
                "sensitive": sensitive,
                "predictions": {},
            }
            for arm, p in forecast.items():
                measured = cognition.scored(p, actual_delta)
                for part, qualified in (
                    ("all", True),
                    ("sensitive", sensitive),
                    ("other", not sensitive),
                    ("late_sensitive", sensitive and sweep >= 3),
                ):
                    if qualified:
                        observations[arm][part].append(measured)
                entry["predictions"][arm] = {
                    "predicted_delta": p["predicted_delta"],
                    "probability_of_true_effect": p["distribution"][actual_delta],
                    "brier": measured["brier"],
                    "basis": p["basis"],
                    "marker_active_before_prediction": p["active_local_marker"] is not None,
                }

            # Deliberate sensor corruption on precisely ONE new observation.
            # The true actual_delta above is the only scored outcome. We never
            # represent this fake report as a genuine original Ora receipt.
            fed_after = after
            faulty = name == "single_faulty_sensor" and sweep == 1 and (
                before == [0, 2] and action == "south"
            )
            if faulty:
                fed_after = [-1, 2] if after == [0, 2] else [0, 2]
                sensor_faults += 1
            entry["reported_delta"] = (
                f"{fed_after[0]-before[0]},{fed_after[1]-before[1]}"
            )
            entry["injected_sensor_error"] = faulty
            counter += 1
            event = _record(
                f"{name}-E{counter:06d}", counter, before, action, fed_after,
            )
            # Append only after all four frozen forecasts have been scored.
            for arm, model in models.items():
                activated = model.observe(event)
                if arm == "TWOCLOCK-1":
                    markers.extend(deepcopy(m) for m in activated)
            per_probe.append(entry)
        if sweep == 2:
            # Restart after the second (potential change-confirming) sweep.
            for arm, model in list(models.items()):
                blob = model.dump()
                previous = model.predict([0, 2], "south", arm=ARMS[arm])
                models[arm] = cognition.TwoClockMemory.load(blob)
                if (models[arm].dump() != blob or
                        models[arm].predict([0, 2], "south", arm=ARMS[arm]) != previous):
                    raise AssertionError("delayed restart altered model or markers")

    if counter != 1000 or len(per_probe) != 400:
        raise AssertionError("a complete panel lost or added a hidden probe")
    if any(model.events[0]["id"] != f"{name}-E000001" or len(model.events) != 1000
           for model in models.values()):
        raise AssertionError("old evidence was dropped, reordered or replayed")
    if name == "single_faulty_sensor" and sensor_faults != 1:
        raise AssertionError("single faulty-sensor control was not singular")
    if name != "single_faulty_sensor" and sensor_faults:
        raise AssertionError("unregistered sensor fault")
    return {
        "scenario": name,
        "private_training_world": old_law,
        "private_evaluation_world": new_law,
        "training_probes": 600,
        "evaluation_probes": 400,
        "actual_sensor_faults": sensor_faults,
        "matched_source_contexts": len(PANEL),
        "sensitive_contexts_predeclared": len(affected),
        "memory_rows_retained": {key: len(m.events) for key, m in models.items()},
        "change_markers": markers,
        "change_marker_count": len(markers),
        "metrics": {
            arm: {key: _metric(rows) for key, rows in partitions.items()}
            for arm, partitions in observations.items()
        },
        "per_probe": per_probe,
        "sample_identity_sha256": cognition.sha([
            [row["evaluation_sweep"], row["source_position"], row["public_action"],
             row["true_delta"], row["reported_delta"]]
            for row in per_probe
        ]),
    }


def run_study() -> dict:
    differences = _differential()
    scenarios = {
        name: _run_one(name, differences)
        for name in SCENARIOS
    }
    passes = []
    for name in ("forward_change", "reverse_change"):
        metrics = scenarios[name]["metrics"]
        candidate = metrics["TWOCLOCK-1"]
        baseline = metrics["LIFETIME-1"]
        passes.append(
            candidate["late_sensitive"]["mean_brier"]
            < baseline["late_sensitive"]["mean_brier"]
        )
        passes.append(
            candidate["other"]["mean_brier"]
            <= baseline["other"]["mean_brier"] + 0.01
        )
    for name in ("no_change", "single_faulty_sensor"):
        passes.append(scenarios[name]["change_marker_count"] == 0)
    return {
        "protocol": PROTOCOL,
        "status": "mechanism_pass" if all(passes) else "negative_or_mixed",
        "conditions": passes,
        "world_queries_per_scenario": 1000,
        "predeclared_affected_pair_count": len(differences),
        "scenarios": scenarios,
        "limits": [
            "Independent per-position physics probes are not a continually evolving individual.",
            "The learner never observes the hidden physical-law switch; private evaluator labels are provenance only.",
            "This mechanistic study does not demonstrate beneficial autonomous action, self-maintenance, new function or consciousness.",
            "One deliberately corrupted telemetry event is synthetic evidence, not a genuine original Ora action receipt.",
        ],
        "source_digests": {
            "model": hashlib.sha256(Path(cognition.__file__).read_bytes()).hexdigest(),
            "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.is_symlink() or not args.output.parent.is_dir():
        raise ValueError("pre-existing read-only study output directory required")
    report = run_study()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = {
        "protocol": report["protocol"],
        "status": report["status"],
        "conditions": report["conditions"],
        "scenarios": {
            name: {
                "markers": value["change_marker_count"],
                "two_clock_late_brier": value["metrics"]["TWOCLOCK-1"]["late_sensitive"]["mean_brier"],
                "lifetime_late_brier": value["metrics"]["LIFETIME-1"]["late_sensitive"]["mean_brier"],
            }
            for name, value in report["scenarios"].items()
        },
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
