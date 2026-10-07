"""Synthetic-only finite-policy invariants; imports no world transition module."""
from __future__ import annotations

from grounded_policy_v2 import policy
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import inspect
import unittest
from unittest.mock import patch

from grounded_policy_v2.primitives import Conflict, canonical, digest


def context(position=None, inventory=None, visible=None):
    return {"position": [0, 0] if position is None else position,
            "inventory_ids": [] if inventory is None else inventory,
            "visible_ids": [] if visible is None else visible}


def row(event, before, after, action="north"):
    return {"event_id": event, "before_context": deepcopy(before), "action": action,
            "after_position": deepcopy(after),
            "refs": {kind: digest([event, kind]) for kind in ("before", "receipt", "after")}}


def discovery(action="north"):
    return [row("D-" + action + "-0", context(inventory=["key-a"]), [0, 0], action),
            row("D-" + action + "-1", context(), [0, 1], action)]


def numeric(body):
    """Remove structural/provenance identities, not forecasts or rule ordering."""
    return {"selected_action": body["selected_action"], "menu": [
        {key: deepcopy(item[key]) for key in ("action", "cohort_status", "forecastable", "forecast_reason",
                                               "inquiry_eligible", "eligibility_reason", "selection_eligible", "selection_reason",
                                               "forecast", "unresolved_mass", "predictive_entropy_bits", "expected_model_entropy_bits", "score_bits")}
        | {"positions": [entry["position"] for entry in item["concrete_predictions"]],
           "weights": [entry["weight"] for entry in item["posterior"]],
           "unavailable_reasons": [entry["reason"] for entry in item["unavailable_models"]]}
        for item in body["menu"]]}


class PolicyCases(unittest.TestCase):
    def evaluate(self, d=None, c=None, u=None):
        d = discovery() if d is None else d
        c = context() if c is None else c
        u = [] if u is None else u
        cohort = policy.build_cohort(d)
        body = policy.evaluate(cohort, c, u)
        self.assertTrue(policy.verify_cohort(d, cohort))
        self.assertTrue(policy.verify_evaluation(d, c, u, body))
        return cohort, body

    def test_synthetic_test_does_not_import_world_or_backend(self):
        source = inspect.getsource(policy)
        self.assertNotIn("open_object_world", source)
        self.assertNotIn("challenge_shadow", source)
        self.assertNotIn("agenttest", source)

    def test_complete_menu_and_observation_derived_delta(self):
        d = [row("a", context(), [0, 0]), row("b", context(inventory=["x"]), [1, -1])]
        cohort, body = self.evaluate(d)
        self.assertEqual(cohort["actions"][0]["nonzero_delta"], [1, -1])
        self.assertEqual([item["action"] for item in body["menu"]], list(policy.ACTIONS))
        self.assertEqual(body["selected_action"], "north")
        self.assertTrue(body["menu"][0]["inquiry_eligible"])
        for item in body["menu"][1:]:
            self.assertEqual(item["forecast_reason"], "insufficient_explanatory_diversity")
            self.assertIsNone(item["forecast"])

    def test_empty_and_missing_diversity_nulls(self):
        for d in ([], [row("a", context(), [0, 0])], [row("a", context(), [0, 1])]):
            _, body = self.evaluate(d)
            self.assertIsNone(body["selected_action"])
            self.assertEqual(len(body["menu"]), 4)
            self.assertFalse(any(item["forecastable"] for item in body["menu"]))

    def test_multiple_nonzero_outside_model_class(self):
        d = discovery() + [row("extra", context(), [1, 0])]
        cohort, body = self.evaluate(d)
        self.assertEqual(cohort["actions"][0]["status"], "outside_first_model_class")
        self.assertEqual(body["menu"][0]["forecast_reason"], "outside_first_model_class")
        self.assertEqual(cohort["actions"][0]["models"], [])

    def test_two_constants_and_complete_support(self):
        cohort, _ = self.evaluate()
        models = cohort["actions"][0]["models"]
        self.assertEqual([model["structure"]["kind"] for model in models],
                         ["constant", "constant", "conditional", "conditional", "unresolved_process"])
        for model in models[:-1]:
            self.assertEqual(len(model["derivation"]["construction"]), 2)
            self.assertTrue(all(model["derivation"]["branches"]))
            self.assertEqual(model["model_id"], "rule-" + digest(model["structure"]))
        self.assertEqual([model["construction_loss"] for model in models[:4]], [1, 1, 0, 0])

    def test_uniform_available_prior_exact_likelihoods(self):
        _, body = self.evaluate()
        item = body["menu"][0]
        for posterior in item["posterior"]:
            self.assertEqual(posterior["weight"], ["1", "5"])
            values = set(tuple(x) for x in posterior["distribution"].values())
            self.assertEqual(values, {("1", "3")} if posterior["model_id"] == "N" else {("19", "20"), ("1", "40")})
        expected = {"zero": ["163", "600"], "displacement": ["77", "120"], "other": ["13", "150"]}
        self.assertEqual(item["forecast"], expected)
        self.assertEqual(sum(policy.parse_pair(pair) for pair in item["forecast"].values()), 1)

    def test_exact_single_evidence_update(self):
        u = [row("U1", context(), [0, 0])]
        _, body = self.evaluate(u=u)
        item = body["menu"][0]
        # One zero-predicting model, three move-predicting models, and N.
        probabilities = [Fraction(19, 20), Fraction(1, 40), Fraction(1, 40), Fraction(1, 40), Fraction(1, 3)]
        denominator = sum(probabilities)
        self.assertEqual([policy.parse_pair(entry["weight"]) for entry in item["posterior"]],
                         [p / denominator for p in probabilities])
        self.assertEqual(item["evidence_event_ids"], ["U1"])

    def test_exact_context_action_match_only(self):
        baseline = self.evaluate()[1]
        variants = [row("wrong-action", context(), [0, 0], "east"),
                    row("new-position", context([1, 0]), [1, 0]),
                    row("new-inventory", context(inventory=["other"]), [0, 0]),
                    row("missing-outcome", context(), None)]
        body = self.evaluate(u=variants)[1]
        self.assertEqual(baseline, body)

    def test_entity_context_changes_do_not_transfer_evidence(self):
        c = context(visible=["opaque"])
        c["entity.opaque.position"] = [1, 0]
        c["entity.opaque.state"] = "closed"
        prior = self.evaluate(c=c)[1]
        changed = deepcopy(c)
        changed["entity.opaque.state"] = "open"
        body = self.evaluate(c=c, u=[row("changed", changed, [0, 0])])[1]
        self.assertEqual(body, prior)

    def test_duplicate_D_and_U_have_no_learning_effect(self):
        d = discovery()
        u = [row("U1", context(), [0, 0])]
        cohort, body = self.evaluate(d, u=u)
        doubled, again = self.evaluate([d[0], d[0], d[1], d[0], d[1]], u=u + u)
        self.assertEqual(cohort, doubled)
        self.assertEqual(body, again)

    def test_changed_body_duplicate_rejects_including_refs(self):
        for changed_key in ("after_position", "refs", "before_context"):
            d = discovery()
            forged = deepcopy(d[0])
            forged[changed_key] = {"after_position": [0, 1], "refs": {kind: "f" * 64 for kind in ("before", "receipt", "after")},
                                  "before_context": context()}[changed_key]
            with self.assertRaises(Conflict):
                policy.build_cohort(d + [forged])
            u = row("U", context(), [0, 0])
            altered = deepcopy(u)
            altered[changed_key] = forged[changed_key]
            if altered != u:
                with self.assertRaises(Conflict):
                    policy.evaluate(policy.build_cohort(d), context(), [u, altered])

    def test_discovery_is_never_recounted_as_evidence(self):
        with self.assertRaises(Conflict):
            policy.evaluate(policy.build_cohort(discovery()), context(), discovery())

    def test_opaque_identifier_alpha_renaming_and_reference_labels(self):
        d = []
        for index in range(8):
            identity = ["z", "a", "t", "b", "k", "c", "n", "d"][index]
            d.append(row("D" + str(index), context(inventory=[identity], visible=["v" + identity]), [0, index % 2]))
        cohort, first = self.evaluate(d, context(inventory=["z"], visible=["vz"]))
        replacements = {x: "renamed-" + str(99 - index) for index, x in enumerate(["z", "a", "t", "b", "k", "c", "n", "d"])}
        def rename_context(c):
            return {"position": c["position"], "inventory_ids": [replacements[x] for x in c["inventory_ids"]],
                    "visible_ids": ["v" + replacements[x[1:]] for x in c["visible_ids"]]}
        renamed = []
        for index, event in enumerate(d):
            changed = row("display-" + str(index), rename_context(event["before_context"]), event["after_position"])
            renamed.append(changed)
        second_cohort, second = self.evaluate(renamed, rename_context(context(inventory=["z"], visible=["vz"])))
        self.assertEqual(numeric(first), numeric(second))
        self.assertEqual([model["structural_order"] for model in cohort["actions"][0]["models"][:-1]],
                         [model["structural_order"] for model in second_cohort["actions"][0]["models"][:-1]])

    def test_json_key_order_and_unordered_identity_sets(self):
        d = discovery()
        d[0]["before_context"]["inventory_ids"] = ["z", "a"]
        reversed_dicts = [{key: item[key] for key in reversed(list(item))} for item in d]
        reversed_dicts[0]["before_context"] = deepcopy(d[0]["before_context"])
        reversed_dicts[0]["before_context"]["inventory_ids"] = ["a", "z"]
        self.assertEqual(policy.build_cohort(d), policy.build_cohort(reversed_dicts))

    def test_chronological_ties_not_identifier_spelling(self):
        d = [row("D" + str(i), context(inventory=[name]), [0, i % 2])
             for i, name in enumerate(["z", "a", "y", "b", "x", "c", "w", "d"])]
        cohort, _ = self.evaluate(d)
        conditions = [m for m in cohort["actions"][0]["models"] if m["structure"]["kind"] == "conditional"]
        self.assertEqual([m["structure"]["value"] for m in conditions], [["z"], ["a"], ["y"], ["b"], ["x"]])

    def test_missing_predicate_abstains_not_false(self):
        c = context()
        c["inventory_ids"] = None
        _, body = self.evaluate(c=c)
        entry = body["menu"][0]
        self.assertEqual(len(entry["concrete_predictions"]), 2)
        self.assertEqual(len(entry["unavailable_models"]), 2)
        self.assertEqual({model["reason"] for model in entry["unavailable_models"]}, {"missing_predicate_field"})
        self.assertEqual([posterior["weight"] for posterior in entry["posterior"]], [["1", "3"]] * 3)
        empty_body = self.evaluate(c=context())[1]
        self.assertNotEqual(body["context_digest"], empty_body["context_digest"])

    def test_missing_field_construction_loss_is_not_correct(self):
        d = discovery() + [row("missing", {"position": [0, 0], "visible_ids": []}, [0, 0])]
        cohort, _ = self.evaluate(d)
        for model in cohort["actions"][0]["models"]:
            if model["structure"]["kind"] == "conditional":
                self.assertEqual(model["construction_loss"], 1)

    def test_missing_position_N_cannot_manufacture_forecast(self):
        c = context()
        c["position"] = None
        _, body = self.evaluate(c=c)
        item = body["menu"][0]
        self.assertEqual(item["forecast_reason"], "no_available_concrete_models")
        self.assertEqual(item["posterior"], [])
        self.assertIsNone(item["forecast"])
        self.assertIsNone(body["selected_action"])

    def test_invalid_compiled_output_removed_before_prior(self):
        _, body = self.evaluate(c=context([2, 2]))
        item = body["menu"][0]
        self.assertEqual(len(item["concrete_predictions"]), 1)
        self.assertTrue(item["forecastable"])
        self.assertFalse(item["inquiry_eligible"])
        self.assertEqual([posterior["weight"] for posterior in item["posterior"]], [["1", "2"], ["1", "2"]])
        self.assertEqual(item["forecast"]["zero"], ["77", "120"])
        self.assertIsNone(body["selected_action"])

    def test_generator_exact_cap_and_complete_overflow_count(self):
        def many(count):
            return [row("D" + str(i), context(inventory=["i" + str(i)], visible=["v" + str(i)]), [0, i % 2]) for i in range(count)]
        at_cap, _ = self.evaluate(many(64))
        item = at_cap["actions"][0]
        self.assertEqual(item["conditional_count"], 128)
        self.assertEqual(item["retained_conditional_count"], 5)
        self.assertEqual(len(item["models"]), 8)
        beyond, body = self.evaluate(many(70))
        self.assertEqual(beyond["actions"][0]["conditional_count"], 140)
        self.assertEqual(beyond["actions"][0]["models"], [])
        self.assertEqual(body["menu"][0]["forecast_reason"], "generator_capacity_exhausted")

    def test_alternating_outcomes_raise_N_and_reduce_disagreement(self):
        first = self.evaluate()[1]["menu"][0]
        u = [row("noise" + str(i), context(), [0, i % 2]) for i in range(32)]
        _, body = self.evaluate(u=u)
        final = body["menu"][0]
        self.assertGreater(policy.parse_pair(final["unresolved_mass"]), Fraction(999, 1000))
        self.assertLess(Decimal(final["score_bits"]), Decimal(first["score_bits"]))
        self.assertGreater(Decimal(final["predictive_entropy_bits"]), Decimal("1.58"))
        self.assertIsNone(body["selected_action"])

    def test_contradiction_counts_unique_events_not_votes(self):
        u = [row("blocked", context(), [0, 0]), row("moved", context(), [0, 1])]
        _, body = self.evaluate(u=u)
        self.assertEqual(body["menu"][0]["evidence_event_ids"], ["blocked", "moved"])
        self.assertGreater(policy.parse_pair(body["menu"][0]["unresolved_mass"]), Fraction(1, 5))
        reverse = self.evaluate(u=list(reversed(u)))[1]
        self.assertEqual(numeric(body), numeric(reverse))

    def test_all_model_misspecification_leads_to_N_and_null(self):
        u = [row("other" + str(i), context(), [1, 0]) for i in range(9)]
        _, body = self.evaluate(u=u)
        item = body["menu"][0]
        self.assertGreater(policy.parse_pair(item["unresolved_mass"]), Fraction(999999, 1000000))
        self.assertIsNone(body["selected_action"])
        self.assertLess(Decimal(item["score_bits"]), policy.THRESHOLD)

    def test_retest_new_context_has_fresh_available_prior(self):
        u = [row("blocked" + str(i), context(), [0, 0]) for i in range(8)]
        _, previous = self.evaluate(u=u)
        changed = context(inventory=["new-object"])
        _, current = self.evaluate(c=changed, u=u)
        self.assertIsNone(previous["selected_action"])
        self.assertEqual(current["selected_action"], "north")
        self.assertEqual(current["menu"][0]["evidence_event_ids"], [])

    def test_four_equal_actions_movement_order_tie(self):
        d = sum((discovery(action) for action in policy.ACTIONS), [])
        _, body = self.evaluate(d)
        self.assertEqual(body["selected_action"], "north")
        self.assertEqual(len({item["score_bits"] for item in body["menu"]}), 1)

    def test_tie_tolerance_uses_global_max_not_pairwise_drift(self):
        menu = [{"action": action, "selection_eligible": True, "score_bits": score} for action, score in zip(
            policy.ACTIONS, ["0.200000000000000000", "0.200000000000900000", "0.200000000001800000", "0.100000000000000000"])]
        self.assertEqual(policy._choose(menu), "east")
        menu[2]["score_bits"] = "0.200000000001000000"
        self.assertEqual(policy._choose(menu), "north")
        menu[2]["score_bits"] = "0.200000000001000001"
        self.assertEqual(policy._choose(menu), "east")
        with localcontext() as external:
            external.prec = 6
            external.rounding = "ROUND_DOWN"
            self.assertEqual(policy._choose(menu), "east")

    def test_strict_threshold_and_half_even_18_digits(self):
        predictions = [{"model_id": "x", "position": [0, 0]}, {"model_id": "y", "position": [0, 1]}]
        distributions = [[Fraction(1, 3)] * 3] * 3
        for score, eligible in [("0.010000000000000000", False), ("0.010000000000000001", True)]:
            item = policy._menu_shell("north", "available")
            with patch.object(policy, "_information", return_value={"score_bits": score}):
                policy._finish_menu(item, predictions, distributions, [Fraction(1, 3)] * 3, [Fraction(1, 3)] * 3, [])
            self.assertEqual(item["selection_eligible"], eligible)
        self.assertEqual(policy._decimal(Decimal("0.1234567890123456785")), "0.123456789012345678")
        self.assertEqual(policy._decimal(Decimal("0.1234567890123456795")), "0.123456789012345680")
        self.assertEqual(policy._decimal(Decimal("-0.0000000000000000001")), "0.000000000000000000")

    def test_entropy_frozen_independent_of_process_decimal_context(self):
        expected = self.evaluate()[1]
        with localcontext() as external:
            external.prec = 6
            external.rounding = "ROUND_DOWN"
            again = self.evaluate()[1]
        self.assertEqual(expected, again)
        self.assertEqual(policy._decimal(policy._entropy([Fraction(1, 3)] * 3)), "1.584962500721156181")

    def test_rational_canonical_pairs_and_256_digits(self):
        self.assertEqual(policy.fraction_pair(Fraction(38, 40)), ["19", "20"])
        self.assertEqual(policy.parse_pair(["0", "1"]), 0)
        self.assertEqual(policy.parse_pair(["9" * 256, "1"]), int("9" * 256))
        for pair in (["2", "4"], ["-0", "1"], ["01", "2"], ["1", "-2"], ["1", "0"], ["1", "01"], ["9" * 257, "1"], [1, "2"]):
            with self.assertRaises(Conflict):
                policy.parse_pair(pair)
        with self.assertRaises(Conflict):
            policy.fraction_pair(Fraction(10 ** 256))

    def test_rational_overflow_returns_no_decision_and_no_mutation(self):
        cohort = policy.build_cohort(discovery())
        before = canonical(cohort)
        u = [row("many" + str(i), context(), [0, 0]) for i in range(200)]
        with self.assertRaisesRegex(Conflict, "rational_component_overflow"):
            policy.evaluate(cohort, context(), u)
        self.assertEqual(canonical(cohort), before)

    def test_exact_brier_endpoints(self):
        forecast = {"zero": ["1", "1"], "displacement": ["0", "1"], "other": ["0", "1"]}
        self.assertEqual(policy.brier_loss(forecast, "zero"), ["0", "1"])
        self.assertEqual(policy.brier_loss(forecast, "other"), ["1", "1"])
        self.assertEqual(policy.brier_loss({key: ["1", "3"] for key in policy.OUTCOMES}, "other"), ["1", "3"])
        with self.assertRaises(Conflict):
            policy.brier_loss({key: ["1", "1"] for key in policy.OUTCOMES}, "other")

    def test_all_input_objects_unchanged(self):
        d, c, u = discovery(), context(), [row("U", context(), [0, 0])]
        original = canonical([d, c, u])
        cohort, body = self.evaluate(d, c, u)
        copy = canonical([cohort, body])
        policy.verify_evaluation(d, c, u, body)
        self.assertEqual(canonical([d, c, u]), original)
        self.assertEqual(canonical([cohort, body]), copy)

    def test_verifier_is_independent_of_backend_producer_and_generator(self):
        d, c, u = discovery(), context(), [row("U", context(), [0, 0])]
        cohort, body = self.evaluate(d, c, u)
        forbidden = ["evaluate", "build_cohort", "_prediction", "_posterior", "_finish_menu", "_choose", "_model"]
        patches = [patch.object(policy, name, side_effect=AssertionError("producer called: " + name)) for name in forbidden]
        for controller in patches:
            controller.start()
        try:
            self.assertTrue(policy.verify_cohort(d, cohort))
            self.assertTrue(policy.verify_evaluation(d, c, u, body))
        finally:
            for controller in reversed(patches):
                controller.stop()

    def test_verifier_rejects_every_committed_selection_dimension(self):
        d, c = discovery(), context()
        _, body = self.evaluate(d, c)
        alterations = []
        def alteration(edit):
            item = deepcopy(body)
            edit(item)
            alterations.append(item)
        alteration(lambda x: x.update(selected_action="east"))
        alteration(lambda x: x["menu"].pop())
        alteration(lambda x: x["menu"][0].update(score_bits="0.999999999999999999"))
        alteration(lambda x: x["menu"][0]["posterior"][0].update(weight=["1", "2"]))
        alteration(lambda x: x["menu"][0]["forecast"].update(zero=["1", "1"]))
        alteration(lambda x: x["menu"][0]["concrete_predictions"][0].update(position=[2, 2]))
        alteration(lambda x: x["menu"][0]["concrete_predictions"][0].update(derivation_digest="f" * 64))
        alteration(lambda x: x["menu"][0].update(evidence_event_ids=["invented"]))
        alteration(lambda x: x["menu"][1].update(forecast_reason=None))
        alteration(lambda x: x.update(context_digest="f" * 64))
        for altered in alterations:
            with self.subTest(altered=altered):
                before = canonical(altered)
                with self.assertRaises(Conflict):
                    policy.verify_evaluation(d, c, [], altered)
                self.assertEqual(canonical(altered), before)

    def test_verifier_rejects_uncomplete_or_wrong_cohort_derivations(self):
        d = discovery()
        cohort = policy.build_cohort(d)
        for key in ("models", "derivation"):
            altered = deepcopy(cohort)
            if key == "models":
                altered["actions"][0]["models"].pop(2)
            else:
                altered["actions"][0]["models"][0]["derivation"]["branches"] = []
            altered["cohort_digest"] = digest({k: v for k, v in altered.items() if k != "cohort_digest"})
            with self.assertRaises(Conflict):
                policy.verify_cohort(d, altered)

    def test_strict_projection_rejects_callbacks_private_fields_and_invalid_positions(self):
        for private in ("_kind", "appearance", "source_label", "cycle", "cached_weights", "transition"):
            c = context()
            c[private] = "forbidden"
            with self.assertRaises(Conflict):
                policy.evaluate(policy.build_cohort(discovery()), c, [])
        for malformed in (lambda: [], (), {"position": [True, 0]}, {"position": [3, 0]}, {"visible_ids": ["duplicate", "duplicate"]}):
            with self.assertRaises(Conflict):
                policy.normalize_context(malformed)
        malformed_row = row("bad", context(), [0, 0])
        malformed_row["refs"] = {"before": "fake", "receipt": "fake", "after": "fake"}
        with self.assertRaises(Conflict):
            policy.build_cohort([malformed_row])


if __name__ == "__main__":
    unittest.main()
