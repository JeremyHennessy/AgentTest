"""Finite, observation-grounded movement policy; no world or authority imports.

Inputs are materialized JSON projections, never callbacks or live objects. Row
order is the authority-verified chronological order. Identifiers establish only
equality; their spelling never orders candidate rules. All probabilities are
exact bounded rationals. Decimal arithmetic is used only for entropy.

This module does not execute an action, issue a capability, or run a study.
"""
from __future__ import annotations

from copy import deepcopy
from contextvars import ContextVar
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import re
from typing import Any

from .primitives import Conflict, bounded, canonical, digest

VERSION = "grounded-policy-v2.1"
ACTIONS = ("north", "east", "south", "west")
FIELDS = ("position", "inventory_ids", "visible_ids")
OUTCOMES = ("zero", "displacement", "other")
MAX_CONDITIONALS = 128
MAX_RETAINED_CONDITIONALS = 5
RATIONAL_DIGITS = 256
# Legacy APIs retain their original numeric contract. Only the named bounded
# exact entrypoints below opt into this separately identified resource envelope.
EXACT_NUMERIC_CONTRACT = "bounded-exact-fractions-8192-v1"
EXACT_RATIONAL_DIGITS = 17_000
EXACT_MAX_EVIDENCE_ROWS = 8192
EXACT_MAX_DISCOVERY_ROWS = 64
EXACT_MAX_MODELS = 8
EXACT_INPUT_BYTES = 8 * 1024 * 1024
EXACT_DECISION_BYTES = 2 * 1024 * 1024
_ACTIVE_RATIONAL_DIGITS = ContextVar("grounded_policy_rational_digits", default=RATIONAL_DIGITS)
_RATIONAL_MAGNITUDES = {RATIONAL_DIGITS: 10 ** RATIONAL_DIGITS,
                        EXACT_RATIONAL_DIGITS: 10 ** EXACT_RATIONAL_DIGITS}
THRESHOLD = Decimal("0.010000000000000000")
TIE_TOLERANCE = Decimal("0.000000000001000000")
QUANTUM = Decimal("0.000000000000000001")
HEX = re.compile(r"[0-9a-f]{64}\Z")
LABEL = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


def _require(test: bool, reason: str) -> None:
    if not test:
        raise Conflict(reason)


def _json(value: Any) -> Any:
    """Reject non-materialized objects, floats, tuples, and hidden callbacks."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is list:
        return [_json(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _json(item) for key, item in value.items()}
    raise Conflict("policy_input_is_not_materialized_json")


def _position(value: Any) -> bool:
    return (type(value) is list and len(value) == 2
            and all(type(x) is int and -2 <= x <= 2 for x in value))


def normalize_context(value: Any) -> dict:
    """Strict allowlist, with missing fields distinct from empty set values."""
    _json(value)
    _require(type(value) is dict, "invalid_policy_context")
    result = {field: deepcopy(value.get(field)) for field in FIELDS}
    _require(result["position"] is None or _position(result["position"]),
             "invalid_context_position")
    for field in FIELDS[1:]:
        ids = result[field]
        if ids is not None:
            _require(type(ids) is list and all(type(x) is str and LABEL.fullmatch(x) for x in ids)
                     and len(ids) == len(set(ids)), "invalid_context_id_set")
            result[field] = sorted(ids)
    inventory, visible = result["inventory_ids"], result["visible_ids"]
    if inventory is not None and visible is not None:
        _require(not set(inventory) & set(visible), "overlapping_context_id_sets")
    for key, item in value.items():
        if key in FIELDS:
            continue
        _require(key.startswith("entity.") and (key.endswith(".position") or key.endswith(".state")),
                 "unallowlisted_context_field")
        suffix = ".position" if key.endswith(".position") else ".state"
        entity_id = key[len("entity."):-len(suffix)]
        _require(bool(LABEL.fullmatch(entity_id)) and visible is not None and entity_id in visible,
                 "unlisted_context_entity")
        _require(item is None or (_position(item) if suffix == ".position" else type(item) is str),
                 "invalid_context_entity_value")
        result[key] = deepcopy(item)
    for entity_id in visible or []:
        result.setdefault(f"entity.{entity_id}.position", None)
        result.setdefault(f"entity.{entity_id}.state", None)
    return result


def normalize_rows(rows: Any) -> list[dict]:
    """Unique projected events in first-delivery order; changed duplicates fail."""
    _json(rows)
    _require(type(rows) is list, "invalid_transition_rows")
    result, seen = [], {}
    for row in rows:
        _require(type(row) is dict and set(row) == {"event_id", "before_context", "action", "after_position", "refs"},
                 "invalid_transition_projection")
        _require(type(row["event_id"]) is str and bool(LABEL.fullmatch(row["event_id"])), "invalid_event_id")
        _require(type(row["action"]) is str and row["action"] in ACTIONS, "nonmovement_policy_action")
        _require(row["after_position"] is None or _position(row["after_position"]), "invalid_transition_position")
        refs = row["refs"]
        _require(type(refs) is dict and set(refs) == {"before", "receipt", "after"}
                 and all(type(ref) is str and HEX.fullmatch(ref) for ref in refs.values()),
                 "invalid_derivation_refs")
        normalized = deepcopy(row)
        normalized["before_context"] = normalize_context(row["before_context"])
        # Compare exact delivered bodies, so contradictory duplicates cannot be
        # hidden by set sorting or explicit-null normalization.
        body = canonical(row)
        event_id = row["event_id"]
        if event_id in seen:
            _require(body == seen[event_id], "changed_body_duplicate_event")
            continue
        seen[event_id] = body
        result.append(normalized)
    return result


def _delta(row: dict) -> list[int] | None:
    before, after = row["before_context"]["position"], row["after_position"]
    if before is None or after is None:
        return None
    return [after[i] - before[i] for i in range(2)]


def _reference(row: dict) -> dict:
    return {"event_id": row["event_id"], "refs": deepcopy(row["refs"])}


def _rule_delta(structure: dict, context: dict) -> list[int] | None:
    if structure["kind"] == "constant":
        return structure["delta"]
    value = context[structure["field"]]
    if value is None:
        return None
    return structure["if_delta"] if value == structure["value"] else structure["else_delta"]


def _prediction(structure: dict, context: dict) -> tuple[list[int] | None, str | None]:
    if context["position"] is None:
        return None, "missing_position"
    delta = _rule_delta(structure, context)
    if delta is None:
        return None, "missing_predicate_field"
    prediction = [context["position"][i] + delta[i] for i in range(2)]
    if not _position(prediction):
        return None, "invalid_public_position_output"
    return prediction, None


def _syntax_length(structure: dict) -> int:
    # Fixed AST token count plus predicate sequence arity, never textual byte
    # length or identifier spelling. The two-coordinate delta is one literal.
    return 2 if structure["kind"] == "constant" else 8 + len(structure["value"])


def _model(structure: dict, order: list[int], rows: list[dict], supporting: list[list[dict]]) -> dict:
    loss = sum(_prediction(structure, row["before_context"])[0] != row["after_position"]
               or row["after_position"] is None for row in rows)
    return {
        "model_id": "rule-" + digest(structure), "structure": deepcopy(structure),
        "code_version": VERSION, "construction_loss": loss,
        "syntax_length": _syntax_length(structure), "structural_order": list(order),
        "derivation": {"construction": [_reference(row) for row in rows],
                       "branches": [[_reference(row) for row in branch] for branch in supporting]},
    }


def _unresolved() -> dict:
    return {"model_id": "N", "structure": {"kind": "unresolved_process"},
            "code_version": VERSION, "derivation": {"kind": "authored_uncertainty_safeguard"}}


def _cohort_shell(rows: list[dict], actions: list[dict]) -> dict:
    result = {"schema_version": "grounded-cohort-v2", "code_version": VERSION,
              "discovery_events": [{"event_id": row["event_id"], "digest": digest(row)} for row in rows],
              "actions": actions}
    result["cohort_digest"] = digest(result)
    return result


def build_cohort(discovery_rows: list[dict]) -> dict:
    """Construct once from D. Complete enumeration, never outcome-based truncation."""
    rows = normalize_rows(discovery_rows)
    actions = []
    for action in ACTIONS:
        records = [row for row in rows if row["action"] == action]
        deltas = []
        for row in records:
            delta = _delta(row)
            if delta is not None and delta not in deltas:
                deltas.append(delta)
        nonzero = [delta for delta in deltas if delta != [0, 0]]
        item = {"action": action, "status": "available", "nonzero_delta": None,
                "observed_deltas": deltas, "conditional_count": 0, "retained_conditional_count": 0,
                "models": []}
        actions.append(item)
        if len(nonzero) > 1:
            item["status"] = "outside_first_model_class"
            continue
        if [0, 0] not in deltas or len(nonzero) != 1:
            item["status"] = "insufficient_explanatory_diversity"
            continue
        item["nonzero_delta"] = nonzero[0]
        constants = [_model({"kind": "constant", "delta": delta}, [index], records,
                            [[row for row in records if _delta(row) == delta]])
                     for index, delta in enumerate(deltas)]
        conditions = []
        count = 0
        for field_index, field in enumerate(FIELDS):
            values = []
            for row in records:
                value = row["before_context"][field]
                if value is not None and value not in values:
                    values.append(value)
            for value_index, value in enumerate(values):
                for delta_index, if_delta in enumerate(deltas):
                    else_index = 1 - delta_index
                    else_delta = deltas[else_index]
                    yes = [row for row in records if row["before_context"][field] == value and _delta(row) == if_delta]
                    no = [row for row in records if row["before_context"][field] is not None
                          and row["before_context"][field] != value and _delta(row) == else_delta]
                    if not yes or not no:
                        continue
                    count += 1
                    if count <= MAX_CONDITIONALS:
                        structure = {"kind": "conditional", "field": field, "value": value,
                                     "if_delta": if_delta, "else_delta": else_delta}
                        conditions.append(_model(structure, [field_index, value_index, delta_index, else_index],
                                                 records, [yes, no]))
        item["conditional_count"] = count
        if count > MAX_CONDITIONALS:
            item["status"] = "generator_capacity_exhausted"
            continue
        conditions.sort(key=lambda model: (model["construction_loss"], model["syntax_length"], model["structural_order"]))
        selected = conditions[:MAX_RETAINED_CONDITIONALS]
        item["retained_conditional_count"] = len(selected)
        item["models"] = constants + selected + [_unresolved()]
    return _cohort_shell(rows, actions)


def _checked(value: Fraction) -> Fraction:
    _require(isinstance(value, Fraction), "nonrational_numeric_value")
    magnitude = _RATIONAL_MAGNITUDES[_ACTIVE_RATIONAL_DIGITS.get()]
    _require(abs(value.numerator) < magnitude and value.denominator < magnitude,
             "rational_component_overflow")
    return value


def _integer_text(value: int) -> str:
    """Exact canonical decimal encoding without changing Python's global limit."""
    if abs(value) < _RATIONAL_MAGNITUDES[RATIONAL_DIGITS]:
        return str(value)
    sign, remaining = ("-", -value) if value < 0 else ("", value)
    chunks = []
    while remaining:
        remaining, chunk = divmod(remaining, 1_000_000_000)
        chunks.append(chunk)
    return sign + str(chunks[-1]) + "".join(f"{chunk:09d}" for chunk in reversed(chunks[:-1]))


def _integer_value(text: str) -> int:
    """Inverse of the exact decimal codec; input syntax/bounds are checked first."""
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    value = 0
    for start in range(0, len(digits), 9):
        chunk = digits[start:start + 9]
        value = value * 10 ** len(chunk) + int(chunk)
    return -value if negative else value


def fraction_pair(value: Fraction) -> list[str]:
    value = _checked(value)
    return [_integer_text(value.numerator), _integer_text(value.denominator)]


def parse_pair(pair: Any) -> Fraction:
    _require(type(pair) is list and len(pair) == 2 and all(type(x) is str for x in pair), "invalid_rational_pair")
    _require(bool(re.fullmatch(r"-?(?:0|[1-9][0-9]*)", pair[0])) and pair[0] != "-0"
             and bool(re.fullmatch(r"[1-9][0-9]*", pair[1])), "noncanonical_rational_pair")
    limit = _ACTIVE_RATIONAL_DIGITS.get()
    _require(len(pair[0].lstrip("-")) <= limit and len(pair[1]) <= limit,
             "rational_component_overflow")
    value = _checked(Fraction(_integer_value(pair[0]), _integer_value(pair[1])))
    _require(fraction_pair(value) == pair, "unreduced_rational_pair")
    return value


def _distribution(predicted_class: str | None) -> list[Fraction]:
    return ([Fraction(1, 3)] * 3 if predicted_class is None else
            [Fraction(38 if outcome == predicted_class else 1, 40) for outcome in OUTCOMES])


def outcome_class(before_position: list[int], after_position: list[int], nonzero_delta: list[int]) -> str:
    _require(_position(before_position) and _position(after_position), "invalid_outcome_positions")
    delta = [after_position[i] - before_position[i] for i in range(2)]
    return "zero" if delta == [0, 0] else "displacement" if delta == nonzero_delta else "other"


def _entropy(probabilities: list[Fraction]) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_EVEN
        log_two = Decimal(2).ln()
        total = Decimal(0)
        for probability in probabilities:
            _checked(probability)
            _require(0 <= probability <= 1, "invalid_probability")
            if probability:
                number = Decimal(probability.numerator) / Decimal(probability.denominator)
                total -= number * number.ln() / log_two
        return +total


def _decimal(value: Decimal) -> str:
    with localcontext() as ctx:
        ctx.prec = 50
        text = format(value.quantize(QUANTUM, rounding=ROUND_HALF_EVEN), "f")
        return "0.000000000000000000" if text == "-0.000000000000000000" else text


def _information(weights: list[Fraction], distributions: list[list[Fraction]], mixture: list[Fraction]) -> dict:
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_EVEN
        predictive = _entropy(mixture)
        expected = sum((Decimal(w.numerator) / Decimal(w.denominator)) * _entropy(p)
                       for w, p in zip(weights, distributions))
        return {"predictive_entropy_bits": _decimal(predictive),
                "expected_model_entropy_bits": _decimal(expected),
                "score_bits": _decimal(predictive - expected)}


def _posterior(distributions: list[list[Fraction]], evidence: list[dict], context: dict, delta: list[int]) -> list[Fraction]:
    weights = [Fraction(1, len(distributions))] * len(distributions)
    for row in evidence:
        outcome = OUTCOMES.index(outcome_class(context["position"], row["after_position"], delta))
        numerators = [_checked(weight * probabilities[outcome]) for weight, probabilities in zip(weights, distributions)]
        total = _checked(sum(numerators, Fraction(0)))
        weights = [_checked(numerator / total) for numerator in numerators]
    return weights


def _mixture(weights: list[Fraction], distributions: list[list[Fraction]]) -> list[Fraction]:
    result = []
    for index in range(3):
        terms = [_checked(weight * probabilities[index]) for weight, probabilities in zip(weights, distributions)]
        result.append(_checked(sum(terms, Fraction(0))))
    _require(sum(result) == 1, "unnormalized_mixture")
    return result


def _validate_cohort(cohort: dict) -> None:
    _json(cohort)
    _require(type(cohort) is dict and set(cohort) == {"schema_version", "code_version", "discovery_events", "actions", "cohort_digest"}, "invalid_cohort")
    _require(cohort["schema_version"] == "grounded-cohort-v2" and cohort["code_version"] == VERSION, "unsupported_cohort_version")
    _require(cohort["cohort_digest"] == digest({key: value for key, value in cohort.items() if key != "cohort_digest"}), "cohort_digest_mismatch")
    _require(type(cohort["actions"]) is list and len(cohort["actions"]) == 4
             and [item.get("action") for item in cohort["actions"]] == list(ACTIONS), "incomplete_cohort_menu")


def _evidence_rows(cohort: dict, evidence_rows: list[dict]) -> list[dict]:
    rows = normalize_rows(evidence_rows)
    discovery_ids = {item["event_id"] for item in cohort["discovery_events"]}
    _require(not discovery_ids & {row["event_id"] for row in rows}, "discovery_counted_as_evidence")
    return rows


def _menu_shell(action: str, status: str) -> dict:
    return {"action": action, "command": {"action": action}, "cohort_status": status,
            "forecastable": False, "forecast_reason": None, "inquiry_eligible": False,
            "eligibility_reason": None, "selection_eligible": False, "selection_reason": None,
            "concrete_predictions": [], "unavailable_models": [], "evidence_event_ids": [],
            "posterior": [], "forecast": None, "unresolved_mass": None,
            "predictive_entropy_bits": None, "expected_model_entropy_bits": None, "score_bits": None}


def _finish_menu(item: dict, predictions: list[dict], distributions: list[list[Fraction]], weights: list[Fraction],
                 mixture: list[Fraction], event_ids: list[str]) -> None:
    item["forecastable"] = True
    item["concrete_predictions"] = predictions
    item["evidence_event_ids"] = event_ids
    ids = [prediction["model_id"] for prediction in predictions] + ["N"]
    item["posterior"] = [{"model_id": model_id, "weight": fraction_pair(weight),
                           "distribution": {outcome: fraction_pair(probability) for outcome, probability in zip(OUTCOMES, distribution)}}
                          for model_id, weight, distribution in zip(ids, weights, distributions)]
    item["forecast"] = {outcome: fraction_pair(probability) for outcome, probability in zip(OUTCOMES, mixture)}
    item["unresolved_mass"] = fraction_pair(weights[-1])
    item.update(_information(weights, distributions, mixture))
    item["inquiry_eligible"] = len({tuple(prediction["position"]) for prediction in predictions}) >= 2
    item["eligibility_reason"] = None if item["inquiry_eligible"] else "insufficient_distinct_concrete_predictions"
    item["selection_eligible"] = item["inquiry_eligible"] and Decimal(item["score_bits"]) > THRESHOLD
    item["selection_reason"] = (None if item["selection_eligible"] else item["eligibility_reason"]
                                or "score_not_above_threshold")


def _choose(menu: list[dict]) -> str | None:
    scores = [Decimal(item["score_bits"]) for item in menu if item["selection_eligible"]]
    if not scores:
        return None
    maximum = max(scores)
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_EVEN
        return next(item["action"] for item in menu if item["selection_eligible"]
                    and maximum - Decimal(item["score_bits"]) <= TIE_TOLERANCE)


def evaluate(cohort: dict, context: dict, evidence_rows: list[dict]) -> dict:
    """Backend producer: complete four-command forecast/menu, then one argmax."""
    _validate_cohort(cohort)
    context = normalize_context(context)
    rows = _evidence_rows(cohort, evidence_rows)
    menu = []
    for action in cohort["actions"]:
        item = _menu_shell(action["action"], action["status"])
        menu.append(item)
        if action["status"] != "available":
            item.update(forecast_reason=action["status"], eligibility_reason=action["status"], selection_reason=action["status"])
            continue
        predictions, distributions = [], []
        for model in action["models"]:
            if model["model_id"] == "N":
                continue
            position, unavailable = _prediction(model["structure"], context)
            if unavailable:
                item["unavailable_models"].append({"model_id": model["model_id"], "reason": unavailable})
                continue
            klass = outcome_class(context["position"], position, action["nonzero_delta"])
            predictions.append({"model_id": model["model_id"], "position": position, "outcome_class": klass,
                                "derivation_digest": digest(model["derivation"])})
            distributions.append(_distribution(klass))
        if not predictions:
            item.update(forecast_reason="no_available_concrete_models", eligibility_reason="no_available_concrete_models",
                        selection_reason="no_available_concrete_models")
            continue
        distributions.append(_distribution(None))
        eligible = [row for row in rows if row["action"] == action["action"] and row["before_context"] == context
                    and row["after_position"] is not None]
        weights = _posterior(distributions, eligible, context, action["nonzero_delta"])
        mixture = _mixture(weights, distributions)
        _finish_menu(item, predictions, distributions, weights, mixture, [row["event_id"] for row in eligible])
    return {"schema_version": "grounded-policy-decision-v2", "code_version": VERSION,
            "cohort_digest": cohort["cohort_digest"], "context": context,
            "context_digest": digest(context), "menu": menu, "selected_action": _choose(menu)}


def brier_loss(forecast: dict, actual_class: str) -> list[str]:
    """Pure three-class half-Brier primitive; never obtains an actual outcome."""
    _require(type(forecast) is dict and set(forecast) == set(OUTCOMES) and actual_class in OUTCOMES, "invalid_brier_input")
    probabilities = [parse_pair(forecast[outcome]) for outcome in OUTCOMES]
    _require(all(0 <= p <= 1 for p in probabilities) and sum(probabilities) == 1, "invalid_brier_distribution")
    terms = [_checked((p - int(outcome == actual_class)) ** 2) for outcome, p in zip(OUTCOMES, probabilities)]
    return fraction_pair(_checked(sum(terms, Fraction(0)) / 2))


# The proof checker deliberately does not call build_cohort, evaluate,
# _prediction, _posterior, _finish_menu, or _choose. It reconstructs source
# derivations and proof assertions instead of asking the backend to select again.
# JSON normalization, bounded rational/entropy primitives and serialization are
# shared; neither verifier function issues a selection capability.
def _verification_prediction(structure: dict, context: dict) -> tuple[list[int] | None, str | None]:
    origin = context.get("position")
    if origin is None:
        return None, "missing_position"
    if structure["kind"] == "conditional":
        observed = context.get(structure["field"])
        if observed is None:
            return None, "missing_predicate_field"
        displacement = structure["else_delta"]
        if observed == structure["value"]:
            displacement = structure["if_delta"]
    else:
        displacement = structure["delta"]
    position = [origin[0] + displacement[0], origin[1] + displacement[1]]
    if not _position(position):
        return None, "invalid_public_position_output"
    return position, None


def _verification_model(structure: dict, order: list[int], records: list[dict], branches: list[list[dict]]) -> dict:
    wrong = 0
    for record in records:
        prediction, reason = _verification_prediction(structure, record["before_context"])
        if reason is not None or record["after_position"] is None or prediction != record["after_position"]:
            wrong += 1
    return {"model_id": "rule-" + digest(structure), "structure": deepcopy(structure),
            "code_version": VERSION, "construction_loss": wrong,
            "syntax_length": 2 if structure["kind"] == "constant" else 8 + len(structure["value"]),
            "structural_order": list(order),
            "derivation": {"construction": [_reference(record) for record in records],
                           "branches": [[_reference(record) for record in branch] for branch in branches]}}


def _reconstruct_cohort(discovery_rows: list[dict]) -> dict:
    records = normalize_rows(discovery_rows)
    proof_actions = []
    for action_name in ACTIONS:
        observations = [record for record in records if record["action"] == action_name]
        observed_displacements, by_displacement = [], {}
        for record in observations:
            origin, destination = record["before_context"]["position"], record["after_position"]
            if origin is None or destination is None:
                continue
            displacement = [destination[0] - origin[0], destination[1] - origin[1]]
            if displacement not in observed_displacements:
                observed_displacements.append(displacement)
            by_displacement.setdefault(tuple(displacement), []).append(record)
        moving = [value for value in observed_displacements if any(value)]
        status = ("outside_first_model_class" if len(moving) > 1 else
                  "insufficient_explanatory_diversity" if len(moving) != 1 or [0, 0] not in observed_displacements else
                  "available")
        entry = {"action": action_name, "status": status, "nonzero_delta": None,
                 "observed_deltas": observed_displacements, "conditional_count": 0,
                 "retained_conditional_count": 0, "models": []}
        proof_actions.append(entry)
        if status != "available":
            continue
        entry["nonzero_delta"] = moving[0]
        constants = []
        for index, displacement in enumerate(observed_displacements):
            constants.append(_verification_model({"kind": "constant", "delta": displacement}, [index],
                                                 observations, [by_displacement[tuple(displacement)]]))
        candidates = []
        complete_count = 0
        for field_index in range(len(FIELDS)):
            field = FIELDS[field_index]
            unique_values = []
            for record in observations:
                actual = record["before_context"][field]
                if actual is not None and actual not in unique_values:
                    unique_values.append(actual)
            for value_index, value in enumerate(unique_values):
                for equal_index in range(2):
                    unequal_index = 1 - equal_index
                    branches = [[], []]
                    for record in observations:
                        actual = record["before_context"][field]
                        if actual is None:
                            continue
                        branch = 0 if actual == value else 1
                        desired = observed_displacements[equal_index if branch == 0 else unequal_index]
                        if record in by_displacement[tuple(desired)]:
                            branches[branch].append(record)
                    if not all(branches):
                        continue
                    complete_count += 1
                    # Enumeration continues through all candidates after overflow.
                    if complete_count <= MAX_CONDITIONALS:
                        syntax = {"kind": "conditional", "field": field, "value": deepcopy(value),
                                  "if_delta": observed_displacements[equal_index],
                                  "else_delta": observed_displacements[unequal_index]}
                        candidates.append(_verification_model(syntax, [field_index, value_index, equal_index, unequal_index],
                                                              observations, branches))
        entry["conditional_count"] = complete_count
        if complete_count > MAX_CONDITIONALS:
            entry["status"] = "generator_capacity_exhausted"
            continue
        ranked = sorted(candidates, key=lambda rule: (rule["construction_loss"], rule["syntax_length"], rule["structural_order"]))
        retained = ranked[:5]
        entry["retained_conditional_count"] = len(retained)
        entry["models"] = constants + retained + [{"model_id": "N", "structure": {"kind": "unresolved_process"},
                                                  "code_version": VERSION,
                                                  "derivation": {"kind": "authored_uncertainty_safeguard"}}]
    cohort = {"schema_version": "grounded-cohort-v2", "code_version": VERSION,
              "discovery_events": [{"event_id": record["event_id"], "digest": digest(record)} for record in records],
              "actions": proof_actions}
    cohort["cohort_digest"] = digest(cohort)
    return cohort


def verify_cohort(discovery_rows: list[dict], cohort: dict) -> bool:
    _json(cohort)
    _require(canonical(cohort) == canonical(_reconstruct_cohort(discovery_rows)), "cohort_derivation_mismatch")
    return True


def verify_evaluation(discovery_rows: list[dict], context: dict, evidence_rows: list[dict], submitted_body: dict) -> bool:
    """Read-only proof check. A mismatch rejects; no replacement result is issued."""
    _json(submitted_body)
    cohort = _reconstruct_cohort(discovery_rows)
    current = normalize_context(context)
    evidence = normalize_rows(evidence_rows)
    discovery_ids = {record["event_id"] for record in normalize_rows(discovery_rows)}
    for event in evidence:
        _require(event["event_id"] not in discovery_ids, "discovery_counted_as_evidence")
    expected_menu = []
    for cohort_action in cohort["actions"]:
        name, status = cohort_action["action"], cohort_action["status"]
        expected = _menu_shell(name, status)
        expected_menu.append(expected)
        if status != "available":
            for key in ("forecast_reason", "eligibility_reason", "selection_reason"):
                expected[key] = status
            continue
        concrete, distributions, unavailable = [], [], []
        for rule in cohort_action["models"]:
            if rule["structure"]["kind"] == "unresolved_process":
                continue
            prediction, reason = _verification_prediction(rule["structure"], current)
            if reason:
                unavailable.append({"model_id": rule["model_id"], "reason": reason})
                continue
            displacement = [prediction[0] - current["position"][0], prediction[1] - current["position"][1]]
            klass = "zero" if displacement == [0, 0] else "displacement" if displacement == cohort_action["nonzero_delta"] else "other"
            concrete.append({"model_id": rule["model_id"], "position": prediction, "outcome_class": klass,
                             "derivation_digest": digest(rule["derivation"])})
            distributions.append([Fraction(38, 40) if label == klass else Fraction(1, 40) for label in OUTCOMES])
        expected["unavailable_models"] = unavailable
        if not concrete:
            for key in ("forecast_reason", "eligibility_reason", "selection_reason"):
                expected[key] = "no_available_concrete_models"
            continue
        distributions.append([Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)])
        count = len(concrete) + 1
        weights = [Fraction(1, count) for _ in range(count)]
        incorporated = []
        for event in evidence:
            if event["action"] != name or event["before_context"] != current or event["after_position"] is None:
                continue
            change = [event["after_position"][j] - current["position"][j] for j in (0, 1)]
            column = 0 if change == [0, 0] else 1 if change == cohort_action["nonzero_delta"] else 2
            unnormalized = [_checked(distributions[index][column] * weights[index]) for index in range(count)]
            normalizer = _checked(sum(unnormalized, Fraction(0)))
            weights = [_checked(value / normalizer) for value in unnormalized]
            incorporated.append(event["event_id"])
        forecast = []
        for column in range(3):
            forecast.append(_checked(sum((_checked(distributions[index][column] * weights[index])
                                          for index in range(count)), Fraction(0))))
        expected["forecastable"] = True
        expected["concrete_predictions"] = concrete
        expected["evidence_event_ids"] = incorporated
        expected["posterior"] = []
        for index in range(count):
            expected["posterior"].append({"model_id": concrete[index]["model_id"] if index < count - 1 else "N",
                                          "weight": fraction_pair(weights[index]),
                                          "distribution": {label: fraction_pair(distributions[index][column])
                                                           for column, label in enumerate(OUTCOMES)}})
        expected["forecast"] = {label: fraction_pair(forecast[index]) for index, label in enumerate(OUTCOMES)}
        expected["unresolved_mass"] = fraction_pair(weights[-1])
        expected.update(_information(weights, distributions, forecast))
        positions = set(tuple(rule["position"]) for rule in concrete)
        expected["inquiry_eligible"] = len(positions) > 1
        if len(positions) <= 1:
            expected["eligibility_reason"] = "insufficient_distinct_concrete_predictions"
            expected["selection_reason"] = "insufficient_distinct_concrete_predictions"
        elif Decimal(expected["score_bits"]) <= Decimal("0.010000000000000000"):
            expected["selection_reason"] = "score_not_above_threshold"
        else:
            expected["selection_eligible"] = True
    qualifying = [(Decimal(item["score_bits"]), index) for index, item in enumerate(expected_menu)
                  if item["selection_eligible"]]
    selected = None
    if qualifying:
        best_score = max(score for score, index in qualifying)
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            winning_index = min(index for score, index in qualifying if abs(score - best_score) <= Decimal("0.000000000001000000"))
        selected = ACTIONS[winning_index]
    expected_body = {"schema_version": "grounded-policy-decision-v2", "code_version": VERSION,
                     "cohort_digest": cohort["cohort_digest"], "context": current,
                     "context_digest": digest(current), "menu": expected_menu, "selected_action": selected}
    _require(canonical(submitted_body) == canonical(expected_body), "selection_receipt_policy_mismatch")
    return True


def _exact_inputs(context: dict, evidence_rows: list[dict], *, cohort: dict | None = None,
                  discovery_rows: list[dict] | None = None) -> None:
    """Finite arithmetic work; this is a resource contract, not evidence sampling."""
    _require(type(evidence_rows) is list and len(evidence_rows) <= EXACT_MAX_EVIDENCE_ROWS,
             "exact_evidence_capacity_exhausted")
    if cohort is not None:
        _require(type(cohort) is dict and type(cohort.get("actions")) is list
                 and len(cohort["actions"]) == len(ACTIONS)
                 and type(cohort.get("discovery_events")) is list
                 and len(cohort["discovery_events"]) <= EXACT_MAX_DISCOVERY_ROWS,
                 "exact_cohort_capacity_exhausted")
        _require(all(type(item.get("models")) is list and len(item["models"]) <= EXACT_MAX_MODELS
                     for item in cohort["actions"]), "exact_model_capacity_exhausted")
    if discovery_rows is not None:
        _require(type(discovery_rows) is list and len(discovery_rows) <= EXACT_MAX_DISCOVERY_ROWS,
                 "exact_discovery_capacity_exhausted")
    bounded({"context": context, "evidence": evidence_rows, "cohort": cohort,
             "discovery": discovery_rows}, EXACT_INPUT_BYTES, "exact policy input")


def evaluate_bounded_exact(cohort: dict, context: dict, evidence_rows: list[dict]) -> dict:
    """Same Fraction/Decimal calculation, with an explicit larger exact envelope."""
    _exact_inputs(context, evidence_rows, cohort=cohort)
    token = _ACTIVE_RATIONAL_DIGITS.set(EXACT_RATIONAL_DIGITS)
    try:
        result = evaluate(cohort, context, evidence_rows)
        result["numeric_contract"] = EXACT_NUMERIC_CONTRACT
        return bounded(result, EXACT_DECISION_BYTES, "exact policy decision")
    finally:
        _ACTIVE_RATIONAL_DIGITS.reset(token)


def verify_bounded_exact_evaluation(discovery_rows: list[dict], context: dict,
                                    evidence_rows: list[dict], submitted_body: dict) -> bool:
    """Independent existing proof checker under the same named exact envelope."""
    _require(type(submitted_body) is dict and submitted_body.get("numeric_contract") == EXACT_NUMERIC_CONTRACT,
             "exact_numeric_contract_mismatch")
    _exact_inputs(context, evidence_rows, discovery_rows=discovery_rows)
    bounded(submitted_body, EXACT_DECISION_BYTES, "exact policy decision")
    body = {key: value for key, value in submitted_body.items() if key != "numeric_contract"}
    token = _ACTIVE_RATIONAL_DIGITS.set(EXACT_RATIONAL_DIGITS)
    try:
        return verify_evaluation(discovery_rows, context, evidence_rows, body)
    finally:
        _ACTIVE_RATIONAL_DIGITS.reset(token)
