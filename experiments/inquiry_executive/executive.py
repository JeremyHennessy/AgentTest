"""Restart-safe ownership for one copied, deterministic Challenge world.

No policy gets the private world. Admission is passive; real ordinary selection
is internal. This proves transaction wiring, never learning or live authority.
"""
from __future__ import annotations

import hashlib
import uuid
from copy import deepcopy
from pathlib import Path

from challenge_action_authority import _validate_inquiry_source, _find_experiment
from challenge_shadow_epistemic_selector import POLICY, select_epistemic_command
from challenge_shadow_recorder import (ChallengeShadowRecorder, SOURCE_ID,
    SOURCE_DESCRIPTOR_HASH, STATE_KEY, public_features, validate_observation,
    validate_receipt as _legacy_receipt)
from open_object_world_challenge import WORLD_VERSION, observe_world, transition
from open_object_world_challenge_explorer import candidate_commands
from .bridge import MemoryStore, run_cycle
from .contracts import (VERSION, RULE, RECORD_CAP, COMPLETION_RESERVE,
    INTERPRETATION_RESERVE, T2_GROWTH_BOUND, T3_GROWTH_BOUND, Conflict, Capacity,
    bounded, canonical, code_manifest, digest, encoded, exact, hypotheses,
    integer, label, profile, strict_json, unique, validate_profile,
    validate_world, verify_seal, ensure_capacity, integral_metadata,
    strict_receipt as validate_receipt)
from .store import CapsuleStore, read_regular

_LOADED_CODE = None


def _code():
    global _LOADED_CODE
    current = code_manifest()
    if _LOADED_CODE is None:
        _LOADED_CODE = current
    if current != _LOADED_CODE:
        raise Conflict("source code changed after loading; restart with reviewed code")
    return current


def _hash_record(row):
    return digest({k: v for k, v in row.items() if k != "hash"})


def _checked_hash(row, what):
    if row.get("hash") != _hash_record(row):
        raise Conflict(f"{what} immutable body mismatch")


def _id(state, kind, number):
    return f"{state['identity']['run_id']}:{kind}{number:08d}"


def _source(path):
    payload, info = read_regular(path)
    return dict(path=str(Path(path)), sha256=hashlib.sha256(payload).hexdigest(),
                device=info.st_dev, inode=info.st_ino, bytes=len(payload)), strict_json(payload)


def _validate_sources(identity):
    copies = {}
    for name, expected in identity["source_inputs"].items():
        actual, copied = _source(expected["path"])
        if canonical(actual) != canonical(expected):
            raise Conflict("pinned copied source changed")
        copies[name] = copied
    return copies


def _memory(ora, path):
    return MemoryStore(deepcopy(ora), Path(path))


def _recorder(ora, path):
    memory = _memory(ora, path)
    return memory, ChallengeShadowRecorder(memory, enabled=True)


def _frame(state, observation, receipt):
    validate_observation(observation)
    if state["frames"]:
        validate_receipt(receipt, state["frames"][-1]["observation"], observation)
    elif receipt is not None or observation["cycle"] != 0:
        raise Conflict("initial source frame must be cycle zero")
    index = len(state["frames"]) + 1
    row = dict(id=_id(state, "F", index), source_id=SOURCE_ID,
               world_id=state["identity"]["adapter"]["world_id"], actor="agent",
               sequence=index, predecessor=state["frames"][-1]["hash"] if index > 1 else None,
               observation=deepcopy(observation), receipt=deepcopy(receipt),
               payload_hash=digest(observation))
    row["hash"] = _hash_record(row)
    bounded(row, what="public frame")
    return row


def _rebuild_recorder(state, frames=None):
    memory, recorder = _recorder({}, state["identity"]["source_inputs"]["ora"]["path"])
    for frame in state["frames"] if frames is None else frames:
        recorder.ingest(frame["observation"], frame["receipt"])
    result = memory.load()[STATE_KEY]
    bounded(result, 131_072, "recorder checkpoint")
    return result


def _one(state, field, identifier):
    matches = [r for r in state.get(field, []) if r.get("id") == identifier]
    if len(matches) != 1:
        raise Conflict(f"ambiguous or missing {field} identity")
    return matches[0]


def _semantic(question, experiment):
    return dict(question={k: deepcopy(question.get(k)) for k in (
        "id", "text", "source", "native_inquiry_candidate_id", "native_relation",
        "source_evidence_refs")}, experiment={k: deepcopy(experiment.get(k)) for k in (
        "id", "question_id", "native_inquiry_candidate_id", "native_inquiry",
        "hypothesis", "method", "falsification", "predicted_observation")})


def _validate_grounding(state, inquiry, *, current=True):
    origin = inquiry["origin"]
    exact(origin, "frame_id publication ora recorder contract hash", "origin")
    _checked_hash(origin, "original grounding")
    frame = _one(state, "frames", origin["frame_id"])
    prefix = state["frames"][:frame["sequence"]]
    if canonical(_rebuild_recorder(state, prefix)) != canonical(origin["recorder"]):
        raise Conflict("original public grounding chain mismatch")
    frozen = deepcopy(origin["ora"])
    frozen[STATE_KEY] = deepcopy(origin["recorder"])
    _, recorder = _recorder(frozen, state["identity"]["source_inputs"]["ora"]["path"])
    experiment = _find_experiment(frozen, inquiry["experiment_id"])
    _validate_inquiry_source(frozen, experiment, recorder, origin["recorder"], frame["observation"])
    if canonical(recorder.publication()) != canonical(origin["publication"]):
        raise Conflict("original publication mismatch")
    question = _one(frozen, "questions", inquiry["question_id"])
    if canonical(_semantic(question, experiment)) != canonical(origin["contract"]):
        raise Conflict("original semantic binding mismatch")
    if current:
        question = _one(state["ora"], "questions", inquiry["question_id"])
        experiment = _one(state["ora"], "experiments", inquiry["experiment_id"])
        if canonical(_semantic(question, experiment)) != canonical(origin["contract"]):
            raise Conflict("current inquiry meaning/binding changed")
    return origin["publication"]["selected_temporal_candidate"]


def _event(state, kind, reference):
    state["revision"] += 1
    row = dict(revision=state["revision"], kind=kind, reference=reference,
               predecessor=state["events"][-1]["hash"] if state["events"] else None)
    row["hash"] = _hash_record(row)
    bounded(row, 4_096, "transition event")
    state["events"].append(row)


def _cancel(state):
    for attempt in state["attempts"]:
        if attempt["status"] == "prepared":
            attempt["status"] = "cancelled"
    state["reserve"] = 0


def _blocked(state):
    if any(a["status"] == "committed" for a in state["attempts"]):
        raise Conflict("interpretation_pending: recover the committed outcome first")


def _prediction(inquiry, frame, command):
    feature = inquiry["origin"]["publication"]["selected_temporal_candidate"]["feature"]
    features = public_features(frame["observation"])
    if feature not in features:
        return None
    result = dict(version="bounded-public-prediction-v1", feature=feature,
                  frame_id=frame["id"], frame_hash=frame["hash"],
                  command=deepcopy(command), before_value=deepcopy(features[feature]),
                  hypotheses=deepcopy(inquiry["hypothesis_versions"][-1]["hypotheses"]),
                  context={"version": "selected-public-feature-v1", "feature": feature,
                           "value": deepcopy(features[feature]), "missing": False})
    # Normalize public tuples, so restarts preserve exact canonical shape.
    result = strict_json(canonical(result))
    bounded(result, 32_768, "frozen prediction")
    return result


def _interpret(attempt, outcome, frame):
    prediction = attempt["contract"]["prediction"]
    feature = prediction["feature"]
    features = strict_json(canonical(public_features(frame["observation"])))
    results = []
    for hypothesis in prediction["hypotheses"]:
        rule = hypothesis["prediction"]
        if feature not in features or rule["kind"] == "unavailable":
            verdict = "unevaluable"
        else:
            actual = features[feature]
            if rule["kind"] == "equal":
                supported = actual == prediction["before_value"]
            elif rule["kind"] == "different":
                supported = actual != prediction["before_value"]
            else:
                supported = actual in rule["values"]
            verdict = "supports_this_case" if supported else "contradicts_this_case"
        results.append({"hypothesis_id": hypothesis["id"], "verdict": verdict})
    standing = {row["verdict"] for row in results}
    reason = ("missing_evidence" if standing == {"unevaluable"}
              else "alternatives_undiscriminated" if len(standing) == 1
              else "case_local_discrimination_only")
    return results, reason


def validate_capsule(state, *, verify_checksum=True):
    exact(state, "version identity identity_hash revision counters ora world recorder frames inquiries decisions attempts outcomes beliefs events reserve seal", "capsule")
    if state["version"] != VERSION:
        raise Conflict("unsupported capsule schema")
    integer(state["revision"], 0, 1_000_000, "capsule revision")
    integer(state["reserve"], 0, COMPLETION_RESERVE, "completion reserve")
    if verify_checksum:
        verify_seal(state)
    identity = state["identity"]
    exact(identity, "run_id path research_dir filesystem source_inputs code_manifest profile adapter initial_ora_hash initial_world_hash initial_frame_count", "identity")
    label(identity["run_id"])
    exact(identity["filesystem"], "directory lock", "filesystem identity")
    for pair in identity["filesystem"].values():
        if not isinstance(pair, list) or len(pair) != 2:
            raise Conflict("invalid filesystem identity pair")
        for number in pair:
            integer(number, 0, 2**64-1, "filesystem identity number")
    if state["identity_hash"] != digest(identity):
        raise Conflict("immutable run/profile identity mismatch")
    validate_profile(identity["profile"])
    if identity["code_manifest"] != _code():
        raise Conflict("source code manifest mismatch")
    exact(identity["source_inputs"], "ora world observations", "source inputs")
    copied_sources = _validate_sources(identity)
    integer(identity["initial_frame_count"], 1, 1_000_001, "initial frame count")
    if (identity["initial_frame_count"] != len(copied_sources["observations"])
        or identity["initial_ora_hash"] != digest(copied_sources["ora"])
        or identity["initial_world_hash"] != digest(copied_sources["world"])):
        raise Conflict("initial copied source identity mismatch")
    exact(identity["adapter"], "source_id descriptor world_id actor sensor grammar", "adapter")
    expected_adapter = dict(source_id=SOURCE_ID, descriptor=SOURCE_DESCRIPTOR_HASH,
        world_id=identity["initial_world_hash"], actor="agent", sensor=WORLD_VERSION,
        grammar="challenge-candidate-commands-v1")
    if identity["adapter"] != expected_adapter:
        raise Conflict("source/world/actor descriptor mismatch")
    exact(state["counters"], "inquiries decisions attempts outcomes beliefs actions", "counters")
    limits = identity["profile"]
    for key in ("inquiries", "decisions", "attempts", "outcomes", "beliefs"):
        integer(state["counters"][key], 0, 1_000_000, key)
        if state["counters"][key] != len(state[key]):
            raise Conflict("counter/lineage mismatch")
    if state["counters"]["decisions"] > limits["max_decisions"]:
        raise Capacity("decision capacity exhausted")
    integer(state["counters"]["actions"], 0, limits["max_actions"], "consumed actions")
    if state["counters"]["actions"] != len(state["outcomes"]):
        raise Conflict("consumed action/outcome mismatch")
    if state["revision"] != len(state["events"]):
        raise Conflict("revision/event mismatch")
    for index, event in enumerate(state["events"], 1):
        exact(event, "revision kind reference predecessor hash", "event")
        integer(event["revision"], 1, 1_000_000, "event revision")
        bounded(event, 4_096, "transition event")
        _checked_hash(event, "event")
        if event["revision"] != index or event["predecessor"] != (state["events"][index-2]["hash"] if index > 1 else None):
            raise Conflict("transition event chain mismatch")
    validate_world(state["world"])
    frames = unique(state["frames"], "frames")
    if not frames:
        raise Conflict("missing public source frames")
    initial = identity["initial_frame_count"]
    if len(frames) != initial + state["counters"]["actions"]:
        raise Conflict("frame/action sequence mismatch")
    for index, frame in enumerate(state["frames"], 1):
        exact(frame, "id source_id world_id actor sequence predecessor observation receipt payload_hash hash", "frame")
        integer(frame["sequence"], 1, 1_000_001, "frame sequence")
        if index <= initial and {"observation": frame["observation"], "receipt": frame["receipt"]} != copied_sources["observations"][index-1]:
            raise Conflict("initial public evidence differs from pinned source")
        bounded(frame, what="public frame")
        _checked_hash(frame, "public frame")
        if (frame["id"] != _id(state, "F", index) or frame["sequence"] != index
            or frame["source_id"] != SOURCE_ID or frame["world_id"] != identity["adapter"]["world_id"]
            or frame["actor"] != "agent" or frame["payload_hash"] != digest(frame["observation"])
            or frame["predecessor"] != (state["frames"][index-2]["hash"] if index > 1 else None)):
            raise Conflict("frame identity/sequence/source mismatch")
        validate_observation(frame["observation"])
        if frame["observation"]["cycle"] != index - 1:
            raise Conflict("nonadjacent observation cycle")
        if index > 1:
            validate_receipt(frame["receipt"], state["frames"][index-2]["observation"], frame["observation"])
            if frame["receipt"] != state["world"]["history"][index-2]:
                raise Conflict("world/public receipt mismatch")
        elif frame["receipt"] is not None:
            raise Conflict("initial frame has receipt")
    if state["frames"][-1]["observation"] != observe_world(state["world"]):
        raise Conflict("current public frame/world mismatch")
    if canonical(_rebuild_recorder(state)) != canonical(state["recorder"]):
        raise Conflict("recorder/public chain mismatch")
    if canonical(state["ora"].get(STATE_KEY)) != canonical(state["recorder"]):
        raise Conflict("Core recorder copy mismatch")
    inquiries = unique(state["inquiries"], "inquiries")
    decisions = unique(state["decisions"], "decisions")
    attempts = unique(state["attempts"], "attempts")
    outcomes = unique(state["outcomes"], "outcomes")
    beliefs = unique(state["beliefs"], "beliefs")
    question_ids, experiment_ids, texts = set(), set(), set()
    for index, inquiry in enumerate(state["inquiries"], 1):
        exact(inquiry, "id question_id experiment_id question origin hypothesis_versions current_belief status predecessor successor", "inquiry")
        if inquiry["id"] != _id(state, "I", index) or inquiry["status"] not in {"open", "suspended", "closed"}:
            raise Conflict("invalid inquiry identity/status")
        if inquiry["question_id"] in question_ids or inquiry["experiment_id"] in experiment_ids or inquiry["question"] in texts:
            raise Conflict("binding_conflict")
        question_ids.add(inquiry["question_id"]); experiment_ids.add(inquiry["experiment_id"]); texts.add(inquiry["question"])
        if len(inquiry["hypothesis_versions"]) != 1:
            raise Conflict("first slice retains one immutable hypothesis version per meaning")
        version = inquiry["hypothesis_versions"][0]
        exact(version, "version hypotheses hash", "hypothesis version")
        integer(version["version"], 1, 1, "hypothesis version")
        _checked_hash(version, "hypothesis version")
        if version["version"] != 1:
            raise Conflict("unsupported hypothesis version")
        hypotheses(version["hypotheses"])
        _validate_grounding(state, inquiry)
        owned_beliefs = [b for b in state["beliefs"] if b["inquiry_id"] == inquiry["id"]]
        latest_belief = owned_beliefs[-1]["id"] if owned_beliefs else None
        if inquiry["current_belief"] != latest_belief:
            raise Conflict("current belief is not latest canonical belief for inquiry")
        if inquiry["question"] != inquiry["origin"]["contract"]["question"]["text"]:
            raise Conflict("inquiry question meaning changed")
        if inquiry["predecessor"] is not None or inquiry["successor"] is not None:
            raise Conflict("meaning migration is not implemented in this bounded slice")
    for index, decision in enumerate(state["decisions"], 1):
        exact(decision, "id bridge inquiry_id attempt_id deferral_reason hash", "decision")
        _checked_hash(decision, "decision")
        if decision["id"] != _id(state, "D", index):
            raise Conflict("decision identity mismatch")
        if decision["inquiry_id"] is not None and decision["inquiry_id"] not in inquiries:
            raise Conflict("decision inquiry missing")
        if decision["attempt_id"] is not None and decision["attempt_id"] not in attempts:
            raise Conflict("decision attempt missing")
        # Full immutable bridge output includes the actual ordinary selector result.
        bridge = decision["bridge"]
        if bridge["pre_state_hash"] != digest(bridge["pre_state"]) or bridge["post_state_hash"] != digest(bridge["post_state"]):
            raise Conflict("decision Core snapshots changed")
    pending = []
    for index, attempt in enumerate(state["attempts"], 1):
        exact(attempt, "id contract contract_hash status outcome_id belief_id", "attempt")
        contract = attempt["contract"]
        exact(contract, "inquiry_id decision_id hypothesis_version hypothesis_hash belief_id command policy prediction frame_id frame_hash world_hash ora_hash adapter identity_hash code_hash expected_revision budget_ordinal question_contract_hash experiment_contract_hash", "attempt contract")
        integer(contract["hypothesis_version"], 1, 1, "attempt hypothesis version")
        integer(contract["expected_revision"], 0, 1_000_000, "attempt expected revision")
        integer(contract["budget_ordinal"], 1, 8, "attempt budget ordinal")
        if attempt["id"] != _id(state, "A", index) or attempt["contract_hash"] != digest(contract):
            raise Conflict("attempt contract/identity mismatch")
        inquiry = inquiries.get(contract["inquiry_id"])
        decision = decisions.get(contract["decision_id"])
        if inquiry is None or decision is None or decision["attempt_id"] != attempt["id"] or decision["inquiry_id"] != inquiry["id"]:
            raise Conflict("attempt ownership mismatch")
        selection = decision["bridge"]["selection"]
        if not selection or not selection["owned"] or selection["question_id"] != inquiry["question_id"] or selection["experiment_id"] != inquiry["experiment_id"]:
            raise Conflict("attempt lacks exact ordinary ownership")
        if (contract["identity_hash"] != state["identity_hash"] or contract["adapter"] != identity["adapter"]
                or contract["code_hash"] != digest(identity["code_manifest"])):
            raise Conflict("attempt source/run/code mismatch")
        version = inquiry["hypothesis_versions"][0]
        if contract["hypothesis_version"] != 1 or contract["hypothesis_hash"] != version["hash"]:
            raise Conflict("attempt hypothesis changed")
        frame = frames.get(contract["frame_id"])
        if frame is None or contract["frame_hash"] != frame["hash"]:
            raise Conflict("attempt public frame changed")
        if canonical(contract["prediction"]) != canonical(_prediction(inquiry, frame, contract["command"])):
            raise Conflict("frozen prediction changed")
        semantic = inquiry["origin"]["contract"]
        if (contract["question_contract_hash"] != digest(semantic["question"])
            or contract["experiment_contract_hash"] != digest(semantic["experiment"])):
            raise Conflict("attempt semantic owner changed")
        if contract["command"] not in candidate_commands(frame["observation"]):
            raise Conflict("command unavailable in bound public frame")
        if attempt["status"] not in {"prepared", "cancelled", "committed", "interpreted"}:
            raise Conflict("invalid attempt lifecycle")
        if attempt["status"] in {"prepared", "committed"}:
            pending.append(attempt)
        earlier_attempts = {a["id"] for a in state["attempts"][:index-1]}
        earlier_beliefs = [b for b in state["beliefs"] if b["inquiry_id"] == inquiry["id"] and b["attempt_id"] in earlier_attempts]
        if contract["belief_id"] != (earlier_beliefs[-1]["id"] if earlier_beliefs else None):
            raise Conflict("attempt references stale or foreign belief")
        if attempt["status"] == "interpreted":
            matching = [b for b in state["beliefs"] if b["attempt_id"] == attempt["id"]]
            if len(matching) != 1 or attempt["belief_id"] != matching[0]["id"]:
                raise Conflict("interpreted attempt missing canonical belief")
        elif attempt["belief_id"] is not None:
            raise Conflict("uninterpreted attempt carries belief")
        if attempt["status"] == "prepared":
            if (contract["expected_revision"] != state["revision"]
                or contract["budget_ordinal"] != state["counters"]["actions"]+1
                or contract["world_hash"] != digest(state["world"])
                or contract["ora_hash"] != digest(state["ora"])
                or contract["frame_id"] != state["frames"][-1]["id"]
                or contract["belief_id"] != inquiry["current_belief"]
                or inquiry["status"] != "open"
                or decision is not state["decisions"][-1]):
                raise Conflict("prepared authority is stale")
        if attempt["status"] in {"prepared", "cancelled"}:
            if attempt["outcome_id"] is not None or attempt["belief_id"] is not None:
                raise Conflict("unconsumed authority has outcome")
        else:
            outcome = outcomes.get(attempt["outcome_id"])
            if outcome is None or outcome["attempt_id"] != attempt["id"]:
                raise Conflict("consumed authority missing full outcome")
    if len(pending) > 1:
        raise Conflict("multiple current capabilities")
    expected_reserve = (COMPLETION_RESERVE if pending and pending[0]["status"] == "prepared"
                        else INTERPRETATION_RESERVE if pending else 0)
    if state["reserve"] != expected_reserve:
        raise Conflict("completion reservation mismatch")
    for index, outcome in enumerate(state["outcomes"], 1):
        exact(outcome, "id attempt_id decision_id inquiry_id receipt before_frame_id after_frame_id world_before_hash world_after_hash observation_status hash", "outcome")
        _checked_hash(outcome, "outcome")
        if outcome["observation_status"] != "complete_public_sensor":
            raise Conflict("unsupported outcome observation status")
        bounded(outcome, 3*RECORD_CAP+16_384, "full outcome")
        attempt = attempts.get(outcome["attempt_id"])
        if (outcome["id"] != _id(state, "O", index) or attempt is None
            or outcome["decision_id"] != attempt["contract"]["decision_id"]
            or outcome["inquiry_id"] != attempt["contract"]["inquiry_id"]
            or outcome["world_before_hash"] != attempt["contract"]["world_hash"]
            or attempt["outcome_id"] != outcome["id"]
            or attempt["contract"]["budget_ordinal"] != index
            or outcome["world_before_hash"] != (state["outcomes"][index-2]["world_after_hash"] if index > 1 else identity["initial_world_hash"])):
            raise Conflict("outcome lineage mismatch")
        before, after = frames.get(outcome["before_frame_id"]), frames.get(outcome["after_frame_id"])
        if before is None or after is None or after["sequence"] != before["sequence"]+1 or outcome["receipt"] != after["receipt"] or before["id"] != attempt["contract"]["frame_id"]:
            raise Conflict("outcome evidence transplanted/nonadjacent")
        validate_receipt(outcome["receipt"], before["observation"], after["observation"])
        if canonical(outcome["receipt"]) != canonical(after["receipt"]):
            raise Conflict("outcome receipt differs from saved public receipt")
        if index == len(state["outcomes"]) and outcome["world_after_hash"] != digest(state["world"]):
            raise Conflict("latest world outcome hash mismatch")
    consumed = set()
    for index, belief in enumerate(state["beliefs"], 1):
        exact(belief, "id inquiry_id attempt_id outcome_id predecessor hypothesis_version prediction_hash outcome_hash rule evaluations unresolved_alternatives reason hash", "belief")
        integer(belief["hypothesis_version"], 1, 1, "belief hypothesis version")
        bounded(belief, what="belief record")
        _checked_hash(belief, "belief")
        if belief["id"] != _id(state, "B", index) or belief["outcome_id"] in consumed:
            raise Conflict("duplicate canonical interpretation")
        consumed.add(belief["outcome_id"])
        attempt = attempts.get(belief["attempt_id"]); outcome = outcomes.get(belief["outcome_id"])
        if attempt is None or outcome is None or attempt["belief_id"] != belief["id"] or attempt["status"] != "interpreted" or outcome["attempt_id"] != attempt["id"]:
            raise Conflict("belief/outcome ownership mismatch")
        if (belief["rule"] != RULE or belief["prediction_hash"] != digest(attempt["contract"]["prediction"])
            or belief["outcome_hash"] != outcome["hash"] or belief["inquiry_id"] != outcome["inquiry_id"]
            or belief["predecessor"] != attempt["contract"]["belief_id"]):
            raise Conflict("interpretation provenance changed")
        evaluations, reason = _interpret(attempt, outcome, frames[outcome["after_frame_id"]])
        prior = [b for b in state["beliefs"][:index-1] if b["inquiry_id"] == belief["inquiry_id"]]
        unresolved = [r["hypothesis_id"] for r in evaluations if r["verdict"] != "contradicts_this_case"]
        if (belief["evaluations"] != evaluations or belief["reason"] != reason
            or belief["hypothesis_version"] != 1 or belief["unresolved_alternatives"] != unresolved
            or belief["predecessor"] != (prior[-1]["id"] if prior else None)):
            raise Conflict("belief differs from frozen prediction/outcome/lineage")
    expected_ora = deepcopy(state["decisions"][-1]["bridge"]["post_state"] if state["decisions"] else copied_sources["ora"])
    expected_ora[STATE_KEY] = deepcopy(state["recorder"])
    if canonical(state["ora"]) != canonical(expected_ora):
        raise Conflict("current Core state differs from its committed source/selection snapshot")
    integral_metadata(state)
    ensure_capacity(state)


class InquiryExecutive:
    def __init__(self, path, *, research_dir, enabled=False):
        self.store = CapsuleStore(path, research_dir, enabled=enabled)
        self.store.read()  # Never create missing state on reopen.

    @classmethod
    def create(cls, path, *, research_dir, source_paths, enabled=False, limits=None):
        store = CapsuleStore(path, research_dir, enabled=enabled)
        exact(source_paths, "ora world observations", "copied source paths")
        identities, copied = {}, {}
        for key, value in source_paths.items():
            identities[key], copied[key] = _source(value)
            if Path(value) in {store.path, store.root / store.lock_name}:
                raise Conflict("output aliases source")
        if len({(row["device"], row["inode"]) for row in identities.values()}) != 3:
            raise Conflict("copied source aliases")
        validate_world(copied["world"])
        limits = profile() if limits is None else deepcopy(limits)
        validate_profile(limits)
        if limits["name"] == "preserved_input_smoke" and limits["input_hash"] != identities["ora"]["sha256"]:
            raise Conflict("smoke preserved input hash mismatch")
        with store._locked(creating=True) as (fd, filesystem):
            identity = dict(run_id=uuid.uuid4().hex, path=str(store.path),
                research_dir=str(store.root), filesystem=filesystem, source_inputs=identities,
                code_manifest=_code(), profile=limits,
                adapter=dict(source_id=SOURCE_ID, descriptor=SOURCE_DESCRIPTOR_HASH,
                    world_id=digest(copied["world"]), actor="agent", sensor=WORLD_VERSION,
                    grammar="challenge-candidate-commands-v1"),
                initial_ora_hash=digest(copied["ora"]), initial_world_hash=digest(copied["world"]),
                initial_frame_count=len(copied["observations"]))
            state = dict(version=VERSION, identity=identity, identity_hash=digest(identity),
                revision=0, counters={key:0 for key in ("inquiries", "decisions", "attempts", "outcomes", "beliefs", "actions")},
                ora=deepcopy(copied["ora"]), world=deepcopy(copied["world"]),
                recorder=None, frames=[], inquiries=[], decisions=[], attempts=[], outcomes=[],
                beliefs=[], events=[], reserve=0, seal=None)
            for item in copied["observations"]:
                exact(item, "observation receipt", "copied source observation")
                state["frames"].append(_frame(state, item["observation"], item["receipt"]))
            state["recorder"] = _rebuild_recorder(state)
            existing = state["ora"].get(STATE_KEY)
            if existing is not None and existing != state["recorder"]:
                raise Conflict("copied Ora recorder/source mismatch")
            state["ora"][STATE_KEY] = deepcopy(state["recorder"])
            store._write_locked(fd, state, creating=True)
        return cls(path, research_dir=research_dir, enabled=True)

    def read(self):
        return self.store.read()

    def admit(self, inquiry_proposal, expected_revision):
        if not isinstance(inquiry_proposal, dict) or not {"question_id", "experiment_id", "hypotheses"} <= set(inquiry_proposal) or set(inquiry_proposal) - {"question_id", "experiment_id", "hypotheses", "origin_frame_sequence"}:
            raise Conflict("inquiry proposal fields violate contract")
        supplied = hypotheses(inquiry_proposal["hypotheses"])
        with self.store._locked() as (fd, identities):
            state = self.store._read_locked(fd, identities)
            self._revision(state, expected_revision)
            _blocked(state)
            limits = state["identity"]["profile"]
            if (state["counters"]["decisions"] >= limits["max_decisions"]
                    or state["counters"]["actions"] >= limits["max_actions"]):
                raise Capacity("capacity_exhausted: new admission is stopped")
            experiment = _find_experiment(state["ora"], inquiry_proposal["experiment_id"])
            question = _one(state["ora"], "questions", inquiry_proposal["question_id"])
            if experiment["question_id"] != question["id"]:
                raise Conflict("binding_conflict")
            if any(row["question_id"] == question["id"] or row["experiment_id"] == experiment["id"] or row["question"] == question["text"] for row in state["inquiries"]):
                raise Conflict("binding_conflict")
            # Reject collisions in the native state too; never silently rebind.
            if len([q for q in state["ora"]["questions"] if q.get("text") == question["text"]]) != 1:
                raise Conflict("binding_conflict: duplicate question text")
            sequence = inquiry_proposal.get("origin_frame_sequence", len(state["frames"]))
            integer(sequence, 1, len(state["frames"]), "original grounding sequence")
            origin_frame = state["frames"][sequence-1]
            origin_recorder = _rebuild_recorder(state, state["frames"][:sequence])
            frozen_ora = deepcopy(state["ora"])
            frozen_ora[STATE_KEY] = deepcopy(origin_recorder)
            memory, recorder = _recorder(frozen_ora, state["identity"]["source_inputs"]["ora"]["path"])
            _validate_inquiry_source(frozen_ora, experiment, recorder, origin_recorder, origin_frame["observation"])
            refs = experiment["native_inquiry"]["evidence_refs"]
            origin = dict(frame_id=origin_frame["id"], publication=recorder.publication(),
                ora=dict(questions=[deepcopy(question)], experiments=[deepcopy(experiment)],
                         episodes=[deepcopy(_one(state["ora"], "episodes", ref)) for ref in refs]),
                recorder=deepcopy(origin_recorder), contract=_semantic(question, experiment))
            origin["hash"] = _hash_record(origin)
            version = dict(version=1, hypotheses=supplied)
            version["hash"] = _hash_record(version)
            state["counters"]["inquiries"] += 1
            inquiry = dict(id=_id(state,"I",state["counters"]["inquiries"]), question_id=question["id"],
                experiment_id=experiment["id"], question=question["text"], origin=origin,
                hypothesis_versions=[version], current_belief=None, status="open",
                predecessor=None, successor=None)
            _cancel(state)
            state["inquiries"].append(inquiry)
            _event(state, "admit", inquiry["id"])
            self.store._write_locked(fd, state)
            return deepcopy(inquiry)

    @staticmethod
    def _revision(state, expected):
        if type(expected) is not int or expected != state["revision"]:
            raise Conflict("stale expected revision")

    def select_next(self, public_inputs, expected_revision):
        with self.store._locked() as (fd, identities):
            state = self.store._read_locked(fd, identities)
            self._revision(state, expected_revision)
            _blocked(state)
            limits = state["identity"]["profile"]
            if state["counters"]["decisions"] >= limits["max_decisions"]:
                raise Capacity("capacity_exhausted: decisions")
            if state["counters"]["actions"] >= limits["max_actions"]:
                raise Capacity("capacity_exhausted: actions")
            if public_inputs.get("provenance") != ("synthetic_control" if limits["name"] == "synthetic_contract" else "preserved_input_smoke"):
                raise Conflict("selection provenance/profile mismatch")
            bridge = run_cycle(state["ora"], public_inputs, state["identity"]["source_inputs"]["ora"]["path"])
            bridge["pre_state_hash"] = digest(bridge["pre_state"])
            bridge["post_state_hash"] = digest(bridge["post_state"])
            state["ora"] = deepcopy(bridge["post_state"])
            _cancel(state)
            state["counters"]["decisions"] += 1
            decision = dict(id=_id(state, "D", state["counters"]["decisions"]), bridge=bridge,
                            inquiry_id=None, attempt_id=None, deferral_reason="no_executable_owned_inquiry")
            selection = bridge["selection"]
            inquiry = None
            if selection:
                matches = [r for r in state["inquiries"] if r["question_id"] == selection["question_id"]]
                if len(matches) == 1 and matches[0]["status"] != "closed":
                    inquiry = matches[0]
            for row in state["inquiries"]:
                if row["status"] != "closed":
                    row["status"] = "open" if row is inquiry else "suspended"
            if inquiry:
                candidate = _validate_grounding(state, inquiry)
                decision["inquiry_id"] = inquiry["id"]
                features = public_features(state["frames"][-1]["observation"])
                if not selection["owned"] or selection["experiment_id"] != inquiry["experiment_id"]:
                    decision["deferral_reason"] = "selected_inquiry_without_owned_native_experiment"
                elif candidate["feature"] not in features:
                    decision["deferral_reason"] = "feature_temporarily_unavailable"
                elif state["counters"]["actions"] >= limits["max_actions"]:
                    decision["deferral_reason"] = "action_capacity_exhausted"
                else:
                    _, recorder = _recorder(state["ora"], state["identity"]["source_inputs"]["ora"]["path"])
                    command_policy = select_epistemic_command(deepcopy(state["frames"][-1]["observation"]),
                        feature=candidate["feature"], relation=candidate["relation"],
                        associations=recorder.action_associations())
                    command = command_policy["command"]
                    prediction = _prediction(inquiry, state["frames"][-1], command)
                    if prediction is not None:
                        state["counters"]["attempts"] += 1
                        attempt_id = _id(state, "A", state["counters"]["attempts"])
                        contract = dict(inquiry_id=inquiry["id"], decision_id=decision["id"],
                            hypothesis_version=1, hypothesis_hash=inquiry["hypothesis_versions"][0]["hash"],
                            belief_id=inquiry["current_belief"], command=command,
                            policy=command_policy, prediction=prediction,
                            frame_id=state["frames"][-1]["id"], frame_hash=state["frames"][-1]["hash"],
                            world_hash=digest(state["world"]), ora_hash=digest(state["ora"]),
                            adapter=deepcopy(state["identity"]["adapter"]), identity_hash=state["identity_hash"],
                            code_hash=digest(state["identity"]["code_manifest"]),
                            expected_revision=state["revision"]+1, budget_ordinal=state["counters"]["actions"]+1,
                            question_contract_hash=digest(inquiry["origin"]["contract"]["question"]),
                            experiment_contract_hash=digest(inquiry["origin"]["contract"]["experiment"]))
                        state["attempts"].append(dict(id=attempt_id, contract=contract,
                            contract_hash=digest(contract), status="prepared", outcome_id=None, belief_id=None))
                        decision["attempt_id"] = attempt_id
                        decision["deferral_reason"] = None
                        state["reserve"] = COMPLETION_RESERVE
            decision["hash"] = _hash_record(decision)
            state["decisions"].append(decision)
            _event(state, "select", decision["id"])
            self.store._write_locked(fd, state)
            return deepcopy(decision)

    def execute(self, attempt_id, expected_revision):
        label(attempt_id, "attempt ID")
        integer(expected_revision, 0, 1_000_000, "expected revision")
        with self.store._locked() as (fd, identities):
            state = self.store._read_locked(fd, identities)
            attempt = _one(state, "attempts", attempt_id)
            if attempt["status"] in {"committed", "interpreted"}:
                return deepcopy(_one(state, "outcomes", attempt["outcome_id"]))
            self._revision(state, expected_revision)
            if attempt["status"] != "prepared":
                raise Conflict("cancelled or stale authority")
            contract = attempt["contract"]
            before_size = len(encoded(state))
            before = state["frames"][-1]
            # The only private transition call is after every freshness check.
            world, receipt = transition(deepcopy(state["world"]), deepcopy(contract["command"]),
                                        cycle=state["world"]["cycle"]+1)
            validate_world(world)
            observation = observe_world(world)
            bounded(receipt, what="receipt")
            validate_receipt(receipt, before["observation"], observation)
            after = _frame(state, observation, receipt)
            state["frames"].append(after)
            state["world"] = world
            state["recorder"] = _rebuild_recorder(state)
            state["ora"][STATE_KEY] = deepcopy(state["recorder"])
            state["counters"]["actions"] += 1
            state["counters"]["outcomes"] += 1
            outcome = dict(id=_id(state,"O",state["counters"]["outcomes"]), attempt_id=attempt_id,
                decision_id=contract["decision_id"], inquiry_id=contract["inquiry_id"], receipt=receipt,
                before_frame_id=before["id"], after_frame_id=after["id"],
                world_before_hash=contract["world_hash"], world_after_hash=digest(world),
                observation_status="complete_public_sensor")
            outcome["hash"] = _hash_record(outcome)
            state["outcomes"].append(outcome)
            attempt["status"] = "committed"; attempt["outcome_id"] = outcome["id"]
            state["reserve"] = INTERPRETATION_RESERVE
            _event(state,"consume",outcome["id"])
            if len(encoded(state))-before_size > T2_GROWTH_BOUND:
                raise Capacity("transition exceeded proven schema growth bound")
            self.store._write_locked(fd, state)
            return deepcopy(outcome)

    def recover_or_interpret(self, *, interpretation_rule=RULE):
        if interpretation_rule != RULE:
            raise Conflict("missing/changed interpretation rule; no reinterpretation allowed")
        with self.store._locked() as (fd, identities):
            state = self.store._read_locked(fd, identities)
            pending = [a for a in state["attempts"] if a["status"] == "committed"]
            if not pending:
                return deepcopy(state["beliefs"][-1]) if state["beliefs"] else None
            attempt = pending[0]
            outcome = _one(state,"outcomes",attempt["outcome_id"])
            frame = _one(state,"frames",outcome["after_frame_id"])
            inquiry = _one(state,"inquiries",outcome["inquiry_id"])
            evaluations, reason = _interpret(attempt,outcome,frame)
            before_size = len(encoded(state))
            state["counters"]["beliefs"] += 1
            belief = dict(id=_id(state,"B",state["counters"]["beliefs"]), inquiry_id=inquiry["id"],
                attempt_id=attempt["id"],outcome_id=outcome["id"],predecessor=inquiry["current_belief"],
                hypothesis_version=1,prediction_hash=digest(attempt["contract"]["prediction"]),
                outcome_hash=outcome["hash"],rule=RULE,evaluations=evaluations,
                unresolved_alternatives=[r["hypothesis_id"] for r in evaluations if r["verdict"] != "contradicts_this_case"],reason=reason)
            belief["hash"] = _hash_record(belief)
            bounded(belief,what="belief record")
            state["beliefs"].append(belief)
            inquiry["current_belief"] = belief["id"]
            attempt["status"] = "interpreted"; attempt["belief_id"] = belief["id"]
            state["reserve"] = 0
            _event(state,"interpret",belief["id"])
            if len(encoded(state))-before_size > T3_GROWTH_BOUND:
                raise Capacity("interpretation exceeded proven schema growth bound")
            self.store._write_locked(fd,state)
            return deepcopy(belief)
