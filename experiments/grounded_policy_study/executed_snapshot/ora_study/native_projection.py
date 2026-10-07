"""Independent, saved-JSON-only projection of native v2 receipts.

No API, policy, selector, world, source file, or callback is loaded here. The
native validator and reviewed source boundary remain the authority: these
checks do not authenticate a producer, rebuild a cohort, recompute a posterior,
or issue a replacement decision. Global sequence numbers MUST come from the
independent controller ledger; capsule revisions are never substituted.

Run-local normalization is deliberately structural, never recursive key/name
stripping. Native decision/case/experiment IDs are checked against their exact
run prefix and replaced by ordinal/action names. Only their dependent hashes,
the anchor's previous decision/belief hashes, and mask mode/reason metadata are
kept in provenance rather than scorer semantics. Mode/reason are verified in
full first; the visible view and included/excluded event hashes remain semantic.
The full body, including the backend choice in a capacity null, is retained.
"""
from copy import deepcopy
import re

from . import scorer


class NativeProjectionError(scorer.SavedDataError):
    """Saved native bytes disagree with the frozen projection contract."""


DIRECTIONS = scorer.DIRECTIONS
OUTCOMES = ("zero", "displacement", "other")
WORLD_VERSION = "open-object-world-challenge-v1"
CODE_VERSION = "grounded-policy-v2.1"
SOURCE_DESCRIPTOR = scorer.digest({
    "version": "reviewed-shadow-source-v1",
    "commit": "80c0f63163d08aa2efc04ca60e1c41032ba2e839",
    "world_blob": "49683553596400e8c7b49b5ed5fdec5f937b7a22",
    "explorer_blob": "db5415b17077fdad65bf1671700f79979ff92be1",
    "objective_blob": "e25fbd9f75ec642971c372a08a476d4fe6bd1641",
    "integration_blob": "57452a114e972408aafd1f97a0c4970298ec5bbe",
})
SOURCE_ID = "research.challenge-v1." + SOURCE_DESCRIPTOR[:16]
CAPSULE_FIELDS = "version identity identity_hash revision frames cohort ora world decisions attempts outcomes beliefs events reserve seal"
IDENTITY_FIELDS = "run_id path research_dir filesystem source_inputs code_manifest runtime_manifest profile selection_backend science_configuration evidence_mode discovery_count adapter initial_ora_hash initial_world_hash initial_frames_hash"
DECISION_FIELDS = "schema id ordinal revision selection_backend producer backend_code_hash runtime_hash source_id source_descriptor source_frame_hash context_hash proposal_manifest_hash input_view_hash mask prior_state_hash anchor policy_state_hash body cases status owner_id experiment_id command case_hash hash"
BODY_FIELDS = "schema_version code_version cohort_digest context context_digest menu selected_action"
MENU_FIELDS = "action command cohort_status forecastable forecast_reason inquiry_eligible eligibility_reason selection_eligible selection_reason concrete_predictions unavailable_models evidence_event_ids posterior forecast unresolved_mass predictive_entropy_bits expected_model_entropy_bits score_bits"
CASE_FIELDS = "id experiment_id context command hypotheses cohort_hash hash"
OUTCOME_FIELDS = "id revision attempt_id decision_id owner_id experiment_id selection_hash case_hash command before_observation after_observation receipt world_before_hash world_after_hash hash"
BELIEF_FIELDS = "id revision owner_id experiment_id outcome_id outcome_hash case_hash rule evaluations reason predecessor hash"
ANCHOR_FIELDS = "world_hash observation_hash previous_decision_hash previous_belief_hash completed_actions completed_decisions"
MASK_FIELDS = "schema source_id descriptor ordinal mode reason included excluded view_hash projection prior_state_hash"


def _require(condition, message):
    if not condition:
        raise NativeProjectionError(message)


def _shape(value, fields, label):
    _require(type(value) is dict and set(value) == set(fields.split()),
             label + " has missing or unknown fields")
    return value


def _list(value, label):
    _require(type(value) is list, label + " must be a list")
    return value


def _integer(value, label, minimum=0):
    _require(type(value) is int and value >= minimum, label + " must be an integer")
    return value


def _hash(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "invalid saved hash")
    return value


def _signed(value, label):
    _require(_hash(value["hash"]) == scorer.digest({k: v for k, v in value.items() if k != "hash"}),
             label + " hash mismatch")


def _position(value):
    _require(type(value) is list and len(value) == 2 and
             all(type(x) is int and -2 <= x <= 2 for x in value), "invalid public position")


def _public_context(observation):
    result = scorer._observation(observation)
    _require(observation["world_version"] == WORLD_VERSION, "wrong public world version")
    _position(observation["position"])
    for entity in observation["visible_entities"]:
        _position(entity["position"])
    for label in observation["inventory_ids"] + result["visible_ids"]:
        _require(bool(re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", label)), "invalid public identity")
    return result


def _normalized_context(context):
    """The policy's explicit missing-state normalization, not a new feature."""
    result = deepcopy(context)
    for entity_id in result["visible_ids"]:
        result.setdefault("entity." + entity_id + ".state", None)
    return result


def _receipt(receipt, before, after):
    required = set("id cycle action target direction before after success blocked observed_effects visible_entity_states".split())
    _require(type(receipt) is dict and required <= set(receipt) <= required | {"inspection"},
             "receipt has missing or unknown fields")
    _require(after["cycle"] == before["cycle"] + 1 and before["world_version"] == after["world_version"],
             "public frames are not adjacent")
    _require(type(receipt["cycle"]) is int and receipt["cycle"] == after["cycle"] and
             receipt["id"] == f"OWC-A{after['cycle']:06d}", "receipt identity/cycle mismatch")
    _require(receipt["before"] == before["position"] and receipt["after"] == after["position"],
             "receipt/public position mismatch")
    _require(receipt["action"] in (*DIRECTIONS, "inspect", "interact", "take", "drop", "push"),
             "unsupported public action")
    for field in ("target", "direction"):
        _require(receipt[field] is None or (type(receipt[field]) is str and
                 re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", receipt[field])), "invalid receipt command field")
    _require(all(type(receipt[key]) is bool for key in ("success", "blocked")), "invalid receipt flags")
    _require(type(receipt["observed_effects"]) is list and
             all(type(x) is str for x in receipt["observed_effects"]), "invalid receipt effects")
    _require(type(receipt["visible_entity_states"]) is dict and
             all(type(k) is str and type(v) is str for k, v in receipt["visible_entity_states"].items()),
             "invalid receipt visible states")
    if "inspection" in receipt:
        inspected = receipt["inspection"]
        _require(type(inspected) is dict and {"id", "position", "appearance"} <= set(inspected) <=
                 {"id", "position", "appearance", "observable_state"}, "invalid inspection fields")
        _position(inspected["position"])
        _require(type(inspected["id"]) is str and type(inspected["appearance"]) is str and
                 ("observable_state" not in inspected or type(inspected["observable_state"]) is str),
                 "invalid public inspection")
    if receipt["action"] in DIRECTIONS:
        _require(receipt["target"] is None and receipt["direction"] is None and "inspection" not in receipt,
                 "movement has extra command/inspection payload")
        expected = {entity["id"]: entity["observable_state"] for entity in after["visible_entities"]
                    if "observable_state" in entity}
        _require(receipt["visible_entity_states"] == expected, "movement public-state map mismatch")


def _frames(frames):
    _require(type(frames) is list and 1 <= len(frames) <= 65, "invalid full saved prefix")
    for index, frame in enumerate(frames):
        _shape(frame, "observation receipt", "public frame")
        _public_context(frame["observation"])
        if index == 0:
            _require(frame["observation"]["cycle"] == 0 and frame["receipt"] is None,
                     "prefix must start at cycle zero")
        else:
            _receipt(frame["receipt"], frames[index - 1]["observation"], frame["observation"])


def _rows(frames):
    rows = []
    for before, after in zip(frames, frames[1:]):
        receipt = after["receipt"]
        if receipt["action"] in DIRECTIONS:
            rows.append({"event_id": receipt["id"], "before_context": _public_context(before["observation"]),
                         "action": receipt["action"], "after_position": deepcopy(after["observation"]["position"]),
                         "refs": {"before": scorer.digest(before["observation"]),
                                  "receipt": scorer.digest(receipt), "after": scorer.digest(after["observation"])}})
    return rows


def _reference(value):
    _shape(value, "event_id refs", "derivation reference")
    _require(type(value["event_id"]) is str and bool(value["event_id"]), "invalid referenced event")
    _shape(value["refs"], "before receipt after", "public reference hashes")
    for item in value["refs"].values():
        _hash(item)


def _cohort(cohort, discovery):
    _shape(cohort, "schema_version code_version discovery_events actions cohort_digest", "cohort")
    _require(cohort["schema_version"] == "grounded-cohort-v2" and cohort["code_version"] == CODE_VERSION,
             "unsupported cohort schema/code")
    _require(cohort["cohort_digest"] == scorer.digest({k: v for k, v in cohort.items() if k != "cohort_digest"}),
             "cohort digest mismatch")
    normalized = [dict(row, before_context=_normalized_context(row["before_context"])) for row in discovery]
    _require(cohort["discovery_events"] == [{"event_id": row["event_id"], "digest": scorer.digest(row)}
                                          for row in normalized], "cohort D references differ")
    _require(type(cohort["actions"]) is list and len(cohort["actions"]) == 4, "incomplete cohort actions")
    for direction, entry in zip(DIRECTIONS, cohort["actions"]):
        _shape(entry, "action status nonzero_delta observed_deltas conditional_count retained_conditional_count models", "cohort action")
        _require(entry["action"] == direction and entry["status"] in
                 {"available", "insufficient_explanatory_diversity", "outside_first_model_class", "generator_capacity_exhausted"},
                 "invalid cohort action/status")
        _integer(entry["conditional_count"], "conditional count")
        _integer(entry["retained_conditional_count"], "retained conditional count")
        for model in _list(entry["models"], "cohort models"):
            if model.get("model_id") == "N":
                _shape(model, "model_id structure code_version derivation", "unresolved model")
                _require(model["structure"] == {"kind": "unresolved_process"} and
                         model["derivation"] == {"kind": "authored_uncertainty_safeguard"}, "changed unresolved model")
            else:
                _shape(model, "model_id structure code_version construction_loss syntax_length structural_order derivation", "concrete model")
                structure = model["structure"]
                _require(type(structure) is dict and structure.get("kind") in ("constant", "conditional"), "invalid model structure")
                _shape(structure, "kind delta" if structure["kind"] == "constant" else
                       "kind field value if_delta else_delta", "model structure")
                _require(model["model_id"] == "rule-" + scorer.digest(structure), "model structural identity mismatch")
                _shape(model["derivation"], "construction branches", "model derivation")
                for reference in _list(model["derivation"]["construction"], "construction references"):
                    _reference(reference)
                for branch in _list(model["derivation"]["branches"], "derivation branches"):
                    for reference in _list(branch, "branch references"):
                        _reference(reference)
            _require(model["code_version"] == CODE_VERSION, "model code version changed")


def _state_shape(state):
    _shape(state, CAPSULE_FIELDS, "native capsule")
    _require(state["version"] == "grounded-investigation-capsule-v2", "unsupported native capsule")
    identity = _shape(state["identity"], IDENTITY_FIELDS, "native identity")
    _require(type(identity["run_id"]) is str and bool(re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", identity["run_id"])), "invalid native run ID")
    _require(state["identity_hash"] == scorer.digest(identity), "native identity hash mismatch")
    _require(identity["selection_backend"] == "grounded_policy_v2" and
             identity["evidence_mode"] in ("retain_first", "withhold_first"), "unsupported native policy identity")
    _shape(identity["profile"], "name max_bytes max_decisions max_actions", "native profile")
    _shape(identity["science_configuration"], "version model_language fields max_conditionals retained_conditionals likelihood_correct likelihood_other unresolved rational_digits entropy_precision entropy_places threshold tie movement_order generator_input update learning_evidence hypothesis_evolution", "native science configuration")
    _shape(identity["filesystem"], "directory lock", "native filesystem identity")
    _shape(identity["source_inputs"], "ora world observations", "native source descriptors")
    for source in identity["source_inputs"].values():
        _shape(source, "path sha256 device inode bytes", "native source descriptor")
        _hash(source["sha256"])
    _shape(identity["adapter"], "source_id descriptor actor world_id world_version grammar", "native adapter")
    _require(identity["adapter"] == {"source_id": SOURCE_ID, "descriptor": SOURCE_DESCRIPTOR,
             "actor": "agent", "world_id": identity["initial_world_hash"], "world_version": WORLD_VERSION,
             "grammar": "challenge-candidate-commands-v1"}, "native source/actor descriptor mismatch")
    _frames(state["frames"])
    _require(identity["initial_frames_hash"] == scorer.digest(state["frames"]), "initial public frames hash mismatch")
    count = _integer(identity["discovery_count"], "discovery boundary")
    _require(count < len(state["frames"]), "discovery boundary exceeds saved prefix")
    _cohort(state["cohort"], _rows(state["frames"][:count + 1]))
    for collection in ("decisions", "outcomes", "beliefs", "attempts", "events"):
        _list(state[collection], collection)
    _require(1 <= len(state["decisions"]) <= 2, "saved projection requires one or two decisions")
    for ordinal, decision in enumerate(state["decisions"], 1):
        _shape(decision, DECISION_FIELDS, "native decision")
        _signed(decision, "native decision")
        _require(decision["ordinal"] == ordinal and type(decision["ordinal"]) is int and
                 decision["id"] == identity["run_id"] + ":decision" + str(ordinal), "native decision identity mismatch")
        _shape(decision["body"], BODY_FIELDS, "native decision body")
        for case in _list(decision["cases"], "native admitted cases"):
            _shape(case, CASE_FIELDS, "native admitted case")
            _signed(case, "native admitted case")
            for hypothesis in _list(case["hypotheses"], "native case hypotheses"):
                _shape(hypothesis, "id model_id position derivation derivation_digest", "native case hypothesis")
    for outcome in state["outcomes"]:
        public_outcome_semantics(outcome)
    for belief in state["beliefs"]:
        _shape(belief, BELIEF_FIELDS, "native belief")
        _signed(belief, "native belief")
        for verdict in _list(belief["evaluations"], "belief evaluations"):
            _shape(verdict, "hypothesis_id verdict", "belief evaluation")
    for attempt in state["attempts"]:
        _shape(attempt, "id decision_id owner_id experiment_id receipt_hash case_hash command status outcome_id belief_id", "native attempt")
    for event in state["events"]:
        _shape(event, "revision kind reference result_hash predecessor hash", "native event")
        _signed(event, "native event")
    decision_ids = {decision["id"] for decision in state["decisions"]}
    outcome_ids = {outcome["id"] for outcome in state["outcomes"]}
    _require(all(row["decision_id"] in decision_ids for row in state["outcomes"] + state["attempts"]) and
             all(row["outcome_id"] in outcome_ids for row in state["beliefs"]), "unbound retained lifecycle record")
    events, actual_outcomes, actual_beliefs, actual_attempts = [], [], [], []
    def append_event(kind, reference, result_hash):
        row = {"revision": len(events) + 1, "kind": kind, "reference": reference,
               "result_hash": result_hash, "predecessor": events[-1]["hash"] if events else None}
        row["hash"] = scorer.digest(row)
        events.append(row)
    for ordinal in range(1, len(state["decisions"]) + 1):
        decision, outcome, belief = _stage_records(state, ordinal)
        _require(decision["revision"] == len(events) + 1, "native selection revision mismatch")
        if ordinal > 1:
            previous, previous_outcome, previous_belief = _stage_records(state, ordinal - 1)
            _require(previous["status"] != "selected" or previous_belief is not None,
                     "next decision before prior canonical interpretation")
        append_event("select", decision["id"], decision["hash"])
        actual_attempts.extend(row for row in state["attempts"] if row["decision_id"] == decision["id"])
        if outcome:
            actual_outcomes.append(outcome)
            append_event("execute", outcome["id"], outcome["hash"])
        if belief:
            actual_beliefs.append(belief)
            append_event("interpret", belief["id"], belief["hash"])
    _require(state["events"] == events and state["revision"] == len(events), "native event history differs")
    _require(state["outcomes"] == actual_outcomes and state["beliefs"] == actual_beliefs and
             state["attempts"] == actual_attempts, "extra or reordered retained native history")
    expected_reserve = (524288 if actual_attempts and actual_attempts[-1]["status"] == "prepared" else
                        65536 if actual_attempts and actual_attempts[-1]["status"] == "committed" else 0)
    _require(state["reserve"] == expected_reserve, "native completion reserve differs")


def public_outcome_semantics(outcome):
    """Full actual public payload, with only native ownership/provenance removed."""
    _shape(outcome, OUTCOME_FIELDS, "native outcome")
    _signed(outcome, "native outcome")
    _shape(outcome["command"], "action", "owned command")
    _require(outcome["command"]["action"] in DIRECTIONS, "nonmovement owned command")
    before, after = outcome["before_observation"], outcome["after_observation"]
    _public_context(before)
    _public_context(after)
    _receipt(outcome["receipt"], before, after)
    _require(outcome["receipt"]["action"] == outcome["command"]["action"], "owned receipt/action mismatch")
    _hash(outcome["world_before_hash"])
    _hash(outcome["world_after_hash"])
    return {name: deepcopy(outcome[name]) for name in
            ("command", "before_observation", "receipt", "after_observation")}


def _stage_records(state, ordinal):
    decision = state["decisions"][ordinal - 1]
    outcomes = [row for row in state["outcomes"] if row["decision_id"] == decision["id"]]
    attempts = [row for row in state["attempts"] if row["decision_id"] == decision["id"]]
    _require(len(outcomes) <= 1 and len(attempts) <= 1, "duplicate owned records")
    outcome = outcomes[0] if outcomes else None
    beliefs = [row for row in state["beliefs"] if outcome is not None and row["outcome_id"] == outcome["id"]]
    _require(len(beliefs) <= 1, "duplicate interpretation")
    belief = beliefs[0] if beliefs else None
    if decision["status"] != "selected":
        _require(not attempts and outcome is None and belief is None, "null decision has owned history")
        return decision, None, None
    _require(len(attempts) == 1, "selected decision lacks saved attempt")
    attempt = attempts[0]
    run = state["identity"]["run_id"]
    expected = {"id": run + ":attempt" + str(ordinal), "decision_id": decision["id"],
                "owner_id": decision["owner_id"], "experiment_id": decision["experiment_id"],
                "receipt_hash": decision["hash"], "case_hash": decision["case_hash"],
                "command": decision["command"], "status": "interpreted" if belief else "committed" if outcome else "prepared",
                "outcome_id": outcome["id"] if outcome else None, "belief_id": belief["id"] if belief else None}
    _require(attempt == expected, "native attempt ownership/status mismatch")
    if outcome:
        expected_links = {"id": run + ":outcome" + str(ordinal), "attempt_id": attempt["id"],
                          "decision_id": decision["id"], "owner_id": decision["owner_id"],
                          "experiment_id": decision["experiment_id"], "selection_hash": decision["hash"],
                          "case_hash": decision["case_hash"], "command": decision["command"]}
        _require(all(outcome[key] == value for key, value in expected_links.items()), "native outcome ownership mismatch")
        _require(outcome["revision"] == decision["revision"] + 1, "native outcome revision mismatch")
        if belief:
            case = next((case for case in decision["cases"] if case["id"] == decision["owner_id"]), None)
            _require(case is not None, "interpretation owner missing from admitted cases")
            evaluations = [{"hypothesis_id": hypothesis["id"], "verdict": "supports_this_case" if
                           hypothesis["position"] == outcome["after_observation"]["position"] else "contradicts_this_case"}
                          for hypothesis in case["hypotheses"]]
            predecessors = [row for row in state["beliefs"] if row["revision"] < belief["revision"]]
            expected_belief = {"id": run + ":belief" + str(ordinal), "revision": outcome["revision"] + 1,
                "owner_id": decision["owner_id"], "experiment_id": decision["experiment_id"],
                "outcome_id": outcome["id"], "outcome_hash": outcome["hash"], "case_hash": decision["case_hash"],
                "rule": "compiled-public-position-case-v2", "evaluations": evaluations,
                "reason": "case_local_discrimination_only" if len({row["verdict"] for row in evaluations}) > 1 else "alternatives_undiscriminated",
                "predecessor": predecessors[-1]["hash"] if predecessors else None}
            _require({k: v for k, v in belief.items() if k != "hash"} == expected_belief, "noncanonical saved interpretation")
    return decision, outcome, belief


def reconstruct_policy_view(state, ordinal):
    """Reconstruct exact allowlisted view and mask from saved public records.

    Private ``state.world`` and ``state.ora`` are deliberately never read. World
    hashes below are saved native provenance; their authenticity is not claimed.
    """
    _state_shape(state)
    _require(type(ordinal) is int and 1 <= ordinal <= len(state["decisions"]), "missing decision ordinal")
    decision = state["decisions"][ordinal - 1]
    count, identity = state["identity"]["discovery_count"], state["identity"]
    discovery, common = _rows(state["frames"][:count + 1]), _rows(state["frames"][count:])
    previous, first_outcome, first_belief = (None, None, None) if ordinal == 1 else _stage_records(state, 1)
    _require(ordinal == 1 or previous["status"] != "selected" or first_belief is not None,
             "second view precedes canonical first interpretation")
    current = first_outcome["after_observation"] if first_outcome else state["frames"][-1]["observation"]
    anchor = {"world_hash": first_outcome["world_after_hash"] if first_outcome else identity["initial_world_hash"],
              "observation_hash": scorer.digest(current),
              "previous_decision_hash": previous["hash"] if previous else None,
              "previous_belief_hash": first_belief["hash"] if first_belief else None,
              "completed_actions": int(first_outcome is not None), "completed_decisions": ordinal - 1}
    evidence = deepcopy(common)
    included, excluded = [scorer.digest(row) for row in evidence], []
    if first_outcome is not None:
        _require(first_outcome["before_observation"] == state["frames"][-1]["observation"] and
                 first_outcome["world_before_hash"] == identity["initial_world_hash"], "first outcome changed initial anchor")
        owned_row = _rows([{"observation": first_outcome["before_observation"], "receipt": None},
                           {"observation": first_outcome["after_observation"], "receipt": first_outcome["receipt"]}])[0]
        _require(owned_row["event_id"] not in {row["event_id"] for row in discovery + common}, "owned event duplicates prefix")
        if identity["evidence_mode"] == "retain_first":
            evidence.append(owned_row)
            included.append(scorer.digest(owned_row))
        else:
            excluded.append(scorer.digest(owned_row))
    view = {"schema": "grounded-policy-view-v2", "cohort": deepcopy(state["cohort"]),
            "context": _public_context(current), "evidence": evidence,
            "lifecycle": {"completed": ordinal - 1, "interpreted": int(first_belief is not None)}}
    mask = {"schema": "trusted-evidence-mask-v2", "source_id": SOURCE_ID, "descriptor": SOURCE_DESCRIPTOR,
            "ordinal": ordinal, "mode": identity["evidence_mode"],
            "reason": "stage_one_common" if ordinal == 1 else "explicit_first_update_retained" if
                      identity["evidence_mode"] == "retain_first" else "explicit_first_update_withheld",
            "included": included, "excluded": excluded, "view_hash": scorer.digest(view),
            "projection": "public_features-full-v2", "prior_state_hash": scorer.digest(anchor)}
    _shape(decision["anchor"], ANCHOR_FIELDS, "native anchor")
    _shape(decision["mask"], MASK_FIELDS, "native mask")
    _require(decision["anchor"] == anchor and decision["prior_state_hash"] == scorer.digest(anchor),
             "native prior-state anchor mismatch")
    _require(decision["mask"] == mask and decision["input_view_hash"] == scorer.digest(view),
             "native policy view/mask mismatch")
    return {"view": view, "mask": mask, "anchor": anchor,
            "discovery_rows": discovery, "common_rows": common}


def _q(pair):
    _require(type(pair) is list and len(pair) == 2, "native rational must be a two-string pair")
    value = {"numerator": pair[0], "denominator": pair[1]}
    scorer.rational(value)
    return value


def _forecasts(state, decision, reconstructed):
    body, view = decision["body"], reconstructed["view"]
    _shape(body, BODY_FIELDS, "native decision body")
    _require(body["schema_version"] == "grounded-policy-decision-v2" and body["code_version"] == CODE_VERSION,
             "unsupported decision body")
    _require(body["cohort_digest"] == state["cohort"]["cohort_digest"] and
             body["context"] == _normalized_context(view["context"]) and
             body["context_digest"] == scorer.digest(body["context"]), "native body context/cohort mismatch")
    _require(type(body["menu"]) is list and len(body["menu"]) == 4, "incomplete native menu")
    result = {}
    for direction, row, cohort_action in zip(DIRECTIONS, body["menu"], state["cohort"]["actions"]):
        _shape(row, MENU_FIELDS, "native menu row")
        _require(row["action"] == direction and row["command"] == {"action": direction} and
                 row["cohort_status"] == cohort_action["status"], "native menu action/cohort mismatch")
        _require(all(type(row[key]) is bool for key in ("forecastable", "inquiry_eligible", "selection_eligible")),
                 "nonboolean native menu eligibility")
        for unavailable in _list(row["unavailable_models"], "unavailable models"):
            _shape(unavailable, "model_id reason", "unavailable model")
            _require(unavailable["reason"] in ("missing_position", "missing_predicate_field", "invalid_public_position_output"),
                     "unknown model unavailability reason")
        source_models = {model["model_id"]: model for model in cohort_action["models"] if model["model_id"] != "N"}
        prediction_ids = [prediction.get("model_id") for prediction in _list(row["concrete_predictions"], "concrete predictions")]
        unavailable_ids = [model["model_id"] for model in row["unavailable_models"]]
        _require(len(prediction_ids + unavailable_ids) == len(set(prediction_ids + unavailable_ids)) and
                 set(prediction_ids + unavailable_ids) == set(source_models), "omitted or repeated native concrete model")
        for prediction in _list(row["concrete_predictions"], "concrete predictions"):
            _shape(prediction, "model_id position outcome_class derivation_digest", "native concrete prediction")
            _position(prediction["position"])
            _hash(prediction["derivation_digest"])
            _require(prediction["outcome_class"] in OUTCOMES, "invalid native predicted class")
            _require(prediction["derivation_digest"] == scorer.digest(source_models[prediction["model_id"]]["derivation"]),
                     "native model derivation hash mismatch")
            difference = [prediction["position"][index] - body["context"]["position"][index] for index in (0, 1)]
            expected_class = "zero" if difference == [0, 0] else "displacement" if difference == cohort_action["nonzero_delta"] else "other"
            _require(prediction["outcome_class"] == expected_class, "native prediction class mismatch")
        for posterior in _list(row["posterior"], "native posterior"):
            _shape(posterior, "model_id weight distribution", "native posterior entry")
            _q(posterior["weight"])
            _shape(posterior["distribution"], "zero displacement other", "native model distribution")
            scorer._probabilities([_q(posterior["distribution"][name]) for name in OUTCOMES])
        if not row["forecastable"]:
            expected_reason = cohort_action["status"] if cohort_action["status"] != "available" else "no_available_concrete_models"
            _require(row["forecast_reason"] == row["eligibility_reason"] == row["selection_reason"] == expected_reason and
                     not row["inquiry_eligible"] and not row["selection_eligible"] and
                     not row["concrete_predictions"] and not row["posterior"] and not row["evidence_event_ids"] and
                     all(row[key] is None for key in ("forecast", "unresolved_mass", "predictive_entropy_bits", "expected_model_entropy_bits", "score_bits")),
                     "inconsistent native unavailable row")
            result[direction] = {"status": "unavailable", "reason": row["forecast_reason"]}
            continue
        _require(cohort_action["status"] == "available" and row["forecast_reason"] is None, "forecast from unavailable cohort")
        _shape(row["forecast"], "zero displacement other", "native mixture")
        eligible = [event for event in view["evidence"] if event["action"] == direction and
                    _normalized_context(event["before_context"]) == body["context"]]
        _require(row["evidence_event_ids"] == [event["event_id"] for event in eligible],
                 "native local evidence IDs bypass view mask")
        common_ids = {event["event_id"] for event in reconstructed["common_rows"]}
        local_u = sum(event["event_id"] in common_ids for event in eligible)
        local_e1 = len(eligible) - local_u
        result[direction] = {"status": "available", "probabilities": [_q(row["forecast"][name]) for name in OUTCOMES],
            "nonzero_delta": deepcopy(cohort_action["nonzero_delta"]),
            "concrete_predictions": [{"model_id": prediction["model_id"], "position": deepcopy(prediction["position"])}
                                     for prediction in row["concrete_predictions"]],
            "posterior": [{"model_id": item["model_id"], "weight": _q(item["weight"])} for item in row["posterior"]],
            "unresolved_mass": _q(row["unresolved_mass"]), "local_u_count": local_u, "local_e1_count": local_e1,
            "information_bits": row["score_bits"], "inquiry_eligible": row["inquiry_eligible"],
            "cohort_sha256": scorer.digest(state["cohort"]), "formation": deepcopy(cohort_action)}
        scorer._forecast(result[direction], view["context"])
    return result


def _cases(state, decision, view):
    expected, semantic = [], []
    run, ordinal = state["identity"]["run_id"], decision["ordinal"]
    _list(decision["cases"], "native admitted cases")
    for menu, cohort_action in zip(decision["body"]["menu"], state["cohort"]["actions"]):
        if not menu["inquiry_eligible"]:
            continue
        action = menu["action"]
        source_models = {model["model_id"]: model for model in cohort_action["models"]}
        hypotheses = []
        for prediction in menu["concrete_predictions"]:
            _require(prediction["model_id"] in source_models, "case references absent cohort model")
            derivation = source_models[prediction["model_id"]]["derivation"]
            _require(prediction["derivation_digest"] == scorer.digest(derivation), "prediction derivation differs")
            hypotheses.append({"id": prediction["model_id"], "model_id": prediction["model_id"],
                "position": deepcopy(prediction["position"]), "derivation": deepcopy(derivation),
                "derivation_digest": prediction["derivation_digest"]})
        case = {"id": run + f":case{ordinal}." + action, "experiment_id": run + f":experiment{ordinal}." + action,
                "context": deepcopy(view["context"]), "command": {"action": action}, "hypotheses": hypotheses,
                "cohort_hash": scorer.digest(state["cohort"])}
        case["hash"] = scorer.digest(case)
        expected.append(case)
        semantic.append({**{key: deepcopy(value) for key, value in case.items() if key not in ("id", "experiment_id", "hash")},
                         "id": f"case{ordinal}." + action, "experiment_id": f"experiment{ordinal}." + action})
    _require(decision["cases"] == expected, "native admitted cases differ from complete body/cohort")
    chosen = next((case for case in expected if case["command"]["action"] == decision["body"]["selected_action"]), None)
    status = decision["status"]
    _require(status in ("selected", "policy_null", "capacity_null"), "unsupported decision status")
    _require((decision["body"]["selected_action"] is None) == (status == "policy_null"),
             "native null/body selection mismatch")
    if status == "selected":
        _require(chosen is not None, "selected action has no admitted owner")
        expected_links = {"owner_id": chosen["id"], "experiment_id": chosen["experiment_id"],
                          "command": chosen["command"], "case_hash": chosen["hash"]}
    else:
        _require(status != "capacity_null" or chosen is not None, "capacity null lost native winning case")
        expected_links = {key: None for key in ("owner_id", "experiment_id", "command", "case_hash")}
    _require(all(decision[key] == value for key, value in expected_links.items()), "native selected owner/command mismatch")
    return semantic


def decision_semantics(state, ordinal):
    """Complete comparison/scorer semantics; all native records remain unedited."""
    reconstructed = reconstruct_policy_view(state, ordinal)
    view, mask = reconstructed["view"], reconstructed["mask"]
    decision = state["decisions"][ordinal - 1]
    expected = {"schema": "selection-receipt-v2", "selection_backend": "grounded_policy_v2",
        "producer": "internal-t1-v2", "backend_code_hash": scorer.digest(state["identity"]["code_manifest"]),
        "runtime_hash": scorer.digest(state["identity"]["runtime_manifest"]), "source_id": SOURCE_ID,
        "source_descriptor": SOURCE_DESCRIPTOR, "source_frame_hash": reconstructed["anchor"]["observation_hash"],
        "context_hash": scorer.digest(view["context"]), "proposal_manifest_hash": scorer.digest(state["cohort"]),
        "policy_state_hash": scorer.digest({"cohort": state["cohort"], "body": decision["body"]})}
    _require(all(decision[key] == value for key, value in expected.items()), "native decision envelope mismatch")
    forecasts = _forecasts(state, decision, reconstructed)
    cases = _cases(state, decision, view)
    _, outcome, _ = _stage_records(state, ordinal)
    if outcome:
        _require(scorer.digest(outcome["before_observation"]) == reconstructed["anchor"]["observation_hash"] and
                 outcome["world_before_hash"] == reconstructed["anchor"]["world_hash"], "owned outcome changed decision anchor")
    action = decision["command"]["action"] if decision["command"] else None
    return {"context": deepcopy(view["context"]), "cohort_sha256": scorer.digest(state["cohort"]),
        "forecasts": forecasts,
        "selection": {"command": action, "owner": f"case{ordinal}." + action if action else None,
                      "null_reason": None if action else decision["status"]},
        "lifecycle": deepcopy(view["lifecycle"]),
        "view_evidence": {"view": deepcopy(view), "included": deepcopy(mask["included"]),
                          "excluded": deepcopy(mask["excluded"]), "projection": mask["projection"]},
        "native_body": deepcopy(decision["body"]), "admitted_cases": cases,
        "native_envelope": expected, "native_status": decision["status"]}


def first_decision_semantics(state):
    """Logical initial input plus full first output, for the pre-E1 pair gate."""
    semantics = decision_semantics(state, 1)
    identity = state["identity"]
    _require(state["decisions"][0]["revision"] == 1, "first native selection is not revision one")
    # These are the complete non-run-local identity fields. Source file paths,
    # device/inode/lock identities, run_id, and fixed arm evidence_mode are the
    # only excluded identity fields. Their raw values remain in saved capsules.
    logical = {key: deepcopy(identity[key]) for key in
        ("code_manifest", "runtime_manifest", "profile", "selection_backend", "science_configuration",
         "discovery_count", "adapter", "initial_ora_hash", "initial_world_hash", "initial_frames_hash")}
    logical["source_inputs"] = {name: {key: source[key] for key in ("sha256", "bytes")}
                                for name, source in identity["source_inputs"].items()}
    return {"initial_identity": logical, "frames": deepcopy(state["frames"]),
            "cohort": deepcopy(state["cohort"]), "decision": semantics}


def project_native_stage(state, ordinal, *, case_id, sequence):
    """Convert saved native JSON using exact supplied global ledger positions.

    ``sequence`` must contain t1_committed, outcome_invoked, outcome_durable,
    t3_completed. Values for absent records must be null. Positive integers are
    checked for local order; the controller must establish cross-arm order.
    """
    semantic = decision_semantics(state, ordinal)
    _require(type(case_id) is str and bool(case_id), "missing registered case ID")
    _shape(sequence, "t1_committed outcome_invoked outcome_durable t3_completed", "global ledger mapping")
    committed = _integer(sequence["t1_committed"], "T1 ledger commitment", 1)
    decision, native_outcome, belief = _stage_records(state, ordinal)
    outcome = None
    if native_outcome is None:
        _require(sequence["outcome_invoked"] is None and sequence["outcome_durable"] is None,
                 "ledger supplies absent owned outcome")
    else:
        invoked = _integer(sequence["outcome_invoked"], "owned invocation ledger position", 1)
        durable = _integer(sequence["outcome_durable"], "owned durable ledger position", 1)
        _require(committed < invoked < durable, "global ledger owned order mismatch")
        outcome = public_outcome_semantics(native_outcome)
        outcome["hashes"] = {key: scorer.digest(value) for key, value in outcome.items()}
        outcome.update(invoked_seq=invoked, durable_seq=durable)
    t3 = None
    if belief is None:
        _require(sequence["t3_completed"] is None, "ledger supplies absent interpretation")
    else:
        completed = _integer(sequence["t3_completed"], "T3 ledger completion", 1)
        _require(outcome is not None and completed > outcome["durable_seq"], "global ledger interpretation order mismatch")
        t3_semantics = {"owner": semantic["selection"]["owner"], "experiment": f"experiment{ordinal}." + decision["command"]["action"],
                        "rule": belief["rule"], "evaluations": deepcopy(belief["evaluations"]), "reason": belief["reason"]}
        t3 = {"semantic": t3_semantics, "sha256": scorer.digest(t3_semantics), "completed_seq": completed,
              "outcome_sha256": scorer.digest(outcome)}
    result = {"t1": {"semantic": semantic, "sha256": scorer.digest(semantic), "committed_seq": committed,
                      "provenance": {"case_id": case_id, "decision_id": decision["id"],
                          "run_id": state["identity"]["run_id"], "native_decision": deepcopy(decision),
                          "native_outcome": deepcopy(native_outcome), "native_belief": deepcopy(belief)}},
              "outcome": outcome, "t3": t3}
    scorer._stage(result, case_id, ordinal, semantic["context"], interrupted=True)
    return result


def public_probe_semantics(probe):
    """Validate separate common-probe schema, then compare the same public body.

    Probe identity/chronology/world-source authority remains bound by the trusted
    controller's external ledger. A probe is never forged into a native outcome.
    """
    _shape(probe,"command before_observation receipt after_observation","public probe")
    _shape(probe["command"],"action","probe command")
    _require(probe["command"]["action"] in DIRECTIONS,"invalid probe movement")
    _public_context(probe["before_observation"])
    _public_context(probe["after_observation"])
    _receipt(probe["receipt"],probe["before_observation"],probe["after_observation"])
    _require(probe["receipt"]["action"]==probe["command"]["action"] and probe["receipt"]["target"] is None and probe["receipt"]["direction"] is None,"probe receipt command differs")
    return deepcopy(probe)
