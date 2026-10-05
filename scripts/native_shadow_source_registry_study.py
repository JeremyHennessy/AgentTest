from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.native_shadow_source_registry import (
    PINNED_OPEN_OBJECT_WORLD_SOURCE,
    expected_attestation,
    registry_entry_hash,
    shadow_source_manifest,
    validate_attestation,
)

_ALLOWED_OBSERVATION_FIELDS = {
    "world_version",
    "observation_id",
    "cycle",
    "position",
    "inventory_ids",
    "visible_entities",
}
_ALLOWED_ENTITY_FIELDS = {
    "id",
    "position",
    "appearance",
    "observable_state",
}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load pinned component: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _assert_public_observation(observation: dict) -> None:
    if set(observation) != _ALLOWED_OBSERVATION_FIELDS:
        raise AssertionError("pinned source emitted unexpected observation fields")
    if any(str(key).startswith("_") for key in observation):
        raise AssertionError("pinned source exposed private observation field")
    for entity in observation["visible_entities"]:
        if not set(entity) <= _ALLOWED_ENTITY_FIELDS:
            raise AssertionError("pinned source exposed unexpected entity field")
        if any(str(key).startswith("_") for key in entity):
            raise AssertionError("pinned source exposed private entity field")


def run(source_dir: Path, attestation_path: Path) -> dict:
    entry = PINNED_OPEN_OBJECT_WORLD_SOURCE
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    checked_attestation = validate_attestation(entry, attestation)
    manifest = shadow_source_manifest(entry, checked_attestation)

    world_module = _load_module(
        "open_object_world",
        source_dir / "open_object_world.py",
    )
    explorer_module = _load_module(
        "open_object_world_explorer",
        source_dir / "open_object_world_explorer.py",
    )

    layout_rows = []
    for seed in range(1, 5):
        world = world_module.initial_world(seed)
        attempts = Counter()
        observation = world_module.observe_world(world)
        _assert_public_observation(observation)
        public_observations = 1
        receipt_count = 0
        for cycle in range(1, 241):
            command = explorer_module.choose_command(observation, attempts)
            attempts[
                (
                    explorer_module.observation_signature(observation),
                    explorer_module.command_key(command),
                )
            ] += 1
            world, receipt = world_module.transition(
                world,
                command,
                cycle=cycle,
            )
            if any(str(key).startswith("_") for key in receipt):
                raise AssertionError("pinned source receipt exposed private field")
            observation = world_module.observe_world(world)
            _assert_public_observation(observation)
            public_observations += 1
            receipt_count += 1
        layout_rows.append(
            {
                "seed": seed,
                "public_observation_count": public_observations,
                "receipt_count": receipt_count,
                "final_observation": observation,
            }
        )

    return {
        "study": "native-shadow-source-registry-v1",
        "registry_entry_hash": registry_entry_hash(entry),
        "attestation": checked_attestation,
        "derived_manifest": manifest,
        "layout_rows": layout_rows,
        "authority": {
            "shadow_only": True,
            "live_activation": False,
            "environment_actions": False,
            "action_lab": False,
            "planning_lab": False,
            "phase42_credit": False,
            "external_model_api": False,
        },
        "limitations": [
            "Git object pinning proves reviewed source bytes in this workflow; it is not cryptographic attestation of an arbitrary future runtime stream.",
            "The explorer drives this shadow stream externally; this does not grant Ora environmental action authority.",
            "Source registration does not solve native evidence retention or StateStore compaction.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run(Path(args.source_dir), Path(args.attestation))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
