"""Zero-simulator, hand-authored saved-JSON/arithmetic tests only.

These fixtures are software checks, never scientific anchors, D/U/E1 streams,
simulator probes, or study results. Loading scorer.py directly avoids importing
any research package initializer or its execution dependency closure.
"""

import ast
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCORER_PATH = Path(__file__).resolve().parents[1] / "ora_study" / "scorer.py"
SPEC = importlib.util.spec_from_file_location("isolated_saved_study_scorer", SCORER_PATH)
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def q(n, d=1):
    """Fixture serialization, not an arithmetic oracle."""
    value = Fraction(n, d)
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def seal(value):
    # Deliberately independent of scorer.digest; the contract fixes these bytes.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


# A manually specified common public context and probability example. No source
# observation, hidden state, simulation, rule generator, or selector is used.
CONTEXT = json.loads('''{"position":[0,0],"inventory_ids":[],"visible_ids":[]}''')
FORECAST = json.loads('''{
 "status":"available",
 "probabilities":[{"numerator":"157","denominator":"360"},
                  {"numerator":"157","denominator":"360"},
                  {"numerator":"23","denominator":"180"}],
 "nonzero_delta":[1,0],
 "concrete_predictions":[{"model_id":"stationary","position":[0,0]},
                         {"model_id":"moving","position":[1,0]}],
 "posterior":[{"model_id":"stationary","weight":{"numerator":"1","denominator":"3"}},
              {"model_id":"moving","weight":{"numerator":"1","denominator":"3"}},
              {"model_id":"N","weight":{"numerator":"1","denominator":"3"}}],
 "unresolved_mass":{"numerator":"1","denominator":"3"},
 "local_u_count":0,"local_e1_count":0,"information_bits":"0.800000000000000000",
 "inquiry_eligible":true,
 "cohort_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
 "formation":{"source":"hand-authored software fixture","concrete_retained":2}
}''')
TRANSITION = json.loads('''{
 "command":{"action":"north"},
 "before_observation":{"world_version":"public-fixture-v1","observation_id":"owc-000032",
   "cycle":32,"position":[0,0],"inventory_ids":[],"visible_entities":[]},
 "receipt":{"id":"OWC-A000033","cycle":33,"action":"north","target":null,
   "direction":null,"before":[0,0],"after":[0,0],"success":false,"blocked":true,
   "observed_effects":["Stayed in place"],"visible_entity_states":{}},
 "after_observation":{"world_version":"public-fixture-v1","observation_id":"owc-000033",
   "cycle":33,"position":[0,0],"inventory_ids":[],"visible_entities":[]},
 "hashes":{},"invoked_seq":6,"durable_seq":7
}''')


def transition(direction="north", invoked=6):
    value = deepcopy(TRANSITION)
    value["command"]["action"] = direction
    value["receipt"]["action"] = direction
    value["invoked_seq"], value["durable_seq"] = invoked, invoked+1
    rehash_transition(value)
    return value


def rehash_transition(value):
    value["hashes"] = {name: seal(value[name]) for name in
        ("command", "before_observation", "receipt", "after_observation")}


def stage(case_id, number, committed):
    value = {
        "t1": {"semantic": {"context": deepcopy(CONTEXT), "cohort_sha256": "a"*64,
            "forecasts": {direction: deepcopy(FORECAST) for direction in
                          ("north", "east", "south", "west")},
            "selection": {"command": None, "owner": None, "null_reason": "fixture null"},
            "lifecycle": {"decision": number}, "view_evidence": {"fixture": True}},
            "provenance": {"case_id": case_id, "decision_id": str(number), "run_id": case_id},
            "sha256": "", "committed_seq": committed}, "outcome": None, "t3": None}
    value["t1"]["sha256"] = seal(value["t1"]["semantic"])
    return value


def anchor():
    """Assemble two copies of the literal software fixture, without execution."""
    value = {"layout": 1, "neutral_t": 32, "initial_observation": deepcopy(TRANSITION["before_observation"]),
             "c0": deepcopy(CONTEXT), "c1": deepcopy(CONTEXT),
             "cases": {}, "forecast_set": {"commands": ["north", "east", "south", "west"],
                "basis": "D/current_C1", "context_sha256": seal(CONTEXT),
                "cohort_sha256": "a"*64, "committed_seq": 5},
             "probes": {d: transition(d, 6+2*i) for i, d in
                        enumerate(("north", "east", "south", "west"))}}
    for arm, first_seq, second_seq in (("R", 1, 3), ("W", 2, 4)):
        case_id = "fixture-1-32-" + arm
        value["cases"][arm] = {"case_id": case_id,
            "stages": {"1": stage(case_id, 1, first_seq), "2": stage(case_id, 2, second_seq)}}
    value["forecast_set"]["sha256"] = seal(value["forecast_set"])
    return value


def payload(include_anchor=True):
    # Registry is prospective slot metadata only. This does not create 32
    # observations, anchors, outcomes, or any scientific evidence.
    registry = [{"layout": layout, "neutral_t": t,
        "cases": {arm: f"fixture-{layout}-{t}-{arm}" for arm in ("R", "W")}}
        for layout in (1, 2, 3, 4) for t in (32, 36, 40, 44, 48, 52, 56, 60)]
    values = {name: {"known": 0, "unknown": False} for name in scorer.COUNTER_NAMES}
    if include_anchor:
        for name in ("decisions_started", "decisions_committed", "probe_invocations", "probe_durable"):
            values[name]["known"] = 4
    return {"schema_version": "ora.frozen-study.saved.v1", "data_kind": "synthetic_fixture",
        "terminal_state": "resource_interrupted", "freeze": deepcopy(scorer.DOCUMENT_HASHES),
        "registry": registry, "anchors": [anchor()] if include_anchor else [],
        "gates": {name: {"status": "pass", "evidence_sha256": "b"*64} for name in scorer.GATE_NAMES},
        "counters": values, "resources": {"cpu_seconds": q(0), "wall_seconds": q(0), "persisted_bytes": 0},
        "formation": {"fixture": True}, "terminal_detail": {"phase": "software fixture", "reason": "not a run"}}


def reseal_stages(value):
    for case in value["cases"].values():
        for decision in case["stages"].values():
            decision["t1"]["sha256"] = seal(decision["t1"]["semantic"])


def add_t3(decision, sequence):
    semantic = {"fixture_verdict": "one matches, one contradicts"}
    decision["t3"] = {"semantic": semantic, "sha256": seal(semantic),
                       "completed_seq": sequence, "outcome_sha256": seal(decision["outcome"])}


def owned_payload():
    """Literal blocked-move example assembled for receipt-link mutation tests."""
    value = payload()
    a = value["anchors"][0]
    for arm, invocation, completion in (("R", 3, 5), ("W", 6, 8)):
        first = a["cases"][arm]["stages"]["1"]
        first["t1"]["semantic"]["selection"] = {"command":"north", "owner":"north-inquiry", "null_reason":None}
        first["outcome"] = transition("north", invocation)
        add_t3(first, completion)
        a["cases"][arm]["stages"]["2"]["t1"]["committed_seq"] = 9 if arm == "R" else 10
    r_second = a["cases"]["R"]["stages"]["2"]
    north = r_second["t1"]["semantic"]["forecasts"]["north"]
    # Independent hand arithmetic: posterior 114:3:40; mixture numerator
    # 14605:2284:1951 over 18840, obtained from frozen 38/40,1/40,1/3.
    north["posterior"] = [{"model_id":"stationary", "weight":q(114,157)},
                           {"model_id":"moving", "weight":q(3,157)},
                           {"model_id":"N", "weight":q(40,157)}]
    north["unresolved_mass"] = q(40,157)
    north["probabilities"] = [q(2921,3768), q(571,4710), q(1951,18840)]
    north["local_e1_count"] = 1
    r_second["t1"]["semantic"]["selection"] = {"command":"north", "owner":"north-second", "null_reason":None}
    r_second["outcome"] = transition("north", 12)
    a["forecast_set"]["committed_seq"] = 11
    a["forecast_set"]["sha256"] = seal({k:v for k,v in a["forecast_set"].items() if k != "sha256"})
    a["probes"] = {d: transition(d, 15+2*i) for i,d in enumerate(("north", "east", "south", "west"))}
    for event in [r_second["outcome"], *a["probes"].values()]:
        event["before_observation"].update(cycle=33, observation_id="owc-000033")
        event["after_observation"].update(cycle=34, observation_id="owc-000034")
        event["receipt"].update(cycle=34, id="OWC-A000034")
        rehash_transition(event)
    add_t3(r_second, 14)
    reseal_stages(a)
    for name in ("owned_invocations", "owned_durable"):
        value["counters"][name]["known"] = 3
    return value


def copy_fixture_slot(source, layout, neutral_t, inventory, seq_offset):
    """Remap a software fixture's identity and public text; never invoke a world."""
    result = deepcopy(source)
    result.update(layout=layout, neutral_t=neutral_t)
    for context in (result["c0"], result["c1"]):
        context["inventory_ids"] = list(inventory)
    result["initial_observation"]["inventory_ids"] = list(inventory)
    for arm, case in result["cases"].items():
        case_id = f"fixture-{layout}-{neutral_t}-{arm}"
        case["case_id"] = case_id
        for decision in case["stages"].values():
            decision["t1"]["provenance"].update(case_id=case_id, run_id=case_id)
            decision["t1"]["committed_seq"] += seq_offset
            decision["t1"]["semantic"]["context"]["inventory_ids"] = list(inventory)
    for event in result["probes"].values():
        for frame in (event["before_observation"], event["after_observation"]):
            frame["inventory_ids"] = list(inventory)
        event["invoked_seq"] += seq_offset
        event["durable_seq"] += seq_offset
        rehash_transition(event)
    commitment = result["forecast_set"]
    commitment["committed_seq"] += seq_offset
    commitment["context_sha256"] = seal(result["c1"])
    commitment["sha256"] = seal({k:v for k,v in commitment.items() if k != "sha256"})
    reseal_stages(result)
    return result


class ExactArithmeticTests(unittest.TestCase):
    def test_brier_independent_integer_oracles(self):
        cases = [([q(1), q(0), q(0)], 0, Fraction(0)),
                 ([q(1), q(0), q(0)], 1, Fraction(1)),
                 ([q(1, 3), q(1, 3), q(1, 3)], 2, Fraction(1, 3)),
                 ([q(1, 2), q(1, 3), q(1, 6)], 0, Fraction(7, 36)),
                 # Explicit integer squares: (203^2 + 157^2 + 46^2)/(2*360^2).
                 (FORECAST["probabilities"], 0, Fraction(11329, 43200))]
        for probabilities, actual, expected in cases:
            with self.subTest(probabilities=probabilities, actual=actual):
                self.assertEqual(scorer.brier_score(probabilities, actual), expected)

    def test_noncanonical_or_unbounded_rationals_rejected(self):
        for value in ({"numerator":"01","denominator":"2"},
                      {"numerator":"2","denominator":"4"},
                      {"numerator":"0","denominator":"2"},
                      {"numerator":"-0","denominator":"1"},
                      {"numerator":"1","denominator":"0"},
                      {"numerator":"1","denominator":"-2"},
                      {"numerator":1,"denominator":"2"},
                      {"numerator":"1"*257,"denominator":"1"}):
            with self.subTest(value=value), self.assertRaises(scorer.SavedDataError):
                scorer.rational(value)

    def test_invalid_probability_vectors_rejected(self):
        for probabilities in ([q(1), q(1), q(0)], [q(-1), q(1), q(1)],
                              [q(1), q(0)], [0.5, 0.5, 0.0]):
            with self.subTest(probabilities=probabilities), self.assertRaises(scorer.SavedDataError):
                scorer.brier_score(probabilities, 0)

    def test_outcome_class_uses_displacement_not_success(self):
        value = transition()
        value["receipt"]["success"] = True
        self.assertEqual(scorer.outcome_class(value, [1, 0]), 0)
        value["after_observation"]["position"] = [1, 0]
        self.assertEqual(scorer.outcome_class(value, [1, 0]), 1)
        value["after_observation"]["position"] = [0, 1]
        self.assertEqual(scorer.outcome_class(value, [1, 0]), 2)

    def test_mirrors_preserve_ids_states_and_transform_entities(self):
        a = {"position": [2, -1], "inventory_ids": ["inventory-z"], "visible_ids": ["opaque-a"],
             "entity.opaque-a.position": [3, -1], "entity.opaque-a.state": "closed"}
        b = deepcopy(a)
        b["position"], b["entity.opaque-a.position"] = [-2, 1], [-3, 1]
        self.assertEqual(scorer.mirror_context_key(a), scorer.mirror_context_key(b))
        b["entity.opaque-a.state"] = "open"
        self.assertNotEqual(scorer.mirror_context_key(a), scorer.mirror_context_key(b))
        c = {"position": [2, -1], "inventory_ids": ["inventory-z"], "visible_ids": ["opaque-b"],
             "entity.opaque-b.position": [3, -1], "entity.opaque-b.state": "closed"}
        self.assertNotEqual(scorer.mirror_context_key(a), scorer.mirror_context_key(c))

    def test_derived_scores_can_exceed_input_digit_limit(self):
        denominator = 10**255 + 7
        probabilities = [q(1, denominator), q(denominator-1, denominator), q(0)]
        result = scorer.brier_score(probabilities, 0)
        # Exact identity: half((1-p)^2 + (1-p)^2) = (1-p)^2.
        self.assertEqual(result, Fraction((denominator-1)**2, denominator**2))
        encoded = scorer.fraction_json(result)
        self.assertGreater(len(encoded["denominator"]), 256)
        self.assertEqual(scorer._derived_fraction(encoded), result)
        # No change to Python's process-global integer-string security guard.
        enormous = Fraction(10**5000 + 1, 10**5001 + 3)
        self.assertEqual(scorer._derived_fraction(scorer.fraction_json(enormous)), enormous)


class ClassificationTests(unittest.TestCase):
    def classify(self, **updates):
        values = {"invalid": False, "interrupted": False, "adverse": False,
            "coverage": True, "denominators_available": True, "benefit": Fraction(1, 20),
            "choice_differences": 4, "choice_context_groups": 2, "discriminating_differences": 4}
        values.update(updates)
        return scorer.classify(**values)

    def test_frozen_order_and_exact_thresholds(self):
        self.assertEqual(self.classify(invalid=True, interrupted=True, adverse=True), scorer.INVALID)
        self.assertEqual(self.classify(interrupted=True, adverse=True), scorer.INCOMPLETE)
        self.assertEqual(self.classify(adverse=True, coverage=False), scorer.ADVERSE)
        self.assertEqual(self.classify(coverage=False), scorer.INCONCLUSIVE)
        self.assertEqual(self.classify(denominators_available=False), scorer.INCONCLUSIVE)
        self.assertEqual(self.classify(benefit=None), scorer.INCONCLUSIVE)
        self.assertEqual(self.classify(benefit=Fraction(49, 1000)), scorer.NO_BENEFIT)
        self.assertEqual(self.classify(benefit=Fraction(0)), scorer.NO_BENEFIT)
        self.assertEqual(self.classify(choice_differences=3), scorer.PREDICTIVE_ONLY)
        self.assertEqual(self.classify(choice_context_groups=1), scorer.PREDICTIVE_ONLY)
        self.assertEqual(self.classify(discriminating_differences=3), scorer.PREDICTIVE_ONLY)
        self.assertEqual(self.classify(), scorer.FULL_PASS)


class SavedReportingTests(unittest.TestCase):
    def assert_invalid(self, value, reason):
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INVALID, report["errors"])
        self.assertTrue(any(reason in error for error in report["errors"]), report["errors"])
        self.assertEqual(report["saved_input"], value)
        return report

    def test_partial_rows_and_exact_fixture_denominators_preserved(self):
        value = payload()
        original = deepcopy(value)
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertEqual(value, original)
        self.assertEqual(report["saved_input"], original)
        self.assertIsNone(report["scientific_result"])
        self.assertIsNone(report["scientific_denominators"])
        counts = report["fixture_denominators"]
        self.assertEqual(counts["validated_anchors"], 1)
        self.assertEqual(counts["observed_saved_rows"]["decisions_committed"], 4)
        self.assertEqual(counts["observed_saved_rows"]["forecast_rows"], 16)
        self.assertEqual(counts["scored_common_actions"], 4)
        self.assertEqual(report["context_balanced"]["loss_R"], q(11329, 43200))
        self.assertEqual(report["context_balanced"]["benefit_W_minus_R"], q(0))
        self.assertEqual(report["per_layout"]["1"]["denominator"], 1)
        self.assertIsNone(report["per_layout"]["2"]["loss_R"])

    def test_empty_interruption_keeps_zero_and_unknown_separate(self):
        value = payload(False)
        for gate in value["gates"].values():
            gate.update(status="not_reached", evidence_sha256=None)
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertEqual(report["fixture_denominators"]["observed_saved_rows"]["anchors"], 0)
        self.assertIsNone(report["context_balanced"]["loss_R"])
        value["counters"]["owned_durable"] = {"known": 3, "unknown": True}
        report = self.assert_invalid(value, "unknown remainder")
        self.assertEqual(report["counters"]["owned_durable"], {"known": 3, "unknown": True})

    def test_registry_32_anchors_64_unique_cases_is_mandatory(self):
        value = payload()
        value["registry"].pop()
        self.assert_invalid(value, "exactly 32 anchors")
        value = payload()
        value["registry"][1]["cases"]["R"] = value["registry"][0]["cases"]["R"]
        self.assert_invalid(value, "duplicate arm case ID")
        value = payload()
        value["registry"][0]["neutral_t"] = 31
        self.assert_invalid(value, "unexpected anchor")

    def test_complete_claim_cannot_turn_missing_rows_into_samples(self):
        value = payload()
        value["terminal_state"] = "complete"
        report = self.assert_invalid(value, "omits scheduled anchor")
        self.assertEqual(report["fixture_denominators"]["observed_saved_rows"]["decisions_committed"], 4)
        self.assertEqual(report["fixed_schedule_not_observed_counts"]["decisions"], 128)

    def test_missing_forecast_is_integrity_failure_even_on_interruption(self):
        value = payload()
        del value["anchors"][0]["cases"]["R"]["stages"]["1"]["t1"]["semantic"]["forecasts"]["west"]
        reseal_stages(value["anchors"][0])
        self.assert_invalid(value, "omitted or extra movement forecast")

    def test_first_stage_equality_ignores_only_explicit_provenance(self):
        value = payload()
        stage_r = value["anchors"][0]["cases"]["R"]["stages"]["1"]
        stage_r["t1"]["provenance"]["run_id"] = "different-local-run"
        self.assertEqual(scorer.score_saved_study(value)["classification"], scorer.INCOMPLETE)
        stage_r["t1"]["semantic"]["view_evidence"]["different"] = True
        reseal_stages(value["anchors"][0])
        self.assert_invalid(value, "first-stage arms differ")

    def test_first_null_requires_second_equality(self):
        value = payload()
        value["anchors"][0]["cases"]["W"]["stages"]["2"]["t1"]["semantic"]["view_evidence"]["leak"] = True
        reseal_stages(value["anchors"][0])
        self.assert_invalid(value, "first-null pair differs")

    def test_different_null_reasons_do_not_count_as_changed_tests(self):
        value=owned_payload()
        second=value["anchors"][0]["cases"]["R"]["stages"]["2"]
        second["t1"]["semantic"]["selection"]={"command":None,"owner":None,"null_reason":"authored distinct capacity explanation"}
        second["outcome"]=None
        second["t3"]=None
        for name in ("owned_invocations","owned_durable"):
            value["counters"][name]["known"]=2
        reseal_stages(value["anchors"][0])
        report=scorer.score_saved_study(value)
        self.assertEqual(report["classification"],scorer.INCOMPLETE,report["errors"])
        self.assertFalse(report["anchors"][0]["choice_difference"])
        self.assertTrue(report["anchors"][0]["null_reason_difference"])
        self.assertEqual(report["coverage"]["choice_difference_contexts"],0)

    def test_owned_outcome_chain_scores_once_against_common_probe(self):
        value = owned_payload()
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        row = report["anchors"][0]
        self.assertTrue(row["local_e1_in_F"])
        self.assertTrue(row["choice_difference"])
        self.assertTrue(row["R_distinguishes_on_difference"])
        self.assertEqual(len(row["actions"]), 4)
        self.assertEqual(len(row["first_owned_scores"]), 2)
        self.assertEqual(report["fixture_denominators"]["scored_common_actions"], 4)
        self.assertEqual(report["fixture_denominators"]["observed_saved_rows"]["owned_outcomes"], 3)

    def test_changed_first_context_remains_scored_with_no_E1_update(self):
        value = owned_payload()
        a = value["anchors"][0]
        a["c1"]["position"] = [1,0]
        for arm, case in a["cases"].items():
            first = case["stages"]["1"]
            first["outcome"]["after_observation"]["position"] = [1,0]
            first["outcome"]["receipt"].update(after=[1,0], success=True, blocked=False)
            rehash_transition(first["outcome"])
            add_t3(first, first["t3"]["completed_seq"])
            second = case["stages"]["2"]
            second["t1"]["semantic"]["context"] = deepcopy(a["c1"])
            for direction in ("north","east","south","west"):
                row = deepcopy(FORECAST)
                row["concrete_predictions"][0]["position"] = [1,0]
                row["concrete_predictions"][1]["position"] = [2,0]
                second["t1"]["semantic"]["forecasts"][direction] = row
        r_second = a["cases"]["R"]["stages"]["2"]
        for event in [r_second["outcome"], *a["probes"].values()]:
            event["before_observation"]["position"] = [1,0]
            event["after_observation"]["position"] = [1,0]
            event["receipt"].update(before=[1,0],after=[1,0])
            rehash_transition(event)
        add_t3(r_second, 14)
        a["forecast_set"]["context_sha256"] = seal(a["c1"])
        a["forecast_set"]["sha256"] = seal({k:v for k,v in a["forecast_set"].items() if k != "sha256"})
        reseal_stages(a)
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertFalse(report["anchors"][0]["local_e1_in_F"])
        self.assertEqual(report["fixture_denominators"]["scored_common_actions"], 4)
        self.assertEqual(report["context_balanced"]["benefit_W_minus_R"], q(0))

    def test_other_outcomes_and_adverse_prediction_stay_visible(self):
        value = owned_payload()
        a = value["anchors"][0]
        r_second = a["cases"]["R"]["stages"]["2"]
        for event in (r_second["outcome"], a["probes"]["north"]):
            event["after_observation"]["position"] = [0,1]
            event["receipt"].update(after=[0,1],success=True,blocked=False)
            rehash_transition(event)
        add_t3(r_second, 14)
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertEqual(report["fixture_denominators"]["other_common_outcomes"], 1)
        self.assertFalse(report["anchors"][0]["R_distinguishes_on_difference"])
        self.assertTrue(report["coverage"]["evaluable_layout_guard_breached"])

    def test_both_first_commits_must_precede_either_first_effect(self):
        value = owned_payload()
        value["anchors"][0]["cases"]["W"]["stages"]["1"]["t1"]["committed_seq"] = 4
        self.assert_invalid(value, "first effect precedes both")

    def test_both_first_lifecycles_must_precede_either_second_T1(self):
        value = owned_payload()
        value["anchors"][0]["cases"]["R"]["stages"]["2"]["t1"]["committed_seq"] = 6
        self.assert_invalid(value, "second T1 precedes both completed first lifecycles")

    def test_missing_peer_T1_cannot_hide_an_early_effect(self):
        value = owned_payload()
        del value["anchors"][0]["cases"]["W"]["stages"]["1"]
        self.assert_invalid(value, "first effect without both")

    def test_owned_second_must_match_full_common_probe(self):
        value = owned_payload()
        event = value["anchors"][0]["probes"]["north"]
        event["receipt"]["observed_effects"] = ["Different public outcome"]
        rehash_transition(event)
        self.assert_invalid(value, "second owned outcome differs")

    def test_same_context_is_not_enough_for_full_frame_continuity(self):
        value = owned_payload()
        probe = value["anchors"][0]["probes"]["east"]
        for frame in (probe["before_observation"], probe["after_observation"]):
            frame["world_version"] = "foreign-public-world"
        rehash_transition(probe)
        self.assert_invalid(value, "full post-first frame")

    def test_T3_binds_actual_outcome_and_withheld_E1_stays_zero(self):
        value = owned_payload()
        value["anchors"][0]["cases"]["R"]["stages"]["1"]["t3"]["outcome_sha256"] = "0"*64
        self.assert_invalid(value, "T3 does not bind")
        value = owned_payload()
        a = value["anchors"][0]
        a["cases"]["W"]["stages"]["2"]["t1"]["semantic"]["forecasts"]["north"]["local_e1_count"] = 1
        reseal_stages(a)
        self.assert_invalid(value, "wrong retained/withheld local E1")

    def test_probabilities_bind_complete_posterior(self):
        value = payload()
        row = value["anchors"][0]["cases"]["R"]["stages"]["1"]["t1"]["semantic"]["forecasts"]["north"]
        row["probabilities"] = [q(1, 3)]*3
        reseal_stages(value["anchors"][0])
        self.assert_invalid(value, "mixture/posterior mismatch")

    def test_cohort_hash_binds_each_row_and_one_D_per_layout(self):
        value = payload()
        value["anchors"][0]["cases"]["R"]["stages"]["1"]["t1"]["semantic"]["forecasts"]["north"]["cohort_sha256"] = "c"*64
        reseal_stages(value["anchors"][0])
        self.assert_invalid(value, "forecast cohort differs")
        value = payload()
        another = copy_fixture_slot(value["anchors"][0], 1, 36, [], 20)
        for case in another["cases"].values():
            for decision in case["stages"].values():
                semantic = decision["t1"]["semantic"]
                semantic["cohort_sha256"] = "c"*64
                for row in semantic["forecasts"].values():
                    row["cohort_sha256"] = "c"*64
        reseal_stages(another)
        value["anchors"].append(another)
        self.assert_invalid(value, "frozen D cohort differs within layout")

    def test_valid_mixture_cannot_hide_wrong_eligible_E1_update(self):
        value = owned_payload()
        a = value["anchors"][0]
        north = a["cases"]["R"]["stages"]["2"]["t1"]["semantic"]["forecasts"]["north"]
        north.update(posterior=deepcopy(FORECAST["posterior"]),
                     probabilities=deepcopy(FORECAST["probabilities"]),
                     unresolved_mass=deepcopy(FORECAST["unresolved_mass"]))
        reseal_stages(a)
        self.assert_invalid(value, "not exact common-U plus eligible E1 update")

    def test_ineligible_action_cannot_change_posterior(self):
        value = owned_payload()
        a = value["anchors"][0]
        rows = a["cases"]["R"]["stages"]["2"]["t1"]["semantic"]["forecasts"]
        rows["east"] = deepcopy(rows["north"])
        rows["east"]["local_e1_count"] = 0
        reseal_stages(a)
        self.assert_invalid(value, "ineligible E1 changed arm posterior")

    def test_large_derived_fractions_survive_complete_reporting_path(self):
        value = payload()
        denominator = 10**250 + 7
        a = value["anchors"][0]
        for case in a["cases"].values():
            for decision in case["stages"].values():
                for row in decision["t1"]["semantic"]["forecasts"].values():
                    row["posterior"] = [{"model_id":"stationary", "weight":q(1,denominator)},
                        {"model_id":"moving", "weight":q(denominator-2,denominator)},
                        {"model_id":"N", "weight":q(1,denominator)}]
                    row["unresolved_mass"] = q(1,denominator)
                    row["probabilities"] = [q(3*denominator+148,120*denominator),
                        q(114*denominator-185,120*denominator), q(3*denominator+37,120*denominator)]
        reseal_stages(a)
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertGreater(len(report["context_balanced"]["loss_R"]["denominator"]), 256)

    def test_invalid_sibling_does_not_erase_supplied_row_counts(self):
        value = payload()
        value["anchors"][0]["cases"]["R"]["stages"]["1"]["t1"]["semantic"] = {}
        report = self.assert_invalid(value, "cohort_sha256")
        self.assertEqual(report["fixture_denominators"]["observed_saved_rows"]["decisions_committed"], 4)
        self.assertEqual(report["fixture_denominators"]["observed_saved_rows"]["probes"], 4)

    def test_forecast_set_cannot_be_outcome_selected(self):
        value = payload()
        commitment = value["anchors"][0]["forecast_set"]
        commitment["commands"].pop()
        commitment["sha256"] = seal({k:v for k,v in commitment.items() if k != "sha256"})
        self.assert_invalid(value, "not exactly common pre-outcome availability")
        value = payload()
        commitment = value["anchors"][0]["forecast_set"]
        commitment["committed_seq"] = 100
        commitment["sha256"] = seal({k:v for k,v in commitment.items() if k != "sha256"})
        self.assert_invalid(value, "probe preview")

    def test_outcome_selected_unavailable_reason_rejects(self):
        value = payload()
        row = value["anchors"][0]["cases"]["R"]["stages"]["1"]["t1"]["semantic"]["forecasts"]
        row["north"] = {"status": "unavailable", "reason": "prediction was wrong"}
        reseal_stages(value["anchors"][0])
        self.assert_invalid(value, "outcome-selected exclusion")

    def test_F_empty_is_unavailable_never_zero(self):
        value = payload()
        a = value["anchors"][0]
        for case in a["cases"].values():
            for decision in case["stages"].values():
                decision["t1"]["semantic"]["forecasts"] = {d: {"status": "unavailable",
                    "reason": "generator_capacity_exhausted"} for d in ("north", "east", "south", "west")}
        reseal_stages(a)
        a["forecast_set"]["commands"] = []
        a["forecast_set"]["sha256"] = seal({k:v for k,v in a["forecast_set"].items() if k != "sha256"})
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertEqual(report["fixture_denominators"]["F_empty_anchors"], 1)
        self.assertIsNone(report["anchors"][0]["loss_R"])
        self.assertIsNone(report["context_balanced"]["loss_R"])
        self.assertEqual(report["fixture_denominators"]["observed_saved_rows"]["probes"], 4)

    def test_receipt_frame_hash_and_absent_position_fail_closed(self):
        for mutate, expected in (
            (lambda p: p["receipt"].update(after=[7, 8]), "position mismatch"),
            (lambda p: p["hashes"].update(receipt="0"*64), "receipt hash mismatch"),
            (lambda p: p["after_observation"].pop("position"), "public observation"),
            (lambda p: p["receipt"].update(action="east"), "receipt/command mismatch")):
            value = payload()
            mutate(value["anchors"][0]["probes"]["north"])
            with self.subTest(expected=expected):
                self.assert_invalid(value, expected)

    def test_partial_missing_probe_does_not_shrink_anchor_denominator(self):
        value = payload()
        del value["anchors"][0]["probes"]["north"]
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertEqual(len(report["anchors"][0]["actions"]), 3)
        self.assertIsNone(report["anchors"][0]["loss_R"])
        self.assertIsNone(report["context_balanced"]["loss_R"])
        self.assertEqual(report["fixture_denominators"]["expected_commands_in_F"], 4)

    def test_global_invocations_and_forbidden_work_are_separate(self):
        value = payload()
        value["counters"]["neutral_invocations"]["known"] = 509
        self.assert_invalid(value, "invocation ceiling")
        value = payload()
        value["counters"]["core_cycles"]["known"] = 1
        self.assert_invalid(value, "forbidden work")

    def test_unknown_counters_preserve_other_known_counts(self):
        value = payload()
        value["counters"]["neutral_durable"] = {"known": 17, "unknown": True}
        value["counters"]["neutral_invocations"]["known"] = 18
        report = self.assert_invalid(value, "unknown remainder")
        self.assertEqual(report["counters"], value["counters"])
        self.assertEqual(report["fixture_denominators"]["scored_common_actions"], 4)

    def test_independent_layout_guard_exact_boundary(self):
        # Direct reporting arithmetic gives loss regression exactly 1/40 or
        # 1/40 + 1/10000. The comparison itself is strict, as frozen.
        for difference, adverse in ((Fraction(1, 40), False), (Fraction(251, 10000), True)):
            summary = scorer._loss_summary([{"loss_R": Fraction(1, 3)+difference,
                "loss_W": Fraction(1, 3), "_actions": []}])
            observed = scorer.rational(summary["loss_R"])-scorer.rational(summary["loss_W"])
            self.assertEqual(observed > Fraction(1, 40), adverse)

    def test_raw_anchor_and_action_micro_use_different_explicit_denominators(self):
        rows = [{"loss_R": Fraction(0), "loss_W": Fraction(1, 2),
                 "_actions": [{"loss_R":Fraction(0),"loss_W":Fraction(1, 2)}]},
                {"loss_R": Fraction(1), "loss_W": Fraction(0),
                 "_actions": [{"loss_R":Fraction(1),"loss_W":Fraction(0)}]*3},
                {"loss_R": None, "loss_W": None, "_actions": []}]
        mean = scorer._loss_summary(rows)
        micro = scorer._loss_summary(rows, True)
        self.assertEqual(mean["loss_R"], q(1, 2))
        self.assertEqual(micro["loss_R"], q(3, 4))
        self.assertEqual(mean["denominator"], 2)
        self.assertEqual(micro["denominator"], 4)
        self.assertEqual(mean["anchors_unavailable"], 1)

    def test_context_balance_weights_contexts_not_repeated_anchors(self):
        value = payload()
        first = value["anchors"][0]
        second = copy_fixture_slot(first, 1, 36, [], 20)
        third = copy_fixture_slot(first, 2, 32, ["another-context"], 40)
        for case in second["cases"].values():
            for decision in case["stages"].values():
                for row in decision["t1"]["semantic"]["forecasts"].values():
                    row["posterior"] = [{"model_id":"stationary", "weight":q(1,2)},
                        {"model_id":"moving", "weight":q(1,4)}, {"model_id":"N", "weight":q(1,4)}]
                    row["unresolved_mass"] = q(1,4)
                    row["probabilities"] = [q(271,480), q(1,3), q(49,480)]
        reseal_stages(second)
        value["anchors"] = [first, second, third]
        for name in ("decisions_started", "decisions_committed", "probe_invocations", "probe_durable"):
            value["counters"][name]["known"] = 12
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        first_loss, second_loss = Fraction(11329,43200), Fraction(11947,76800)
        self.assertEqual(report["context_balanced"]["loss_R"], q((3*first_loss+second_loss)/4))
        self.assertEqual(report["raw_anchor_mean"]["loss_R"], q((2*first_loss+second_loss)/3))
        self.assertEqual(report["context_balanced"]["context_denominator"], 2)
        self.assertEqual(sorted(c["denominator"] for c in report["per_context"]), [1,2])

    def test_zero_evaluable_context_denominator_is_visible(self):
        value = payload()
        missing = copy_fixture_slot(value["anchors"][0], 2, 32, ["unavailable-context"], 20)
        for case in missing["cases"].values():
            for decision in case["stages"].values():
                decision["t1"]["semantic"]["forecasts"] = {d: {"status":"unavailable",
                    "reason":"no_available_concrete_models"} for d in ("north","east","south","west")}
        reseal_stages(missing)
        missing["forecast_set"]["commands"] = []
        missing["forecast_set"]["sha256"] = seal({k:v for k,v in missing["forecast_set"].items() if k != "sha256"})
        value["anchors"].append(missing)
        for name in ("decisions_started", "decisions_committed", "probe_invocations", "probe_durable"):
            value["counters"][name]["known"] = 8
        report = scorer.score_saved_study(value)
        self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        self.assertEqual(report["context_balanced"]["unavailable_context_denominators"], 1)
        self.assertFalse(report["coverage"]["required_denominators_available"])

    def test_json_reader_rejects_duplicate_keys_floats_and_nan(self):
        for source in ('{"x":1,"x":2}', '{"x":0.5}', '{"x":NaN}'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "fixture.json"
                path.write_text(source, encoding="utf-8")
                with self.assertRaises(scorer.SavedDataError):
                    scorer.load_saved_json(path)

    def test_saved_json_readback_reports_without_world_imports(self):
        value = payload()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            report = scorer.score_saved_study(scorer.load_saved_json(path))
            self.assertEqual(report["classification"], scorer.INCOMPLETE, report["errors"])
        tree = ast.parse(SCORER_PATH.read_text(encoding="utf-8"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                modules.append(node.module)
        self.assertEqual(set(modules), {"copy", "fractions", "hashlib", "json", "pathlib", "re"})


if __name__ == "__main__":
    unittest.main()
