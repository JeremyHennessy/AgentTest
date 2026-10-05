from __future__ import annotations

import deepcopy
import unittest

from experiments.native_shadow_source_registry import (
    ATTESTATION_VERSION,
    MANIFEST_VERSION,
    PINNED_OPEN_OBJECT_WORLD_SOURCE,
    expected_attestation,
    registry_entry_hash,
    shadow_source_manifest,
    validate_attestation,
    validate_registry_entry,
)


class NativeShadowSourceRegistryTests(unittest.TestCase):
    def entry(self):
        return deepcopy(PINNED_OPEN_OBJECT_WORLD_SOURCE)

    def test_reviewed_entry_is_strictly_shadow_only(self):
        checked = validate_registry_entry(self.entry())
        self.assertEqual(
            checked["source_id"],
            "research.open-object-world-v0",
        )
        self.assertEqual(checked["activation_scope"], "shadow_only")
        for field in (
            "signed_source",
            "allow_live_activation",
            "allow_environment_actions",
            "allow_action_lab",
            "allow_planning_lab",
            "allow_phase42_credit",
        ):
            self.assertFalse(checked[field])

    def test_registry_hash_is_order_stable_for_components(self):
        first = self.entry()
        second = self.entry()
        second["components"].reverse()
        self.assertEqual(registry_entry_hash(first), registry_entry_hash(second))

    def test_tampered_commit_or_component_is_rejected_by_attestation(self):
        entry = self.entry()
        attestation = expected_attestation(entry)

        wrong_commit = deepcopy(attestation)
        wrong_commit["commit_sha"] = "0" * 40
        with self.assertRaises(ValueError):
            validate_attestation(entry, wrong_commit)

        wrong_blob = deepcopy(attestation)
        wrong_blob["components"][0]["blob_sha"] = "1" * 40
        with self.assertRaises(ValueError):
            validate_attestation(entry, wrong_blob)

        missing = deepcopy(attestation)
        missing["components"].pop()
        with self.assertRaises(ValueError):
            validate_attestation(entry, missing)

    def test_registry_cannot_be_reinterpreted_as_live_authority(self):
        for field in (
            "allow_live_activation",
            "allow_environment_actions",
            "allow_action_lab",
            "allow_planning_lab",
            "allow_phase42_credit",
            "signed_source",
        ):
            entry = self.entry()
            entry[field] = True
            with self.assertRaises(ValueError):
                validate_registry_entry(entry)

        entry = self.entry()
        entry["activation_scope"] = "live"
        with self.assertRaises(ValueError):
            validate_registry_entry(entry)

    def test_manifest_is_derived_only_after_exact_attestation(self):
        entry = self.entry()
        attestation = expected_attestation(entry)
        self.assertEqual(attestation["version"], ATTESTATION_VERSION)
        manifest = shadow_source_manifest(entry, attestation)
        self.assertEqual(manifest["version"], MANIFEST_VERSION)
        self.assertEqual(
            manifest["registry_entry_hash"],
            registry_entry_hash(entry),
        )
        self.assertFalse(manifest["signed_source"])
        self.assertFalse(manifest["allow_live_activation"])

    def test_component_paths_reject_escape_or_duplicates(self):
        entry = self.entry()
        entry["components"][0]["path"] = "../open_object_world.py"
        with self.assertRaises(ValueError):
            validate_registry_entry(entry)

        entry = self.entry()
        entry["components"][1]["path"] = entry["components"][0]["path"]
        with self.assertRaises(ValueError):
            validate_registry_entry(entry)


if __name__ == "__main__":
    unittest.main()
