"""Authored numerical boundary/equivalence controls; no real-history admission."""
from copy import deepcopy
from fractions import Fraction
import sys
import unittest
from unittest.mock import patch

from agenttest.grounded_policy import policy
from agenttest.grounded_policy.primitives import Conflict, canonical, digest


def row(identifier, before, after, action="north"):
    return {"event_id": identifier,
            "before_context": {"position": before, "inventory_ids": None, "visible_ids": None},
            "action": action, "after_position": after,
            "refs": {"before": digest(before), "receipt": digest(identifier), "after": digest(after)}}


def inputs(count):
    discovery = [row("D-move", [0, 0], [1, 0]), row("D-zero", [1, 0], [1, 0])]
    evidence = [row(f"U-{index}", [0, 0], [1, 0]) for index in range(count)]
    return discovery, discovery[0]["before_context"], evidence


class ExactNumericContract(unittest.TestCase):
    def test_legacy_bodies_scores_ties_and_thresholds_are_byte_identical(self):
        for count in (0, 1, 7, 40, 120):
            with self.subTest(count=count):
                discovery, context, evidence = inputs(count)
                cohort = policy.build_cohort(discovery)
                legacy = policy.evaluate(cohort, context, evidence)
                exact = policy.evaluate_bounded_exact(cohort, context, evidence)
                self.assertEqual(exact.pop("numeric_contract"), policy.EXACT_NUMERIC_CONTRACT)
                self.assertEqual(canonical(exact), canonical(legacy))
                self.assertTrue(policy.verify_evaluation(discovery, context, evidence, legacy))
        # A complete symmetric menu preserves the established movement-order tie.
        discovery = [row(f"D-{action}-{kind}", before, after, action)
                     for action in policy.ACTIONS
                     for kind, before, after in (("move", [0, 0], [1, 0]), ("zero", [1, 0], [1, 0]))]
        cohort = policy.build_cohort(discovery)
        legacy = policy.evaluate(cohort, context, [])
        exact = policy.evaluate_bounded_exact(cohort, context, [])
        exact.pop("numeric_contract")
        self.assertEqual(canonical(exact), canonical(legacy))

    def test_146_updates_extend_exactly_and_match_independent_integer_masses(self):
        discovery, context, evidence = inputs(146)
        cohort = policy.build_cohort(discovery)
        with self.assertRaisesRegex(Conflict, "rational_component_overflow"):
            policy.evaluate(cohort, context, evidence)
        body = policy.evaluate_bounded_exact(cohort, context, evidence)
        north = body["menu"][0]
        # Closed form is an independent test oracle, not the production updater.
        masses = [114 ** 146 if model["position"] == [1, 0] else 3 ** 146
                  for model in north["concrete_predictions"]] + [40 ** 146]
        total = sum(masses)
        actual = [Fraction(int(item["weight"][0]), int(item["weight"][1])) for item in north["posterior"]]
        self.assertEqual(actual, [Fraction(mass, total) for mass in masses])
        self.assertGreater(max(len(component) for item in north["posterior"] for component in item["weight"]), 256)
        self.assertTrue(policy.verify_bounded_exact_evaluation(discovery, context, evidence, body))
        # Reading old 256-digit receipts still uses the old contract.
        old = policy.evaluate(cohort, context, evidence[:7])
        self.assertTrue(policy.verify_evaluation(discovery, context, evidence[:7], old))
        with self.assertRaisesRegex(Conflict, "rational_component_overflow"):
            policy._checked(Fraction(10 ** 256))

    def test_history_bound_and_codec_are_exact_without_global_digit_settings(self):
        bound = 120 * 8 * 114 ** policy.EXACT_MAX_EVIDENCE_ROWS
        self.assertLess(bound, 10 ** policy.EXACT_RATIONAL_DIGITS)
        self.assertEqual(bound.bit_length(), 55985)
        old_limit = sys.get_int_max_str_digits()
        token = policy._ACTIVE_RATIONAL_DIGITS.set(policy.EXACT_RATIONAL_DIGITS)
        try:
            value = Fraction(-(10 ** 6000 + 7), 10 ** 5999 + 9)
            encoded = policy.fraction_pair(value)
            self.assertGreater(len(encoded[0]), 4300)
            self.assertEqual(policy.parse_pair(encoded), value)
            self.assertEqual(policy._integer_text(bound).__len__(), 16854)
            with self.assertRaisesRegex(Conflict, "rational_component_overflow"):
                policy._checked(Fraction(10 ** policy.EXACT_RATIONAL_DIGITS))
        finally:
            policy._ACTIVE_RATIONAL_DIGITS.reset(token)
        self.assertEqual(sys.get_int_max_str_digits(), old_limit)
        with self.assertRaisesRegex(Conflict, "rational_component_overflow"):
            policy.parse_pair(encoded)

    def test_resource_boundaries_and_scoped_failure_do_not_relax_legacy_api(self):
        discovery, context, evidence = inputs(1)
        cohort = policy.build_cohort(discovery)
        with self.assertRaisesRegex(Conflict, "exact_evidence_capacity_exhausted"):
            policy.evaluate_bounded_exact(cohort, context, evidence * 8193)
        oversized = {"numeric_contract": policy.EXACT_NUMERIC_CONTRACT,
                     "oversized": "x" * policy.EXACT_DECISION_BYTES}
        with self.assertRaisesRegex(Conflict, "exact policy decision exceeds"):
            policy.verify_bounded_exact_evaluation(discovery, context, evidence, oversized)
        with patch.object(policy, "evaluate", side_effect=Conflict("authored_failure")):
            with self.assertRaisesRegex(Conflict, "authored_failure"):
                policy.evaluate_bounded_exact(cohort, context, evidence)
        with self.assertRaisesRegex(Conflict, "rational_component_overflow"):
            policy._checked(Fraction(10 ** 256))
        self.assertEqual(policy.RATIONAL_DIGITS, 256)
        self.assertEqual(str(policy.THRESHOLD), "0.010000000000000000")
        self.assertEqual(str(policy.TIE_TOLERANCE), "1.000000E-12")


if __name__ == "__main__":
    unittest.main()
