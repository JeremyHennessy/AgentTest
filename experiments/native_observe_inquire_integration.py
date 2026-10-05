from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from agenttest.core import AgentCore
from agenttest.native_evidence import NATIVE_EVIDENCE_V2_VERSION
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION

SOURCE_MANIFEST_VERSION = "native-observation-source-v1"
PUBLICATION_VERSION = "native-recorder-publication-v1"
POLICY_VERSION = "native-observe-inquire-policy-v1"

_ALLOWED_TEMPORAL = {"same_next_observation", "changes_next_observation"}
_BOUNDED_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

DEFAULT_POLICY = {
    "version": POLICY_VERSION,
    "enabled": False,
    "mode": "off",
    "allowed_relations": [],
    "objective": None,
    "persist_evidence": False,
    "persist_inquiry": False,
    "allow_environment_actions": False,
    "allow_action_lab": False,
    "allow_planning_lab": False,
    "allow_phase42_credit": False,
}


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _bounded(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _BOUNDED_ID.fullmatch(value):
        raise ValueError(f"{field} must be a bounded identifier")
    return value


def observe_and_inquire_policy() -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "enabled": True,
        "mode": "observe_and_inquire",
        "allowed_relations": [
            "same_next_observation",
            "changes_next_observation",
        ],
        "objective": "information_gain",
        "persist_evidence": True,
        "persist_inquiry": True,
        "allow_environment_actions": False,
        "allow_action_lab": False,
        "allow_planning_lab": False,
        "allow_phase42_credit": False,
    }


def validate_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    if policy is None:
        return deepcopy(DEFAULT_POLICY)
    if not isinstance(policy, dict) or set(policy) != set(DEFAULT_POLICY):
        raise ValueError("observe/inquire policy fields do not match contract")
    if policy["version"] != POLICY_VERSION:
        raise ValueError("unsupported observe/inquire policy version")
    if type(policy["enabled"]) is not bool:
        raise ValueError("policy enabled must be boolean")
    if policy["mode"] not in {"off", "observe_and_inquire"}:
        raise ValueError("unsupported observe/inquire policy mode")
    relations = policy["allowed_relations"]
    if (
        not isinstance(relations, list)
        or len(relations) != len(set(relations))
        or any(item not in _ALLOWED_TEMPORAL for item in relations)
    ):
        raise ValueError("observe/inquire policy permits temporal relations only")
    for field in (
        "persist_evidence",
        "persist_inquiry",
        "allow_environment_actions",
        "allow_action_lab",
        "allow_planning_lab",
        "allow_phase42_credit",
    ):
        if type(policy[field]) is not bool:
            raise ValueError(f"{field} must be boolean")
    if (
        policy["allow_environment_actions"]
        or policy["allow_action_lab"]
        or policy["allow_planning_lab"]
        or policy["allow_phase42_credit"]
    ):
        raise ValueError("observe/inquire policy cannot grant action or Phase42 authority")
    if not policy["enabled"]:
        if (
            policy["mode"] != "off"
            or relations
            or policy["objective"] is not None
            or policy["persist_evidence"]
            or policy["persist_inquiry"]
        ):
            raise ValueError("disabled observe/inquire policy must be fully off")
    else:
        if policy["mode"] != "observe_and_inquire":
            raise ValueError("enabled policy must be observe_and_inquire")
        if set(relations) != _ALLOWED_TEMPORAL:
            raise ValueError("enabled v1 policy requires the frozen temporal allowlist")
        if policy["objective"] != "information_gain":
            raise ValueError("enabled v1 policy requires frozen information_gain")
        if not policy["persist_evidence"] or not policy["persist_inquiry"]:
            raise ValueError("enabled policy requires explicit evidence/inquiry persistence")
    return deepcopy(policy)


def validate_source_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    required = {
        "version",
        "source_id",
        "source_kind",
        "observation_schema",
        "recorder_version",
        "provenance_mode",
        "cumulative_publications",
        "max_recent_observation_refs",
        "signed_source",
        "allow_environment_actions",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("observation source manifest fields do not match contract")
    if manifest["version"] != SOURCE_MANIFEST_VERSION:
        raise ValueError("unsupported observation source manifest version")
    normalized = deepcopy(manifest)
    normalized["source_id"] = _bounded(manifest["source_id"], "source_id")
    normalized["observation_schema"] = _bounded(
        manifest["observation_schema"], "observation_schema"
    )
    normalized["recorder_version"] = _bounded(
        manifest["recorder_version"], "recorder_version"
    )
    if manifest["source_kind"] != "public_observation_stream":
        raise ValueError("source kind must be public_observation_stream")
    if manifest["provenance_mode"] != "hash_chained_unsigned":
        raise ValueError("v1 integration supports hash_chained_unsigned provenance only")
    if manifest["cumulative_publications"] is not True:
        raise ValueError("v1 integration requires cumulative publications")
    if manifest["max_recent_observation_refs"] != 64:
        raise ValueError("v1 integration requires the existing 64-ref evidence bound")
    if manifest["signed_source"] is not False:
        raise ValueError("v1 does not claim a signed observation source")
    if manifest["allow_environment_actions"] is not False:
        raise ValueError("observation source cannot grant environment action authority")
    return normalized


def source_manifest_hash(manifest: dict[str, Any]) -> str:
    return _canonical_hash(validate_source_manifest(manifest))


def validate_publication(
    publication: dict[str, Any],
    manifest: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    checked_manifest = validate_source_manifest(manifest)
    checked_policy = validate_policy(policy)
    required = {
        "version",
        "source_id",
        "source_manifest_hash",
        "chain_hash",
        "coverage",
        "observation_refs",
        "selected_temporal_candidate",
    }
    if not isinstance(publication, dict) or set(publication) != required:
        raise ValueError("recorder publication fields do not match contract")
    if publication["version"] != PUBLICATION_VERSION:
        raise ValueError("unsupported recorder publication version")
    if publication["source_id"] != checked_manifest["source_id"]:
        raise ValueError("publication source does not match source manifest")
    expected_manifest_hash = _canonical_hash(checked_manifest)
    if publication["source_manifest_hash"] != expected_manifest_hash:
        raise ValueError("publication source manifest hash mismatch")
    if not isinstance(publication["chain_hash"], str) or not _HEX64.fullmatch(
        publication["chain_hash"]
    ):
        raise ValueError("publication chain hash must be sha256 hex")

    coverage = publication["coverage"]
    if not isinstance(coverage, dict) or set(coverage) != {"start_cycle", "end_cycle"}:
        raise ValueError("publication coverage fields do not match contract")
    start = coverage["start_cycle"]
    end = coverage["end_cycle"]
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError("publication coverage must be a positive contiguous prefix")

    refs = publication["observation_refs"]
    source_prefix = checked_manifest["source_id"] + ":"
    if (
        not isinstance(refs, list)
        or not refs
        or len(refs) > checked_manifest["max_recent_observation_refs"]
        or len(refs) != len(set(refs))
        or any(
            not isinstance(ref, str)
            or not ref.startswith(source_prefix)
            or len(ref) > 180
            for ref in refs
        )
    ):
        raise ValueError("publication observation refs do not match source/bounds")

    candidate = publication["selected_temporal_candidate"]
    candidate_fields = {
        "relation",
        "feature",
        "objective",
        "objective_score",
        "evaluable",
        "confirmations",
        "refutations",
    }
    if not isinstance(candidate, dict) or set(candidate) != candidate_fields:
        raise ValueError("selected temporal candidate fields do not match contract")
    relation = candidate["relation"]
    if relation not in checked_policy["allowed_relations"]:
        raise ValueError("publication relation is not allowed by policy")
    feature = _bounded(candidate["feature"], "selected feature")
    if candidate["objective"] != checked_policy["objective"]:
        raise ValueError("publication objective does not match frozen policy")
    score = candidate["objective_score"]
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise ValueError("publication objective score must be numeric")
    if not 0.0 <= float(score) <= 1.0:
        raise ValueError("publication objective score must be between 0 and 1")
    counts = {}
    for field in ("evaluable", "confirmations", "refutations"):
        value = candidate[field]
        if type(value) is not int or value < 0:
            raise ValueError(f"{field} must be a non-negative integer")
        counts[field] = value
    if counts["confirmations"] + counts["refutations"] != counts["evaluable"]:
        raise ValueError("publication temporal counts must partition evaluable")
    if counts["evaluable"] == 0 or counts["evaluable"] > end - start:
        raise ValueError("publication evaluable count exceeds covered transitions")

    normalized = deepcopy(publication)
    normalized["coverage"] = {"start_cycle": start, "end_cycle": end}
    normalized["observation_refs"] = list(refs)
    normalized["selected_temporal_candidate"] = {
        "relation": relation,
        "feature": feature,
        "objective": candidate["objective"],
        "objective_score": round(float(score), 6),
        **counts,
    }
    return normalized


class _MemoryStore:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = deepcopy(state)

    def load(self) -> dict[str, Any]:
        return deepcopy(self.state)

    def save(self, state: dict[str, Any]) -> None:
        self.state = deepcopy(state)


def _candidate_id(
    source_id: str,
    manifest_hash: str,
    publication: dict[str, Any],
) -> str:
    candidate = publication["selected_temporal_candidate"]
    source_hash = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
    publication_hash = _canonical_hash(publication)
    feature_hash = hashlib.sha256(candidate["feature"].encode("utf-8")).hexdigest()
    relation = "same" if candidate["relation"] == "same_next_observation" else "change"
    return (
        f"NIC:integration:{source_hash[:10]}:{manifest_hash[:10]}:"
        f"{publication_hash[:10]}:{feature_hash[:10]}:{relation}"
    )


def _relation(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": candidate["relation"],
        "feature": candidate["feature"],
        "action": None,
        "comparison_status": "not_applicable",
    }


def stage_publication_inquiry(
    core: AgentCore,
    *,
    policy: dict[str, Any],
    source_manifest: dict[str, Any],
    publication: dict[str, Any],
) -> dict[str, Any]:
    checked_policy = validate_policy(policy)
    if not checked_policy["enabled"]:
        raise RuntimeError("observe/inquire integration policy is off")
    checked_manifest = validate_source_manifest(source_manifest)
    checked_publication = validate_publication(
        publication,
        checked_manifest,
        checked_policy,
    )
    manifest_hash = _canonical_hash(checked_manifest)
    source_id = checked_manifest["source_id"]
    source_hash = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
    candidate_id = _candidate_id(source_id, manifest_hash, checked_publication)
    loaded = core.store.load()

    existing = next(
        (
            experiment
            for experiment in loaded.get("experiments", [])
            if experiment.get("native_inquiry_candidate_id") == candidate_id
        ),
        None,
    )
    if existing is not None:
        return {
            "status": "already_staged",
            "candidate_id": candidate_id,
            "source_manifest_hash": manifest_hash,
            "publication_hash": _canonical_hash(checked_publication),
            "experiment": deepcopy(existing),
            "state": deepcopy(loaded),
        }

    relation = _relation(checked_publication["selected_temporal_candidate"])
    source_prefix = f"NIC:integration:{source_hash[:10]}:"
    for experiment in loaded.get("experiments", []):
        if experiment.get("status") != "proposed":
            continue
        existing_id = str(experiment.get("native_inquiry_candidate_id") or "")
        native = experiment.get("native_inquiry")
        existing_relation = native.get("relation") if isinstance(native, dict) else None
        if (
            existing_id.startswith(source_prefix)
            and isinstance(existing_relation, dict)
            and existing_relation.get("feature") == relation["feature"]
        ):
            raise RuntimeError(
                "active inquiry already owns this cumulative source feature"
            )

    memory = _MemoryStore(loaded)
    staged_core = AgentCore(memory)
    candidate = checked_publication["selected_temporal_candidate"]
    evidence = {
        "version": NATIVE_EVIDENCE_V2_VERSION,
        "relation": relation,
        "observation_refs": list(checked_publication["observation_refs"]),
        "measurement_kind": "binary_transition_outcomes",
        "measurement": {
            "evaluable": candidate["evaluable"],
            "confirmations": candidate["confirmations"],
            "refutations": candidate["refutations"],
        },
    }
    evidence_result = staged_core.record_native_evidence(
        evidence,
        enabled=True,
        persist=True,
    )

    stable = candidate["relation"] == "same_next_observation"
    inquiry = {
        "version": NATIVE_INQUIRY_VERSION,
        "id": candidate_id,
        "objective": candidate["objective"],
        "objective_score": candidate["objective_score"],
        "relation": relation,
        "question": (
            f"For source {source_id}, what next public observation would most "
            f"directly test whether {candidate['feature']} "
            f"{'remains stable' if stable else 'changes'}?"
        ),
        "hypothesis": (
            f"Within public source {source_id}, observed {candidate['feature']} "
            f"tends to {'remain stable' if stable else 'change'} across "
            "consecutive evaluable observations."
        ),
        "method": (
            f"Collect one later public {candidate['feature']} observation from "
            f"the same source identity and compare it with the prior evaluable value."
        ),
        "falsification": (
            f"A later evaluable {candidate['feature']} value that "
            f"{'differs' if stable else 'remains the same'} counts against "
            "this temporal hypothesis."
        ),
        "predicted_observation": (
            f"The next evaluable {candidate['feature']} observation from "
            f"{source_id} {'matches' if stable else 'differs from'} the prior value."
        ),
        "evidence_refs": [evidence_result["evidence_ref"]],
    }
    inquiry_result = staged_core.propose_native_inquiry(
        inquiry,
        enabled=True,
        persist=True,
    )
    staged_state = memory.load()

    if checked_policy["persist_evidence"] and checked_policy["persist_inquiry"]:
        core.store.save(staged_state)
    else:
        raise RuntimeError("enabled v1 integration requires atomic persistence")

    return {
        "status": "staged",
        "candidate_id": candidate_id,
        "source_identity_hash": source_hash,
        "source_manifest_hash": manifest_hash,
        "publication_hash": _canonical_hash(checked_publication),
        "publication_chain_hash": checked_publication["chain_hash"],
        "source_id": source_id,
        "evidence_result": evidence_result,
        "inquiry_result": inquiry_result,
        "state": deepcopy(staged_state),
    }
