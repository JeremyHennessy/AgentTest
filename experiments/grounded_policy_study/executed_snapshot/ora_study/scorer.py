"""Saved-data-only reporter for FIRST_COMPARISON.md v3.

This module never imports an executor, policy, simulator, Core, or selector. It
does not construct scientific observations or run an experiment. A future
reviewed adapter must materialize the following JSON contract. Hash checks bind
bytes; they do NOT authenticate the producer or replace independent source,
authority, masking, resource, and receipt-verifier review.

Saved JSON schema ``ora.frozen-study.saved.v1``:

* Root: schema_version, data_kind (scientific_saved or synthetic_fixture),
  terminal_state (complete, resource_interrupted, integrity_failure), freeze,
  registry, anchors, gates, counters, resources, formation, terminal_detail.
  ``freeze`` maps the three DOCUMENT_HASHES names to their exact hashes.
  ``registry`` has exactly 32 {layout, neutral_t, cases:{R:id,W:id}} entries.
  ``anchors`` is the saved partial/full list of rows for those registry entries.
  ``gates`` maps each GATE_NAMES name to {status: pass/fail/not_reached,
  evidence_sha256: hash-or-null}; these are trusted, externally audited results.
  ``counters`` maps each COUNTER_NAMES name to {known: nonnegative-int,
  unknown: bool}. Known is an exact known count, or a known lower bound when
  unknown is true. Such evidence loss is invalid, even during interruption.
  ``resources``, ``formation``, and ``terminal_detail`` are retained verbatim.
* Anchor: layout, neutral_t, initial_observation, c0, c1,
  cases:{R:{case_id,stages},W:{...}},
  forecast_set, probes. Contexts are exact JSON public_features maps: position,
  sorted inventory_ids, sorted visible_ids, entity.<id>.position and optional
  entity.<id>.state. No IDs or states are transformed when normalizing mirrors.
  During interruption c1/forecast_set may be null and stages/probes incomplete.
* Stage keys are "1" and "2". A saved stage is {t1, outcome, t3} where t1 is
  {semantic, provenance:{case_id,decision_id,run_id}, sha256, committed_seq}.
  Semantic is {context,cohort_sha256,forecasts,selection,lifecycle,view_evidence}.
  Selection is {command: direction-or-null,owner: semantic-owner-or-null,
  null_reason: text-or-null}. Provenance is excluded from paired comparisons;
  all semantic fields are compared. Full original receipts/masks may be kept in
  provenance or view_evidence, but run-local fields belong only in provenance.
  Every committed t1 contains all four direction-keyed forecast rows, including
  unavailable rows, regardless of whether its action/outcome later completed.
* Available forecast: {status:available, probabilities:[Q,Q,Q],
  nonzero_delta:[x,y], concrete_predictions:[{model_id,position}],
  posterior:[{model_id,weight:Q}], unresolved_mass:Q, local_u_count:int,
  local_e1_count:0-or-1, information_bits:18-place-decimal-string,
  inquiry_eligible:bool, cohort_sha256:hash, formation:object}.
  Posterior has one entry per concrete model and the unresolved model "N".
  Unavailable forecast: {status:unavailable, reason:UNAVAILABLE_REASONS member}.
  Q is a reduced {numerator:decimal-string,denominator:positive-decimal-string}
  pair, with each component at most 256 digits. Floats are never accepted.
* ``forecast_set`` is {commands:[directions in frozen order],
  basis:"D/current_C1",context_sha256,cohort_sha256,committed_seq,sha256}.
  Its sha256 covers its other fields. It must follow both second t1 commits
  and precede every second owned invocation and every probe invocation.
* Transition: {command:{action:direction}, before_observation, receipt,
  after_observation, hashes:{command,before_observation,receipt,
  after_observation}, invoked_seq,durable_seq}. Hashes cover their named values.
  Full public observation/receipt contracts are checked independently here.
  ``probes`` is a direction-keyed map containing all four common transitions.
* T3 is {semantic,sha256,completed_seq,outcome_sha256}. Its semantic content is
  retained and compared between first-stage arms; outcome_sha256 binds the
  complete saved transition, or is null for a null selection. Each non-null
  completed decision requires T3 after durable outcome. A null can complete
  with t3=null, since no canonical action interpretation is due.

Sequence numbers are positive integers from the independent global ledger.
Missing committed receipt fields are invalid, including on partial runs.
Unstarted stages/anchors and unfinished outcomes are permitted only when the
controller explicitly reports interruption/failure. The exact registry is still
required, because all 64 cases must have been declared before starting.

Primary context-balanced loss averages available identical-F anchor losses
within each context, then available contexts equally. F-empty losses remain
unavailable, never zero. Every aggregate discloses its actual denominator;
four per-layout denominators and a primary denominator are required. Both the
raw anchor mean and pooled-action micro mean are separately reported. If an
observed context group has no evaluable anchor, its denominator is unavailable;
available-group means remain descriptive but cannot yield a conclusive result.

Synthetic fixtures are never scientific samples: scientific_denominators and
scientific_result are null, and counts appear under fixture_denominators.
The fixed study schedule is metadata, never evidence that any slot executed.
"""

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re


SCHEMA_VERSION = "ora.frozen-study.saved.v1"
DIRECTIONS = ("north", "east", "south", "west")
ANCHOR_TIMES = (32, 36, 40, 44, 48, 52, 56, 60)
EXPECTED_ANCHORS = frozenset((layout, t) for layout in (1, 2, 3, 4)
                             for t in ANCHOR_TIMES)
DOCUMENT_HASHES = {
    "PROTOCOL_V4_EXACT_BYTE_SIGNOFF.md": "d33be2c89ed7e1563f872574d4b7186d31e9507977284dac9c8eacc70471e0dd",
    "FIRST_COMPARISON_V4.md": "0764aab03b99d59cc9eeb9c3aaeac481beda5c955c860e6c3db5f94fd08bda50",
    "AMENDMENT_RECORD.md": "095db08770dcd89a358abcad80562b027abf58c09e23fb8aa9376141f966d80a",
    "PROTOCOL_COHORT_CONSTRUCTION_AMENDMENT_REVIEW_V2.md": "7c0be59220df4b44d578c2a48c4859ba9db647712c768ff89e7701017d6e282f",
    "FIRST_COMPARISON.md": "6f40f7bd8606a0e97f3f18eb4220347309e36892c0872bd4f5ff2721c6881241",
    "POLICY_AND_API.md": "5d1d686afa22a269b5061031c5a75b77121241aee2aac84228473481da4e319d",
    "FINAL_REVIEW.md": "1606e9e72680d9b92e33a6cd98e90302ec5b2a58fb0a66a37db684bf376a0014",
}
GATE_NAMES = ("authority", "source", "leakage", "integrity", "lifecycle",
              "masking", "budget", "receipt_verification", "finalization")
COUNTER_NAMES = ("neutral_invocations", "neutral_durable", "owned_invocations",
                 "owned_durable", "probe_invocations", "probe_durable",
                 "decisions_started", "decisions_committed", "core_cycles",
                 "historical_runs", "provider_calls")
UNAVAILABLE_REASONS = frozenset(("insufficient_explanatory_diversity",
    "outside_first_model_class", "generator_capacity_exhausted",
    "no_available_concrete_models", "invalid_cohort"))
INVALID = "invalid"
INCOMPLETE = "incomplete"
ADVERSE = "adverse observed prediction result"
INCONCLUSIVE = "inconclusive"
NO_BENEFIT = "no demonstrated useful prediction benefit"
PREDICTIVE_ONLY = ("own-outcome predictive benefit only; "
                   "evidence-sensitive selection unestablished")
FULL_PASS = ("finite-corpus own-outcome predictive benefit with "
             "evidence-sensitive test selection")


class SavedDataError(ValueError):
    """The saved data violates the fixed reporting contract."""


def _require(condition, reason):
    if not condition:
        raise SavedDataError(reason)


def canonical_json(value):
    """Canonical public JSON; does not permit non-JSON numeric values."""
    def check(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for child in item.values():
                check(child)
            return
        raise SavedDataError("noncanonical JSON value (including float)")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _hash(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value),
             "invalid SHA-256")
    return value


def _integer(value, minimum=0):
    _require(type(value) is int and value >= minimum, "invalid integer")
    return value


def _text(value):
    _require(type(value) is str and bool(value), "missing nonempty text")
    return value


def rational(value):
    """Read a bounded canonical rational, without binary floating point."""
    _require(type(value) is dict and set(value) == {"numerator", "denominator"},
             "rational requires numerator and denominator")
    n, d = value["numerator"], value["denominator"]
    _require(type(n) is str and type(d) is str, "rational components must be text")
    _require(bool(re.fullmatch(r"0|-?[1-9][0-9]*", n)) and
             bool(re.fullmatch(r"[1-9][0-9]*", d)), "noncanonical rational text")
    _require(len(n.lstrip("-")) <= 256 and len(d) <= 256,
             "rational component exceeds 256 digits")
    result = Fraction(int(n), int(d))
    _require(str(result.numerator) == n and str(result.denominator) == d,
             "rational must be reduced")
    return result


def fraction_json(value):
    """Report exact derived arithmetic; input-only 256-digit limits still hold."""
    if value is None:
        return None
    return {"numerator": _decimal_integer(value.numerator),
            "denominator": _decimal_integer(value.denominator)}


def _decimal_integer(value):
    """Serialize derived integers without changing Python's global digit guard."""
    negative, remaining, chunks = value < 0, abs(value), []
    base = 10 ** 1000
    while remaining >= base:
        remaining, tail = divmod(remaining, base)
        chunks.append(str(tail).zfill(1000))
    return ("-" if negative else "") + str(remaining) + "".join(reversed(chunks))


def _derived_integer(value):
    negative = value.startswith("-")
    digits = value[1:] if negative else value
    result = 0
    for start in range(0, len(digits), 1000):
        piece = digits[start:start+1000]
        result = result * 10 ** len(piece) + int(piece)
    return -result if negative else result


def _derived_fraction(value):
    """Decode our own exact summaries, whose products can exceed input bounds."""
    return Fraction(_derived_integer(value["numerator"]), _derived_integer(value["denominator"]))


def _probabilities(values):
    _require(type(values) is list and len(values) == 3,
             "forecast requires exactly three probabilities")
    result = [rational(value) for value in values]
    _require(all(0 <= value <= 1 for value in result) and sum(result) == 1,
             "probabilities must lie in [0,1] and sum exactly to one")
    return result


def brier_score(probabilities, actual_class):
    """Half the exact three-class squared error; class 0/1/2 is zero/d/other."""
    _require(type(actual_class) is int and actual_class in (0, 1, 2),
             "invalid actual outcome class")
    values = _probabilities(probabilities)
    return sum((p - int(k == actual_class)) ** 2
               for k, p in enumerate(values)) / 2


def _position(value):
    _require(type(value) is list and len(value) == 2 and
             all(type(v) is int for v in value), "missing or invalid position")
    return value


def _identities(values, sorted_required=False):
    _require(type(values) is list and all(type(x) is str and x for x in values),
             "invalid public identities")
    _require(len(values) == len(set(values)), "duplicate public identities")
    _require(not sorted_required or values == sorted(values),
             "context identities must be sorted")
    return values


def _context(value):
    _require(type(value) is dict, "missing exact context")
    _position(value.get("position"))
    _identities(value.get("inventory_ids"), True)
    visible = _identities(value.get("visible_ids"), True)
    allowed = {"position", "inventory_ids", "visible_ids"}
    for entity_id in visible:
        pos, state = f"entity.{entity_id}.position", f"entity.{entity_id}.state"
        _position(value.get(pos))
        allowed.update((pos, state))
        if state in value:
            _require(type(value[state]) is str, "invalid entity public state")
    _require(not (set(value) - allowed), "undeclared context field")
    _require(not (set(visible) & set(value["inventory_ids"])),
             "visible and inventory identities overlap")
    return value


def mirror_context_key(context):
    """Minimum serialization under all four x/y sign flips, evaluator-only."""
    _context(context)
    fields = ["position"] + [f"entity.{i}.position" for i in context["visible_ids"]]
    candidates = []
    for xsign, ysign in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        transformed = deepcopy(context)
        for field in fields:
            x, y = transformed[field]
            transformed[field] = [xsign * x, ysign * y]
        candidates.append(canonical_json(transformed))
    return min(candidates)


def _observation(value):
    fields = {"world_version", "observation_id", "cycle", "position",
              "inventory_ids", "visible_entities"}
    _require(type(value) is dict and set(value) == fields,
             "incomplete or extended public observation")
    _text(value["world_version"])
    cycle = _integer(value["cycle"])
    _require(value["observation_id"] == f"owc-{cycle:06d}",
             "observation ID/cycle mismatch")
    pos = _position(value["position"])
    inventory = _identities(value["inventory_ids"])
    _require(type(value["visible_entities"]) is list, "missing visible entities")
    seen = set(inventory)
    context = {"position": deepcopy(pos), "inventory_ids": sorted(inventory),
               "visible_ids": []}
    for entity in value["visible_entities"]:
        _require(type(entity) is dict and {"id", "position", "appearance"} <= set(entity)
                 and not set(entity) - {"id", "position", "appearance", "observable_state"},
                 "incomplete or extended visible entity")
        entity_id = _text(entity["id"])
        _require(entity_id not in seen, "duplicate entity identity")
        seen.add(entity_id)
        entity_pos = _position(entity["position"])
        _require(sum(abs(a-b) for a, b in zip(pos, entity_pos)) <= 1,
                 "nonlocal entity in public frame")
        _require(type(entity["appearance"]) is str, "invalid appearance")
        context["visible_ids"].append(entity_id)
        context[f"entity.{entity_id}.position"] = deepcopy(entity_pos)
        if "observable_state" in entity:
            _require(type(entity["observable_state"]) is str, "invalid observable state")
            context[f"entity.{entity_id}.state"] = entity["observable_state"]
    context["visible_ids"].sort()
    return context


def _transition(row, direction, expected_before=None):
    _require(type(row) is dict, "missing saved transition")
    _require(row.get("command") == {"action": direction}, "actual command mismatch")
    before, after, receipt = (row["before_observation"], row["after_observation"],
                              row["receipt"])
    before_context, after_context = _observation(before), _observation(after)
    _require(before["world_version"] == after["world_version"], "world version drift")
    _require(after["cycle"] == before["cycle"] + 1, "nonconsecutive public frames")
    required = {"id", "cycle", "action", "target", "direction", "before", "after",
                "success", "blocked", "observed_effects", "visible_entity_states"}
    _require(type(receipt) is dict and required <= set(receipt) and
             not set(receipt) - required - {"inspection"}, "incomplete public receipt")
    _require(receipt["cycle"] == after["cycle"] and type(receipt["cycle"]) is int and
             receipt["id"] == f"OWC-A{after['cycle']:06d}", "receipt ID/cycle mismatch")
    _require(receipt["action"] == direction and receipt["target"] is None and
             receipt["direction"] is None, "receipt/command mismatch")
    _require(receipt["before"] == before["position"] and receipt["after"] == after["position"],
             "receipt/public-frame position mismatch")
    _require(type(receipt["success"]) is bool and type(receipt["blocked"]) is bool,
             "invalid receipt flags")
    _require(type(receipt["observed_effects"]) is list and
             all(type(x) is str for x in receipt["observed_effects"]), "invalid public effects")
    states = receipt["visible_entity_states"]
    _require(type(states) is dict and all(type(k) is str and type(v) is str
             for k, v in states.items()), "invalid public state map")
    expected_states = {e["id"]: e["observable_state"] for e in after["visible_entities"]
                       if "observable_state" in e}
    _require(states == expected_states, "receipt/public-frame visible states mismatch")
    if "inspection" in receipt:
        _require(receipt["inspection"] is None, "movement receipt has unexpected inspection")
    if expected_before is not None:
        _require(before_context == expected_before, "transition starts from wrong public context")
    _require(type(row.get("hashes")) is dict and set(row["hashes"]) ==
             {"command", "before_observation", "receipt", "after_observation"},
             "missing transition hashes")
    for name, saved_hash in row["hashes"].items():
        _require(_hash(saved_hash) == digest(row[name]), f"{name} hash mismatch")
    invoked = _integer(row["invoked_seq"], 1)
    _require(_integer(row["durable_seq"], 1) > invoked, "invalid transition sequence")
    return before_context, after_context


def outcome_class(transition, nonzero_delta):
    """Classify only receipt/public positions, never success or private state."""
    _position(nonzero_delta)
    _require(nonzero_delta != [0, 0], "nonzero displacement is zero")
    before, after = transition["before_observation"], transition["after_observation"]
    _position(before["position"])
    _position(after["position"])
    delta = [b-a for a, b in zip(before["position"], after["position"])]
    return 0 if delta == [0, 0] else 1 if delta == nonzero_delta else 2


def _forecast(row, context):
    _require(type(row) is dict, "missing forecast-or-unavailable row")
    if row.get("status") == "unavailable":
        _require(set(row) == {"status", "reason"} and row["reason"] in UNAVAILABLE_REASONS,
                 "unfrozen or outcome-selected exclusion reason")
        return False
    _require(row.get("status") == "available", "invalid forecast availability")
    _probabilities(row["probabilities"])
    delta = _position(row["nonzero_delta"])
    _require(delta != [0, 0], "zero D-inferred nonzero delta")
    predictions = row["concrete_predictions"]
    _require(type(predictions) is list and 1 <= len(predictions) <= 7,
             "forecast needs one to seven available concrete models")
    ids, positions = set(), set()
    for prediction in predictions:
        _require(type(prediction) is dict and set(prediction) == {"model_id", "position"},
                 "incomplete concrete prediction")
        model_id = _text(prediction["model_id"])
        _require(model_id not in ids and model_id != "N", "duplicate/reserved concrete model ID")
        ids.add(model_id)
        pos = _position(prediction["position"])
        _require(pos in (context["position"], [a+b for a, b in zip(context["position"], delta)]),
                 "concrete prediction outside declared displacement classes")
        positions.add(tuple(pos))
    posterior = row["posterior"]
    _require(type(posterior) is list and len(posterior) == len(ids)+1, "incomplete posterior")
    weights = {}
    for model in posterior:
        _require(type(model) is dict and set(model) == {"model_id", "weight"},
                 "invalid posterior model")
        model_id = _text(model["model_id"])
        _require(model_id not in weights, "duplicate posterior model")
        weights[model_id] = rational(model["weight"])
    _require(set(weights) == ids | {"N"} and sum(weights.values()) == 1 and
             all(0 < weight <= 1 for weight in weights.values()), "invalid posterior distribution")
    _require(rational(row["unresolved_mass"]) == weights["N"], "N mass/posterior mismatch")
    # Independent mixture reconstruction from saved static predictions/weights.
    expected = [weights["N"] / 3] * 3
    for prediction in predictions:
        predicted = 0 if prediction["position"] == context["position"] else 1
        for k in range(3):
            expected[k] += weights[prediction["model_id"]] * Fraction(38 if k == predicted else 1, 40)
    _require(_probabilities(row["probabilities"]) == expected, "mixture/posterior mismatch")
    _integer(row["local_u_count"])
    _require(type(row["local_e1_count"]) is int and row["local_e1_count"] in (0, 1),
             "invalid local E1 count")
    _require(type(row["information_bits"]) is str and
             bool(re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{18}", row["information_bits"])),
             "I score must be a frozen nonnegative 18-place decimal")
    _require(type(row["inquiry_eligible"]) is bool and
             row["inquiry_eligible"] == (len(positions) >= 2), "inquiry eligibility mismatch")
    _hash(row["cohort_sha256"])
    _require(type(row["formation"]) is dict, "missing formation disclosure")
    return True


def _transition_body(row):
    return {key: row[key] for key in ("command", "before_observation", "receipt", "after_observation")}


def _stage(stage, case_id, number, expected_context, interrupted):
    _require(type(stage) is dict and {"t1", "outcome", "t3"} <= set(stage),
             "incomplete saved decision row")
    t1 = stage["t1"]
    semantic = t1["semantic"]
    _require(type(semantic) is dict and {"context", "cohort_sha256", "forecasts", "selection",
             "lifecycle", "view_evidence"} <= set(semantic), "incomplete semantic T1 receipt")
    _require(_context(semantic["context"]) == expected_context, "T1 context mismatch")
    _hash(semantic["cohort_sha256"])
    _require(type(semantic["lifecycle"]) is dict and type(semantic["view_evidence"]) is dict,
             "missing lifecycle or view/mask disclosure")
    _require(_hash(t1["sha256"]) == digest(semantic), "T1 semantic hash mismatch")
    _integer(t1["committed_seq"], 1)
    provenance = t1["provenance"]
    _require(provenance["case_id"] == case_id, "T1 foreign case identity")
    _text(provenance["decision_id"])
    _text(provenance["run_id"])
    forecasts = semantic["forecasts"]
    _require(type(forecasts) is dict and set(forecasts) == set(DIRECTIONS),
             "omitted or extra movement forecast row")
    available = {d for d in DIRECTIONS if _forecast(forecasts[d], expected_context)}
    _require(all(forecasts[d]["cohort_sha256"] == semantic["cohort_sha256"] for d in available),
             "forecast cohort differs from committed T1 cohort")
    if number == 1:
        _require(all(forecasts[d]["local_e1_count"] == 0 for d in available),
                 "first decision contains E1 evidence")
    selection = semantic["selection"]
    _require(type(selection) is dict and set(selection) == {"command", "owner", "null_reason"},
             "incomplete ownership/null receipt")
    command = selection["command"]
    if command is None:
        _require(selection["owner"] is None and type(selection["null_reason"]) is str and
                 bool(selection["null_reason"]), "invalid null receipt")
        _require(stage["outcome"] is None, "null selection has a substitute outcome")
    else:
        _require(command in available and forecasts[command]["inquiry_eligible"],
                 "selected command lacks distinguishing concrete inquiry")
        _text(selection["owner"])
        _require(selection["null_reason"] is None, "owned selection has null reason")
        if stage["outcome"] is None:
            _require(interrupted, "missing owned outcome")
        else:
            _transition(stage["outcome"], command, expected_context)
            _require(stage["outcome"]["invoked_seq"] > t1["committed_seq"],
                     "outcome invocation precedes frozen T1")
    t3 = stage["t3"]
    if t3 is None:
        _require(command is None or interrupted, "missing canonical T3")
    else:
        _require(type(t3["semantic"]) is dict and _hash(t3["sha256"]) == digest(t3["semantic"]),
                 "T3 semantic hash mismatch")
        outcome = stage["outcome"]
        _require(command is None or outcome is not None, "T3 without an owned outcome")
        expected_hash = digest(outcome) if outcome is not None else None
        _require(t3["outcome_sha256"] == expected_hash, "T3 does not bind persisted outcome")
        predecessor = outcome["durable_seq"] if outcome is not None else t1["committed_seq"]
        _require(_integer(t3["completed_seq"], 1) > predecessor, "T3 out of order")
    return available


def _choice_key(selection):
    """Null explanation differences are disclosures, not different tests."""
    return (None,None) if selection["command"] is None else (selection["command"],selection["owner"])


def classify(*, invalid, interrupted, adverse, coverage, denominators_available,
             benefit, choice_differences, choice_context_groups, discriminating_differences):
    """Frozen ordered decision rule, also independently testable on exact scalars."""
    if invalid:
        return INVALID
    if interrupted:
        return INCOMPLETE
    if adverse:
        return ADVERSE
    if not coverage or not denominators_available or benefit is None:
        return INCONCLUSIVE
    if benefit < Fraction(1, 20):
        return NO_BENEFIT
    if choice_differences < 4 or choice_context_groups < 2 or discriminating_differences < 4:
        return PREDICTIVE_ONLY
    return FULL_PASS


def _mean(values):
    return sum(values, Fraction()) / len(values) if values else None


def _loss_summary(rows, actions=False):
    usable = [row for row in rows if row.get("loss_R") is not None]
    r, w = [], []
    for row in usable:
        if actions:
            r.extend(action["loss_R"] for action in row["_actions"])
            w.extend(action["loss_W"] for action in row["_actions"])
        else:
            r.append(row["loss_R"])
            w.append(row["loss_W"])
    rmean, wmean = _mean(r), _mean(w)
    return {"anchors_observed": len(rows), "anchors_evaluable": len(usable),
            "anchors_unavailable": len(rows)-len(usable), "denominator": len(r),
            "loss_R": fraction_json(rmean), "loss_W": fraction_json(wmean),
            "benefit_W_minus_R": fraction_json(wmean-rmean) if rmean is not None else None}


def _serialize_fractions(value):
    if isinstance(value, Fraction):
        return fraction_json(value)
    if type(value) is dict:
        return {key: _serialize_fractions(child) for key, child in value.items() if not key.startswith("_")}
    if type(value) is list:
        return [_serialize_fractions(child) for child in value]
    return value


def _anchor(row, registry, interrupted):
    _integer(row["layout"], 1)
    _integer(row["neutral_t"])
    key = (row["layout"], row["neutral_t"])
    _require(key in registry, "unscheduled anchor")
    c0 = _context(row["c0"])
    initial = row["initial_observation"]
    _require(_observation(initial) == c0, "initial frame/context mismatch")
    c1 = row.get("c1")
    if c1 is not None:
        _context(c1)
    else:
        _require(interrupted, "missing post-first context")
    cases = row["cases"]
    _require(type(cases) is dict and set(cases) == {"R", "W"}, "missing paired cases")
    stages = {}
    for arm in ("R", "W"):
        case = cases[arm]
        _require(case["case_id"] == registry[key][arm], "case does not match registry")
        stages[arm] = case["stages"]
        _require(type(stages[arm]) is dict and not set(stages[arm]) - {"1", "2"},
                 "extra decision stage")
        _require(interrupted or set(stages[arm]) == {"1", "2"}, "omitted scheduled decision")
        for number, stage in stages[arm].items():
            _stage(stage, case["case_id"], int(number), c0 if number == "1" else c1, interrupted)
            if number == "1" and stage["outcome"] is not None:
                _require(stage["outcome"]["before_observation"] == initial,
                         "first outcome does not start from full initial frame")
    first_pair = all("1" in stages[arm] for arm in ("R", "W"))
    first_null, local_e1 = None, False
    if first_pair:
        first_r, first_w = stages["R"]["1"], stages["W"]["1"]
        _require(first_r["t1"]["semantic"] == first_w["t1"]["semantic"],
                 "first-stage arms differ")
        first_null = first_r["t1"]["semantic"]["selection"]["command"] is None
        last_first_commit = max(first_r["t1"]["committed_seq"], first_w["t1"]["committed_seq"])
        for first in (first_r, first_w):
            if first["outcome"] is not None:
                _require(first["outcome"]["invoked_seq"] > last_first_commit,
                         "first effect precedes both first T1 commitments")
        if first_r["outcome"] is not None and first_w["outcome"] is not None:
            _require(_transition_body(first_r["outcome"]) == _transition_body(first_w["outcome"]),
                     "first-stage public outcomes differ")
        for first in (first_r, first_w):
            if c1 is not None:
                if first_null:
                    _require(c1 == c0, "first-null context changed")
                elif first["outcome"] is not None:
                    _require(_observation(first["outcome"]["after_observation"]) == c1,
                             "C1 does not match first outcome")
        if first_r["t3"] is not None and first_w["t3"] is not None:
            _require(first_r["t3"]["semantic"] == first_w["t3"]["semantic"],
                     "first-stage canonical interpretations differ")
    else:
        _require(all("1" not in stages[arm] or stages[arm]["1"]["outcome"] is None
                     for arm in ("R", "W")), "first effect without both first T1 commitments")
    second_pair = all("2" in stages[arm] for arm in ("R", "W"))
    if any("2" in stages[arm] for arm in ("R", "W")):
        _require(first_pair, "second decision without paired first decisions")
        if not first_null:
            _require(all(stages[arm]["1"]["outcome"] is not None and
                         stages[arm]["1"]["t3"] is not None for arm in ("R", "W")),
                     "second T1 precedes durable first T3")
        completed = max(stages[arm]["1"]["t3"]["completed_seq"]
                        if stages[arm]["1"]["t3"] is not None
                        else stages[arm]["1"]["t1"]["committed_seq"] for arm in ("R", "W"))
        _require(all("2" not in stages[arm] or stages[arm]["2"]["t1"]["committed_seq"] > completed
                     for arm in ("R", "W")), "second T1 precedes both completed first lifecycles")
        if not second_pair:
            _require(all("2" not in stages[arm] or stages[arm]["2"]["outcome"] is None
                         for arm in ("R", "W")), "second effect without both second T1 commitments")
    summary = {"layout": key[0], "neutral_t": key[1],
               "context_key": mirror_context_key(c1) if c1 is not None else None,
               "forecast_commands": None, "loss_R": None, "loss_W": None,
               "benefit_W_minus_R": None, "actions": [], "_actions": [],
               "first_null": first_null, "local_e1_in_F": False,
               "choice_difference": False, "R_distinguishes_on_difference": False,
               "first_owned_scores": {}, "choices": {}}
    for arm in ("R", "W"):
        summary["choices"][arm] = {n: deepcopy(s["t1"]["semantic"]["selection"])
                                   for n, s in stages[arm].items()}
        if "1" in stages[arm] and stages[arm]["1"]["outcome"] is not None:
            first = stages[arm]["1"]
            direction = first["t1"]["semantic"]["selection"]["command"]
            forecast = first["t1"]["semantic"]["forecasts"][direction]
            actual = outcome_class(first["outcome"], forecast["nonzero_delta"])
            summary["first_owned_scores"][arm] = {"command": direction, "actual_class": actual,
                "loss": brier_score(forecast["probabilities"], actual),
                "probabilities": deepcopy(forecast["probabilities"]), "primary_sample": False}
    probes = row.get("probes", {})
    _require(type(probes) is dict and not set(probes) - set(DIRECTIONS), "extra probe command")
    _require(interrupted or set(probes) == set(DIRECTIONS), "missing common probe")
    forecast_set = row.get("forecast_set")
    if not second_pair:
        _require(not probes and forecast_set is None, "probe/set before both second T1 commits")
        return summary
    _require(first_pair, "second decision without paired first decisions")
    second = {arm: stages[arm]["2"] for arm in ("R", "W")}
    if first_null:
        _require(second["R"]["t1"]["semantic"] == second["W"]["t1"]["semantic"],
                 "first-null pair differs at second stage")
    for arm in ("R", "W"):
        first, current = stages[arm]["1"], second[arm]
        if not first_null:
            _require(first["outcome"] is not None and first["t3"] is not None,
                     "second T1 precedes durable first T3")
        predecessor = first["t3"]["completed_seq"] if first["t3"] is not None else first["t1"]["committed_seq"]
        _require(current["t1"]["committed_seq"] > predecessor, "second T1 out of order")
    first_completion = max(stages[arm]["1"]["t3"]["completed_seq"]
                           if stages[arm]["1"]["t3"] is not None
                           else stages[arm]["1"]["t1"]["committed_seq"] for arm in ("R", "W"))
    _require(all(second[arm]["t1"]["committed_seq"] > first_completion for arm in ("R", "W")),
             "second T1 precedes both completed first lifecycles")
    semantics = {arm: second[arm]["t1"]["semantic"] for arm in ("R", "W")}
    _require(semantics["R"]["cohort_sha256"] == semantics["W"]["cohort_sha256"], "arm cohort differs")
    _require(semantics["R"]["cohort_sha256"] == stages["R"]["1"]["t1"]["semantic"]["cohort_sha256"],
             "frozen D cohort changed between stages")
    _require(semantics["R"]["lifecycle"] == semantics["W"]["lifecycle"], "arm lifecycle differs")
    forecasts = {arm: semantics[arm]["forecasts"] for arm in ("R", "W")}
    expected_F = []
    e1 = stages["R"]["1"]["outcome"]
    for direction in DIRECTIONS:
        r, w = forecasts["R"][direction], forecasts["W"][direction]
        _require(r["status"] == w["status"], "arm forecast availability differs")
        if r["status"] == "unavailable":
            _require(r == w, "arm unavailable reasons differ")
            continue
        expected_F.append(direction)
        for name in ("nonzero_delta", "concrete_predictions", "cohort_sha256", "local_u_count",
                     "inquiry_eligible", "formation"):
            _require(r[name] == w[name], f"arm {name} differs")
        expected_e1 = int(e1 is not None and _observation(e1["before_observation"]) == c1
                          and e1["command"] == {"action": direction})
        _require(r["local_e1_count"] == expected_e1 and w["local_e1_count"] == 0,
                 "wrong retained/withheld local E1 accounting")
        retained = {p["model_id"]: rational(p["weight"]) for p in r["posterior"]}
        withheld = {p["model_id"]: rational(p["weight"]) for p in w["posterior"]}
        if expected_e1:
            actual = outcome_class(e1, r["nonzero_delta"])
            expected_weights = {"N": withheld["N"] / 3}
            for prediction in r["concrete_predictions"]:
                predicted = 0 if prediction["position"] == c1["position"] else 1
                expected_weights[prediction["model_id"]] = (withheld[prediction["model_id"]]
                    * Fraction(38 if predicted == actual else 1, 40))
            normalizer = sum(expected_weights.values())
            expected_weights = {model_id: weight / normalizer for model_id, weight in expected_weights.items()}
            _require(retained == expected_weights, "retained posterior is not exact common-U plus eligible E1 update")
        else:
            _require(retained == withheld, "ineligible E1 changed arm posterior")
        local_e1 = local_e1 or bool(expected_e1)
    if forecast_set is None:
        _require(interrupted and not probes, "missing pre-outcome forecast-set commitment")
        return summary
    _require(type(forecast_set) is dict and set(forecast_set) ==
             {"commands", "basis", "context_sha256", "cohort_sha256", "committed_seq", "sha256"},
             "incomplete forecast-set commitment")
    _require(forecast_set["commands"] == expected_F and forecast_set["basis"] == "D/current_C1",
             "forecast set not exactly common pre-outcome availability")
    _require(forecast_set["context_sha256"] == digest(c1) and
             forecast_set["cohort_sha256"] == semantics["R"]["cohort_sha256"],
             "forecast set context/cohort binding mismatch")
    _require(forecast_set["sha256"] == digest({k: v for k, v in forecast_set.items() if k != "sha256"}),
             "forecast-set hash mismatch")
    set_seq = _integer(forecast_set["committed_seq"], 1)
    _require(set_seq > max(second[a]["t1"]["committed_seq"] for a in ("R", "W")),
             "forecast set predates second T1 commitments")
    for direction, probe in probes.items():
        _transition(probe, direction, c1)
        expected_frame = e1["after_observation"] if e1 is not None else initial
        _require(probe["before_observation"] == expected_frame,
                 "probe does not start from full post-first frame")
        _require(probe["invoked_seq"] > set_seq, "probe preview before forecast-set commitment")
    summary["forecast_commands"] = expected_F
    summary["local_e1_in_F"] = local_e1
    for arm in ("R", "W"):
        owned = second[arm]["outcome"]
        if owned is not None:
            _require(owned["before_observation"] == (e1["after_observation"] if e1 is not None else initial),
                     "second owned outcome does not start from full post-first frame")
            _require(owned["invoked_seq"] > set_seq, "second owned outcome before shared F freeze")
            direction = semantics[arm]["selection"]["command"]
            if direction not in probes:
                _require(interrupted, "missing probe for owned second action")
            else:
                _require(_transition_body(owned) == _transition_body(probes[direction]),
                         "second owned outcome differs from common probe")
    summary["choice_difference"] = _choice_key(semantics["R"]["selection"]) != _choice_key(semantics["W"]["selection"])
    summary["null_reason_difference"] = (semantics["R"]["selection"]["command"] is None and semantics["W"]["selection"]["command"] is None and semantics["R"]["selection"]["null_reason"] != semantics["W"]["selection"]["null_reason"])
    r_owned = second["R"]["outcome"]
    if summary["choice_difference"] and r_owned is not None:
        command = semantics["R"]["selection"]["command"]
        positions = [p["position"] for p in forecasts["R"][command]["concrete_predictions"]]
        actual_pos = r_owned["after_observation"]["position"]
        summary["R_distinguishes_on_difference"] = any(p == actual_pos for p in positions) and any(p != actual_pos for p in positions)
    for direction in expected_F:
        if direction not in probes:
            continue
        actual = outcome_class(probes[direction], forecasts["R"][direction]["nonzero_delta"])
        action = {"command": direction, "actual_class": actual,
                  "receipt": deepcopy(probes[direction]["receipt"]),
                  "probabilities_R": deepcopy(forecasts["R"][direction]["probabilities"]),
                  "probabilities_W": deepcopy(forecasts["W"][direction]["probabilities"]),
                  "loss_R": brier_score(forecasts["R"][direction]["probabilities"], actual),
                  "loss_W": brier_score(forecasts["W"][direction]["probabilities"], actual),
                  "local_u_count": forecasts["R"][direction]["local_u_count"],
                  "local_e1_count_R": forecasts["R"][direction]["local_e1_count"],
                  "unresolved_mass_R": deepcopy(forecasts["R"][direction]["unresolved_mass"]),
                  "unresolved_mass_W": deepcopy(forecasts["W"][direction]["unresolved_mass"]),
                  "information_bits_R": forecasts["R"][direction]["information_bits"],
                  "information_bits_W": forecasts["W"][direction]["information_bits"]}
        summary["actions"].append(action)
        summary["_actions"].append(action)
    if expected_F and len(summary["actions"]) == len(expected_F):
        summary["loss_R"] = _mean([a["loss_R"] for a in summary["actions"]])
        summary["loss_W"] = _mean([a["loss_W"] for a in summary["actions"]])
        summary["benefit_W_minus_R"] = summary["loss_W"] - summary["loss_R"]
    return summary


def load_saved_json(path):
    """Read only an existing JSON file; reject duplicate keys and all floats."""
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SavedDataError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def bad_number(_):
        raise SavedDataError("JSON numbers must be integers; use rational pairs")
    with Path(path).open("r", encoding="utf-8") as saved:
        return json.load(saved, object_pairs_hook=unique, parse_float=bad_number,
                         parse_constant=bad_number)


def score_saved_study(payload):
    """Return an exact report, preserving every supplied row and counter.

    Invalid anchors are retained in ``saved_input`` and ``invalid_anchor_rows``;
    their trustworthy sibling anchors can still be described, but never used to
    rescue the terminal invalid status. No exception is a silent exclusion.
    """
    errors, rows, registry = [], [], {}
    supplied = deepcopy(payload)
    if type(payload) is not dict:
        return {"classification": INVALID, "errors": ["root must be an object"],
                "saved_input": supplied, "scientific_result": None,
                "scientific_denominators": None, "fixture_denominators": None}
    interrupted = payload.get("terminal_state") in ("resource_interrupted", "integrity_failure")
    fixture = payload.get("data_kind") == "synthetic_fixture"
    def check(label, operation):
        try:
            return operation()
        except (SavedDataError, KeyError, TypeError, IndexError, AttributeError) as exc:
            errors.append(label + ": " + str(exc))
            return None
    check("canonical JSON", lambda: canonical_json(payload))
    check("schema", lambda: _require(payload.get("schema_version") == SCHEMA_VERSION, "wrong schema version"))
    check("kind", lambda: _require(payload.get("data_kind") in ("scientific_saved", "synthetic_fixture"), "unknown data kind"))
    check("terminal", lambda: _require(payload.get("terminal_state") in
          ("complete", "resource_interrupted", "integrity_failure"), "unknown terminal state"))
    check("freeze", lambda: _require(payload.get("freeze") == DOCUMENT_HASHES, "reviewed document hashes differ"))
    if payload.get("terminal_state") == "integrity_failure":
        errors.append("controller reports integrity failure")
    def validate_registry():
        values = payload["registry"]
        _require(type(values) is list and len(values) == 32, "registry must contain exactly 32 anchors")
        ids = set()
        for value in values:
            _require(type(value) is dict and set(value) == {"layout", "neutral_t", "cases"}, "invalid registry entry")
            _integer(value["layout"], 1)
            _integer(value["neutral_t"])
            key = (value["layout"], value["neutral_t"])
            _require(key in EXPECTED_ANCHORS and key not in registry, "duplicate or unexpected anchor")
            cases = value["cases"]
            _require(type(cases) is dict and set(cases) == {"R", "W"}, "registry must have both arms")
            for case_id in cases.values():
                _text(case_id)
                _require(case_id not in ids, "duplicate arm case ID")
                ids.add(case_id)
            registry[key] = cases
        _require(set(registry) == EXPECTED_ANCHORS and len(ids) == 64, "incomplete case registry")
    check("registry", validate_registry)
    gates = payload.get("gates", {})
    for gate_name in GATE_NAMES:
        def validate_gate(name=gate_name):
            gate = gates[name]
            _require(type(gate) is dict and set(gate) == {"status", "evidence_sha256"}, "invalid gate receipt")
            _require(gate["status"] in ("pass", "fail", "not_reached"), "invalid gate status")
            _require(gate["status"] != "fail", "trusted review/controller gate failed")
            if gate["status"] == "pass":
                _hash(gate["evidence_sha256"])
            else:
                _require(interrupted and gate["evidence_sha256"] is None, "required gate not satisfied")
        check("gate " + gate_name, validate_gate)
    counters = payload.get("counters", {})
    known = {}
    for name in COUNTER_NAMES:
        def validate_counter(n=name):
            counter = counters[n]
            _require(type(counter) is dict and set(counter) == {"known", "unknown"}, "invalid exact counter")
            count = _integer(counter["known"])
            _require(type(counter["unknown"]) is bool, "unknown flag must be boolean")
            known[n] = count
            _require(not counter["unknown"], "count contains unknown remainder")
        check("counter " + name, validate_counter)
    def validate_budgets():
        _require(sum(known[n] for n in ("neutral_invocations", "owned_invocations", "probe_invocations")) <= 512,
                 "global simulator invocation ceiling exceeded")
        _require(known["neutral_durable"] <= 256 and known["owned_durable"] <= 128 and
                 known["probe_durable"] <= 128 and known["decisions_started"] <= 128 and
                 known["decisions_committed"] <= known["decisions_started"], "fixed slot budget exceeded")
        for kind in ("neutral", "owned", "probe"):
            _require(known[kind + "_durable"] <= known[kind + "_invocations"], "durable count exceeds invocations")
        _require(all(known[n] == 0 for n in ("core_cycles", "historical_runs", "provider_calls")),
                 "forbidden work counter is nonzero")
        if not interrupted:
            _require(known["neutral_durable"] == 256 and known["probe_durable"] == 128 and
                     known["decisions_committed"] == 128, "completed run lacks fixed horizon counts")
    check("budgets", validate_budgets)
    anchor_values = payload.get("anchors", [])
    if type(anchor_values) is not list:
        errors.append("anchors must be a list")
        anchor_values = []
    seen, invalid_rows, decision_ids, layout_cohorts = set(), [], set(), {}
    observed = {"anchors": len(anchor_values), "arm_cases": 0, "decisions_committed": 0,
                "owned_outcomes": 0, "probes": 0, "nulls": 0, "blocked_owned": 0,
                "forecast_rows": 0}
    # Count all structurally supplied rows independently of validity. A malformed
    # sibling must not erase later supplied data from observed-row accounting.
    # These are counts of claimed saved rows, not independent ledger attestations.
    for anchor in anchor_values:
        if type(anchor) is not dict:
            continue
        cases = anchor.get("cases", {})
        if type(cases) is dict:
            for case in cases.values():
                observed["arm_cases"] += 1
                if type(case) is not dict or type(case.get("stages")) is not dict:
                    continue
                for stage in case["stages"].values():
                    observed["decisions_committed"] += 1
                    if type(stage) is not dict:
                        continue
                    t1 = stage.get("t1")
                    semantic = t1.get("semantic", {}) if type(t1) is dict else {}
                    if type(semantic) is dict:
                        forecasts, selection = semantic.get("forecasts"), semantic.get("selection")
                        if type(forecasts) is dict:
                            observed["forecast_rows"] += len(forecasts)
                        if type(selection) is dict and "command" in selection and selection["command"] is None:
                            observed["nulls"] += 1
                    if stage.get("outcome") is not None:
                        observed["owned_outcomes"] += 1
                        outcome = stage["outcome"]
                        receipt = outcome.get("receipt") if type(outcome) is dict else None
                        if type(receipt) is dict and receipt.get("blocked") is True:
                            observed["blocked_owned"] += 1
        if type(anchor.get("probes")) is dict:
            observed["probes"] += len(anchor["probes"])
    for index, anchor in enumerate(anchor_values):
        def count_and_validate_anchor(a=anchor):
            key = (a["layout"], a["neutral_t"])
            _require(key not in seen, "duplicate saved anchor")
            seen.add(key)
            for arm in ("R", "W"):
                case = a["cases"][arm]
                for stage in case["stages"].values():
                    provenance = stage["t1"]["provenance"]
                    decision_id = (provenance["run_id"], provenance["decision_id"])
                    _require(decision_id not in decision_ids, "duplicate decision identity")
                    decision_ids.add(decision_id)
                    semantic = stage["t1"]["semantic"]
                    cohort = _hash(semantic["cohort_sha256"])
                    _require(a["layout"] not in layout_cohorts or layout_cohorts[a["layout"]] == cohort,
                             "frozen D cohort differs within layout")
                    layout_cohorts[a["layout"]] = cohort
            return _anchor(a, registry, interrupted)
        result = check("anchor " + str(index), count_and_validate_anchor)
        if result is None:
            invalid_rows.append(index)
        else:
            rows.append(result)
    if not interrupted and seen != EXPECTED_ANCHORS:
        errors.append("complete report omits scheduled anchor rows")
    for label, saved_name in (("decisions_committed", "decisions_committed"),
                               ("owned_outcomes", "owned_durable"), ("probes", "probe_durable")):
        if saved_name in known:
            if observed[label] > known[saved_name] or (not interrupted and observed[label] != known[saved_name]):
                errors.append("saved rows/independent ledger mismatch: " + label)
    per_layout = {str(layout): {
        **_loss_summary([row for row in rows if row["layout"] == layout]),
        "scheduled_anchors": 8,
        "saved_anchor_rows": sum(type(a) is dict and a.get("layout") == layout for a in anchor_values),
        "missing_or_invalid_anchor_slots": 8-sum(row["layout"] == layout for row in rows)}
        for layout in (1, 2, 3, 4)}
    contexts = sorted({row["context_key"] for row in rows if row["context_key"] is not None})
    per_context = [{"context_key": key, **_loss_summary([r for r in rows if r["context_key"] == key])}
                   for key in contexts]
    context_r = [_derived_fraction(c["loss_R"]) for c in per_context if c["loss_R"] is not None]
    context_w = [_derived_fraction(c["loss_W"]) for c in per_context if c["loss_W"] is not None]
    primary_r, primary_w = _mean(context_r), _mean(context_w)
    benefit = primary_w-primary_r if primary_r is not None else None
    adequate = [r for r in rows if r["forecast_commands"] is not None and len(r["forecast_commands"]) >= 2]
    local = [r for r in adequate if r["local_e1_in_F"]]
    differences = [r for r in rows if r["choice_difference"]]
    coverage = {"anchors_with_at_least_two_commands": len(adequate),
                "layouts_with_at_least_two_commands": len({r["layout"] for r in adequate}),
                "contexts_with_at_least_two_commands": len({r["context_key"] for r in adequate}),
                "local_E1_anchors_among_adequate": len(local),
                "local_E1_layouts": len({r["layout"] for r in local}),
                "local_E1_contexts": len({r["context_key"] for r in local}),
                "complete_forecast_rows": observed["forecast_rows"] == 512,
                "choice_differences": len(differences),
                "choice_difference_contexts": len({r["context_key"] for r in differences}),
                "discriminating_R_difference_anchors": sum(r["R_distinguishes_on_difference"] for r in differences)}
    sufficient = (len(adequate) >= 16 and coverage["layouts_with_at_least_two_commands"] == 4
                  and coverage["contexts_with_at_least_two_commands"] >= 4 and len(local) >= 8
                  and coverage["local_E1_layouts"] >= 2 and coverage["local_E1_contexts"] >= 2
                  and coverage["complete_forecast_rows"] and observed["decisions_committed"] == 128)
    evaluable_layouts = [summary for summary in per_layout.values() if summary["loss_R"] is not None]
    adverse = any(_derived_fraction(s["loss_R"])-_derived_fraction(s["loss_W"]) > Fraction(1, 40)
                  for s in evaluable_layouts)
    denominators_available = (len(evaluable_layouts) == 4 and benefit is not None
                              and len(context_r) == len(contexts))
    classification = classify(invalid=bool(errors), interrupted=interrupted, adverse=adverse,
        coverage=sufficient, denominators_available=denominators_available, benefit=benefit,
        choice_differences=len(differences), choice_context_groups=coverage["choice_difference_contexts"],
        discriminating_differences=coverage["discriminating_R_difference_anchors"])
    denominator_report = {"observed_saved_rows": observed,
        "observed_saved_rows_are_unverified_claims": True, "validated_anchors": len(rows),
        "validated_decisions": sum(len(stages) for row in rows for stages in row["choices"].values()),
        "invalid_anchor_rows": len(invalid_rows), "evaluable_anchors": sum(r["loss_R"] is not None for r in rows),
        "F_empty_anchors": sum(r["forecast_commands"] == [] for r in rows),
        "forecast_set_unavailable_anchors": sum(r["forecast_commands"] is None for r in rows),
        "expected_commands_in_F": sum(len(r["forecast_commands"] or []) for r in rows),
        "scored_common_actions": sum(len(r["actions"]) for r in rows),
        "other_common_outcomes": sum(a["actual_class"] == 2 for r in rows for a in r["actions"]),
        "contexts_observed": len(contexts), "contexts_evaluable": len(context_r)}
    return {"schema_version": "ora.frozen-study.report.v1", "data_kind": payload.get("data_kind"),
        "classification": classification, "classification_scope": "synthetic_fixture_only" if fixture else "saved_scientific_data",
        "scientific_result": None if fixture else classification,
        "scientific_denominators": None if fixture else denominator_report,
        "fixture_denominators": denominator_report if fixture else None,
        "fixed_schedule_not_observed_counts": {"anchors": 32, "arm_cases": 64, "decisions": 128,
            "neutral_transitions": 256, "probes": 128, "maximum_owned_transitions": 128,
            "maximum_simulator_invocations": 512},
        "errors": errors, "invalid_anchor_rows": invalid_rows,
        "coverage": {**coverage, "sufficient": sufficient, "required_denominators_available": denominators_available,
                     "evaluable_layout_guard_breached": adverse},
        "context_balanced": {"loss_R": fraction_json(primary_r), "loss_W": fraction_json(primary_w),
            "benefit_W_minus_R": fraction_json(benefit), "context_denominator": len(context_r),
            "unavailable_context_denominators": len(contexts)-len(context_r)},
        "raw_anchor_mean": _loss_summary(rows), "micro_action_mean": _loss_summary(rows, True),
        "per_layout": per_layout, "per_context": per_context, "anchors": _serialize_fractions(rows),
        "counters": deepcopy(counters), "resources": deepcopy(payload.get("resources")),
        "formation": deepcopy(payload.get("formation")), "terminal_detail": deepcopy(payload.get("terminal_detail")),
        "saved_input": supplied,
        "limits": ["Mirrored layouts and evaluator probes are not independent scientific samples.",
            "Changed choices do not establish comparative action utility or efficient exploration.",
            "No result establishes generalization, open-ended learning, or live activation."]}
