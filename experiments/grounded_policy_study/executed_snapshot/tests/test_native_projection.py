"""Authored native-shaped JSON only: zero API/selector/simulator invocations.

These fixtures test projection and byte/link checks, never scientific model
validity. In particular their authored cohorts and decimal scores are NOT
claims that the native cohort/decision proof checker accepted them.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from ora_study import native_projection as projection
from ora_study import scorer


MOVES = ("north", "east", "south", "west")


def h(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def signed(value):
    value["hash"] = h({key: item for key, item in value.items() if key != "hash"})
    return value


def observation(cycle):
    # Hand-authored stationary public frames; no world is constructed.
    return {"world_version": "open-object-world-challenge-v1", "observation_id": f"owc-{cycle:06d}",
            "cycle": cycle, "position": [0, 0], "inventory_ids": [], "visible_entities": []}


CONTEXT = {"position": [0, 0], "inventory_ids": [], "visible_ids": []}


def fixture_context(frame):
    result = {"position": deepcopy(frame["position"]), "inventory_ids": sorted(frame["inventory_ids"]),
              "visible_ids": sorted(entity["id"] for entity in frame["visible_entities"])}
    for entity in frame["visible_entities"]:
        result["entity." + entity["id"] + ".position"] = deepcopy(entity["position"])
        if "observable_state" in entity:
            result["entity." + entity["id"] + ".state"] = entity["observable_state"]
    return result


def authored_cohort():
    actions = []
    for action in MOVES:
        models = []
        if action == "north":
            for index, delta in enumerate(([0, 0], [1, 0])):
                structure = {"kind": "constant", "delta": delta}
                models.append({"model_id": "rule-" + h(structure), "structure": structure,
                               "code_version": "grounded-policy-v2.1", "construction_loss": 0,
                               "syntax_length": 2, "structural_order": [index],
                               "derivation": {"construction": [], "branches": [[]]}})
            models.append({"model_id": "N", "structure": {"kind": "unresolved_process"},
                           "code_version": "grounded-policy-v2.1",
                           "derivation": {"kind": "authored_uncertainty_safeguard"}})
        actions.append({"action": action, "status": "available" if models else "insufficient_explanatory_diversity",
                        "nonzero_delta": [1, 0] if models else None,
                        "observed_deltas": [[0, 0], [1, 0]] if models else [],
                        "conditional_count": 0, "retained_conditional_count": 0, "models": models})
    cohort = {"schema_version": "grounded-cohort-v2", "code_version": "grounded-policy-v2.1",
              "discovery_events": [], "actions": actions}
    cohort["cohort_digest"] = h(cohort)
    return cohort


def authored_body(cohort, updated=False, policy_null=False):
    menu = []
    for action in cohort["actions"]:
        reason = action["status"] if action["status"] != "available" else None
        row = {"action": action["action"], "command": {"action": action["action"]},
               "cohort_status": action["status"], "forecastable": reason is None,
               "forecast_reason": reason, "inquiry_eligible": reason is None,
               "eligibility_reason": reason, "selection_eligible": reason is None,
               "selection_reason": reason, "concrete_predictions": [], "unavailable_models": [],
               "evidence_event_ids": [], "posterior": [], "forecast": None, "unresolved_mass": None,
               "predictive_entropy_bits": None, "expected_model_entropy_bits": None, "score_bits": None}
        if reason is None:
            weights = [["114", "157"], ["3", "157"], ["40", "157"]] if updated else [["1", "3"]] * 3
            for index, model in enumerate(action["models"]):
                distribution = [["1", "3"]] * 3 if index == 2 else [
                    ["19", "20"] if index == column else ["1", "40"] for column in range(3)]
                row["posterior"].append({"model_id": model["model_id"], "weight": weights[index],
                                         "distribution": dict(zip(("zero", "displacement", "other"), distribution))})
                if index < 2:
                    row["concrete_predictions"].append({"model_id": model["model_id"], "position": [index, 0],
                        "outcome_class": ("zero", "displacement")[index], "derivation_digest": h(model["derivation"])})
            row["forecast"] = dict(zip(("zero", "displacement", "other"),
                [["2921", "3768"], ["571", "4710"], ["1951", "18840"]] if updated else
                [["157", "360"], ["157", "360"], ["23", "180"]]))
            row["unresolved_mass"] = weights[-1]
            row["evidence_event_ids"] = ["OWC-A000001"] if updated else []
            row.update(predictive_entropy_bits="1.400000000000000000",
                       expected_model_entropy_bits="0.600000000000000000", score_bits="0.800000000000000000")
            if policy_null:
                row.update(selection_eligible=False, selection_reason="score_not_above_threshold",
                           score_bits="0.000000000000000000")
        menu.append(row)
    return {"schema_version": "grounded-policy-decision-v2", "code_version": "grounded-policy-v2.1",
            "cohort_digest": cohort["cohort_digest"], "context": deepcopy(CONTEXT),
            "context_digest": h(CONTEXT), "menu": menu, "selected_action": None if policy_null else "north"}


def bare_state(run="native-R", mode="retain_first"):
    frame = {"observation": observation(0), "receipt": None}
    identity = {"run_id": run, "path": "/fixture/" + run, "research_dir": "/fixture",
        "filesystem": {"directory": [1, 2], "lock": [1, 3]},
        "source_inputs": {name: {"path": "/fixture/" + run + "/" + name, "sha256": "a" * 64,
                                  "device": 1, "inode": index, "bytes": 13}
                          for index, name in enumerate(("ora", "world", "observations"), 4)},
        "code_manifest": {"fixture.py": "b" * 64}, "runtime_manifest": {"fixture": "authored"},
        "profile": {"name": "synthetic_two_decision_v2", "max_bytes": 2097152, "max_decisions": 2, "max_actions": 2},
        "selection_backend": "grounded_policy_v2", "evidence_mode": mode, "discovery_count": 0,
        "science_configuration": {name: None for name in "version model_language fields max_conditionals retained_conditionals likelihood_correct likelihood_other unresolved rational_digits entropy_precision entropy_places threshold tie movement_order generator_input update learning_evidence hypothesis_evolution".split()},
        "adapter": {"source_id": projection.SOURCE_ID, "descriptor": projection.SOURCE_DESCRIPTOR,
                    "actor": "agent", "world_id": "c" * 64,
                    "world_version": "open-object-world-challenge-v1", "grammar": "challenge-candidate-commands-v1"},
        "initial_ora_hash": "d" * 64, "initial_world_hash": "c" * 64, "initial_frames_hash": h([frame])}
    return {"version": "grounded-investigation-capsule-v2", "identity": identity, "identity_hash": h(identity),
            "revision": 0, "frames": [frame], "cohort": authored_cohort(),
            "ora": {"fixture": "opaque"}, "world": {"fixture": "opaque private payload, never observed"},
            "decisions": [], "attempts": [], "outcomes": [], "beliefs": [], "events": [], "reserve": 0, "seal": None}


def add_event(state, kind, record):
    event = signed({"revision": len(state["events"]) + 1, "kind": kind, "reference": record["id"],
                    "result_hash": record["hash"], "predecessor": state["events"][-1]["hash"] if state["events"] else None})
    state["events"].append(event)
    state["revision"] = len(state["events"])


def add_decision(state, *, status="selected", complete=False):
    """Assemble a declared receipt fixture, without selecting an action."""
    ordinal, identity = len(state["decisions"]) + 1, state["identity"]
    run = identity["run_id"]
    prior = state["outcomes"][0] if state["outcomes"] else None
    current = prior["after_observation"] if prior else state["frames"][-1]["observation"]
    context = fixture_context(current)
    evidence, included, excluded = [], [], []
    for before, after in zip(state["frames"][identity["discovery_count"]:], state["frames"][identity["discovery_count"] + 1:]):
        if after["receipt"]["action"] not in MOVES:
            continue
        row = {"event_id": after["receipt"]["id"], "before_context": fixture_context(before["observation"]),
               "action": after["receipt"]["action"], "after_position": deepcopy(after["observation"]["position"]),
               "refs": {"before": h(before["observation"]), "receipt": h(after["receipt"]), "after": h(after["observation"])}}
        evidence.append(row)
        included.append(h(row))
    if prior:
        row = {"event_id": prior["receipt"]["id"], "before_context": fixture_context(prior["before_observation"]), "action": "north",
               "after_position": [0, 0], "refs": {"before": h(prior["before_observation"]),
                                                  "receipt": h(prior["receipt"]), "after": h(prior["after_observation"])}}
        if identity["evidence_mode"] == "retain_first":
            evidence.append(row)
            included.append(h(row))
        else:
            excluded.append(h(row))
    view = {"schema": "grounded-policy-view-v2", "cohort": deepcopy(state["cohort"]), "context": deepcopy(context),
            "evidence": evidence, "lifecycle": {"completed": ordinal - 1, "interpreted": int(prior is not None)}}
    anchor = {"world_hash": prior["world_after_hash"] if prior else identity["initial_world_hash"],
              "observation_hash": h(current), "previous_decision_hash": state["decisions"][-1]["hash"] if state["decisions"] else None,
              "previous_belief_hash": state["beliefs"][-1]["hash"] if state["beliefs"] else None,
              "completed_actions": int(prior is not None), "completed_decisions": ordinal - 1}
    mask = {"schema": "trusted-evidence-mask-v2", "source_id": projection.SOURCE_ID, "descriptor": projection.SOURCE_DESCRIPTOR,
            "ordinal": ordinal, "mode": identity["evidence_mode"], "reason": "stage_one_common" if ordinal == 1 else
                      "explicit_first_update_retained" if identity["evidence_mode"] == "retain_first" else "explicit_first_update_withheld",
            "included": included, "excluded": excluded, "view_hash": h(view), "projection": "public_features-full-v2",
            "prior_state_hash": h(anchor)}
    body = authored_body(state["cohort"], updated=bool(evidence), policy_null=status == "policy_null")
    body["context"] = deepcopy(context)
    for entity_id in context["visible_ids"]:
        body["context"].setdefault("entity." + entity_id + ".state", None)
    body["context_digest"] = h(body["context"])
    body["menu"][0]["evidence_event_ids"] = [row["event_id"] for row in evidence]
    hypotheses = [{"id": prediction["model_id"], "model_id": prediction["model_id"], "position": deepcopy(prediction["position"]),
                   "derivation": deepcopy(state["cohort"]["actions"][0]["models"][index]["derivation"]),
                   "derivation_digest": prediction["derivation_digest"]}
                  for index, prediction in enumerate(body["menu"][0]["concrete_predictions"])]
    case = signed({"id": run + f":case{ordinal}.north", "experiment_id": run + f":experiment{ordinal}.north",
                   "context": deepcopy(context), "command": {"action": "north"}, "hypotheses": hypotheses,
                   "cohort_hash": h(state["cohort"])})
    decision = signed({"schema": "selection-receipt-v2", "id": run + f":decision{ordinal}", "ordinal": ordinal,
        "revision": state["revision"] + 1, "selection_backend": "grounded_policy_v2", "producer": "internal-t1-v2",
        "backend_code_hash": h(identity["code_manifest"]), "runtime_hash": h(identity["runtime_manifest"]),
        "source_id": projection.SOURCE_ID, "source_descriptor": projection.SOURCE_DESCRIPTOR,
        "source_frame_hash": h(current), "context_hash": h(context), "proposal_manifest_hash": h(state["cohort"]),
        "input_view_hash": h(view), "mask": mask, "prior_state_hash": h(anchor), "anchor": anchor,
        "policy_state_hash": h({"cohort": state["cohort"], "body": body}), "body": body, "cases": [case], "status": status,
        "owner_id": case["id"] if status == "selected" else None,
        "experiment_id": case["experiment_id"] if status == "selected" else None,
        "command": {"action": "north"} if status == "selected" else None,
        "case_hash": case["hash"] if status == "selected" else None})
    state["decisions"].append(decision)
    add_event(state, "select", decision)
    if status != "selected":
        return state
    attempt = {"id": run + f":attempt{ordinal}", "decision_id": decision["id"], "owner_id": decision["owner_id"],
               "experiment_id": decision["experiment_id"], "receipt_hash": decision["hash"], "case_hash": case["hash"],
               "command": {"action": "north"}, "status": "prepared", "outcome_id": None, "belief_id": None}
    state["attempts"].append(attempt)
    state["reserve"] = 524288
    if not complete:
        return state
    after = observation(current["cycle"] + 1)
    receipt = {"id": f"OWC-A{after['cycle']:06d}", "cycle": after["cycle"], "action": "north", "target": None,
               "direction": None, "before": [0, 0], "after": [0, 0], "success": False, "blocked": True,
               "observed_effects": ["Authored fixture stayed in place"], "visible_entity_states": {}}
    outcome = signed({"id": run + f":outcome{ordinal}", "revision": state["revision"] + 1,
        "attempt_id": attempt["id"], "decision_id": decision["id"], "owner_id": decision["owner_id"],
        "experiment_id": decision["experiment_id"], "selection_hash": decision["hash"], "case_hash": case["hash"],
        "command": {"action": "north"}, "before_observation": deepcopy(current), "after_observation": after,
        "receipt": receipt, "world_before_hash": anchor["world_hash"], "world_after_hash": "e" * 64})
    state["outcomes"].append(outcome)
    add_event(state, "execute", outcome)
    belief = signed({"id": run + f":belief{ordinal}", "revision": state["revision"] + 1,
        "owner_id": decision["owner_id"], "experiment_id": decision["experiment_id"], "outcome_id": outcome["id"],
        "outcome_hash": outcome["hash"], "case_hash": case["hash"], "rule": "compiled-public-position-case-v2",
        "evaluations": [{"hypothesis_id": hypothesis["id"], "verdict": "supports_this_case" if index == 0 else "contradicts_this_case"}
                        for index, hypothesis in enumerate(hypotheses)], "reason": "case_local_discrimination_only",
        "predecessor": state["beliefs"][-1]["hash"] if state["beliefs"] else None})
    state["beliefs"].append(belief)
    add_event(state, "interpret", belief)
    attempt.update(status="interpreted", outcome_id=outcome["id"], belief_id=belief["id"])
    state["reserve"] = 0
    return state


def rebind_first_null_decision(state):
    """Reseal an authored null fixture after an intentional semantic mutation."""
    decision = state["decisions"][0]
    decision["policy_state_hash"] = h({"cohort": state["cohort"], "body": decision["body"]})
    signed(decision)
    state["events"] = []
    add_event(state, "select", decision)


class SavedNativeProjectionTests(unittest.TestCase):
    def test_complete_first_pair_ignores_only_declared_run_provenance(self):
        retain = add_decision(bare_state())
        withhold = add_decision(bare_state("native-W", "withhold_first"))
        self.assertEqual(projection.first_decision_semantics(retain), projection.first_decision_semantics(withhold))
        result = projection.first_decision_semantics(retain)
        self.assertEqual(result["decision"]["native_body"], retain["decisions"][0]["body"])
        self.assertEqual(len(result["decision"]["admitted_cases"]), 1)
        self.assertEqual(set(result["decision"]["forecasts"]), set(MOVES))

    def test_every_native_body_field_survives_pair_comparison(self):
        original = add_decision(bare_state(), status="policy_null")
        changed = deepcopy(original)
        changed["decisions"][0]["body"]["menu"][0]["expected_model_entropy_bits"] = "0.610000000000000000"
        rebind_first_null_decision(changed)
        self.assertNotEqual(projection.first_decision_semantics(original), projection.first_decision_semantics(changed))

    def test_exact_retain_withhold_views_keep_full_actual_history(self):
        retain = add_decision(add_decision(bare_state(), complete=True))
        withhold = add_decision(add_decision(bare_state("native-W", "withhold_first"), complete=True))
        before = deepcopy(withhold)
        r = projection.reconstruct_policy_view(retain, 2)
        w = projection.reconstruct_policy_view(withhold, 2)
        self.assertEqual(len(r["view"]["evidence"]), 1)
        self.assertEqual(w["view"]["evidence"], [])
        self.assertEqual(r["mask"]["included"], w["mask"]["excluded"])
        self.assertEqual(r["view"]["lifecycle"], w["view"]["lifecycle"])
        self.assertEqual(projection.public_outcome_semantics(retain["outcomes"][0]),
                         projection.public_outcome_semantics(withhold["outcomes"][0]))
        self.assertEqual(withhold, before)
        self.assertEqual(projection.decision_semantics(retain, 2)["forecasts"]["north"]["local_e1_count"], 1)
        self.assertEqual(projection.decision_semantics(withhold, 2)["forecasts"]["north"]["local_e1_count"], 0)

    def test_first_null_second_decision_equality(self):
        r = add_decision(add_decision(bare_state(), status="policy_null"))
        w = add_decision(add_decision(bare_state("native-W", "withhold_first"), status="policy_null"))
        self.assertEqual(projection.decision_semantics(r, 2), projection.decision_semantics(w, 2))

    def test_capacity_null_keeps_winning_body_menu_and_cases(self):
        state = add_decision(bare_state(), status="capacity_null")
        result = projection.decision_semantics(state, 1)
        self.assertEqual(result["selection"], {"command": None, "owner": None, "null_reason": "capacity_null"})
        self.assertEqual(result["native_body"]["selected_action"], "north")
        self.assertTrue(result["admitted_cases"])
        self.assertEqual(state["outcomes"], [])

    def test_explicit_sequence_mapping_and_full_native_provenance(self):
        state = add_decision(bare_state(), complete=True)
        sequence = {"t1_committed": 10, "outcome_invoked": 20, "outcome_durable": 21, "t3_completed": 30}
        stage = projection.project_native_stage(state, 1, case_id="registered.R", sequence=sequence)
        self.assertEqual(stage["t1"]["committed_seq"], 10)
        self.assertEqual(stage["outcome"]["durable_seq"], 21)
        self.assertEqual(stage["t3"]["completed_seq"], 30)
        self.assertEqual(stage["t1"]["provenance"]["native_decision"], state["decisions"][0])
        self.assertEqual(stage["t1"]["provenance"]["native_outcome"], state["outcomes"][0])
        self.assertEqual(stage["t3"]["outcome_sha256"], h(stage["outcome"]))
        self.assertEqual(scorer._stage(stage, "registered.R", 1, CONTEXT, False), {"north"})

    def test_absent_or_bad_ledger_mapping_never_invents_sequence(self):
        state = add_decision(bare_state(), complete=True)
        for sequence in ({}, {"t1_committed": 1, "outcome_invoked": None, "outcome_durable": None, "t3_completed": None},
                         {"t1_committed": 10, "outcome_invoked": 9, "outcome_durable": 11, "t3_completed": 12},
                         {"t1_committed": True, "outcome_invoked": 2, "outcome_durable": 3, "t3_completed": 4}):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                projection.project_native_stage(state, 1, case_id="registered.R", sequence=sequence)

    def test_changed_mask_rejected_even_if_native_decision_rehashed(self):
        state = add_decision(bare_state(), status="policy_null")
        for key, value in (("included", ["f" * 64]), ("projection", "alternative"), ("mode", "withhold_first"),
                           ("prior_state_hash", "f" * 64), ("view_hash", "f" * 64)):
            changed = deepcopy(state)
            changed["decisions"][0]["mask"][key] = value
            rebind_first_null_decision(changed)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "view/mask"):
                projection.decision_semantics(changed, 1)

    def test_unknown_fields_rejected_at_all_projection_boundaries(self):
        state = add_decision(bare_state(), status="policy_null")
        for path in ((), ("identity",), ("cohort",), ("decisions", 0), ("decisions", 0, "body"),
                     ("decisions", 0, "mask"), ("decisions", 0, "body", "menu", 0),
                     ("decisions", 0, "cases", 0), ("frames", 0, "observation")):
            changed = deepcopy(state)
            target = changed
            for key in path:
                target = target[key]
            target["unexpected"] = "evidence-bearing payload"
            if path and path[0] == "decisions":
                rebind_first_null_decision(changed)
            with self.subTest(path=path), self.assertRaises(ValueError):
                projection.decision_semantics(changed, 1)

    def test_private_state_is_never_used_as_policy_input(self):
        state = add_decision(bare_state())
        changed = deepcopy(state)
        changed["world"] = {"hidden_future_answer": [2, 2], "private_entities": {"secret": "state"}}
        changed["ora"] = {"posterior_cache": ["untrusted", "payload"]}
        self.assertEqual(projection.decision_semantics(state, 1), projection.decision_semantics(changed, 1))

    def test_native_owner_and_case_hash_drift_rejects(self):
        for key in ("owner_id", "case_hash", "command"):
            state = add_decision(bare_state())
            state["decisions"][0][key] = None
            signed(state["decisions"][0])
            with self.subTest(key=key), self.assertRaises(ValueError):
                projection.decision_semantics(state, 1)

    def test_extra_full_outcome_cannot_be_silently_dropped(self):
        state = add_decision(bare_state(), complete=True)
        extra = deepcopy(state["outcomes"][0])
        extra["decision_id"] = "foreign:decision1"
        signed(extra)
        state["outcomes"].append(extra)
        with self.assertRaisesRegex(ValueError, "unbound retained"):
            projection.decision_semantics(state, 1)

    def test_authored_unavailability_reasons_remain_complete(self):
        state = add_decision(bare_state(), status="policy_null")
        result = projection.decision_semantics(state, 1)
        self.assertEqual([result["forecasts"][action]["reason"] for action in MOVES[1:]],
                         ["insufficient_explanatory_diversity"] * 3)
        self.assertEqual(result["native_body"]["menu"], state["decisions"][0]["body"]["menu"])

    def test_all_native_cohort_unavailable_reasons_are_preserved(self):
        for reason in ("insufficient_explanatory_diversity", "outside_first_model_class", "generator_capacity_exhausted"):
            state = bare_state()
            state["cohort"]["actions"][1]["status"] = reason
            state["cohort"]["cohort_digest"] = h({key: value for key, value in state["cohort"].items() if key != "cohort_digest"})
            add_decision(state)
            with self.subTest(reason=reason):
                self.assertEqual(projection.decision_semantics(state, 1)["forecasts"]["east"],
                                 {"status": "unavailable", "reason": reason})

    def test_no_available_concrete_models_retains_every_model_reason(self):
        state = add_decision(bare_state(), status="policy_null")
        decision = state["decisions"][0]
        row = decision["body"]["menu"][0]
        unavailable = [{"model_id": item["model_id"], "reason": "invalid_public_position_output"}
                       for item in row["concrete_predictions"]]
        row.update(forecastable=False, forecast_reason="no_available_concrete_models", inquiry_eligible=False,
                   eligibility_reason="no_available_concrete_models", selection_eligible=False,
                   selection_reason="no_available_concrete_models", concrete_predictions=[], unavailable_models=unavailable,
                   posterior=[], forecast=None, unresolved_mass=None, predictive_entropy_bits=None,
                   expected_model_entropy_bits=None, score_bits=None)
        decision["cases"] = []
        rebind_first_null_decision(state)
        semantic = projection.decision_semantics(state, 1)
        self.assertEqual(semantic["forecasts"]["north"], {"status": "unavailable", "reason": "no_available_concrete_models"})
        self.assertEqual(semantic["native_body"]["menu"][0]["unavailable_models"], unavailable)

    def test_missing_entity_state_preserves_distinct_view_and_body_context(self):
        state = bare_state()
        state["frames"][0]["observation"]["visible_entities"] = [
            {"id": "crate", "position": [0, 1], "appearance": "wooden fixture"}]
        state["identity"]["initial_frames_hash"] = h(state["frames"])
        state["identity_hash"] = h(state["identity"])
        add_decision(state)
        semantic = projection.decision_semantics(state, 1)
        self.assertNotIn("entity.crate.state", semantic["context"])
        self.assertIsNone(semantic["native_body"]["context"]["entity.crate.state"])

    def test_withholding_never_discards_common_U(self):
        state = bare_state("native-W", "withhold_first")
        receipt = {"id": "OWC-A000001", "cycle": 1, "action": "north", "target": None, "direction": None,
                   "before": [0, 0], "after": [0, 0], "success": False, "blocked": True,
                   "observed_effects": ["Authored common event"], "visible_entity_states": {}}
        state["frames"].append({"observation": observation(1), "receipt": receipt})
        state["identity"]["initial_frames_hash"] = h(state["frames"])
        state["identity_hash"] = h(state["identity"])
        add_decision(state, complete=True)
        add_decision(state)
        view = projection.reconstruct_policy_view(state, 2)
        self.assertEqual([event["event_id"] for event in view["view"]["evidence"]], ["OWC-A000001"])
        self.assertEqual(len(view["mask"]["excluded"]), 1)
        forecast = projection.decision_semantics(state, 2)["forecasts"]["north"]
        self.assertEqual((forecast["local_u_count"], forecast["local_e1_count"]), (1, 0))

    def test_no_execution_or_policy_dependencies(self):
        path = Path(projection.__file__)
        tree = ast.parse(path.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or ".")
        self.assertEqual(imported, {"copy", "re", "."})
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                             node.func.id in {"eval", "exec", "__import__", "open"} for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
