"""Opt-in copied public records -> passive contracts. No world or action access."""
from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .native_evidence import NATIVE_EVIDENCE_V2_VERSION, validate_native_evidence_payload
from .native_inquiry import NATIVE_INQUIRY_VERSION, validate_native_inquiry_candidate
from .episode_identity import episode_sequence

POLICY = "public-temporal-candidates-v1"
SOURCE = "public_observation_candidate"
KEY = "public_observation_registry"
RELATIONS = ("same_next_observation", "changes_next_observation")
MAX_BYTES = 65536


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _object_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode(raw: str):
    if not isinstance(raw, str) or len(raw.encode()) > MAX_BYTES:
        raise ValueError("public JSON size/type")
    return json.loads(raw, object_pairs_hook=_object_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("public contract fields")


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", value):
        raise ValueError("public identifier")


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("public hash")


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("public integer bounds")


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("public timestamp syntax")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _position(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("public position")
    for coordinate in value:
        _integer(coordinate, -2, 2)


def validate_payload(payload):
    _fields(payload, "world_version observation_id cycle position inventory_ids visible_entities")
    if payload["world_version"] != "open-object-world-challenge-v1":
        raise ValueError("public world version")
    _id(payload["observation_id"])
    _integer(payload["cycle"], 0, 1000000)
    _position(payload["position"])
    ids = payload["inventory_ids"]
    if not isinstance(ids, list) or len(ids) > 16:
        raise ValueError("public inventory bounds")
    for item in ids:
        _id(item)
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate inventory identity")
    entities = payload["visible_entities"]
    if not isinstance(entities, list) or len(entities) > 16:
        raise ValueError("public visibility bounds")
    seen = set()
    for entity in entities:
        if not isinstance(entity, dict) or set(entity) not in (
            {"id", "position", "appearance"}, {"id", "position", "appearance", "observable_state"}
        ):
            raise ValueError("public entity fields")
        _id(entity["id"])
        if entity["id"] in seen:
            raise ValueError("duplicate visible identity")
        seen.add(entity["id"])
        _position(entity["position"])
        if sum(abs(a-b) for a,b in zip(entity["position"], payload["position"])) > 1:
            raise ValueError("nonlocal visibility")
        if not isinstance(entity["appearance"], str) or len(entity["appearance"]) > 128:
            raise ValueError("public appearance")
        if "observable_state" in entity and (
            not isinstance(entity["observable_state"], str) or len(entity["observable_state"]) > 32
        ):
            raise ValueError("public observable state")
    return payload


def validate_bundle(bundle):
    _fields(bundle, "descriptor acquisition_manifest raw_record")
    descriptor = bundle["descriptor"]
    _fields(descriptor, "version source_id world_instance_id actor_id world_version sensor_code_sha256 genesis_payload_sha256 maximum_records acquisition_start acquisition_end disclosure")
    if descriptor["version"] != "public-source-descriptor-v1" or descriptor["world_version"] != "open-object-world-challenge-v1" or descriptor["disclosure"] != "isolated-research-not-ora-experience":
        raise ValueError("public descriptor version/disclosure")
    for name in ("source_id", "world_instance_id", "actor_id"):
        _id(descriptor[name])
    for name in ("sensor_code_sha256", "genesis_payload_sha256"):
        _hash(descriptor[name])
    _integer(descriptor["maximum_records"], 1, 3)
    start, end = _time(descriptor["acquisition_start"]), _time(descriptor["acquisition_end"])
    if start > end:
        raise ValueError("public acquisition interval")
    manifest = bundle["acquisition_manifest"]
    _fields(manifest, "version descriptor_sha256 ordered_raw_record_sha256")
    if manifest["version"] != "public-acquisition-v1" or manifest["descriptor_sha256"] != digest(descriptor):
        raise ValueError("public acquisition descriptor")
    hashes = manifest["ordered_raw_record_sha256"]
    if not isinstance(hashes, list) or len(hashes) != descriptor["maximum_records"]:
        raise ValueError("public acquisition count")
    for value in hashes:
        _hash(value)
    raw = bundle["raw_record"]
    record = decode(raw)
    _fields(record, "version source_id world_instance_id actor_id source_descriptor_sha256 sequence previous_record_sha256 observed_at payload payload_sha256 record_sha256")
    if record["version"] != "public-observation-record-v1":
        raise ValueError("public record version")
    for name in ("source_id", "world_instance_id", "actor_id"):
        if record[name] != descriptor[name]:
            raise ValueError("public source identity")
    if record["source_descriptor_sha256"] != digest(descriptor):
        raise ValueError("public record descriptor")
    sequence = record["sequence"]
    _integer(sequence, 1, descriptor["maximum_records"])
    observed = _time(record["observed_at"])
    if not start <= observed <= end:
        raise ValueError("public acquisition time")
    validate_payload(record["payload"])
    if record["payload_sha256"] != digest(record["payload"]) or record["record_sha256"] != digest({k:v for k,v in record.items() if k != "record_sha256"}):
        raise ValueError("public content checksum")
    if hashlib.sha256(raw.encode()).hexdigest() != hashes[sequence-1]:
        raise ValueError("public raw acquisition checksum")
    if sequence == 1:
        if record["previous_record_sha256"] is not None or record["payload_sha256"] != descriptor["genesis_payload_sha256"]:
            raise ValueError("public genesis")
    else:
        _hash(record["previous_record_sha256"])
    return descriptor, manifest, record


def load_bundle(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("public bundle size")
    return decode(path.read_text(encoding="utf-8"))


def features(payload):
    result = {("position", "x"): payload["position"][0],
              ("position", "y"): payload["position"][1],
              ("inventory", "count"): len(payload["inventory_ids"])}
    for entity in payload["visible_entities"]:
        if "observable_state" in entity:
            result[("entity", entity["id"], "state")] = entity["observable_state"]
    return result


def validate_source(source, source_id):
    """One raw schema/adjacency boundary for accepted and prospective prefixes."""
    _fields(source, "descriptor acquisition_manifest raw_records pair_evidence")
    if digest(source["descriptor"]) != source_id:
        raise ValueError("public source descriptor")
    raw_records = source["raw_records"]
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("public source needs a nonempty record prefix")
    bindings = source["pair_evidence"]
    if not isinstance(bindings, dict):
        raise ValueError("public pair bindings")
    for pair_id, relations in bindings.items():
        _hash(pair_id)
        if not isinstance(relations, dict) or not set(relations) <= set(RELATIONS):
            raise ValueError("public pair relation bindings")
        for ref in relations.values():
            _id(ref)
    records = []
    seen = set()
    for index, raw in enumerate(raw_records, 1):
        _, _, record = validate_bundle({"descriptor": source["descriptor"],
                                       "acquisition_manifest": source["acquisition_manifest"],
                                       "raw_record": raw})
        if record["sequence"] != index:
            raise ValueError("public noncontiguous sequence")
        observation_id = record["payload"]["observation_id"]
        if observation_id in seen:
            raise ValueError("public repeated observation identity")
        if records:
            previous = records[-1]
            if record["previous_record_sha256"] != previous["record_sha256"] or _time(record["observed_at"]) < _time(previous["observed_at"]):
                raise ValueError("public broken chain/order")
            if record["payload"]["cycle"] <= previous["payload"]["cycle"]:
                raise ValueError("public world cycle must strictly increase")
        seen.add(observation_id)
        records.append(record)
    return records


def _validated_registry(registry):
    _fields(registry, "version sources families versions")
    if registry["version"] != POLICY:
        raise ValueError("public registry policy")
    for name in ("sources", "families", "versions"):
        if not isinstance(registry[name], dict):
            raise ValueError("public registry mapping")
    if len(registry["sources"]) > 2:
        raise ValueError("public source bound")
    identities = set()
    for source_id, source in registry["sources"].items():
        _hash(source_id)
        validate_source(source, source_id)
        identity = (source["descriptor"]["source_id"], source["descriptor"]["world_instance_id"])
        if identity in identities:
            raise ValueError("public reviewed source descriptor conflict")
        identities.add(identity)
    for version_id, contract in registry["versions"].items():
        if not isinstance(contract, dict) or not all(isinstance(contract.get(name), str) for name in ("policy", "version_id", "source_id", "family_id")):
            raise ValueError("public retained contract identifiers")
        if contract["policy"] != POLICY or contract["version_id"] != version_id or contract["source_id"] not in registry["sources"]:
            raise ValueError("public retained contract version")
        if not isinstance(contract.get("pair_ids"), list) or version_id != "POV:"+digest([contract.get("family_id"),contract["pair_ids"]])[:48]:
            raise ValueError("public noncanonical retained version")
    for family_id, entry in registry["families"].items():
        _id(family_id)
        _fields(entry, "question_id version_id source_id")
        _id(entry["question_id"])
        if not all(isinstance(entry[name], str) for name in ("version_id", "source_id")):
            raise ValueError("public retained family identifiers")
        contract = registry["versions"].get(entry["version_id"])
        if not contract or contract.get("family_id") != family_id or contract.get("source_id") != entry["source_id"]:
            raise ValueError("public retained family contract")
    return registry


def _pairs(source):
    result = {}
    records = [decode(raw) for raw in source["raw_records"]]
    descriptor_hash = digest(source["descriptor"])
    for before, after in zip(records, records[1:]):
        if after["payload"]["cycle"] <= before["payload"]["cycle"]:
            continue
        left, right = features(before["payload"]), features(after["payload"])
        for feature in sorted(left.keys() & right.keys()):
            pair = {"descriptor_sha256": descriptor_hash, "feature": list(feature),
                    "before_sequence": before["sequence"], "after_sequence": after["sequence"],
                    "record_hashes": [before["record_sha256"], after["record_sha256"]],
                    "same": left[feature] == right[feature]}
            result[digest(pair)] = pair
    return result


def ingest(state, bundle):
    """Validate before mutation. Returns internal pair records needing episode refs."""
    descriptor, manifest, record = validate_bundle(bundle)
    source_id = digest(descriptor)
    registry = state.get(KEY, {"version": POLICY, "sources": {}, "families": {}, "versions": {}})
    _validated_registry(registry)
    sources = registry["sources"]
    for known_id, known in sources.items():
        known_descriptor = known["descriptor"]
        if (known_descriptor["source_id"], known_descriptor["world_instance_id"]) == (descriptor["source_id"], descriptor["world_instance_id"]) and known_id != source_id:
            raise ValueError("public reviewed source descriptor conflict")
    existing = sources.get(source_id)
    source = deepcopy(existing) if existing else {"descriptor": descriptor, "acquisition_manifest": manifest, "raw_records": [], "pair_evidence": {}}
    if source["descriptor"] != descriptor or source["acquisition_manifest"] != manifest:
        raise ValueError("public source provenance changed")
    sequence = record["sequence"]
    records = source["raw_records"]
    if sequence <= len(records):
        if records[sequence-1] != bundle["raw_record"]:
            raise ValueError("public accepted sequence conflict")
        return {"status": "idempotent_replay", "source": source_id, "pairs": []}
    if sequence != len(records)+1:
        raise ValueError("public noncontiguous sequence")
    if not existing and len(sources) >= 2:
        raise ValueError("public source bound")
    records.append(bundle["raw_record"])
    validate_source(source, source_id)
    source_pairs = _pairs(source)
    new_pairs = []
    for pair_id, pair in source_pairs.items():
        if pair_id not in source["pair_evidence"]:
            source["pair_evidence"][pair_id] = {}
            for relation in RELATIONS:
                confirms = int(pair["same"] == (relation == RELATIONS[0]))
                payload = {"version": NATIVE_EVIDENCE_V2_VERSION,
                           "relation": {"kind": relation, "feature": "pub."+digest([source_id,pair["feature"]])[:40], "action": None, "comparison_status": "not_applicable"},
                           "observation_refs": ["PO:"+source_id[:16]+":"+str(pair["before_sequence"]), "PO:"+source_id[:16]+":"+str(pair["after_sequence"])],
                           "measurement_kind": "binary_transition_outcomes",
                           "measurement": {"evaluable": 1, "confirmations": confirms, "refutations": 1-confirms}}
                new_pairs.append({"pair_id": pair_id, "relation": relation, "evidence": validate_native_evidence_payload(payload)})
    if KEY not in state:
        state[KEY] = registry
    sources[source_id] = source
    return {"status": "accepted", "source": source_id, "sequence": sequence, "pairs": new_pairs}


def bind_evidence(state, source_id, pair_id, relation, evidence_ref):
    state[KEY]["sources"][source_id]["pair_evidence"][pair_id][relation] = evidence_ref


def compile_candidates(state, source_id):
    """Pure compiler: raw lookup, internal pairs and exact episode contents must agree."""
    source = _validated_registry(state[KEY])["sources"][source_id]
    validate_source(source, source_id)
    grouped = {}
    pairs = _pairs(source)
    episodes = {episode.get("id"): episode for episode in state.get("episodes", [])}
    for pair_id, pair in pairs.items():
        for relation in RELATIONS:
            ref = source["pair_evidence"].get(pair_id, {}).get(relation)
            episode = episodes.get(ref)
            if not episode or episode.get("kind") != "native_inquiry_evidence":
                raise ValueError("public compiler episode unavailable")
            evidence = validate_native_evidence_payload(decode(episode["content"]))
            confirms = int(pair["same"] == (relation == RELATIONS[0]))
            expected_relation = {"kind": relation, "feature": "pub."+digest([source_id,pair["feature"]])[:40], "action": None, "comparison_status": "not_applicable"}
            expected_refs = ["PO:"+source_id[:16]+":"+str(pair["before_sequence"]), "PO:"+source_id[:16]+":"+str(pair["after_sequence"])]
            if evidence["relation"] != expected_relation or evidence["observation_refs"] != expected_refs or evidence["measurement_kind"] != "binary_transition_outcomes" or evidence["measurement"] != {"evaluable": 1, "confirmations": confirms, "refutations": 1-confirms}:
                raise ValueError("public compiler episode mismatch")
            grouped.setdefault((tuple(pair["feature"]), relation), []).append((pair_id,pair,ref,evidence))
    compiled = []
    latest = decode(source["raw_records"][-1])
    current_features = {
        tuple(pair["feature"]) for pair in pairs.values()
        if pair["after_sequence"] == len(source["raw_records"])
    }
    for (feature, relation), rows in sorted(grouped.items()):
        if feature not in current_features:
            continue
        family = "POF:"+digest([POLICY,source_id,list(feature),relation])[:48]
        version = "POV:"+digest([family,[row[0] for row in rows]])[:48]
        n = len(rows); c = sum(row[3]["measurement"]["confirmations"] for row in rows)
        p = (c+1)/(n+2); entropy = -p*math.log2(p)-(1-p)*math.log2(1-p)
        stable = relation == RELATIONS[0]
        word, opposite = ("equal", "different") if stable else ("different", "equal")
        readable = ".".join(feature)
        candidate = {"version": NATIVE_INQUIRY_VERSION, "id": version, "objective": "information_gain",
                     "objective_score": round(entropy*(0.35+0.65*n/(n+4)),6),
                     "relation": deepcopy(rows[0][3]["relation"]),
                     "question": f"For {family}, will public {readable} be {word} in the next consecutive evaluable pair?",
                     "hypothesis": f"Public {readable} will be {word} in the next consecutive evaluable pair.",
                     "method": f"Passively compare public {readable} in one subsequent adjacent pair with both values visible.",
                     "falsification": f"A {opposite} subsequent evaluable pair counts against this hypothesis.",
                     "predicted_observation": f"The next evaluable adjacent pair has {word} public {readable}.",
                     "evidence_refs": [row[2] for row in rows]}
        candidate = validate_native_inquiry_candidate(candidate,state)
        compiled.append({"family_id": family, "version_id": version, "source_id": source_id, "policy": POLICY,
                         "feature_tuple": list(feature), "pair_ids": [row[0] for row in rows], "candidate": candidate,
                         "counts": {"evaluable": n, "confirmations": c, "refutations": n-c},
                         "outcome_floor_sequence": len(source["raw_records"]), "outcome_floor_record_hash": latest["record_sha256"],
                         "outcome_floor_world_cycle": latest["payload"]["cycle"],
                         "status": "exhausted" if len(source["raw_records"]) >= source["descriptor"]["maximum_records"] else "prospective"})
    if len(compiled) > 38:
        raise ValueError("public current candidate bound")
    return compiled


def admit(state, source_id, upsert_question):
    contracts = compile_candidates(state,source_id)
    registry = state[KEY]
    for contract in contracts:
        registry["versions"][contract["version_id"]] = deepcopy(contract)
        entry = registry["families"].get(contract["family_id"])
        if entry:
            question = next(q for q in state["questions"] if q["id"] == entry["question_id"])
        else:
            question = upsert_question(state,contract["candidate"]["question"])
        question["source"] = SOURCE
        question["public_observation_family"] = contract["family_id"]
        question["source_evidence_refs"] = list(contract["candidate"]["evidence_refs"])
        registry["families"][contract["family_id"]] = {"question_id": question["id"], "version_id": contract["version_id"], "source_id": source_id}
    if len(registry["versions"]) > 76*len(registry["sources"]):
        raise ValueError("public candidate version bound")
    return contracts


def validated_contract(state, question):
    try:
        if not isinstance(question, dict) or question.get("source") != SOURCE or question.get("status") != "open":
            return None
        registry = _validated_registry(state.get(KEY, {}))
        family = question.get("public_observation_family")
        entry = registry["families"].get(family)
        if not entry or entry["question_id"] != question.get("id"):
            return None
        contract = next((c for c in compile_candidates(state,entry["source_id"]) if c["family_id"] == family),None)
        if not contract or contract["status"] != "prospective" or entry["version_id"] != contract["version_id"] or registry["versions"].get(entry["version_id"]) != contract or question.get("source_evidence_refs") != contract["candidate"]["evidence_refs"] or question.get("text") != contract["candidate"]["question"]:
            return None
        return contract
    except (KeyError, ValueError, TypeError, StopIteration):
        return None


def registry_eligible(state, question):
    return validated_contract(state,question) is not None


def _unique(rows, identity, label):
    matches = [row for row in rows if row.get("id") == identity]
    if len(matches) != 1:
        raise ValueError("public resolution ambiguous/missing " + label)
    return matches[0]


def _original_resolution_contract(state, experiment):
    """Rebuild the immutable allocation prefix, never current eligibility."""
    contract = experiment.get("public_observation_contract")
    if not isinstance(contract, dict):
        raise ValueError("public resolution allocation contract unavailable")
    registry = _validated_registry(state[KEY])
    family = contract["family_id"]
    if experiment.get("public_observation_family") != family:
        raise ValueError("public resolution family mismatch")
    linked = [e for e in state["experiments"] if e.get("public_observation_family") == family]
    if len(linked) != 1:
        raise ValueError("public resolution ambiguous family ownership")
    question = _unique(state["questions"], experiment.get("question_id"), "owner")
    entry = registry["families"].get(family)
    if (not entry or entry["question_id"] != question["id"] or entry["source_id"] != contract["source_id"]
            or question.get("source") != SOURCE or question.get("public_observation_family") != family):
        raise ValueError("public resolution owner provenance mismatch")
    source = registry["sources"][contract["source_id"]]
    records = validate_source(source, contract["source_id"])
    floor = contract["outcome_floor_sequence"]
    if type(floor) is not int or not 1 <= floor <= len(records):
        raise ValueError("public resolution allocation floor unavailable")
    if (records[floor-1]["record_sha256"] != contract["outcome_floor_record_hash"]
            or records[floor-1]["payload"]["cycle"] != contract["outcome_floor_world_cycle"]):
        raise ValueError("public resolution allocation raw floor mismatch")
    prefix = dict(state)
    prefix[KEY] = deepcopy(registry)
    prefix_source = prefix[KEY]["sources"][contract["source_id"]]
    prefix_source["raw_records"] = prefix_source["raw_records"][:floor]
    prefix_pairs = _pairs(prefix_source)
    prefix_source["pair_evidence"] = {k:v for k,v in source["pair_evidence"].items() if k in prefix_pairs}
    for bindings in prefix_source["pair_evidence"].values():
        for ref in bindings.values():
            _unique(state["episodes"], ref, "grounding episode")
    rebuilt = [c for c in compile_candidates(prefix, contract["source_id"]) if c["family_id"] == family]
    if len(rebuilt) != 1 or canonical(rebuilt[0]) != canonical(contract) or contract["status"] != "prospective":
        raise ValueError("public resolution original contract mismatch")
    candidate = contract["candidate"]
    native = experiment.get("native_inquiry") or {}
    expected = {"version": NATIVE_INQUIRY_VERSION, "candidate_id": candidate["id"],
                "objective": candidate["objective"], "objective_score": candidate["objective_score"],
                "relation": candidate["relation"], "evidence_refs": candidate["evidence_refs"]}
    if canonical({k:native.get(k) for k in expected}) != canonical(expected):
        raise ValueError("public resolution native allocation metadata mismatch")
    for name in ("hypothesis", "method", "falsification", "predicted_observation"):
        if experiment.get(name) != candidate[name]:
            raise ValueError("public resolution allocation specification mismatch")
    if question.get("text") != candidate["question"]:
        raise ValueError("public resolution question identity mismatch")
    episode_floor = native.get("resolution_evidence_floor_episode_sequence")
    if type(episode_floor) is not int or episode_floor < 0:
        raise ValueError("public resolution native sequence floor unavailable")
    for ref in candidate["evidence_refs"]:
        seq = episode_sequence(_unique(state["episodes"], ref, "grounding episode")["id"])
        if seq is None or seq > episode_floor:
            raise ValueError("public resolution grounding exceeds allocation floor")
    return contract, source, episode_floor


class PublicResolutionConflict(ValueError):
    """Deterministic failed-batch receipt; never persisted as successful closure."""
    def __init__(self, reason):
        super().__init__(reason)
        self.receipt = {"status": "rejected", "reason": reason}


def plan_public_resolutions(state, newly_bound):
    try:
        return _plan_public_resolutions(state, newly_bound)
    except (ValueError, KeyError, TypeError, StopIteration) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "public resolution malformed provenance"
        raise PublicResolutionConflict(reason) from exc


def _plan_public_resolutions(state, newly_bound):
    """Pure fail-closed batch. Only supplied current-cycle bindings, no backlog."""
    if not isinstance(newly_bound, list):
        raise ValueError("public resolution binding list required")
    plans, receipts = [], []
    if not newly_bound:
        return {"plans": plans, "receipts": receipts}
    registry = _validated_registry(state[KEY])
    identities = set()
    for row in newly_bound:
        _fields(row, "source_id pair_id relation evidence_ref")
        key = (row["source_id"], row["pair_id"], row["relation"])
        if key in identities:
            raise ValueError("public resolution duplicate outcome binding")
        identities.add(key)
        source = registry["sources"][row["source_id"]]
        if source["pair_evidence"].get(row["pair_id"], {}).get(row["relation"]) != row["evidence_ref"]:
            raise ValueError("public resolution forged binding")
        episode = _unique(state["episodes"], row["evidence_ref"], "outcome episode")
        if episode.get("kind") != "native_inquiry_evidence" or episode.get("cycle") != state["cycles"]:
            raise ValueError("public resolution historical/non-native binding")
        pair = _pairs(source).get(row["pair_id"])
        if pair is None or row["relation"] not in RELATIONS:
            raise ValueError("public resolution raw pair unavailable")
        confirms = int(pair["same"] == (row["relation"] == RELATIONS[0]))
        expected = {"version": NATIVE_EVIDENCE_V2_VERSION,
                    "relation": {"kind": row["relation"], "feature": "pub."+digest([row["source_id"],pair["feature"]])[:40],
                                 "action": None, "comparison_status": "not_applicable"},
                    "observation_refs": ["PO:"+row["source_id"][:16]+":"+str(pair["before_sequence"]),
                                         "PO:"+row["source_id"][:16]+":"+str(pair["after_sequence"])],
                    "measurement_kind": "binary_transition_outcomes",
                    "measurement": {"evaluable": 1, "confirmations": confirms, "refutations": 1-confirms}}
        if canonical(validate_native_evidence_payload(decode(episode["content"]))) != canonical(expected):
            raise ValueError("public resolution outcome raw/episode mismatch")
    experiments = sorted((e for e in state["experiments"] if e.get("public_observation_family")),
                         key=lambda e:(e.get("cycle", -1), str(e.get("id", ""))))
    for experiment in experiments:
        _unique(state["experiments"], experiment.get("id"), "experiment")
        if experiment.get("status") not in {"proposed", "completed"}:
            continue
        contract, source, episode_floor = _original_resolution_contract(state, experiment)
        floor = contract["outcome_floor_sequence"]
        pairs = _pairs(source)
        matching = [row for row in newly_bound if row["source_id"] == contract["source_id"]
                    and row["relation"] == contract["candidate"]["relation"]["kind"]
                    and pairs[row["pair_id"]]["feature"] == contract["feature_tuple"]
                    and pairs[row["pair_id"]]["before_sequence"] == floor
                    and pairs[row["pair_id"]]["after_sequence"] == floor+1]
        if not matching:
            receipts.append({"experiment_id": experiment["id"], "status": "not_yet_evaluable"})
            continue
        if len(matching) != 1:
            raise ValueError("public resolution ambiguous outcome")
        row = matching[0]
        episode = _unique(state["episodes"], row["evidence_ref"], "outcome episode")
        sequence = episode_sequence(episode["id"])
        if sequence is None or sequence <= episode_floor:
            raise ValueError("public resolution outcome predates allocation")
        pair = pairs[row["pair_id"]]
        if pair["record_hashes"][0] != contract["outcome_floor_record_hash"]:
            raise ValueError("public resolution outcome raw floor mismatch")
        evidence = decode(episode["content"])
        outcome = "supported" if evidence["measurement"]["confirmations"] == 1 else "falsified"
        identity = {"experiment_id": experiment["id"], "source_id": contract["source_id"],
                    "family_id": contract["family_id"], "version_id": contract["version_id"],
                    "floor_hash": contract["outcome_floor_record_hash"], "pair_id": row["pair_id"],
                    "relation": row["relation"]}
        receipt = {"version": "public-resolution-dispatch-v1", "key": digest(identity), **identity,
                   "evidence_ref": row["evidence_ref"], "outcome": outcome}
        if experiment["status"] == "completed":
            saved = experiment.get("public_resolution_receipt") or {}
            reflection_id = saved.get("reflection_id")
            if canonical(saved) != canonical({**receipt, "reflection_id": reflection_id}):
                raise ValueError("public resolution conflicting terminal receipt")
            reflection = _unique(state["reflections"], reflection_id, "resolution reflection")
            native_result = experiment.get("native_resolution") or {}
            histories = [h for h in experiment.get("status_history", []) if h.get("public_resolution_key") == receipt["key"]]
            expected_native = {"version": "native-inquiry-resolution-v1", "evidence_ref": row["evidence_ref"],
                               "relation": evidence["relation"], "measurement_kind": "binary_transition_outcomes", "outcome": outcome}
            if (experiment.get("outcome") != outcome or experiment.get("readiness") != "resolved"
                    or experiment.get("evidence_refs") != [row["evidence_ref"]]
                    or experiment.get("completion_source") != "native_evidence_contract"
                    or canonical(native_result) != canonical(expected_native)
                    or reflection.get("public_resolution_key") != receipt["key"]
                    or reflection.get("experiment_id") != experiment["id"] or reflection.get("evidence_ref") != row["evidence_ref"]
                    or reflection.get("outcome") != outcome or len(histories) != 1
                    or sum(r.get("public_resolution_key") == receipt["key"] for r in state["reflections"]) != 1
                    or reflection.get("source") != "native_inquiry" or reflection.get("cycle") != histories[0].get("cycle")
                    or histories[0].get("from") != "proposed" or histories[0].get("to") != "completed"
                    or histories[0].get("evidence_refs") != [row["evidence_ref"]]
                    or histories[0].get("reason") != "native_evidence_contract_resolved" or histories[0].get("outcome") != outcome):
                raise ValueError("public resolution conflicting terminal transition")
            receipts.append({"experiment_id": experiment["id"], "status": "already_resolved", "receipt": saved})
        else:
            if experiment.get("readiness") != "awaiting_native_evidence" or experiment.get("public_resolution_receipt"):
                raise ValueError("public resolution proposed contract state conflict")
            plans.append({"experiment_id": experiment["id"], "evidence_ref": row["evidence_ref"],
                          "outcome": outcome, "receipt": receipt})
    return {"plans": plans, "receipts": receipts}


def require_capacity_proofs(state, receipts):
    """Research driver attests scheduled envelope validation; no future values.

    The driver is responsible for actual file existence/readability/schema/hash
    validation. Here only opaque commitments are accepted, never a payload.
    """
    if not isinstance(receipts, dict):
        raise ValueError("copy capacity receipts must be an object")
    registry = _validated_registry(state.get(KEY, {})) if KEY in state else {"sources": {}}
    for source_id, source in registry["sources"].items():
        sequence = len(source["raw_records"])
        hashes = source["acquisition_manifest"]["ordered_raw_record_sha256"]
        if sequence >= len(hashes):
            continue
        receipt = receipts.get(source_id)
        fields = {"kind", "verified", "source_id", "current_sequence", "next_sequence",
                  "next_raw_record_sha256", "next_envelope_sha256"}
        if (not isinstance(receipt, dict) or set(receipt) != fields
                or receipt["kind"] != "verified_scheduled_copy_envelope"
                or receipt["verified"] is not True or receipt["source_id"] != source_id
                or type(receipt["current_sequence"]) is not int
                or type(receipt["next_sequence"]) is not int
                or receipt["current_sequence"] != sequence
                or receipt["next_sequence"] != sequence + 1
                or receipt["next_raw_record_sha256"] != hashes[sequence]):
            raise ValueError("missing or mismatched scheduled next-envelope proof")
        _hash(receipt["next_envelope_sha256"])


def obtainable_contract(state, question, capacity_receipts):
    """Copied finite acquisition capacity, not status/schema or live temporal access.

    Inspect the retained prefix and committed record hashes only. Never inspect
    a future record's payload to choose a feature or a preferred outcome.
    """
    contract = validated_contract(state, question)
    if contract is None:
        return None
    source = state[KEY]["sources"][contract["source_id"]]
    sequence = len(source["raw_records"])
    hashes = source["acquisition_manifest"]["ordered_raw_record_sha256"]
    if sequence >= len(hashes) or sequence >= source["descriptor"]["maximum_records"]:
        return None
    require_capacity_proofs(state, capacity_receipts)
    receipt = capacity_receipts[contract["source_id"]]
    latest = decode(source["raw_records"][-1])
    if tuple(contract["feature_tuple"]) not in features(latest["payload"]):
        return None
    linked = [experiment for experiment in state.get("experiments", [])
              if experiment.get("public_observation_family") == contract["family_id"]]
    if linked and (len(linked) != 1 or linked[0].get("status") != "proposed"
                   or linked[0].get("question_id") != question.get("id")
                   or linked[0].get("public_observation_contract") != contract):
        return None
    return {"contract": contract, "availability": {
        "kind": "copied_committed_acquisition_capacity",
        "source_id": contract["source_id"],
        "current_sequence": sequence,
        "next_sequence": sequence + 1,
        "next_raw_record_sha256": hashes[sequence],
        "current_feature_visible": True,
        "future_payload_inspected": False,
        "scheduled_envelope_verified": True,
        "next_envelope_sha256": receipt["next_envelope_sha256"],
    }}


def prospective_outcome(state, contract, raw_before, raw_after):
    """Pure passive test check; never resolves a native experiment or stores a result."""
    source = state[KEY]["sources"][contract["source_id"]]
    if contract not in compile_candidates(state, contract["source_id"]):
        raise ValueError("public outcome contract is not internally compiled")
    if raw_before != source["raw_records"][-1]:
        raise ValueError("public outcome floor is not the retained raw record")
    prospective = deepcopy(source)
    prospective["raw_records"].append(raw_after)
    records = validate_source(prospective, contract["source_id"])
    before,after=records[-2:]
    if before["sequence"] != contract["outcome_floor_sequence"] or before["record_sha256"] != contract["outcome_floor_record_hash"] or after["sequence"] != before["sequence"]+1 or after["previous_record_sha256"] != before["record_sha256"]:
        raise ValueError("public outcome is not subsequent adjacent evidence")
    feature=tuple(contract["feature_tuple"]); left,right=features(before["payload"]),features(after["payload"])
    if feature not in left or feature not in right:
        return None
    return (left[feature] == right[feature]) == (contract["candidate"]["relation"]["kind"] == RELATIONS[0])


def allocate_selected(state, question, decision, now):
    """Called only with the actual normal-cycle decision object, never an input flag."""
    decisions=state.get("agenda",{}).get("decisions",[])
    if not decisions or decision is not decisions[-1] or decision.get("cycle") != state["cycles"] or decision.get("selected",{}).get("question_id") != question.get("id"):
        return None
    contract=validated_contract(state,question)
    if contract is None:
        return None
    family=contract["family_id"]
    linked=[x for x in state["experiments"] if x.get("public_observation_family")==family]
    if linked:
        if (len(linked) != 1 or linked[0].get("status") != "proposed"
                or linked[0].get("question_id") != question.get("id")
                or linked[0].get("public_observation_contract") != contract):
            return None
        return linked[0]
    candidate=contract["candidate"]
    experiment={"id":f"X{len(state['experiments'])+1:06d}","cycle":state["cycles"],"question_id":question["id"],"status":"proposed","intention_id":None,"cognition_candidate_id":None,"hypothesis":candidate["hypothesis"],"method":candidate["method"],"falsification":candidate["falsification"],"predicted_observation":candidate["predicted_observation"],"created_at":now,"times_selected":1,"last_selected_cycle":state["cycles"],"readiness":"awaiting_native_evidence","public_observation_family":family,"public_observation_contract":deepcopy(contract),"native_inquiry":{"version":NATIVE_INQUIRY_VERSION,"candidate_id":candidate["id"],"objective":candidate["objective"],"objective_score":candidate["objective_score"],"relation":deepcopy(candidate["relation"]),"evidence_refs":list(candidate["evidence_refs"]),"resolution_evidence_floor_episode_sequence":int(state.get("next_episode_index",1))-1}}
    state["experiments"].append(experiment)
    return experiment
