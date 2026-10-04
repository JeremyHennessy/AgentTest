from __future__ import annotations

import unittest

from agenttest.native_activation import (
    DEFAULT_NATIVE_ACTIVATION_POLICY,
    temporal_activation_policy,
    validate_native_activation_policy,
)


class NativeActivationPolicyTests(unittest.TestCase):
    def test_default_policy_is_fully_off(self):
        policy = validate_native_activation_policy(None)
        self.assertEqual(policy, DEFAULT_NATIVE_ACTIVATION_POLICY)
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["mode"], "off")
        self.assertEqual(policy["allowed_relations"], [])
        self.assertIsNone(policy["objective"])

    def test_explicit_temporal_policy_is_observe_and_inquire_only(self):
        policy = validate_native_activation_policy(temporal_activation_policy())
        self.assertTrue(policy["enabled"])
        self.assertEqual(policy["mode"], "observe_and_inquire")
        self.assertEqual(policy["objective"], "information_gain")
        self.assertEqual(
            set(policy["allowed_relations"]),
            {"same_next_observation", "changes_next_observation"},
        )
        self.assertFalse(policy["allow_environment_actions"])
        self.assertFalse(policy["allow_action_lab"])
        self.assertFalse(policy["allow_planning_lab"])

    def test_action_association_cannot_be_allowlisted(self):
        policy = temporal_activation_policy()
        policy["allowed_relations"].append("action_associated_with_change")
        with self.assertRaises(ValueError):
            validate_native_activation_policy(policy)

    def test_policy_cannot_grant_environment_action_authority(self):
        for field in (
            "allow_environment_actions",
            "allow_action_lab",
            "allow_planning_lab",
        ):
            policy = temporal_activation_policy()
            policy[field] = True
            with self.assertRaises(ValueError):
                validate_native_activation_policy(policy)

    def test_disabled_policy_cannot_hide_persistence_or_objective(self):
        policy = dict(DEFAULT_NATIVE_ACTIVATION_POLICY)
        policy["objective"] = "information_gain"
        with self.assertRaises(ValueError):
            validate_native_activation_policy(policy)


if __name__ == "__main__":
    unittest.main()
